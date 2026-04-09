"""
꿀통몬스터 블로그 → Blogger 포스팅
- 쿠팡 상품 수집 + 포스트 생성 + Blogger API 발행
"""
import os, sys, json, re, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

# .env 로드 — 크론/subprocess 환경에서 환경변수 누락 방지
try:
    _env_file = BASE_DIR / ".env"
    if _env_file.exists():
        for _line in _env_file.read_text(encoding='utf-8').splitlines():
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line:
                continue
            _k, _v = _line.split('=', 1)
            _k = _k.strip()
            if _k and _k not in os.environ:
                os.environ[_k] = _v.strip()
except Exception:
    pass

from coupang_api import get_products_with_shorten
from generate_post_ggultongmon import generate_post, build_full_html

# ── 환경변수 ──────────────────────────────────────────────────────
TOPIC           = os.environ.get("TOPIC", "에어프라이어 가성비 추천 TOP5")
SEARCH_KW       = os.environ.get("SEARCH_KW") or os.environ.get("search_keyword", "에어프라이어")
ANGLE           = os.environ.get("ANGLE", "")
LABELS_STR      = os.environ.get("LABELS") or os.environ.get("labels", "에어프라이어 추천,에어프라이어 가성비")
META_DESC       = os.environ.get("META_DESC") or os.environ.get("meta_desc", "")
CATEGORY        = os.environ.get("CATEGORY") or os.environ.get("category", "")
BLOG_ID         = os.environ.get("TARGET_BLOG_ID", "4422596386410826373")
PRODUCTS_JSON   = os.environ.get("PRODUCTS_JSON") or os.environ.get("products_json", "")

BLOGGER_CLIENT_ID     = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]

LABELS = [l.strip() for l in LABELS_STR.split(",") if l.strip()]

