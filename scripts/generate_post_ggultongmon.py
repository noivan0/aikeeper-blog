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

# .env 자동 로드 (cron/subprocess 환경에서도 동작)
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env_loader import load_env, make_anthropic_client, get_model
load_env()
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from coupang_api import get_products_with_shorten

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ── AdSense 설정 (ggultongmon 블로그) ────────────────────────────────
_ADSENSE_PUB_GG       = "ca-pub-2597570939533872"
_DISPLAY_SLOT_GG      = "8117048415"
_IN_ARTICLE_SLOT_GG   = "6675974233"

# ── 인아티클 광고 (본문 중간 삽입용 — script 중복 없음) ────────────────
_AD_IN_ARTICLE_GG = f"""\
<div style="margin:2.5em 0;text-align:center;min-height:200px;">
<ins class="adsbygoogle"
 style="display:block;text-align:center;"
 data-ad-layout="in-article"
 data-ad-format="fluid"
 data-ad-client="{_ADSENSE_PUB_GG}"
 data-ad-slot="{_IN_ARTICLE_SLOT_GG}"
 data-full-width-responsive="true"></ins>
<script defer>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""

_AD_DISPLAY_GG = f"""\
<div style="margin:2.5em 0;min-height:100px;">
<ins class="adsbygoogle"
 style="display:block"
 data-ad-client="{_ADSENSE_PUB_GG}"
 data-ad-slot="{_DISPLAY_SLOT_GG}"
 data-ad-format="auto"
 data-full-width-responsive="true"></ins>
<script defer>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""

# ── 파트너스 고지문 (최상단 1회만) ─────────────────────────────────────
# 쿠팡 링크 클릭 전 광고 최대 노출 전략:
# 파트너스 고지문 바로 다음에 디스플레이 광고 삽입
PARTNERS_NOTICE_HTML = f"""\
<div style="background:#fff8e1;border:1px solid #ffc107;border-radius:10px;\
padding:10px 16px;margin:0 0 1.2em;font-size:0.82em;color:#6d4c41;line-height:1.5;">
<strong>📢 파트너스 안내</strong>&nbsp;
이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
</div>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={_ADSENSE_PUB_GG}" crossorigin="anonymous"></script>
<div style="margin:0 0 1.6em;min-height:100px;">
<ins class="adsbygoogle"
 style="display:block"
 data-ad-client="{_ADSENSE_PUB_GG}"
 data-ad-slot="{_DISPLAY_SLOT_GG}"
 data-ad-format="auto"
 data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
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
    # 광고 카피형 — 궁금증/불안 자극 (클릭 유도 최우선)
    "광고카피_충격형: 예) 장갑 하나 잘못 골라서 손 다쳤습니다 / 이 이어폰 샀다가 환불했습니다",
    "광고카피_비밀형: 예) 요리 유튜버들이 조용히 쓰는 장갑이 있습니다 / 피부과 의사가 추천하는 클렌저",
    "광고카피_대결형: 예) 3만원짜리 vs 7천원짜리, 진짜 차이는 이겁니다 / 국산 vs 일제, 써보니 달랐습니다",
    "광고카피_경고형: 예) 이거 모르고 사면 두 번 삽니다 / 이 실수만 안 해도 반은 성공입니다",
    "광고카피_공감형: 예) 저도 처음엔 비싼 걸 샀습니다 / 3개 다 써봤는데 결론은 하나였습니다",
    "광고카피_질문형: 예) 왜 같은 가격인데 이렇게 다를까요? / 비싼 게 정말 좋은 건지 직접 확인했습니다",
    "광고카피_숫자형: 예) 3만원 아끼려다 30만원 날렸습니다 / 딱 이 3가지만 보면 실패 없습니다",
]

# ── 색상 테마 (변수화) ─────────────────────────────────────────────────
COLOR_PRIMARY   = os.environ.get("GG_COLOR_PRIMARY", "#e53935")    # 메인 빨강
COLOR_SECONDARY = os.environ.get("GG_COLOR_SECONDARY", "#ff6f00")  # 보조 주황
COLOR_ACCENT    = os.environ.get("GG_COLOR_ACCENT", "#1a237e")     # 강조 남색


def minify_css(css: str) -> str:
    """CSS 인라인 최소화 — 공백/주석 제거로 페이로드 크기 축소"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)  # 주석 제거
    css = re.sub(r'\s+', ' ', css)                         # 공백 압축
    css = re.sub(r';\s*}', '}', css)                       # 마지막 세미콜론
    css = re.sub(r':\s+', ':', css)                        # 콜론 뒤 공백
    css = re.sub(r',\s+', ',', css)                        # 콤마 뒤 공백
    css = re.sub(r'{\s+', '{', css)                        # 중괄호 뒤 공백
    css = re.sub(r'\s+{', '{', css)                        # 중괄호 앞 공백
    return css.strip()


