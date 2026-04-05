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
    """구글 알고리즘 리스크 기준 중복 체크

    실제 구글 페널티 기준:
    - 주제/제목 유사 → 패널티 없음 (언론사도 매달 같은 주제 발행)
    - 동일 상품을 당일 여러 번 → SEO 실익 없는 중복

    체크 기준 (최소한으로):
    - 상품 ID 겹침: 당일만 차단 (내일은 같은 상품도 재발행 가능)
    """
    if not LOG_FILE.exists():
        return False

    today = datetime.date.today()
    check_product_ids = set(str(pid) for pid in (product_ids or []))

    # 상품 ID가 없으면 중복 체크 자체를 스킵
    if not check_product_ids:
        return False

    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entry_date = datetime.date.fromisoformat(entry["date"])

                # 당일 발행만 체크
                if entry_date != today:
                    continue

                # 상품 ID 1개 이상 겹치면 중복
                entry_pids = set(str(p) for p in entry.get("product_ids", []))
                if entry_pids and check_product_ids & entry_pids:
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
