#!/usr/bin/env python3
"""
Blogger 자동 포스팅 — 요즘IT/브런치 스타일 HTML
- 실제 상위 블로그 분석 기반 CSS
- JSON-LD 구조화 데이터
- 모바일 최적화
- 중복 방지
"""
import os
import sys
import json
import re
import datetime
import requests
import markdown as md_lib
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BLOG_ID = "3598676904202320050"  # AI키퍼
BLOG_URL = "https://aikeeper.allsweep.xyz"
BLOG_NAME = "AI키퍼"

# ── Google AdSense 광고 코드 ──────────────────────────────────────
ADSENSE_PUB = "ca-pub-2597570939533872"

# 인아티클 광고 — 본문 섹션 사이 삽입 (클릭률 가장 높음)
AD_IN_ARTICLE = """
<div style="margin:2.5em 0;text-align:center;">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2597570939533872" crossorigin="anonymous"></script>
<ins class="adsbygoogle"
 style="display:block;text-align:center;"
 data-ad-layout="in-article"
 data-ad-format="fluid"
 data-ad-client="ca-pub-2597570939533872"
 data-ad-slot="6675974233"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
"""

# 디스플레이 광고 — 본문 하단 삽입
AD_DISPLAY = """
<div style="margin:2.5em 0;">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2597570939533872" crossorigin="anonymous"></script>
<ins class="adsbygoogle"
 style="display:block"
 data-ad-client="ca-pub-2597570939533872"
 data-ad-slot="8117048415"
 data-ad-format="auto"
 data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
"""

# ── 성능 최적화: Google Fonts preconnect (렌더 블로킹 제거) ──────
# @import → preconnect + link rel=stylesheet 방식으로 교체
# AdSense script는 본문 하단 1회만 삽입 (중복 제거)
FONT_PRECONNECT = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" media="print" onload="this.media='all'">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap"></noscript>"""

# AdSense 초기화 스크립트 — 포스트당 1회만 (async, 중복 방지)
ADSENSE_INIT = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2597570939533872" crossorigin="anonymous"></script>"""

# 인아티클 광고 — script 태그 없이 ins + push만 (init은 위에서 1회)
AD_IN_ARTICLE_INS = """
<div style="margin:2.5em 0;text-align:center;min-height:200px;">
<ins class="adsbygoogle"
 style="display:block;text-align:center;"
 data-ad-layout="in-article"
 data-ad-format="fluid"
 data-ad-client="ca-pub-2597570939533872"
 data-ad-slot="6675974233"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
"""

# 디스플레이 광고 — 하단
AD_DISPLAY_INS = """
<div style="margin:2.5em 0;min-height:100px;">
<ins class="adsbygoogle"
 style="display:block"
 data-ad-client="ca-pub-2597570939533872"
 data-ad-slot="8117048415"
 data-ad-format="auto"
 data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
"""

# 하위 호환: 기존 변수명 유지
AD_IN_ARTICLE = AD_IN_ARTICLE_INS
AD_DISPLAY = AD_DISPLAY_INS

