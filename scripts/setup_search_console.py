#!/usr/bin/env python3
"""
Search Console & 네이버 사이트맵 셋업 스크립트
- Google Search Console: 사이트맵 제출 (Indexing API 서비스계정 사용)
- 네이버 IndexNow: 최신 포스트 URL 제출

사용법:
  TARGET_BLOG_URL=https://www.allsweep.xyz python3 scripts/setup_search_console.py
  TARGET_BLOG_URL=https://aikeeper.allsweep.xyz python3 scripts/setup_search_console.py
"""
import os, sys, json, re, time
import urllib.request, urllib.parse

# ── 설정 ────────────────────────────────────────────────────────
BLOG_URL   = os.environ.get("TARGET_BLOG_URL", "https://www.allsweep.xyz").rstrip("/")
BLOG_ID    = os.environ.get("TARGET_BLOG_ID",  "8772490249452917821")

# 네이버 IndexNow 키 (사이트별로 다를 수 있음)
NAVER_INDEXNOW_KEY = os.environ.get("NAVER_INDEXNOW_KEY", "")

# Google Service Account (Indexing API용 — 이미 설정됨)
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")


# ── 1. Blogger atom feed에서 최신 URL 수집 ─────────────────────
def get_recent_post_urls(max_count: int = 20) -> list[str]:
    atom_url = f"{BLOG_URL}/feeds/posts/default?max-results={max_count}&alt=json"
    try:
        req = urllib.request.Request(atom_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        urls = []
        for entry in data.get("feed", {}).get("entry", []):
            for link in entry.get("link", []):
                if link.get("rel") == "alternate":
                    urls.append(link["href"])
                    break
        print(f"  포스트 URL {len(urls)}개 수집 완료")
        return urls
    except Exception as e:
        print(f"  atom feed 오류: {e}")
        return []


# ── 2. Google Indexing API 색인 요청 ────────────────────────────
def request_google_indexing(urls: list[str]) -> int:
    if not GOOGLE_SA_JSON:
        print("  Google SA JSON 없음 — 건너뜀")
        return 0

    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    try:
        import indexing_api as idx
        token = idx.get_indexing_token()
    except Exception as e:
        print(f"  Indexing API 토큰 오류: {e}")
        return 0

    count = 0
    for url in urls[:10]:  # 하루 최대 200개 — 10개만
        try:
            result = idx.request_indexing(url, token, "URL_UPDATED")
            if "error" not in result:
                print(f"  ✅ Google 색인 요청: {url[:60]}")
                count += 1
            else:
                print(f"  ⚠️ Google 색인 오류: {result.get('error',{}).get('message','')[:60]}")
        except Exception as e:
            print(f"  ⚠️ Google 색인 예외: {e}")
        time.sleep(0.5)

    return count


# ── 3. 네이버 IndexNow 제출 ─────────────────────────────────────
def submit_naver_indexnow(urls: list[str]) -> bool:
    if not NAVER_INDEXNOW_KEY:
        print("  NAVER_INDEXNOW_KEY 없음 — 네이버 IndexNow 건너뜀")
        return False

    host = BLOG_URL.replace("https://", "").replace("http://", "").split("/")[0]
    payload = {
        "host": host,
        "key": NAVER_INDEXNOW_KEY,
        "keyLocation": f"{BLOG_URL}/{NAVER_INDEXNOW_KEY}.txt",
        "urlList": urls[:100],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://searchadvisor.naver.com/indexnow",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            status = r.status
        print(f"  ✅ 네이버 IndexNow 제출: HTTP {status}, {len(urls[:100])}개 URL")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"  ⚠️ 네이버 IndexNow HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"  ⚠️ 네이버 IndexNow 오류: {e}")
        return False


# ── 4. Blogger sitemap URL 체크 ─────────────────────────────────
def check_sitemap_accessible() -> dict:
    results = {}
    sitemaps = [
        f"{BLOG_URL}/sitemap.xml",
        f"{BLOG_URL}/feeds/posts/default",
        f"{BLOG_URL}/atom.xml",
    ]
    for url in sitemaps:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Googlebot/2.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                size = len(r.read())
            results[url] = f"✅ 접근 가능 ({size:,} bytes)"
        except Exception as e:
            results[url] = f"❌ 오류: {e}"
    return results


# ── 5. Blogger 포스트 수 확인 ───────────────────────────────────
def check_blogger_post_count() -> int:
    token_data = urllib.parse.urlencode({
        "client_id":     os.environ.get("BLOGGER_CLIENT_ID", ""),
        "client_secret": os.environ.get("BLOGGER_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("BLOGGER_REFRESH_TOKEN", ""),
        "grant_type":    "refresh_token",
    }).encode()
    try:
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            token = json.loads(r.read()).get("access_token", "")

        api_url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}?fields=posts"
        req2 = urllib.request.Request(api_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req2, timeout=10) as r2:
            data = json.loads(r2.read())
        return data.get("posts", {}).get("totalItems", 0)
    except Exception as e:
        print(f"  포스트 수 조회 오류: {e}")
        return 0


# ── main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"🔍 Search Console 셋업 — {BLOG_URL}")
    print(f"{'='*55}\n")

    # 사이트맵 접근성 확인
    print("1️⃣  사이트맵 URL 체크")
    sitemap_results = check_sitemap_accessible()
    for url, status in sitemap_results.items():
        print(f"  {status}: {url}")

    # 포스트 수 확인
    print("\n2️⃣  블로그 포스트 현황")
    post_count = check_blogger_post_count()
    print(f"  총 포스트: {post_count}개")

    # 최신 URL 수집
    print("\n3️⃣  최신 포스트 URL 수집")
    urls = get_recent_post_urls(20)
    if urls:
        for u in urls[:5]:
            print(f"  - {u}")
        if len(urls) > 5:
            print(f"  ... 외 {len(urls)-5}개")

    # Google Indexing API
    print("\n4️⃣  Google 색인 요청")
    g_count = request_google_indexing(urls)
    print(f"  완료: {g_count}개 요청")

    # 네이버 IndexNow
    print("\n5️⃣  네이버 IndexNow 제출")
    submit_naver_indexnow(urls)

    print(f"\n{'='*55}")
    print("✅ 완료!")
    print(f"\n📋 다음 단계 (수동):")
    print(f"  1. Google Search Console 방문: https://search.google.com/search-console")
    print(f"  2. 사이트 추가: {BLOG_URL}")
    print(f"  3. 소유권 확인 (HTML 태그 방식 — Blogger 테마에 이미 있음)")
    print(f"  4. 사이트맵 제출: {BLOG_URL}/sitemap.xml")
    print(f"     또는 Atom feed: {BLOG_URL}/feeds/posts/default")
    print(f"\n  네이버 서치어드바이저: https://searchadvisor.naver.com")
    print(f"  사이트맵 제출 URL: {BLOG_URL}/feeds/posts/default")
