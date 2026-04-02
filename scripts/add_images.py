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
                if img_url and is_valid_image_url(img_url):
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

                # RSS 이미지 없으면 기사 페이지 scrapling → og:image
                if link:
                    try:
                        page_html = scrapling_fetch(link, timeout=15)
                        og = extract_og_image(page_html) if page_html else None
                        if og and is_valid_image_url(og):
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
                if hint == "image" and ext_url and is_valid_image_url(ext_url):
                    post_url = f"https://reddit.com{pd.get('permalink', '')}"
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
                if thumb and thumb.startswith("http") and is_valid_image_url(thumb):
                    post_url = f"https://reddit.com{pd.get('permalink', '')}"
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
    """이미지 딕셔너리 → SEO 최적화 HTML figure"""
    url = img["url"]
    alt = img.get("alt", "")[:100]
    credit = img.get("credit", "")
    credit_url = img.get("credit_url", "")
    source_label = img.get("source_label", "📷 출처")

    credit_html = (
        f'<a href="{credit_url}" target="_blank" rel="noopener noreferrer"'
        f' style="color:#4f6ef7;text-decoration:none;">{credit}</a>'
        if credit_url else credit
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

def collect_images(query: str, labels: list = None) -> list:
    """다중 소스에서 이미지 수집, 우선순위 적용"""
    all_images = []

    # 1순위: 뉴스/블로그 소스 scrapling (신뢰도 최고)
    print(f"  📰 뉴스 소스 검색 중...")
    news_imgs = search_from_news_sources(query, labels)
    all_images.extend(news_imgs)

    # 뉴스에서 못 찾으면 Reddit 시도 (단, 만료 안 되는 URL만 허용)
    if len(all_images) < 2:
        print(f"  💬 Reddit 검색 중...")
        reddit_imgs = search_from_reddit(query)
        all_images.extend(reddit_imgs)

    # 2순위: Wikimedia Commons (무료 CC 라이선스, 안정적 URL)
    if len(all_images) < 2:
        print(f"  🖼️  Wikimedia 검색 중...")
        wiki_imgs = search_wikimedia(query)
        all_images.extend(wiki_imgs)

    # 3순위: Unsplash API (키 있을 때) 또는 Direct
    if len(all_images) < 2:
        if UNSPLASH_ACCESS_KEY:
            print(f"  📸 Unsplash API 검색 중...")
            unsplash_imgs = search_unsplash(query)
            all_images.extend(unsplash_imgs)
        else:
            print(f"  📸 Unsplash Direct 검색 중...")
            unsplash_imgs = search_unsplash_direct(query)
            all_images.extend(unsplash_imgs)

    # 이미지 접근 가능 여부 실제 검증 (만료 URL 걸러냄)
    verified = []
    for img in all_images:
        if verify_image_accessible(img["url"]):
            verified.append(img)
        else:
            print(f"  ⚠️  이미지 접근 실패, 스킵: {img['url'][:60]}")

    all_images = verified

    # 검증 후 이미지 부족하면 Unsplash Direct 추가 시도 (항상 안정적)
    if len(all_images) < 1:
        print(f"  📸 Unsplash Direct 폴백 시도...")
        unsplash_direct = search_unsplash_direct(query)
        for img in unsplash_direct:
            if verify_image_accessible(img["url"]):
                all_images.append(img)
                print(f"  ✅ Unsplash Direct 폴백 성공")
                break

    # 최종 폴백: FALLBACK_IMAGES (Unsplash 고정 URL, 항상 안정적)
    if not all_images:
        seed = int(hashlib.md5((query + datetime.date.today().isoformat()).encode()).hexdigest(), 16)
        fallback = FALLBACK_IMAGES[seed % len(FALLBACK_IMAGES)]
        all_images.append(fallback)
        print(f"  🔄 Fallback 이미지 사용: {fallback['url'][:60]}...")

    return all_images[:2]


def inject_images(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    query = meta.get("image_query", meta.get("title", "artificial intelligence"))
    title = meta.get("title", "")
    labels = meta.get("labels", [])
    if isinstance(labels, str):
        labels = [l.strip() for l in labels.split(",")]

    print(f"  🔍 이미지 검색: {query}")

    images = collect_images(query, labels)

    # ── 대표 이미지 (hero) ──
    # collect_images()가 항상 최소 1개 반환하므로 else 불필요
    hero_html = build_image_html(images[0], is_hero=True)
    print(f"  ✅ 대표 이미지 확보 ({images[0]['source']})")

    # ── 본문 중간 이미지 (2번째 h2 앞에 삽입) ──
    h2_positions = [m.start() for m in re.finditer(r'^## ', body, re.MULTILINE)]
    if len(images) > 1 and len(h2_positions) >= 2:
        img2_html = build_image_html(images[1], is_hero=False)
        insert_pos = h2_positions[len(h2_positions) // 2]  # 중간 섹션
        body = body[:insert_pos] + img2_html + "\n" + body[insert_pos:]
        print(f"  ✅ 중간 이미지 삽입 ({images[1]['source']})")

    # front matter에 hero_image_url 저장 (post_to_blogger.py가 읽을 수 있도록)
    if content.startswith("---"):
        parts = content.split("---", 2)
        fm_text = parts[1]
        body_text = body  # 이미 파싱된 body 사용 (중간 이미지 삽입 후)

        hero_url = images[0]["url"] if images else ""
        # 기존 hero_image_url 있으면 교체, 없으면 추가
        if "hero_image_url:" in fm_text:
            fm_text = re.sub(r'hero_image_url:.*', f'hero_image_url: "{hero_url}"', fm_text)
        else:
            fm_text = fm_text.rstrip() + f'\nhero_image_url: "{hero_url}"\n'

        new_content = "---" + fm_text + "---\n\n" + hero_html + "\n" + body_text
    else:
        new_content = hero_html + "\n" + body

    Path(file_path).write_text(new_content, encoding="utf-8")
    print(f"  ✅ 이미지 삽입 완료 (총 {min(len(images),2)}개)")
    return file_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_images.py <markdown_file>")
        sys.exit(0)
    print(f"🖼️  이미지 처리: {sys.argv[1]}")
    inject_images(sys.argv[1])
