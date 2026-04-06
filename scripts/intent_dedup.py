"""
intent_dedup.py — 검색 의도(Search Intent) 기반 중복 판단 공통 모듈
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
핵심 철학:
  같은 키워드여도 검색 의도가 다르면 다른 주제 → 중복 아님
  예) "Claude API 사용법" vs "Claude vs ChatGPT 비교" → 허용

Intent 유형:
  - how-to:    사용법, 방법, 설치, 시작, 입문
  - comparison: vs, 비교, 차이, 골라, 선택
  - problem:   오류, 에러, 해결, 문제
  - review:    후기, 리뷰, 실제 사용, 경험
  - news:      출시, 발표, 업데이트, 공개
  - roundup:   추천, TOP, 순위, 정리
  - general:   기타

사용법:
    from intent_dedup import is_duplicate, get_search_intent
"""
import re
import math


# ── 불용어 (내용어 겹침 판단에서 제외) ──────────────────────────────────────
_STOPWORDS = {
    "ai", "vs", "2026", "2025", "2024", "한국", "방법", "도구", "서비스", "기능",
    "비교", "추천", "완전", "정리", "가이드", "완벽", "실제", "사용", "활용",
    "최신", "정보", "소개", "분석", "전략", "이유", "방식", "관련", "통해",
    "le", "chat", "the", "for", "and", "to", "in", "of",
    "있는", "하는", "이다", "위한", "대한", "인가", "인지", "것은",
}


def get_words(text: str) -> set:
    return set(re.findall(r"[\w가-힣]{2,}", text.lower()))


def get_words_list(text: str) -> list:
    return re.findall(r"[\w가-힣]{2,}", text.lower())


def bigrams(text: str) -> set:
    words = get_words_list(text)
    return {(words[i], words[i + 1]) for i in range(len(words) - 1)}


def get_content_words(text: str) -> set:
    """불용어 제거 후 내용어만 반환"""
    return {w for w in get_words(text) if w not in _STOPWORDS and len(w) >= 3}


def similarity(a: str, b: str) -> float:
    """자카드 유사도 (단어 + 바이그램 평균)"""
    wa, wb = get_words(a.lower()), get_words(b.lower())
    ba, bb = bigrams(a.lower()), bigrams(b.lower())
    ws = len(wa & wb) / len(wa | wb) if wa | wb else 0.0
    bs = len(ba & bb) / len(ba | bb) if ba | bb else 0.0
    return (ws + bs) / 2.0


def get_search_intent(text: str) -> str:
    """검색 의도 분류"""
    t = text.lower()
    if any(w in t for w in ["vs", "비교", "차이", "골라", "선택", "어느쪽", "어떤게"]):
        return "comparison"
    if any(w in t for w in ["사용법", "하는법", "방법", "설치", "연동", "시작", "입문",
                              "완전정복", "따라하기", "처음", "기초", "how to"]):
        return "how-to"
    if any(w in t for w in ["오류", "에러", "문제", "해결", "안될때", "막히는", "실패"]):
        return "problem"
    if any(w in t for w in ["후기", "리뷰", "실제", "써봤", "사용해봤", "경험", "솔직"]):
        return "review"
    if any(w in t for w in ["출시", "발표", "업데이트", "새로운", "공개", "등장", "런칭"]):
        return "news"
    if any(w in t for w in ["추천", "top", "best", "순위", "정리", "총정리", "모음"]):
        return "roundup"
    return "general"


# 핵심 주제 키워드 그룹 — 같은 그룹 키워드 + 같은 Intent → 중복
_TOPIC_KEY_GROUPS = [
    {"claude", "클로드", "anthropic"},
    {"chatgpt", "gpt", "openai", "오픈ai"},
    {"gemini", "bard", "구글ai"},
    {"llm", "llama", "라마", "mistral"},
    {"kling", "runway", "sora", "pika", "veo"},
    {"cursor", "copilot", "windsurf", "codeium"},
    {"perplexity", "검색ai", "ai검색"},
    {"자율주행", "tesla", "테슬라"},
    {"반도체", "gpu", "nvidia", "엔비디아"},
    {"네이버", "카카오", "국산ai", "clova"},
]


def topic_key_overlap(a: str, b: str) -> bool:
    """핵심 키워드 그룹 겹침 + 검색 의도 동시 충족 시 True"""
    wa, wb = get_words(a.lower()), get_words(b.lower())
    for group in _TOPIC_KEY_GROUPS:
        if (group & wa) and (group & wb):
            # 같은 그룹 단어가 겹치더라도 Intent가 다르면 허용
            if get_search_intent(a) == get_search_intent(b):
                return True
    return False


def is_duplicate(query: str, used: set, threshold: float = 0.30) -> bool:
    """
    검색 의도(Search Intent) 기반 중복 판단.

    중복 조건 (모두 AND):
      1. 전체 제목 유사도 >= threshold, OR
      2. 내용어(불용어 제외) 3개 이상 겹침 + 같은 Intent, OR
      3. 핵심 키워드 그룹 겹침 + 같은 Intent

    허용 케이스:
      - 같은 툴명(Claude, Kling 등) + 다른 Intent → 중복 아님
      - 불용어(ai, vs, 2026 등)만 겹침 → 중복 아님
    """
    if not query or not used:
        return False

    q = query.lower()
    q_intent = get_search_intent(q)
    q_content = get_content_words(q)

    for u in used:
        ul = u.lower()
        # 1. 전체 제목 유사도
        if similarity(q, ul) >= threshold:
            return True
        # 2. 내용어 겹침 + 같은 Intent
        shared = q_content & get_content_words(ul)
        if len(shared) >= 3 and q_intent == get_search_intent(ul):
            return True
        # 3. 핵심 키워드 그룹 + 같은 Intent
        if topic_key_overlap(q, ul):
            return True

    return False


# ── 자가 테스트 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("Kling AI vs Runway vs Sora: 크리에이터 비교",
         "kling ai 사용법 2026: ai 영상 만들기 5단계",
         False, "비교 vs how-to → 허용"),

        ("Kling AI vs Runway vs Sora",
         "미스트랄 le chat vs perplexity ai: 무료 ai 검색 도구",
         False, "다른 툴 비교 → 허용"),

        ("ChatGPT 사용법 완전 입문",
         "chatgpt 시작하는 법 초보자 정복",
         True, "같은툴+같은의도 → 중복"),

        ("Claude vs ChatGPT: 마케터 선택",
         "claude api 사용법 개발자 가이드",
         False, "비교 vs how-to → 허용"),

        ("네이버 AI vs 카카오 AI: 소상공인 비교",
         "미스트랄 vs perplexity: 무료 ai 비교",
         False, "다른 툴 비교 → 허용"),
    ]

    ok = 0
    for q, u, expected, desc in tests:
        result = is_duplicate(q, {u})
        status = "✅" if result == expected else "❌"
        if result == expected:
            ok += 1
        q_i = get_search_intent(q)
        u_i = get_search_intent(u)
        print(f"{status} [{q_i}] vs [{u_i}] | {desc} → {result}")

    print(f"\n{'✅' if ok == len(tests) else '❌'} {ok}/{len(tests)} 통과")
