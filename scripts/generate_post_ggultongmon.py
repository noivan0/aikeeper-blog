"""
꿀통몬스터 쿠팡 파트너스 블로그 포스트 생성기 v2
- 파트너스 고지: 최상단 1회만
- 각 상품 섹션 안에 이미지 + 설명 + 구매 버튼 인라인 삽입 (클릭률 최적화)
- Claude가 [PRODUCT_N] 마커 출력 → 자동으로 상품 카드 치환
"""
import os, sys, json, re, urllib.request, urllib.parse, anthropic
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from coupang_api import get_products_with_shorten

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ── 파트너스 고지문 (최상단 1회만) ─────────────────────────────────────
PARTNERS_NOTICE_HTML = """\
<div style="background:#fff8e1;border:1px solid #ffc107;border-radius:10px;\
padding:12px 18px;margin:0 0 2em;font-size:0.83em;color:#6d4c41;line-height:1.6;">
<strong>📢 파트너스 안내</strong>&nbsp;&nbsp;
이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
</div>"""

# ── 상품 인라인 카드 (본문 섹션 안에 삽입) ──────────────────────────────
def build_inline_card(product: dict, rank: int) -> str:
    """상품 이미지 + 가격 + 구매 버튼 — 본문 h2 섹션 안에 삽입"""
    name      = product.get("productName", "상품명 없음")[:60]
    price     = f"{product.get('productPrice', 0):,}"
    img_url   = product.get("productImage", "")
    buy_url   = product.get("shortenUrl", product.get("productUrl", "#"))
    is_rocket = product.get("isRocket", False)
    is_free   = product.get("isFreeShipping", False)

    badges = ""
    if is_rocket:
        badges += '<span style="background:#00bcd4;color:#fff;font-size:0.72em;padding:2px 8px;border-radius:20px;margin-right:5px;vertical-align:middle;">로켓배송</span>'
    if is_free:
        badges += '<span style="background:#66bb6a;color:#fff;font-size:0.72em;padding:2px 8px;border-radius:20px;vertical-align:middle;">무료배송</span>'

    return f"""\
<div style="border:2px solid #e8eaf6;border-radius:16px;padding:20px;margin:1.5em 0 2em;background:#f8f9ff;">
  <!-- 상품 정보 -->
  <div style="display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;margin-bottom:16px;">
    <a href="{buy_url}" rel="noopener noreferrer" target="_blank" style="flex-shrink:0;display:block;">
      <img src="{img_url}" alt="{name}"
           style="width:150px;height:150px;object-fit:contain;border-radius:12px;border:1px solid #e0e0e0;background:#fff;display:block;"
           loading="lazy">
    </a>
    <div style="flex:1;min-width:160px;">
      <p style="margin:0 0 6px;font-size:0.78em;color:#9e9e9e;font-weight:600;letter-spacing:0.5px;">TOP {rank}</p>
      <p style="margin:0 0 8px;font-size:1.04em;font-weight:700;color:#1a237e;line-height:1.45;">{name}</p>
      <p style="margin:0 0 10px;">{badges}</p>
      <p style="margin:0;font-size:1.5em;font-weight:800;color:#e53935;">
        {price}<span style="font-size:0.55em;font-weight:500;color:#757575;margin-left:3px;">원</span>
      </p>
    </div>
  </div>
  <!-- 구매 버튼 (풀 너비, 눈에 띄게) -->
  <a href="{buy_url}" rel="noopener noreferrer" target="_blank"
     style="display:block;text-align:center;background:#e53935;color:#fff;font-size:1.05em;font-weight:700;
            padding:15px 20px;border-radius:12px;text-decoration:none;letter-spacing:-0.2px;
            transition:background 0.2s;"
     onmouseover="this.style.background='#c62828'" onmouseout="this.style.background='#e53935'">
    쿠팡에서 최저가 확인하기 &rarr;
  </a>
</div>"""


