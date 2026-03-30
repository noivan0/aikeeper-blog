#!/usr/bin/env python3
"""
Blogger 자동 포스팅 (고퀄리티 SEO 버전)
- 상위 블로그 수준 HTML/CSS 스타일
- 가독성 최적화 레이아웃
- 구조화 데이터(JSON-LD) 삽입
- 중복 포스팅 방지
"""
import os
import sys
import json
import re
import datetime
import markdown as md_lib
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "3598676904202320050"  # AI키퍼
BLOG_URL = "https://aikeeper.allsweep.xyz"


# ── 프리미엄 CSS 스타일 ──────────────────────────────────────────
PREMIUM_CSS = """
<style>
/* ── 기본 폰트 & 레이아웃 ── */
.post-body {
  font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 17px;
  line-height: 1.85;
  color: #1a1a2e;
  max-width: 780px;
  margin: 0 auto;
  word-break: keep-all;
}

/* ── 제목 스타일 ── */
.post-body h2 {
  font-size: 1.55em;
  font-weight: 700;
  color: #0d1b4b;
  margin: 2.2em 0 0.8em;
  padding-bottom: 0.4em;
  border-bottom: 3px solid #4f6ef7;
  letter-spacing: -0.3px;
}
.post-body h3 {
  font-size: 1.2em;
  font-weight: 600;
  color: #1a237e;
  margin: 1.6em 0 0.5em;
}

/* ── 단락 ── */
.post-body p {
  margin: 0 0 1.3em;
}

/* ── 강조 ── */
.post-body strong {
  color: #1a237e;
  font-weight: 700;
  background: linear-gradient(180deg, transparent 60%, #e8edff 60%);
  padding: 0 2px;
}

/* ── 인용구 (팁/주의) ── */
.post-body blockquote {
  background: #f0f4ff;
  border-left: 4px solid #4f6ef7;
  border-radius: 0 8px 8px 0;
  margin: 1.5em 0;
  padding: 1em 1.4em;
  color: #2c3e7a;
  font-size: 0.96em;
}
.post-body blockquote p { margin: 0; }

/* ── 코드 ── */
.post-body code {
  background: #f1f3f9;
  color: #c0392b;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.88em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.post-body pre {
  background: #1e2233;
  color: #e8eaf6;
  padding: 1.2em 1.5em;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 0.88em;
  line-height: 1.6;
  margin: 1.5em 0;
}
.post-body pre code {
  background: none;
  color: inherit;
  padding: 0;
  font-size: inherit;
}

/* ── 리스트 ── */
.post-body ul, .post-body ol {
  padding-left: 1.6em;
  margin: 0.8em 0 1.3em;
}
.post-body li {
  margin-bottom: 0.5em;
}
.post-body ul li::marker { color: #4f6ef7; }

/* ── 표 ── */
.post-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5em 0;
  font-size: 0.95em;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.post-body th {
  background: #4f6ef7;
  color: white;
  font-weight: 600;
  padding: 12px 16px;
  text-align: left;
}
.post-body td {
  padding: 10px 16px;
  border-bottom: 1px solid #e8ecf4;
}
.post-body tr:nth-child(even) td { background: #f7f9ff; }
.post-body tr:last-child td { border-bottom: none; }

/* ── 이미지 ── */
.post-body img {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
  margin: 1.5em auto;
  display: block;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

/* ── 이미지 캡션 ── */
.post-body em {
  display: block;
  text-align: center;
  font-size: 0.82em;
  color: #888;
  margin-top: -1em;
  margin-bottom: 1.5em;
}

/* ── 요약 박스 ── */
.post-body h2:has(+ ul),
.summary-box {
  background: #e8edff;
  border-radius: 10px;
  padding: 1.2em 1.5em;
}

/* ── 구분선 ── */
.post-body hr {
  border: none;
  border-top: 2px solid #e8ecf4;
  margin: 2em 0;
}

/* ── 모바일 최적화 ── */
@media (max-width: 640px) {
  .post-body { font-size: 16px; }
  .post-body h2 { font-size: 1.3em; }
  .post-body pre { font-size: 0.82em; padding: 1em; }
  .post-body table { font-size: 0.88em; }
}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap" rel="stylesheet">
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
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except ImportError:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()
    return meta, body


def build_json_ld(title: str, meta_desc: str, labels: list, pub_date: str) -> str:
    """구조화 데이터 (Google 검색 결과 강화)"""
    keywords = ", ".join(labels)
    return f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "{title}",
  "description": "{meta_desc}",
  "keywords": "{keywords}",
  "datePublished": "{pub_date}",
  "author": {{
    "@type": "Organization",
    "name": "AI키퍼",
    "url": "{BLOG_URL}"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "AI키퍼",
    "url": "{BLOG_URL}"
  }}
}}
</script>"""


def enhance_html(html: str) -> str:
    """HTML 후처리 — 가독성 강화"""
    # ✅ 핵심 요약 섹션 배경 강조
    html = re.sub(
        r'(<h2[^>]*>.*?핵심 요약.*?</h2>)',
        r'<div class="summary-box">\1',
        html
    )

    # 이미지 lazy loading
    html = html.replace('<img ', '<img loading="lazy" ')

    return html


def build_full_html(title: str, meta_desc: str, html_body: str, labels: list) -> str:
    keywords = ", ".join(labels)
    pub_date = datetime.date.today().isoformat()
    json_ld = build_json_ld(title, meta_desc, labels, pub_date)

    return f"""{json_ld}

<!-- SEO Meta -->
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="AI키퍼">

{PREMIUM_CSS}

<div class="post-body">
{enhance_html(html_body)}
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

    return {
        "title": title,
        "content": build_full_html(title, meta_desc, html_body, labels),
        "labels": labels,
        "is_draft": is_draft,
    }


def check_duplicate(service, title: str) -> bool:
    try:
        result = service.posts().search(blogId=BLOG_ID, q=title).execute()
        for item in result.get("items", []):
            if item["title"] == title:
                return True
    except Exception:
        pass
    return False


def post_to_blogger(file_path: str):
    creds = get_credentials()
    service = build("blogger", "v3", credentials=creds)
    post_data = parse_post(file_path)

    if check_duplicate(service, post_data["title"]):
        print(f"⚠️  중복 건너뜀: {post_data['title']}")
        return None

    body = {
        "title": post_data["title"],
        "content": post_data["content"],
    }
    if post_data["labels"]:
        body["labels"] = post_data["labels"]

    result = service.posts().insert(
        blogId=BLOG_ID,
        body=body,
        isDraft=post_data["is_draft"],
    ).execute()

    print(f"✅ 포스팅 완료: {result['title']}")
    print(f"   URL: {result['url']}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python post_to_blogger.py <markdown_file>")
        sys.exit(1)
    post_to_blogger(sys.argv[1])
