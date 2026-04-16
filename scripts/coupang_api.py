"""
쿠팡 파트너스 Open API V1 클라이언트 — 다중 폴백 전략
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
폴백 우선순위:
  1. SOCKS5 프록시 (동적으로 갱신된 목록 사용)
  2. 직접 연결 (웹필터 없는 환경)
  3. GitHub Actions 캐시 (coupang_cache/latest.json)
  4. 로컬 캐시 (최근 성공 데이터)

이미지 전략:
  - 쿠팡 CDN 이미지 직접 사용 (웹필터 미적용)
  - 해상도 최적화 (width 파라미터)
  - 섬네일 + 본문 이미지 분리
"""
import hmac
import hashlib
import urllib.request
import urllib.parse
import json
import os
import re
import ssl
import socket
import time
import datetime
from pathlib import Path
from time import gmtime, strftime

# ── 기본 설정 ─────────────────────────────────────────────────────────────
DOMAIN      = "https://api-gateway.coupang.com"
ACCESS_KEY  = os.environ.get("COUPANG_ACCESS_KEY", "")
SECRET_KEY  = os.environ.get("COUPANG_SECRET_KEY", "")
SUB_ID      = "ggultongmon"

PARTNERS_NOTICE = (
    '이 포스팅은 쿠팡 파트너스 활동의 일환으로, '
    '이에 따른 일정액의 수수료를 제공받습니다.'
)

# 캐시 파일 경로
_BASE_DIR    = Path(__file__).parent.parent
_CACHE_FILE  = _BASE_DIR / "coupang_cache" / "latest.json"
_LOCAL_CACHE = _BASE_DIR / "coupang_cache" / "local_cache.json"

# ── SOCKS5 프록시 동적 갱신 ─────────────────────────────────────────────
_PROXY_LIST = []          # 런타임에 갱신
_proxy_last_refresh = 0   # 마지막 갱신 시각

def _refresh_proxy_list(force=False):
    """프록시 목록 동적 갱신 (30분마다 또는 force=True)"""
    global _PROXY_LIST, _proxy_last_refresh
    if not force and time.time() - _proxy_last_refresh < 1800 and _PROXY_LIST:
        return
    try:
        req = urllib.request.Request(
            "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1"
            "&sort_by=lastChecked&sort_type=desc&protocols=socks5&speed=fast",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            new_list = [(p["ip"], int(p["port"])) for p in data.get("data", [])]
            if new_list:
                _PROXY_LIST = new_list[:50]
                _proxy_last_refresh = time.time()
    except Exception:
        pass  # 갱신 실패 시 기존 목록 유지

def _test_proxy(host, port, timeout=5):
    """프록시 단일 테스트. 성공 시 True."""
    try:
        import socks as _socks
        s = _socks.socksocket()
        s.set_proxy(_socks.SOCKS5, host, port)
        s.settimeout(timeout)
        s.connect(("api-gateway.coupang.com", 443))
        ctx = ssl.create_default_context()
        ss = ctx.wrap_socket(s, server_hostname="api-gateway.coupang.com")
        # 최소한의 요청으로 확인
        path = "/v2/providers/affiliate_open_api/apis/openapi/products/bestcategories/1016"
        query = "limit=1&subId=ggultongmon"
        dt = strftime("%y%m%dT%H%M%SZ", gmtime())
        msg = dt + "GET" + path + "?" + query
        sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, signed-date={dt}, signature={sig}"
        ss.send(f"GET {path}?{query} HTTP/1.1\r\nHost: api-gateway.coupang.com\r\nAuthorization: {auth}\r\nContent-Type: application/json;charset=UTF-8\r\nConnection: close\r\n\r\n".encode())
        resp = b""
        while len(resp) < 512:
            c = ss.recv(256)
            if not c: break
            resp += c
        ss.close(); s.close()
        return b"200 OK" in resp[:50] or b'"rCode"' in resp
    except Exception:
        return False

def _get_working_proxy():
    """동작하는 프록시 반환. 없으면 None."""
    _refresh_proxy_list()
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_test_proxy, h, p, 5): (h, p) for h, p in _PROXY_LIST[:20]}
            for f in concurrent.futures.as_completed(futures, timeout=10):
                hp = futures[f]
                try:
                    if f.result():
                        return hp
                except Exception:
                    pass
    except Exception:
        pass
    return None

