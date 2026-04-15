#!/usr/bin/env python3
"""
ggultongmon Blogger 전체 포스팅 쿠팡 링크 → 공식 shortenUrl 일괄 변환
실행: python3 scripts/fix_all_coupang_links.py
"""
import sys, os, re, time, json, urllib.parse, hmac, hashlib, ssl
import urllib.request
from pathlib import Path
from time import gmtime, strftime

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

import google.oauth2.credentials
import googleapiclient.discovery

BLOG_ID = os.environ.get('GGULTONGMON_BLOG_ID', '4422596386410826373')
LOG_FILE = Path(__file__).parent.parent / 'results' / 'fix_links_log.jsonl'
LOG_FILE.parent.mkdir(exist_ok=True)

ACCESS_KEY = os.environ.get('COUPANG_ACCESS_KEY', '')
SECRET_KEY = os.environ.get('COUPANG_SECRET_KEY', '')
SUB_ID = 'ggultongmon'
DOMAIN = 'https://api-gateway.coupang.com'

# Blogger API 인증
creds = google.oauth2.credentials.Credentials(
    token=None,
    refresh_token=os.environ['GGULTONGMON_REFRESH_TOKEN'],
    client_id=os.environ['GGULTONGMON_CLIENT_ID'],
    client_secret=os.environ['GGULTONGMON_CLIENT_SECRET'],
    token_uri='https://oauth2.googleapis.com/token'
)
service = googleapiclient.discovery.build('blogger', 'v3', credentials=creds)

AFFSDP_PAT = re.compile(r'https://link\.coupang\.com/re/AFFSDP\?[^\s"<]+')


def generate_hmac(method, url):
    path, *query = url.split('?')
    dt = strftime('%y%m%d', gmtime()) + 'T' + strftime('%H%M%S', gmtime()) + 'Z'
    msg = dt + method + path + (query[0] if query else '')
    sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f'CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature={sig}'


def deeplink_direct(coupang_urls):
    """직접 연결로 deeplink API 호출 (프록시 없음)"""
    path = '/v2/providers/affiliate_open_api/apis/openapi/deeplink'
    auth = generate_hmac('POST', path)
    body = json.dumps({'coupangUrls': coupang_urls}).encode('utf-8')
    req = urllib.request.Request(
        DOMAIN + path,
        data=body,
        method='POST',
        headers={
            'Authorization': auth,
            'Content-Type': 'application/json;charset=UTF-8'
        }
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        raw = r.read()
        for enc in ('utf-8', 'euc-kr', 'cp949', 'latin-1'):
            try:
                return json.loads(raw.decode(enc))
            except Exception:
                continue
        raise ValueError(f'응답 디코딩 실패: {raw[:50]}')


def get_deeplink_batch(items):
    """items: list of (pageKey, itemId, vendorItemId) → {pageKey: shortenUrl}"""
    urls = []
    for pk, iid, vid in items:
        if iid and vid:
            urls.append(f'https://www.coupang.com/vp/products/{pk}?itemId={iid}&vendorItemId={vid}')
        else:
            urls.append(f'https://www.coupang.com/vp/products/{pk}')
    try:
        r = deeplink_direct(urls)
        result = {}
        for i, d in enumerate(r.get('data', [])):
            pk = items[i][0]
            surl = d.get('shortenUrl', '')
            if surl:
                result[pk] = surl
        return result
    except Exception as e:
        print(f'  [WARN] deeplink 실패: {e}')
        return {}


def get_all_posts():
    posts = []
    token = None
    page = 0
    while True:
        kwargs = dict(blogId=BLOG_ID, maxResults=50, fetchBodies=True)
        if token:
            kwargs['pageToken'] = token
        r = service.posts().list(**kwargs).execute()
        batch = r.get('items', [])
        posts.extend(batch)
        token = r.get('nextPageToken')
        page += 1
        print(f'  페이지 {page}: {len(batch)}개 (누적 {len(posts)}개)')
        if not token:
            break
        time.sleep(0.3)
    return posts


def extract_affsdp_links(content):
    links = AFFSDP_PAT.findall(content)
    result = {}
    for raw in links:
        url = raw.replace('&amp;', '&').split('"')[0].split("'")[0].rstrip(');,')
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        pk = params.get('pageKey', '')
        if pk and pk not in result:
            result[pk] = {
                'itemId': params.get('itemId', ''),
                'vendorItemId': params.get('vendorItemId', ''),
            }
    return result


def fix_content(content, pk_to_shorten):
    def replacer(m):
        raw = m.group(0)
        url = raw.replace('&amp;', '&').split('"')[0].split("'")[0].rstrip(');,')
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        pk = params.get('pageKey', '')
        return pk_to_shorten.get(pk, raw)
    return AFFSDP_PAT.sub(replacer, content)


def main():
    print('=== ggultongmon 전체 쿠팡 링크 수정 (직접연결) ===')
    print('전체 포스팅 수집 중...')
    all_posts = get_all_posts()
    print(f'총 {len(all_posts)}개 수집 완료\n')

    to_fix = []
    for p in all_posts:
        content = p.get('content', '')
        if 'link.coupang.com/re/AFFSDP' in content:
            link_map = extract_affsdp_links(content)
            if link_map:
                to_fix.append({'id': p['id'], 'title': p['title'], 'content': content, 'link_map': link_map})

    print(f'수정 대상: {len(to_fix)}개 포스팅\n')

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for idx, post in enumerate(to_fix):
        pid = post['id']
        title = post['title'][:45]
        link_map = post['link_map']

        keys = list(link_map.keys())
        pk_to_shorten = {}
        for i in range(0, len(keys), 10):
            batch_keys = keys[i:i+10]
            items = [(pk, link_map[pk]['itemId'], link_map[pk]['vendorItemId']) for pk in batch_keys]
            result = get_deeplink_batch(items)
            pk_to_shorten.update(result)
            if i + 10 < len(keys):
                time.sleep(0.5)

        if not pk_to_shorten:
            print(f'  [{idx+1}/{len(to_fix)}] SKIP (단종/API실패): {title}')
            skip_count += 1
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps({'post_id': pid, 'title': title, 'status': 'skip'}, ensure_ascii=False) + '\n')
            continue

        new_content = fix_content(post['content'], pk_to_shorten)
        remaining = len(AFFSDP_PAT.findall(new_content))

        try:
            service.posts().patch(
                blogId=BLOG_ID, postId=pid,
                body={'content': new_content}
            ).execute()
            ok_count += 1
            print(f'  [{idx+1}/{len(to_fix)}] OK: {title} | {len(pk_to_shorten)}/{len(keys)}상품 | 잔여:{remaining}')
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps({'post_id': pid, 'title': title, 'status': 'ok',
                                    'fixed': len(pk_to_shorten), 'total': len(keys),
                                    'remaining_affsdp': remaining}, ensure_ascii=False) + '\n')
        except Exception as e:
            fail_count += 1
            print(f'  [{idx+1}/{len(to_fix)}] FAIL: {title} | {e}')
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps({'post_id': pid, 'title': title, 'status': 'fail', 'error': str(e)}, ensure_ascii=False) + '\n')

        time.sleep(1.0)

    print(f'\n=== 완료 ===')
    print(f'수정 성공: {ok_count}개 | 단종 스킵: {skip_count}개 | 실패: {fail_count}개')


if __name__ == '__main__':
    main()
