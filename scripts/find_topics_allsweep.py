#!/usr/bin/env python3
"""allsweep.xyz 주제 발굴 — 뉴스 카테고리 기반 + 검색의도(SEO) 최적화
aikeeper의 find_topics.py 방식 그대로 적용.
카테고리: 세계/사회/경제/IT/생활 뉴스 (한국 시사 중심)
"""
import os, sys, re, subprocess, datetime, hashlib, json, time, math

# .env 자동 로드 (cron/subprocess 환경에서도 동작)
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env_loader import load_env, make_anthropic_client, get_model
load_env()
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

# ── 고CPC 우선 주제 (실생활 정보 + 구매 연결형) ─────────────────────────────
# 기존: 뉴스/시사 → CPC 낮음
# 개선: 실생활 정보 + 구매 의도 키워드 포함 → CPC ₩1,000~8,000 수준
PREFERRED_TOPICS = [
    "재테크/투자 방법",        # CPC ₩1,000~5,000
    "보험/금융 상품 비교",     # CPC ₩2,000~8,000
    "생활비 절약 방법",        # 생활 정보 + 구매 연결
    "카드 추천/혜택 비교",     # CPC 높음
    "에너지 절약/전기세",      # 시사 연결 가능
    "실손보험 청구 방법",      # 보험 청구 고의도 검색 = 고CPC
    "연금저축 vs IRP",         # 세액공제/노후 = 고CPC 금융 키워드
    "신용카드 연회비 환급",    # 카드 혜택 고의도 = 고CPC
    "주택담보대출 갈아타기",   # 대출 비교 = 최고CPC 금융 키워드
]

# 피해야 할 주제 (CPC 낮음 + 독자 이탈 빠름)
AVOID_TOPICS = [
    "정치", "선거", "연예", "스포츠 경기 결과",
]

# SEO 자동완성 (뉴스 주제 기반)
import sys as _sys_seo, os as _os_seo
_sys_seo.path.insert(0, _os_seo.path.dirname(_os_seo.path.abspath(__file__)))
try:
    from seo_title_helper import get_seo_keywords as _get_seo_kws
    def _gac(kw, lang="ko"): return _get_seo_kws(kw).get("google", [])
    _SEO_NEWS_AVAIL = True
except ImportError:
    def _get_seo_kws(kw, pname=""): return {"combined": []}
    def _gac(kw, lang="ko"): return []
    _SEO_NEWS_AVAIL = False

# PREFERRED_TOPICS 키워드 → CPC 판별에 사용할 확장 키워드
PREFERRED_KEYWORDS = [
    "재테크", "투자", "적금", "예금", "주식", "펀드", "ETF", "ISA",
    "보험", "실손", "생명보험", "자동차보험", "보험 비교", "보험료",
    "절약", "생활비", "지출", "가계부", "알뜰", "할인", "혜택",
    "카드 추천", "신용카드", "체크카드", "카드 혜택", "카드 비교",
    "전기세", "가스비", "에너지", "절전", "공과금",
    "대출", "금리", "이자", "연금", "퇴직금", "청약",
    "부동산", "집값", "아파트", "월세", "전세", "임대",
    "세금", "소득공제", "세액공제", "연말정산",
    # 신규 추가 (2-3 보완)
    "실손보험 청구", "실손 청구", "보험 청구 방법",
    "연금저축", "IRP", "퇴직연금", "개인연금",
    "연회비 환급", "카드 연회비", "연회비 면제",
    "주담대 갈아타기", "주택담보대출", "대출 갈아타기", "대환대출",
]

# AVOID 판별 키워드
AVOID_KEYWORDS = [
    "선거", "대선", "총선", "후보", "여당", "야당", "정당",
    "연예인", "아이돌", "배우", "드라마 결말", "시청률",
    "경기 결과", "득점", "승리", "패배", "리그", "토너먼트",
]

def is_preferred_topic(topic_str: str) -> bool:
    """PREFERRED_TOPICS와 관련된 고CPC 주제이면 True"""
    t = topic_str.lower()
    return any(kw in t for kw in PREFERRED_KEYWORDS)

