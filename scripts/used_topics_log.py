#!/usr/bin/env python3
"""공통 발행 주제 로그 유틸 — 3개 블로그(aikeeper, allsweep, ggultongmon) 공유
파일: /root/.openclaw/workspace/paperclip-company/projects/p004-blogger/used_topics.jsonl
"""
import json
import datetime
from pathlib import Path

# 프로젝트 루트 기준 (scripts/ 의 부모)
LOG_FILE = Path(__file__).parent.parent / "used_topics.jsonl"


def log_topic(blog_id: str, topic: str, keywords: str) -> None:
    """발행 성공 시 주제를 로그에 기록"""
    entry = {
        "blog": blog_id,
        "topic": topic,
        "keywords": keywords,
        "date": datetime.date.today().isoformat(),
        "ts": datetime.datetime.now().isoformat(),
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[used_topics_log] 로그 기록 실패 (무시): {e}")


def is_duplicate(topic: str, keywords: str = "", days: int = 7) -> bool:
    """최근 N일 이내 유사 주제 발행 여부 체크

    Args:
        topic:    체크할 주제 제목
        keywords: 쉼표 구분 키워드 문자열
        days:     몇 일 이내를 중복으로 볼지 (기본 7일)

    Returns:
        True이면 중복 (발행 스킵 권장), False이면 새 주제
    """
    if not LOG_FILE.exists():
        return False

    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    topic_lower = topic.lower()
    kw_set = set(k.strip() for k in keywords.lower().split(",") if k.strip()) if keywords else set()

    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_date = datetime.date.fromisoformat(entry["date"])
                if entry_date < cutoff:
                    continue  # 오래된 항목은 무시

                entry_topic = entry.get("topic", "").lower()

                # ── 주제 제목 50% 이상 겹치면 중복 (2자 이상 단어 기준) ──
                words = [w for w in topic_lower.split() if len(w) >= 2]
                if words:
                    matches = sum(1 for w in words if w in entry_topic)
                    if matches / len(words) >= 0.5:
                        return True

                # ── 키워드 세트가 완전히 동일하면 중복 ──
                entry_kw = set(
                    k.strip()
                    for k in entry.get("keywords", "").lower().split(",")
                    if k.strip()
                )
                if kw_set and kw_set == entry_kw:
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