# ── HMAC 서명 ─────────────────────────────────────────────────────────────
def generate_hmac(method: str, url: str) -> str:
    """쿠팡 파트너스 공식 HMAC 서명 생성"""
    path, *query = url.split("?")
    datetime_gmt = strftime("%y%m%d", gmtime()) + "T" + strftime("%H%M%S", gmtime()) + "Z"
    message = datetime_gmt + method + path + (query[0] if query else "")
    signature = hmac.new(
        bytes(SECRET_KEY, "utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, "
        f"signed-date={datetime_gmt}, signature={signature}"
    )

# ── 핵심 HTTP 요청 (다중 폴백) ────────────────────────────────────────────
def _call_api(path_with_query: str, method="GET", body=None) -> dict:
    """
    쿠팡 API 호출 — 4단계 폴백:
    1. SOCKS5 프록시 (동적 목록에서 작동 프록시 탐색)
    2. 직접 연결 (웹필터 없는 환경)
    3. GitHub Actions 캐시 파일 (coupang_cache/latest.json)
    4. 로컬 캐시
    """
    # ── 1단계: SOCKS5 프록시 ──
    working = _get_working_proxy()
    if working:
        try:
            return _request_via_socks(method, path_with_query, working, body)
        except Exception:
            pass

    # ── 2단계: 직접 연결 ──
    try:
        return _request_direct(method, path_with_query, body)
    except Exception:
        pass

    # ── 3단계: GitHub Actions 캐시 (GET 전용) ──
    if method == "GET" and "bestcategories" in path_with_query:
        cat_id = re.search(r"bestcategories/(\d+)", path_with_query)
        if cat_id:
            cached = _read_cache(cat_id.group(1))
            if cached:
                print(f"  [캐시] 카테고리 {cat_id.group(1)}: {len(cached)}개 (Actions 캐시)")
                return {"rCode": "0", "data": cached}

    raise ConnectionError("모든 쿠팡 API 접근 방법 실패")

def _request_via_socks(method, path_with_query, proxy, body=None):
    """SOCKS5 프록시 경유 요청"""
    import socks as _socks
    host, port = proxy
    auth = generate_hmac(method, path_with_query)
    headers = {
        "Host": "api-gateway.coupang.com",
        "Authorization": auth,
        "Content-Type": "application/json;charset=UTF-8",
        "Connection": "close",
    }
    s = _socks.socksocket()
    s.set_proxy(_socks.SOCKS5, host, port)
    s.settimeout(15)
    s.connect(("api-gateway.coupang.com", 443))
    ctx = ssl.create_default_context()
    ss = ctx.wrap_socket(s, server_hostname="api-gateway.coupang.com")

    header_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    if body:
        body_bytes = json.dumps(body).encode("utf-8")
        header_str += f"Content-Length: {len(body_bytes)}\r\n"
        raw = f"{method} {path_with_query} HTTP/1.1\r\n{header_str}\r\n".encode() + body_bytes
    else:
        raw = f"{method} {path_with_query} HTTP/1.1\r\n{header_str}\r\n".encode()

    ss.send(raw)
    resp = b""
    while True:
        try:
            c = ss.recv(8192)
            if not c: break
            resp += c
        except Exception: break
    try: ss.close()
    except: pass

    return _parse_http_response(resp)

def _request_direct(method, path_with_query, body=None):
    """직접 연결 요청"""
    auth = generate_hmac(method, path_with_query)
    headers = {"Authorization": auth, "Content-Type": "application/json;charset=UTF-8"}
    url = DOMAIN + path_with_query

    if body:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            method=method, headers=headers
        )
    else:
        req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
            try:
                return json.loads(raw.decode(enc))
            except Exception:
                continue
        raise ValueError("응답 디코딩 실패")