def is_avoid_topic(topic_str: str) -> bool:
    """AVOID_TOPICS에 해당하면 True (저CPC 주제 필터링)"""
    t = topic_str.lower()
    return any(kw in t for kw in AVOID_KEYWORDS)

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
    """검색 의도(Search Intent) 기반 중복 판단 — intent_dedup 공통 모듈 사용"""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from intent_dedup import is_duplicate as _dedup
    return _dedup(query, used, threshold)

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
        # AVOID_TOPICS 도메인은 건너뜀
        if is_avoid_topic(domain) or is_avoid_topic(query):
            continue
        if not is_duplicate(query, used_history):
            preferred = is_preferred_topic(domain) or is_preferred_topic(query)
            queries.append({"title": query, "source": f"domain:{cat}", "category": cat,
                            "domain": domain, "angle": angle, "preferred": preferred})
    # PREFERRED_TOPICS 관련 쿼리를 앞으로 정렬
    queries.sort(key=lambda x: (0 if x.get("preferred") else 1))

    # 고CPC 선호 주제가 부족하면 경제/생활 카테고리에서 강제 추가
    if sum(1 for q in queries if q.get("preferred")) < 3:
        bonus_queries = [
            {"title": f"[경제] {kw} — 개인 재테크에 미치는 영향", "source": "domain:경제(보강)",
             "category": "경제", "domain": kw, "angle": "개인 재테크에 미치는 영향", "preferred": True}
            for kw in ["연금 세금 재테크", "금리 인플레이션 물가"]
            if not is_duplicate(kw, used_history)
        ]
        bonus_queries += [
            {"title": f"[생활] {kw} — 바로 써먹는 실전 팁", "source": "domain:생활(보강)",
             "category": "생활", "domain": kw, "angle": "바로 써먹는 실전 팁", "preferred": True}
            for kw in ["절약 생활비 꿀팁"]
            if not is_duplicate(kw, used_history)
        ]
        queries = bonus_queries + queries
    return queries

