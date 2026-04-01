#!/usr/bin/env python3
"""
Google Indexing API — 포스트 URL 즉시 색인 요청
서비스 계정 기반 (GOOGLE_SERVICE_ACCOUNT_JSON 환경변수)
"""
import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse

# google-auth 라이브러리
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest

INDEXING_SCOPE = "https://www.googleapis.com/auth/indexing"
INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

BLOG_URL = "https://aikeeper.allsweep.xyz"
BLOG_ID  = "3598676904202320050"


def get_indexing_token() -> str:
    """서비스 계정으로 Indexing API access token 발급"""
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 환경변수 없음")

    sa_info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=[INDEXING_SCOPE]
    )
    creds.refresh(GoogleRequest())
    return creds.token


def request_indexing(url: str, token: str, notification_type: str = "URL_UPDATED") -> dict:
    """단일 URL 색인 요청"""
    payload = json.dumps({
        "url": url,
        "type": notification_type,
    }).encode()

    req = urllib.request.Request(
        INDEXING_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": e.code, "message": body[:200]}


def get_recent_post_urls(token_blogger: str, count: int = 5) -> list:
    """Blogger API로 최근 포스트 URL 목록 조회"""
    import requests as _req
    r = _req.get(
        f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts"
        f"?maxResults={count}&fields=items(url,title)&orderBy=published",
        headers={"Authorization": f"Bearer {token_blogger}"},
        timeout=10,
    )
    if r.status_code == 200:
        return [(item["url"], item.get("title","")) for item in r.json().get("items", [])]
    return []


def index_url_from_args():
    """CLI: python indexing_api.py <url>"""
    if len(sys.argv) < 2:
        print("Usage: python indexing_api.py <post_url>")
        sys.exit(1)

    url = sys.argv[1].strip()
    if not url.startswith("http"):
        print(f"❌ 유효하지 않은 URL: {url}")
        sys.exit(1)

    print(f"🔍 Indexing API 색인 요청: {url}")
    try:
        token = get_indexing_token()
        result = request_indexing(url, token)

        if "error" in result:
            print(f"  ⚠️  색인 요청 실패 [{result['error']}]: {result.get('message','')}")
            sys.exit(1)
        else:
            notify = result.get("urlNotificationMetadata", {}).get("latestUpdate", {})
            print(f"  ✅ 색인 요청 완료!")
            print(f"     URL: {notify.get('url', url)}")
            print(f"     Type: {notify.get('type', 'URL_UPDATED')}")
            print(f"     시각: {notify.get('notifyTime', datetime.datetime.utcnow().isoformat())}")
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        sys.exit(1)


def index_recent_posts(count: int = 3):
    """최근 N개 포스트 일괄 색인 요청 (배치 실행용)"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    print(f"📡 최근 포스트 {count}개 색인 요청 중...")

    # Blogger OAuth token
    try:
        blogger_creds = Credentials(
            token=None,
            refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
            client_id=os.environ["BLOGGER_CLIENT_ID"],
            client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/blogger"],
        )
        blogger_creds.refresh(Request())
        blogger_token = blogger_creds.token
    except Exception as e:
        print(f"  ⚠️  Blogger 토큰 실패: {e}")
        blogger_token = None

    # Indexing API token
    try:
        indexing_token = get_indexing_token()
    except Exception as e:
        print(f"  ❌ Indexing API 토큰 실패: {e}")
        return

    urls = []
    if blogger_token:
        urls = get_recent_post_urls(blogger_token, count=count)

    if not urls:
        # fallback: sitemap.xml에서 URL 파싱
        print("  → Blogger API 실패, sitemap 파싱 시도")
        try:
            with urllib.request.urlopen(f"{BLOG_URL}/sitemap.xml", timeout=10) as r:
                content = r.read().decode()
            import re
            urls_raw = re.findall(r'<loc>(https://[^<]+)</loc>', content)
            urls = [(u, "") for u in urls_raw[:count]]
        except Exception:
            pass

    if not urls:
        print("  ⚠️  색인할 URL 없음")
        return

    for url, title in urls:
        result = request_indexing(url, indexing_token)
        if "error" in result:
            print(f"  ⚠️  [{result['error']}] {url[:60]}")
        else:
            print(f"  ✅ {title[:40] or url[:60]}")
        time.sleep(0.5)  # API quota 보호

    print(f"  완료: {len(urls)}개 색인 요청")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1].startswith("http"):
        index_url_from_args()
    else:
        # 인자 없으면 최근 3개 일괄 처리
        index_recent_posts(count=3)