SYSTEM_PROMPT_COUPANG = """\
당신은 쿠팡 파트너스 블로그 '꿀통 몬스터'의 전문 콘텐츠 에디터입니다.
독자가 실제 구매 결정을 내릴 수 있도록 돕는 상품 추천/비교 포스트를 작성합니다.

## 글쓰기 원칙
- 구매자 관점: "이 상품을 왜 사야 하나?"에 명확히 답변
- 실제 사용 경험처럼 자연스럽고 신뢰감 있게
- 가격/스펙/장단점 구체적으로 비교
- 검색의도 키워드 자연스럽게 포함
- 분량: 4,000~6,000자

## 포스트 구조 (반드시 준수)
1. 도입부 훅 (200~300자): 독자 공감 상황
2. 선택 기준 섹션 (h2): 구매 시 체크할 핵심 포인트 3~5개
3. 각 상품별 h2 섹션:
   - h2 제목 직후 반드시 [PRODUCT_N] 마커 한 줄 삽입 (N=순번, 예: [PRODUCT_1])
   - 그 다음 줄부터 해당 상품 상세 설명 (300~500자)
   - 장점 2~3개 불릿, 추천 대상 명시
   - 섹션 끝에 [BUY_N] 마커 한 줄 삽입 (중간 구매 버튼 위치)
4. 비교표 (h2): 가격/특징/추천대상 3열 이상
5. FAQ (h2): 구매 전 자주 묻는 질문 3~5개
6. 마무리 (h2): 한 줄 정리 + 최종 추천

## 금지 사항
- 본문에 "파트너스 활동", "수수료를 제공받습니다" 문구 절대 삽입 금지 (별도 자동 삽입됨)
- 이모지 사용 금지

## 마커 예시 (정확히 이 형식)
## 1위. ANF 식스프리 강아지 사료
[PRODUCT_1]
이 사료는 알레르기가 심한 강아지에게 특히 좋습니다...
...상세 설명...
[BUY_1]
"""


def generate_post(topic: str, search_keyword: str, products: list,
                  angle: str = "", meta_desc: str = "") -> dict:
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y년 %m월 %d일")

    product_info = "\n".join([
        f"[PRODUCT_{i+1}] {p['productName'][:50]} | {p['productPrice']:,}원 | "
        f"로켓:{p['isRocket']} | 무료배송:{p['isFreeShipping']}"
        for i, p in enumerate(products)
    ])

    prompt = f"""오늘은 {today}. 아래 상품 정보를 바탕으로 꿀통 몬스터 블로그 포스트를 작성하세요.

포스트 주제: {topic}
글쓰기 각도: {angle}

[쿠팡 검색된 상품 목록 — 각 섹션에 마커 삽입 필수]
{product_info}

===TITLE===
최종 포스트 제목 (50자 이내, 이모지 금지)
===CONTENT===
포스트 본문 (Markdown)
[각 상품 h2 바로 아래 [PRODUCT_N] 마커, 섹션 끝에 [BUY_N] 마커 반드시 삽입]
===FAQ===
Q1: 질문
A1: 답변 (150자 이상)
Q2: 질문
A2: 답변
Q3: 질문
A3: 답변
===END===
"""

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=ANTHROPIC_BASE_URL,
    )

    print(f"   Claude 포스트 생성 중... ({ANTHROPIC_MODEL})")
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT_COUPANG,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text

    def extract(tag):
        s = text.find(f"==={tag}===")
        if s == -1: return ""
        s += len(f"==={tag}===")
        e = text.find("===", s)
        return text[s:e if e != -1 else None].strip()

    title   = extract("TITLE")
    content = extract("CONTENT")
    faq_raw = extract("FAQ")

    # 이모지 제거
    title = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001F9FF]', '', title).strip()
    char_count = len(content.replace(' ', '').replace('\n', ''))
    print(f"   생성 완료: {char_count:,}자")

    return {"title": title, "content": content, "faq_raw": faq_raw, "char_count": char_count}


