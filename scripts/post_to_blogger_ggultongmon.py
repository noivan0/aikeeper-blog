"""
꿀통몬스터 블로그 → Blogger 포스팅
- 쿠팡 상품 수집 + 포스트 생성 + Blogger API 발행
"""
import os, sys, json, re, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from coupang_api import get_products_with_shorten
from generate_post_ggultongmon import generate_post, build_full_html

# ── 환경변수 ──────────────────────────────────────────────────────
TOPIC           = os.environ.get("TOPIC", "에어프라이어 가성비 추천 TOP5")
SEARCH_KW       = os.environ.get("SEARCH_KW") or os.environ.get("search_keyword", "에어프라이어")
ANGLE           = os.environ.get("ANGLE", "")
LABELS_STR      = os.environ.get("LABELS") or os.environ.get("labels", "에어프라이어 추천,에어프라이어 가성비")
META_DESC       = os.environ.get("META_DESC") or os.environ.get("meta_desc", "")
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
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    body = json.dumps({
        "title": title,
        "content": html,
        "labels": labels,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


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

    # 6. 마크다운 백업
    md_path = save_markdown(title, post_data["content"], LABELS, products)
    print(f"[INFO] 마크다운 저장: {md_path}")
    
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


if __name__ == "__main__":
    main()
