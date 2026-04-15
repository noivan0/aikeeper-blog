#!/usr/bin/env python3
"""
기존 포스트 canonical 중복 + JSON-LD 중복 수정
Blogger API PATCH로 기존 포스트 content 업데이트
"""
import os, sys, re, json, time, gzip
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BLOG_ID  = os.environ.get("ALLSWEEP_BLOG_ID", "3598676904202320050")
BLOG_URL = "https://aikeeper.allsweep.xyz"

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

def fix_html_content(html: str) -> tuple[str, list]:
    """포스트 HTML에서 문제 태그 제거, 변경 목록 반환"""
    changes = []
    original = html

    # 1. canonical 중복 제거 — href="https://aikeeper.allsweep.xyz/" 로 끝나는 것만 제거
    #    (Blogger 테마가 올바른 포스트별 canonical 이미 삽입)
    pattern = r'<link\s+rel=["\']canonical["\']\s+href=["\']https://aikeeper\.allsweep\.xyz/["\']\s*/?>|<link\s+href=["\']https://aikeeper\.allsweep\.xyz/["\']\s+rel=["\']canonical["\']\s*/?>'
    new_html, n = re.subn(pattern, '', html, flags=re.I)
    if n:
        html = new_html
        changes.append(f"canonical 중복 {n}개 제거")

    # 2. charset/viewport/content-language 메타 제거 (Blogger 테마에서 중복)
    for pat in [
        r'<meta\s+charset=["\']UTF-8["\'][^>]*/?>',
        r'<meta\s+name=["\']viewport["\'][^>]*/?>',
        r'<meta\s+http-equiv=["\']content-language["\'][^>]*/?>',
    ]:
        new_html, n = re.subn(pat, '', html, flags=re.I)
        if n:
            html = new_html
            changes.append(f"중복 메타 제거: {pat[:30]}...")

    # 3. WebSite JSON-LD 스키마 제거 (포스트 수준 불필요)
    website_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>\s*\{[^}]*"@type"\s*:\s*"WebSite"[^<]*\}\s*</script>'
    new_html, n = re.subn(website_pattern, '', html, flags=re.S|re.I)
    if n:
        html = new_html
        changes.append(f"WebSite JSON-LD {n}개 제거")

    # 4. og:url 홈 주소 태그 제거 (포스트별 URL 아닌 홈 주소)
    og_url_pattern = r'<meta\s+property=["\']og:url["\']\s+content=["\']https://aikeeper\.allsweep\.xyz/["\']\s*/?>'
    new_html, n = re.subn(og_url_pattern, '', html, flags=re.I)
    if n:
        html = new_html
        changes.append(f"og:url 홈 중복 {n}개 제거")

    return html, changes

def patch_post(post_id: str, content: str, token: str) -> bool:
    """Blogger API PATCH로 포스트 content 업데이트"""
    url = f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts/{post_id}"
    body = {"content": content}
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(raw)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Encoding": "gzip",
    }
    resp = requests.patch(url, headers=headers, data=compressed, timeout=30, allow_redirects=False)
    return resp.status_code in (200, 204)

def list_all_posts(token: str) -> list:
    """블로그 전체 포스트 목록 조회"""
    posts = []
    page_token = None
    while True:
        params = {"maxResults": 20, "fields": "items(id,url,title),nextPageToken"}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts",
            headers={"Authorization": f"Bearer {token}"},
            params=params, timeout=15
        )
        if resp.status_code != 200:
            print(f"  포스트 목록 조회 실패: {resp.status_code}")
            break
        data = resp.json()
        posts.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return posts

def get_post_content(post_id: str, token: str) -> str:
    """단일 포스트 content 조회"""
    resp = requests.get(
        f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts/{post_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "content"},
        timeout=15
    )
    if resp.status_code == 200:
        return resp.json().get("content", "")
    return ""

def main():
    print("🔧 기존 포스트 SEO 수정 시작")
    creds = get_credentials()
    token = creds.token
    print(f"  토큰 발급 완료")

    posts = list_all_posts(token)
    print(f"  총 {len(posts)}개 포스트 발견\n")

    ok, skipped, failed = 0, 0, 0

    for i, post in enumerate(posts, 1):
        post_id = post["id"]
        title = post.get("title", "")[:50]
        url = post.get("url", "")
        print(f"[{i}/{len(posts)}] {title}")

        # content 조회
        content = get_post_content(post_id, token)
        if not content:
            print(f"  ⚠️  content 없음, 스킵")
            skipped += 1
            continue

        # 수정
        new_content, changes = fix_html_content(content)

        if not changes:
            print(f"  ✅ 수정 불필요 (이미 깨끗함)")
            skipped += 1
        else:
            print(f"  📝 수정: {', '.join(changes)}")
            # 토큰 갱신 (만료 방지)
            if not creds.valid:
                creds.refresh(Request())
                token = creds.token

            success = patch_post(post_id, new_content, token)
            if success:
                print(f"  ✅ 업데이트 완료")
                ok += 1
            else:
                print(f"  ❌ 업데이트 실패")
                failed += 1

        time.sleep(0.8)  # API quota 보호

    print(f"\n완료: 수정 {ok}개 / 스킵 {skipped}개 / 실패 {failed}개 / 전체 {len(posts)}개")

if __name__ == "__main__":
    main()
