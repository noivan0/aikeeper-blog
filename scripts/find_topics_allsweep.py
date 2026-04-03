#!/usr/bin/env python3
"""allsweep.xyz 주제 발굴 — 뉴스 카테고리 기반 + 검색의도(SEO) 최적화
aikeeper의 find_topics.py 방식 그대로 적용.
카테고리: 세계/사회/경제/IT/생활 뉴스 (한국 시사 중심)
"""
import os, sys, re, subprocess, datetime, hashlib, json, time, math
import urllib.request, urllib.parse

import anthropic as _anthropic

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
BRAVE_API_KEY   = os.environ.get("BRAVE_API_KEY", "")

TODAY    = datetime.date.today().isoformat()
BLOG_ID  = os.environ.get("TARGET_BLOG_ID", "8772490249452917821")
BLOG_URL = os.environ.get("TARGET_BLOG_URL", "https://www.allsweep.xyz")

# ── 뉴스 도메인 (5개 카테고리) ──────────────────────────────────────────────
NEWS_DOMAINS = [
    # 세계 뉴스
    ("세계", "미국 정치 외교 트럼프"),
    ("세계", "중국 경제 무역 갈등"),
    ("세계", "유럽 정치 경제"),
    ("세계", "중동 분쟁 에너지"),
    ("세계", "러시아 우크라이나 전쟁"),
    ("세계", "일본 한일관계"),
    ("세계", "북한 핵 미사일"),
    ("세계", "글로벌 기후변화 환경"),
    ("세계", "국제 무역 관세"),
    ("세계", "AI 테크 글로벌 기업"),

    # 사회 뉴스
    ("사회", "한국 정치 여야"),
    ("사회", "한국 사건사고 범죄"),
    ("사회", "교육 입시 대학"),
    ("사회", "의료 건강 병원"),
    ("사회", "환경 재난 재해"),
    ("사회", "노동 고용 취업"),
    ("사회", "주거 부동산 임대차"),
    ("사회", "인구 저출산 고령화"),
    ("사회", "복지 사회보장"),
    ("사회", "젠더 다양성 인권"),

    # 경제 뉴스
    ("경제", "한국 증시 주식"),
    ("경제", "부동산 아파트 집값"),
    ("경제", "금리 인플레이션 물가"),
    ("경제", "환율 달러 원화"),
    ("경제", "반도체 삼성 SK하이닉스"),
    ("경제", "자동차 현대 전기차"),
    ("경제", "스타트업 벤처 투자"),
    ("경제", "소비 유통 이커머스"),
    ("경제", "에너지 원유 가스"),
    ("경제", "연금 세금 재테크"),

    # IT 뉴스
    ("IT", "AI 인공지능 챗GPT"),
    ("IT", "삼성 갤럭시 스마트폰"),
    ("IT", "카카오 네이버 플랫폼"),
    ("IT", "게임 콘텐츠 엔터"),
    ("IT", "사이버보안 해킹"),
    ("IT", "메타버스 VR AR"),
    ("IT", "클라우드 SaaS 데이터"),
    ("IT", "핀테크 가상화폐 블록체인"),
    ("IT", "자율주행 로봇 드론"),
    ("IT", "통신 5G 6G"),

    # 생활 뉴스
    ("생활", "날씨 기상 계절"),
    ("생활", "음식 요리 외식"),
    ("생활", "여행 관광 레저"),
    ("생활", "건강 다이어트 운동"),
    ("생활", "문화 영화 드라마"),
    ("생활", "육아 가족 라이프"),
    ("생활", "패션 뷰티 트렌드"),
    ("생활", "반려동물"),
    ("생활", "자동차 교통"),
    ("생활", "절약 생활비 꿀팁"),
]

# 카테고리별 검색의도 앵글
CATEGORY_ANGLES = {
    "세계": [
        "한국에 미치는 영향 분석",
        "쉽게 이해하는 배경 설명",
        "최신 동향 + 전망",
        "실생활 연결 포인트",
        "찬반 논쟁 정리",
    ],
    "사회": [
        "실생활 영향과 대처법",
        "원인과 해결책 분석",
        "숫자로 보는 현황",
        "사례로 이해하는 쉬운 설명",
        "알아두면 도움되는 정보",
    ],
    "경제": [
        "개인 재테크에 미치는 영향",
        "쉽게 이해하는 경제 개념",
        "투자자가 알아야 할 포인트",
        "최신 통계와 전망",
        "직장인·자영업자 실전 대응법",
    ],
    "IT": [
        "일반인이 알아야 할 핵심",
        "실생활 활용법",
        "쉽게 이해하는 기술 설명",
        "국내외 서비스 비교",
        "미래 전망과 기회",
    ],
    "생활": [
        "바로 써먹는 실전 팁",
        "초보자도 쉽게 따라하는",
        "비용 절감 방법",
        "전문가 조언 총정리",
        "계절·시기별 완전 가이드",
    ],
}

