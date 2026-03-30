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

# ── 요즘IT/브런치 분석 기반 프리미엄 CSS ──────────────────────────
PREMIUM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');.ak-post{font-family:'Noto Sans KR',-apple-system,BlinkMacSystemFont,sans-serif;font-size:17px;line-height:1.9;color:#1a1a2e;max-width:760px;margin:0 auto;padding:0 4px;word-break:keep-all;overflow-wrap:break-word;}
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


def build_json_ld(title: str, meta_desc: str, labels: list, faqs: list = None) -> str:
    pub_date = datetime.date.today().isoformat()
    keywords = ", ".join(labels)

    blogposting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": meta_desc,
        "keywords": keywords,
        "datePublished": pub_date,
        "dateModified": pub_date,
        "author": {"@type": "Organization", "name": BLOG_NAME, "url": BLOG_URL},
        "publisher": {"@type": "Organization", "name": BLOG_NAME, "url": BLOG_URL},
        "mainEntityOfPage": {"@type": "WebPage", "@id": BLOG_URL}
    }

    scripts = f"""<script type="application/ld+json">
{json.dumps(blogposting, ensure_ascii=False, indent=2)}
</script>"""

    # FAQ 스키마 (구글 검색 결과에 FAQ 리치 스니펫 표시)
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

    return scripts


def post_process_html(html: str) -> str:
    """HTML 후처리 — 가독성 강화"""
    # 이미지 lazy loading
    html = html.replace('<img ', '<img loading="lazy" ')

    # 핵심 요약 섹션 div 래핑
    html = re.sub(
        r'(<h2[^>]*>(?:.*?핵심 요약|.*?이것만 기억|.*?정리).*?</h2>)',
        r'<div class="summary-section">\1',
        html,
        flags=re.IGNORECASE
    )

    return html


def build_full_html(title: str, meta_desc: str, html_body: str, labels: list, faqs: list = None) -> str:
    keywords = ", ".join(labels)
    json_ld = build_json_ld(title, meta_desc, labels, faqs)
    processed = post_process_html(html_body)

    return f"""{json_ld}

<!-- SEO -->
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta property="og:title" content="{title} | {BLOG_NAME}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{BLOG_NAME}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{meta_desc}">

{PREMIUM_CSS}

<div class="ak-post">
{processed}
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
    """requests 기반 Blogger API 호출 (httplib2 302 버그 우회)
    body를 json= 대신 data= raw bytes로 전송해야 리다이렉트 방지됨.
    """
    url = f"https://blogger.googleapis.com/v3{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    resp = requests.request(
        method, url,
        headers=headers,
        params=params,
        data=raw,
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
