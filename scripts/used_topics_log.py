#!/usr/bin/env python3
"""공통 발행 주제 로그 유틸 — 3개 블로그(aikeeper, allsweep, ggultongmon) 공유
파일: /root/.openclaw/workspace/paperclip-company/projects/p004-blogger/used_topics.jsonl
"""
import json
import datetime
from pathlib import Path

# 프로젝트 루트 기준 (scripts/ 의 부모)
LOG_FILE = Path(__file__).parent.parent / "used_topics.jsonl"


def log_topic(blog_id: str, topic: str, keywords: str, search_keyword: str = "", product_ids: list = None) -> None:
    """발행 성공 시 주제를 로그에 기록"""
    entry = {
        "blog": blog_id,
        "topic": topic,
        "keywords": keywords,
        "search_keyword": search_keyword,   # 쿠팡 검색 키워드 (상품 중복 방지용)
        "product_ids": product_ids or [],   # 쿠팡 상품 ID 목록 (상품 레벨 중복 방지)
        "date": datetime.date.today().isoformat(),
        "ts": datetime.datetime.now().isoformat(),
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[used_topics_log] 로그 기록 실패 (무시): {e}")


def is_duplicate(topic: str, keywords: str = "", days: int = 7,
                 search_keyword: str = "", product_ids: list = None) -> bool:
    """구글 알고리즘 리스크 기준 중복 체크 (완화 설정)

    실제 구글 페널티 기준:
    - 같은 날 동일 상품/키워드 발행 → 캐니벌라이제이션 위험
    - 3일 내 완전 동일 상품 재발행 → Thin Content 위험
    - 제목이 70% 이상 같으면 → 중복 콘텐츠 판정 위험

    완화 기준 (불필요한 차단 최소화):
    - 검색 키워드 동일: 당일(0일 차이)만 차단
    - 상품 ID 겹침: 3일 이내만 차단
    - 제목 유사도: 70% 이상 + 3일 이내만 차단
    - 키워드 세트 완전 일치: 당일만 차단
    """
    if not LOG_FILE.exists():
        return False

    today = datetime.date.today()
    cutoff_3d = today - datetime.timedelta(days=3)
    topic_lower = topic.lower()
    kw_set = set(k.strip() for k in keywords.lower().split(",") if k.strip()) if keywords else set()
    check_product_ids = set(str(pid) for pid in (product_ids or []))
    search_kw_lower = search_keyword.lower().strip() if search_keyword else ""

    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_date = datetime.date.fromisoformat(entry["date"])
                entry_topic = entry.get("topic", "").lower()
                entry_search_kw = entry.get("search_keyword", "").lower().strip()
                entry_pids = set(str(p) for p in entry.get("product_ids", []))
                entry_kw = set(
                    k.strip()
                    for k in entry.get("keywords", "").lower().split(",")
                    if k.strip()
                )

                # ── 1. 검색 키워드 동일 → 당일만 차단 ──────────────────────
                if search_kw_lower and entry_search_kw and search_kw_lower == entry_search_kw:
                    if entry_date == today:
                        return True

                # ── 2. 상품 ID 겹침 → 3일 이내만 차단 ──────────────────────
                if check_product_ids and entry_pids and check_product_ids & entry_pids:
                    if entry_date >= cutoff_3d:
                        return True

                # ── 3. 제목 70% 이상 유사 → 3일 이내만 차단 ────────────────
                if entry_date >= cutoff_3d:
                    words = [w for w in topic_lower.split() if len(w) >= 2]
                    if words:
                        matches = sum(1 for w in words if w in entry_topic)
                        if matches / len(words) >= 0.7:
                            return True

                # ── 4. 키워드 세트 완전 일치 → 당일만 차단 ─────────────────
                if kw_set and kw_set == entry_kw:
                    if entry_date == today:
                        return True

            except Exception:
                continue

    return False


def get_recent_topics(days: int = 7) -> list[dict]:
    """최근 N일 발행된 항목 목록 반환"""
    if not LOG_FILE.exists():
        return []

    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    results = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_date = datetime.date.fromisoformat(entry["date"])
                if entry_date >= cutoff:
                    results.append(entry)
            except Exception:
                continue
    return results


if __name__ == "__main__":
    # 간단 테스트
    print(f"LOG_FILE: {LOG_FILE}")
    print(f"최근 7일 로그: {len(get_recent_topics())}개")
