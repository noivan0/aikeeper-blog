#!/usr/bin/env python3
"""
fix_affsdp_links.py — AFFSDP 링크 → 공식 shortenUrl 일괄 변환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ggultongmon Blogger: AFFSDP 링크가 있는 포스팅 → deeplink API shortenUrl로 교체
- 결과 요약 출력 + 실패 목록 파일 저장
"""
import sys
import os
import re
import time
import urllib.parse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

import google.oauth2.credentials
import google.auth.transport.requests
import googleapiclient.discovery
from coupang_api import _post

# ── 설정 ─────────────────────────────────────────────────────────────────
BLOG_ID = os.environ.get('GGULTONGMON_BLOG_ID', '4422596386410826373')
DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/deeplink"
AFFSDP_PATTERN = re.compile(r'https://link\.coupang\.com/re/AFFSDP\?[^"<\s\']+')

# ── Blogger API 인증 ──────────────────────────────────────────────────────
def build_blogger_service():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ['GGULTONGMON_REFRESH_TOKEN'],
        client_id=os.environ['GGULTONGMON_CLIENT_ID'],
        client_secret=os.environ['GGULTONGMON_CLIENT_SECRET'],
        token_uri='https://oauth2.googleapis.com/token'
    )
    # 토큰 강제 갱신
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    service = googleapiclient.discovery.build('blogger', 'v3', credentials=creds)
    return service

# ── 포스팅 목록 전체 수집 ─────────────────────────────────────────────────
def fetch_all_posts(service):
    """페이징으로 전체 포스팅 목록 수집"""
    all_posts = []
    page_token = None
    page_num = 0
    while True:
        page_num += 1
        kwargs = dict(blogId=BLOG_ID, maxResults=500, fields='nextPageToken,items(id,title,content)', status='LIVE')
        if page_token:
            kwargs['pageToken'] = page_token
        resp = service.posts().list(**kwargs).execute()
        items = resp.get('items', [])
        all_posts.extend(items)
        print(f"  페이지 {page_num}: {len(items)}개 수집 (누적: {len(all_posts)}개)")
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
        time.sleep(0.5)
    return all_posts

# ── URL 파싱 ─────────────────────────────────────────────────────────────
def parse_affsdp_url(url):
    """AFFSDP URL에서 pageKey, itemId, vendorItemId 추출"""
    try:
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        page_key = params.get('pageKey') or params.get('pagekey')
        item_id = params.get('itemId') or params.get('itemid')
        vendor_item_id = params.get('vendorItemId') or params.get('vendoritemid')
        return page_key, item_id, vendor_item_id
    except Exception:
        return None, None, None

# ── deeplink API 배치 호출 ────────────────────────────────────────────────
def get_shorten_urls_batch(coupang_urls):
    """coupang_urls 리스트 → {url: shortenUrl} 딕셔너리"""
    result = {}
    if not coupang_urls:
        return result
    for i in range(0, len(coupang_urls), 10):
        batch = coupang_urls[i:i+10]
        try:
            resp = _post(DEEPLINK_PATH, {"coupangUrls": batch})
            data_list = resp.get("data", [])
            # 순서 기반 매핑
            if len(data_list) == len(batch):
                for orig_url, item in zip(batch, data_list):
                    shorten = item.get("shortenUrl", "")
                    if shorten:
                        result[orig_url] = shorten
            else:
                # landingUrl로 매핑 시도
                for item in data_list:
                    shorten = item.get("shortenUrl", "")
                    landing = item.get("landingUrl", "")
                    if shorten and landing:
                        result[landing] = shorten
        except Exception as e:
            print(f"  [WARN] deeplink 배치 실패: {e}")
        if i + 10 < len(coupang_urls):
            time.sleep(1)
    return result

