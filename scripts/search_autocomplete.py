#!/usr/bin/env python3
"""
search_autocomplete.py — 구글/네이버 검색 자동완성 기반 키워드 수집
모든 채널(ggultongmon, aikeeper, allsweep, P005)에서 공용 사용

사용법:
    from search_autocomplete import get_search_keywords
    keywords = get_search_keywords("에어프라이어 추천")
    # → ["에어프라이어 추천 1인가구", "에어프라이어 추천 10만원대", ...]
"""
import urllib.request
import urllib.parse
import json
import time


def google_autocomplete(keyword: str, lang: str = "ko") -> list[str]:
    """구글 자동완성 API — 실시간 검색어 제안"""
    q = urllib.parse.quote(keyword)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={lang}&q={q}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data[1][:10] if len(data) > 1 else []
    except Exception:
        return []


def get_search_keywords(base_keyword: str, product_name: str = "") -> list[str]:
    """
    상품명 기반 구글 자동완성 키워드 수집.
    
    전략:
    1. 상품명 직접 검색 (단어 + 추천/후기/가격/단점/비교)
    2. 중복 제거 + 정렬
    3. 검색량 높은 키워드 우선 (자동완성 순서 = 검색량 순)
    
    반환: 검색어 리스트 (최대 15개)
    """
    results = []

    # 1. 기본 키워드
    results += google_autocomplete(base_keyword)
    time.sleep(0.2)

    # 2. 상품명이 따로 있으면 추가 수집
    if product_name and product_name != base_keyword:
        short_name = product_name[:20]  # 너무 긴 상품명 단축
        results += google_autocomplete(short_name)
        time.sleep(0.2)

    # 3. 구매 의도 변형 키워드 수집
    for suffix in ["추천", "후기", "가격", "단점", "비교"]:
        kw = f"{base_keyword} {suffix}"
        suggestions = google_autocomplete(kw)
        results += suggestions[:3]  # suffix당 상위 3개만
        time.sleep(0.15)

    # 중복 제거 + base_keyword 자체 제외
    seen = set()
    filtered = []
    for kw in results:
        kw = kw.strip()
        if kw and kw != base_keyword and kw not in seen:
            seen.add(kw)
            filtered.append(kw)

    return filtered[:15]


def build_seo_title_prompt(
    base_keyword: str,
    product_name: str,
    search_keywords: list[str],
    channel: str = "ggultongmon"
) -> str:
    """
    검색 자동완성 기반 제목 생성 프롬프트 블록 반환.
    각 채널의 Claude 프롬프트에 삽입용.
    """
    kw_list = "\n".join(f"  - {kw}" for kw in search_keywords[:10])

    if channel == "ggultongmon":
        style = "쇼핑 비교/후기 (감정 자극, 경험담, 궁금증 유발)"
        example = '"9천원짜리가 2만원짜리보다 낫다고요" / "이거 모르고 사면 두 번 삽니다"'
    elif channel == "aikeeper":
        style = "AI/기술 정보 (실용성, 최신성, 핵심 전달)"
        example = '"코딩 없이 10분 만에" / "2026년 최신 기준으로 정리했습니다"'
    elif channel == "allsweep":
        style = "뉴스/정보 요약 (핵심, 오늘, 지금)"
        example = '"오늘 꼭 알아야 할" / "지금 바로 확인하세요"'
    else:  # p005
        style = "브랜드커넥트 상품 후기 (솔직, 직접 경험, 구체적)"
        example = '"직접 써봤습니다" / "솔직 후기" / "2주 써본 결과"'

    return f"""
[SEO 제목 최적화 — 검색 자동완성 기반]
상품/주제: {base_keyword}
검색 유입 극대화를 위해 아래 실제 검색어를 제목에 반드시 반영하세요:

{kw_list}

제목 작성 원칙:
1. 위 검색어 중 1~2개를 제목에 자연스럽게 포함 (검색 유입 직결)
2. 채널 스타일({style}) 유지
3. 예시: {example}
4. 50자 이내, 이모지 금지
5. 검색 의도 매칭: 구매 전 비교/후기 탐색 단계 타겟
"""


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    print(f"[{kw}] 검색 자동완성 키워드:")
    keywords = get_search_keywords(kw)
    for k in keywords:
        print(f"  {k}")
    print()
    print(build_seo_title_prompt(kw, kw, keywords, "ggultongmon"))

def naver_autocomplete(keyword: str) -> list[str]:
    """네이버 자동완성 API."""
    url = (
        "https://ac.search.naver.com/nx/ac"
        f"?q={urllib.parse.quote(keyword)}"
        "&q_enc=UTF-8&st=100&frm=nx&r_format=json&r_enc=UTF-8&r_unicode=1"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://search.naver.com/",
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        keywords = []
        for group in data.get("items", []):
            for item in group:
                kw = item[0] if isinstance(item, list) else item
                if isinstance(kw, str) and kw.strip():
                    keywords.append(kw.strip())
        return keywords[:10]
    except Exception:
        return []


def get_seo_keywords(keyword: str, product_name: str = "") -> dict:
    """네이버+구글 자동완성 통합 반환."""
    query = product_name if product_name else keyword
    # 상품명이 길면 앞 2~3단어로 단축 (자동완성 결과 품질 향상)
    words = query.split()
    short_query = " ".join(words[:2]) if len(words) > 2 else query
    naver_kws = naver_autocomplete(short_query)
    if not naver_kws and short_query != keyword:
        naver_kws = naver_autocomplete(keyword)
    google_kws = google_autocomplete(short_query)
    if not google_kws and short_query != keyword:
        google_kws = google_autocomplete(keyword)
    seen, combined = set(), []
    for kw in naver_kws + google_kws:
        k = kw.lower().strip()
        if k and k not in seen:
            seen.add(k)
            combined.append(kw)
    return {"naver": naver_kws[:8], "google": google_kws[:8], "combined": combined[:10]}


# 모듈 정상 로드 플래그
_SEO_AVAILABLE = True
