#!/usr/bin/env python3
"""
generate_rss.py — 네이버 서치어드바이저 RSS 2.0 피드 생성기

네이버 공식 가이드 기준:
- RSS 2.0 형식 (<?xml version="1.0"?> + <rss version="2.0">)
- item마다 본문 전체 포함 (<description> CDATA)
- pubDate: RFC 822 형식 (Thu, 02 Apr 2026 15:00:00 +0900)
- guid = 포스트 URL (isPermaLink="true")
- 도메인: 소유확인된 사이트(aikeeper.allsweep.xyz)와 동일해야 함
- 용량: 10MB 미만

배포 URL: https://noivan0.github.io/aikeeper-blog/rss.xml
"""

import os, re, sys, datetime, xml.etree.ElementTree as ET, urllib.request, html as html_lib

BLOG_URL       = "https://aikeeper.allsweep.xyz"
RSS_SERVE_URL  = "https://noivan0.github.io/aikeeper-blog/rss.xml"
BLOG_TITLE     = "AI키퍼"
BLOG_DESC      = "AI트렌드, ChatGPT, Claude, Gemini 등 생성형 AI 최신 소식을 한국어로 정리합니다."
ATOM_URL       = f"{BLOG_URL}/atom.xml"
MAX_ITEMS      = 20  # 본문 전체 포함이므로 최신 20개

BLOGGER_CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
BLOGGER_CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
BLOGGER_REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")
BLOG_ID               = os.environ.get("ALLSWEEP_BLOG_ID", "3598676904202320050")


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


def fetch_posts_via_api(token: str) -> list:
    import json
    url = (f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts"
           f"?maxResults={MAX_ITEMS}&status=LIVE&fetchBodies=true")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data.get("items", [])


def to_rfc822(iso_str: str) -> str:
    """ISO8601 → RFC 822 (KST)"""
    try:
        m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2}|Z)?', iso_str)
        if not m:
            raise ValueError
        dt_str, tz = m.group(1), m.group(2) or "+00:00"
        dt = datetime.datetime.fromisoformat(dt_str)
        if tz and tz != "Z":
            sign = 1 if tz[0] == "+" else -1
            h, mn = int(tz[1:3]), int(tz[4:6])
            offset = datetime.timedelta(hours=h, minutes=mn) * sign
        else:
            offset = datetime.timedelta(0)
        kst = dt - offset + datetime.timedelta(hours=9)
        return kst.strftime("%a, %d %b %Y %H:%M:%S +0900")
    except Exception:
        return datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")


def clean_html_for_rss(html: str) -> str:
    """본문 HTML 정제 — script/style/광고 제거, 본문 유지"""
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.S)
    html = re.sub(r'<ins[^>]*>.*?</ins>',       '', html, flags=re.S)
    html = re.sub(r'<meta[^>]+>',               '', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def build_rss(posts: list) -> str:
    now_rfc = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%a, %d %b %Y %H:%M:%S +0900")

    items_xml = ""
    for p in posts:
        title   = p.get("title", "")
        url     = p.get("url", "")
        pub_iso = p.get("published", "")
        content = clean_html_for_rss(p.get("content", ""))
        pub_rfc = to_rfc822(pub_iso) if pub_iso else now_rfc

        items_xml += f"""
  <item>
    <title><![CDATA[{title}]]></title>
    <link>{url}</link>
    <description><![CDATA[{content}]]></description>
    <pubDate>{pub_rfc}</pubDate>
    <guid isPermaLink="true">{url}</guid>
  </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{BLOG_TITLE}</title>
    <link>{BLOG_URL}/</link>
    <description>{BLOG_DESC}</description>
    <language>ko</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href="{RSS_SERVE_URL}" rel="self" type="application/rss+xml"/>
{items_xml}
  </channel>
</rss>"""


def main():
    print("RSS 2.0 생성 시작...")
    posts = []
    if BLOGGER_REFRESH_TOKEN:
        try:
            token = get_access_token()
            api_posts = fetch_posts_via_api(token)
            for p in api_posts:
                posts.append({
                    "title":     p.get("title", ""),
                    "url":       p.get("url", ""),
                    "published": p.get("published", ""),
                    "content":   p.get("content", ""),
                })
            print(f"  API: {len(posts)}개 로드")
        except Exception as e:
            print(f"  API 실패: {e}")

    if not posts:
        print("  atom.xml fallback...")
        req = urllib.request.Request(ATOM_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            xml = r.read().decode("utf-8", errors="ignore")
        for e in re.findall(r'<entry>(.*?)</entry>', xml, re.S)[:MAX_ITEMS]:
            t = re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
            l = re.search(r"<link[^>]+rel=['\"]alternate['\"][^>]+href=['\"]([^'\"]+)['\"]", e)
            p = re.search(r"<published>(.*?)</published>", e, re.S)
            c = re.search(r"<content[^>]*>(.*?)</content>", e, re.S)
            if t and l:
                posts.append({
                    "title":     html_lib.unescape(t.group(1).strip()),
                    "url":       l.group(1).strip(),
                    "published": p.group(1).strip() if p else "",
                    "content":   html_lib.unescape(c.group(1).strip()) if c else "",
                })
        print(f"  atom.xml: {len(posts)}개 로드")

    if not posts:
        print("포스트 없음")
        sys.exit(1)

    rss_xml = build_rss(posts)
    size_mb = len(rss_xml.encode("utf-8")) / 1024 / 1024
    if size_mb >= 10:
        posts = posts[:10]
        rss_xml = build_rss(posts)
        size_mb = len(rss_xml.encode("utf-8")) / 1024 / 1024

    out_path = sys.argv[1] if len(sys.argv) > 1 else "rss.xml"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rss_xml)

    try:
        ET.fromstring(rss_xml)
        print(f"  XML 유효성 OK | {len(posts)}개 | {size_mb:.2f}MB → {out_path}")
    except ET.ParseError as e:
        print(f"  XML 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
