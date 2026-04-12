#!/usr/bin/env python3
"""
ggultongmon -> 티스토리 크로스포스팅
- 카테고리: '쿠팡' (ID 1199098)
- 이미지: 캐러셀 커버 이미지 + 상품별 productImage -> GitHub Pages 업로드
- CTA: 버튼 스타일로 ggultongmon 연결
- 대표 이미지: cover_image_url -> thumbnail 설정
- SEO: E-E-A-T 기반 2,500~3,000자 + FAQ 섹션
"""
import os, sys, json, re, requests, urllib.request, base64, time, io
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
BLOG_NAME        = os.environ.get("TISTORY_BLOG_NAME", "banidad")
CATEGORY_COUPANG = os.environ.get("TISTORY_CATEGORY_COUPANG", "1199098")
API_BASE         = f"https://{BLOG_NAME}.tistory.com/manage"

requests.packages.urllib3.disable_warnings()


# ── HTML 블록 헬퍼 ───────────────────────────────────────────────────────────
def _btn(post_url: str, text: str, bg: str = "#FF4500") -> str:
    css = (
        f"display:inline-block;background:{bg};color:#fff!important;"
        "font-size:17px;font-weight:bold;padding:16px 32px;border-radius:50px;"
        "text-decoration:none!important;box-shadow:0 4px 14px rgba(0,0,0,.25);"
        "letter-spacing:-.3px;margin:6px 0;"
    )
    return (
        f'<div style="text-align:center;margin:28px 0;">'
        f'<a href="{post_url}" style="{css}">{text}</a>'
        f'</div>'
    )

def _top_cta(post_url: str) -> str:
    return _btn(post_url, "&#128073; 지금 바로 최저가 확인하기", "#FF4500")

def _bottom_cta(post_url: str) -> str:
    return _btn(post_url, "&#127873; 전체 비교 + 쿠팡 최저가 구매링크", "#E8000D")

def _cover_img_block(image_url: str, alt: str = "") -> str:
    """커버 이미지 블록 (대표 이미지용)"""
    return (
        f'<p style="text-align:center;margin:0 0 4px;">'
        f'<img src="{image_url}" alt="{alt}" '
        f'style="max-width:100%;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.15);" />'
        f'</p>'
    )

def _product_img_block(image_url: str, alt: str = "", price: str = "") -> str:
    """상품 이미지 블록 (GitHub Pages URL 사용)"""
    if not image_url:
        return ""
    caption = f'<p style="text-align:center;font-size:14px;color:#666;margin:4px 0 16px;">{price}</p>' if price else ""
    return (
        f'<p style="text-align:center;margin:16px 0 0;">'
        f'<img src="{image_url}" alt="{alt}" '
        f'style="max-width:100%;border-radius:8px;margin:12px 0;" />'
        f'</p>'
        f'{caption}'
    )


# ── 이미지 다운로드 + GitHub Pages 업로드 ───────────────────────────────────
def _download_coupang_image(url: str) -> bytes:
    """쿠팡 CDN 이미지 다운로드 (Referer 위장)"""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
                "Referer": "https://www.coupang.com/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as e:
        print(f"  [tistory] 이미지 다운로드 실패 ({url[:60]}): {e}")
        return b""