AD_FILTER = {"buy","sale","discount","구매","할인","무료체험","지금신청","click here"}

def get_words(text):
    return set(re.findall(r"[\w가-힣]{2,}", text.lower()))

def bigrams(text):
    words = re.findall(r"[\w가-힣]{2,}", text.lower())
    return {(words[i], words[i+1]) for i in range(len(words)-1)}

def similarity(a, b):
    wa, wb = get_words(a), get_words(b)
    ba, bb = bigrams(a), bigrams(b)
    ws = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    bs = len(ba & bb) / len(ba | bb) if ba and bb else 0.0
    return (ws + bs) / 2.0

def is_duplicate(query, used, threshold=0.30):
    q = query.lower()
    for u in used:
        if similarity(q, u) >= threshold:
            return True
        if len(get_words(q) & get_words(u)) >= 3:
            return True
    return False

def has_ad(text):
    tl = text.lower()
    return any(w in tl for w in AD_FILTER)

# ── 이력 로드 ─────────────────────────────────────────────────────────────────
def load_blogger_titles_today():
    titles = set()
    try:
        token_data = urllib.parse.urlencode({
            "client_id":     os.environ.get("BLOGGER_CLIENT_ID", ""),
            "client_secret": os.environ.get("BLOGGER_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("BLOGGER_REFRESH_TOKEN", ""),
            "grant_type":    "refresh_token",
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            access_token = json.loads(r.read()).get("access_token", "")
        if not access_token:
            return titles

        today = datetime.date.today().isoformat()
        start_t = urllib.parse.quote(f"{today}T00:00:00+09:00")
        end_t   = urllib.parse.quote(f"{today}T23:59:59+09:00")
        api_url = (
            f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts"
            f"?startDate={start_t}&endDate={end_t}"
            f"&fields=items(title)&maxResults=50&fetchBodies=false"
        )
        req2 = urllib.request.Request(api_url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req2, timeout=10) as r2:
            data = json.loads(r2.read())
        for item in data.get("items", []):
            t = item.get("title", "").strip()
            if t:
                titles.add(t.lower())
        print(f"  [중복방지] Blogger 당일 발행 {len(titles)}개 로드")
    except Exception as e:
        print(f"  [중복방지] Blogger API 조회 실패: {e}")
    return titles

def load_posted_history():
    used = load_blogger_titles_today()
    posts_dir = os.path.join(BASE, "posts-allsweep")
    if os.path.isdir(posts_dir):
        for fn in os.listdir(posts_dir):
            if not fn.endswith(".md"):
                continue
            try:
                for line in open(os.path.join(posts_dir, fn), encoding="utf-8"):
                    line = line.strip()
                    if line.startswith("title:"):
                        title = line[6:].strip().strip('"\'')
                        if title:
                            used.add(title.lower())
                        break
            except Exception:
                pass
    print(f"  [중복방지] 총 이력 {len(used)}개 로드")
    return used

# ── 뉴스 수집 ─────────────────────────────────────────────────────────────────
def scrapling_fetch(url):
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp = f.name
        subprocess.run(
            ["scrapling", "extract", "get", url, tmp, "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=30
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def parse_google_news(content, source):
    items = []
    pattern = re.compile(r'<a href="[^"]*" target="_blank">(.*?)</a>', re.DOTALL)
    for m in pattern.finditer(content):
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if len(title) >= 10:
            items.append({"title": title, "source": source})
        if len(items) >= 10:
            break
    return items

def fetch_all_news():
    all_news = []
    print("  📡 Google News (KO) 수집...")
    url = "https://news.google.com/rss/search?q=한국+사회+경제+정치+when:3d&hl=ko&gl=KR&ceid=KR:ko"
    items = parse_google_news(scrapling_fetch(url), "Google News KO")
    all_news.extend(items); print(f"     → {len(items)}개")

    print("  📡 Google News 세계...")
    url2 = "https://news.google.com/rss/search?q=세계+국제+뉴스+when:3d&hl=ko&gl=KR&ceid=KR:ko"
    items2 = parse_google_news(scrapling_fetch(url2), "Google News 세계")
    all_news.extend(items2); print(f"     → {len(items2)}개")

    print("  📡 Google News IT...")
    url3 = "https://news.google.com/rss/search?q=AI+IT+기술+when:3d&hl=ko&gl=KR&ceid=KR:ko"
    items3 = parse_google_news(scrapling_fetch(url3), "Google News IT")
    all_news.extend(items3); print(f"     → {len(items3)}개")

    return all_news

# ── 오늘의 도메인 로테이션 ────────────────────────────────────────────────────
def get_todays_domains():
    seed = int(hashlib.md5(TODAY.encode()).hexdigest(), 16) % len(NEWS_DOMAINS)
    rotated = NEWS_DOMAINS[seed:] + NEWS_DOMAINS[:seed]
    return rotated[:15]  # 하루 15개 도메인

def generate_domain_queries(used_history):
    todays = get_todays_domains()
    queries = []
    for cat, domain in todays:
        angles = CATEGORY_ANGLES.get(cat, ["최신 동향"])
        seed_val = int(hashlib.md5((TODAY + domain).encode()).hexdigest(), 16)
        angle = angles[seed_val % len(angles)]
        query = f"[{cat}] {domain} — {angle}"
        if not is_duplicate(query, used_history):
            queries.append({"title": query, "source": f"domain:{cat}", "category": cat, "domain": domain, "angle": angle})
    return queries

# ── Claude 최적 주제 선정 ─────────────────────────────────────────────────────
def select_best_topic(news_items, used_history, target_category=None):
    today_str = datetime.date.today().strftime("%Y년 %m월 %d일")
    domain_queries = generate_domain_queries(used_history)

    seen, merged = set(), []
    for item in news_items + domain_queries:
        t = item.get("title", "")
        if t and t not in seen and not has_ad(t) and not is_duplicate(t, used_history):
            seen.add(t); merged.append(item)

    if not merged:
        return {"topic": "오늘의 한국 뉴스 총정리", "keywords": ["뉴스","한국","오늘"], "angle": "", "category": "사회"}

    news_text = "\n".join([f"[{item['source']}] {item['title']}" for item in merged[:40]])
    used_titles_text = "\n".join(f"- {t}" for t in sorted(used_history)) if used_history else "없음"

    # 오늘 카테고리 순환 (매 포스팅마다 다른 카테고리)
    cats = ["세계", "사회", "경제", "IT", "생활"]
    cat_seed = int(hashlib.md5((TODAY + str(len(used_history))).encode()).hexdigest(), 16)
    preferred_cat = target_category or cats[cat_seed % len(cats)]

    prompt = f"""오늘은 {today_str}입니다.

당신은 구글/네이버 SEO 전문가이자 "모든정보 쓸어담기" 블로그 에디터입니다.
이 블로그는 **한국 시사/뉴스** 전문 블로그로, 세계·사회·경제·IT·생활 5개 카테고리를 운영합니다.

## 핵심 원칙: 검색 의도(Search Intent) 우선

뉴스 이슈를 단순 요약하는 게 아니라, **"누군가 이 사건/이슈를 이해하기 위해 구글/네이버에 검색할 쿼리"** 에 최적화된 포스트를 선정합니다.

### 주제 선정 기준
1. **뉴스 + 설명형**: "~란? / ~이유 / ~뜻 / ~배경" 형태 → 검색 수요 높음
2. **실생활 연결**: "~이 나에게 미치는 영향 / 대처법" → 클릭률 높음
3. **비교/정리형**: "A vs B / ~총정리 / ~완전정리" → 체류시간 높음
4. **현재 화제 + 배경 설명**: 뉴스에서 화제되는 키워드의 개념 설명 → 지속 유입

### 오늘 우선 카테고리: **{preferred_cat}**
(다른 카테고리도 가능하나, 이 카테고리를 우선 고려)

## 이미 발행된 포스트 (중복 금지)
{used_titles_text}

## 오늘의 뉴스/이슈 후보
{news_text}

## 좋은 주제 예시
- "트럼프 관세란? 한국 수출에 미치는 영향 총정리" (세계/경제)
- "한국 출산율 0.7 뜻과 이유 — 저출산 문제 쉽게 이해하기" (사회)
- "집값 하락 이유 5가지와 2026 부동산 전망" (경제)
- "챗GPT로 업무 자동화하는 실전 방법 3가지" (IT)
- "봄철 황사 대비법 — 마스크 선택부터 실내 공기 관리까지" (생활)

형식:
===TOPIC===
블로그 주제 (한국어, 구체적으로)
===CATEGORY===
세계/사회/경제/IT/생활 중 하나
===KEYWORDS===
실제 검색어 기반 키워드 4개 (한국어, 쉼표 구분)
===SEARCH_INTENT===
타겟 독자 / 검색 상황 / 예상 월 검색량
===ANGLE===
차별화된 글쓰기 각도
===END==="""

    _ck = dict(base_url=ANTHROPIC_BASE_URL, timeout=120, max_retries=2)
    if ANTHROPIC_API_KEY:
        _ck["api_key"] = ANTHROPIC_API_KEY
    client = _anthropic.Anthropic(**_ck)
    resp = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text

    def extract(t, key):
        tags = ["===TOPIC===","===CATEGORY===","===KEYWORDS===","===SEARCH_INTENT===","===ANGLE===","===END==="]
        tag = f"==={key}==="
        s = t.find(tag)
        if s == -1: return ""
        s += len(tag)
        e = len(t)
        for other in tags:
            if other == tag: continue
            pos = t.find(other, s)
            if 0 < pos < e: e = pos
        return t[s:e].strip()

    result = {
        "topic":    extract(text, "TOPIC"),
        "category": extract(text, "CATEGORY") or preferred_cat,
        "keywords": [k.strip() for k in extract(text, "KEYWORDS").split(",") if k.strip()],
        "angle":    extract(text, "ANGLE"),
    }

    # 중복 재시도
    for retry in range(2):
        if not result["topic"] or not is_duplicate(result["topic"], used_history, 0.28):
            break
        print(f"  ⚠️  중복 감지 (retry {retry+1}): {result['topic'][:50]}")
        retry_prompt = prompt + f"\n\n[추가 제약] '{result['topic']}'는 중복입니다. 완전히 다른 주제를 선정하세요."
        resp2 = client.messages.create(model=ANTHROPIC_MODEL, max_tokens=600,
            messages=[{"role": "user", "content": retry_prompt}])
        text = resp2.content[0].text
        result = {
            "topic":    extract(text, "TOPIC"),
            "category": extract(text, "CATEGORY") or preferred_cat,
            "keywords": [k.strip() for k in extract(text, "KEYWORDS").split(",") if k.strip()],
            "angle":    extract(text, "ANGLE"),
        }

    return result


if __name__ == "__main__":
    manual_topic    = sys.argv[1] if len(sys.argv) > 1 else ""
    manual_keywords = sys.argv[2] if len(sys.argv) > 2 else ""
    target_cat      = sys.argv[3] if len(sys.argv) > 3 else ""

    GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "/tmp/gh_output.txt")

    def write_output(key, value):
        safe = str(value).replace('\r','').replace('\n',' ')
        with open(GITHUB_OUTPUT, "a", encoding="utf-8") as f:
            f.write(f"{key}={safe}\n")

    print(f"🔍 allsweep 주제 발굴 — {TODAY}")

    if manual_topic.strip():
        write_output("topic", manual_topic.strip())
        write_output("keywords", manual_keywords.strip())
        write_output("angle", "")
        write_output("category", target_cat or "사회")
        print(f"수동 주제: {manual_topic[:60]}")
        sys.exit(0)

    used_history = load_posted_history()

    print("\n📡 뉴스 수집 중...")
    news = fetch_all_news()
    print(f"\n✅ 총 {len(news)}개 수집 완료")

    print("\n🤖 최적 주제 선정 중 (Claude)...")
    result = select_best_topic(news, used_history, target_cat)

    print(f"\n📌 선정 주제: {result['topic']}")
    print(f"   카테고리: {result['category']}")
    print(f"   키워드: {', '.join(result['keywords'])}")

    print(f"\ntopic:{result['topic']}")
    print(f"keywords:{','.join(result['keywords'])}")
    print(f"angle:{result['angle']}")
    print(f"category:{result['category']}")

    write_output("topic", result["topic"])
    write_output("keywords", ",".join(result["keywords"]))
    write_output("angle", result["angle"])
    write_output("category", result["category"])