def _parse_http_response(resp: bytes) -> dict:
    """raw HTTP 응답 bytes → dict"""
    header_end = resp.find(b"\r\n\r\n")
    if header_end == -1:
        raise ValueError("HTTP 응답 파싱 실패")
    raw_body = resp[header_end + 4:]
    if not raw_body.strip():
        raise ValueError("빈 응답")
    for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            return json.loads(raw_body.decode(enc))
        except Exception:
            continue
    raise ValueError("디코딩 실패")

# ── 캐시 관리 ────────────────────────────────────────────────────────────
def _read_cache(cat_id: str) -> list:
    """Actions 캐시 또는 로컬 캐시에서 카테고리 데이터 읽기"""
    # Actions 캐시 (git pull 최신)
    for cache_file in [_CACHE_FILE, _LOCAL_CACHE]:
        try:
            if cache_file.exists():
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                cats = data.get("categories", {})
                products = cats.get(str(cat_id), [])
                if products:
                    return products
        except Exception:
            pass
    return []

def _save_local_cache(cat_id: str, products: list):
    """성공한 데이터를 로컬 캐시에 저장"""
    try:
        _LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if _LOCAL_CACHE.exists():
            existing = json.loads(_LOCAL_CACHE.read_text(encoding="utf-8"))
        cats = existing.get("categories", {})
        cats[str(cat_id)] = products
        existing["categories"] = cats
        existing["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        _LOCAL_CACHE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _load_item_id_cache() -> dict:
    """item_ids 캐시 로드 — {productId: {itemId, vendorItemId}}"""
    try:
        if _LOCAL_CACHE.exists():
            data = json.loads(_LOCAL_CACHE.read_text(encoding="utf-8"))
            return data.get("item_ids", {})
    except Exception:
        pass
    return {}

def _save_item_id_cache(product_id: str, item_id: str, vendor_item_id: str):
    """itemId/vendorItemId를 로컬 캐시에 저장"""
    try:
        _LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if _LOCAL_CACHE.exists():
            existing = json.loads(_LOCAL_CACHE.read_text(encoding="utf-8"))
        item_ids = existing.get("item_ids", {})
        item_ids[str(product_id)] = {
            "itemId": str(item_id),
            "vendorItemId": str(vendor_item_id),
        }
        existing["item_ids"] = item_ids
        existing["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        _LOCAL_CACHE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _extract_item_ids_from_url(url: str) -> tuple:
    """
    URL에서 itemId, vendorItemId 파라미터 추출.
    반환: (itemId, vendorItemId) 또는 (None, None)
    """
    m = re.search(r'itemId=(\d+).*?vendorItemId=(\d+)', url)
    if m:
        return m.group(1), m.group(2)
    # vendorItemId가 itemId 앞에 올 수도 있음
    m2 = re.search(r'vendorItemId=(\d+).*?itemId=(\d+)', url)
    if m2:
        return m2.group(2), m2.group(1)
    return None, None

def _get_item_ids_via_redirect(product_url: str) -> tuple:
    """
    productUrl 리다이렉트 추적으로 itemId/vendorItemId 추출.
    우선순위: URL 직접 파싱 → curl 리다이렉트 → scrapling
    반환: (itemId, vendorItemId) 또는 (None, None)
    """
    import subprocess

    # 1단계: productUrl 자체에 itemId/vendorItemId가 있는지 확인
    item_id, vendor_item_id = _extract_item_ids_from_url(product_url)
    if item_id and vendor_item_id:
        return item_id, vendor_item_id

    # 2단계: curl 리다이렉트 추적
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{redirect_url}",
             "-L", "--max-redirs", "5",
             "-A", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
             product_url],
            capture_output=True, text=True, timeout=10
        )
        redirect_url = result.stdout.strip()
        if redirect_url:
            item_id, vendor_item_id = _extract_item_ids_from_url(redirect_url)
            if item_id and vendor_item_id:
                return item_id, vendor_item_id
    except Exception:
        pass

    return None, None

