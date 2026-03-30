#!/usr/bin/env python3
"""
Google Search Console — Sitemap 제출 + 포스트 URL 색인 요청
실행: python3 scripts/submit_sitemap.py
"""
import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BLOG_URL = "https://aikeeper.allsweep.xyz"

# Search Console은 별도 scope 필요
SCOPES = [
    "https://www.googleapis.com/auth/blogger",
    "https://www.googleapis.com/auth/webmasters",
]

SITEMAPS = [
    f"{BLOG_URL}/sitemap.xml",
    f"{BLOG_URL}/atom.xml",
    f"{BLOG_URL}/feeds/posts/default",
]

def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def submit_sitemaps(token: str):
    """Search Console API로 sitemap 제출"""
    site_url = f"sc-domain:{BLOG_URL.replace('https://','').replace('http://','')}"
    # URL prefix 방식도 시도
    site_urls = [
        BLOG_URL + "/",
        f"sc-domain:aikeeper.allsweep.xyz",
    ]

    print("=== Sitemap 제출 ===")
    for sitemap_url in SITEMAPS:
        for site in site_urls[:1]:  # 첫 번째만 시도
            endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(site, safe='')}/sitemaps/{requests.utils.quote(sitemap_url, safe='')}"
            r = requests.put(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
            )
            print(f"  [{r.status_code}] {sitemap_url}")
            if r.status_code not in (200, 204):
                print(f"    응답: {r.text[:100]}")


def get_recent_posts(token: str) -> list:
    """최근 포스트 URL 목록 조회"""
    r = requests.get(
        "https://blogger.googleapis.com/v3/blogs/3598676904202320050/posts?maxResults=10&fields=items(url)",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 200:
        return [p["url"] for p in r.json().get("items", [])]
    return []


def request_indexing(token: str, urls: list):
    """Google Indexing API로 URL 색인 요청"""
    print("\n=== URL 색인 요청 ===")
    # Indexing API는 별도 서비스 계정 필요 — 안내만
    print("  ℹ️  Indexing API는 서비스 계정 키 필요 (Search Console 수동 제출 권장)")
    print("  수동 제출 URL:")
    for url in urls[:5]:
        print(f"    {url}")


if __name__ == "__main__":
    try:
        creds = get_credentials()
        print(f"✅ 토큰 발급 성공")
        submit_sitemaps(creds.token)
        urls = get_recent_posts(creds.token)
        request_indexing(creds.token, urls)
        print("\n✅ 완료")
        print(f"\n📌 서치 콘솔에서 직접 확인:")
        print(f"   https://search.google.com/search-console/sitemaps?resource_id={BLOG_URL}/")
    except Exception as e:
        print(f"❌ 오류: {e}")