def compress_html(html: str) -> str:
    """HTML 출력 경량화 — Blogger 저장 크기 축소 (pre/code 내부 보호)"""
    # 연속 빈줄 → 단일 빈줄
    html = re.sub(r'\n{3,}', '\n\n', html)
    # 태그 사이 불필요한 공백 (pre 내부는 건드리지 않음)
    html = re.sub(r'>\s{2,}<', '> <', html)
    return html


def optimize_coupang_img(url: str, width: int = 300) -> str:
    """쿠팡 CDN 이미지 크기 최적화 — 더 작은 이미지 요청으로 LCP 개선"""
    if 'coupangcdn.com' in url or 'thumbnail' in url.lower():
        if '?' not in url:
            return f"{url}?w={width}"
        elif 'w=' not in url:
            return f"{url}&w={width}"
    return url


def fetch_related_posts(current_url: str, category: str, limit: int = 3) -> list:
    """atom.xml에서 현재 글 제외, 같은 카테고리 우선 관련 글 추출"""
    import urllib.request, xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(
            "https://ggultongmon.allsweep.xyz/atom.xml",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        posts = []
        for entry in root.findall('atom:entry', ns):
            url = ''
            for link in entry.findall('atom:link', ns):
                if link.get('rel') == 'alternate':
                    url = link.get('href', '')
                    break
            if not url or url == current_url:
                continue
            title = entry.findtext('atom:title', namespaces=ns) or ''
            cats = [c.get('term', '') for c in entry.findall('atom:category', ns)]
            # 같은 카테고리 우선 (score 2), 그 외 최신 글 (score 1)
            score = 2 if category in cats else 1
            posts.append({'url': url, 'title': title, 'score': score})
        posts.sort(key=lambda x: x['score'], reverse=True)
        return posts[:limit]
    except Exception as e:
        print(f"[WARN] fetch_related_posts 실패: {e}")
        return []


def build_related_posts_html(related: list) -> str:
    """관련 글 추천 섹션 HTML 생성"""
    if not related:
        return ""
    items_html = "\n".join(
        f'<li style="margin:8px 0;">'
        f'<a href="{p["url"]}" style="color:{COLOR_ACCENT};text-decoration:none;'
        f'font-size:0.95em;font-weight:600;">▸ {p["title"]}</a>'
        f'</li>'
        for p in related
    )
    return (
        f'<div style="background:#f0f4ff;border:1px solid #c5cae9;border-radius:12px;'
        f'padding:18px 22px;margin:2em 0 1.5em;">'
        f'<p style="margin:0 0 12px;font-weight:700;color:{COLOR_ACCENT};font-size:0.97em;">'
        f'📌 함께 읽으면 좋은 글</p>'
        f'<ul style="margin:0;padding-left:4px;list-style:none;">'
        f'{items_html}'
        f'</ul></div>'
    )


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
            f'<a href="{url}" rel="nofollow sponsored noopener" '
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
    - 이미지: 썸네일(300px 카드) + 중간(600px 클릭 확대)
    """
    from coupang_api import get_product_images
    name      = product.get("productName", "상품명 없음")[:55]
    price     = f"{int(product.get('productPrice', 0)):,}"
    imgs      = get_product_images(product)
    img_url   = imgs["thumb"] or optimize_coupang_img(product.get("productImage", ""), width=300)
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
    <a href="{buy_url}" rel="nofollow sponsored noopener"
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
  <a href="{buy_url}" rel="nofollow sponsored noopener"
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
        f'<a href="{url}" rel="nofollow sponsored noopener" '
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
- 분량: 최소 5,000자 이상 (5,000~7,000자 목표)

## E-E-A-T 강화 규칙 (구글 Helpful Content Update 2023~ 핵심 랭킹 신호)
- 상품 직접 사용 경험 기반 서술 ("실제로 써보니", "배송받아서 확인하니")
- 단점 필수 언급 (신뢰성 ↑ — 장점만 나열하면 광고성 콘텐츠로 평가됨)
- 가격 정보에 날짜 명시 ("2026년 4월 기준 쿠팡 최저가")

## 글 품질 강화 지침
- 각 상품 섹션: 실제 구매자 입장의 장단점 솔직하게 작성 (단점도 1개 반드시 언급)
- 비교표: "이런 분께 추천" 열 반드시 포함
- 도입부: 독자가 처한 구체적 상황 묘사 (예: "주방에 새 에어프라이어를 들이려는데 어떤 걸 골라야 할지 막막하셨죠?")
- 가격 정보: 현재 쿠팡 가격 기준으로 "원래 OOO원 → 현재 OOO원 할인" 형식 (가능 시)
- 분량: 최소 5,000자 이상

## 도입부(200~300자) 규칙
- 독자가 겪는 구체적 상황 묘사로 시작 (예: "에어프라이어를 새로 살까 고민 중인데 어떤 걸 골라야 할지 막막하셨나요?")
- "안녕하세요", "오늘은 ~에 대해 알아보겠습니다" 절대 금지
- 문제 제시 → 해결 예고 구조

## 포스트 구조 (반드시 준수)
1. 도입부 훅 (200~300자): 독자가 공감할 상황으로 시작
2. 선택 기준 (h2): 구매 시 체크할 핵심 포인트 3~5개
3. 각 상품별 h2 섹션:
   - h2 제목 직후 반드시 [PRODUCT_N] 마커 한 줄
   - 상세 설명 300~500자 (장점 2~3개 불릿, 추천 대상)
   - 섹션 끝에 [BUY_N] 마커 한 줄
4. 비교표 (h2): 가격/특징/추천대상 3열 이상, 추천 상품 강조
5. FAQ (h2): 실제 구글 검색창에 치는 구어체 질문 4~5개
   - "~는 얼마인가요?" (가격 검색 → 고CPC 유도)
   - "~와 ~의 차이는?" (비교 검색 → 고CTR)
   - "~하면 부작용/단점 있나요?" (우려 해소 → 전환율 높음)
   - "~를 사면 후회하나요?" (구매 결정 직전 검색)
   - 각 답변 150자 이상
6. 마무리 (h2): 한 줄 정리 + 구체적 구매 권유
7. 관련 검색어 마커 (본문 최하단): 아래 형식으로 반드시 1줄 추가
   `[RELATED_SEARCH:관련키워드1|관련키워드2|관련키워드3]`
   예: `[RELATED_SEARCH:에어프라이어 추천|에어프라이어 가성비|에어프라이어 비교]`
   (이 마커는 추후 내부 링크로 자동 교체됩니다 — 토픽 클러스터링)

## 상품 링크 밀도 규칙 (Google Affiliate 가이드라인 준수)
- 포스트당 쿠팡 상품 링크는 최대 5개 (PRODUCT/BUY 마커 합산)
- 상품 소개 외 본문 흐름에 링크 과잉 삽입 금지
- 각 상품 섹션은 1개 PRODUCT 카드 + 1개 BUY 버튼만 (중복 삽입 금지)

## 금지 사항
- 본문에 "파트너스 활동", "수수료를 제공받습니다" 문구 절대 삽입 금지
- 이모지 사용 금지 (비교표 ✓/✗ 제외)
- 상품 링크 5개 초과 금지
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
아래 광고 카피 스타일을 참고해서 작성하세요: {title_pattern}
(예시는 참고만 — 실제 상품과 상황에 맞게 창의적으로 변형)

제목 규칙:
- 광고 카피처럼 궁금증을 유발하거나 감정을 자극하는 문장으로 작성
- 50자 이내, 이모지 금지, 큰따옴표 금지
- "TOP3", "완전정리", "후회없는", "추천" 같은 진부한 클릭베이트는 지양
- 대신: 구체적 상황/결과/비교/충격 포인트로 클릭 욕구 자극
- 연도(2026)는 필요할 때만 (카피 흐름을 방해하면 생략)

===TITLE===
최종 포스트 제목 (50자 이내, 이모지 금지, 큰따옴표(" ") 절대 사용 금지 — 작은따옴표(')만 허용)
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

    client = make_anthropic_client(timeout=600, max_retries=2)

    print(f"   Claude 포스트 생성 중... ({get_model()}) | 제목패턴: {title_pattern[:30]}...")
    # 스트리밍 방식으로 호출 (non-streaming은 내부 API에서 500 발생)
    text = ""
    with client.messages.stream(
        model=get_model(),
        max_tokens=8192,
        system=SYSTEM_PROMPT_COUPANG,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk

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
    # Blogger API 400 방지: 제목 내 큰따옴표 → 작은따옴표
    title = title.replace('"', "'").replace('\u201c', "'").replace('\u201d', "'")
    # 제목 파싱 실패 시 topic으로 fallback (빈 제목 → Blogger가 JSON-LD 첫줄로 slug 생성하는 버그 방지)
    if not title or len(title) < 5 or title.startswith(("{", "@", "<", "http")):
        print(f"   [WARN] 제목 파싱 실패 → topic으로 대체")
        title = topic
    char_count = len(content.replace(' ', '').replace('\n', ''))
    print(f"   생성 완료: {char_count:,}자 | 제목: {title[:40]}")

    # ── 최소 글자수 3,500자 미만 → 자동 재생성 (최대 2회) ──────────────
    MIN_CHARS = 5000
    for _retry in range(2):
        if char_count >= MIN_CHARS:
            break
        print(f"   [RETRY {_retry+1}/2] {char_count:,}자 — {MIN_CHARS:,}자 미만, 내용 보강 재생성 중...")
        retry_prompt = (
            prompt +
            f"\n\n[필수] 위 글이 {char_count:,}자로 너무 짧습니다. "
            f"최소 {MIN_CHARS:,}자 이상이 되도록 각 섹션을 더 풍부하게 작성하세요:\n"
            "- 각 상품 설명을 500자 이상으로 확장\n"
            "- FAQ를 5개 이상, 각 답변 200자 이상\n"
            "- 비교표 아래 '언제 어떤 제품을 골라야 하는지' 추가 설명\n"
            "- 마무리 섹션에 구매 결정 도움말 추가"
        )
        _raw = ""
        with client.messages.stream(
            model=get_model(), max_tokens=8192,
            system=SYSTEM_PROMPT_COUPANG,
            messages=[{"role": "user", "content": retry_prompt}]
        ) as stream:
            for chunk in stream.text_stream:
                _raw += chunk
        def _ex(tag, src=_raw):
            s = src.find(f"==={tag}===")
            if s == -1: return ""
            s += len(f"==={tag}===")
            e = src.find("===", s)
            return src[s:e if e != -1 else None].strip()
        _title_new = _ex("TITLE") or title
        _content_new = _ex("CONTENT")
        _count_new = len(_content_new.replace(' ', '').replace('\n', ''))
        print(f"   재생성 결과: {_count_new:,}자")
        if _count_new > char_count:
            title, content, char_count = _title_new, _content_new, _count_new
        else:
            break  # 재생성해도 안 늘면 포기

    if char_count < MIN_CHARS:
        print(f"   [WARN] 최종 {char_count:,}자 — {MIN_CHARS:,}자 미달 (그대로 진행)")

    return {
        "title": title, "content": content,
        "faq_raw": faq_raw, "meta_desc": meta,
        "char_count": char_count,
    }


def build_full_html(title: str, content: str, products: list,
                    labels: list, meta_desc: str, faq_raw: str = "",
                    current_url: str = "", category: str = "") -> str:
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
    _first_product_replaced = [False]  # G-3: 첫 번째 이미지 LCP 추적용

    def replace_product(m):
        n = int(m.group(1)) - 1
        if 0 <= n < len(products):
            card_html = build_inline_card(products[n], n + 1, title_seed=title)
            # G-3: Core Web Vitals — 첫 번째 상품 이미지를 eager + fetchpriority=high로 교체
            if not _first_product_replaced[0]:
                card_html = card_html.replace(
                    'loading="lazy"',
                    'loading="eager" fetchpriority="high"',
                    1  # 첫 번째 img만
                )
                _first_product_replaced[0] = True
            return card_html
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
    # 구글 디스커버: 카테고리별 Unsplash 폴백 (1200x630 보장)
    DISCOVER_FALLBACK_IMAGES = {
        "주방":    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1200&h=630&fit=crop&auto=format",
        "가전":    "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=1200&h=630&fit=crop&auto=format",
        "뷰티":    "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?w=1200&h=630&fit=crop&auto=format",
        "건강":    "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?w=1200&h=630&fit=crop&auto=format",
        "패션":    "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&h=630&fit=crop&auto=format",
        "스포츠":  "https://images.unsplash.com/photo-1517649763962-0c623066013b?w=1200&h=630&fit=crop&auto=format",
        "출산":    "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=1200&h=630&fit=crop&auto=format",
        "반려":    "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=1200&h=630&fit=crop&auto=format",
        "default": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&h=630&fit=crop&auto=format",
    }
    _cat_key = next((k for k in DISCOVER_FALLBACK_IMAGES if k != "default" and k in title), "default")
    _discover_img = DISCOVER_FALLBACK_IMAGES[_cat_key]

    # 이미지 3종 준비 (coupang_api.get_product_images 활용)
    from coupang_api import get_product_images, optimize_coupang_img as _opt_img
    if products:
        _p0_imgs = get_product_images(products[0])
        hero_img     = _p0_imgs["medium"]   # 본문 대표 이미지 (600px)
        hero_img_og  = _p0_imgs["og"]       # OG/JSON-LD (1200px)
        hero_img_th  = _p0_imgs["thumb"]    # 히든 썸네일 (300px)
    else:
        hero_img = hero_img_og = hero_img_th = ""

    # og:image: 쿠팡 상품 이미지(1200px) 우선, 없으면 카테고리 폴백
    og_hero_img = hero_img_og if hero_img_og else _discover_img
    # 히든 썸네일: 항상 보장 (상품 이미지 우선, 없으면 폴백)
    # og:image용: 1200px 이미지 우선 (구글 디스커버리 최적화)
    thumb_src = hero_img_og if hero_img_og else (hero_img_th if hero_img_th else (hero_img if hero_img else _discover_img))
    # 썸네일: Blogger 피드 추출 + 구글 크롤러 인식을 위해 실제 크기로 렌더링
    # div로 감싸 overflow:hidden + max-height:0 → 레이아웃 비파괴, 크롤러 인식 OK
    thumb_html = (
        f'<div style="overflow:hidden;max-height:0;max-width:0;line-height:0;font-size:0;">'
        f'<img src="{thumb_src}" alt="{title}" width="1200" height="630" '
        f'style="width:1200px;height:630px;display:block;" loading="eager">'
        f'</div>\n'
    )

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
        "image": [
            {"@type": "ImageObject", "url": thumb_src, "width": 1200, "height": 1200},
            {"@type": "ImageObject", "url": thumb_src, "width": 1200, "height": 900},
            {"@type": "ImageObject", "url": thumb_src, "width": 1200, "height": 630},
        ],
    }, ensure_ascii=False, separators=(',', ':'))

    json_ld_faq = ""
    if faq_items:
        json_ld_faq = f'\n<script type="application/ld+json">\n{json.dumps({"@context":"https://schema.org","@type":"FAQPage","mainEntity":faq_items},ensure_ascii=False,separators=(",",":"))}\n</script>'

    _css_raw = (
        f".gg-post{{font-family:'Noto Sans KR',sans-serif;line-height:1.85;color:#333;max-width:800px;}}"
        f".gg-post h2{{color:{COLOR_ACCENT};font-size:1.22em;margin:2em 0 0.7em;padding-bottom:0.35em;border-bottom:2.5px solid #e8eaf6;}}"
        f".gg-post h3{{color:#283593;margin:1.4em 0 0.5em;}}"
        f".gg-post table{{width:100%;border-collapse:collapse;margin:1.5em 0;font-size:0.93em;}}"
        f".gg-post th{{background:{COLOR_ACCENT};color:#fff;padding:10px 12px;text-align:left;}}"
        f".gg-post td{{padding:9px 12px;border:1px solid #e0e0e0;}}"
        f".gg-post tr:nth-child(even) td{{background:#f5f7ff;}}"
        f".gg-post tr td:first-child{{font-weight:600;}}"
        f".gg-post blockquote{{background:#e8f5e9;border-left:4px solid #43a047;padding:12px 16px;margin:1.5em 0;border-radius:0 8px 8px 0;}}"
        f".gg-post table tr.best-pick td{{background:#fff8e1!important;font-weight:700;border-left:3px solid {COLOR_PRIMARY};}}"
        f".gg-post table tr td:has(span.best){{background:#fff8e1;}}"
        f".gg-post .faq-item{{border:1px solid #e8eaf6;border-radius:10px;margin:10px 0;padding:14px 18px;background:#fafafa;}}"
        f".gg-post .faq-q{{font-weight:700;color:{COLOR_ACCENT};margin:0 0 6px;}}"
        f".gg-post .faq-a{{color:#444;margin:0;font-size:0.95em;line-height:1.7;}}"
        f"@media(max-width:480px){{"
        f".gg-post .prod-card img{{width:100px!important;height:100px!important;}}"
        f".gg-post .prod-card .prod-info{{min-width:120px!important;}}"
        f".gg-post .quick-bar>div{{min-width:100%!important;border-right:none!important;border-bottom:1px solid #e8eaf6;}}"
        f"}}"
    )
    css = f"<style>{minify_css(_css_raw)}</style>"

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

    # ── AdSense 본문 중간 삽입 (COUPANG 전략: ②본문1/3 + ③본문2/3 + ④최하단) ──
    # PARTNERS_NOTICE_HTML에 ① 디스플레이 광고가 이미 있으므로
    # body_html에 ②③ 인아티클 + ④ 디스플레이 추가 → 총 4개
    def _inject_body_ads(bhtml: str) -> str:
        h2s = list(re.finditer(r'<h2[^>]*>', bhtml))
        total = len(h2s)
        if total < 2:
            # h2 부족 → 중간 + 끝에만
            mid = len(bhtml) // 2
            bhtml = bhtml[:mid] + _AD_IN_ARTICLE_GG + bhtml[mid:]
            bhtml = bhtml + _AD_IN_ARTICLE_GG
        else:
            # 1/3 지점 h2 앞 → 인아티클
            idx1 = max(1, total // 3)
            pos1 = h2s[idx1].start()
            bhtml = bhtml[:pos1] + _AD_IN_ARTICLE_GG + bhtml[pos1:]
            # 재계산
            h2s = list(re.finditer(r'<h2[^>]*>', bhtml))
            total = len(h2s)
            # 2/3 지점 h2 앞 → 인아티클
            idx2 = max(2, (total * 2) // 3)
            idx2 = min(idx2, total - 1)
            pos2 = h2s[idx2].start()
            bhtml = bhtml[:pos2] + _AD_IN_ARTICLE_GG + bhtml[pos2:]
        # 최하단 디스플레이
        bhtml = bhtml + _AD_DISPLAY_GG
        return bhtml

    body_html = _inject_body_ads(body_html)

    # 관련 글 추천 섹션 (FAQ 다음에 삽입)
    related_posts = fetch_related_posts(current_url, category, limit=3)
    related_html = build_related_posts_html(related_posts)
    print(f"   관련 글 {len(related_posts)}개 수집 (카테고리: {category})")

    raw_html = (
        f"{thumb_html}"
        f'<script type="application/ld+json">\n{json_ld_blog}\n</script>'
        f"{json_ld_faq}\n"
        f'<meta name="description" content="{meta_desc[:160].replace(chr(34),"&quot;")}">\n'
        f'<meta name="keywords" content="{keywords_str}">\n'
        f'<meta name="robots" content="index, follow, max-image-preview:large">\n'
        f'<meta property="og:title" content="{title.replace(chr(34),"&quot;")}">\n'
        f'<meta property="og:description" content="{meta_desc[:160].replace(chr(34),"&quot;")}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:image" content="{og_hero_img}">\n'
        f'<meta property="og:image:width" content="1200">\n'
        f'<meta property="og:image:height" content="630">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f"{css}\n\n"
        f'<div class="gg-post" lang="ko">\n\n'
        f"{PARTNERS_NOTICE_HTML}\n\n"
        f'<div style="background:linear-gradient(135deg,#fff8e1 0%,#fffde7 100%);border:1.5px solid #ffe082;border-radius:14px;padding:1.1em 1.5em;margin:0 0 1.8em;font-size:0.94em;line-height:1.8;box-shadow:0 2px 8px rgba(255,193,7,0.12);">\n'
        f'<div style="display:flex;align-items:center;gap:8px;font-weight:800;color:#e65100;margin-bottom:0.4em;">🛒 이 글 핵심 요약</div>\n'
        f'<div style="color:#333;">이 글에서는 <strong>{title[:30]}</strong> 관련 쿠팡 실판매 상품을 분석해 가성비·기능·사용자 후기 기준 TOP3를 추천합니다. 각 상품 특징과 선택 기준을 꼼꼼히 정리했습니다.</div>\n'
        f'</div>\n\n'
        f"{quick_bar_html}\n\n"
        f"{toc_html}\n\n"
        f"{body_html}\n\n"
        f"{faq_html}\n\n"
        f"{related_html}\n\n"
        f"</div>\n"
    )
    return compress_html(raw_html)


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    topic   = sys.argv[2] if len(sys.argv) > 2 else f"{keyword} 가성비 추천 TOP5"
    products = get_products_with_shorten(keyword, limit=3)
    result = generate_post(topic, keyword, products)
    print(f"제목: {result['title']} | {result['char_count']:,}자")
