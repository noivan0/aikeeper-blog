#!/usr/bin/env python3
"""
seo_title_helper.py — 네이버+구글 검색 자동완성 통합 SEO 제목 헬퍼
P004/P005 전 채널 공용 단일 모듈 (경로 의존성 없음)

주요 함수:
  get_seo_keywords(keyword, product_name="") → {"combined": [...], "naver": [...], "google": [...]}
  build_seo_title_prompt(product_name, search_keyword, channel) → (prompt, keywords)
  validate_title(title, keywords) → bool
"""
import json
import time
import urllib.parse
import urllib.request
import os
import sys


# ── 네이버 자동완성 ──────────────────────────────────────────────────
def naver_autocomplete(keyword: str) -> list[str]:
    """네이버 검색 자동완성 (ac.search.naver.com)"""
    q = urllib.parse.quote(keyword)
    url = (
        f"https://ac.search.naver.com/nx/ac"
        f"?q={q}&q_enc=UTF-8&st=100&frm=nv"
        f"&r_format=json&r_enc=UTF-8&_callback="
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.naver.com/",
        "Accept": "*/*",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read().decode("utf-8").strip()
            data = json.loads(raw)
            items = data.get("items", [[]])[0]
            return [item[0] for item in items if isinstance(item, list) and item]
    except Exception:
        return []


# ── 구글 자동완성 ──────────────────────────────────────────────────
def google_autocomplete(keyword: str, lang: str = "ko") -> list[str]:
    """구글 검색 자동완성 (suggestqueries.google.com)"""
    q = urllib.parse.quote(keyword)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={lang}&q={q}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data[1][:10] if len(data) > 1 else []
    except Exception:
        return []


# ── 통합 수집 ─────────────────────────────────────────────────────
def get_seo_keywords(keyword: str, product_name: str = "") -> dict:
    """
    네이버+구글 자동완성 통합 수집.

    전략:
    1. 네이버 자동완성 (실검 반영, 한국어 특화)
    2. 구글 자동완성 (글로벌 검색 트렌드)
    3. 구매 의도 변형 키워드 (추천/후기/가격/단점/비교)
    4. 중복 제거 + 네이버 우선 정렬

    반환:
      {"combined": [...], "naver": [...], "google": [...]}
    """
    naver_kws: list[str] = []
    google_kws: list[str] = []

    # 1. 기본 키워드
    naver_kws += naver_autocomplete(keyword)
    time.sleep(0.15)
    google_kws += google_autocomplete(keyword)
    time.sleep(0.1)

    # 2. 상품명이 따로 있으면 추가
    if product_name and product_name != keyword:
        short = product_name[:20]
        naver_kws += naver_autocomplete(short)
        time.sleep(0.1)
        google_kws += google_autocomplete(short)
        time.sleep(0.1)

    # 3. 구매 의도 변형
    for suffix in ["추천", "후기", "단점", "가격", "비교"]:
        combo = f"{keyword} {suffix}"
        naver_kws += naver_autocomplete(combo)[:3]
        google_kws += google_autocomplete(combo)[:2]
        time.sleep(0.1)

    # 중복 제거 (네이버 우선)
    def dedup(lst: list[str], base: str) -> list[str]:
        seen = set()
        result = []
        for kw in lst:
            kw = kw.strip()
            if kw and kw != base and kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

    naver_clean = dedup(naver_kws, keyword)[:12]
    google_clean = dedup(google_kws, keyword)[:10]

    # 네이버 우선, 구글 보완
    combined_seen = set(naver_clean)
    combined = list(naver_clean)
    for kw in google_clean:
        if kw not in combined_seen:
            combined.append(kw)
            combined_seen.add(kw)

    return {
        "combined": combined[:15],
        "naver": naver_clean,
        "google": google_clean,
    }


# ── 제목 프롬프트 빌더 ────────────────────────────────────────────
def build_seo_title_prompt(
    product_name: str,
    search_keyword: str = "",
    channel: str = "p005",
) -> tuple[str, list[str]]:
    """
    채널별 SEO 최적화 제목 생성 프롬프트 반환.

    반환: (prompt_str, keywords_list)
    """
    kw = search_keyword or product_name
    result = get_seo_keywords(kw, product_name)
    keywords = result["combined"][:10]
    naver_kws = result["naver"][:6]
    google_kws = [k for k in result["google"][:6] if k not in set(naver_kws)]

    if not keywords:
        return "", []

    naver_list = "\n".join(f"  - {k}" for k in naver_kws) if naver_kws else "  (수집 실패)"
    google_list = "\n".join(f"  - {k}" for k in google_kws[:4]) if google_kws else "  (수집 실패)"

    channel_styles = {
        "ggultongmon": (
            "쇼핑 비교/후기 (감정 자극, 경험담, 궁금증 유발)",
            '"9천원짜리가 2만원짜리보다 낫다고요" / "이거 모르고 사면 두 번 삽니다"',
        ),
        "aikeeper": (
            "AI/기술 실용 정보 (최신, 핵심, 5분 완성)",
            '"코딩 없이 10분 만에" / "2026년 최신 기준으로 정리"',
        ),
        "allsweep": (
            "뉴스 요약 (오늘, 핵심, 지금 확인)",
            '"오늘 꼭 알아야 할 5가지" / "지금 바로 확인하세요"',
        ),
        "p005": (
            "브랜드커넥트 상품 솔직 후기 (직접 사용, 구체적, 신뢰)",
            '"직접 써봤습니다" / "솔직 후기, 단점까지" / "2주 사용 결과"',
        ),
    }
    style, example = channel_styles.get(channel, channel_styles["p005"])

    prompt = f"""
[SEO 제목 필수 최적화 — 검색 자동완성 기반]

상품/주제: {product_name}

▼ 실제 사용자 검색어 (네이버 자동완성)
{naver_list}

▼ 실제 사용자 검색어 (구글 자동완성)
{google_list}

━━━ 제목 작성 필수 규칙 ━━━
1. [필수] 위 검색어 중 정확히 1~2개를 제목에 포함할 것
   → 검색 유입 직결. 이 규칙이 가장 중요합니다.
   → 자연스럽지 않으면 단어만 발췌해서 포함 가능
2. 채널 스타일: {style}
3. 참고 문구: {example}
4. 제목 길이: 40자 이내, 이모지 금지
5. 검색 의도 타겟: 구매 전 비교/후기 탐색 단계
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

    return prompt, keywords


# ── 제목 검증 ────────────────────────────────────────────────────
def validate_title(title: str, keywords: list[str]) -> bool:
    """
    제목에 SEO 키워드가 포함됐는지 검증.
    상위 5개 키워드 중 1개 이상 포함 시 True.
    """
    if not keywords:
        return True
    title_lower = title.lower().replace(" ", "")
    for kw in keywords[:5]:
        kw_core = kw.lower().replace(" ", "")[:8]
        if kw_core in title_lower:
            return True
    return False


# ── CLI 테스트 ────────────────────────────────────────────────────
if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "에어프라이어"
    print(f"[{kw}] 네이버+구글 통합 검색어 수집 중...")
    result = get_seo_keywords(kw)
    print(f"\n네이버 자동완성 ({len(result['naver'])}개):")
    for k in result["naver"]:
        print(f"  {k}")
    print(f"\n구글 자동완성 ({len(result['google'])}개):")
    for k in result["google"]:
        print(f"  {k}")
    print(f"\n통합 상위 키워드 ({len(result['combined'])}개):")
    for i, k in enumerate(result["combined"][:8], 1):
        print(f"  {i}. {k}")

    prompt, kws = build_seo_title_prompt(kw, kw, "ggultongmon")
    print(f"\n프롬프트:\n{prompt}")
