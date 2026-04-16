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

# .env 로드 (크론/subprocess 환경에서 환경변수 누락 방지)
try:
    _env_file = BASE_DIR / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            if _k and _k not in os.environ:
                os.environ[_k] = _v.strip()
except Exception:
    pass

ATOM_URL     = os.environ.get("GGULTONGMON_ATOM_URL", "https://ggultongmon.allsweep.xyz/atom.xml")
LOG_FILE     = BASE_DIR / "results" / "naver_posts.jsonl"
SCRIPT       = Path(__file__).parent / "post_to_naver_prosweep.py"
LOCK_FILE    = Path("/tmp/naver_cron.lock")
MAX_AGE_DAYS = 3   # 3일 이내 포스팅만 크로스포스팅


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── N-2-1: 네이버 제목 최적화 (40자 이내 압축) ──────────────────────
def optimize_naver_title(title: str, keyword: str = "") -> str:
    """ggultongmon 원본 제목을 40자 이내로 압축.
    
    원본 제목이 40자 이내면 그대로 사용.
    초과하면 핵심 키워드+연도+핵심 단어만 남겨 40자 이내로 압축.
    예: '아기 턱받이, 비싼 게 좋을까? 거즈·실리콘 TOP3 소재별 완전비교 2026'
        → '아기 턱받이 소재별 TOP3 비교 2026'
    """
    if not title:
        return title
    # 40자 이내면 그대로
    if len(title) <= 40:
        return title

    # 연도 추출 (2025, 2026 등)
    year_match = re.search(r'(20\d\d)', title)
    year_suffix = year_match.group(1) if year_match else ""

    # 핵심 주제어: 쉼표/물음표 이전 앞부분
    # ex) "아기 턱받이, 비싼 게 좋을까? 거즈·실리콘 TOP3 소재별 완전비교 2026"
    #   → subject = "아기 턱받이"
    subject_match = re.match(r'^([^,，?？!！]+)', title)
    subject = subject_match.group(1).strip() if subject_match else title[:12].strip()

    # 핵심 수식어 (중복 없이, TOP3/TOP5 등은 숫자 포함 하나로)
    modifiers = []
    # TOP+숫자
    top_match = re.search(r'TOP\s*(\d+)', title)
    if top_match:
        modifiers.append(f"TOP{top_match.group(1)}")
    # 단독 키워드 (순서대로, 중복 제외)
    for kw in ['소재별', '용량별', '성분별', '가성비', '추천', '비교', '완전비교', '선택법']:
        if kw in title and kw not in " ".join(modifiers):
            modifiers.append(kw)
            break  # 수식어는 1개만

    # 조합: 주제 + 수식어 + 연도
    parts = [subject]
    if modifiers:
        parts.append(" ".join(modifiers))
    if year_suffix:
        parts.append(year_suffix)

    compressed = " ".join(parts)
    # 40자 초과 시 강제 자르기 (단어 경계 고려)
    if len(compressed) > 40:
        compressed = compressed[:40].rsplit(' ', 1)[0]

    return compressed.strip() or title[:40]