def _resize_image(data: bytes, max_size: int = 800) -> bytes:
    """PIL로 이미지 리사이즈 (최대 800px, JPEG 품질 85)"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"  [tistory] 리사이즈 실패: {e}")
        return data


def _upload_to_github_pages(img_data: bytes, filename: str, ts: str) -> str:
    """
    이미지를 GitHub Pages gh-pages 브랜치에 업로드하고 공개 URL 반환.
    경로: tistory/{ts}/{filename}
    """
    gh_token = os.environ.get("GITHUB_PAT", "")
    repo     = os.environ.get("GITHUB_PAGES_REPO", "noivan0/aikeeper-blog")
    branch   = os.environ.get("GITHUB_PAGES_BRANCH", "gh-pages")
    base_url = os.environ.get("GITHUB_PAGES_BASE", "https://noivan0.github.io/aikeeper-blog")

    if not gh_token or not img_data:
        return ""

    remote_path = f"tistory/{ts}/{filename}"
    content = base64.b64encode(img_data).decode()
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"

    payload = json.dumps({
        "message": f"tistory img: {ts}/{filename}",
        "content": content,
        "branch": branch,
    }).encode()

    req = urllib.request.Request(
        api_url, data=payload, method="PUT",
        headers={
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    try:
        urllib.request.urlopen(req, timeout=30)
        public_url = f"{base_url}/{remote_path}"
        print(f"  [tistory] 이미지 업로드: {filename} -> {public_url}")
        return public_url
    except Exception as e:
        print(f"  [tistory] GitHub 업로드 실패 ({filename}): {e}")
        return ""


def upload_product_images(products: list, ts: str) -> list:
    """
    상품 목록의 productImage를 다운로드 -> 리사이즈 -> GitHub Pages 업로드.
    반환: [{"name":..., "price":..., "gh_url":..., "original_url":...}, ...]
    """
    results = []
    for i, p in enumerate(products):
        pname  = p.get("productName", p.get("name", f"상품{i+1}"))
        pprice = p.get("productPrice", p.get("price", ""))
        pimg   = p.get("productImage", "")

        try:
            price_str = f"{int(pprice):,}원" if pprice else ""
        except (ValueError, TypeError):
            price_str = str(pprice) if pprice else ""

        gh_url = ""
        if pimg:
            print(f"  [tistory] 상품{i+1} 이미지 처리: {pname[:30]}")
            img_data = _download_coupang_image(pimg)
            if img_data:
                img_data = _resize_image(img_data, max_size=800)
                fname = f"product_{i+1:02d}.jpg"
                gh_url = _upload_to_github_pages(img_data, fname, ts)
                time.sleep(0.5)  # GitHub API rate limit

        results.append({
            "index": i + 1,
            "name": pname,
            "price": price_str,
            "url": p.get("shortenUrl", p.get("coupang_url", "")),
            "gh_url": gh_url,
            "original_url": pimg,
        })
    return results


# ── requests 세션 ────────────────────────────────────────────────────────────
def _sess():
    session = os.environ.get("TISTORY_SESSION", TSSESSION)
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "Cookie":           f"TSSESSION={session}",
        "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Origin":           f"https://{BLOG_NAME}.tistory.com",
        "Referer":          f"{API_BASE}/newpost/",
        "Content-Type":     "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    s.cookies.set("TSSESSION", session, domain=f"{BLOG_NAME}.tistory.com")
    return s


# ── Claude 크로스포스트 생성 ─────────────────────────────────────────────────
def generate_cross_post(topic: str, products: list, post_url: str,
                        labels: list, cover_image_url: str = "",
                        uploaded_images: list = None) -> dict:
    """
    Claude로 E-E-A-T 기반 완결형 크로스포스팅 생성.
    - 커버 이미지 + 상품별 GitHub Pages 이미지 본문 삽입
    - 2,500~3,000자, FAQ 섹션 포함
    - target="_blank" 금지
    uploaded_images: upload_product_images() 반환값 (gh_url 포함)
    """
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

    uploaded_images = uploaded_images or []
    # uploaded_images를 index 기준 dict로
    img_map = {ui["index"]: ui for ui in uploaded_images}

    # 상품별 정보 + 이미지 블록 사전 생성
    prod_blocks = []
    prod_list_text = []
    for i, p in enumerate(products):
        pname  = p.get("productName", p.get("name", ""))
        pprice = p.get("productPrice", p.get("price", ""))
        purl   = p.get("shortenUrl", p.get("coupang_url", ""))

        try:
            price_str = f"{int(pprice):,}원" if pprice else ""
        except (ValueError, TypeError):
            price_str = str(pprice) if pprice else ""

        prod_list_text.append(f"- 상품{i+1}: {pname} / {price_str}")

        # GitHub Pages에 업로드된 URL 우선 사용
        ui = img_map.get(i + 1, {})
        gh_url = ui.get("gh_url", "")
        img_html = _product_img_block(gh_url, pname, price_str) if gh_url else ""
        prod_blocks.append({
            "index": i + 1,
            "name": pname,
            "price": price_str,
            "url": purl,
            "img_block": img_html,
        })

    prod_list = "\n".join(prod_list_text)

    # 상품 이미지 블록 설명 (프롬프트용)
    prod_img_instructions = ""
    for pb in prod_blocks:
        if pb["img_block"]:
            prod_img_instructions += (
                f"\n상품{pb['index']} ({pb['name']}) 이미지 블록 (해당 상품 설명 h2/h3 바로 아래에 삽입):\n"
                f"{pb['img_block']}\n"
            )

    # HTML 블록 사전 생성
    img_block     = _cover_img_block(cover_image_url, topic) if cover_image_url else ""
    top_btn_block = _top_cta(post_url)
    bottom_block  = _bottom_cta(post_url)

    # 앵글 선택
    import hashlib
    _angle_seed = int(hashlib.md5(topic.encode()).hexdigest(), 16) % 5
    angles = [
        "실패 경험 -> 해결 스토리형: 처음 잘못 샀다가 손해 본 경험을 도입으로 시작하고, 올바른 선택 기준을 알려주는 스토리텔링 방식",
        "사용 상황별 추천형: '이런 상황이라면 이 제품' 식으로 독자 상황(입문자/자주 사용/가성비 중시 등)에 맞게 추천하는 방식",
        "구매 전 체크리스트형: 이 카테고리 상품을 살 때 놓치기 쉬운 3~5가지 함정/실수를 앞에 짚고, 각 제품이 어떻게 해결하는지 설명",
        "사용법 활용 팁형: 제품 소개보다 올바른 사용법, 관리법, 극대화 팁 위주로 쓰고 제품은 도구로 자연스럽게 녹여내는 방식",
        "비교 기준 심화형: 가격/디자인이 아닌 소재, 인증, 실제 착용감 등 전문적 기준으로 심층 비교하는 방식",
    ]
    angle = angles[_angle_seed]

    prompt = f"""아래 정보를 바탕으로 티스토리 크로스포스팅 글을 작성하세요.

