#!/usr/bin/env python3
"""
seo_title_helper.py — 네이버·구글 자동완성 기반 SEO 제목 생성 헬퍼

사용법:
    from seo_title_helper import get_seo_keywords, build_seo_title_prompt

핵심 기능:
    1. 네이버/구글 자동완성 수집 → 실제 검색어 파악
    2. 검색량 높은 키워드 조합 → Claude 프롬프트에 주입
    3. 제목 길이/형식 검증
"""
import re
import time
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def naver_autocomplete(keyword: str, max_results: int = 8) -> list[str]:
    """네이버 자동완성 API"""
    try:
        url = (
            f"https://ac.search.naver.com/nx/ac"
            f"?q={requests.utils.quote(keyword)}&st=100&r_format=json"
            f"&r_enc=UTF-8&l_enc=UTF-8&c=1&q_enc=UTF-8&t_koreng=1"
        )
        r = requests.get(url, headers={"User-Agent": UA}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [[]])[0] if data.get("items") else []
            return [item[0] for item in items[:max_results] if item]
    except Exception:
        pass
    return []


def google_autocomplete(keyword: str, max_results: int = 8) -> list[str]:
    """구글 자동완성 API"""
    try:
        url = (
            f"https://suggestqueries.google.com/complete/search"
            f"?client=firefox&hl=ko&q={requests.utils.quote(keyword)}"
        )
        r = requests.get(url, headers={"User-Agent": UA}, timeout=5)
        if r.status_code == 200:
            return r.json()[1][:max_results]
    except Exception:
        pass
    return []


def get_seo_keywords(product_name: str, search_keyword: str = "") -> dict:
    """
    상품명 / 검색 키워드 기반으로 네이버+구글 자동완성 수집.
    반환: {
        "naver": [...],
        "google": [...],
        "combined": [...]   # 중복 제거 통합
    }
    """
    base = search_keyword or product_name

    # 핵심 키워드 추출 (브랜드+모델 2~3단어)
    words = re.sub(r'\[[^\]]*\]', '', base).split()
    short = " ".join(words[:3])

    naver_kws = naver_autocomplete(short)
    time.sleep(0.3)
    google_kws = google_autocomplete(short)

    # 상품명 전체로도 추가 조회
    if len(words) > 3:
        full_kws = naver_autocomplete(" ".join(words[:4]))
        naver_kws = list(dict.fromkeys(naver_kws + full_kws))[:10]

    combined = list(dict.fromkeys(naver_kws + [g for g in google_kws if g not in naver_kws]))[:12]

    return {
        "base_keyword": short,
        "naver": naver_kws,
        "google": google_kws,
        "combined": combined,
    }


def build_seo_title_prompt(
    product_name: str,
    search_keyword: str = "",
    price: int = 0,
    discount_rate: float = 0,
    blog_type: str = "ggultongmon",  # ggultongmon | aikeeper | allsweep | naver
    max_len: int = 30,
) -> tuple[str, list[str]]:
    """
    SEO 최적화 제목 생성용 프롬프트 반환.
    반환: (prompt_text, seo_keywords_list)
    """
    seo = get_seo_keywords(product_name, search_keyword)
    kws = seo["combined"]

    price_str = f"{price:,}원" if price else ""
    disc_str = f" ({int(discount_rate)}% 할인)" if discount_rate >= 5 else ""

    # 블로그별 제목 스타일 가이드
    style_guides = {
        "ggultongmon": "쿠팡 파트너스 실생활 비교 블로그. 1인칭 경험담, 가격 비교, 감정 자극형.",
        "aikeeper": "AI·테크 정보 블로그. 검색 의도 중심, 정보성, 롱테일 키워드.",
        "allsweep": "생활용품·리뷰 블로그. 솔직 후기, 가성비 중심.",
        "naver": "네이버 블로그. 친근한 어투, 정보성 + 구매 유도.",
    }
    style = style_guides.get(blog_type, style_guides["ggultongmon"])

    prompt = f"""다음 상품의 블로그 포스트 제목을 SEO 최적화하여 생성하세요.

【상품 정보】
- 상품명: {product_name}
- 가격: {price_str}{disc_str}
- 블로그 스타일: {style}

【네이버·구글 실제 자동완성 검색어 (사람들이 실제로 검색하는 키워드)】
{chr(10).join(f"  - {kw}" for kw in kws[:10])}

【제목 생성 규칙】
1. 위 자동완성 검색어 중 1~2개를 제목에 자연스럽게 포함 (검색 유입 극대화)
2. 제목 길이: {max_len}자 이내 (네이버 검색 결과 잘림 방지)
3. 이모지·em dash(—) 사용 금지
4. 아래 스타일 중 상황에 맞는 것 선택:
   - 후기형: "{kws[0] if kws else product_name[:10]} 직접 써봤습니다"
   - 비교형: "비슷한 가격대 중 이게 달랐습니다"
   - 정보형: "{kws[1] if len(kws)>1 else ''} 고를 때 이것만 보세요"
   - 구매가이드형: "사기 전 꼭 확인해야 할 것들"
5. 검색자의 구매 의도가 담긴 구체적 표현 사용

제목만 1줄로 출력하세요. 다른 설명 불필요."""

    return prompt, kws


def validate_title(title: str, max_len: int = 30) -> dict:
    """제목 유효성 검사"""
    return {
        "ok": len(title) <= max_len and title.strip(),
        "length": len(title),
        "has_emoji": bool(re.search(r'[^\x00-\x7F\u3131-\u318E\uAC00-\uD7A3\s\w.,!?%\-()]', title)),
        "has_emdash": "—" in title,
    }
