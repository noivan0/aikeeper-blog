"""
꿀통몬스터 블로그 주제 발굴 v2
- bestcategories API로 전체 카테고리 실시간 베스트 상품 수집
- Claude가 상품명 분석 → 블로그 최적 주제 + 검색 키워드 도출
- 가격 필터링: 로켓배송 우선, 카테고리별 최소 가격 적용
"""
import os, sys, json, random, time, urllib.request, urllib.parse, anthropic
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from coupang_api import _get, search_products

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
COUPANG_SUB_ID     = os.environ.get("COUPANG_SUB_ID", "ggultongmon")

# ── 카테고리 정의 (공식 API 기준) ──────────────────────────────────────
CATEGORIES = {
    1001: "여성패션",
    1002: "남성패션",
    1010: "뷰티",
    1011: "출산/유아동",
    1012: "식품",
    1013: "주방용품",
    1014: "생활용품",
    1015: "홈인테리어",
    1016: "가전디지털",
    1017: "스포츠/레저",
    1018: "자동차용품",
    1020: "완구/취미",
    1024: "헬스/건강식품",
    1029: "반려동물용품",
    1030: "유아동패션",
}

# 카테고리별 최소 가격 필터 (단순 소모품/샘플 제외)
MIN_PRICE = {
    1001: 8000,   # 여성패션
    1002: 8000,   # 남성패션
    1010: 5000,   # 뷰티
    1011: 5000,   # 출산/유아동
    1012: 3000,   # 식품
    1013: 5000,   # 주방용품
    1014: 3000,   # 생활용품
    1015: 10000,  # 홈인테리어
    1016: 15000,  # 가전디지털
    1017: 10000,  # 스포츠/레저
    1018: 5000,   # 자동차용품
    1020: 5000,   # 완구/취미
    1024: 5000,   # 헬스/건강식품
    1029: 5000,   # 반려동물용품
    1030: 5000,   # 유아동패션
}

# 블로그에 적합하지 않은 카테고리 (필요 시 비활성화)
SKIP_CATEGORIES = {1019}  # 도서/음반 — 쿠팡 파트너스 수수료 낮음


def get_best_products(cat_id: int, limit: int = 20) -> list:
    """bestcategories API로 카테고리 베스트 상품 수집 + 가격 필터"""
    path = f"/v2/providers/affiliate_open_api/apis/openapi/products/bestcategories/{cat_id}?limit={limit}&subId={COUPANG_SUB_ID}"
    try:
        d = _get(path)
        if d.get("rCode") != "0":
            return []
        products = d.get("data", [])
        min_p = MIN_PRICE.get(cat_id, 3000)
        # 가격 필터 + 로켓배송 우선 정렬
        filtered = [
            p for p in products
            if int(p.get("productPrice", 0)) >= min_p
        ]
        # 로켓배송 우선
        filtered.sort(key=lambda p: (0 if p.get("isRocket") else 1))
        return filtered
    except Exception as e:
        print(f"[WARN] bestcategories/{cat_id} 실패: {e}")
        return []


def pick_category_and_products() -> tuple[int, str, list]:
    """
    랜덤 카테고리 선택 → 베스트 상품 수집
    상품이 5개 미만이면 다른 카테고리로 재시도
    """
    candidates = [cid for cid in CATEGORIES if cid not in SKIP_CATEGORIES]
    random.shuffle(candidates)

    for cat_id in candidates[:5]:  # 최대 5개 카테고리 시도
        cat_name = CATEGORIES[cat_id]
        products = get_best_products(cat_id, limit=30)
        if len(products) >= 5:
            print(f"카테고리: {cat_name}({cat_id}) | 상품 {len(products)}개 수집")
            return cat_id, cat_name, products
        time.sleep(0.3)

    # fallback: 가전디지털 (항상 풍부)
    return 1016, "가전디지털", get_best_products(1016, limit=30)