원문 주제: {topic}
원문 URL: {post_url}
상품 목록:
{prod_list}

=== E-E-A-T 기반 SEO 핵심 원칙 ===
구글 중복 콘텐츠 패널티를 피하기 위해 원문({post_url})과 완전히 다른 각도로 접근해야 합니다.
선택된 앵글: {angle}

[Experience] 실제 구매/사용 경험 기반 1인칭 서술 자연스럽게 녹이기
[Expertise] 카테고리 전문 지식 (소재, 성분, 인증, 기술 스펙, 수치 데이터) 포함
[Authoritativeness] 구체적 수치, 비교 데이터, 실측값 포함
[Trustworthiness] 단점/주의사항도 솔직하게 언급 (광고성 일색 금지)

=== 제목 ===
- 위 앵글에 맞는 제목 (원문 제목과 60% 이상 달라야 함)
- 독자의 고민/실수/상황을 직접 건드리는 표현 사용
- 핵심 키워드 자연스럽게 포함

=== 본문 구조 (1~6 순서 고정) ===

[1] 커버 이미지 (아래 HTML 그대로 삽입):
{img_block}

[2] 도입 문단 - <p style="margin-bottom:20px;"> 태그 사용:
   - 3~4문장, 위 앵글에 맞는 도입 (공감, 문제제기, 상황 설정)
   - 핵심 키워드 자연스럽게 포함
   - 이 글에서 무엇을 얻을 수 있는지 명시

[3] 상단 버튼 (아래 HTML 그대로 삽입):
{top_btn_block}

[4] 본문 본체 (h2 소제목 4~5개):
   - 각 h2 앞: <p style="margin:28px 0 4px;">&nbsp;</p> 삽입
   - 각 h2 아래: <p style="margin-bottom:16px;"> 3~4문장씩 상세 서술
   - 항목 나열: <ul style="margin:8px 0 16px;padding-left:20px;"><li style="margin-bottom:8px;">
   - 핵심 키워드: <strong>으로 강조
   - 제품별 설명 섹션: 이름, 가격, 핵심 스펙, 추천 대상, 가성비 수치 명시
   - 단점/주의사항 1~2개 솔직 언급 (신뢰도 향상)
   - 상품 이미지 블록: 각 상품 설명 h2/h3 바로 아래에 해당 상품 이미지 삽입
{prod_img_instructions}
   - 전체 분량: 2,500~3,000자 (풍부하고 상세하게)

[5] FAQ 섹션 (구글 Featured Snippet 타겟):
   - h2 제목: "자주 묻는 질문"
   - Q&A 3~4개, <strong>Q: 질문</strong> + <p>A: 답변</p> 형식
   - 실제 독자가 궁금해할 구체적 질문 (가격, 사용법, 비교, 주의사항)

[6] 하단 버튼 (아래 HTML 그대로 삽입):
{bottom_block}

=== 링크 규칙 (필수) ===
- 모든 <a> 태그에 target="_blank" 및 rel="noopener" 절대 사용 금지
- 링크는 같은 탭에서 열려야 함 (Google AdSense 전면광고 노출 필수 조건)

=== 태그 ===
쉼표 구분 8~10개 (상품명, 카테고리, 롱테일 키워드, 상황 키워드 혼합)