# ── 프리미엄 CSS — @import 제거, 시스템폰트 fallback 우선 ─────────
PREMIUM_CSS = """
<style>
.ak-post{font-family:'Noto Sans KR',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;font-size:17px;line-height:1.9;color:#1a1a2e;max-width:760px;margin:0 auto;padding:0 4px;word-break:keep-all;overflow-wrap:break-word;content-visibility:auto;}
.ak-post > p:first-of-type{font-size:1.08em;color:#2c3e70;line-height:2;padding:20px 24px;background:linear-gradient(135deg,#f0f4ff 0%,#e8f4f8 100%);border-radius:12px;border-left:4px solid #4f6ef7;margin-bottom:2em;}
.ak-post h2{font-size:1.5em;font-weight:700;color:#0d1b4b;margin:2.5em 0 0.9em;padding:0 0 0.5em;border-bottom:2px solid #e8ecf4;position:relative;}
.ak-post h2::before{content:'';position:absolute;bottom:-2px;left:0;width:60px;height:2px;background:#4f6ef7;}
.ak-post h3{font-size:1.15em;font-weight:600;color:#1a237e;margin:1.8em 0 0.6em;padding-left:12px;border-left:3px solid #7c8ef7;}
.ak-post h4{font-size:1em;font-weight:600;color:#37474f;margin:1.4em 0 0.4em;}
.ak-post p{margin:0 0 1.4em;}
.ak-post strong{color:#1a237e;font-weight:700;}
.ak-post blockquote{background:#f5f7ff;border-left:4px solid #4f6ef7;border-radius:0 10px 10px 0;margin:1.8em 0;padding:1.1em 1.5em;color:#2c3a7a;font-size:0.97em;position:relative;}
.ak-post blockquote::before{content:'💡';position:absolute;top:-12px;left:12px;font-size:1.2em;background:#f5f7ff;padding:0 4px;}
.ak-post blockquote p{margin:0;line-height:1.75;}
.ak-post code{background:#f0f2fa;color:#c0392b;padding:2px 8px;border-radius:5px;font-size:0.88em;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;border:1px solid #e0e4f0;}
.ak-post pre{background:#1a1f35;color:#cdd5f5;padding:1.4em 1.6em;border-radius:12px;overflow-x:auto;font-size:0.87em;line-height:1.65;margin:1.8em 0;box-shadow:0 4px 16px rgba(0,0,0,0.2);}
.ak-post pre code{background:none;color:inherit;padding:0;border:none;font-size:inherit;}
.ak-post ul,.ak-post ol{padding-left:1.7em;margin:0.6em 0 1.4em;}
.ak-post li{margin-bottom:0.6em;line-height:1.75;}
.ak-post ul > li::marker{color:#4f6ef7;font-size:1.1em;}
.ak-post ol > li::marker{color:#4f6ef7;font-weight:700;}
.ak-post table{width:100%;border-collapse:collapse;margin:2em 0;font-size:0.94em;box-shadow:0 2px 12px rgba(79,110,247,0.1);border-radius:10px;overflow:hidden;}
.ak-post th{background:linear-gradient(135deg,#4f6ef7,#7c8ef7);color:white;font-weight:600;padding:13px 18px;text-align:left;font-size:0.93em;letter-spacing:0.02em;}
.ak-post td{padding:11px 18px;border-bottom:1px solid #edf0fb;vertical-align:top;line-height:1.65;}
.ak-post tr:nth-child(even) td{background:#f8f9ff;}
.ak-post tr:last-child td{border-bottom:none;}
.ak-post tr:hover td{background:#f0f3ff;transition:background 0.15s;}
.ak-post img{max-width:100%;height:auto;border-radius:12px;margin:1.8em auto;display:block;box-shadow:0 6px 24px rgba(0,0,0,0.1);}
.ak-post p > em:only-child,.ak-post em.caption{display:block;text-align:center;font-size:0.82em;color:#999;font-style:normal;margin-top:-1.2em;margin-bottom:1.8em;}
.ak-post hr{border:none;height:2px;background:linear-gradient(90deg,#4f6ef7 0%,transparent 100%);margin:2.5em 0;border-radius:2px;}
.ak-post .summary-section{background:linear-gradient(135deg,#e8edff 0%,#f0f8ff 100%);border-radius:14px;padding:1.6em 2em;margin:2.5em 0;border:1px solid #d0d8ff;}
.ak-post .summary-section h2{border-bottom-color:transparent;margin-top:0;color:#1a237e;}
.ak-post .summary-section h2::before{display:none;}
@media (max-width:640px){.ak-post{font-size:15.5px;padding:0;}
.ak-post h2{font-size:1.25em;margin-top:2em;}
.ak-post h3{font-size:1.05em;}
.ak-post > p:first-of-type{font-size:1em;padding:14px 16px;}
.ak-post pre{font-size:0.82em;padding:1em;border-radius:8px;}
.ak-post blockquote{padding:0.9em 1.1em;}
.ak-post table{font-size:0.87em;}
.ak-post th,.ak-post td{padding:9px 12px;}
}
</style>
"""


def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    creds.refresh(Request())
    return creds


def parse_front_matter(content: str):
    meta, body = {}, content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    # YAML 파싱 실패 시 단순 파싱으로 폴백
                    meta = {}
                    for line in parts[1].strip().splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip()] = v.strip().strip('"').replace('\\"', '"')
            except ImportError:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()
    return meta, body


def estimate_read_time(html: str) -> int:
    """평균 읽기 속도 200wpm 기준 읽기 시간(분) 계산"""
    text = re.sub(r'<[^>]+>', '', html)
    words = len(text.split())
    return max(1, round(words / 200))


def count_words(html: str) -> int:
    text = re.sub(r'<[^>]+>', '', html)
    return len(text.split())


