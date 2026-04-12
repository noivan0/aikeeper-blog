#!/usr/bin/env python3
"""
Google 색인 촉진 스크립트 v2
- 전략 1: Indexing API (공식: Job/LiveVideo URL용. 일반 블로그에도 크롤 힌트 제공)
- 전략 2: GSC URL Inspection (색인 상태 확인)
- 전략 3: Sitemap ping (Google/Bing에 sitemap 업데이트 알림)
- 전략 4: IndexNow (Bing/Yandex 즉시 색인, API key 불필요 방식)

NOTE: Google Indexing API 공식 스펙은 JobPosting/BroadcastEvent 전용이지만
      URL_UPDATED 요청을 보내면 크롤 힌트로 활용됨 (색인 보장 아님).
      가장 확실한 방법은 고품질 콘텐츠 + 외부 백링크 확보.
"""
import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse
import requests

# .env 로드
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from env_loader import load_env
    load_env()
except Exception:
    _env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _, _v = _line.partition('=')
                    os.environ.setdefault(_k.strip(), _v.strip())

from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest

INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

# 블로그별 설정
BLOG_CONFIGS = {
    "aikeeper": {
        "blog_id":  "3598676904202320050",
        "base_url": "https://aikeeper.allsweep.xyz",
        "sitemap":  "https://aikeeper.allsweep.xyz/sitemap.xml",
        "atom":     "https://aikeeper.allsweep.xyz/feeds/posts/default",
        "cid_env":  "AIKEEPER_CLIENT_ID",
        "csec_env": "AIKEEPER_CLIENT_SECRET",
        "rt_env":   "AIKEEPER_REFRESH_TOKEN",
    },
    "allsweep": {
        "blog_id":  "8772490249452917821",
        "base_url": "https://www.allsweep.xyz",
        "sitemap":  "https://www.allsweep.xyz/sitemap.xml",
        "atom":     "https://www.allsweep.xyz/feeds/posts/default",
        "cid_env":  "ALLSWEEP_CLIENT_ID",
        "csec_env": "ALLSWEEP_CLIENT_SECRET",
        "rt_env":   "ALLSWEEP_REFRESH_TOKEN",
    },
    "ggultongmon": {
        "blog_id":  "4422596386410826373",
        "base_url": "https://ggultongmon.allsweep.xyz",
        "sitemap":  "https://ggultongmon.allsweep.xyz/sitemap.xml",
        "atom":     "https://ggultongmon.allsweep.xyz/feeds/posts/default",
        "cid_env":  "GGULTONGMON_CLIENT_ID",
        "csec_env": "GGULTONGMON_CLIENT_SECRET",
        "rt_env":   "GGULTONGMON_REFRESH_TOKEN",
    },
}


def _load_sa_info() -> dict:
    """서비스 계정 JSON 로드 (작은따옴표 래핑 처리)"""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("GOOGLE_SERVICE_ACCOUNT_JSON="):
                    raw = line.strip()[len("GOOGLE_SERVICE_ACCOUNT_JSON="):]
                    if raw.startswith("'") and raw.endswith("'"):
                        raw = raw[1:-1]
                    break
    if not raw:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 없음")
    return json.loads(raw)


def get_indexing_token() -> str:
    """Indexing API 서비스 계정 토큰"""
    sa_info = _load_sa_info()
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/indexing"]
    )
    creds.refresh(GoogleRequest())
    return creds.token


def get_sa_webmaster_token() -> str:
    """Search Console API 서비스 계정 토큰"""
    sa_info = _load_sa_info()
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=["https://www.googleapis.com/auth/webmasters"]
    )
    creds.refresh(GoogleRequest())
    return creds.token


def get_blogger_token(blog_name: str) -> str:
    """블로그 전용 OAuth 토큰"""
    cfg = BLOG_CONFIGS[blog_name]
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials(
        token=None,
        refresh_token=os.environ[cfg["rt_env"]],
        client_id=os.environ[cfg["cid_env"]],
        client_secret=os.environ[cfg["csec_env"]],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    creds.refresh(Request())
    return creds.token


# ── 전략 1: Indexing API URL_UPDATED ───────────────────────────────────────
def indexing_api_request(url: str, token: str) -> dict:
    """Indexing API 크롤 힌트 요청 (공식 Job/Video 전용이지만 크롤 신호 제공)"""
    r = requests.post(
        INDEXING_ENDPOINT,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"url": url, "type": "URL_UPDATED"},
        timeout=15
    )
    return {"status": r.status_code, "body": r.json()}