def generate_topic_with_claude(cat_id: int, cat_name: str, products: list) -> dict:
    """
    Claude에게 베스트 상품 목록을 주고 블로그 포스트 최적 주제 선정 요청
    - 단순 카테고리명이 아닌 실제 상품명 기반으로 구체적 검색 키워드 도출
    """
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y년 %m월 %d일")

    # 상위 15개 상품 요약
    product_summary = "\n".join([
        f"[{i+1}] {p['productName'][:45]} | {int(p['productPrice']):,}원 | "
        f"{'로켓' if p.get('isRocket') else '일반'}"
        for i, p in enumerate(products[:15])
    ])

    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=ANTHROPIC_BASE_URL,
    )

    prompt = f"""오늘은 {today}. 쿠팡 '{cat_name}' 카테고리 실시간 베스트 상품 목록입니다.

{product_summary}

이 상품들을 분석해서 쿠팡 파트너스 블로그 '꿀통 몬스터' 포스트 주제를 선정하세요.

조건:
- 위 상품들 중 3개를 한 포스트에 묶을 수 있는 공통 주제 선정
- 소비자가 실제로 검색할 법한 구체적 키워드 (예: "탈모샴푸 추천" O, "뷰티" X)
- 단순 소모품/식재료보다 정보성 포스트 가능한 상품 우선 (예: 기기/용품/건강식품)
- 같은 카테고리라도 묶일 수 있는 상품이면 OK

===TOPIC===
포스트 제목 (50자 이내, 이모지 금지, 숫자/비교/추천 포함)
===SEARCH_KEYWORD===
파트너스 API 검색 키워드 (1~3단어, 한국어, 소비자가 검색할 실제 단어)
===PRODUCT_IDS===
위 목록에서 포스트에 쓸 상품 번호 (쉼표 구분, 3개, 예: 1,3,5)
===ANGLE===
포스트 작성 각도 한 줄 (독자 관점, 구체적)
===LABELS===
SEO 라벨 6~9개 (쉼표 구분, 실제 검색어 기반)
===META===
검색결과 설명 (150~160자)"""

    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text

    def extract(tag):
        s = text.find(f"==={tag}===")
        if s == -1: return ""
        s += len(f"==={tag}===")
        e = text.find("===", s)
        return text[s:e if e != -1 else None].strip()

    # Claude가 선택한 상품 인덱스로 실제 상품 추출
    try:
        ids = [int(x.strip())-1 for x in extract("PRODUCT_IDS").split(",") if x.strip().isdigit()]
        selected = [products[i] for i in ids if 0 <= i < len(products)]
    except Exception:
        selected = products[:3]

    if len(selected) < 3:
        selected = products[:3]

    return {
        "topic":          extract("TOPIC"),
        "search_keyword": extract("SEARCH_KEYWORD") or cat_name,
        "angle":          extract("ANGLE"),
        "labels":         [l.strip() for l in extract("LABELS").split(",") if l.strip()],
        "meta_desc":      extract("META"),
        "category":       cat_name,
        "cat_id":         cat_id,
        "selected_products": selected,  # ← Claude가 직접 선택한 상품 (재검색 불필요)
    }


def enrich_with_shorten(products: list) -> list:
    """선택된 상품에 shortenUrl 추가"""
    sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
    from coupang_api import get_shorten_urls
    try:
        urls = [p.get("productUrl", "") for p in products if p.get("productUrl")]
        shorten_map = get_shorten_urls(urls)
        for p in products:
            orig = p.get("productUrl", "")
            p["shortenUrl"] = shorten_map.get(orig, orig)
    except Exception as e:
        print(f"[WARN] shortenUrl 실패: {e}")
        for p in products:
            p["shortenUrl"] = p.get("productUrl", "#")
    return products


if __name__ == "__main__":
    # 수동 실행 시 env var로 주제/카테고리 지정 가능 (workflow_dispatch 지원)
    manual_topic    = os.environ.get("MANUAL_TOPIC", "").strip()
    manual_category = os.environ.get("MANUAL_CATEGORY", "").strip()

    # Step 1: 카테고리 베스트 상품 수집
    if manual_category:
        # 카테고리 이름으로 ID 찾기
        cat_id   = next((cid for cid, name in CATEGORIES.items() if manual_category in name), None)
        cat_name = manual_category if cat_id else "가전디지털"
        cat_id   = cat_id or 1016
        products = get_best_products(cat_id, limit=30)
        print(f"[수동] 카테고리: {cat_name}({cat_id})")
    else:
        cat_id, cat_name, products = pick_category_and_products()

    # Step 2: Claude 주제 선정 (수동 주제 지정 시 스킵)
    if manual_topic:
        print(f"[수동] 주제 고정: {manual_topic}")
        topic_data = generate_topic_with_claude(cat_id, cat_name, products)
        topic_data["topic"] = manual_topic  # 주제만 덮어쓰기
    else:
        print(f"Claude 주제 선정 중...")
        topic_data = generate_topic_with_claude(cat_id, cat_name, products)
    print(f"\n선정 주제: {topic_data['topic']}")
    print(f"검색 키워드: {topic_data['search_keyword']}")
    print(f"라벨: {topic_data['labels']}")
    print(f"선택 상품 {len(topic_data['selected_products'])}개:")
    for p in topic_data["selected_products"]:
        print(f"  - {p['productName'][:40]} / {int(p['productPrice']):,}원")

    # Step 3: shortenUrl 추가
    topic_data["selected_products"] = enrich_with_shorten(topic_data["selected_products"])

    # Step 4: CI output
    output_file = os.environ.get("GITHUB_OUTPUT", "/tmp/ggultongmon_topic.txt")

    # selected_products를 JSON으로 직렬화해서 전달
    products_json = json.dumps(topic_data["selected_products"], ensure_ascii=False)

    with open(output_file, "a") as f:
        f.write(f"topic={topic_data['topic']}\n")
        f.write(f"search_keyword={topic_data['search_keyword']}\n")
        f.write(f"angle={topic_data['angle']}\n")
        f.write(f"category={topic_data['category']}\n")
        f.write(f"labels={','.join(topic_data['labels'])}\n")
        f.write(f"meta_desc={topic_data['meta_desc']}\n")
        f.write(f"products_json={products_json}\n")

    print(f"\n저장 완료 → {output_file}")
