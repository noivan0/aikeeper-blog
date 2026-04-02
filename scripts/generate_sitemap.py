#!/usr/bin/env python3
"""
generate_sitemap.py — 네이버 서치어드바이저 sitemap.xml 생성기

네이버 공식 기준:
- urlset xmlns (필수)
- <loc> 모든 포스트 URL (aikeeper.allsweep.xyz 도메인)
- <lastmod> ISO8601 +09:00
- <changefreq> weekly
- <priority> 0.8
- 용량 10MB 미만, URL 50,000개 미만

출력: sitemap.xml → gh-pages 브랜치 배포
서빙 URL: https://noivan0.github.io/aikeeper-blog/sitemap.xml
"""

import os, re, sys, datetime, urllib.request, xml.etree.ElementTree as ET

BLOG_URL = "https://aikeeper.allsweep.xyz"
ATOM_URL = f"{BLOG_URL}/atom.xml"

# Blogger API
BLOGGER_CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
BLOG_ID               = "3598676904202320050"


def get_access_token() -> str:
    import json, urllib.parse
    data = urllib.parse.urlencode({
        "client_id":     BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def fetch_all_posts_api(token: str) -> list:
    """Blogger API — 전체 포스트 (페이지네이션)"""
    import json
    posts = []
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
            posts.append({
                "url":       p.get("url", ""),
                "published": p.get("published", ""),
                "updated":   p.get("updated", ""),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return posts


def fetch_from_atom() -> list:
    """fallback: atom.xml 파싱 (최신 25개만)"""
    req = urllib.request.Request(ATOM_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        xml = r.read().decode("utf-8", errors="ignore")
    posts = []
    for e in re.findall(r'<entry>(.*?)</entry>', xml, re.S):
        link_m = re.search(r"<link[^>]+rel=['\"]alternate['\"][^>]+href=['\"]([^'\"]+)['\"]", e)
        pub_m  = re.search(r"<published>(.*?)</published>", e, re.S)
        upd_m  = re.search(r"<updated>(.*?)</updated>", e, re.S)
        if link_m:
            posts.append({
                "url":       link_m.group(1).strip(),
                "published": pub_m.group(1).strip() if pub_m else "",
                "updated":   upd_m.group(1).strip() if upd_m else "",
            })
    return posts


def to_lastmod(iso_str: str) -> str:
    """ISO8601 → 네이버 sitemap lastmod (YYYY-MM-DDTHH:MM:SS+09:00)"""
    if not iso_str:
        return datetime.date.today().isoformat() + "T00:00:00+09:00"
    try:
        m = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2}|Z)?', iso_str)
        if not m:
            return iso_str[:10] + "T00:00:00+09:00"
        date_s, time_s, tz = m.group(1), m.group(2), m.group(3) or "+00:00"
        dt = datetime.datetime.fromisoformat(f"{date_s}T{time_s}")
        if tz and tz != "Z":
            sign = 1 if tz[0] == "+" else -1
            h, mn = int(tz[1:3]), int(tz[4:6])
            offset = datetime.timedelta(hours=h, minutes=mn) * sign
        else:
            offset = datetime.timedelta(0)
        kst = dt - offset + datetime.timedelta(hours=9)
        return kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except Exception:
        return datetime.date.today().isoformat() + "T00:00:00+09:00"


def build_sitemap(posts: list) -> str:
    now_kst = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    url_entries = ""
    for p in posts:
        url = p["url"]
        if not url.startswith("https://aikeeper.allsweep.xyz"):
            continue  # 도메인 검증 (네이버 요구사항)
        lastmod = to_lastmod(p.get("updated") or p.get("published"))
        url_entries += f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_entries}</urlset>"""


def main():
    print("sitemap.xml 생성 시작...")
    posts = []

    if BLOGGER_REFRESH_TOKEN:
        try:
            token = get_access_token()
            posts = fetch_all_posts_api(token)
            print(f"  API: {len(posts)}개 포스트")
        except Exception as e:
            print(f"  API 실패: {e}")

    if not posts:
        print("  atom.xml fallback...")
        posts = fetch_from_atom()
        print(f"  atom.xml: {len(posts)}개 포스트")

    if not posts:
        print("포스트 없음")
        sys.exit(1)

    sitemap = build_sitemap(posts)
    size_mb = len(sitemap.encode("utf-8")) / 1024 / 1024
    print(f"  크기: {size_mb:.3f}MB | URL 수: {len(posts)}개")

    out = sys.argv[1] if len(sys.argv) > 1 else "sitemap.xml"
    with open(out, "w", encoding="utf-8") as f:
        f.write(sitemap)

    try:
        ET.fromstring(sitemap)
        print(f"  XML 유효성 OK → {out}")
    except ET.ParseError as e:
        print(f"  XML 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