# ── 포스팅 처리 ──────────────────────────────────────────────────────────
def process_post(post, shorten_cache):
    """
    포스팅 내 AFFSDP 링크 분석 및 교체.
    - shorten_cache: {pageKey: shortenUrl} 공유 캐시
    - 반환: (new_content, changed, skipped_urls)
    """
    content = post.get('content', '')
    if not content:
        return content, False, []

    affsdp_urls = AFFSDP_PATTERN.findall(content)
    if not affsdp_urls:
        return content, False, []

    # pageKey별 고유 상품 URL 수집
    page_key_to_coupang = {}  # pageKey → coupang URL
    page_key_to_shorten = {}  # pageKey → shortenUrl (캐시에서)
    skipped = []

    for url in set(affsdp_urls):
        page_key, item_id, vendor_item_id = parse_affsdp_url(url)
        if not page_key or not item_id or not vendor_item_id:
            skipped.append(url)
            continue

        if page_key in shorten_cache:
            page_key_to_shorten[page_key] = shorten_cache[page_key]
        else:
            coupang_url = f"https://www.coupang.com/vp/products/{page_key}?itemId={item_id}&vendorItemId={vendor_item_id}"
            page_key_to_coupang[page_key] = coupang_url

    # 신규 상품 deeplink 호출
    if page_key_to_coupang:
        coupang_urls = list(page_key_to_coupang.values())
        url_to_shorten = get_shorten_urls_batch(coupang_urls)
        for pk, coupang_url in page_key_to_coupang.items():
            if coupang_url in url_to_shorten:
                page_key_to_shorten[pk] = url_to_shorten[coupang_url]
                shorten_cache[pk] = url_to_shorten[coupang_url]
            else:
                skipped.append(f"pageKey={pk} (deeplink 실패)")

    # 내용 교체
    new_content = content
    changed = False
    for url in AFFSDP_PATTERN.findall(content):
        page_key, _, _ = parse_affsdp_url(url)
        if page_key and page_key in page_key_to_shorten:
            shorten = page_key_to_shorten[page_key]
            new_content = new_content.replace(url, shorten)
            changed = True

    # 교체 후 AFFSDP 링크 잔존 확인
    remaining = AFFSDP_PATTERN.findall(new_content)
    if remaining:
        skipped.extend([f"잔존(교체실패): {u}" for u in remaining])

    return new_content, changed, skipped

# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("AFFSDP → shortenUrl 일괄 변환 시작")
    print("=" * 60)

    service = build_blogger_service()
    print("\n[1] 전체 포스팅 목록 수집 중...")
    all_posts = fetch_all_posts(service)
    print(f"  총 {len(all_posts)}개 포스팅 수집 완료\n")

    # AFFSDP 링크가 있는 포스팅 필터링
    target_posts = []
    for post in all_posts:
        content = post.get('content', '')
        if content and AFFSDP_PATTERN.search(content):
            target_posts.append(post)

    print(f"[2] AFFSDP 링크 포스팅: {len(target_posts)}개\n")

    success_count = 0
    skip_count = 0
    error_count = 0
    failed_posts = []
    shorten_cache = {}  # pageKey → shortenUrl 공유 캐시

    for idx, post in enumerate(target_posts, 1):
        post_id = post['id']
        title = post.get('title', '')[:50]

        try:
            new_content, changed, skipped = process_post(post, shorten_cache)

            if changed:
                # Blogger API PATCH
                try:
                    service.posts().patch(
                        blogId=BLOG_ID,
                        postId=post_id,
                        body={'content': new_content}
                    ).execute()
                    success_count += 1
                    status = "✓ 수정"
                except Exception as e:
                    error_count += 1
                    failed_posts.append({'id': post_id, 'title': title, 'error': str(e)})
                    status = f"✗ PATCH 실패: {e}"
            else:
                skip_count += 1
                status = "- 변경없음"

            if skipped:
                print(f"  [{idx}/{len(target_posts)}] {title} | {status} | 스킵: {len(skipped)}")
                for s in skipped[:3]:
                    print(f"    ⚠ {s[:80]}")
            elif idx % 10 == 0 or changed:
                print(f"  [{idx}/{len(target_posts)}] {title} | {status}")

        except Exception as e:
            error_count += 1
            failed_posts.append({'id': post_id, 'title': title, 'error': str(e)})
            print(f"  [{idx}/{len(target_posts)}] {title} | ✗ 오류: {e}")

        # Rate limit: 포스팅당 1초 대기
        time.sleep(1)

    # 결과 요약
    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    print(f"  대상 포스팅:  {len(target_posts)}개")
    print(f"  수정 성공:    {success_count}개")
    print(f"  변경 없음:    {skip_count}개")
    print(f"  실패/오류:    {error_count}개")
    print(f"  공유 캐시:    {len(shorten_cache)}개 pageKey")

    # 실패 목록 저장
    if failed_posts:
        out_path = Path(__file__).parent.parent / "fix_affsdp_failed.json"
        out_path.write_text(json.dumps(failed_posts, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n  실패 목록 저장: {out_path}")
        for fp in failed_posts[:10]:
            print(f"    - [{fp['id']}] {fp['title']}: {fp['error']}")

    return success_count, error_count, failed_posts

if __name__ == '__main__':
    main()
