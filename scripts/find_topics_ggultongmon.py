"""
꿀통몬스터 블로그 주제 발굴 v4
- bestcategories API로 전체 카테고리 실시간 베스트 상품 수집
- Claude가 상품명 분석 → 블로그 최적 주제 + 검색 키워드 도출
- 가격 필터링: 로켓배송 우선, 카테고리별 최소 가격 적용
- 요일별 카테고리 테마 + 시즌 키워드 선점 전략 적용
- 중복 주제 방지: Blogger API로 최근 30개 포스트 제목 수집 → 유사도 차단
"""
import os, sys, json, random, time, re, hashlib, urllib.request, urllib.parse, urllib.error, anthropic
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))

from coupang_api import _get, search_products

ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
COUPANG_SUB_ID     = os.environ.get("COUPANG_SUB_ID", "ggultongmon")

# ── 중복 주제 방지 유틸 ──────────────────────────────────────────────────
def get_words(text: str) -> set:
    return set(re.findall(r"[\w가-힣]{2,}", text.lower()))

def bigrams(text: str) -> set:
    words = re.findall(r"[\w가-힣]{2,}", text.lower())
    return {(words[i], words[i+1]) for i in range(len(words)-1)}

def topic_similarity(a: str, b: str) -> float:
    wa, wb = get_words(a), get_words(b)
    ba, bb = bigrams(a), bigrams(b)
    ws = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    bs = len(ba & bb) / len(ba | bb) if ba and bb else 0.0
    return (ws + bs) / 2.0

def is_duplicate_topic(topic: str, used_titles: list, threshold: float = 0.30) -> bool:
    """기존 포스트 제목과 유사도가 threshold 이상이면 중복으로 판단"""
    t = topic.lower()
    for u in used_titles:
        sim = topic_similarity(t, u)
        if sim >= threshold:
            return True
        # 핵심 키워드 3개 이상 겹쳐도 중복
        if len(get_words(t) & get_words(u)) >= 3:
            return True
    return False