def build_full_html(title: str, content: str, products: list,
                    labels: list, meta_desc: str, faq_raw: str = "") -> str:
    """
    최종 Blogger HTML
    - 파트너스 고지: 최상단 1회만
    - [PRODUCT_N] → 인라인 상품 카드 (이미지+가격)
    - [BUY_N]     → 구매 버튼
    """
    import markdown as md_lib

    # Claude가 본문에 파트너스 고지를 중복 삽입할 수 있으므로 제거
    content = re.sub(
        r'(>?\s*)?(본\s*포스트|이\s*포스팅|이\s*글)[은는이]\s*쿠팡\s*파트너스\s*활동[^\n]{0,150}',
        '', content, flags=re.IGNORECASE
    ).strip()

    # Markdown → HTML
    body_html = md_lib.markdown(
        content,
        extensions=["tables", "fenced_code", "nl2br", "toc"]
    )

    # [PRODUCT_N] → 상품 인라인 카드 치환
    def replace_product(m):
        n = int(m.group(1)) - 1
        if 0 <= n < len(products):
            return build_inline_card(products[n], n + 1)
        return ""

    body_html = re.sub(r'\[PRODUCT_(\d+)\]', replace_product, body_html)

    # [BUY_N] → 추가 구매 버튼 (섹션 하단)
    def replace_buy(m):
        n = int(m.group(1)) - 1
        if 0 <= n < len(products):
            p = products[n]
            url = p.get("shortenUrl", p.get("productUrl", "#"))
            return (
                f'<div style="text-align:center;margin:1em 0 2em;">'
                f'<a href="{url}" rel="noopener noreferrer" target="_blank" '
                f'style="display:inline-block;background:#ff6f00;color:#fff;font-size:1em;'
                f'font-weight:700;padding:13px 32px;border-radius:30px;text-decoration:none;">'
                f'지금 바로 구매하기 &rarr;</a></div>'
            )
        return ""

    body_html = re.sub(r'\[BUY_(\d+)\]', replace_buy, body_html)

    # 히든 썸네일 (Blogger 미리보기용, HTML 최상단)
    hero_img = products[0].get("productImage", "") if products else ""
    thumb_html = (
        f'<img src="{hero_img}" alt="{title}" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);" '
        f'width="1" height="1" aria-hidden="true">\n'
    ) if hero_img else ""

    keywords_str = ", ".join(labels)

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": meta_desc,
        "keywords": keywords_str,
        "datePublished": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "author": {"@type": "Person", "name": "꿀통 몬스터 에디터"},
        "publisher": {"@type": "Organization", "name": "꿀통 몬스터",
                      "url": "https://ggultongmon.allsweep.xyz"},
        "inLanguage": "ko-KR",
        "articleSection": "쿠팡 상품 추천",
        "image": hero_img,
    }, ensure_ascii=False, indent=2)

    css = """\
<style>
.gg-post{font-family:'Noto Sans KR',sans-serif;line-height:1.85;color:#333;max-width:780px;}
.gg-post h2{color:#1a237e;font-size:1.25em;margin:2em 0 0.7em;padding-bottom:0.35em;border-bottom:2.5px solid #e8eaf6;}
.gg-post h3{color:#283593;margin:1.4em 0 0.5em;}
.gg-post table{width:100%;border-collapse:collapse;margin:1.5em 0;font-size:0.95em;}
.gg-post th{background:#3f51b5;color:#fff;padding:10px 13px;text-align:left;}
.gg-post td{padding:9px 13px;border:1px solid #e0e0e0;}
.gg-post tr:nth-child(even) td{background:#f5f7ff;}
.gg-post blockquote{background:#e8f5e9;border-left:4px solid #43a047;padding:12px 16px;margin:1.5em 0;border-radius:0 8px 8px 0;}
</style>"""

    return f"""{thumb_html}<script type="application/ld+json">
{json_ld}
</script>
<meta name="description" content="{meta_desc.replace('"','&quot;')}">
<meta name="keywords" content="{keywords_str}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="{title.replace('"','&quot;')}">
<meta property="og:description" content="{meta_desc.replace('"','&quot;')}">
<meta property="og:type" content="article">
<meta property="og:image" content="{hero_img}">
<meta name="twitter:card" content="summary_large_image">
{css}

<div class="gg-post" lang="ko">

{PARTNERS_NOTICE_HTML}

{body_html}

</div>
"""


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    topic   = sys.argv[2] if len(sys.argv) > 2 else f"{keyword} 가성비 추천 TOP5"
    products = get_products_with_shorten(keyword, limit=3)
    result = generate_post(topic, keyword, products)
    print(f"제목: {result['title']} | {result['char_count']:,}자")
