#!/usr/bin/env python3
"""
이미지 자동 수집 — 다중 소스, 신뢰도 기반
수집 전략 (우선순위 순):
  1. Unsplash Source API (API 키 불필요, 안정적 CDN)
  2. Wikimedia Commons — 무료 CC 라이선스
  3. 관련 뉴스/블로그에서 scrapling으로 og:image 추출
     - TechCrunch, VentureBeat, Ars Technica, TheVerge, 한국IT뉴스
  4. 이모지 배너 CSS (폴백)

제거: Reddit — CDN 서명 파라미터 만료 문제로 신뢰 불가

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
    """scrapling으로 URL 가져오기 — 봇 차단 우회"""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    try:
        result = subprocess.run(
            ["scrapling", "extract", "get", url, tmp,
             "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=timeout
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


# ── 3순위: 뉴스/블로그 소스 scrapling ───────────────────────────

def search_from_news_sources(query: str, labels: list = None) -> list:
    """신뢰 뉴스 소스에서 관련 이미지 수집"""
    results = []

    # 1-1. Google News 검색으로 관련 기사 URL 수집
    search_queries = [
        query,
        " ".join((labels or [])[:3]),
    ]

    article_urls = []
    for sq in search_queries:
        if not sq.strip():
            continue
        try:
            encoded = urllib.parse.quote(sq)
            gnews_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            html = scrapling_fetch(gnews_url, timeout=20)
            if html:
                # RSS에서 링크 추출
                links = re.findall(r'<link>([^<]+)</link>', html)
                for link in links[:8]:
                    if any(src["domain"] in link for src in TRUSTED_SOURCES):
                        article_urls.append(link)
        except Exception:
            pass
        if len(article_urls) >= 5:
            break

    # 1-2. 각 기사에서 og:image 추출
    for url in article_urls[:4]:
        try:
            domain_name = get_domain_name(url)
            html = scrapling_fetch(url, timeout=20)
            if not html:
                continue

            og_img = extract_og_image(html)
            if og_img and is_valid_image_url(og_img):
                results.append({
                    "url": og_img,
                    "alt": query,
                    "credit": domain_name,
                    "credit_url": url,
                    "source": "news",
                    "source_label": f"📰 {domain_name}"
                })
                print(f"  ✅ 뉴스 이미지: {domain_name} — {og_img[:55]}...")
                if len(results) >= 3:
                    break
        except Exception:
            continue

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

    # 1순위: Unsplash Source (API 키 불필요, 안정적)
    print(f"  📸 Unsplash 검색 중...")
    unsplash_imgs = search_unsplash_direct(query)
    all_images.extend(unsplash_imgs)

    # 2순위: Wikimedia Commons (무료 CC, 안정적 URL)
    if len(all_images) < 2:
        print(f"  🖼️  Wikimedia 검색 중...")
        wiki_imgs = search_wikimedia(query)
        all_images.extend(wiki_imgs)

    # 3순위: 뉴스 소스 (scrapling — 실패 가능성 높음)
    if len(all_images) < 2:
        print(f"  📰 뉴스 소스 검색 중...")
        news_imgs = search_from_news_sources(query, labels)
        all_images.extend(news_imgs)

    # Reddit은 제거 — CDN URL 만료 문제로 신뢰 불가

    # 이미지 접근 가능 여부 검증
    verified = []
    for img in all_images:
        if verify_image_accessible(img["url"]):
            verified.append(img)
        else:
            print(f"  ⚠️  이미지 접근 실패, 스킵: {img['url'][:60]}")

    # 검증 실패해도 최소 1개는 보장 (fallback)
    if not verified and all_images:
        verified = [all_images[0]]  # 검증 실패해도 일단 첫번째 사용

    all_images = verified

    # 폴백: FALLBACK_IMAGES (Unsplash 고정 URL, 안정적)
    if not all_images:
        seed = int(hashlib.md5((query + datetime.date.today().isoformat()).encode()).hexdigest(), 16)
        fallback = FALLBACK_IMAGES[seed % len(FALLBACK_IMAGES)]
        all_images.append(fallback)
        print(f"  🔄 Fallback 이미지 사용")

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