def build_json_ld(title: str, meta_desc: str, labels: list,
                  faqs: list = None, hero_image_url: str = "",
                  word_count: int = 0, read_time: int = 0) -> str:
    pub_date = datetime.date.today().isoformat()
    keywords = ", ".join(labels)

    # ── 1. BlogPosting (구글 Article 권장 필드 모두 포함) ──
    blogposting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title[:110],          # 구글 권장: 110자 이내
        "description": meta_desc[:300],
        "keywords": keywords,
        "datePublished": pub_date,
        "dateModified": pub_date,
        "author": {
            "@type": "Organization",
            "name": BLOG_NAME,
            "url": BLOG_URL
        },
        "publisher": {
            "@type": "Organization",
            "name": BLOG_NAME,
            "url": BLOG_URL,
            "logo": {
                "@type": "ImageObject",
                "url": f"{BLOG_URL}/favicon.ico"
            }
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": BLOG_URL
        },
        "inLanguage": "ko-KR",
    }
    if hero_image_url:
        blogposting["image"] = {
            "@type": "ImageObject",
            "url": hero_image_url,
            "width": 1200,
            "height": 630
        }
    if word_count:
        blogposting["wordCount"] = word_count
    if read_time:
        blogposting["timeRequired"] = f"PT{read_time}M"

    scripts = f"""<script type="application/ld+json">
{json.dumps(blogposting, ensure_ascii=False, indent=2)}
</script>"""

    # ── 2. FAQPage (리치 스니펫 — 검색결과에 FAQ 펼침 표시) ──
    if faqs:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": f["a"]}
                }
                for f in faqs if f.get("q") and f.get("a")
            ]
        }
        if faq_schema["mainEntity"]:
            scripts += f"""
<script type="application/ld+json">
{json.dumps(faq_schema, ensure_ascii=False, indent=2)}
</script>"""

    # ── 3. BreadcrumbList (사이트 구조 명확화) ──
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1,
             "name": "홈", "item": BLOG_URL},
            {"@type": "ListItem", "position": 2,
             "name": "AI 블로그", "item": f"{BLOG_URL}/"},
            {"@type": "ListItem", "position": 3,
             "name": title[:50], "item": BLOG_URL}
        ]
    }
    scripts += f"""
<script type="application/ld+json">
{json.dumps(breadcrumb, ensure_ascii=False, indent=2)}
</script>"""

    # ── 4. WebSite (사이트 전체 스키마) ──
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": BLOG_NAME,
        "url": BLOG_URL,
        "inLanguage": "ko-KR",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{BLOG_URL}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string"
        }
    }
    scripts += f"""
<script type="application/ld+json">
{json.dumps(website, ensure_ascii=False, indent=2)}
</script>"""

    return scripts


