#!/usr/bin/env python3
"""
네이버 홈판 최적화 크로스포스팅 runner
────────────────────────────────────────
ggultongmon atom.xml → Claude 홈판 포맷 생성 → 네이버 발행

흐름:
1. atom.xml에서 미발행 최신 포스팅 1개 선택
2. 원본 포스트에서 상품/주제 파싱
3. generate_naver_post.py로 홈판 최적화 본문 생성
4. post_to_naver_simple.py로 발행
"""
import os, sys, json, re, time, subprocess, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

BASE_DIR   = Path(__file__).parent.parent
ATOM_URL   = "https://ggultongmon.allsweep.xyz/atom.xml"
LOG_FILE   = BASE_DIR / "results" / "naver_homefeed_posts.jsonl"
LOCK_FILE  = Path("/tmp/naver_homefeed.lock")
MAX_AGE_DAYS = 7


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_published() -> set:
    if not LOG_FILE.exists():
        return set()
    urls = set()
    for line in LOG_FILE.read_text().splitlines():
        try:
            d = json.loads(line)
            if d.get("original_url"):
                urls.add(d["original_url"])
        except Exception:
            pass
    return urls


def fetch_atom() -> list:
    req = urllib.request.Request(ATOM_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        xml_data = r.read()
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)

    now = datetime.now(timezone.utc)
    posts = []
    for entry in entries:
        url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("rel") == "alternate":
                url = link.attrib.get("href", "")
                break
        if not url:
            continue
        title = entry.findtext("atom:title", namespaces=ns) or ""
        published = entry.findtext("atom:published", namespaces=ns) or ""
        content = entry.findtext("atom:content", namespaces=ns) or ""

        # 날짜 파싱
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age_days = (now - pub_dt).days
            if age_days > MAX_AGE_DAYS:
                continue
        except Exception:
            pass

        posts.append({"url": url, "title": title, "content": content, "published": published})

    return posts


def parse_products_from_content(content: str) -> list:
    """atom 콘텐츠에서 상품 정보 파싱"""
    products = []
    # 상품명 패턴 (h3, 제품명 등)
    # 쿠팡 링크 패턴
    coupang_links = re.findall(r'href=["\']([^"\']*coupang\.com[^"\']*)["\']', content)
    # 가격 패턴
    prices = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*원', content)
    # 상품명 — img alt 또는 strong 태그 내용
    names = re.findall(r'alt=["\']([^"\']{5,50})["\']', content)

    for i in range(min(3, len(coupang_links))):
        products.append({
            "name": names[i] if i < len(names) else f"상품{i+1}",
            "price": f"{prices[i]}원" if i < len(prices) else "",
            "coupang_url": coupang_links[i],
        })
    return products


def run_post(post: dict) -> bool:
    log(f"  홈판 포스트 생성 시작: {post['title'][:50]}")

    products = parse_products_from_content(post['content'])
    log(f"  상품 파싱: {len(products)}개")

    # 1. 네이버 홈판 포맷 본문 생성
    body_output = f"/tmp/naver_hf_body_{int(time.time())}.txt"
    env = {
        **os.environ,
        "TOPIC":        post['title'],
        "PRODUCTS_JSON": json.dumps(products, ensure_ascii=False),
        "POST_URL":     post['url'],
        "GITHUB_OUTPUT": f"/tmp/naver_hf_out_{int(time.time())}.txt",
    }
    r = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "generate_naver_post.py")],
        env=env, capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        log(f"  ❌ 본문 생성 실패: {r.stderr[:200]}")
        return False

    # 출력에서 제목/본문 파일 경로 추출
    title = ""
    body_path = ""
    for line in r.stdout.split('\n'):
        if line.startswith('[네이버 포스트 생성]'):
            continue
        if '제목' in line and '===':
            pass
        if line.startswith('naver_title='):
            pass

    # GITHUB_OUTPUT 파일 읽기
    out_file = env["GITHUB_OUTPUT"]
    if Path(out_file).exists():
        for line in Path(out_file).read_text().splitlines():
            if line.startswith("naver_title="):
                title = line[len("naver_title="):]
            elif line.startswith("naver_body_path="):
                body_path = line[len("naver_body_path="):]

    if not title or not body_path or not Path(body_path).exists():
        log(f"  ❌ 제목 또는 본문 파일 없음 (title={title}, body_path={body_path})")
        log(f"  stdout: {r.stdout[-500:]}")
        return False

    body_chars = len(Path(body_path).read_text())
    log(f"  본문 생성 완료: 제목={title[:40]} / {body_chars}자")

    # 2. 네이버 발행
    env2 = {
        **os.environ,
        "NAVER_TITLE":     title,
        "NAVER_BODY_PATH": body_path,
        "DISPLAY":         ":99",
    }
    r2 = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "post_to_naver_api.py")],
        env=env2, capture_output=False, timeout=300
    )

    # 발행 성공 여부 로그 파일로 확인
    if r2.returncode == 0:
        # 로그 파일에서 최신 성공 URL 확인
        simple_log = BASE_DIR / "results" / "naver_simple_posts.jsonl"
        if simple_log.exists():
            last = simple_log.read_text().splitlines()[-1]
            d = json.loads(last)
            if d.get("success"):
                # homefeed 로그에도 기록
                LOG_FILE.parent.mkdir(exist_ok=True)
                with open(LOG_FILE, "a") as f:
                    f.write(json.dumps({
                        "original_url": post['url'],
                        "original_title": post['title'],
                        "naver_title": title,
                        "naver_url": d.get("naver_url", ""),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }, ensure_ascii=False) + "\n")
                log(f"  ✅ 발행 성공: {d.get('naver_url','')}")
                return True
    log(f"  ❌ 발행 실패 (returncode={r2.returncode})")
    return False


def main():
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < 600:
            log("이미 실행 중 (lock 파일 존재)")
            return
        LOCK_FILE.unlink()

    LOCK_FILE.touch()
    try:
        log("=== 네이버 홈판 크로스포스팅 시작 ===")
        published = load_published()
        log(f"이미 발행된 포스팅: {len(published)}개")

        posts = fetch_atom()
        log(f"atom.xml: {len(posts)}개 포스팅")

        # 미발행 포스팅 선택
        new_posts = [p for p in posts if p['url'] not in published]
        if not new_posts:
            log("발행할 새 포스팅 없음")
            return

        target = new_posts[0]
        log(f"발행 대상: {target['title'][:50]}")
        run_post(target)
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