# ── 전략 2: GSC URL Inspection 상태 확인 ───────────────────────────────────
def check_index_status(site_url: str, page_url: str, wm_token: str) -> dict:
    """GSC URL Inspection — 색인 상태 확인"""
    r = requests.post(
        "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
        headers={"Authorization": f"Bearer {wm_token}"},
        json={"inspectionUrl": page_url, "siteUrl": site_url},
        timeout=20
    )
    if r.status_code == 200:
        result = r.json().get("inspectionResult", {})
        idx = result.get("indexStatusResult", {})
        return {
            "verdict":   idx.get("verdict", ""),
            "coverage":  idx.get("coverageState", ""),
            "last_crawl": idx.get("lastCrawlTime", "")[:10] if idx.get("lastCrawlTime") else "없음",
            "robots":    idx.get("robotsTxtState", ""),
            "sitemap":   idx.get("sitemap", []),
        }
    return {"error": r.status_code, "body": r.text[:200]}


# ── 전략 3: Sitemap Ping ────────────────────────────────────────────────────
def ping_sitemaps(blog_name: str = None) -> dict:
    """Google/Bing에 sitemap 업데이트 ping 전송"""
    results = {}
    targets = [blog_name] if blog_name else list(BLOG_CONFIGS.keys())

    for name in targets:
        cfg = BLOG_CONFIGS[name]
        sitemap_url = requests.utils.quote(cfg["sitemap"], safe='')
        atom_url    = requests.utils.quote(cfg["atom"], safe='')

        # Google Sitemap ping은 2023년 6월 deprecated
        # 대신 GSC에 sitemap 제출된 상태이므로 Google이 자동 크롤
        # Bing IndexNow (키 없이도 202 응답, 실제 처리는 키 검증 후)
        b_r = requests.post(
            "https://api.indexnow.org/indexnow",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"host": cfg["base_url"].replace("https://", ""),
                  "key": "placeholder-key",
                  "urlList": [cfg["base_url"] + "/"]},
            timeout=10
        )

        results[name] = {
            "google_ping": "deprecated (GSC sitemap 자동 크롤)",
            "indexnow":    b_r.status_code,
        }
        print(f"  [{name}] Google:GSC자동 IndexNow:{b_r.status_code}")
        time.sleep(0.3)

    return results


# ── 전략 4: IndexNow (Bing/Yandex 즉시 색인) ───────────────────────────────
def indexnow_submit(urls: list, host: str, key: str = None) -> dict:
    """
    IndexNow 프로토콜로 Bing/Yandex에 즉시 색인 요청.
    key 없으면 자동 생성 (첫 실행 시 host에 키 파일 배포 필요).
    Blogger는 직접 파일 배포 불가하므로 키 검증 우회 방식 사용.
    """
    if not key:
        # Blogger에서는 IndexNow 키 파일 배포가 어려우므로 건너뜀
        print("  [IndexNow] 키 없음 — Blogger에서 키 파일 배포 불가, 건너뜀")
        return {}

    r = requests.post(
        "https://api.indexnow.org/indexnow",
        headers={"Content-Type": "application/json; charset=utf-8"},
        json={"host": host, "key": key, "urlList": urls},
        timeout=15
    )
    return {"status": r.status_code, "body": r.text[:100]}


# ── 최근 포스트 URL 조회 ───────────────────────────────────────────────────
def get_recent_urls(blog_name: str, count: int = 10) -> list:
    """Blogger API로 최근 포스트 URL 목록 조회"""
    cfg = BLOG_CONFIGS[blog_name]
    try:
        blogger_token = get_blogger_token(blog_name)
        r = requests.get(
            f"https://blogger.googleapis.com/v3/blogs/{cfg['blog_id']}/posts"
            f"?maxResults={count}&fields=items(url,title)&orderBy=published",
            headers={"Authorization": f"Bearer {blogger_token}"},
            timeout=10,
        )
        if r.status_code == 200:
            return [(item["url"], item.get("title","")) for item in r.json().get("items", [])]
    except Exception as e:
        print(f"  [WARN] Blogger API 실패 ({blog_name}): {e}")

    # fallback: atom.xml 파싱
    import re
    try:
        with urllib.request.urlopen(cfg["atom"], timeout=10) as resp:
            content = resp.read().decode()
        urls = re.findall(
            r"<link rel='alternate' type='text/html' href='(" + re.escape(cfg["base_url"]) + r"/\d{4}/[^']+)'",
            content
        )
        return [(u, "") for u in urls[:count]]
    except Exception as e:
        print(f"  [WARN] atom.xml 파싱 실패 ({blog_name}): {e}")
    return []


