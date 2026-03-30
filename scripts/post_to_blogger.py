#!/usr/bin/env python3
"""
Blogger 자동 포스팅 스크립트 (SEO 최적화 버전)
- 마크다운 → HTML 변환
- SEO 메타태그 자동 삽입
- 중복 포스팅 방지
"""
import os
import sys
import json
import re
import markdown as md_lib
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "3598676904202320050"  # AI키퍼


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


def build_seo_html(title: str, meta_desc: str, html_body: str, labels: list) -> str:
    """SEO 메타태그 포함 HTML 생성"""
    keywords = ", ".join(labels) if labels else title

    seo_head = f"""<!-- SEO Meta -->
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">

<!-- 스타일 -->
<style>
  .post-body img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 16px 0; }}
  .post-body pre {{ background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }}
  .post-body code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  .post-body table {{ border-collapse: collapse; width: 100%; }}
  .post-body th, .post-body td {{ border: 1px solid #ddd; padding: 8px; }}
  .post-body th {{ background: #f2f2f2; }}
</style>

"""
    return seo_head + html_body


def parse_post(file_path: str):
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    html_body = md_lib.markdown(
        body,
        extensions=["tables", "fenced_code", "nl2br", "toc"]
    )

    title = meta.get("title") or Path(file_path).stem.replace("-", " ")
    labels = meta.get("labels", [])
    if isinstance(labels, str):
        labels = [l.strip() for l in labels.split(",")]
    is_draft = str(meta.get("draft", "false")).lower() == "true"
    meta_desc = meta.get("meta_description", "")

    # meta_description 없으면 본문 첫 150자
    if not meta_desc:
        plain = re.sub(r'<[^>]+>', '', html_body)
        meta_desc = plain[:150].strip()

    final_html = build_seo_html(title, meta_desc, html_body, labels)

    return {
        "title": title,
        "content": final_html,
        "labels": labels,
        "is_draft": is_draft,
        "meta_description": meta_desc,
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
        print(f"⚠️  중복 포스트 건너뜀: {post_data['title']}")
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
