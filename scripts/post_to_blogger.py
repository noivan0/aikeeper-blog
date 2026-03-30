#!/usr/bin/env python3
"""
Blogger 자동 포스팅 스크립트
- 마크다운 파일을 HTML로 변환 후 Blogger API로 포스팅
- Front Matter(YAML) 지원: title, labels, draft
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
    """YAML Front Matter 파싱"""
    meta = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except ImportError:
                # yaml 없으면 간단 파싱
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()

    return meta, body


def parse_post(file_path: str):
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    # 마크다운 → HTML
    html_body = md_lib.markdown(
        body,
        extensions=["tables", "fenced_code", "nl2br"]
    )

    title = meta.get("title") or Path(file_path).stem.replace("-", " ")
    labels = meta.get("labels", [])
    if isinstance(labels, str):
        labels = [l.strip() for l in labels.split(",")]
    is_draft = str(meta.get("draft", "false")).lower() == "true"

    return {
        "title": title,
        "content": html_body,
        "labels": labels,
        "is_draft": is_draft,
    }


def check_duplicate(service, title: str) -> bool:
    """같은 제목의 포스트가 이미 있는지 확인"""
    result = service.posts().search(blogId=BLOG_ID, q=title).execute()
    for item in result.get("items", []):
        if item["title"] == title:
            return True
    return False


def post_to_blogger(file_path: str):
    creds = get_credentials()
    service = build("blogger", "v3", credentials=creds)

    post_data = parse_post(file_path)

    # 중복 확인
    if check_duplicate(service, post_data["title"]):
        print(f"⚠️  이미 존재하는 포스트 건너뜀: {post_data['title']}")
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
