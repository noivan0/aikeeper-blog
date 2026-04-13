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
ATOM_URL   = os.environ.get("GGULTONGMON_ATOM_URL", "https://ggultongmon.allsweep.xyz/atom.xml")
LOG_FILE   = BASE_DIR / "results" / "naver_homefeed_posts.jsonl"
LOCK_FILE  = Path("/tmp/naver_homefeed.lock")
MAX_AGE_DAYS = int(os.environ.get("NAVER_MAX_AGE_DAYS", "7"))


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
    coupang_links = re.findall(r'href=["\']([^"\']*coupang\.com[^"\']*)["\']', content)
    prices = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*원', content)
    names = re.findall(r'alt=["\']([^"\']{5,50})["\']', content)

    for i in range(min(3, len(coupang_links))):
        products.append({
            "name": names[i] if i < len(names) else f"상품{i+1}",
            "price": f"{prices[i]}원" if i < len(prices) else "",
            "coupang_url": coupang_links[i],
        })
    return products


def enrich_products_with_extra_images(products: list, topic: str) -> list:
    """
    상품 목록에 관련 추가 상품을 보강 (이미지 밀도 6개+ 목표).
    전략: 같은 키워드로 관련 상품 검색 → 기존 products에 최대 3개 추가
    총 상품 수 5~6개 → 링크 2회씩 = 이미지+OG카드 10~12개
    """
    try:
        from coupang_api import search_products
        # 기존 상품이 이미 3개이면 스킵
        if len(products) >= 3:
            log(f"  이미지 보강: 기존 상품 {len(products)}개 (충분)")
            return products

        keyword = re.sub(r'[^\w\s]', '', topic).strip()[:20]
        result  = search_products(keyword, limit=8)
        extras  = result.get("productData", [])

        existing_names = {p.get("name","") for p in products}
        added = 0
        for e in extras:
            pname = e.get("productName","")
            purl  = e.get("productUrl","")
            pimg  = e.get("productImage","")
            pprice = e.get("productPrice","")
            if pname and purl and pname not in existing_names:
                products.append({
                    "name": pname[:40],
                    "productName": pname,
                    "price": f"{pprice}원" if pprice else "",
                    "coupang_url": purl,
                    "shortenUrl": purl,
                    "productImage": pimg,
                })
                existing_names.add(pname)
                added += 1
            if len(products) >= 4:
                break

        log(f"  이미지 보강: +{added}개 추가 상품 (총 {len(products)}개)")
        return products
    except Exception as e:
        log(f"  [WARN] 이미지 보강 실패 (무시): {e}")
        return products


def run_post(post: dict) -> bool:
    log(f"  홈판 포스트 생성 시작: {post['title'][:50]}")

    products = parse_products_from_content(post['content'])
    log(f"  상품 파싱: {len(products)}개")
    # 상품이 2개 미만이면 관련 상품 추가 검색 (이미지 밀도 확보)
    if len(products) < 3:
        products = enrich_products_with_extra_images(products, post['title'])

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

    # GITHUB_OUTPUT 파일 읽기
    title = ""
    body_path = ""
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
    # productImage URL 목록 → 추가 이미지로 전달
    extra_imgs = [p.get("productImage","") for p in products if p.get("productImage","")]
    env2 = {
        **os.environ,
        "NAVER_TITLE":        title,
        "NAVER_BODY_PATH":    body_path,
        "DISPLAY":            ":99",
        "EXTRA_IMAGE_URLS":   json.dumps(extra_imgs[:4], ensure_ascii=False),
    }
    r2 = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "post_to_naver_api.py")],
        env=env2, capture_output=True, text=True, timeout=300
    )
    # stdout을 로그에도 출력
    if r2.stdout:
        print(r2.stdout)
    if r2.stderr:
        print(r2.stderr)

    # 발행 성공 여부를 stdout에서 URL 직접 추출
    naver_url = ""
    if r2.returncode == 0:
        # stdout에서 발행된 네이버 URL 추출
        _url_match = re.search(r'https?://blog\.naver\.com/\S+', r2.stdout)
        if _url_match:
            naver_url = _url_match.group(0).rstrip(".,;)")

    if r2.returncode == 0 and naver_url:
        # homefeed 로그에 기록
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "original_url": post['url'],
                "original_title": post['title'],
                "naver_title": title,
                "naver_url": naver_url,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False) + "\n")
        log(f"  ✅ 발행 성공: {naver_url}")
        return True
    elif r2.returncode == 0:
        # URL을 찾지 못했지만 returncode는 0 — 로그 파일로 fallback
        simple_log = BASE_DIR / "results" / "naver_simple_posts.jsonl"
        if simple_log.exists():
            lines = simple_log.read_text().splitlines()
            if lines:
                try:
                    d = json.loads(lines[-1])
                    if d.get("success"):
                        naver_url = d.get("naver_url", "")
                        LOG_FILE.parent.mkdir(exist_ok=True)
                        with open(LOG_FILE, "a") as f:
                            f.write(json.dumps({
                                "original_url": post['url'],
                                "original_title": post['title'],
                                "naver_title": title,
                                "naver_url": naver_url,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            }, ensure_ascii=False) + "\n")
                        log(f"  ✅ 발행 성공 (로그파일 확인): {naver_url}")
                        return True
                except Exception:
                    pass
        log(f"  ⚠️  returncode=0이나 URL 미확인 — 성공 처리")
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
