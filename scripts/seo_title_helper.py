#!/usr/bin/env python3
"""
seo_title_helper.py — 검색 자동완성 기반 SEO 제목 최적화 헬퍼
P004/P005 모든 채널 공용

주요 함수:
  get_seo_keywords(keyword, product_name="") → {"combined": [키워드 리스트]}
  build_seo_title_prompt(product_name, search_keyword, channel="p005") → (prompt, keywords)
  validate_title(title, keywords) → bool
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    from search_autocomplete import get_search_keywords, google_autocomplete
    _AVAIL = True
except ImportError:
    _AVAIL = False
    def get_search_keywords(kw, pname=""): return []
    def google_autocomplete(kw, lang="ko"): return []


def get_seo_keywords(keyword: str, product_name: str = "") -> dict:
    """
    키워드 기반 SEO 검색어 수집.
    반환: {"combined": [키워드 리스트], "google": [...], "naver": [...]}
    """
    if not _AVAIL:
        return {"combined": [], "google": [], "naver": []}
    
    keywords = get_search_keywords(keyword, product_name)
    return {
        "combined": keywords,
        "google": keywords,
        "naver": [],  # 네이버 자동완성은 서버 차단으로 비활성
    }


def build_seo_title_prompt(
    product_name: str,
    search_keyword: str = "",
    channel: str = "p005"
) -> tuple[str, list]:
    """
    SEO 최적화 제목 생성 프롬프트 + 수집된 키워드 반환.
    
    반환: (prompt_text, keywords_list)
    """
    kw = search_keyword or product_name
    keywords = get_search_keywords(kw, product_name)[:10]
    
    if not keywords:
        return "", []
    
    kw_list = "\n".join(f"  - {k}" for k in keywords)
    
    channel_style = {
        "p005": ("상품 솔직 후기/비교 (직접 사용, 구체적, 신뢰)", '"직접 써봤습니다" / "솔직 후기" / "2주 사용 결과"'),
        "ggultongmon": ("쇼핑 감정 자극/비교 (궁금증, 경험담)", '"이거 모르고 사면 두 번 삽니다" / "9천원짜리가 낫다고요"'),
        "aikeeper": ("AI/기술 실용 정보 (최신, 핵심, 5분 요약)", '"코딩 없이 10분" / "2026년 최신 기준"'),
        "allsweep": ("뉴스 요약 (오늘, 핵심, 지금)", '"오늘 꼭 알아야 할" / "지금 확인하세요"'),
    }
    style, example = channel_style.get(channel, channel_style["p005"])
    
    prompt = f"""[SEO 제목 최적화 — 검색 자동완성 기반]
상품/주제: {product_name}

아래는 실제 사용자가 검색하는 구글 자동완성 키워드입니다:
{kw_list}

제목 작성 필수 규칙:
1. 위 검색어 중 1~2개를 제목에 자연스럽게 포함 (검색 유입 직결 — 가장 중요)
2. 채널 스타일: {style}
3. 예시: {example}
4. 40자 이내, 이모지 금지
5. 검색 의도: 구매 전 비교/후기 탐색 단계 타겟
"""
    return prompt, keywords


def validate_title(title: str, keywords: list) -> bool:
    """
    제목에 SEO 키워드가 포함됐는지 검증.
    최소 1개 키워드 포함 시 True.
    """
    if not keywords:
        return True  # 키워드 없으면 검증 스킵
    title_lower = title.lower()
    return any(kw.lower()[:8] in title_lower for kw in keywords[:5])


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    result = get_seo_keywords(kw)
    print(f"[{kw}] 검색 키워드:")
    for k in result["combined"]:
        print(f"  {k}")
    prompt, kws = build_seo_title_prompt(kw, kw, "p005")
    print(f"\n프롬프트:\n{prompt}")
