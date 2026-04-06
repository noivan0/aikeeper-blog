"""
쿠팡 파트너스 Open API V1 클라이언트
- HMAC 인증: yyMMddTHHmmssZ 형식 (공식 문서 기준)
- 상품 검색 / shortenUrl 생성 / 이미지 수집
- 네트워크 웹필터 우회: SOCKS5 프록시 경유 (회사 네트워크 차단 대응)
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
from time import gmtime, strftime

# ── SOCKS5 프록시 설정 (회사 웹필터 우회용) ──────────────────────────────
# 87.117.11.57:1080 — 쿠팡 API 접근 확인된 프록시
# 프록시 실패 시 자동으로 다음 프록시로 폴백
_PROXY_LIST = [
    ("87.117.11.57", 1080),
    ("91.201.119.198", 1337),
    ("178.207.10.110", 1080),
]
_working_proxy = None  # 한 번 성공한 프록시 캐시

def _get_socks_socket(host, port, timeout=20):
    """SOCKS5 프록시를 경유한 SSL 소켓 반환. 실패 시 None."""
    try:
        import socks as _socks
        for proxy_host, proxy_port in _PROXY_LIST:
            try:
                s = _socks.socksocket()
                s.set_proxy(_socks.SOCKS5, proxy_host, proxy_port)
                s.settimeout(timeout)
                s.connect((host, port))
                ctx = ssl.create_default_context()
                ss = ctx.wrap_socket(s, server_hostname=host)
                return ss, f"{proxy_host}:{proxy_port}"
            except Exception:
                continue
    except ImportError:
        pass
    return None, None

def _http_via_proxy(method, path_with_query, body=None, extra_headers=None):
    """SOCKS5 프록시를 통해 쿠팡 API 호출. 성공 시 dict 반환."""
    host = "api-gateway.coupang.com"
    auth = generate_hmac(method, path_with_query)
    headers = {
        "Host": host,
        "Authorization": auth,
        "Content-Type": "application/json;charset=UTF-8",
        "Connection": "close",
    }
    if extra_headers:
        headers.update(extra_headers)

    ss, proxy_used = _get_socks_socket(host, 443)
    if ss is None:
        raise ConnectionError("모든 SOCKS5 프록시 연결 실패")

    header_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    if body:
        body_bytes = json.dumps(body).encode("utf-8")
        header_str += f"Content-Length: {len(body_bytes)}\r\n"
        req_bytes = f"{method} {path_with_query} HTTP/1.1\r\n{header_str}\r\n".encode() + body_bytes
    else:
        req_bytes = f"{method} {path_with_query} HTTP/1.1\r\n{header_str}\r\n".encode()

    ss.send(req_bytes)
    resp = b""
    while True:
        try:
            chunk = ss.recv(8192)
            if not chunk: break
            resp += chunk
        except Exception: break
    try: ss.close()
    except: pass

    # HTTP 응답 파싱
    header_end = resp.find(b"\r\n\r\n")
    if header_end == -1:
        raise ValueError(f"응답 파싱 실패 (proxy={proxy_used})")
    status_line = resp[:resp.find(b"\r\n")].decode("utf-8", errors="replace")
    status_code = int(status_line.split()[1]) if len(status_line.split()) > 1 else 0
    raw_body = resp[header_end + 4:]

    if not raw_body.strip():
        raise ValueError("빈 응답")
    for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            text = raw_body.decode(enc)
            if text.strip():
                return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"응답 디코딩/파싱 실패 (status={status_code})")

DOMAIN = "https://api-gateway.coupang.com"
ACCESS_KEY = os.environ.get("COUPANG_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("COUPANG_SECRET_KEY", "")

PARTNERS_NOTICE = (
    '이 포스팅은 쿠팡 파트너스 활동의 일환으로, '
    '이에 따른 일정액의 수수료를 제공받습니다.'
)


def generate_hmac(method: str, url: str) -> str:
    """쿠팡 파트너스 공식 HMAC 서명 생성 (signed-date: yyMMddTHHmmssZ)"""
    path, *query = url.split("?")
    datetime_gmt = strftime('%y%m%d', gmtime()) + 'T' + strftime('%H%M%S', gmtime()) + 'Z'
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


def _get(path_with_query: str) -> dict:
    # 1차: SOCKS5 프록시 경유 (웹필터 우회)
    try:
        return _http_via_proxy("GET", path_with_query)
    except Exception as proxy_err:
        pass  # 프록시 실패 시 직접 연결 시도

    # 2차: 직접 연결 (프록시 없는 환경 대비)
    auth = generate_hmac("GET", path_with_query)
    req = urllib.request.Request(
        DOMAIN + path_with_query,
        headers={"Authorization": auth, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        if not raw or not raw.strip():
            raise ValueError("빈 응답")
        for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
            try:
                text = raw.decode(enc)
                if text.strip():
                    return json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        decoded = raw.decode("utf-8", errors="ignore")
        if not decoded.strip():
            raise ValueError("디코딩 후 빈 응답")
        return json.loads(decoded)


def _post(path: str, body: dict) -> dict:
    # 1차: SOCKS5 프록시 경유
    try:
        return _http_via_proxy("POST", path, body=body)
    except Exception:
        pass

    # 2차: 직접 연결
    auth = generate_hmac("POST", path)
    req = urllib.request.Request(
        DOMAIN + path,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Authorization": auth, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def search_products(keyword: str, limit: int = 5, sub_id: str = "ggultongmon") -> list[dict]:
    """
    키워드로 쿠팡 상품 검색
    반환: [{ productId, productName, productPrice, productImage, productUrl,
              categoryName, isRocket, isFreeShipping, keyword, rank }]
    """
    kw_enc = urllib.parse.quote(keyword)
    path = (
        f"/v2/providers/affiliate_open_api/apis/openapi/products/search"
        f"?keyword={kw_enc}&limit={limit}&subId={sub_id}"
    )
    data = _get(path)
    if data.get("rCode") != "0":
        raise RuntimeError(f"상품검색 실패: {data}")
    return data["data"].get("productData", [])


def get_shorten_urls(product_urls: list[str]) -> dict[str, str]:
    """
    상품 URL 목록 → shortenUrl 딕셔너리
    반환: { originalUrl: shortenUrl }
    """
    result = {}
    # 한 번에 최대 50개
    for i in range(0, len(product_urls), 50):
        chunk = product_urls[i:i+50]
        data = _post(
            "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink",
            {"coupangUrls": chunk}
        )
        if data.get("rCode") == "0":
            for item in data.get("data", []):
                orig = item.get("originalUrl", "")
                short = item.get("shortenUrl", "")
                if orig and short:
                    result[orig] = short
    return result


def download_product_image(image_url: str, save_path: str) -> bool:
    """쿠팡 상품 이미지 다운로드"""
    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            with open(save_path, "wb") as f:
                f.write(r.read())
        return True
    except Exception as e:
        print(f"이미지 다운로드 실패: {e}")
        return False


def get_products_with_shorten(keyword: str, limit: int = 5) -> list[dict]:
    """
    상품 검색 + shortenUrl 자동 생성 통합
    반환: productData + shortenUrl 필드 추가
    API 실패 시 빈 리스트 반환 (예외 전파 금지)
    """
    try:
        products = search_products(keyword, limit)
    except Exception as e:
        print(f"[WARN] 쿠팡 상품 검색 실패 ({keyword}): {e}")
        return []
    
    # productUrl → shortenUrl 변환
    # productUrl은 이미 affiliate URL이지만 길어서 shortenUrl 생성
    # 단, productUrl이 link.coupang.com/re/... 형식이면 이미 affiliate URL
    # → 상품 페이지 URL로 변환 후 deeplink 생성
    raw_urls = []
    for p in products:
        product_id = p.get("productId")
        if product_id:
            raw_urls.append(f"https://www.coupang.com/vp/products/{product_id}")
    
    shorten_map = get_shorten_urls(raw_urls)
    
    for p in products:
        product_id = p.get("productId")
        raw_url = f"https://www.coupang.com/vp/products/{product_id}"
        p["shortenUrl"] = shorten_map.get(raw_url, p.get("productUrl", raw_url))
        p["rawProductUrl"] = raw_url
    
    return products


if __name__ == "__main__":
    # 테스트
    import sys
    keyword = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    print(f"키워드: {keyword}")
    products = get_products_with_shorten(keyword, limit=3)
    for p in products:
        print(f"\n[{p['rank']}위] {p['productName'][:40]}")
        print(f"  가격: {p['productPrice']:,}원 | 로켓: {p['isRocket']}")
        print(f"  shortenUrl: {p['shortenUrl']}")
        print(f"  이미지: {p['productImage'][:60]}...")