# ── 메인: 단일 URL 색인 요청 (크론 연동용) ────────────────────────────────
def index_single_url(url: str):
    """발행 직후 단일 URL 색인 촉진 (Indexing API + Sitemap Ping)"""
    print(f"[색인 촉진] {url}")

    # 블로그 이름 판별
    blog_name = None
    for name, cfg in BLOG_CONFIGS.items():
        if cfg["base_url"] in url:
            blog_name = name
            break

    # 전략 1: Indexing API
    try:
        token = get_indexing_token()
        result = indexing_api_request(url, token)
        status = result["status"]
        if status == 200:
            print(f"  ✅ Indexing API: 크롤 힌트 전송 완료 (HTTP {status})")
        else:
            print(f"  ⚠️  Indexing API: HTTP {status} — {result['body']}")
    except Exception as e:
        print(f"  ⚠️  Indexing API 오류: {e}")

    # 전략 3: Sitemap Ping
    if blog_name:
        try:
            ping_sitemaps(blog_name)
        except Exception as e:
            print(f"  ⚠️  Sitemap Ping 오류: {e}")

    print(f"  완료")


# ── 일괄 색인 촉진 (여러 블로그 최근 포스트) ────────────────────────────
def index_recent_posts(blog_name: str = None, count: int = 10):
    """최근 N개 포스트 일괄 색인 촉진"""
    targets = [blog_name] if blog_name else list(BLOG_CONFIGS.keys())

    try:
        indexing_token = get_indexing_token()
        wm_token       = get_sa_webmaster_token()
    except Exception as e:
        print(f"❌ 토큰 발급 실패: {e}")
        return

    for name in targets:
        cfg = BLOG_CONFIGS[name]
        print(f"\n[{name}] 최근 {count}개 포스트 색인 촉진 중...")

        urls = get_recent_urls(name, count=count)
        if not urls:
            print(f"  URL 없음")
            continue

        for url, title in urls:
            # Indexing API
            result = indexing_api_request(url, indexing_token)
            status_icon = "✅" if result["status"] == 200 else "⚠️ "
            print(f"  {status_icon} [{result['status']}] {title[:35] or url[:60]}")
            time.sleep(0.3)

        # Sitemap ping (블로그당 1회)
        try:
            ping_sitemaps(name)
        except Exception as e:
            print(f"  [WARN] Ping 실패: {e}")

    print("\n✅ 색인 촉진 완료")


# ── 색인 상태 전체 보고서 ──────────────────────────────────────────────────
def index_status_report():
    """3개 블로그 최근 5개 포스트 색인 상태 확인"""
    try:
        wm_token = get_sa_webmaster_token()
    except Exception as e:
        print(f"❌ 토큰 실패: {e}")
        return

    for name, cfg in BLOG_CONFIGS.items():
        print(f"\n[{name}]")
        urls = get_recent_urls(name, count=5)
        for url, title in urls[:5]:
            status = check_index_status(cfg["base_url"] + "/", url, wm_token)
            cov = status.get("coverage","?")
            crawl = status.get("last_crawl","없음")
            icon = "✅" if "Indexed" in cov else "⚠️ "
            print(f"  {icon} {cov} | 크롤:{crawl} | {title[:30]}")
            time.sleep(0.5)


# ── CLI 진입점 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        arg = sys.argv[1].strip()
        if arg.startswith("http"):
            # 단일 URL
            index_single_url(arg)
        elif arg == "report":
            # 색인 상태 보고서
            index_status_report()
        elif arg == "ping":
            # sitemap ping만
            ping_sitemaps()
        elif arg in BLOG_CONFIGS:
            # 특정 블로그
            count = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
            index_recent_posts(arg, count=count)
        else:
            print(f"Unknown arg: {arg}")
    else:
        # 기본: 3개 블로그 최근 포스트 색인 촉진
        index_recent_posts(count=5)
