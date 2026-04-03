"""
쿠팡 파트너스 Open API V1 클라이언트
- HMAC 인증: yyMMddTHHmmssZ 형식 (공식 문서 기준)
- 상품 검색 / shortenUrl 생성 / 이미지 수집
"""
import hmac
import hashlib
import urllib.request
import urllib.parse
import json
import os
import re
from time import gmtime, strftime

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
    auth = generate_hmac("GET", path_with_query)
    req = urllib.request.Request(
        DOMAIN + path_with_query,
        headers={"Authorization": auth, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _post(path: str, body: dict) -> dict:
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
    """
    products = search_products(keyword, limit)
    
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