# ── Claude 최적 주제 선정 ─────────────────────────────────────────────────────
def select_best_topic(news_items, used_history, target_category=None):
    today_str = datetime.date.today().strftime("%Y년 %m월 %d일")
    domain_queries = generate_domain_queries(used_history)

    seen, merged = set(), []
    for item in news_items + domain_queries:
        t = item.get("title", "")
        # AVOID_TOPICS 필터링
        if is_avoid_topic(t):
            continue
        if t and t not in seen and not has_ad(t) and not is_duplicate(t, used_history):
            preferred = item.get("preferred", False) or is_preferred_topic(t)
            seen.add(t)
            merged.append({**item, "preferred": preferred})

    # 선호 주제를 앞으로 정렬
    merged.sort(key=lambda x: (0 if x.get("preferred") else 1))

    if not merged:
        return {"topic": "생활비 절약 꿀팁 총정리", "keywords": ["생활비","절약","꿀팁","재테크"], "angle": "", "category": "생활"}

    # 뉴스 텍스트: 선호 주제에 ★ 표시
    news_text = "\n".join([
        f"[{'★선호CPC ' if item.get('preferred') else ''}{item['source']}] {item['title']}"
        for item in merged[:40]
    ])
    used_titles_text = "\n".join(f"- {t}" for t in sorted(used_history)) if used_history else "없음"

    # 오늘 카테고리 순환 (매 포스팅마다 다른 카테고리)
    cats = ["세계", "사회", "경제", "IT", "생활"]
    cat_seed = int(hashlib.md5((TODAY + str(len(used_history))).encode()).hexdigest(), 16)
    preferred_cat = target_category or cats[cat_seed % len(cats)]

    preferred_topics_text  = "\n".join(f"- {t}" for t in PREFERRED_TOPICS)
    avoid_topics_text      = "\n".join(f"- {t}" for t in AVOID_TOPICS)

    # SEO: 실시간 검색어 기반 뉴스 힌트
    news_seo_hint = ""
    if _SEO_NEWS_AVAIL:
        try:
            import time as _t
            _news_kws = []
            for _seed_kw in ["오늘 뉴스", "한국 이슈 오늘", preferred_cat]:
                _kws = _get_seo_kws(_seed_kw).get("combined", [])[:4]
                _news_kws.extend(_kws)
                _t.sleep(0.1)
            _uniq = list(dict.fromkeys(_news_kws))[:8]
            if _uniq:
                news_seo_hint = "【오늘 실시간 검색어 (네이버+구글 자동완성) — 제목에 반드시 1~2개 포함】\n" + "\n".join(f"  - {k}" for k in _uniq) + "\n→ 위 검색어를 제목에 자연스럽게 포함하면 검색 유입이 극대화됩니다. 포함하지 않으면 검색 노출이 불리합니다."
                print(f"[SEO] 뉴스 키워드: {_uniq[:3]}")
        except Exception as _e:
            print(f"[SEO] 뉴스 자동완성 실패: {_e}")

    prompt = f"""오늘은 {today_str}입니다.

당신은 구글/네이버 SEO 전문가이자 "모든정보 쓸어담기" 블로그 에디터입니다.
이 블로그는 **한국 시사/뉴스** 전문 블로그로, 세계·사회·경제·IT·생활 5개 카테고리를 운영합니다.

## 💰 최우선 원칙: 고CPC 주제 우선 선택

**선호 주제 (CPC ₩1,000~8,000 — 우선 선택):**
{preferred_topics_text}

**피해야 할 주제 (CPC 매우 낮음 — 절대 선택 금지):**
{avoid_topics_text}

★선호CPC 표시가 붙은 후보 항목을 반드시 우선 검토하세요.
뉴스 이슈와 연결되더라도 위 AVOID 카테고리는 선택하지 마세요.

---

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

## 키워드 전략 (필수 준수)
신규 도메인이므로 **경쟁이 낮은 롱테일 키워드** 위주로 선택하세요.

❌ 피해야 할 패턴 (경쟁 과열):
- "재테크 방법", "신용카드 추천", "전기세 절약" 등 단순 1~2단어 주제
- 메이저 언론사/대형 블로그가 이미 상위 점령한 시사 뉴스 요약

✅ 선택해야 할 패턴 (롱테일 저경쟁):
- **구체적 상황 + 대상**: "육아휴직 중 국민연금 임의가입 실제 납부액 계산법"
- **비교 + 조건**: "청년도약계좌 vs ISA, 월 70만원 넣을 때 5년 후 실수령 비교"
- **최신 + 수치**: "2026년 4월 기준 실손보험 비급여 한도 변경사항 정리"
- **오해 해소형**: "국민연금 임의가입하면 손해라는 말, 실제로 계산해봤습니다"
- **실전 절차형**: "직장인이 ISA 개설하고 첫 달 ETF 매수하는 단계별 방법"

## 좋은 주제 예시
- "2026 청년도약계좌 가입 조건 나이 소득 정확히 정리 (feat. 변경사항)" (경제, 롱테일)
- "실손보험 비급여 본인부담률 30% 적용 언제부터? 청구 방법 달라지나" (생활, 롱테일)
- "트럼프 관세 25% 한국 자동차 수출 실제 영향 — 현대차 주가와 연결해서 보기" (경제/세계)
- "국민연금 일시금 vs 연금 수령, 60세에 3억 있을 때 어떤 게 유리한가" (경제, 롱테일)
- "봄철 황사 공기청정기 필터 교체 시기 — 제조사별 교체 주기 실제 비교" (생활)

형식:
[SEO 제목 최적화]
{news_seo_hint}

===TOPIC===
SEO 최적화 주제/제목 (한국어, 구체적으로 — 위 검색어를 1개 이상 포함)
===CATEGORY===
세계/사회/경제/IT/생활 중 하나
===KEYWORDS===
실제 검색어 기반 키워드 4개 (한국어, 쉼표 구분)
===SEARCH_INTENT===
타겟 독자 / 검색 상황 / 예상 월 검색량
===ANGLE===
차별화된 글쓰기 각도
===END==="""

    client = make_anthropic_client(timeout=180, max_retries=2)
    text = ""
    with client.messages.stream(
        model=get_model(), max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk

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
        text = ""
        with client.messages.stream(model=ANTHROPIC_MODEL, max_tokens=600,
            messages=[{"role": "user", "content": retry_prompt}]) as _s:
            for _c in _s.text_stream:
                text += _c
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

    # ── 공통 used_topics.jsonl 로그 병합 (3개 블로그 간 중복 방지) ─────
    try:
        import sys as _sys
        _sys.path.insert(0, BASE)
        from scripts.used_topics_log import get_recent_topics as _get_recent
        _recent = _get_recent(days=7)
        print(f"  [공통로그] 최근 7일 발행 {len(_recent)}개 로드")
        for _entry in _recent:
            _t = _entry.get("topic", "").lower()
            if _t:
                used_history.add(_t)
    except Exception as _e:
        print(f"  [공통로그] 로드 스킵: {_e}")

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