def _build_complete_coupang_link(product_url: str, item_id: str, vendor_item_id: str) -> str:
    """
    productUrl에 itemId/vendorItemId가 없으면 추가하여 완전한 링크 반환.
    이미 있으면 그대로 반환.
    """
    if 'itemId=' in product_url and 'vendorItemId=' in product_url:
        return product_url  # 이미 완전한 링크
    # pageKey 파라미터 뒤에 삽입
    if '?' in product_url:
        return f"{product_url}&itemId={item_id}&vendorItemId={vendor_item_id}"
    return product_url

def refresh_cache_from_git():
    """git pull로 Actions 캐시 갱신"""
    try:
        import subprocess
        subprocess.run(
            ["git", "-C", str(_BASE_DIR), "pull", "--ff-only", "-q"],
            capture_output=True, timeout=30
        )
    except Exception:
        pass

# ── 공개 API ────────────────────────────────────────────────────────────
def _get(path_with_query: str) -> dict:
    """GET 요청 (다중 폴백)"""
    result = _call_api(path_with_query, "GET")
    # 성공하면 로컬 캐시 저장
    if result.get("rCode") == "0":
        cat_id = re.search(r"bestcategories/(\d+)", path_with_query)
        if cat_id and result.get("data"):
            _save_local_cache(cat_id.group(1), result["data"])
    return result

def _post(path: str, body: dict) -> dict:
    """POST 요청 (다중 폴백)"""
    return _call_api(path, "POST", body)

def get_bestcategory_products(cat_id: int, limit: int = 20) -> list:
    """
    카테고리 베스트 상품 수집
    폴백: API → Actions 캐시 → 로컬 캐시
    """
    path = f"/v2/providers/affiliate_open_api/apis/openapi/products/bestcategories/{cat_id}"
    query = f"limit={limit}&subId={SUB_ID}"
    try:
        r = _get(f"{path}?{query}")
        products = r.get("data", [])
        if products:
            return products
    except Exception as e:
        print(f"  [WARN] bestcategories/{cat_id} 실패: {e}")

    # 캐시 폴백
    cached = _read_cache(str(cat_id))
    if cached:
        print(f"  [캐시 폴백] 카테고리 {cat_id}: {len(cached)}개")
    return cached

def search_products(keyword: str, limit: int = 5) -> list:
    """키워드 검색 (다중 폴백)"""
    encoded = urllib.parse.quote(keyword)
    path = f"/v2/providers/affiliate_open_api/apis/openapi/products/search"
    query = f"keyword={encoded}&limit={limit}&subId={SUB_ID}"
    try:
        r = _get(f"{path}?{query}")
        return r.get("data", [])
    except Exception as e:
        print(f"  [WARN] 검색 실패 ({keyword}): {e}")
        return []

def _get_deeplink_shorten_urls(coupang_urls: list) -> dict:
    """
    쿠팡 파트너스 공식 deeplink API를 사용하여 shortenUrl 일괄 획득.
    - POST /v2/providers/affiliate_open_api/apis/openapi/deeplink
    - body: {"coupangUrls": [...], "subId": "ggultongmon"}
    - 반환: {원본URL: shortenUrl} 딕셔너리 (link.coupang.com/a/... 형태만)
    - 최대 10개씩 배치 처리
    - [규칙] shortenUrl 없으면 해당 상품 skip — productUrl fallback 절대 금지 (노이반님 원칙)
    """
    # [규칙] path는 /openapi/deeplink (v1 없음) — 실제 API 확인 완료
    DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/deeplink"
    SUBID = os.environ.get("COUPANG_SUBID", "ggultongmon")
    result = {}

    if not coupang_urls:
        return result

    # 최대 10개씩 배치
    for i in range(0, len(coupang_urls), 10):
        batch = coupang_urls[i:i + 10]
        try:
            resp = _post(DEEPLINK_PATH, {"coupangUrls": batch, "subId": SUBID})
            data_list = resp.get("data", [])
            # 1차: originalUrl 기반 매핑 (공식 응답 필드)
            for item in data_list:
                orig = item.get("originalUrl", "")
                shorten = item.get("shortenUrl", "")
                if shorten and "link.coupang.com/a/" in shorten and orig:
                    result[orig] = shorten
            # 2차: 순서 기반 fallback (originalUrl 미포함 응답 대비)
            for idx, orig_url in enumerate(batch):
                if orig_url not in result and idx < len(data_list):
                    shorten = data_list[idx].get("shortenUrl", "")
                    if shorten and "link.coupang.com/a/" in shorten:
                        result[orig_url] = shorten
        except Exception as e:
            print(f"  [WARN] deeplink API 배치 실패: {e}")

    return result


