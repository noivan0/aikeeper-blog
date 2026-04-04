"""
꿀통몬스터 쿠팡 파트너스 블로그 포스트 생성기 v3
개선사항:
- 제목 패턴 5종 랜덤 → 다양성 확보
- FAQ 실제 검색어 기반 질문 생성 지시
- 상단 빠른구매 요약 카드 추가 (above the fold)
- 버튼 텍스트 7종 랜덤 (A/B 효과)
- 모바일 반응형 상품 카드
- subId env 변수화
- 하드코딩 최소화
"""
import os, sys, json, re, anthropic
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
padding:10px 16px;margin:0 0 1.6em;font-size:0.82em;color:#6d4c41;line-height:1.5;">
<strong>📢 파트너스 안내</strong>&nbsp;
이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
</div>"""

# ── 버튼 텍스트 7종 (A/B 랜덤) ────────────────────────────────────────
BUY_BUTTON_TEXTS = [
    "쿠팡에서 최저가 확인하기 →",
    "지금 바로 구매하기 →",
    "오늘 가격 확인하기 →",
    "로켓배송으로 빠르게 받기 →",
    "쿠팡 할인가 보러가기 →",
    "최저가로 구매하기 →",
    "상품 상세 보기 →",
]

# ── 제목 패턴 5종 (Claude에게 랜덤 지시) ──────────────────────────────
TITLE_PATTERNS = [
    "숫자+비교형: 예) 2026 에어프라이어 TOP3, 가격대별 완전 비교",
    "문제해결형: 예) 에어프라이어 고를 때 후회 안 하는 법, 실패 없는 선택 기준",
    "상황맞춤형: 예) 1인가구 에어프라이어 추천, 이 3가지면 충분합니다",
    "궁금증해소형: 예) 에어프라이어 비싼 게 좋을까? 가성비 3종 직접 비교",
    "시즌/트렌드형: 예) 2026년 지금 가장 많이 팔리는 에어프라이어 TOP3",
]

# ── 색상 테마 (변수화) ─────────────────────────────────────────────────
COLOR_PRIMARY   = os.environ.get("GG_COLOR_PRIMARY", "#e53935")    # 메인 빨강
COLOR_SECONDARY = os.environ.get("GG_COLOR_SECONDARY", "#ff6f00")  # 보조 주황
COLOR_ACCENT    = os.environ.get("GG_COLOR_ACCENT", "#1a237e")     # 강조 남색


def _pick(lst: list, seed: str) -> str:
    """seed 기반 결정론적 랜덤 선택 (같은 포스트는 일관성 유지)"""
    return lst[hash(seed) % len(lst)]


def build_quick_buy_bar(products: list) -> str:
    """
    포스트 최상단 빠른 구매 바 (Above the fold)
    스크롤 없이 바로 상품 확인 + 클릭 유도
    """
    items = []
    for i, p in enumerate(products[:3]):
        name  = p.get("productName", "")[:20] + "..."
        price = f"{int(p.get('productPrice', 0)):,}원"
        url   = p.get("shortenUrl", p.get("productUrl", "#"))
        btn_text = _pick(BUY_BUTTON_TEXTS, p.get("productName","") + "quick")
        items.append(
            f'<div style="flex:1;min-width:140px;text-align:center;padding:10px 8px;'
            f'border-right:1px solid #e8eaf6;">'
            f'<p style="margin:0 0 4px;font-size:0.75em;color:#9e9e9e;">TOP {i+1}</p>'
            f'<p style="margin:0 0 6px;font-size:0.85em;font-weight:700;color:#1a237e;'
            f'line-height:1.3;">{name}</p>'
            f'<p style="margin:0 0 8px;font-size:1em;font-weight:800;color:{COLOR_PRIMARY};">'
            f'{price}</p>'
            f'<a href="{url}" rel="noopener noreferrer" '
            f'style="display:inline-block;background:{COLOR_PRIMARY};color:#fff;'
            f'font-size:0.78em;font-weight:700;padding:7px 14px;border-radius:20px;'
            f'text-decoration:none;">구매하기</a>'
            f'</div>'
        )
    items_html = "\n".join(items)
    return f"""\
