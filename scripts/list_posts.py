#!/usr/bin/env python3
"""
AI키퍼 블로그 포스트 목록 확인
"""
import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BLOG_ID = "3598676904202320050"


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


def list_posts(status="live", max_results=20):
    creds = get_credentials()
    service = build("blogger", "v3", credentials=creds)

    result = service.posts().list(
        blogId=BLOG_ID,
        maxResults=max_results,
        status=status,
        orderBy="published",
        fetchBodies=False
    ).execute()

    posts = result.get("items", [])
    print(f"\n📋 AI키퍼 블로그 포스트 ({status}) — 총 {len(posts)}개\n")
    print(f"{'No':<4} {'발행일':<12} {'제목':<45} {'라벨'}")
    print("-" * 90)

    for i, post in enumerate(posts, 1):
        date = post["published"][:10]
        title = post["title"][:43] + ".." if len(post["title"]) > 45 else post["title"]
        labels = ", ".join(post.get("labels", []))
        print(f"{i:<4} {date:<12} {title:<45} {labels}")

    print()
    return posts


if __name__ == "__main__":
    import sys
    status = sys.argv[1] if len(sys.argv) > 1 else "live"
    list_posts(status)