def get_products_with_shorten(keyword_or_products, limit: int = 5) -> list:
    """
    상품 수집 + shortenUrl 설정 통합 (쿠팡 파트너스 공식 deeplink API 사용)
    - keyword_or_products: str(키워드) 또는 list(이미 수집된 상품)
    - itemId/vendorItemId 추출 → 완전한 쿠팡 URL 구성
    - deeplink API 일괄 호출 → 공식 shortenUrl(link.coupang.com/a/...) 획득
    - fallback: deeplink 실패 시 productUrl 유지
    """
    try:
        if isinstance(keyword_or_products, str):
            products = search_products(keyword_or_products, limit)
        else:
            products = list(keyword_or_products)

        # 캐시 로드 (한 번만)
        item_id_cache = _load_item_id_cache()

        # 1단계: 각 상품의 itemId/vendorItemId 수집
        products_needing_deeplink = []  # (product, complete_url) 튜플 목록

        for p in products:
            if p.get("shortenUrl") and "link.coupang.com/a/" in p.get("shortenUrl", ""):
                continue  # 이미 공식 shortenUrl이 있으면 건너뜀

            product_url = p.get("productUrl", "#")
            product_id = str(p.get("productId", ""))

            # itemId/vendorItemId 수집 우선순위:
            # 1. productUrl에 직접 포함된 경우
            item_id, vendor_item_id = _extract_item_ids_from_url(product_url)

            if not (item_id and vendor_item_id):
                # 2. 로컬 캐시에서 조회
                if product_id and product_id in item_id_cache:
                    cached = item_id_cache[product_id]
                    item_id = cached["itemId"]
                    vendor_item_id = cached["vendorItemId"]
                    print(f"  [캐시] {product_id}: itemId={item_id}")

            if not (item_id and vendor_item_id):
                # 3. 리다이렉트 추적으로 추출
                if product_url and product_url != "#":
                    print(f"  [리다이렉트] {product_id} itemId 추출 중...")
                    item_id, vendor_item_id = _get_item_ids_via_redirect(product_url)
                    if item_id and vendor_item_id:
                        print(f"  [성공] itemId={item_id}, vendorItemId={vendor_item_id}")
                        if product_id:
                            _save_item_id_cache(product_id, item_id, vendor_item_id)
                            item_id_cache[product_id] = {"itemId": item_id, "vendorItemId": vendor_item_id}

            if item_id and vendor_item_id:
                # 완전한 쿠팡 상품 URL 구성
                complete_url = (
                    f"https://www.coupang.com/vp/products/{product_id}"
                    f"?itemId={item_id}&vendorItemId={vendor_item_id}"
                )
                products_needing_deeplink.append((p, complete_url))
                # 캐시 업데이트
                if product_id and product_id not in item_id_cache:
                    _save_item_id_cache(product_id, item_id, vendor_item_id)
                    item_id_cache[product_id] = {"itemId": item_id, "vendorItemId": vendor_item_id}
            else:
                # [규칙] itemId 없어도 productUrl fallback 금지 — 해당 상품 skip (노이반님 원칙)
                print(f"  [SKIP] {product_id}: itemId 없음 — shortenUrl 불가, 상품 제외")
                p["_skip"] = True

        # 2단계: deeplink API 일괄 호출
        if products_needing_deeplink:
            all_complete_urls = [url for _, url in products_needing_deeplink]
            print(f"  [deeplink] {len(all_complete_urls)}개 상품 shortenUrl 요청 중...")
            url_to_shorten = _get_deeplink_shorten_urls(all_complete_urls)
            print(f"  [deeplink] {len(url_to_shorten)}개 shortenUrl 획득")

            for p, complete_url in products_needing_deeplink:
                shorten = url_to_shorten.get(complete_url)
                if shorten and "link.coupang.com/a/" in shorten:
                    p["shortenUrl"] = shorten
                    print(f"  [OK] {p.get('productId')}: {shorten}")
                else:
                    # [규칙] deeplink 실패해도 productUrl fallback 절대 금지 — skip (노이반님 원칙)
                    print(f"  [SKIP] {p.get('productId')}: deeplink 실패 — 상품 제외")
                    p["_skip"] = True

        # skip 표시 상품 제거
        products = [p for p in products if not p.get("_skip")]

        return products
    except Exception as e:
        print(f"[WARN] 상품 수집 실패: {e}")
        return []

