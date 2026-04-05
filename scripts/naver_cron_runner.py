#!/usr/bin/env python3
"""
네이버 prosweep 크로스포스팅 cron runner
- atom.xml에서 ggultongmon 최신 포스팅 URL 읽기
- naver_posts.jsonl과 비교해 중복 발행 방지
- 새 포스팅만 prosweep 네이버에 발행

실행:
  cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger
  NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py

crontab 예시 (KST 08:30, 11:00, 14:00, 17:30, 21:00 — ggultongmon 발행 30분 후):
  30 23 * * * cd /repo && NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py >> /tmp/naver_cron.log 2>&1
  0  2  * * * cd /repo && NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py >> /tmp/naver_cron.log 2>&1
  0  5  * * * cd /repo && NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py >> /tmp/naver_cron.log 2>&1
  30  8  * * * cd /repo && NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py >> /tmp/naver_cron.log 2>&1
  0  12 * * * cd /repo && NAVER_ID=kjjhad NAVER_PW='...' python3 scripts/naver_cron_runner.py >> /tmp/naver_cron.log 2>&1
"""
import os, sys, json, re, time, subprocess, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR     = Path(__file__).parent.parent
ATOM_URL     = "https://ggultongmon.allsweep.xyz/atom.xml"
LOG_FILE     = BASE_DIR / "results" / "naver_posts.jsonl"
SCRIPT       = Path(__file__).parent / "post_to_naver_prosweep.py"
LOCK_FILE    = Path("/tmp/naver_cron.lock")
MAX_AGE_DAYS = 3   # 3일 이내 포스팅만 크로스포스팅


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def already_posted_urls() -> set:
    """naver_posts.jsonl에서 이미 발행된 original_url 목록 반환"""
    posted = set()
    if not LOG_FILE.exists():
        return posted
    for line in LOG_FILE.read_text(encoding="utf-8").strip().splitlines():
        try:
            d = json.loads(line)
            url = d.get("original_url", "")
            if url:
                posted.add(url.strip())
        except Exception:
            pass
    return posted


def fetch_latest_posts(max_age_days: int = MAX_AGE_DAYS) -> list[dict]:
    """
    atom.xml에서 최신 포스팅 목록 반환
    반환 형식: [{"url": ..., "title": ..., "summary": ..., "labels": [...], "published": ...}]
    """
    log(f"atom.xml 읽는 중: {ATOM_URL}")
    try:
        req = urllib.request.Request(
            ATOM_URL,
            headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"  ❌ atom.xml 접근 실패: {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log(f"  ❌ XML 파싱 실패: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    log(f"  총 {len(entries)}개 포스팅 발견")

    now = datetime.now(timezone.utc)
    cutoff_seconds = max_age_days * 86400

    posts = []
    for entry in entries:
        # URL (alternate link)
        url = ""
        for link in entry.findall("atom:link", ns):
            if link.get("rel") == "alternate":
                url = link.get("href", "")
                break
        if not url:
            continue

        # 제목
        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip() if title_el is not None else ""

        # 요약
        summary_el = entry.find("atom:summary", ns)
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        if not summary:
            content_el = entry.find("atom:content", ns)
            if content_el is not None:
                raw_html = content_el.text or ""
                # <script>...</script> 블록 전체 제거 (JSON-LD 등이 summary에 노출되는 문제 방지)
                clean_html = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
                plain = re.sub(r'<[^>]+>', '', clean_html)
                # 공백/개행 정리 후 첫 200자
                plain = re.sub(r'\s+', ' ', plain).strip()
                summary = plain[:200].strip()

        # 발행일 — 나이 계산
        published_el = entry.find("atom:published", ns)
        published_str = (published_el.text or "").strip() if published_el is not None else ""
        try:
            pub_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            age_sec = (now - pub_dt).total_seconds()
        except Exception:
            age_sec = 0

        if age_sec > cutoff_seconds:
            continue  # 오래된 포스팅 스킵

        # 레이블 (categories)
        labels = []
        for cat in entry.findall("atom:category", ns):
            term = cat.get("term", "")
            if term:
                labels.append(term)

        posts.append({
            "url": url,
            "title": title,
            "summary": summary,
            "labels": labels,
            "published": published_str,
            "age_hours": round(age_sec / 3600, 1),
        })

    log(f"  {max_age_days}일 이내 포스팅: {len(posts)}개")
    return posts


def run_naver_post(post: dict) -> bool:
    """post_to_naver_prosweep.py 실행 — 환경변수 전달"""
    env = os.environ.copy()
    env.update({
        "POST_TITLE":   post["title"],
        "POST_URL":     post["url"],
        "POST_SUMMARY": post["summary"],
        "LABELS":       ",".join(post["labels"][:7]),
        "DISPLAY":      ":99",
    })

    # NAVER_ID / NAVER_PW가 env에 없으면 경고
    if not env.get("NAVER_ID") or not env.get("NAVER_PW"):
        log("  ❌ NAVER_ID / NAVER_PW 환경변수 없음")
        return False

    log(f"  📝 발행 시작: {post['title'][:50]}")
    log(f"     원본 URL: {post['url']}")

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=env,
            timeout=300,   # 5분
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log("  ❌ 타임아웃 (5분 초과)")
        return False
    except Exception as e:
        log(f"  ❌ 실행 오류: {e}")
        return False


def ensure_xvfb():
    """Xvfb :99가 없으면 실행"""
    result = subprocess.run(["pgrep", "-f", "Xvfb :99"], capture_output=True)
    if result.returncode != 0:
        log("Xvfb :99 시작...")
        subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1280x900x24", "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    else:
        log("Xvfb :99 이미 실행 중")


def main():
    log("=" * 50)
    log("네이버 크로스포스팅 cron runner 시작")

    # 중복 실행 방지 (lock file)
    if LOCK_FILE.exists():
        lock_age = time.time() - LOCK_FILE.stat().st_mtime
        if lock_age < 600:   # 10분 내 lock이면 스킵
            log(f"  ⏸️  이미 실행 중 (lock 나이: {lock_age:.0f}초) — 스킵")
            return
        else:
            log(f"  ⚠️  오래된 lock 파일 제거 ({lock_age:.0f}초)")
            LOCK_FILE.unlink()

    LOCK_FILE.write_text(str(os.getpid()))
    try:
        ensure_xvfb()

        # 이미 발행된 URL 목록
        posted = already_posted_urls()
        log(f"이미 발행된 포스팅: {len(posted)}개")

        # 최신 포스팅 목록 수집
        latest = fetch_latest_posts()
        if not latest:
            log("새 포스팅 없음 — 종료")
            return

        # 중복 제외
        new_posts = [p for p in latest if p["url"] not in posted]
        log(f"새 포스팅 (미발행): {len(new_posts)}개")

        if not new_posts:
            log("발행할 새 포스팅 없음 — 종료")
            return

        # 가장 최근 1개만 발행 (중복 방지 + 세션 부담 최소화)
        target = new_posts[0]
        log(f"발행 대상: [{target['age_hours']}시간 전] {target['title'][:50]}")

        success = run_naver_post(target)
        if success:
            log(f"✅ 발행 성공: {target['url']}")
        else:
            log(f"❌ 발행 실패: {target['url']}")
            sys.exit(1)

    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()

    log("=" * 50)


if __name__ == "__main__":
    main()