def load_recent_post_titles(blog_id: str, refresh_token: str, client_id: str, client_secret: str, max_posts: int = 50) -> list:
    """Blogger API로 최근 포스트 제목 수집"""
    try:
        # access token 발급
        token_url = "https://oauth2.googleapis.com/token"
        body = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(token_url, data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as r:
            token_data = json.loads(r.read())
        access_token = token_data["access_token"]

        # 포스트 목록 가져오기
        api_url = (f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
                   f"?maxResults={max_posts}&fields=items(title)&fetchBodies=false")
        req2 = urllib.request.Request(api_url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2, timeout=10) as r2:
            data = json.loads(r2.read())
        titles = [item["title"] for item in data.get("items", []) if item.get("title")]
        print(f"[중복방지] 최근 포스트 {len(titles)}개 로드")
        return titles
    except Exception as e:
        print(f"[WARN] 포스트 제목 로드 실패: {e}")
        return []

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

# ── 요일별 카테고리 테마 (0=월, 1=화, ..., 6=일) ───────────────────────
# 각 요일에 우선 탐색할 카테고리 ID 리스트 (순서 = 우선순위)
WEEKDAY_THEME = {
    0: [1013, 1016, 1015],        # 월: 주방용품, 가전디지털, 홈인테리어
    1: [1010, 1024, 1011],        # 화: 뷰티, 헬스/건강식품, 출산/유아동
    2: [1001, 1002, 1030],        # 수: 여성패션, 남성패션, 유아동패션
    3: [1017, 1018, 1020],        # 목: 스포츠/레저, 자동차용품, 완구/취미
    4: [1016, 1013, 1014],        # 금: 가전디지털, 주방용품, 생활용품
    5: [1011, 1012, 1029],        # 토: 출산/유아동, 식품, 반려동물용품
    6: [1029, 1012, 1024],        # 일: 반려동물용품, 식품, 헬스/건강식품
}

# ── 시즌 키워드 우선순위 테이블 ────────────────────────────────────────
# (월, 카테고리ID, 검색 키워드, 앵글)
SEASON_KEYWORDS = [
    # 4월
    (4,  1017, "캠핑 장비 추천",          "봄 캠핑 시즌 선점"),
    (4,  1014, "공기청정기 추천 미세먼지", "봄철 미세먼지 대비"),
    (4,  1001, "봄 여성 가디건 추천",      "봄 패션 시즌"),
    (4,  1002, "봄 남성 아우터 추천",      "봄 패션 시즌"),
    # 5월
    (5,  1020, "어버이날 선물 추천",       "어버이날 선물 성수기"),
    (5,  1024, "스승의날 선물 건강식품",   "스승의날 선물 성수기"),
    (5,  1016, "에어컨 추천 2026",         "여름 에어컨 사전 구매"),
    (5,  1017, "등산 용품 추천",           "봄 등산 시즌"),
    # 6월
    (6,  1015, "냉감 침구 여름 추천",      "여름 침구 성수기"),
    (6,  1014, "제습기 추천 장마",         "장마 대비 제습기"),
    (6,  1017, "수영복 물놀이 용품",       "여름 물놀이 시즌"),
    # 7월
    (7,  1016, "선풍기 추천 가성비",       "여름 냉방 성수기"),
    (7,  1012, "여름 간식 냉동식품",       "여름 식품 성수기"),
    # 8월
    (8,  1001, "가을 여성 패션 추천",      "가을 패션 사전 수요"),
    (8,  1017, "홈트 운동기구 추천",       "운동 의지 시즌"),
    # 9월
    (9,  1012, "추석 선물세트 추천",       "추석 선물 성수기"),
    (9,  1015, "가을 인테리어 소품",       "가을 인테리어 수요"),
    # 10월
    (10, 1001, "가을 여성 코트 추천",      "가을 패션 피크"),
    (10, 1017, "등산 등 아웃도어 가을",    "단풍 시즌 아웃도어"),
    # 11월
    (11, 1015, "겨울 전기장판 추천",       "겨울 난방용품 성수기"),
    (11, 1016, "공기청정기 추천 겨울",     "겨울 실내 공기질"),
    # 12월
    (12, 1020, "크리스마스 선물 장난감",   "크리스마스 선물 성수기"),
    (12, 1016, "노트북 추천 연말 선물",    "연말 선물 성수기"),
]

def get_season_hint() -> dict | None:
    """현재 월 기준 시즌 키워드 힌트 반환 (있을 경우)"""
    now = datetime.now(timezone(timedelta(hours=9)))
    month = now.month
    candidates = [s for s in SEASON_KEYWORDS if s[0] == month]
    if not candidates:
        return None
    # 당일 날짜 기반 결정론적 선택 (같은 날은 같은 시즌 힌트)
    idx = now.day % len(candidates)
    cat_id_season, kw_season, angle_season = candidates[idx][1], candidates[idx][2], candidates[idx][3]
    return {"cat_id": cat_id_season, "keyword": kw_season, "angle": angle_season}


def get_weekday_categories() -> list[int]:
    """오늘 요일에 맞는 우선 카테고리 리스트 반환"""
    weekday = datetime.now(timezone(timedelta(hours=9))).weekday()
    theme = WEEKDAY_THEME.get(weekday, [])
    # 나머지 카테고리도 fallback으로 포함
    all_cats = [cid for cid in CATEGORIES if cid not in SKIP_CATEGORIES]
    for cid in all_cats:
        if cid not in theme:
            theme.append(cid)
    return theme


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
    요일별 테마 카테고리 우선 선택 → 시즌 키워드 힌트 반영 → 베스트 상품 수집
    상품이 5개 미만이면 다음 우선순위 카테고리로 재시도
    """
    # 시즌 힌트 확인 (50% 확률로 시즌 키워드 우선 적용 — 과도한 고정 방지)
    season = get_season_hint()
    if season and random.random() < 0.5:
        cat_id = season["cat_id"]
        cat_name = CATEGORIES.get(cat_id, "기타")
        products = get_best_products(cat_id, limit=30)
        if len(products) >= 5:
            print(f"[시즌] 카테고리: {cat_name}({cat_id}) | 키워드: {season['keyword']} | 상품 {len(products)}개")
            return cat_id, cat_name, products

    # 요일별 테마 카테고리 순서대로 시도
    candidates = get_weekday_categories()
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    wd = datetime.now(timezone(timedelta(hours=9))).weekday()
    print(f"[요일테마] {weekday_names[wd]}요일 → 우선 카테고리: {[CATEGORIES.get(c,'?') for c in candidates[:3]]}")

    for cat_id in candidates[:7]:  # 최대 7개 카테고리 시도
        cat_name = CATEGORIES.get(cat_id, "기타")
        products = get_best_products(cat_id, limit=30)
        if len(products) >= 5:
            print(f"카테고리: {cat_name}({cat_id}) | 상품 {len(products)}개 수집")
            return cat_id, cat_name, products
        time.sleep(0.3)

    # fallback: 가전디지털 (항상 풍부)
    return 1016, "가전디지털", get_best_products(1016, limit=30)


def generate_topic_with_claude(cat_id: int, cat_name: str, products: list,
                               used_titles: list = None) -> dict:
    """
    Claude에게 베스트 상품 목록을 주고 블로그 포스트 최적 주제 선정 요청
    - 단순 카테고리명이 아닌 실제 상품명 기반으로 구체적 검색 키워드 도출
    - used_titles: 기존 포스트 제목 목록 (중복방지용)
    """
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y년 %m월 %d일")
    used_titles = used_titles or []

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

    # 시즌 힌트 추가 정보
    season = get_season_hint()
    season_hint = ""
    if season:
        season_hint = f"\n[시즌 힌트] 이번 달 주목할 키워드: '{season['keyword']}' ({season['angle']})\n위 상품과 연결 가능하면 시즌 키워드를 반영하세요.\n"

    # 최근 포스트 제목 컨텍스트 (중복 방지)
    recent_context = ""
    if used_titles:
        recent_list = "\n".join(f"- {t}" for t in used_titles[:20])
        recent_context = f"\n[⚠️ 중복 금지] 아래 제목들과 유사한 주제는 절대 선정하지 마세요:\n{recent_list}\n"

    prompt = f"""오늘은 {today}. 쿠팡 '{cat_name}' 카테고리 실시간 베스트 상품 목록입니다.
{season_hint}{recent_context}
{product_summary}

이 상품들을 분석해서 쿠팡 파트너스 블로그 '꿀통 몬스터' 포스트 주제를 선정하세요.

조건:
- 위 상품들 중 3개를 한 포스트에 묶을 수 있는 공통 주제 선정
- 소비자가 실제로 검색할 법한 구체적 키워드 (예: "탈모샴푸 추천" O, "뷰티" X)
- 단순 소모품/식재료보다 정보성 포스트 가능한 상품 우선 (예: 기기/용품/건강식품)
- 같은 카테고리라도 묶일 수 있는 상품이면 OK
- [중복 금지] 목록의 제목과 주제·키워드가 겹치면 반드시 다른 주제 선정

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

    def extract(text, tag):
        s = text.find(f"==={tag}===")
        if s == -1: return ""
        s += len(f"==={tag}===")
        e = text.find("===", s)
        return text[s:e if e != -1 else None].strip()

    def parse_result(text):
        topic = extract(text, "TOPIC")
        try:
            ids = [int(x.strip())-1 for x in extract(text, "PRODUCT_IDS").split(",") if x.strip().isdigit()]
            selected = [products[i] for i in ids if 0 <= i < len(products)]
        except Exception:
            selected = products[:3]
        if len(selected) < 3:
            selected = products[:3]
        return {
            "topic":             topic,
            "search_keyword":    extract(text, "SEARCH_KEYWORD") or cat_name,
            "angle":             extract(text, "ANGLE"),
            "labels":            [l.strip() for l in extract(text, "LABELS").split(",") if l.strip()],
            "meta_desc":         extract(text, "META"),
            "category":          cat_name,
            "cat_id":            cat_id,
            "selected_products": selected,
        }

    # 첫 시도
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    result = parse_result(msg.content[0].text)

    # 중복 감지 → 최대 2회 재시도
    for attempt in range(2):
        if not is_duplicate_topic(result["topic"], used_titles):
            break
        print(f"  [중복감지] '{result['topic'][:40]}' → 재시도 ({attempt+1}/2)")
        retry_prompt = (prompt +
            f"\n\n[필수] 방금 제안한 '{result['topic']}'는 기존 포스트와 너무 유사합니다. "
            f"완전히 다른 상품 조합과 주제로 다시 선정하세요.")
        msg2 = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": retry_prompt}]
        )
        result = parse_result(msg2.content[0].text)

    if is_duplicate_topic(result["topic"], used_titles):
        print(f"  [WARN] 재시도 후에도 유사 주제 — 그대로 진행")

    return result


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

    # Step 0: 기존 포스트 제목 수집 (중복방지)
    blog_id       = os.environ.get("TARGET_BLOG_ID", "4422596386410826373")
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
    client_id     = os.environ.get("BLOGGER_CLIENT_ID", "")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET", "")
    used_titles = load_recent_post_titles(blog_id, refresh_token, client_id, client_secret, max_posts=50)

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
        topic_data = generate_topic_with_claude(cat_id, cat_name, products, used_titles)
        topic_data["topic"] = manual_topic  # 주제만 덮어쓰기
    else:
        print(f"Claude 주제 선정 중...")
        topic_data = generate_topic_with_claude(cat_id, cat_name, products, used_titles)
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
