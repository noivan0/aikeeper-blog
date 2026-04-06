#!/usr/bin/env python3
"""
이미지 자동 수집 — 다중 소스, 신뢰도 기반
수집 전략 (우선순위 순):
  1. 관련 뉴스/블로그에서 scrapling으로 og:image 추출
     - TechCrunch, VentureBeat, Ars Technica, TheVerge, 한국IT뉴스
     - Reddit r/artificial, r/MachineLearning 스레드
  2. Wikimedia Commons — 무료 CC 라이선스
  3. Unsplash (API 키 있으면 API, 없으면 Source API)
  4. FALLBACK_IMAGES — Unsplash 고정 URL (폴백)

Reddit 이미지: CDN preview(만료됨) 대신 direct URL / thumbnail 우선 사용
모든 이미지: HTTP HEAD 검증 후 접근 불가 URL 자동 제외

출처 표시 원칙:
  - 모든 이미지에 출처(사이트명 + URL) 표기
  - 저작권 이슈 있는 이미지는 자동 제외
  - 신뢰 도메인 화이트리스트 적용
"""
import os
import sys
import re
import json
import subprocess
import tempfile
import urllib.request
import urllib.parse
import hashlib
import datetime
from pathlib import Path

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()

FALLBACK_IMAGES = [
    {"url": "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=1200&h=630&fit=crop&auto=format", "alt": "인공지능 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1676299081847-824916de030a?w=1200&h=630&fit=crop&auto=format", "alt": "AI 머신러닝", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1655720828018-edd2daec9349?w=1200&h=630&fit=crop&auto=format", "alt": "AI 데이터 분석", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=1200&h=630&fit=crop&auto=format", "alt": "AI 로봇 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&h=630&fit=crop&auto=format", "alt": "데이터 코드 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1509228627152-72ae9ae6848d?w=1200&h=630&fit=crop&auto=format", "alt": "네트워크 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200&h=630&fit=crop&auto=format", "alt": "미래 기술 혁신", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=1200&h=630&fit=crop&auto=format", "alt": "컴퓨터 기술 개발", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200&h=630&fit=crop&auto=format", "alt": "반도체 칩 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
    {"url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&h=630&fit=crop&auto=format", "alt": "디지털 지구 기술", "credit": "Unsplash", "credit_url": "https://unsplash.com", "source": "fallback", "source_label": "🖼️ AI 이미지"},
]

# ── 신뢰 뉴스 소스 화이트리스트 ─────────────────────────────────
TRUSTED_SOURCES = [
    # 글로벌 테크 뉴스
    {"domain": "techcrunch.com",    "name": "TechCrunch",    "query_suffix": ""},
    {"domain": "venturebeat.com",   "name": "VentureBeat",   "query_suffix": ""},
    {"domain": "theverge.com",      "name": "The Verge",     "query_suffix": ""},
    {"domain": "arstechnica.com",   "name": "Ars Technica",  "query_suffix": ""},
    {"domain": "wired.com",         "name": "Wired",         "query_suffix": ""},
    {"domain": "thenextweb.com",    "name": "TNW",           "query_suffix": ""},
    {"domain": "zdnet.com",         "name": "ZDNet",         "query_suffix": ""},
    # AI 전문
    {"domain": "towardsdatascience.com", "name": "Towards Data Science", "query_suffix": ""},
    {"domain": "arxiv.org",         "name": "arXiv",         "query_suffix": ""},
    {"domain": "openai.com",        "name": "OpenAI",        "query_suffix": ""},
    {"domain": "anthropic.com",     "name": "Anthropic",     "query_suffix": ""},
    # 한국 IT 뉴스
    {"domain": "zdnet.co.kr",       "name": "ZDNet Korea",   "query_suffix": ""},
    {"domain": "bloter.net",        "name": "Bloter",        "query_suffix": ""},
    {"domain": "itworld.co.kr",     "name": "ITWorld",       "query_suffix": ""},
]

# 제외할 이미지 패턴 (로고, 광고, 아이콘 등)
EXCLUDE_PATTERNS = [
    r'logo', r'icon', r'avatar', r'favicon', r'sprite',
    r'banner', r'ad\.', r'ads\.', r'tracking', r'pixel',
    r'\.gif$', r'1x1', r'spacer', r'blank',
]


# ── 파싱 헬퍼 ────────────────────────────────────────────────────

def parse_front_matter(content: str):
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()
    return meta, body


# ── scrapling 헬퍼 ───────────────────────────────────────────────

def scrapling_fetch(url: str, timeout: int = 25) -> str:
    """scrapling으로 URL 가져오기 — .html 확장자로 저장해 raw HTML 구조 보존"""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = f.name
    try:
        result = subprocess.run(
            ["scrapling", "extract", "get", url, tmp,
             "--impersonate", "chrome", "--no-verify", "--timeout", str(timeout)],
            capture_output=True, text=True, timeout=timeout + 5
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def is_valid_image_url(url: str) -> bool:
    """이미지 URL 유효성 검사"""
    if not url or len(url) < 20:
        return False
    url_lower = url.lower()
    # 확장자 체크
    if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$|#)', url_lower):
        if 'image' not in url_lower and 'photo' not in url_lower and 'img' not in url_lower:
            return False
    # 제외 패턴
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, url_lower):
            return False
    # 최소 크기 추정 (URL 길이로)
    if len(url) < 30:
        return False
    return True


def verify_image_accessible(url: str, timeout: int = 6) -> bool:
    """실제 HTTP HEAD 요청으로 이미지 접근 가능 여부 확인"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="HEAD"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            return "image" in ct or resp.status == 200
    except Exception:
        return False


def extract_og_image(html: str) -> str:
    """HTML에서 og:image 추출"""
    # og:image 우선
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
    if m:
        return m.group(1)
    # twitter:image
    m = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1)
    return ""


def get_domain_name(url: str) -> str:
    """URL에서 사이트명 추출"""
    m = re.match(r'https?://(?:www\.)?([^/]+)', url)
    if not m:
        return "출처"
    domain = m.group(1)
    for src in TRUSTED_SOURCES:
        if src["domain"] in domain:
            return src["name"]
    return domain.split('.')[0].title()


def is_relevant_image(img_url: str, img_alt: str, query: str) -> bool:
    """이미지가 주제와 관련 있는지 기본 체크.
    
    너무 엄격하면 이미지 자체가 없어지므로, 명백히 무관한 패턴만 걸러냄.
    Google/Bing/Wikimedia/Unsplash 이미지는 이미 주제 기반이므로 항상 통과.
    뉴스/Reddit 소스에서 온 이미지에만 엄격하게 적용.
    """
    url_lower = img_url.lower()
    alt_lower = (img_alt or "").lower()

    # 명백히 무관한 패턴 제외 (자동차, 렌트, 음식 등 주제 무관 카테고리)
    irrelevant_patterns = [
        'jump-starter', 'land-cruiser', 'land_cruiser',
        'mildlyinfuriating', 'r/rent', 'r/food', 'r/recipe',
        '/cars/', '/auto/', '/vehicle/', '/jumpstarter/',
        'car-review', 'auto-loan', 'vehicle-insurance',
    ]
    for pat in irrelevant_patterns:
        if pat in url_lower:
            return False

    return True  # 기본적으로 통과 (이미지 없는 것보다 관련성 낮아도 있는 게 나음)


# ── 1순위: Unsplash Source API (API 키 불필요) ───────────────────

def search_unsplash_direct(query: str) -> list:
    """Unsplash Source API — API 키 불필요, 쿼리 기반 안정적 이미지"""
    results = []
    # 영문 키워드 추출 (한글 쿼리 대비)
    en_query = re.sub(r'[^\w\s]', ' ', query)
    en_words = [w for w in en_query.split() if w.isascii() and len(w) > 2]
    search_term = '+'.join(en_words[:4]) if en_words else 'artificial+intelligence'

    # Unsplash Source: 쿼리 기반 고품질 이미지 (1200x630)
    url = f"https://source.unsplash.com/1200x630/?{search_term}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.url  # redirect 후 실제 이미지 URL
            if final_url and 'images.unsplash.com' in final_url:
                # 서명 파라미터 제거하고 고정 파라미터로 대체
                base = final_url.split('?')[0]
                clean_url = base + '?w=1200&h=630&fit=crop&auto=format'
                results.append({
                    "url": clean_url,
                    "alt": f"{query} 관련 이미지",
                    "credit": "Unsplash",
                    "credit_url": "https://unsplash.com",
                    "source": "unsplash",
                    "source_label": "📸 Unsplash"
                })
                print(f"  ✅ Unsplash 이미지: {clean_url[:70]}...")
    except Exception as e:
        print(f"  ⚠️  Unsplash direct 실패: {e}")

    return results


# ── 2순위: Wikimedia Commons ─────────────────────────────────────

def search_wikimedia(query: str) -> list:
    """Wikimedia Commons — 무료 CC 라이선스"""
    try:
        encoded = urllib.parse.quote(query)
        url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&generator=search&gsrnamespace=6"
            f"&gsrsearch={encoded}&gsrlimit=5&prop=imageinfo"
            f"&iiprop=url|extmetadata&iiurlwidth=800&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AIkeeper-Blog/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        images = []
        for page in (data.get("query", {}).get("pages", {}).values()):
            ii = page.get("imageinfo", [{}])[0]
            img_url = ii.get("thumburl") or ii.get("url", "")
            if not img_url or not img_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            ext = ii.get("extmetadata", {})
            author = re.sub(r"<[^>]+>", "", ext.get("Artist", {}).get("value", "Wikimedia Commons")).strip()[:40]
            license_name = ext.get("LicenseShortName", {}).get("value", "CC")
            images.append({
                "url": img_url,
                "alt": query,
                "credit": f"{author} / Wikimedia Commons ({license_name})",
                "credit_url": "https://commons.wikimedia.org",
                "source": "wikimedia",
                "source_label": "🖼️ Wikimedia Commons"
            })
            if len(images) >= 2:
                break
        return images
    except Exception as e:
        print(f"  ⚠️ Wikimedia 오류: {e}")
        return []


# ── 뉴스 소스 RSS 피드 목록 ─────────────────────────────────────
NEWS_RSS_FEEDS = [
    # 글로벌 AI/테크 뉴스 — RSS 직접 구독 (Google News 중간단계 제거)
    {"name": "VentureBeat AI",  "url": "https://venturebeat.com/category/ai/feed/",                       "domain": "venturebeat.com"},
    {"name": "The Verge AI",    "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml","domain": "theverge.com"},
    {"name": "Ars Technica",    "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",         "domain": "arstechnica.com"},
    {"name": "TechCrunch AI",   "url": "https://techcrunch.com/category/artificial-intelligence/feed/",   "domain": "techcrunch.com"},
    {"name": "Wired AI",        "url": "https://www.wired.com/feed/tag/ai/latest/rss",                     "domain": "wired.com"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/",                           "domain": "technologyreview.com"},
]

def _fetch_rss_curl(url: str, timeout: int = 12) -> str:
    """RSS XML을 curl로 직접 수집 — scrapling은 RSS 구조를 깨뜨림"""
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout),
             "-H", "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
             "-H", "Accept: application/rss+xml, application/xml, text/xml, */*",
             url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        return result.stdout
    except Exception:
        return ""

def _extract_rss_items(xml: str) -> list:
    """RSS XML에서 (title, link, image_url) 튜플 목록 추출"""
    import html as html_module
    items = []
    raw_items = re.findall(r'<(?:item|entry)>(.*?)</(?:item|entry)>', xml, re.S)
    for raw in raw_items:
        # 제목
        t = re.search(r'<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', raw, re.S)
        title = re.sub(r'<[^>]+>', '', t.group(1)).strip() if t else ""

        # 링크
        l = re.search(r'<link[^>]*>(?:<!\[CDATA\[)?(https?://[^\s<]+)(?:\]\]>)?</link>', raw, re.S)
        if not l:
            l = re.search(r'<link[^>]+href=["\']?(https?://[^\s"\'<>]+)', raw)
        link = l.group(1).strip() if l else ""

        # 이미지 — media:content, enclosure, img src, 본문 내 URL 순서로 탐색
        img = None
        # media:content
        m = re.search(r'<media:content[^>]+url=["\']?(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*)', raw, re.I)
        if m:
            img = m.group(1)
        # enclosure
        if not img:
            m = re.search(r'<enclosure[^>]+url=["\']?(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*)', raw, re.I)
            if m:
                img = m.group(1)
        # img src
        if not img:
            m = re.search(r'<img[^>]+src=["\']?(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*)', raw, re.I)
            if m:
                img = m.group(1)
        # 본문 내 plain URL
        if not img:
            candidates = re.findall(r'(https?://[^\s"<>]+\.(?:jpg|jpeg|png|webp))(?:[?&][^\s"<>]*)?', raw, re.I)
            for c in candidates:
                if not any(x in c.lower() for x in ['logo','icon','avatar','favicon','1x1','sprite','banner']):
                    img = c
                    break

        # HTML 엔티티 디코딩 (&amp; → &, etc.)
        if img:
            img = html_module.unescape(img)
        if link:
            link = html_module.unescape(link)

        if link:
            items.append((title.lower(), link, img))
    return items

# ── 3순위: 뉴스/블로그 소스 RSS 직접 구독 ─────────────────────────

def search_from_news_sources(query: str, labels: list = None) -> list:
    """신뢰 뉴스 RSS 직접 구독 → 쿼리 키워드 매칭 → 이미지 추출
    
    이전 방식(Google News RSS → 리다이렉트 URL → 기사 scrapling)을 폐기.
    각 소스 RSS를 직접 가져와 제목에서 키워드 매칭 후 이미지를 즉시 추출.
    실패 시 og:image 개별 기사 scrapling으로 보완.
    """
    results = []

    # 쿼리 키워드 분리
    query_words = set(re.sub(r'[^\w\s]', ' ', query.lower()).split())
    label_words = set(re.sub(r'[^\w\s]', ' ', ' '.join(labels or [])).lower().split()) if labels else set()
    keywords = query_words | label_words
    # 불용어 제거
    stopwords = {'the','a','an','of','in','to','for','and','or','is','are','with','on','at','by'}
    keywords -= stopwords
    keywords = {w for w in keywords if len(w) > 2}

    for feed in NEWS_RSS_FEEDS:
        if len(results) >= 2:
            break
        try:
            xml = _fetch_rss_curl(feed["url"], timeout=12)
            if not xml or len(xml) < 200:
                print(f"  ⚠️ {feed['name']}: RSS 응답 없음")
                continue

            items = _extract_rss_items(xml)
            print(f"  📰 {feed['name']}: {len(items)}개 항목 스캔")

            for title, link, img_url in items:
                # 키워드 매칭
                matched = sum(1 for kw in keywords if kw in title)
                if matched == 0:
                    continue

                # RSS에서 바로 이미지 URL 확보
                if img_url and is_valid_image_url(img_url) and is_relevant_image(img_url, "", query):
                    results.append({
                        "url": img_url,
                        "alt": query,
                        "credit": feed["name"],
                        "credit_url": link,
                        "source": "news",
                        "source_label": f"📰 {feed['name']}",
                    })
                    print(f"  ✅ {feed['name']} RSS 이미지 (match={matched}): {img_url[:60]}...")
                    break
                elif img_url and not is_relevant_image(img_url, "", query):
                    print(f"  ⚠️ {feed['name']} 이미지 관련성 미달, 스킵: {img_url[:60]}...")

                # RSS 이미지 없으면 기사 페이지 scrapling → og:image
                if link:
                    try:
                        page_html = scrapling_fetch(link, timeout=15)
                        og = extract_og_image(page_html) if page_html else None
                        if og and is_valid_image_url(og) and is_relevant_image(og, "", query):
                            results.append({
                                "url": og,
                                "alt": query,
                                "credit": feed["name"],
                                "credit_url": link,
                                "source": "news",
                                "source_label": f"📰 {feed['name']}",
                            })
                            print(f"  ✅ {feed['name']} og:image (match={matched}): {og[:60]}...")
                            break
                    except Exception:
                        pass

        except Exception as e:
            print(f"  ⚠️ {feed['name']} 오류: {e}")
            continue

    return results


def search_from_reddit(query: str) -> list:
    """Reddit JSON API — 외부 링크 이미지 우선 (CDN preview 만료 문제 회피)"""
    results = []
    subreddits = ["artificial", "MachineLearning", "technology", "singularity"]

    for sub in subreddits[:2]:
        try:
            url = (
                f"https://www.reddit.com/r/{sub}/search.json"
                f"?q={urllib.parse.quote(query)}&limit=10&sort=relevance&t=month"
            )
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 AIkeeper-Blog/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            for post in data.get("data", {}).get("children", []):
                pd = post.get("data", {})

                # 1순위: post_hint=="image" 인 경우 — url이 직접 이미지 링크
                hint = pd.get("post_hint", "")
                ext_url = pd.get("url_overridden_by_dest", pd.get("url", ""))
                permalink = pd.get("permalink", "")
                if hint == "image" and ext_url and is_valid_image_url(ext_url) and is_relevant_image(ext_url, "", query):
                    post_url = f"https://reddit.com{permalink}"
                    results.append({
                        "url": ext_url,
                        "alt": query[:80],
                        "credit": f"Reddit r/{sub}",
                        "credit_url": post_url,
                        "source": "reddit",
                        "source_label": f"💬 Reddit r/{sub}",
                    })
                    print(f"  ✅ Reddit 이미지(direct): r/{sub}")
                    break

                # 2순위: thumbnail이 실제 이미지 URL인 경우 (HTML 엔티티 디코딩)
                import html as _html
                thumb = _html.unescape(pd.get("thumbnail", ""))
                if thumb and thumb.startswith("http") and is_valid_image_url(thumb) and is_relevant_image(thumb, "", query):
                    post_url = f"https://reddit.com{permalink}"
                    results.append({
                        "url": thumb,
                        "alt": query[:80],
                        "credit": f"Reddit r/{sub}",
                        "credit_url": post_url,
                        "source": "reddit",
                        "source_label": f"💬 Reddit r/{sub}",
                    })
                    print(f"  ✅ Reddit 이미지(thumb): r/{sub}")
                    break

        except Exception:
            continue
        if results:
            break

    return results


def search_from_x_twitter(query: str) -> list:
    """X(Twitter)/fxtwitter에서 트윗 이미지 수집"""
    results = []
    try:
        # fxtwitter 검색 우회 — nitter 또는 Twitter API 없이 검색
        search_url = f"https://api.fxtwitter.com/search?q={urllib.parse.quote(query + ' AI filter:images')}&count=5"
        html = scrapling_fetch(search_url, timeout=15)
        if html:
            imgs = re.findall(r'https://pbs\.twimg\.com/media/[^\s"\'<>]+\.(?:jpg|png|webp)[^\s"\'<>]*', html)
            for img_url in imgs[:2]:
                img_url = img_url.split('?')[0] + '?format=jpg&name=large'
                results.append({
                    "url": img_url,
                    "alt": query,
                    "credit": "X (Twitter)",
                    "credit_url": f"https://x.com/search?q={urllib.parse.quote(query)}",
                    "source": "twitter",
                    "source_label": "🐦 X (Twitter)"
                })
                print(f"  ✅ Twitter 이미지: {img_url[:55]}...")
                break
    except Exception:
        pass
    return results


# ── Unsplash API (키 있을 때) ─────────────────────────────────────

def search_unsplash(query: str) -> list:
    if not UNSPLASH_ACCESS_KEY:
        return []
    try:
        url = (
            f"https://api.unsplash.com/search/photos"
            f"?query={urllib.parse.quote(query)}&per_page=3&orientation=landscape"
        )
        req = urllib.request.Request(
            url, headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [
            {
                "url": p["urls"]["regular"],
                "alt": p.get("alt_description") or query,
                "credit": f"{p['user']['name']} / Unsplash",
                "credit_url": p["user"]["links"]["html"],
                "source": "unsplash",
                "source_label": "📸 Unsplash"
            }
            for p in data.get("results", [])
        ]
    except Exception:
        return []


# ── 이모지 배너 폴백 ─────────────────────────────────────────────

TOPIC_EMOJI_MAP = {
    "ai": "🤖", "claude": "🤖", "gpt": "🤖", "llm": "🧠", "chatgpt": "🤖",
    "robot": "🦾", "chip": "💻", "data": "📊", "security": "🔒", "보안": "🔒",
    "money": "💰", "startup": "🚀", "google": "🔍", "apple": "🍎",
    "medical": "🏥", "health": "💊", "education": "📚", "future": "🔮",
    "seo": "🔍", "search": "🔍", "algorithm": "⚙️", "autonomous": "🚗",
    "space": "🚀", "energy": "⚡", "climate": "🌱", "meta": "🥽",
}

def make_emoji_banner(query: str, title: str) -> str:
    q_lower = (query + " " + title).lower()
    emoji = "🤖"
    for kw, em in TOPIC_EMOJI_MAP.items():
        if kw in q_lower:
            emoji = em
            break
    short = title[:45] + "..." if len(title) > 45 else title
    return (
        f'<div style="background:linear-gradient(135deg,#1a237e 0%,#283593 50%,#1565c0 100%);'
        f'border-radius:16px;padding:48px 32px;text-align:center;margin:0 0 2em;'
        f'min-height:200px;display:flex;flex-direction:column;justify-content:center;'
        f'align-items:center;color:#fff;">'
        f'<div style="font-size:4rem;margin-bottom:16px">{emoji}</div>'
        f'<div style="font-size:1.1rem;opacity:.85;font-weight:500;max-width:480px">{short}</div>'
        f'</div>'
    )


# ── HTML 빌더 ─────────────────────────────────────────────────────

def build_image_html(img: dict, is_hero: bool = True) -> str:
    """이미지 딕셔너리 → SEO 최적화 HTML figure
    
    캡션: source_label + 출처 도메인명만 표시 (기사 제목/영어 텍스트 노출 제거)
    """
    url = img["url"]
    alt = img.get("alt", "")[:100]
    credit_url = img.get("credit_url", "")
    source_label = img.get("source_label", "📷 출처")

    # 도메인명만 추출 (기사 제목 대신 사이트명으로 간결하게)
    domain_name = get_domain_name(credit_url) if credit_url else img.get("credit", "출처")

    credit_html = (
        f'<a href="{credit_url}" rel="nofollow noopener"'
        f' style="color:#4f6ef7;text-decoration:none;">{domain_name}</a>'
        if credit_url else domain_name
    )

    # LCP 최적화: 히어로 이미지는 eager+high priority, 나머지는 lazy
    loading = 'eager" fetchpriority="high' if is_hero else 'lazy'

    return (
        f'<figure style="margin:0 0 2em;text-align:center;">'
        f'<img src="{url}" alt="{alt}" '
        f'width="800" height="450" '
        f'style="width:100%;max-width:760px;height:auto;aspect-ratio:16/9;'
        f'border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.12);object-fit:cover;" '
        f'loading="{loading}" decoding="async"/>'
        f'<figcaption style="font-size:.82em;color:#888;margin-top:.6em;line-height:1.5;">'
        f'{source_label}: {credit_html}'
        f'</figcaption></figure>\n\n'
    )


# ── 메인 오케스트레이터 ──────────────────────────────────────────

def search_google_images(query: str, num: int = 5) -> list:
    """Google 이미지 검색 크롤링 — 주제 기반 실제 이미지"""
    import urllib.parse, urllib.request, re, json

    results = []
    try:
        # Google 이미지 검색 URL
        encoded = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded}&tbm=isch&hl=ko&num=10"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Referer": "https://www.google.com/",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Google 이미지 URL 추출 (JSON 데이터에서)
        patterns = [
            r'"(https://[^"]+\.(?:jpg|jpeg|png|webp)(?:\?[^"]*)?)"',
            r'imgurl=([^&"]+\.(?:jpg|jpeg|png))',
        ]
        found_urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for m in matches:
                url_clean = urllib.parse.unquote(m)
                if (url_clean.startswith("http")
                        and "google" not in url_clean
                        and "gstatic" not in url_clean
                        and len(url_clean) < 300
                        and not any(x in url_clean for x in ["icon", "logo", "favicon", "1x1", "pixel"])):
                    found_urls.add(url_clean)
                    if len(found_urls) >= num:
                        break
            if len(found_urls) >= num:
                break

        for img_url in list(found_urls)[:num]:
            results.append({
                "url": img_url,
                "alt": query,
                "credit": "Google Images",
                "credit_url": f"https://www.google.com/search?q={encoded}&tbm=isch",
                "source": "google",
                "source_label": "🔍 Google Images"
            })

        if results:
            print(f"  ✅ Google 이미지: {len(results)}개")
        else:
            print(f"  ⚠️  Google 이미지 추출 실패 (패턴 미매칭)")
    except Exception as e:
        print(f"  ⚠️  Google 이미지 검색 실패: {e}")

    return results


def search_bing_images(query: str, num: int = 5) -> list:
    """Bing 이미지 검색 크롤링 — Google 실패 시 대안"""
    import urllib.parse, urllib.request, re

    results = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.bing.com/images/search?q={encoded}&count=10&mkt=ko-KR"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Bing 이미지 URL 패턴: murl 파라미터
        matches = re.findall(r'"murl":"(https://[^"]+)"', html)
        found = []
        for m in matches:
            if (m.startswith("http") and len(m) < 500
                    and any(m.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"])
                    and "bing.com" not in m):
                found.append(m)
            if len(found) >= num:
                break

        for img_url in found[:num]:
            results.append({
                "url": img_url,
                "alt": query,
                "credit": "Bing Images",
                "credit_url": f"https://www.bing.com/images/search?q={encoded}",
                "source": "bing",
                "source_label": "🔍 Bing Images"
            })

        if results:
            print(f"  ✅ Bing 이미지: {len(results)}개")
    except Exception as e:
        print(f"  ⚠️  Bing 이미지 검색 실패: {e}")

    return results


def _make_pollinations_image(query: str, idx: int = 0) -> dict:
    """Pollinations AI — 무료 주제 맞춤 이미지 생성 (API 키 불필요)"""
    import hashlib as _hl
    prompts = [
        f"{query}, professional blog illustration, clean modern infographic, 16:9 widescreen",
        f"{query}, Korean blog hero image, bright clean design, technology concept 2026",
        f"{query} overview, minimalist diagram, educational, high quality",
    ]
    prompt = prompts[idx % len(prompts)]
    seed_val = int(_hl.md5(f"{query}{idx}".encode()).hexdigest(), 16) % 99999
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&seed={seed_val}&nologo=true"
    return {
        "url": url,
        "alt": f"{query} 설명 이미지",
        "credit": "Pollinations AI",
        "credit_url": "https://pollinations.ai",
        "source": "ai_generated",
        "source_label": "🤖 AI 생성 이미지",
    }


def make_hero_image(title: str, query: str) -> dict:
    """대표(hero) 이미지 생성 — 배경+텍스트 형태로 미리보기 최적화

    Pollinations AI에 제목 텍스트를 포함한 썸네일용 이미지를 생성.
    블로그 카드/SNS 미리보기에서 제목이 배경에 표시되는 형태.
    """
    import hashlib as _hl
    # 제목에서 핵심어 추출 (앞 30자)
    short_title = re.sub(r'[^\w\s가-힣]', ' ', title).strip()[:40]

    prompt = (
        f"Blog thumbnail image, dark gradient background, "
        f"large bold Korean text overlay '{short_title}', "
        f"clean modern design, 16:9 aspect ratio, "
        f"professional tech blog style, 2026, "
        f"subject: {query}"
    )
    seed_val = int(_hl.md5(f"hero:{title}".encode()).hexdigest(), 16) % 99999
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&seed={seed_val}&nologo=true&model=flux"
    return {
        "url": url,
        "alt": title,
        "credit": "Pollinations AI",
        "credit_url": "https://pollinations.ai",
        "source": "ai_hero",
        "source_label": "🎨 AI 생성 대표이미지",
    }


def collect_images(query: str, labels: list = None, exclude_urls: set = None):
    """다중 소스에서 이미지 수집, 우선순위 적용 — 최소 3장 보장
    
    exclude_urls: 이미 수집된 URL 집합 — 이 URL은 처음부터 제외 (중복 방지)
    반환: (images: list, all_seen: set) — 검증 실패 포함 모든 수집 URL 집합 반환
    """
    all_images = []
    seen_urls: set = set(exclude_urls) if exclude_urls else set()
    initial_seen = set(seen_urls)  # exclude_urls 포함 초기 상태 기록

    def _add(img_list):
        for img in img_list:
            if img["url"] not in seen_urls:
                # Reddit thumb 소형 이미지(140px) 제외
                if "width=140" in img["url"] or "height=140" in img["url"]:
                    continue
                seen_urls.add(img["url"])
                all_images.append(img)

    # 0순위: Google 이미지 검색
    print(f"  🔍 Google 이미지 검색 중...")
    _add(search_google_images(query))

    # 1순위: 뉴스/블로그 소스 (신뢰도 최고)
    if len(all_images) < 3:
        print(f"  📰 뉴스 소스 검색 중...")
        _add(search_from_news_sources(query, labels))

    # Bing 보완
    if len(all_images) < 2:
        print(f"  🔍 Bing 이미지 검색 중...")
        _add(search_bing_images(query))

    # Reddit (direct URL만 — thumb 제외는 _add에서 처리)
    if len(all_images) < 3:
        print(f"  💬 Reddit 검색 중...")
        _add(search_from_reddit(query))

    # Wikimedia Commons
    if len(all_images) < 3:
        print(f"  🖼️  Wikimedia 검색 중...")
        _add(search_wikimedia(query))

    # Unsplash API / Direct
    if len(all_images) < 3:
        if UNSPLASH_ACCESS_KEY:
            print(f"  📸 Unsplash API 검색 중...")
            _add(search_unsplash(query))
        else:
            print(f"  📸 Unsplash Direct 검색 중...")
            _add(search_unsplash_direct(query))

    # 이미지 접근 가능 여부 실제 검증 (만료 URL 걸러냄)
    verified = []
    for img in all_images:
        if verify_image_accessible(img["url"]):
            verified.append(img)
        else:
            print(f"  ⚠️  이미지 접근 실패, 스킵: {img['url'][:60]}")
            # 접근 실패 URL도 seen_urls에 유지 — 다른 소스에서 중복 추가 방지
    all_images = verified
    # seen_urls는 유지 (검증 실패 URL 포함) — 재수집 시 중복 방지

    # ── 부족하면 Pollinations AI로 채우기 (항상 성공, 주제 맞춤) ──────────────
    if len(all_images) < 3:
        need = 3 - len(all_images)
        print(f"  🤖 이미지 부족({len(all_images)}장) — Pollinations AI로 {need}장 생성...")
        for i in range(need + 1):  # 여유분 1장 추가
            if len(all_images) >= 5:
                break
            ai_img = _make_pollinations_image(query, i)
            if ai_img["url"] not in seen_urls:
                seen_urls.add(ai_img["url"])
                all_images.append(ai_img)
                print(f"  ✅ Pollinations AI 이미지 [{i+1}]")

    # ── 최후 폴백: FALLBACK_IMAGES (날짜+idx로 다양하게) ──────────────────────
    if len(all_images) < 3:
        seed_str = query + datetime.date.today().isoformat()
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        for fi in range(len(FALLBACK_IMAGES)):
            if len(all_images) >= 5:
                break
            fb = FALLBACK_IMAGES[(seed + fi) % len(FALLBACK_IMAGES)]
            if fb["url"] not in seen_urls:
                seen_urls.add(fb["url"])
                all_images.append(fb)

    # 최종 폴백: FALLBACK_IMAGES (Unsplash 고정 URL, 항상 안정적)
    if not all_images:
        # query + 날짜 기반 hash — 날짜마다 다른 이미지 선택
        seed_str = query + datetime.date.today().isoformat()
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        fallback = FALLBACK_IMAGES[seed % len(FALLBACK_IMAGES)]
        all_images.append(fallback)
        print(f"  🔄 Fallback 이미지 사용: {fallback['url'][:60]}...")

    # seen_urls에는 검증 실패 URL도 포함 — 호출자가 중복 방지에 활용
    return all_images[:5], seen_urls


def insert_body_images(body: str, images: list, title: str = "") -> str:
    """
    본문 마크다운에 이미지를 최대 4개 자연스럽게 삽입
    - images[1:5] (hero 제외 최대 4개)를 h2 섹션에 배분
    - h2 섹션이 부족하면 있는 만큼만 삽입
    - <pre>, <code> 블록 사이에는 삽입하지 않음
    """
    if len(images) < 2:
        return body

    lines = body.split("\n")
    h2_positions = [i for i, l in enumerate(lines) if l.startswith("## ")]

    if len(h2_positions) < 2:
        return body  # h2가 2개 미만이면 삽입 불가

    # <pre>/<code> 블록 범위 탐지 (삽입 금지 구간)
    forbidden_ranges = []
    in_code = False
    code_start = 0
    for i, line in enumerate(lines):
        if re.match(r'^\s*```', line) or re.match(r'^\s*<pre', line, re.I):
            if not in_code:
                in_code = True
                code_start = i
        elif in_code and (re.match(r'^\s*```', line) or re.match(r'^\s*</pre', line, re.I)):
            forbidden_ranges.append((code_start, i))
            in_code = False

    def is_forbidden(pos: int) -> bool:
        for start, end in forbidden_ranges:
            if start <= pos <= end:
                return True
        return False

    # body 이미지: images[1:5] — 최대 4개
    body_images = images[1:5]
    num_to_insert = min(len(body_images), len(h2_positions) - 1)

    if num_to_insert == 0:
        return body

    # h2 섹션을 균등 분배하여 삽입 위치 계산
    # 예: h2 5개, 이미지 4개 → 2번째, 3번째, 4번째, 5번째 h2 뒤에 삽입
    # h2가 3개이고 이미지 4개이면 → 2번째, 3번째 h2 뒤에만 삽입 (2개)
    h2_slots = h2_positions[1:]  # 1번째 h2 이후부터 사용
    if len(h2_slots) < num_to_insert:
        num_to_insert = len(h2_slots)

    # 균등 간격으로 슬롯 선택
    step = len(h2_slots) / num_to_insert
    selected_h2s = [h2_slots[int(i * step)] for i in range(num_to_insert)]

    insert_positions = []
    for h2_pos in selected_h2s:
        # 해당 h2 뒤 첫 빈 줄 다음 위치 탐색
        insert_at = h2_pos + 2
        for i in range(h2_pos + 1, min(h2_pos + 6, len(lines))):
            if lines[i].strip() == "":
                insert_at = i + 1
                break
        # 금지 구간이면 다음 줄로
        while is_forbidden(insert_at) and insert_at < len(lines):
            insert_at += 1
        insert_positions.append(insert_at)

    # 이미지 HTML 생성
    def make_img_md(img: dict) -> str:
        url = img["url"]
        alt = img.get("alt", title or "관련 이미지")[:100]
        credit_url = img.get("credit_url", "")
        source_label = img.get("source_label", "📷 출처")

        # 도메인명만 표시 (기사 제목/영어 텍스트 제거)
        domain_name = get_domain_name(credit_url) if credit_url else img.get("credit", "출처")

        credit_html = (
            f'<a href="{credit_url}" rel="nofollow noopener"'
            f' style="color:#4f6ef7;text-decoration:none;">{domain_name}</a>'
            if credit_url else domain_name
        )
        return (
            f'\n<figure style="margin:2em 0;text-align:center;">'
            f'<img src="{url}" alt="{alt}" '
            f'width="800" height="450" '
            f'style="width:100%;max-width:760px;height:auto;aspect-ratio:16/9;'
            f'border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.12);object-fit:cover;" '
            f'loading="lazy" decoding="async"/>'
            f'<figcaption style="font-size:.82em;color:#888;margin-top:.6em;line-height:1.5;">'
            f'{source_label}: {credit_html}'
            f'</figcaption></figure>\n'
        )

    # 역순으로 삽입 (인덱스 밀림 방지)
    pairs = list(zip(insert_positions[:num_to_insert], body_images[:num_to_insert]))
    for pos, img in sorted(pairs, key=lambda x: -x[0]):
        img_md = make_img_md(img)
        lines.insert(min(pos, len(lines)), img_md)

    return "\n".join(lines)


def inject_images(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    query = meta.get("image_query", meta.get("title", "artificial intelligence"))
    title = meta.get("title", "")
    labels = meta.get("labels", [])
    if isinstance(labels, str):
        labels = [l.strip() for l in labels.split(",")]

    print(f"  🔍 이미지 검색: {query}")

    # 전역 중복 추적 set — 검증 실패 URL 포함 모든 수집 시도 URL 기록
    global_seen: set = set()

    # 1차 수집
    images, all_seen1 = collect_images(query, labels, exclude_urls=global_seen)
    global_seen.update(all_seen1)  # 검증 실패 포함 모든 URL 기록

    # 부족하면 추가 수집 (global_seen 전달로 이미 시도한 URL 완전 차단)
    if len(images) < 5:
        extra_queries = [query + " 2026", query + " guide", query + " technology"]
        for eq in extra_queries:
            if len(images) >= 5:
                break
            extra_imgs, all_seen_extra = collect_images(eq, labels, exclude_urls=global_seen)
            global_seen.update(all_seen_extra)
            # 최종 중복 체크 (혹시 global_seen 갱신 타이밍 이슈 방지)
            for img in extra_imgs:
                if img["url"] not in {i["url"] for i in images}:
                    images.append(img)
                    if len(images) >= 5:
                        break

    # 여전히 부족하면 Pollinations AI로 주제 맞춤 이미지 생성
    if len(images) < 3:
        print(f"  🤖 이미지 부족({len(images)}장) — AI 이미지 생성으로 보완...")
        # Pollinations.ai — 무료 AI 이미지 생성, API 키 불필요
        import hashlib as _hl
        ai_prompts = [
            f"{query}, professional blog illustration, clean modern style, 16:9",
            f"{query} concept, infographic style, Korean blog, bright colors",
            f"{query} overview, minimalist design, technology, 2026",
        ]
        for i, ap in enumerate(ai_prompts):
            if len(images) >= 5:
                break
            # seed를 title+index 기반으로 고정 → 매번 같은 이미지 생성 방지
            seed_val = int(_hl.md5(f"{title}{i}".encode()).hexdigest(), 16) % 99999
            encoded_prompt = urllib.parse.quote(ap)
            ai_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed_val}&nologo=true"
            try:
                req_check = urllib.request.Request(ai_url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
                with urllib.request.urlopen(req_check, timeout=15) as _r:
                    if _r.status == 200 and ai_url not in seen_urls:
                        seen_urls.add(ai_url)
                        images.append({
                            "url": ai_url,
                            "alt": f"{query} 설명 이미지",
                            "credit": "Pollinations AI",
                            "credit_url": "https://pollinations.ai",
                            "source": "ai_generated",
                            "source_label": "🤖 AI 생성 이미지",
                        })
                        print(f"  ✅ AI 이미지 생성 성공 [{i+1}]")
            except Exception as _ae:
                print(f"  ⚠️  AI 이미지 생성 실패 [{i+1}]: {_ae}")

    # Unsplash 고정 풀에서 추가 (최후 보완, 항상 다른 사진)
    if len(images) < 3:
        import hashlib as _hl2
        for fi, fb in enumerate(FALLBACK_IMAGES):
            if len(images) >= 5:
                break
            if fb["url"] not in seen_urls:
                seen_urls.add(fb["url"])
                images.append(fb)

    # ── images 리스트 자체 중복 제거 (global_seen 타이밍 이슈 최종 방어) ──────────
    _seen_final = set()
    images_dedup = []
    for img in images:
        if img["url"] not in _seen_final:
            _seen_final.add(img["url"])
            images_dedup.append(img)
    images = images_dedup

    # ── hero 이미지 선택: 배경+텍스트 형태로 대표이미지 최적화 ───────────────────
    # 크롤링 이미지(news/reddit/wikimedia)가 있으면 hero로 사용,
    # 없거나 AI생성만 있으면 make_hero_image로 배경+텍스트 썸네일 생성
    real_imgs = [img for img in images if img.get("source") not in ("ai_generated", "ai_hero", "fallback")]
    if real_imgs:
        hero = real_imgs[0]  # 실제 이미지 중 첫 번째를 hero로
    else:
        # 크롤링 이미지 없음 → 배경+텍스트 AI 썸네일 생성
        hero = make_hero_image(title, query)
        if hero["url"] not in global_seen:
            global_seen.add(hero["url"])
        print(f"  🎨 Hero: 배경+텍스트 AI 썸네일 생성")

    print(f"  ✅ 대표 이미지 확보 ({hero['source']}) — 총 {len(images)}장")

    # ── 본문 이미지 삽입 (h2 섹션 사이, 최대 4개) ─────────────────────────────
    # hero는 제외하고 나머지(중복 없이)를 본문에 삽입
    body_imgs = [img for img in images if img["url"] != hero["url"]]
    if body_imgs:
        body = insert_body_images(body, [hero] + body_imgs, title)
        print(f"  ✅ 본문 이미지 {min(len(body_imgs), 4)}개 삽입")
    else:
        print(f"  ⚠️  본문 삽입용 이미지 없음 — hero만 사용")

    # ── front matter에 hero 정보 저장 ──────────────────────────────
    hero_url          = hero["url"]
    hero_alt          = hero.get("alt", "")
    hero_credit       = hero.get("credit", "")
    hero_credit_url   = hero.get("credit_url", "")
    hero_source_label = hero.get("source_label", "")

    if content.startswith("---"):
        parts = content.split("---", 2)
        fm_text = parts[1]

        def _set_fm(fm, key, val):
            val_escaped = val.replace('"', '\\"')
            if f"{key}:" in fm:
                fm = re.sub(rf'{key}:.*', f'{key}: "{val_escaped}"', fm)
            else:
                fm = fm.rstrip() + f'\n{key}: "{val_escaped}"\n'
            return fm

        fm_text = _set_fm(fm_text, "hero_image_url",    hero_url)
        fm_text = _set_fm(fm_text, "hero_image_alt",    hero_alt)
        fm_text = _set_fm(fm_text, "hero_credit",       hero_credit)
        fm_text = _set_fm(fm_text, "hero_credit_url",   hero_credit_url)
        fm_text = _set_fm(fm_text, "hero_source_label", hero_source_label)

        new_content = "---" + fm_text + "---\n\n" + body
    else:
        new_content = body

    Path(file_path).write_text(new_content, encoding="utf-8")
    print(f"  ✅ 이미지 처리 완료 (hero + 본문 {min(len(images)-1,2)}개)")
    return file_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_images.py <markdown_file>")
        sys.exit(0)
    print(f"🖼️  이미지 처리: {sys.argv[1]}")
    inject_images(sys.argv[1])