# ── 이미지 유틸리티 ────────────────────────────────────────────────────────
def optimize_coupang_img(url: str, width: int = 400) -> str:
    """
    쿠팡 CDN 이미지 URL 최적화
    - image10.coupangcdn.com 형태에 width 파라미터 추가
    - 썸네일용(300px) / 본문용(600px) / 대표(1200px) 분리
    """
    if not url:
        return ""
    # 이미 파라미터가 있으면 교체
    if "?w=" in url or "&w=" in url:
        url = re.sub(r"[?&]w=\d+", "", url)
    # coupangcdn 이미지는 w 파라미터로 리사이즈 가능
    if "coupangcdn.com" in url or "coupang.com" in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}w={width}"
    return url

def get_product_images(product: dict) -> dict:
    """
    상품의 이미지 3종 반환:
    - thumb: 썸네일 (300px) — 상품 카드용
    - medium: 중간 (600px) — 본문 삽입용
    - og: 대표 이미지 (1200px) — OG/JSON-LD용
    """
    base_url = product.get("productImage", "")
    if not base_url:
        return {"thumb": "", "medium": "", "og": ""}
    return {
        "thumb":  optimize_coupang_img(base_url, width=300),
        "medium": optimize_coupang_img(base_url, width=600),
        "og":     optimize_coupang_img(base_url, width=1200),
    }

def download_product_image(image_url: str, save_path: str) -> bool:
    """쿠팡 상품 이미지 다운로드 (로컬 저장)"""
    try:
        req = urllib.request.Request(
            image_url,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.coupang.com"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            Path(save_path).write_bytes(r.read())
        return True
    except Exception as e:
        print(f"이미지 다운로드 실패: {e}")
        return False

def get_shorten_urls(product_urls: list) -> dict:
    """
    상품 URL → shortenUrl (공식 deeplink API 호출)
    - [규칙] 반드시 link.coupang.com/a/... 형태만 반환 (노이반님 원칙)
    - deeplink 실패한 URL은 결과에서 제외 (raw URL fallback 절대 금지)
    """
    # deeplink API로 실제 shortenUrl 획득
    return _get_deeplink_shorten_urls(product_urls)

# ── CLI 테스트 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("=== 쿠팡 API 연결 테스트 ===")
        print(f"ACCESS_KEY: {ACCESS_KEY[:10]}...")

        # 프록시 탐색
        print("\n[1] 작동 프록시 탐색 중...")
        proxy = _get_working_proxy()
        print(f"  → {proxy if proxy else '없음 (직접 연결 시도)'}")

        # 카테고리 수집
        print("\n[2] 카테고리 1016 테스트...")
        products = get_bestcategory_products(1016, limit=3)
        print(f"  → {len(products)}개")
        for p in products[:2]:
            imgs = get_product_images(p)
            print(f"  - {p.get('productName','')[:30]}")
            print(f"    thumb: {imgs['thumb'][:60]}")
            print(f"    url:   {p.get('productUrl','')[:60]}")
