#!/usr/bin/env python3
"""
update_existing_posts.py — 기존 포스트 전체 SEO 업데이트

적용 내용:
1. datePublished/Modified → ISO8601 완전형식 (날짜+시간+KST)
2. author @type Person (AI키퍼 편집팀)
3. image → 다중 비율 배열 [1:1, 4:3, 16:9]
4. thumbnailUrl 추가
5. speakable cssSelector 추가
6. mainEntityOfPage @id → 포스트 자신의 URL
7. url 필드 추가
8. 네이버 요약박스 (.post-summary) 추가 (없는 경우)
9. 기존 구버전 custom JSON-LD 제거 후 신버전으로 교체
"""

import os, re, sys, json, time, datetime, urllib.request, urllib.parse, gzip

BLOG_ID = "3598676904202320050"
BLOG_URL = "https://aikeeper.allsweep.xyz"
BLOG_NAME = "AI키퍼"

CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")


def get_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def blogger_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"https://blogger.googleapis.com/v3{path}",
        headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def blogger_patch(path: str, token: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    compressed = gzip.compress(data)
    req = urllib.request.Request(
        f"https://blogger.googleapis.com/v3{path}",
        data=compressed,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Content-Encoding": "gzip",
            "Accept-Encoding": "gzip",
        },
        method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def to_kst_iso(iso_str: str) -> str:
    """ISO8601 → KST 완전형식"""
    if not iso_str:
        return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    m = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2}|Z)?', iso_str)
    if not m:
        return iso_str
    date_s, time_s, tz = m.group(1), m.group(2), m.group(3) or "+00:00"
    dt = datetime.datetime.fromisoformat(f"{date_s}T{time_s}")
    if tz == "Z":
        offset = datetime.timedelta(0)
    else:
        sign = 1 if tz[0] == "+" else -1
        h, mn = int(tz[1:3]), int(tz[4:6])
        offset = datetime.timedelta(hours=h, minutes=mn) * sign
    kst = dt - offset + datetime.timedelta(hours=9)
    return kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def build_new_blogposting(old_jld: dict, post_url: str, pub_iso: str) -> dict:
    """기존 JSON-LD에서 필요한 값 추출 → 신버전 BlogPosting 생성"""
    pub_kst = to_kst_iso(pub_iso)
    headline = old_jld.get("headline", "")
    description = old_jld.get("description", "")
    keywords = old_jld.get("keywords", "")
    word_count = old_jld.get("wordCount", 0)
    time_req = old_jld.get("timeRequired", "")

    # 이미지 URL 추출 (기존 단일 or 배열)
    img = old_jld.get("image") or old_jld.get("thumbnailUrl", "")
    if isinstance(img, dict):
        img_url = img.get("url", "")
    elif isinstance(img, list) and img:
        img_url = img[0].get("url", "") if isinstance(img[0], dict) else ""
    else:
        img_url = str(img) if img else ""

    new_jld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": headline[:110],
        "description": description[:300],
        "keywords": keywords,
        "datePublished": pub_kst,
        "dateModified": pub_kst,
        "author": {
            "@type": "Person",
            "name": "AI키퍼 편집팀",
            "url": BLOG_URL
        },
        "publisher": {
            "@type": "Organization",
            "name": BLOG_NAME,
            "url": BLOG_URL,
            "logo": {"@type": "ImageObject", "url": f"{BLOG_URL}/favicon.ico"}
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": post_url},
        "url": post_url,
        "inLanguage": "ko-KR",
        "articleSection": "AI 기술 블로그",
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": ["h1", "h2", ".post-summary"]
        },
    }
    if img_url:
        new_jld["image"] = [
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 1200},
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 900},
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 630},
        ]
        new_jld["thumbnailUrl"] = img_url
    if word_count:
        new_jld["wordCount"] = word_count
    if time_req:
        new_jld["timeRequired"] = time_req
    return new_jld