# ── atom.xml 상품 섹션 파싱 ──────────────────────────────────────
def parse_product_sections(html: str) -> list:
    """h2 태그로 구분된 상품 섹션 파싱.
    
    반환: [{"name":..., "price":..., "link":..., "image":..., "desc":...}, ...]
    """
    EXCLUDE_KEYWORDS = [
        '선택기준', '선택 기준', '비교', 'FAQ', '마무리', '자주 묻는',
        '상황별', '조합', '안내', '정리', '한눈에', '결론',
    ]

    # 1. JSON-LD script 태그 제거
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 2. h2로 섹션 분리
    parts = re.split(r'<h2[^>]*>(.*?)</h2>', html, flags=re.DOTALL | re.IGNORECASE)

    products = []
    i = 1
    while i < len(parts) - 1:
        h2_raw = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ''
        h2_text = re.sub(r'<[^>]+>', '', h2_raw).strip()

        # 3. 제외 키워드 섹션 건너뜀
        skip = any(kw in h2_text for kw in EXCLUDE_KEYWORDS)
        if skip:
            i += 2
            continue

        # 4. 가격(원) 포함 여부로 상품 섹션 판별
        prices_in_body = re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+원)', body)
        if not prices_in_body:
            i += 2
            continue

        # 5. 첫 번째 쿠팡 링크
        links = re.findall(r'href=["\']+(https://link\.coupang\.com/[^"\'>\s]+)', body)
        first_link = links[0] if links else ''

        # 6. 첫 번째 coupangcdn 이미지
        imgs = re.findall(r'src=["\']([^"\'> ]+coupangcdn[^"\'> ]+)["\']', body)
        if not imgs:
            imgs = re.findall(r'src=["\']([^"\'> ]+coupang[^"\'> ]+)["\']', body)
        # ?w=300 같은 썸네일 파라미터 제거해 원본 이미지 URL 사용
        first_img = imgs[0].split('?')[0] if imgs else ''

        # 7. 텍스트 앞 150자 (HTML 태그 제거 후)
        plain = re.sub(r'<[^>]+>', '', body)
        plain = re.sub(r'\s+', ' ', plain).strip()
        desc = plain[:150].strip()

        # [규칙] 제품 링크는 반드시 shortenUrl(link.coupang.com/a/...) 사용 (노이반님 원칙)
        # AFFSDP URL(link.coupang.com/re/...) / raw URL 전달 금지
        safe_link = first_link if first_link and "link.coupang.com/a/" in first_link else ""

        products.append({
            'name': h2_text,
            'price': prices_in_body[0],
            'link': safe_link,
            'image': first_img,
            'desc': desc,
        })

        if len(products) >= 3:
            break
        i += 2

    return products


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
    반환 형식: [{"url":..., "title":..., "summary":..., "labels":[...],
                 "published":..., "images":[...], "product_data":[...]}]
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

        # content HTML 가져오기
        content_el = entry.find("atom:content", ns)
        content_raw = (content_el.text or "") if content_el is not None else ""

        # 요약 (JSON-LD script 제거 후)
        summary_el = entry.find("atom:summary", ns)
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        if not summary:
            clean_html = re.sub(r'<script[^>]*>.*?</script>', '', content_raw, flags=re.DOTALL | re.IGNORECASE)
            plain = re.sub(r'<[^>]+>', '', clean_html)
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

        # ── 상품 데이터 파싱 (핵심 개선) ─────────────────────────
        product_data = parse_product_sections(content_raw)

        # 상품 이미지 (product_data 우선, 없으면 기존 방식)
        if product_data:
            product_images = [p["image"] for p in product_data if p.get("image")][:3]
        else:
            img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content_raw)
            coupang_imgs = [u for u in img_urls if 'coupang' in u or 'thumbnail' in u]
            other_imgs = [u for u in img_urls if u not in coupang_imgs]
            product_images = (coupang_imgs + other_imgs)[:3]

        if product_data:
            log(f"  ✅ 상품 파싱 성공: {len(product_data)}개 — {[p['name'][:20] for p in product_data]}")

        posts.append({
            "url": url,
            "title": title,
            "summary": summary,
            "labels": labels,
            "published": published_str,
            "age_hours": round(age_sec / 3600, 1),
            "images": product_images,
            "product_data": product_data,   # ← 새로 추가
        })

    log(f"  {max_age_days}일 이내 포스팅: {len(posts)}개")
    return posts


def run_naver_post(post: dict) -> bool:
    """post_to_naver_prosweep.py 실행 — 환경변수 전달"""
    labels = post.get("labels", [])
    primary_keyword = labels[0] if labels else ""

    # 제목 40자 이내 압축 (잘린 채 반복 방지)
    optimized_title = optimize_naver_title(post["title"])
    if optimized_title != post["title"]:
        log(f"  📝 제목 압축: [{post['title'][:40]}] → [{optimized_title}]")

    # 상품 데이터 JSON 직렬화 (post_to_naver_prosweep.py에 전달)
    product_data = post.get("product_data", [])
    product_data_json = json.dumps(product_data, ensure_ascii=False) if product_data else ""

    env = os.environ.copy()
    env.update({
        "POST_TITLE":     optimized_title,
        "POST_URL":       post["url"],
        "POST_SUMMARY":   post["summary"],
        "LABELS":         ",".join(post["labels"][:7]),
        "COUPANG_IMAGES": "|".join(post.get("images", [])[:3]),
        "DISPLAY":        ":99",
        "NAVER_PRIMARY_KW":   primary_keyword,
        "NAVER_MIN_HEADINGS": "5",
        "PRODUCT_DATA":   product_data_json,    # ← 새로 추가: 상품 데이터 JSON
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