<div style="border:2px solid #e8eaf6;border-radius:14px;padding:14px;margin:0 0 2em;
background:linear-gradient(135deg,#f8f9ff 0%,#ffffff 100%);">
  <p style="margin:0 0 10px;font-size:0.8em;font-weight:700;color:#616161;
  letter-spacing:0.5px;text-transform:uppercase;">추천 상품 바로 구매</p>
  <div style="display:flex;gap:0;flex-wrap:wrap;">
{items_html}
  </div>
</div>"""


def build_inline_card(product: dict, rank: int, title_seed: str = "") -> str:
    """
    상품 인라인 카드 (본문 h2 섹션 안)
    - 모바일 반응형 (flex-wrap + 최소 너비)
    - 버튼 텍스트 랜덤
    """
    name      = product.get("productName", "상품명 없음")[:55]
    price     = f"{int(product.get('productPrice', 0)):,}"
    img_url   = product.get("productImage", "")
    buy_url   = product.get("shortenUrl", product.get("productUrl", "#"))
    is_rocket = product.get("isRocket", False)
    is_free   = product.get("isFreeShipping", False)

    badges = ""
    if is_rocket:
        badges += ('<span style="background:#00bcd4;color:#fff;font-size:0.72em;'
                   'padding:3px 9px;border-radius:20px;margin-right:5px;">로켓배송</span>')
    if is_free:
        badges += ('<span style="background:#66bb6a;color:#fff;font-size:0.72em;'
                   'padding:3px 9px;border-radius:20px;">무료배송</span>')

    btn_text = _pick(BUY_BUTTON_TEXTS, title_seed + name)

    return f"""\
<div style="border:2px solid #e8eaf6;border-radius:16px;padding:18px;margin:1.4em 0 2em;
background:#f8f9ff;">
  <div style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-bottom:14px;">
    <!-- 상품 이미지 -->
    <a href="{buy_url}" rel="noopener noreferrer"
       style="flex-shrink:0;display:block;">
      <img src="{img_url}" alt="{name}"
           style="width:130px;height:130px;object-fit:contain;border-radius:12px;
           border:1px solid #e0e0e0;background:#fff;display:block;"
           loading="lazy">
    </a>
    <!-- 상품 정보 -->
    <div style="flex:1;min-width:150px;">
      <p style="margin:0 0 5px;font-size:0.75em;color:#9e9e9e;font-weight:700;
      letter-spacing:0.8px;">TOP {rank}</p>
      <p style="margin:0 0 7px;font-size:1.02em;font-weight:700;color:{COLOR_ACCENT};
      line-height:1.4;">{name}</p>
      <p style="margin:0 0 9px;">{badges}</p>
      <p style="margin:0;font-size:1.45em;font-weight:800;color:{COLOR_PRIMARY};">
        {price}<span style="font-size:0.52em;font-weight:500;color:#9e9e9e;
        margin-left:2px;">원</span>
      </p>
    </div>
  </div>
  <!-- CTA 버튼 (풀 너비) -->
  <a href="{buy_url}" rel="noopener noreferrer"
     style="display:block;text-align:center;background:{COLOR_PRIMARY};color:#fff;
     font-size:1.02em;font-weight:700;padding:14px 20px;border-radius:12px;
     text-decoration:none;letter-spacing:-0.2px;">
    {btn_text}
  </a>
</div>"""


def build_section_buy_btn(product: dict, title_seed: str = "") -> str:
    """섹션 하단 보조 구매 버튼 (색상 구분)"""
    url      = product.get("shortenUrl", product.get("productUrl", "#"))
    btn_text = _pick(BUY_BUTTON_TEXTS, title_seed + product.get("productName","") + "btn")
    return (
        f'<div style="text-align:center;margin:0.8em 0 2.2em;">'
        f'<a href="{url}" rel="noopener noreferrer" '
        f'style="display:inline-block;background:{COLOR_SECONDARY};color:#fff;'
        f'font-size:0.98em;font-weight:700;padding:13px 34px;border-radius:30px;'
        f'text-decoration:none;">{btn_text}</a></div>'
    )


# ── Claude 시스템 프롬프트 ─────────────────────────────────────────────
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
1. 도입부 훅 (200~300자): 독자가 공감할 상황으로 시작
2. 선택 기준 (h2): 구매 시 체크할 핵심 포인트 3~5개
3. 각 상품별 h2 섹션:
   - h2 제목 직후 반드시 [PRODUCT_N] 마커 한 줄
   - 상세 설명 300~500자 (장점 2~3개 불릿, 추천 대상)
   - 섹션 끝에 [BUY_N] 마커 한 줄
4. 비교표 (h2): 가격/특징/추천대상 3열 이상, 추천 상품 강조
5. FAQ (h2): 실제 네이버·구글 검색창에 칠 법한 질문 4~5개
   - 구어체·단답 검색어 형태 ("~하면 어때요?", "~차이 뭐예요?" 등)
   - 각 답변 150자 이상
6. 마무리 (h2): 한 줄 정리 + 구체적 구매 권유

## 금지 사항
- 본문에 "파트너스 활동", "수수료를 제공받습니다" 문구 절대 삽입 금지
- 이모지 사용 금지 (비교표 ✓/✗ 제외)
"""


def generate_post(topic: str, search_keyword: str, products: list,
                  angle: str = "", meta_desc: str = "") -> dict:
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y년 %m월 %d일")

    # 제목 패턴 랜덤 선택
    title_pattern = _pick(TITLE_PATTERNS, topic)

    product_info = "\n".join([
        f"[PRODUCT_{i+1}] {p['productName'][:50]} | {int(p.get('productPrice',0)):,}원 | "
        f"로켓:{p.get('isRocket',False)} | 무료:{p.get('isFreeShipping',False)}"
        for i, p in enumerate(products)
    ])

    prompt = f"""오늘은 {today}. 아래 상품 정보로 꿀통 몬스터 블로그 포스트를 작성하세요.

포스트 주제: {topic}
글쓰기 각도: {angle}

[상품 목록 — 각 섹션 마커 삽입 필수]
{product_info}

제목 작성 지침:
아래 패턴을 사용하세요: {title_pattern}
(패턴 참고만, 실제 상품에 맞게 창의적으로 작성)

===TITLE===
최종 포스트 제목 (50자 이내, 이모지 금지)
===META===
검색결과 노출 설명문 (150~160자, 핵심 키워드 포함, "지금 확인하세요" 등 CTA 포함)
===CONTENT===
포스트 본문 (Markdown)
[각 상품 h2 바로 아래 [PRODUCT_N], 섹션 끝에 [BUY_N] 반드시 삽입]
===FAQ===
Q1: (네이버 검색창에 칠 법한 구어체 질문)
A1: (150자 이상 답변)
Q2:
A2:
Q3:
A3:
Q4:
A4:
===END===
"""

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=ANTHROPIC_BASE_URL,
    )

    print(f"   Claude 포스트 생성 중... ({ANTHROPIC_MODEL}) | 제목패턴: {title_pattern[:30]}...")
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
    meta    = extract("META") or meta_desc

    # 이모지 제거 (제목만)
    title = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001F9FF]', '', title).strip()
    char_count = len(content.replace(' ', '').replace('\n', ''))
    print(f"   생성 완료: {char_count:,}자 | 제목: {title[:40]}")

    return {
        "title": title, "content": content,
        "faq_raw": faq_raw, "meta_desc": meta,
        "char_count": char_count,
    }


