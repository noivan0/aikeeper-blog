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
    channel: str = "ggultongmon",
    related_keywords: list[str] = None,
) -> str:
    """
    검색 자동완성 + 연관검색어 기반 제목 생성 프롬프트 블록 반환.
    대장 지시: 전 파이프라인 동일 문구 적용.
    """
    auto_list = "\n".join(f"  - {kw}" for kw in search_keywords[:8]) or "  (수집 실패)"
    related_list = ""
    if related_keywords:
        related_list = "\n연관 검색어:\n" + "\n".join(f"  - {kw}" for kw in related_keywords[:6])

    return f"""
[🔍 SEO 제목 필수 규칙 — 반드시 준수]
아래는 실제 사용자가 검색하는 키워드입니다 (네이버+구글 자동완성+연관검색어):

검색 자동완성:
{auto_list}{related_list}

제목 작성 규칙:
1. 위 키워드 중 정확히 1개를 제목에 그대로 포함할 것 (변형 금지)
2. 포함하지 않은 제목은 무효 — 반드시 재작성
3. 키워드는 제목 앞부분(첫 20자 이내)에 배치할 것 (검색 노출 최적화)
4. 50자 이내, 이모지 금지, em dash(—) 금지
"""

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


def get_seo_keywords(keyword: str, product_name: str = "",
                      include_related: bool = True) -> dict:
    """
    네이버+구글 자동완성 + 연관검색어(suffix 변형) 통합 반환.

    반환:
        naver:          네이버 자동완성
        google:         구글 자동완성
        naver_related:  네이버 suffix 연관검색어
        google_related: 구글 suffix 연관검색어
        combined:       전체 통합 (중복제거, 상위 15개)
    """
    query = product_name if product_name else keyword
    # 상품명이 길면 앞 2단어로 단축 (자동완성 품질 향상)
    words = query.split()
    short_query = " ".join(words[:2]) if len(words) > 2 else query

    naver_kws  = naver_autocomplete(short_query) or naver_autocomplete(keyword)
    google_kws = google_autocomplete(short_query) or google_autocomplete(keyword)

    # 연관검색어 (suffix 변형)
    naver_related, google_related = [], []
    if include_related:
        try:
            rel = get_related_keywords(short_query)
            naver_related  = rel.get("naver_related", [])
            google_related = rel.get("google_related", [])
        except Exception:
            pass

    # 통합 (자동완성 우선, 연관검색어 후)
    seen, combined = set(), []
    for kw in naver_kws + google_kws + naver_related + google_related:
        k = kw.lower().strip()
        if k and k not in seen:
            seen.add(k)
            combined.append(kw)

    return {
        "naver":          naver_kws[:8],
        "google":         google_kws[:8],
        "naver_related":  naver_related[:8],
        "google_related": google_related[:8],
        "combined":       combined[:15],
    }


# 모듈 정상 로드 플래그
_SEO_AVAILABLE = True


# ── 연관검색어 수집 (suffix 변형 방식) ────────────────────────────────────
_RELATED_SUFFIXES = ["추천", "후기", "단점", "비교", "가격"]

def _google_autocomplete_chrome(keyword: str) -> list[str]:
    """구글 chrome client — firefox보다 많은 결과 반환."""
    q = urllib.parse.quote(keyword)
    url = f"https://suggestqueries.google.com/complete/search?client=chrome&q={q}&hl=ko"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data[1][:10] if len(data) > 1 else []
    except Exception:
        return []


def get_related_keywords(keyword: str, max_per_suffix: int = 3) -> dict[str, list[str]]:
    """
    suffix 변형으로 연관검색어 효과 구현.
    네이버/구글 검색창 연관검색어 HTML 파싱은 봇 차단이 심해
    자동완성 suffix 변형으로 동등한 효과를 얻음.

    반환: {"naver_related": [...], "google_related": [...]}
    """
    words = keyword.split()
    base = " ".join(words[:2]) if len(words) > 2 else keyword

    naver_related, google_related = [], []
    seen_n, seen_g = set(), set()

    for suf in _RELATED_SUFFIXES:
        query = f"{base} {suf}"
        # 네이버
        n_kws = naver_autocomplete(query)[:max_per_suffix]
        for kw in n_kws:
            k = kw.lower().strip()
            if k not in seen_n and k != base.lower():
                seen_n.add(k)
                naver_related.append(kw)
        # 구글
        g_kws = _google_autocomplete_chrome(query)[:max_per_suffix]
        for kw in g_kws:
            k = kw.lower().strip()
            if k not in seen_g and k != base.lower():
                seen_g.add(k)
                google_related.append(kw)
        time.sleep(0.15)

    return {
        "naver_related": naver_related[:10],
        "google_related": google_related[:10],
    }
