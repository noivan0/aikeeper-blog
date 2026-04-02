#!/usr/bin/env python3
"""
naver_indexing.py — 네이버 서치어드바이저 IndexNow 색인 요청 자동화

네이버 IndexNow 공식 엔드포인트:
  https://searchadvisor.naver.com/indexnow
  ?url=<인코딩된 포스트 URL>
  &key=<IndexNow 키>
  &keyLocation=<키 파일 URL>

키 파일: https://noivan0.github.io/aikeeper-blog/<key>.txt
  (gh-pages 브랜치에 배포)

사용법:
  python3 scripts/naver_indexing.py <post_url>      # 단건
  python3 scripts/naver_indexing.py --bulk           # atom.xml 전체 (최신 10개)
  python3 scripts/naver_indexing.py --bulk --all     # atom.xml 전체 (전부)
"""

import os, sys, re, time, urllib.request, urllib.parse

INDEXNOW_ENDPOINT  = "https://searchadvisor.naver.com/indexnow"
INDEXNOW_KEY       = os.environ.get("NAVER_INDEXNOW_KEY", "")
KEY_LOCATION_BASE  = "https://noivan0.github.io/aikeeper-blog"
BLOG_URL           = "https://aikeeper.allsweep.xyz"
ATOM_URL           = f"{BLOG_URL}/atom.xml"

# Blogger API (bulk 모드에서 전체 포스트 목록 가져오기)
BLOGGER_CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
BLOG_ID               = "3598676904202320050"


def get_blogger_token() -> str:
    import json, urllib.parse as up
    data = up.urlencode({
        "client_id":     BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def get_all_post_urls() -> list:
    """전체 포스트 URL 목록 (Blogger API → atom.xml fallback)"""
    urls = []

    # Blogger API 우선
    if BLOGGER_REFRESH_TOKEN:
        try:
            import json
            token = get_blogger_token()
            page_token = None
            while True:
                url = (f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts"
                       f"?maxResults=500&status=LIVE&fetchBodies=false")
                if page_token:
                    url += f"&pageToken={page_token}"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read())
                for p in data.get("items", []):
                    u = p.get("url", "")
                    if u:
                        urls.append(u)
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            return urls
        except Exception as e:
            print(f"  Blogger API 실패: {e}, atom.xml fallback")

    # atom.xml fallback
    req = urllib.request.Request(ATOM_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        xml = r.read().decode("utf-8", errors="ignore")
    pat = r"<link rel='alternate' type='text/html' href='(https://aikeeper\.allsweep\.xyz/\d{4}/[^']+)'"
    urls = re.findall(pat, xml)
    return urls


def request_indexnow(post_url: str, dry_run: bool = False) -> dict:
    """IndexNow 단건 색인 요청"""
    if not INDEXNOW_KEY:
        return {"status": "skip", "reason": "NAVER_INDEXNOW_KEY 없음"}

    key_location = f"{KEY_LOCATION_BASE}/{INDEXNOW_KEY}.txt"
    params = urllib.parse.urlencode({
        "url":         post_url,
        "key":         INDEXNOW_KEY,
        "keyLocation": key_location,
    })
    full_url = f"{INDEXNOW_ENDPOINT}?{params}"

    if dry_run:
        return {"status": "dry_run", "url": full_url}

    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.getcode()
        return {"status": "ok", "http": code, "url": post_url}
    except urllib.error.HTTPError as e:
        return {"status": "error", "http": e.code, "url": post_url, "reason": str(e)}
    except Exception as e:
        return {"status": "error", "url": post_url, "reason": str(e)}


def main():
    args = sys.argv[1:]
    dry_run   = "--dry-run" in args
    bulk_all  = "--all" in args
    bulk_mode = "--bulk" in args or bulk_all

    if not INDEXNOW_KEY:
        print("❌ NAVER_INDEXNOW_KEY 환경변수가 없습니다.")
        print("   GitHub Secret에 NAVER_INDEXNOW_KEY를 추가하세요.")
        sys.exit(1)

    if bulk_mode:
        print("📡 네이버 IndexNow 벌크 색인 요청...")
        urls = get_all_post_urls()
        if not bulk_all:
            urls = urls[:10]  # 기본: 최신 10개만
        print(f"  대상 URL: {len(urls)}개")

        ok, fail = 0, 0
        for i, url in enumerate(urls):
            result = request_indexnow(url, dry_run=dry_run)
            status = result.get("status")
            http   = result.get("http", "")
            if status == "ok" or (status == "dry_run"):
                ok += 1
                label = "DRY" if dry_run else "OK"
                print(f"  {label} [{http}]: {url[:70]}")
            else:
                fail += 1
                print(f"  FAIL [{http}] {result.get('reason','')}: {url[:70]}")
            # 요청 간 딜레이 (rate limit 방지)
            if i < len(urls) - 1:
                time.sleep(0.5)

        print(f"\n결과: 성공 {ok}개 / 실패 {fail}개")

    else:
        # 단건 모드
        target_urls = [a for a in args if a.startswith("http") or a.startswith("https")]
        if not target_urls:
            print("Usage: python3 naver_indexing.py <url> [--dry-run]")
            print("       python3 naver_indexing.py --bulk [--all] [--dry-run]")
            sys.exit(1)

        for url in target_urls:
            result = request_indexnow(url, dry_run=dry_run)
            print(f"  {result}")


if __name__ == "__main__":
    main()