def get_oauth_token() -> str:
    data = urllib.parse.urlencode({
        "client_id":     BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def publish_to_blogger(title: str, html: str, labels: list, token: str) -> dict:
    # Blogger API는 제목에 큰따옴표 등 특수문자가 있으면 400 반환 → 치환
    safe_title = (title
                  .replace('"', "'")
                  .replace('\u201c', "'").replace('\u201d', "'")  # 좌우 큰따옴표
                  .replace('\u300c', "").replace('\u300d', "")    # 일본어 괄호
                  .strip())
    # HTML 본문 제어문자 제거 (null bytes, BOM 등 → Blogger badRequest 원인)
    import re as _re
    safe_html = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', html)
    safe_html = safe_html.replace('\ufeff', '')  # BOM 제거

    # 라벨: 포스팅 내용에 맞는 것으로 최대 3개
    safe_labels = labels[:3]

    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    body = json.dumps({
        "title": safe_title,
        "content": safe_html,
        "labels": safe_labels,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8",
    })
    import time as _time
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')[:500]
            if e.code == 429:
                wait = 60 * (attempt + 1)  # 60초 → 120초 → 180초
                print(f"[WARN] Blogger API 429 Rate Limit — {wait}초 대기 후 재시도 ({attempt+1}/3)")
                _time.sleep(wait)
                # 토큰 만료 대비 req 재생성
                req = urllib.request.Request(url, data=body, method="POST", headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json;charset=UTF-8",
                })
                continue
            print(f"[ERROR] Blogger API {e.code}: {err_body}")
            raise
    raise RuntimeError("Blogger API 429 — 3회 재시도 모두 실패")


def save_markdown(title: str, content: str, labels: list, products: list) -> Path:
    """GitHub 백업용 마크다운 저장"""
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    slug = re.sub(r'[^\w가-힣]', '-', title)[:40].strip('-')
    posts_dir = Path(os.environ.get("POSTS_OUTPUT_DIR", BASE_DIR / "posts-ggultongmon"))
    posts_dir.mkdir(parents=True, exist_ok=True)
    
    product_links = "\n".join(
        f"- [{p['productName'][:40]}]({p.get('shortenUrl', '#')}) — {p['productPrice']:,}원"
        for p in products
    )
    
    md_path = posts_dir / f"{today}-{slug}.md"
    md_path.write_text(
        f"---\ntitle: \"{title}\"\nlabels: {json.dumps(labels, ensure_ascii=False)}\n"
        f"date: {today}\nblog: ggultongmon\n---\n\n{content}\n\n"
        f"## 추천 상품 링크\n{product_links}\n",
        encoding="utf-8"
    )
    return md_path


def main():
    # 주제가 비어있으면 발행 의미 없음 — 조기 종료
    if not TOPIC or len(TOPIC.strip()) < 5:
        print(f"[SKIP] 주제(TOPIC)가 비어있음 — 발행 건너뜀")
        sys.exit(0)
    print(f"[INFO] 주제: {TOPIC}")
    print(f"[INFO] 검색 키워드: {SEARCH_KW}")
    
    # 1. 상품 수집 (bestcategories 결과 우선, 없으면 키워드 검색 fallback)
    if PRODUCTS_JSON:
        try:
            products = json.loads(PRODUCTS_JSON)
            # rank 필드 정규화
            for i, p in enumerate(products):
                p.setdefault("rank", i + 1)
                p["productPrice"] = int(float(p.get("productPrice", 0)))
            print(f"[INFO] bestcategories 상품 {len(products)}개 사용")
        except Exception as e:
            print(f"[WARN] products_json 파싱 실패 ({e}), 키워드 검색으로 fallback")
            products = get_products_with_shorten(SEARCH_KW, limit=5)
    else:
        print(f"[INFO] 쿠팡 상품 검색: {SEARCH_KW}")
        products = get_products_with_shorten(SEARCH_KW, limit=5)

    print(f"[INFO] 상품 {len(products)}개 준비 완료")
    for p in products:
        print(f"       [{p.get('rank','-')}] {p['productName'][:40]} / {int(p['productPrice']):,}원 / {p.get('shortenUrl','')[:50]}")
    
    # 2. 포스트 생성
    print(f"[INFO] Claude 포스트 생성 중...")
    post_data = generate_post(
        topic=TOPIC,
        search_keyword=SEARCH_KW,
        products=products,
        angle=ANGLE,
        meta_desc=META_DESC,
    )
    title = post_data["title"]
    # 제목이 비어있거나 이상하면 TOPIC으로 fallback (빈 제목 → Blogger가 JSON-LD 첫줄을 slug로 사용하는 버그 방지)
    if not title or len(title.strip()) < 5 or title.strip().startswith(("{", "@", "<", "http")):
        print(f"[WARN] 제목 파싱 실패 ('{title[:30]}'), TOPIC으로 대체")
        title = TOPIC
    title = title.strip()
    # 큰따옴표 → 작은따옴표 (Blogger API 400 방지)
    title = (title
             .replace('"', "'")
             .replace('\u201c', "'").replace('\u201d', "'")
             .replace('\u0022', "'").replace('\u02ba', "'"))
    # TOPIC까지 빈 경우 발행 중단 (빈 제목 포스트 방지)
    if not title or len(title.strip()) < 5:
        print(f"[ERROR] 제목을 확정할 수 없음 — 발행 중단")
        sys.exit(1)
    print(f"[INFO] 파싱 완료: {title}")
    print(f"[INFO] 글자수: {post_data['char_count']:,}자")
    
    # 3. HTML 빌드
    html = build_full_html(
        title=title,
        content=post_data["content"],
        products=products,
        labels=LABELS,
        meta_desc=META_DESC or post_data.get("meta_desc", ""),
        faq_raw=post_data.get("faq_raw", ""),
        current_url="",       # 발행 전이라 URL 미확정; atom.xml에서 자동 제외 불필요
        category=CATEGORY,
    )

    # 4. Blogger 토큰 획득 (내부링크 + 발행 공용)
    print(f"[INFO] Blogger 발행 중...")
    token = get_oauth_token()

    # 4-1. 내부링크 (연관글 카드) 삽입 — 꿀통몬스터 블로그 포스트만 참조
    try:
        from internal_links import add_internal_links
        html, related = add_internal_links(
            html,
            current_title=title,
            current_labels=LABELS,
            current_url="",   # 발행 전이라 URL 미확정
            token=token,
            verbose=True,
            blog_id=BLOG_ID,                          # 꿀통몬스터 ID 명시 전달
            blog_url="https://ggultongmon.allsweep.xyz",
        )
        if related:
            print(f"[INFO] 연관글 {len(related)}개 삽입 완료")
    except Exception as e:
        print(f"[INFO] 연관글 스킵 (비치명적): {e}")

    # 발행 직전 토큰 재발급 (내부링크 처리 중 만료 방지)
    token = get_oauth_token()
    result = publish_to_blogger(title, html, LABELS, token)
    post_url = result.get("url", "")
    print(f"✅ 포스팅 완료: {title}")
    print(f"   URL: {post_url}")
    
    # 4-1. 카드뉴스 자동 생성 (비치명적 — 실패해도 포스팅은 완료)
    if post_url:
        try:
            sys.path.insert(0, str(BASE_DIR / "instagram"))
            from carousel_auto import generate_carousel
            carousel_result = generate_carousel(
                post_url=post_url,
                topic=TOPIC,
                products=products,
            )
            print(f"  ✅ 카드뉴스 생성 완료: {carousel_result['out_dir']}")
            print(f"     슬라이드 {len(carousel_result['slides'])}장")
            os.environ["CAROUSEL_OUT_DIR"] = str(carousel_result["out_dir"])

            # 4-2. Instagram 자동 업로드 (비치명적)
            try:
                sys.path.insert(0, str(BASE_DIR / "instagram"))
                from upload_instagram import publish_carousel_from_dir
                caption = (
                    f"{TOPIC}\n\n"
                    f"쿠팡 추천 상품 링크는 프로필 참고\n"
                    f"블로그 상세 리뷰 → 프로필 링크\n\n"
                    f"#쿠팡추천 #가성비 #꿀통몬 #헬스보충제 #운동영양제"
                )
                ig_result = publish_carousel_from_dir(
                    slides_dir=carousel_result["out_dir"],
                    caption=caption,
                    topic=TOPIC,
                    post_url=post_url,
                )
                if ig_result.get("success"):
                    print(f"  ✅ Instagram 업로드 완료: {ig_result.get('permalink','')}")
                    # Instagram 업로드 시 사용된 GitHub Pages URL 저장 (litt.ly 이미지용)
                    os.environ["CAROUSEL_IMAGE_URLS"] = __import__("json").dumps(
                        ig_result.get("image_urls", [])
                    )
                else:
                    print(f"  ℹ️  Instagram 업로드 실패: {ig_result.get('error','')}")
            except Exception as _ie:
                print(f"  ℹ️  Instagram 업로드 스킵 (비치명적): {_ie}")

        except Exception as _ce:
            print(f"  ℹ️  카드뉴스 생성 스킵 (비치명적): {_ce}")

    # 4-3. litt.ly 상품 등록 (비치명적)
    # 상품 슬라이드 URL: Instagram 업로드 시 사용한 GitHub Pages URL에서
    # slide_03_product.jpg ~ slide_0N_product.jpg 를 상품 이미지로 활용
    carousel_dir = os.environ.get("CAROUSEL_OUT_DIR", "")
    if products and carousel_dir:
        try:
            import json as _json
            sys.path.insert(0, str(BASE_DIR / "instagram"))
            from upload_littly import LittlyClient

            # GitHub Pages에 올라간 이미지 URL 목록 (slide_03_product ~ slide_0N_product)
            _all_gh_urls = _json.loads(os.environ.get("CAROUSEL_IMAGE_URLS", "[]"))
            _prod_gh_urls = [u for u in _all_gh_urls if u and "product" in (u or "")]

            _littly_prods = []
            for i, p in enumerate(products):
                _littly_prods.append({
                    "title": p.get("productName", p.get("name", "상품")),
                    "url":   p.get("shortenUrl", p.get("coupang_url", p.get("url", ""))),
                    "tags":  LABELS[:3],   # 포스트 라벨을 강조 태그로 사용 (최대 3개)
                })

            lc = LittlyClient()
            lc.login()
            # public_urls로 GitHub Pages URL 전달 → S3 우회
            lc.register_products(_littly_prods, [None]*len(_littly_prods), public_urls=_prod_gh_urls)
            print(f"  ✅ litt.ly 상품 등록 완료: {len(_littly_prods)}개")
        except Exception as _le:
            print(f"  ℹ️  litt.ly 등록 스킵 (비치명적): {_le}")

    # 4-4. 텔레그램 상품 이미지 전달 (비치명적)
    if carousel_dir:
        try:
            import urllib.request as _ur, urllib.parse as _up
            _tg_token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            _tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "420793033")
            if _tg_token:
                from pathlib import Path as _P2
                # 상품 이미지 전송 (상품 수 기준 가변)
                _emoji_nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
                _prod_count = len(products) if products else 4
                _sent = 0
                for i in range(1, _prod_count + 1):
                    _img = _P2(carousel_dir) / f"_prod{i}.jpg"
                    if not _img.exists():
                        continue
                    _img_data = _img.read_bytes()
                    # 상품명 추출
                    _prod_name = products[i-1].get("productName", products[i-1].get("name", "")) if i-1 < len(products) else ""
                    _emoji = _emoji_nums[i-1] if i-1 < len(_emoji_nums) else f"{i}."
                    _photo_caption = f"{_emoji} {_prod_name}"
                    _boundary = "----FormBoundary7MA4YWxkTrZu0gW"
                    _body = (
                        f"--{_boundary}\r\n"
                        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
                        f"{_tg_chat_id}\r\n"
                        f"--{_boundary}\r\n"
                        f'Content-Disposition: form-data; name="caption"\r\n\r\n'
                        f"{_photo_caption}\r\n"
                        f"--{_boundary}\r\n"
                        f'Content-Disposition: form-data; name="photo"; filename="_prod{i}.jpg"\r\n'
                        f"Content-Type: image/jpeg\r\n\r\n"
                    ).encode() + _img_data + f"\r\n--{_boundary}--\r\n".encode()
                    _req = _ur.Request(
                        f"https://api.telegram.org/bot{_tg_token}/sendPhoto",
                        data=_body,
                        headers={"Content-Type": f"multipart/form-data; boundary={_boundary}"},
                        method="POST"
                    )
                    _ur.urlopen(_req, timeout=15)
                    _sent += 1
                # 포스트 링크 별도 메시지
                _caption = f"[꿀통몬] {TOPIC[:60]}\n{post_url}"
                _data = _up.urlencode({"chat_id": _tg_chat_id, "text": _caption}).encode()
                _ur.urlopen(_ur.Request(
                    f"https://api.telegram.org/bot{_tg_token}/sendMessage",
                    data=_data
                ), timeout=10)
                print(f"  ✅ 텔레그램 상품 이미지 전달 완료: {_sent}장")
        except Exception as _te:
            print(f"  ℹ️  텔레그램 전송 스킵 (비치명적): {_te}")

    # 4-5. Threads 스레드형 연속 포스팅 (비치명적)
    if products and post_url:
        try:
            sys.path.insert(0, str(BASE_DIR / "instagram"))
            from upload_threads import publish_thread
            _all_urls = json.loads(os.environ.get("CAROUSEL_IMAGE_URLS", "[]"))
            # product 슬라이드만 (slide_03_product, slide_04_product, slide_05_product)
            _prod_gh_urls = [u for u in _all_urls if u and "product" in u]
            _th_result = publish_thread(
                topic=TOPIC,
                products=products,
                image_urls=_prod_gh_urls,
                post_url=post_url,
                labels=LABELS,
            )
            if _th_result.get("success"):
                print(f"  ✅ Threads 게시 완료: {_th_result.get('permalink','')}")
            else:
                print(f"  ℹ️  Threads 게시 실패: {_th_result.get('error','')}")
        except Exception as _the:
            print(f"  ℹ️  Threads 게시 스킵 (비치명적): {_the}")

    # 5. Google Indexing API — 즉시 색인 요청
    if post_url:
        try:
            sys.path.insert(0, str(BASE_DIR / "scripts"))
            import indexing_api as idx
            idx_token = idx.get_indexing_token()
            idx_result = idx.request_indexing(post_url, idx_token)
            if "error" in idx_result:
                print(f"  ℹ️  Indexing API [{idx_result['error']}]: {idx_result.get('message','')[:80]}")
            else:
                print(f"  ✅ Indexing API 색인 요청 완료: {post_url[:60]}")
        except Exception as e:
            print(f"  ℹ️  Indexing API 스킵 (비치명적): {e}")

    # 6. 마크다운 백업 + published: true 마킹
    md_path = save_markdown(title, post_data["content"], LABELS, products)
    print(f"[INFO] 마크다운 저장: {md_path}")
    # 발행 성공 마킹 — 다음 크론 중복 발행 방지
    try:
        _text = md_path.read_text(encoding='utf-8')
        if _text.startswith('---') and 'published: true' not in _text:
            _parts = _text.split('---', 2)
            _fm = _parts[1].rstrip() + f'\npublished: true\nblogger_url: "{post_url}"\n'
            md_path.write_text('---' + _fm + '---' + _parts[2], encoding='utf-8')
            print(f"  ✅ 발행 완료 마킹: published: true")
    except Exception as _me:
        print(f"  ℹ️  마킹 스킵: {_me}")
    
    # 6. GitHub push
    import subprocess
    try:
        git_dir = BASE_DIR
        remote = f"https://{os.environ.get('GITHUB_PAT', '')}@github.com/noivan0/aikeeper-blog.git"

        subprocess.run(["git", "-C", str(git_dir), "add", str(md_path)], check=True)
        subprocess.run(["git", "-C", str(git_dir), "commit", "-m",
                        f"feat: [ggultongmon] {title[:50]}"], check=True)

        if os.environ.get("GITHUB_PAT", ""):
            # fetch 후 rebase (실패 시 abort하고 force push로 대체)
            try:
                subprocess.run(
                    ["git", "-C", str(git_dir), "fetch", remote, "main"],
                    check=True, capture_output=True, timeout=30
                )
                subprocess.run(
                    ["git", "-C", str(git_dir), "rebase", "FETCH_HEAD"],
                    check=True, capture_output=True, timeout=30
                )
            except subprocess.CalledProcessError:
                # rebase 충돌 시 abort 후 로컬 커밋 유지 (포스팅 백업 우선)
                subprocess.run(["git", "-C", str(git_dir), "rebase", "--abort"],
                               capture_output=True)
            subprocess.run(
                ["git", "-C", str(git_dir), "push", remote, "main"],
                check=True, timeout=30
            )
            print(f"[INFO] GitHub push 완료")
    except Exception as e:
        print(f"[WARN] GitHub push 실패 (포스팅은 완료됨): {e}")

    # 7. GitHub Actions output 내보내기 (크로스포스팅용)
    gh_out = os.environ.get("GITHUB_OUTPUT", "")
    if gh_out and post_url:
        with open(gh_out, "a") as f:
            f.write(f"post_url={post_url}\n")
            f.write(f"post_title={title}\n")
        print(f"[INFO] GitHub output 저장: post_url={post_url[:60]}")

    # 8. 공통 주제 로그 기록 (상품ID 당일 중복 방지용)
    try:
        import sys as _sys
        _sys.path.insert(0, str(BASE_DIR / "scripts"))
        from used_topics_log import log_topic as _log_topic
        _keywords = os.environ.get("SEARCH_KW") or os.environ.get("search_keyword", "")
        _product_ids = [
            str(p.get("productId", p.get("itemId", "")))
            for p in products
            if p.get("productId") or p.get("itemId")
        ]
        _log_topic("ggultongmon", TOPIC, _keywords,
                   search_keyword=_keywords, product_ids=_product_ids)
        print(f"  📝 used_topics.jsonl 기록 완료: {TOPIC[:50]} | 상품ID {len(_product_ids)}개")
    except Exception as _le:
        print(f"  ℹ️  주제 로그 기록 스킵 (비치명적): {_le}")


if __name__ == "__main__":
    main()
