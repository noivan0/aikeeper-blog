#!/usr/bin/env python3
"""
update_allsweep_posts.py — allsweep.xyz 기존 포스트 AdSense + JSON-LD 삽입

적용 내용:
1. AdSense in-article 광고 (본문 중간 삽입)
2. AdSense display 광고 (본문 하단 삽입)
3. JSON-LD BlogPosting 스키마 삽입 (없는 경우)
4. 이미 ca-pub 코드가 있으면 스킵

Blog ID: 8772490249452917821
Blog URL: https://www.allsweep.xyz
"""

import os, re, sys, json, time, datetime, urllib.request, urllib.parse, gzip, logging

# ── 블로그 설정 ──
BLOG_ID   = os.environ.get("TARGET_BLOG_ID",   "8772490249452917821")
BLOG_URL  = os.environ.get("TARGET_BLOG_URL",  "https://www.allsweep.xyz")
BLOG_NAME = os.environ.get("TARGET_BLOG_NAME", "모든정보 쓸어담기")
ADSENSE_PUB          = os.environ.get("ADSENSE_PUB",            "ca-pub-2597570939533872")
ADSENSE_IN_ARTICLE   = os.environ.get("ADSENSE_IN_ARTICLE_SLOT","6675974233")
ADSENSE_DISPLAY      = os.environ.get("ADSENSE_DISPLAY_SLOT",   "8117048415")
NAVER_VERIFY         = os.environ.get("NAVER_SITE_VERIFICATION","cecd949ef22ac450cb8403b1a51b820bbe46fcb3")

# ── API 인증 ──
CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")

# ── 처리 제한 ──
MAX_POSTS   = int(os.environ.get("MAX_POSTS", "100"))   # 최대 처리 포스트 수
SLEEP_SEC   = float(os.environ.get("SLEEP_SEC", "1.2")) # 요청 간 대기
RATE_WAIT   = 30                                         # 429 시 대기 초

LOG_FILE = "/var/log/allsweep_update.log"

# ── 로깅 설정 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("allsweep_update")


# ── AdSense 코드 템플릿 ──
def adsense_in_article() -> str:
    return f"""
<div style="margin:32px 0;text-align:center;">
<ins class="adsbygoogle"
     style="display:block;text-align:center;"
     data-ad-layout="in-article"
     data-ad-format="fluid"
     data-ad-client="{ADSENSE_PUB}"
     data-ad-slot="{ADSENSE_IN_ARTICLE}"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
"""

def adsense_display() -> str:
    return f"""
<div style="margin:32px 0;text-align:center;">
<ins class="adsbygoogle"
     style="display:block;"
     data-ad-client="{ADSENSE_PUB}"
     data-ad-slot="{ADSENSE_DISPLAY}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
"""

def build_json_ld(headline: str, description: str, post_url: str,
                  pub_iso: str, img_url: str = "") -> str:
    """BlogPosting JSON-LD 생성"""
    pub_kst = to_kst_iso(pub_iso)
    jld: dict = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": headline[:110],
        "description": description[:300] if description else headline[:150],
        "datePublished": pub_kst,
        "dateModified": pub_kst,
        "author": {
            "@type": "Organization",
            "name": BLOG_NAME,
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
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": ["h1", "h2", ".post-body"]
        },
    }
    if img_url:
        jld["image"] = [
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 1200},
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 900},
            {"@type": "ImageObject", "url": img_url, "width": 1200, "height": 630},
        ]
        jld["thumbnailUrl"] = img_url
    return (
        f'<script type="application/ld+json">\n'
        f'{json.dumps(jld, ensure_ascii=False, indent=2)}\n'
        f'</script>'
    )


def to_kst_iso(iso_str: str) -> str:
    if not iso_str:
        return datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))
        ).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    m = re.match(
        r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?([+-]\d{2}:\d{2}|Z)?',
        iso_str
    )
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


# ── Blogger API 헬퍼 ──
_token_cache: dict = {}