def inject_ads(html: str) -> str:
    """본문 HTML에 AdSense 광고 자동 삽입
    
    배치 전략:
      - 인아티클 ①: 전체 h2 섹션 중 1/3 지점 (독자 몰입 직후)
      - 인아티클 ②: 2/3 지점 (본문 후반부 진입 시)  
      - 디스플레이:  본문 최하단 (읽기 완료 후)
    """
    # h2 태그 위치 모두 수집
    h2_positions = [(m.start(), m.end()) for m in re.finditer(r'<h2[^>]*>.*?</h2>', html, re.DOTALL)]
    total = len(h2_positions)

    if total < 2:
        # 섹션이 너무 적으면 중간 + 하단에만 삽입
        mid = len(html) // 2
        html = html[:mid] + AD_IN_ARTICLE + html[mid:]
        html = html + AD_DISPLAY
        return html

    # 1/3 지점 h2 앞에 인아티클 ①
    idx1 = max(1, total // 3)
    pos1 = h2_positions[idx1][0]

    # 2/3 지점 h2 앞에 인아티클 ②
    idx2 = max(idx1 + 1, (total * 2) // 3)
    idx2 = min(idx2, total - 1)

    # 역순으로 삽입 (앞 삽입이 뒤 위치에 영향 주지 않도록)
    pos2 = h2_positions[idx2][0]

    # pos2 > pos1 보장
    if pos2 > pos1:
        html = html[:pos2] + AD_IN_ARTICLE + html[pos2:]
        html = html[:pos1] + AD_IN_ARTICLE + html[pos1:]
    else:
        html = html[:pos1] + AD_IN_ARTICLE + html[pos1:]

    # 디스플레이 광고: 본문 마지막에 추가
    html = html + AD_DISPLAY

    return html


def fix_images_for_cls(html: str) -> str:
    """CLS(누적 레이아웃 이동) 방지 — 이미지에 width/height/lazy/decoding 추가
    
    - width/height: 브라우저가 공간 미리 확보 → CLS 제거
    - loading=lazy: 뷰포트 밖 이미지 지연 로드 → LCP 개선
    - decoding=async: 메인스레드 블로킹 제거
    - fetchpriority=high: 첫 번째 이미지(LCP 후보)만 우선 로드
    """
    first_img = True

    def fix_img(m):
        nonlocal first_img
        tag = m.group(0)

        # loading 설정
        if 'loading=' not in tag:
            if first_img:
                # LCP 후보: 첫 이미지는 eager + fetchpriority=high
                tag = tag.rstrip('>').rstrip('/') + ' loading="eager" fetchpriority="high" decoding="async">'
                first_img = False
            else:
                tag = tag.rstrip('>').rstrip('/') + ' loading="lazy" decoding="async">'
        else:
            if 'decoding=' not in tag:
                tag = tag.rstrip('>').rstrip('/') + ' decoding="async">'
            first_img = False

        # width/height 없으면 기본값 추가 → CLS 방지
        if 'width=' not in tag and 'height=' not in tag:
            tag = tag.replace('<img ', '<img width="800" height="450" style="aspect-ratio:16/9;" ')

        return tag

    return re.sub(r'<img[^>]+>', fix_img, html)


def post_process_html(html: str) -> str:
    """HTML 후처리 — 가독성 강화 + CLS 수정 + 광고 삽입"""
    # 이미지 CLS/LCP/lazy 최적화
    html = fix_images_for_cls(html)

    # 핵심 요약 섹션 div 래핑
    html = re.sub(
        r'(<h2[^>]*>(?:.*?핵심 요약|.*?이것만 기억|.*?정리).*?</h2>)',
        r'<div class="summary-section">\1',
        html,
        flags=re.IGNORECASE
    )

    # 광고 삽입
    html = inject_ads(html)

    return html


def extract_hero_image(html: str) -> str:
    """본문에서 첫 번째 이미지 URL 추출 (OG image용)"""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    return m.group(1) if m else ""


def build_full_html(title: str, meta_desc: str, html_body: str, labels: list, faqs: list = None) -> str:
    keywords = ", ".join(labels)

    # 본문 통계
    word_count = count_words(html_body)
    read_time = estimate_read_time(html_body)
    hero_img = extract_hero_image(html_body)

    json_ld = build_json_ld(title, meta_desc, labels, faqs,
                            hero_image_url=hero_img,
                            word_count=word_count,
                            read_time=read_time)
    processed = post_process_html(html_body)

    # 제목 앞에 h1 삽입 (구글: 페이지당 h1 1개 권장)
    h1_tag = f'<h1 style="font-size:1.9em;font-weight:800;color:#0d1b4b;line-height:1.4;margin:0 0 0.5em;word-break:keep-all;">{title}</h1>\n'

    # 읽기 시간 배지
    read_badge = (
        f'<p style="font-size:0.82em;color:#888;margin:0 0 2em;">'
        f'⏱ 읽기 약 {read_time}분 &nbsp;|&nbsp; 📝 {word_count:,}자'
        f'</p>\n'
    )

    og_image = hero_img or f"{BLOG_URL}/favicon.ico"
    safe_title = title.replace('"', '&quot;')
    safe_meta = meta_desc.replace('"', '&quot;')

    return f"""{json_ld}

<!-- ── 기술 SEO ── -->
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="content-language" content="ko">
<link rel="canonical" href="{BLOG_URL}/">

<!-- ── 검색엔진 메타 ── -->
<meta name="description" content="{safe_meta}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="index, follow">
<meta name="author" content="{BLOG_NAME}">

<!-- ── Open Graph (SNS 공유 최적화) ── -->
<meta property="og:title" content="{safe_title} | {BLOG_NAME}">
<meta property="og:description" content="{safe_meta}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{BLOG_NAME}">
<meta property="og:url" content="{BLOG_URL}/">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ko_KR">
<meta property="article:author" content="{BLOG_NAME}">
<meta property="article:published_time" content="{datetime.date.today().isoformat()}">

<!-- ── Twitter Card ── -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{safe_title}">
<meta name="twitter:description" content="{safe_meta}">
<meta name="twitter:image" content="{og_image}">

<!-- ── Google Search Console 사이트맵 힌트 ── -->
<link rel="alternate" type="application/atom+xml" title="{BLOG_NAME} Feed" href="{BLOG_URL}/feeds/posts/default">

<!-- ── 성능: Fonts preconnect (렌더 블로킹 제거) ── -->
{FONT_PRECONNECT}

<!-- ── 성능: AdSense 초기화 1회만 (중복 script 제거) ── -->
{ADSENSE_INIT}

{PREMIUM_CSS}

<div class="ak-post" lang="ko">
{h1_tag}{read_badge}{processed}
</div>
"""


def parse_post(file_path: str):
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    html_body = md_lib.markdown(
        body,
        extensions=["tables", "fenced_code", "nl2br", "toc", "attr_list"]
    )

    title = meta.get("title") or Path(file_path).stem.replace("-", " ")
    labels = meta.get("labels", [])
    if isinstance(labels, str):
        labels = [l.strip() for l in labels.split(",")]
    is_draft = str(meta.get("draft", "false")).lower() == "true"

    meta_desc = meta.get("meta_description", "")
    if not meta_desc:
        plain = re.sub(r'<[^>]+>', '', html_body)
        meta_desc = plain[:150].strip()

    # FAQ 파싱 (JSON 또는 리스트)
    faqs_raw = meta.get("faqs", [])
    if isinstance(faqs_raw, str):
        try:
            faqs_raw = json.loads(faqs_raw)
        except Exception:
            faqs_raw = []
    faqs = faqs_raw if isinstance(faqs_raw, list) else []

    # SEO 키워드 meta 태그용
    seo_kw = meta.get("seo_keywords", "")

    return {
        "title": title,
        "content": build_full_html(title, meta_desc, html_body, labels, faqs),
        "labels": labels,
        "is_draft": is_draft,
        "seo_keywords": seo_kw,
    }


def blogger_request(method: str, path: str, token: str, body=None, params=None):
    """requests 기반 Blogger API 호출
    - gzip 압축 전송: 30KB+ 대용량 HTML 포스트도 안정적으로 전송
    - httplib2 302 리다이렉트 버그 완전 우회
    """
    import gzip as _gzip
    url = f"https://blogger.googleapis.com/v3{path}"

    if body:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        # gzip 압축 (평균 65% 크기 감소 — 대용량 HTML 302 우회)
        compressed = _gzip.compress(raw)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Content-Encoding": "gzip",
            "Accept-Encoding": "gzip",
        }
        resp = requests.request(
            method, url,
            headers=headers,
            params=params,
            data=compressed,
            allow_redirects=False,
            timeout=30,
        )
    else:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.request(
            method, url,
            headers=headers,
            params=params,
            allow_redirects=False,
            timeout=30,
        )
    return resp


def check_duplicate(token: str, title: str) -> bool:
    try:
        r = blogger_request("GET", f"/blogs/{BLOG_ID}/posts/search",
                            token, params={"q": title[:50]})
        if r.status_code == 200:
            for item in r.json().get("items", []):
                if item["title"] == title:
                    return True
    except Exception:
        pass
    return False


def post_to_blogger(file_path: str):
    import traceback

    print(f"[INFO] 파일: {file_path}")
    print(f"[INFO] BLOG_ID: {BLOG_ID}")

    try:
        creds = get_credentials()
        print(f"[INFO] 토큰 갱신 성공: {creds.valid}")
    except Exception as e:
        print(f"[ERROR] 토큰 갱신 실패: {e}")
        traceback.print_exc()
        sys.exit(1)

    try:
        post_data = parse_post(file_path)
        print(f"[INFO] 파싱 완료: {post_data['title'][:50]}")
    except Exception as e:
        print(f"[ERROR] 마크다운 파싱 실패: {e}")
        traceback.print_exc()
        sys.exit(1)

    token = creds.token

    if check_duplicate(token, post_data["title"]):
        print(f"⚠️  중복 건너뜀: {post_data['title']}")
        return None

    body = {"title": post_data["title"], "content": post_data["content"]}
    if post_data["labels"]:
        body["labels"] = post_data["labels"]

    try:
        is_draft = post_data["is_draft"]
        r = blogger_request(
            "POST", f"/blogs/{BLOG_ID}/posts",
            token,
            body=body,
            params={"isDraft": str(is_draft).lower()},
        )
        if r.status_code not in (200, 201):
            print(f"[ERROR] Blogger API HTTP {r.status_code}: {r.text[:300]}")
            sys.exit(1)
        result = r.json()
        print(f"✅ 포스팅 완료: {result['title']}")
        print(f"   URL: {result.get('url', '(url pending)')}")
        return result
    except Exception as e:
        print(f"[ERROR] Blogger API 실패: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_to_blogger.py <markdown_file>")
        sys.exit(1)
    post_to_blogger(sys.argv[1])
