#!/usr/bin/env python3
"""
ggultongmon -> 티스토리 크로스포스팅
- 카테고리: '쿠팡' (ID 1199098)
- 이미지: 캐러셀 커버 이미지 (GitHub Pages URL) 포함
- CTA: 버튼 스타일로 ggultongmon 연결
"""
import os, sys, json, re, requests
from pathlib import Path
from anthropic import Anthropic

BASE_DIR = Path(__file__).parent.parent

# .env 로드
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

TSSESSION        = os.environ.get("TISTORY_SESSION", "")
BLOG_NAME        = "banidad"
CATEGORY_COUPANG = "1199098"   # '쿠팡' 카테고리 ID
API_BASE         = f"https://{BLOG_NAME}.tistory.com/manage"

requests.packages.urllib3.disable_warnings()


# ── 버튼 스타일 HTML ─────────────────────────────────────────────────────────
def _btn(post_url: str, text: str, bg: str = "#FF4500") -> str:
    css = (
        f"display:inline-block;background:{bg};color:#fff!important;"
        "font-size:17px;font-weight:bold;padding:16px 32px;border-radius:50px;"
        "text-decoration:none!important;box-shadow:0 4px 14px rgba(0,0,0,.25);"
        "letter-spacing:-.3px;margin:6px 0;"
    )
    return (
        f'<div style="text-align:center;margin:28px 0;">'
        f'<a href="{post_url}" target="_blank" rel="noopener" style="{css}">{text}</a>'
        f'</div>'
    )

def _top_cta(post_url: str) -> str:
    """본문 상단 버튼 (이미지 바로 아래)"""
    return _btn(post_url, "&#128073; 지금 바로 최저가 확인하기", "#FF4500")

def _bottom_cta(post_url: str) -> str:
    """본문 하단 버튼"""
    return _btn(post_url, "&#127873; 전체 비교 + 쿠팡 최저가 구매링크", "#E8000D")

def _cover_img_block(image_url: str, alt: str = "") -> str:
    """커버 이미지 블록"""
    return (
        f'<p style="text-align:center;margin:0 0 4px;">'
        f'<img src="{image_url}" alt="{alt}" '
        f'style="max-width:100%;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.15);" />'
        f'</p>'
    )


# ── requests 세션 ────────────────────────────────────────────────────────────
def _sess():
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "Cookie":           f"TSSESSION={TSSESSION}",
        "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Origin":           f"https://{BLOG_NAME}.tistory.com",
        "Referer":          f"{API_BASE}/newpost/",
        "Content-Type":     "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


# ── Claude 크로스포스트 생성 ─────────────────────────────────────────────────
def generate_cross_post(topic: str, products: list, post_url: str,
                        labels: list, cover_image_url: str = "") -> dict:
    """Claude로 다른 앵글의 완결형 크로스포스팅 생성 (이미지/버튼 포함)"""
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

    prod_list = "\n".join(
        f"- {p.get('productName','')}: {int(p.get('productPrice',0)):,}원"
        for p in products
    )

    # 이미지+상단버튼 블록 (Claude가 본문 앞에 삽입하도록 지시)
    top_block = ""
    if cover_image_url:
        top_block = _cover_img_block(cover_image_url, topic) + _top_cta(post_url)

    bottom_block = _bottom_cta(post_url)

    prompt = f"""아래 쿠팡 추천 포스트를 기반으로 티스토리 크로스포스팅용 글을 작성하세요.

원문 주제: {topic}
원문 URL: {post_url}
상품 목록:
{prod_list}

=== 작성 조건 ===

[제목]
- 원문과 다른 각도 (질문형 또는 문제해결형)

[본문 구조 — 가독성 최우선]
- <h2> 소제목: 3~5개, 각 섹션 명확히 구분
- 각 <h2> 아래 <p>는 2~3문장씩 끊어서 작성 (한 <p>에 5줄 이상 금지)
- 문단 사이 여백: <p style="margin-bottom:16px;"> 사용
- 핵심 키워드: <strong>으로 강조
- 항목 나열 시: <ul><li> 사용 (줄글로 나열 금지)
- 각 <h2> 앞에는 반드시 빈 <p>&nbsp;</p> 1개 삽입 (단락 구분)
- 전체 1,500~2,000자 분량

[구조 순서 — 수정 금지]
{top_block}
[↑ 상단 블록: 이미지+버튼 고정]

[본문 내용 여기에 작성 — 위 HTML 블록을 content 맨 앞에 붙일 것]

{bottom_block}
[↑ 하단 버튼 고정, content 맨 끝에 붙일 것]

[태그]
- 쉼표 구분 5~8개

=== 응답 형식 ===
아래 JSON만 출력 (content = 상단블록+본문+하단버튼 완성 HTML):
{{
  "title": "제목",
  "content": "완성된 HTML 전체",
  "tag": "태그1,태그2,태그3"
}}"""

    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


# ── 티스토리 발행 ────────────────────────────────────────────────────────────
def publish_to_tistory(title: str, content: str, tag: str = "",
                       category: str = CATEGORY_COUPANG) -> dict:
    """티스토리 /manage/post.json API로 글 발행"""
    if not TSSESSION:
        raise RuntimeError("TISTORY_SESSION 환경변수 없음")

    s = _sess()
    payload = {
        "title":           title,
        "content":         content,
        "visibility":      "20",       # 공개
        "category":        category,   # 쿠팡 카테고리
        "tag":             tag,
        "acceptComment":   "1",
        "acceptTrackback": "0",
        "published":       "1",
    }
    r = s.post(f"{API_BASE}/post.json", json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"발행 실패 {r.status_code}: {r.text[:200]}")

    result = r.json()
    entry_url = result.get("entryUrl", "")
    print(f"  [tistory] 발행 완료: {entry_url}")
    return {"success": True, "url": entry_url}


# ── 메인 플로우 ──────────────────────────────────────────────────────────────
def cross_post(topic: str, products: list, post_url: str,
               labels: list = None, cover_image_url: str = "") -> dict:
    """전체 크로스포스팅 플로우"""
    labels = labels or []
    print(f"[tistory] 크로스포스팅 시작: {topic[:40]}...")

    # 커버 이미지 자동 추출 — CAROUSEL_IMAGE_URLS 에서 slide_01_cover 우선
    if not cover_image_url:
        carousel_urls = os.environ.get("CAROUSEL_IMAGE_URLS", "")
        if carousel_urls:
            urls = [u.strip() for u in carousel_urls.split(",") if u.strip().startswith("http")]
            # slide_01_cover 를 가장 먼저
            cover_candidates = [u for u in urls if "slide_01" in u or "cover" in u]
            cover_image_url = (cover_candidates or urls)[0] if (cover_candidates or urls) else ""
            if cover_image_url:
                print(f"[tistory] 커버 이미지: {cover_image_url[:80]}...")

    print("[tistory] Claude 크로스포스트 생성 중...")
    data = generate_cross_post(topic, products, post_url, labels, cover_image_url)
    print(f"[tistory] 제목: {data['title']}")

    result = publish_to_tistory(
        title=data["title"],
        content=data["content"],
        tag=data.get("tag", ",".join(labels)),
    )
    return result


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",     required=True)
    parser.add_argument("--post-url",  required=True)
    parser.add_argument("--products",  default="[]")
    parser.add_argument("--cover-img", default="")
    args = parser.parse_args()

    products = json.loads(args.products)
    result = cross_post(args.topic, products, args.post_url,
                        cover_image_url=args.cover_img)
    print(json.dumps(result, ensure_ascii=False, indent=2))
