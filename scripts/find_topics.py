#!/usr/bin/env python3
"""
최신 AI 뉴스 & 트렌드 수집 → 블로그 주제 자동 선정
소스: Reddit (r/artificial, r/MachineLearning, r/singularity) + TechCrunch + Hacker News
최근 1주일~1개월 이내 실제 최신 소식만 사용
"""
import os
import sys
import subprocess
import datetime
import re
import tempfile

import anthropic as _anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def scrapling_fetch(url: str) -> str:
    """scrapling CLI로 URL 가져오기"""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    try:
        result = subprocess.run(
            ["scrapling", "extract", "get", url, tmp, "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=30
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"⚠️  scrapling 오류 ({url}): {e}")
        return ""
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def parse_reddit_rss(content: str, source: str, max_items: int = 8) -> list:
    """Reddit RSS 텍스트 파싱 (scrapling 출력 형식)"""
    items = []
    lines = content.splitlines()
    i = 0
    while i < len(lines) and len(items) < max_items:
        line = lines[i].strip()
        # 날짜 패턴: 2026-03-xx
        if re.match(r'^\d{4}-\d{2}-\d{2}T', line):
            date = line[:10]
            # 다음 날짜 또는 제목 찾기
            for j in range(i+1, min(i+4, len(lines))):
                title = lines[j].strip()
                if len(title) > 15 and not title.startswith('http') and not title.startswith('/'):
                    # HTML 태그 제거
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if len(title) > 15:
                        items.append({"title": title, "date": date, "source": source})
                        break
        i += 1
    return items


def parse_simple_rss(content: str, source: str, max_items: int = 8) -> list:
    """TechCrunch/일반 RSS 텍스트 파싱"""
    items = []
    lines = content.splitlines()
    i = 0
    while i < len(lines) and len(items) < max_items:
        line = lines[i].strip()
        # 날짜 패턴: "Sun, 29 Mar 2026" 또는 "2026-03-29"
        date_match = re.match(r'.*(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(\d+)\s+(\w+)\s+(\d{4})', line)
        if date_match:
            date = line[:16]
            # 이전 줄이 제목
            for k in range(i-1, max(i-4, -1), -1):
                prev = lines[k].strip()
                prev = re.sub(r'<[^>]+>', '', prev).strip()
                if (len(prev) > 20 and not prev.startswith('http')
                        and not prev.startswith('https') and '://' not in prev):
                    items.append({"title": prev, "date": date, "source": source})
                    break
        i += 1
    return items


def fetch_hackernews_ai() -> list:
    """Hacker News AI 관련 최신 글"""
    content = scrapling_fetch("https://hnrss.org/newest?q=AI+LLM+Claude+GPT+Gemini&count=15")
    items = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        date_match = re.match(r'.*(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d+\s+\w+\s+2026', line)
        if date_match:
            date = line[:16]
            for k in range(i-1, max(i-4, -1), -1):
                prev = re.sub(r'<[^>]+>', '', lines[k]).strip()
                if len(prev) > 20 and '://' not in prev and not prev.startswith('http'):
                    items.append({"title": prev, "date": date, "source": "Hacker News"})
                    break
        if len(items) >= 6:
            break
    return items


def fetch_all_news() -> list:
    """모든 소스에서 최신 뉴스 수집"""
    all_news = []

    sources = [
        ("https://www.reddit.com/r/artificial/top/.rss?t=week", "r/artificial", "reddit"),
        ("https://www.reddit.com/r/MachineLearning/top/.rss?t=week", "r/MachineLearning", "reddit"),
        ("https://www.reddit.com/r/singularity/top/.rss?t=week", "r/singularity", "reddit"),
        ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI", "simple"),
        ("https://feeds.feedburner.com/venturebeat/SZYF", "VentureBeat AI", "simple"),
    ]

    for url, name, fmt in sources:
        print(f"  📡 {name} 수집 중...")
        content = scrapling_fetch(url)
        if not content:
            continue
        if fmt == "reddit":
            items = parse_reddit_rss(content, name, max_items=6)
        else:
            items = parse_simple_rss(content, name, max_items=5)
        print(f"     → {len(items)}개")
        all_news.extend(items)

    # Hacker News
    print("  📡 Hacker News 수집 중...")
    hn_items = fetch_hackernews_ai()
    print(f"     → {len(hn_items)}개")
    all_news.extend(hn_items)

    return all_news


def select_best_topic(news_items: list) -> dict:
    """Claude로 최신 뉴스 기반 블로그 주제 선정"""
    today = datetime.date.today().strftime("%Y년 %m월 %d일")

    news_text = "\n".join([
        f"[{item['source']}] {item['title']} ({item.get('date','')})"
        for item in news_items[:25]
    ]) or "뉴스 없음"

    prompt = f"""오늘은 {today}입니다.

아래는 지난 1주일간 Reddit, TechCrunch, VentureBeat, Hacker News에서 수집한 실제 최신 AI/기술 뉴스입니다.

[최신 뉴스 목록]
{news_text}

AI키퍼 블로그 (한국어, AI/기술 전문)에 가장 적합한 주제를 선정해주세요.

선택 기준:
1. 위 뉴스 목록에서 실제로 화제인 소식 기반일 것
2. 한국 독자들이 관심 가질 만한 주제
3. 단순 뉴스 요약이 아닌 "왜 중요한가", "어떻게 활용할까" 각도
4. 2026년 현재 시점에 맞는 최신성

아래 형식으로 정확히 응답하세요:

===TOPIC===
블로그 주제 (한국어, 구체적으로 — 위 뉴스 중 하나를 기반으로)
===KEYWORDS===
키워드1,키워드2,키워드3,키워드4
===REASON===
선택 이유 (어떤 뉴스 기반인지 포함, 1~2줄)
===ANGLE===
차별화된 글쓰기 각도 (한국 독자 시각, 실용적 관점)
===SOURCE_NEWS===
참고한 원본 뉴스 제목
===END==="""

    client = _anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        timeout=120,
        max_retries=2,
    )

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text

    def extract(t, key):
        tags = ["===TOPIC===","===KEYWORDS===","===REASON===","===ANGLE===","===SOURCE_NEWS===","===END==="]
        tag = f"==={key}==="
        s = t.find(tag)
        if s == -1: return ""
        s += len(tag)
        e = len(t)
        for other in tags:
            if other == tag: continue
            pos = t.find(other, s)
            if 0 < pos < e: e = pos
        return t[s:e].strip()

    return {
        "topic": extract(text, "TOPIC"),
        "keywords": [k.strip() for k in extract(text, "KEYWORDS").split(",") if k.strip()],
        "reason": extract(text, "REASON"),
        "angle": extract(text, "ANGLE"),
        "source_news": extract(text, "SOURCE_NEWS"),
    }


if __name__ == "__main__":
    print(f"🔍 최신 뉴스 수집 중... ({datetime.date.today()})")
    news = fetch_all_news()
    print(f"\n총 {len(news)}개 뉴스 수집 완료\n")

    if not news:
        # 폴백: 하드코딩 최신 주제
        print("TOPIC:Claude AI 최신 업데이트와 활용법 2026")
        print("KEYWORDS:Claude,Anthropic,AI,활용법")
        print("ANGLE:실제 사용자 관점에서 바라본 최신 기능")
        sys.exit(0)

    print("🤖 Claude가 최적 주제 선정 중...")
    result = select_best_topic(news)

    print(f"\n✅ 선정된 주제: {result['topic']}")
    print(f"   키워드: {', '.join(result['keywords'])}")
    print(f"   근거: {result['reason']}")
    print(f"   원본 뉴스: {result['source_news']}")

    print(f"\nTOPIC:{result['topic']}")
    print(f"KEYWORDS:{','.join(result['keywords'])}")
    print(f"ANGLE:{result['angle']}")