def get_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def api_get(url: str, token: str, retry: int = 3) -> dict:
    for attempt in range(retry):
        try:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {token}",
                         "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log.warning(f"429 Rate limit — {RATE_WAIT}s 대기 (시도 {attempt+1})")
                time.sleep(RATE_WAIT)
            elif e.code == 401:
                raise  # 토큰 오류는 재시도 불가
            else:
                raise
        except Exception as e:
            if attempt == retry - 1:
                raise
            time.sleep(3)
    return {}


def api_patch(post_id: str, token: str, content: str, retry: int = 3) -> bool:
    url = f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts/{post_id}"
    body = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(body)
    for attempt in range(retry):
        try:
            req = urllib.request.Request(
                url, data=compressed,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Content-Encoding": "gzip",
                    "Accept-Encoding": "gzip",
                },
                method="PATCH"
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status in (200, 204)
        except urllib.error.HTTPError as e:
            body_err = e.read().decode("utf-8", errors="ignore")[:200]
            if e.code == 429:
                log.warning(f"429 Rate limit — {RATE_WAIT}s 대기 (시도 {attempt+1})")
                time.sleep(RATE_WAIT)
            else:
                log.error(f"PATCH HTTP {e.code}: {body_err}")
                return False
        except Exception as e:
            if attempt == retry - 1:
                log.error(f"PATCH 실패: {e}")
                return False
            time.sleep(3)
    return False


# ── HTML 변환 로직 ──
def extract_hero_image(html: str) -> str:
    """첫 번째 img 태그 src 추출"""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else ""


def extract_title(html: str) -> str:
    """h1 태그에서 텍스트 추출"""
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return ""


def extract_description(html: str) -> str:
    """첫 번째 p 태그 텍스트 추출 (최대 200자)"""
    m = re.search(r'<p[^>]*>(.*?)</p>', html, re.S | re.I)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:200]
    return ""


def upgrade_post_html(
    html: str,
    post_url: str,
    pub_iso: str,
    title_fallback: str = ""
) -> tuple[str, bool, list[str]]:
    """
    포스트 HTML 업그레이드:
    - AdSense 삽입 (중간 + 하단)
    - JSON-LD 삽입 (없는 경우)
    반환: (new_html, changed, changes_list)
    """
    changes = []
    changed = False

    # ── 1. AdSense 이미 있으면 스킵 ──
    if ADSENSE_PUB in html or "adsbygoogle" in html:
        return html, False, ["SKIP: AdSense 이미 존재"]

    new_html = html

    # ── 2. JSON-LD 없으면 삽입 ──
    has_json_ld = bool(re.search(
        r'<script[^>]*type=["\']application/ld\+json["\']', html, re.I
    ))
    if not has_json_ld:
        title    = extract_title(html) or title_fallback
        desc     = extract_description(html)
        img_url  = extract_hero_image(html)
        jld_block = build_json_ld(title, desc, post_url, pub_iso, img_url)
        # 본문 맨 앞에 삽입
        new_html = jld_block + "\n" + new_html
        changes.append("JSON-LD 삽입")
        changed = True

    # ── 3. AdSense in-article: 본문 중간 (h2 태그 2번째 앞에 삽입) ──
    h2_matches = list(re.finditer(r'<h2[^>]*>', new_html, re.I))
    if len(h2_matches) >= 2:
        # 두 번째 h2 앞에 삽입
        insert_pos = h2_matches[1].start()
        new_html = (
            new_html[:insert_pos]
            + adsense_in_article()
            + new_html[insert_pos:]
        )
        changes.append("AdSense in-article 삽입 (h2-2 앞)")
    elif len(h2_matches) == 1:
        # h2가 1개면 그 앞에 삽입
        insert_pos = h2_matches[0].start()
        new_html = (
            new_html[:insert_pos]
            + adsense_in_article()
            + new_html[insert_pos:]
        )
        changes.append("AdSense in-article 삽입 (h2-1 앞)")
    else:
        # h2 없으면 첫 p 뒤에 삽입
        p_match = re.search(r'</p>', new_html, re.I)
        if p_match:
            insert_pos = p_match.end()
            new_html = (
                new_html[:insert_pos]
                + adsense_in_article()
                + new_html[insert_pos:]
            )
            changes.append("AdSense in-article 삽입 (p 뒤)")
        else:
            changes.append("AdSense in-article: 삽입 위치 없음")

    # ── 4. AdSense display: 본문 맨 끝에 삽입 ──
    new_html = new_html.rstrip() + "\n" + adsense_display()
    changes.append("AdSense display 삽입 (하단)")
    changed = True

    return new_html, changed, changes