def update_post_html(html: str, post_url: str, pub_iso: str) -> tuple[str, bool]:
    """포스트 HTML에서 구버전 JSON-LD 제거 → 신버전으로 교체 + 요약박스 추가"""
    changed = False

    # ── 1. 기존 custom BlogPosting JSON-LD 찾기 ──
    # Blogger 테마 삽입 JSON-LD(lh3.googleusercontent 이미지 등)는 건드리지 않음
    # 우리가 삽입한 JSON-LD만 대상: headline 필드가 있는 블록
    jld_pattern = re.compile(
        r'<script type=["\']application/ld\+json["\']>\s*(\{.*?\})\s*</script>',
        re.S
    )

    old_jld_block = None
    old_jld_data = None
    new_html = html

    for m in jld_pattern.finditer(html):
        try:
            data = json.loads(m.group(1))
            if data.get("@type") == "BlogPosting" and "headline" in data:
                # 우리가 삽입한 BlogPosting (headline 있고 publisher.name == BLOG_NAME)
                pub = data.get("publisher", {})
                if pub.get("name") == BLOG_NAME or pub.get("url", "").startswith(BLOG_URL):
                    old_jld_block = m.group(0)
                    old_jld_data = data
                    break
        except Exception:
            continue

    if old_jld_block and old_jld_data:
        new_jld_data = build_new_blogposting(old_jld_data, post_url, pub_iso)
        new_jld_block = (
            f'<script type="application/ld+json">\n'
            f'{json.dumps(new_jld_data, ensure_ascii=False, indent=2)}\n'
            f'</script>'
        )
        new_html = new_html.replace(old_jld_block, new_jld_block, 1)
        changed = True

    # ── 2. 네이버 요약박스 추가 (없는 경우만) ──
    if 'post-summary' not in new_html:
        # h1 태그 다음에 삽입
        h1_match = re.search(r'(<h1[^>]*>.*?</h1>)', new_html, re.S)
        if h1_match:
            # 제목에서 키워드 추출 (첫 20자)
            title_text = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
            summary_box = (
                f'\n<div class="post-summary" style="'
                f'background:#f0f7ff;border-left:4px solid #1a73e8;'
                f'padding:16px 20px;margin:16px 0 24px;border-radius:0 8px 8px 0;'
                f'font-size:0.95em;line-height:1.7;color:#1a1a2e;">'
                f'<strong>📌 이 글의 핵심</strong><br>'
                f'이 글에서는 <strong>{title_text[:30]}</strong>에 대해 '
                f'실전 중심으로 정리합니다. 아래 본문에서 단계별로 확인하세요.'
                f'</div>\n'
            )
            insert_after = h1_match.end()
            new_html = new_html[:insert_after] + summary_box + new_html[insert_after:]
            changed = True

    return new_html, changed


def main():
    token = get_token()
    print("🔄 전체 포스트 SEO 업데이트 시작...\n")

    # 전체 포스트 목록
    posts = []
    page_token = None
    while True:
        url = f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts?maxResults=500&status=LIVE&fetchBodies=false"
        if page_token:
            url += f"&pageToken={page_token}"
        data = blogger_get(f"/blogs/{BLOG_ID}/posts" + ("" if not page_token else f"?maxResults=500&status=LIVE&fetchBodies=false&pageToken={page_token}"), token)
        # 직접 URL 방식으로
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        for p in data.get("items", []):
            posts.append({"id": p["id"], "url": p.get("url", ""), "published": p.get("published", "")})
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    print(f"총 {len(posts)}개 포스트 처리 예정\n")
    ok, skip, fail = 0, 0, 0

    for i, post in enumerate(posts, 1):
        pid = post["id"]
        purl = post["url"]
        pub  = post["published"]
        print(f"[{i:2}/{len(posts)}] {purl.split('/')[-1][:40]}")

        try:
            # 포스트 전체 본문 가져오기
            req = urllib.request.Request(
                f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts/{pid}?fields=content,published",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                pdata = json.loads(r.read())

            content = pdata.get("content", "")
            pub_iso = pdata.get("published", pub)

            new_content, changed = update_post_html(content, purl, pub_iso)

            if not changed:
                print(f"       → SKIP (변경 없음 또는 JSON-LD 없음)")
                skip += 1
                time.sleep(0.3)
                continue

            # PATCH로 업데이트
            result = blogger_patch(
                f"/blogs/{BLOG_ID}/posts/{pid}",
                token,
                {"content": new_content}
            )
            print(f"       → OK ✅")
            ok += 1

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:100]
            print(f"       → FAIL ❌ HTTP {e.code}: {body}")
            fail += 1
            if e.code == 429:
                print("       Rate limit — 10초 대기")
                time.sleep(10)

        except Exception as e:
            print(f"       → FAIL ❌ {e}")
            fail += 1

        # Rate limit 방지
        time.sleep(1.2)

    print(f"\n완료: 성공 {ok}개 / 스킵 {skip}개 / 실패 {fail}개")


if __name__ == "__main__":
    main()