def build_full_html(title: str, content: str, products: list,
                    labels: list, meta_desc: str, faq_raw: str = "") -> str:
    """
    최종 Blogger HTML
    - 최상단: 히든 썸네일 → JSON-LD → 메타태그
    - 본문: 파트너스 고지(1회) → 빠른구매바 → 본문
    - [PRODUCT_N]/[BUY_N] → 카드/버튼 치환
    """
    import markdown as md_lib

    # 본문 내 중복 파트너스 고지 제거
    content = re.sub(
        r'(>?\s*)?(본\s*포스트|이\s*포스팅|이\s*글)[은는이]\s*쿠팡\s*파트너스\s*활동[^\n]{0,150}',
        '', content, flags=re.IGNORECASE
    ).strip()

    # TOC(목차) 자동 생성 — h2 헤딩 추출
    h2_list = re.findall(r'^## (.+)$', content, re.MULTILINE)
    toc_html = ""
    if len(h2_list) >= 3:
        toc_items = []
        for i, h in enumerate(h2_list):
            anchor = re.sub(r'[^\w가-힣]', '-', h).strip('-').lower()
            toc_items.append(
                f'<li style="margin:5px 0;">'
                f'<a href="#{anchor}" style="color:{COLOR_ACCENT};text-decoration:none;'
                f'font-size:0.93em;">▸ {h}</a></li>'
            )
        toc_html = (
            f'<div style="background:#f0f4ff;border:1px solid #c5cae9;border-radius:12px;'
            f'padding:16px 20px;margin:0 0 2em;">'
            f'<p style="margin:0 0 10px;font-weight:700;color:{COLOR_ACCENT};font-size:0.95em;">'
            f'📋 목차</p>'
            f'<ul style="margin:0;padding-left:10px;list-style:none;">'
            + "\n".join(toc_items) +
            f'</ul></div>'
        )
        # 앵커 ID를 h2에 삽입 (Markdown 처리 전)
        def add_anchor(m):
            h = m.group(1)
            anchor = re.sub(r'[^\w가-힣]', '-', h).strip('-').lower()
            return f'## <span id="{anchor}"></span>{h}'
        content = re.sub(r'^## (.+)$', add_anchor, content, flags=re.MULTILINE)

    # Markdown → HTML
    body_html = md_lib.markdown(
        content,
        extensions=["tables", "fenced_code", "nl2br", "toc"]
    )

    # [PRODUCT_N] → 상품 인라인 카드
    def replace_product(m):
        n = int(m.group(1)) - 1
        if 0 <= n < len(products):
            return build_inline_card(products[n], n + 1, title_seed=title)
        return ""

    body_html = re.sub(r'\[PRODUCT_(\d+)\]', replace_product, body_html)

    # [BUY_N] → 보조 구매 버튼
    def replace_buy(m):
        n = int(m.group(1)) - 1
        if 0 <= n < len(products):
            return build_section_buy_btn(products[n], title_seed=title)
        return ""

    body_html = re.sub(r'\[BUY_(\d+)\]', replace_buy, body_html)

    # 상단 빠른구매바
    quick_bar_html = build_quick_buy_bar(products)

    # 히든 썸네일 (Blogger 미리보기)
    hero_img = products[0].get("productImage", "") if products else ""
    thumb_html = (
        f'<img src="{hero_img}" alt="{title}" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;'
        f'clip:rect(0,0,0,0);white-space:nowrap;" width="1" height="1" aria-hidden="true">\n'
    ) if hero_img else ""

    keywords_str = ", ".join(labels)

    # FAQ → JSON-LD FAQPage
    faq_items = []
    faq_blocks = re.findall(r'Q(\d+):\s*(.+?)\nA\1:\s*(.+?)(?=\nQ\d+:|\Z)', faq_raw, re.DOTALL)
    for _, q, a in faq_blocks:
        faq_items.append({
            "@type": "Question",
            "name": q.strip(),
            "acceptedAnswer": {"@type": "Answer", "text": a.strip()[:500]}
        })

    json_ld_blog = json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": meta_desc[:160],
        "keywords": keywords_str,
        "datePublished": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "author": {"@type": "Person", "name": "꿀통 몬스터 에디터"},
        "publisher": {"@type": "Organization", "name": "꿀통 몬스터",
                      "url": "https://ggultongmon.allsweep.xyz"},
        "inLanguage": "ko-KR",
        "articleSection": "쿠팡 상품 추천",
        "image": hero_img,
    }, ensure_ascii=False, indent=2)

    json_ld_faq = ""
    if faq_items:
        json_ld_faq = f'\n<script type="application/ld+json">\n{json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":faq_items},ensure_ascii=False,indent=2)}\n</script>'

    css = f"""\
<style>
.gg-post{{font-family:'Noto Sans KR',sans-serif;line-height:1.85;color:#333;max-width:800px;}}
.gg-post h2{{color:{COLOR_ACCENT};font-size:1.22em;margin:2em 0 0.7em;
  padding-bottom:0.35em;border-bottom:2.5px solid #e8eaf6;}}
.gg-post h3{{color:#283593;margin:1.4em 0 0.5em;}}
.gg-post table{{width:100%;border-collapse:collapse;margin:1.5em 0;font-size:0.93em;}}
.gg-post th{{background:{COLOR_ACCENT};color:#fff;padding:10px 12px;text-align:left;}}
.gg-post td{{padding:9px 12px;border:1px solid #e0e0e0;}}
.gg-post tr:nth-child(even) td{{background:#f5f7ff;}}
.gg-post tr td:first-child{{font-weight:600;}}
.gg-post blockquote{{background:#e8f5e9;border-left:4px solid #43a047;
  padding:12px 16px;margin:1.5em 0;border-radius:0 8px 8px 0;}}
/* 비교표 추천 행 강조 */
.gg-post table tr.best-pick td{{background:#fff8e1!important;font-weight:700;
  border-left:3px solid {COLOR_PRIMARY};}}
.gg-post table tr td:has(span.best){{background:#fff8e1;}}
/* FAQ 섹션 스타일 */
.gg-post .faq-item{{border:1px solid #e8eaf6;border-radius:10px;margin:10px 0;
  padding:14px 18px;background:#fafafa;}}
.gg-post .faq-q{{font-weight:700;color:{COLOR_ACCENT};margin:0 0 6px;}}
.gg-post .faq-a{{color:#444;margin:0;font-size:0.95em;line-height:1.7;}}
/* 모바일 상품카드 최적화 */
@media(max-width:480px){{
  .gg-post .prod-card img{{width:100px!important;height:100px!important;}}
  .gg-post .prod-card .prod-info{{min-width:120px!important;}}
  .gg-post .quick-bar>div{{min-width:100%!important;border-right:none!important;
    border-bottom:1px solid #e8eaf6;}}
}}
</style>"""

    # FAQ → 구조화된 HTML 카드 (JSON-LD와 별도로 시각적으로도 렌더링)
    faq_html = ""
    if faq_items:
        faq_card_items = "".join(
            f'<div class="faq-item">'
            f'<p class="faq-q">Q. {item["name"]}</p>'
            f'<p class="faq-a">{item["acceptedAnswer"]["text"]}</p>'
            f'</div>'
            for item in faq_items
        )
        faq_html = (
            f'<h2 id="faq"><span id="faq"></span>자주 묻는 질문 (FAQ)</h2>\n'
            f'<div class="faq-section">{faq_card_items}</div>\n'
        )
        # body_html 내 기존 FAQ h2 중복 제거 (Claude가 본문에 넣은 경우)
        body_html = re.sub(
            r'<h2[^>]*>[^<]*FAQ[^<]*</h2>.*?(?=<h2|$)',
            '', body_html, flags=re.DOTALL | re.IGNORECASE
        )

    return (
        f"{thumb_html}"
        f'<script type="application/ld+json">\n{json_ld_blog}\n</script>'
        f"{json_ld_faq}\n"
        f'<meta name="description" content="{meta_desc[:160].replace(chr(34),"&quot;")}">\n'
        f'<meta name="keywords" content="{keywords_str}">\n'
        f'<meta name="robots" content="index, follow, max-image-preview:large">\n'
        f'<meta property="og:title" content="{title.replace(chr(34),"&quot;")}">\n'
        f'<meta property="og:description" content="{meta_desc[:160].replace(chr(34),"&quot;")}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:image" content="{hero_img}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f"{css}\n\n"
        f'<div class="gg-post" lang="ko">\n\n'
        f"{PARTNERS_NOTICE_HTML}\n\n"
        f"{quick_bar_html}\n\n"
        f"{toc_html}\n\n"
        f"{body_html}\n\n"
        f"{faq_html}\n\n"
        f"</div>\n"
    )


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    topic   = sys.argv[2] if len(sys.argv) > 2 else f"{keyword} 가성비 추천 TOP5"
    products = get_products_with_shorten(keyword, limit=3)
    result = generate_post(topic, keyword, products)
    print(f"제목: {result['title']} | {result['char_count']:,}자")