# ── 메인 ──
def main():
    log.info("=" * 60)
    log.info(f"allsweep.xyz 포스트 AdSense+JSON-LD 업그레이드 시작")
    log.info(f"Blog ID: {BLOG_ID} / URL: {BLOG_URL}")
    log.info(f"AdSense PUB: {ADSENSE_PUB}")
    log.info(f"최대 처리 수: {MAX_POSTS}")
    log.info("=" * 60)

    # 토큰 획득
    try:
        token = get_token()
        log.info("OAuth 토큰 획득 완료")
    except Exception as e:
        log.error(f"토큰 획득 실패: {e}")
        sys.exit(1)

    # ── 포스트 목록 수집 ──
    posts = []
    page_token = None
    page = 0
    while True:
        page += 1
        url = (
            f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts"
            f"?maxResults=50&status=LIVE&fetchBodies=false&orderBy=PUBLISHED"
        )
        if page_token:
            url += f"&pageToken={page_token}"
        try:
            data = api_get(url, token)
        except Exception as e:
            log.error(f"포스트 목록 조회 실패 (페이지 {page}): {e}")
            break

        for p in data.get("items", []):
            posts.append({
                "id":        p["id"],
                "url":       p.get("url", ""),
                "title":     p.get("title", ""),
                "published": p.get("published", ""),
            })

        page_token = data.get("nextPageToken")
        log.info(f"  목록 페이지 {page}: {len(data.get('items', []))}개 수집 (누계 {len(posts)}개)")

        if not page_token or len(posts) >= MAX_POSTS:
            break
        time.sleep(0.5)

    # 최신순 MAX_POSTS개만
    posts = posts[:MAX_POSTS]
    total = len(posts)
    log.info(f"\n처리 대상: {total}개 포스트\n")

    ok, skip, fail = 0, 0, 0
    sample_url = ""

    for i, post in enumerate(posts, 1):
        pid   = post["id"]
        purl  = post["url"]
        ptitle = post["title"]
        pub   = post["published"]

        log.info(f"[{i:3}/{total}] {ptitle[:50]}")

        # 포스트 본문 조회
        try:
            data = api_get(
                f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts/{pid}"
                f"?fields=content,published,url,title",
                token
            )
        except Exception as e:
            log.error(f"       → 조회 실패: {e}")
            fail += 1
            time.sleep(SLEEP_SEC)
            continue

        content   = data.get("content", "")
        pub_iso   = data.get("published", pub)
        real_url  = data.get("url", purl)
        real_title = data.get("title", ptitle)

        if not content:
            log.info(f"       → SKIP (본문 없음)")
            skip += 1
            time.sleep(SLEEP_SEC)
            continue

        # HTML 업그레이드
        new_content, changed, changes = upgrade_post_html(
            content, real_url, pub_iso, real_title
        )

        if not changed:
            log.info(f"       → SKIP ({changes[0] if changes else '변경 없음'})")
            skip += 1
            time.sleep(SLEEP_SEC)
            continue

        log.info(f"       → 변경: {', '.join(changes)}")

        # PATCH 업데이트
        success = api_patch(pid, token, new_content)
        if success:
            log.info(f"       → OK ✅ {real_url}")
            ok += 1
            if not sample_url:
                sample_url = real_url
        else:
            log.error(f"       → FAIL ❌")
            fail += 1

        time.sleep(SLEEP_SEC)

    log.info("\n" + "=" * 60)
    log.info(f"완료: 성공 {ok}개 / 스킵 {skip}개 / 실패 {fail}개 / 전체 {total}개")
    log.info(f"샘플 포스트: {sample_url}")
    log.info("=" * 60)

    print(f"\n{'='*60}")
    print(f"✅ 완료 — 성공: {ok}  스킵: {skip}  실패: {fail}  전체: {total}")
    print(f"📄 샘플 URL: {sample_url}")
    print(f"📋 로그: {LOG_FILE}")


if __name__ == "__main__":
    main()