=== 응답 형식 (JSON만 출력, 다른 텍스트 금지) ===
{{
  "title": "제목",
  "content": "[1]~[6] 합친 완성 HTML",
  "tag": "태그1,태그2,태그3"
}}"""

    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        data = json.loads(match.group())
        # thumbnail 키 추가 (대표 이미지용)
        data["thumbnail"] = cover_image_url
        return data
    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


# ── 티스토리 발행 ────────────────────────────────────────────────────────────
def _refresh_session_if_needed() -> str:
    """세션이 만료된 경우 자동 재갱신 후 새 세션값 반환"""
    import subprocess
    script = Path(__file__).parent / "refresh_tistory_session.py"
    print("  [tistory] 세션 만료 감지 -> 자동 재갱신 시도...")
    env2 = {**os.environ, "DISPLAY": ":99"}
    r = subprocess.run([sys.executable, str(script)], env=env2,
                       capture_output=True, text=True, timeout=90)
    print(r.stdout[-300:] if r.stdout else "")
    if r.returncode != 0:
        raise RuntimeError(f"세션 재갱신 실패: {r.stderr[-200:]}")

    env_file = Path(__file__).parent.parent / ".env"
    for line in env_file.read_text().splitlines():
        if line.startswith("TISTORY_SESSION="):
            new_session = line.split("=", 1)[1].strip()
            os.environ["TISTORY_SESSION"] = new_session
            return new_session
    raise RuntimeError("새 TISTORY_SESSION 값을 .env에서 찾을 수 없음")


def publish_to_tistory(title: str, content: str, tag: str = "",
                       category: str = CATEGORY_COUPANG,
                       thumbnail_url: str = "") -> dict:
    """
    티스토리 /manage/post.json API로 글 발행.
    thumbnail_url: 대표 이미지 URL (있을 경우 payload에 포함)
    """
    if not TSSESSION and not os.environ.get("TISTORY_SESSION"):
        raise RuntimeError("TISTORY_SESSION 환경변수 없음")

    s = _sess()
    payload = {
        "title":           title,
        "content":         content,
        "visibility":      "20",
        "category":        category,
        "tag":             tag,
        "acceptComment":   "1",
        "acceptTrackback": "0",
        "published":       "1",
    }
    if thumbnail_url:
        payload["thumbnail"] = thumbnail_url

    r = s.post(f"{API_BASE}/post.json", json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"발행 실패 {r.status_code}: {r.text[:200]}")

    # 세션 만료 감지: 응답이 HTML인 경우
    content_type = r.headers.get("content-type", "")
    if "html" in content_type or r.text.strip().startswith("<!"):
        print("  [tistory] 세션 만료 감지 (HTML 응답) -> 재갱신 후 재시도")
        _refresh_session_if_needed()
        s2 = _sess()
        r = s2.post(f"{API_BASE}/post.json", json=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"재시도 발행 실패 {r.status_code}: {r.text[:200]}")

    try:
        result = r.json()
    except Exception:
        raise RuntimeError(f"응답 JSON 파싱 실패 (세션 문제 가능성): {r.text[:200]}")

    entry_url = result.get("entryUrl", "")
    print(f"  [tistory] 발행 완료: {entry_url}")
    return {"success": True, "url": entry_url}


# ── 메인 플로우 ──────────────────────────────────────────────────────────────
def cross_post(topic: str, products: list, post_url: str,
               labels: list = None, cover_image_url: str = "") -> dict:
    """전체 크로스포스팅 플로우"""
    labels = labels or []
    print(f"[tistory] 크로스포스팅 시작: {topic[:40]}...")

    # 커버 이미지 fallback
    if not cover_image_url:
        import json as _cj
        _all = _cj.loads(os.environ.get("CAROUSEL_IMAGE_URLS", "[]"))
        _candidates = [u for u in _all if u and ("slide_01" in u or "cover" in u)]
        cover_image_url = (_candidates or _all or [""])[0]
    if cover_image_url:
        print(f"[tistory] 커버 이미지: {cover_image_url[:80]}...")

    # 상품 이미지 다운로드 -> GitHub Pages 업로드
    prod_img_count = sum(1 for p in products if p.get("productImage", ""))
    print(f"[tistory] 상품 {len(products)}개 (이미지 있는 상품: {prod_img_count}개)")
    ts = time.strftime("%Y%m%d_%H%M%S")
    uploaded_images = []
    if prod_img_count > 0:
        print("[tistory] 상품 이미지 GitHub Pages 업로드 중...")
        uploaded_images = upload_product_images(products, ts)
        # GitHub Pages 반영 대기 (5초)
        time.sleep(5)

    print("[tistory] Claude 크로스포스트 생성 중...")
    data = generate_cross_post(topic, products, post_url, labels, cover_image_url,
                               uploaded_images=uploaded_images)
    print(f"[tistory] 제목: {data['title']}")

    result = publish_to_tistory(
        title=data["title"],
        content=data["content"],
        tag=data.get("tag", ",".join(labels)),
        thumbnail_url=data.get("thumbnail", cover_image_url),
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
    result = cross_post(
        topic=args.topic,
        products=products,
        post_url=args.post_url,
        cover_image_url=args.cover_img,
    )
    print(json.dumps(result, ensure_ascii=False))
