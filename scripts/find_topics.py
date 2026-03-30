#!/usr/bin/env python3
"""
최신 AI 뉴스 & 트렌드 수집 → 블로그 주제 자동 선정
소스:
  1. Google News (한국어 + 영어) — 최근 1주일
  2. Reddit (r/artificial, r/MachineLearning, r/singularity) — 주간 TOP
  3. TechCrunch AI RSS
  4. X (Twitter) AI 인플루언서 최신 트윗 — fxtwitter API
"""
import os
import sys
import re
import subprocess
import tempfile
import datetime

import anthropic as _anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def scrapling_fetch(url: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ["scrapling", "extract", "get", url, tmp, "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=30
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"  ⚠️  scrapling 오류: {e}")
        return ""
    finally:
        try: os.unlink(tmp)
        except: pass


def parse_google_news(content: str, source: str) -> list:
    """Google News RSS에서 기사 제목+날짜 추출"""
    items = []
    # 기사 제목은 <a href="...">제목</a> 형식
    pattern = re.compile(r'<a href="[^"]*" target="_blank">(.*?)</a>', re.DOTALL)
    date_pattern = re.compile(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+(\d+)\s+(\w+)\s+2026')

    lines = content.splitlines()
    for i, line in enumerate(lines):
        m = pattern.search(line)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) < 15:
                continue
            # 날짜 찾기 (주변 줄)
            date = ""
            for j in range(max(0, i-3), min(len(lines), i+3)):
                dm = date_pattern.search(lines[j])
                if dm:
                    date = lines[j].strip()[:20]
                    break
            items.append({"title": title, "date": date, "source": source})
            if len(items) >= 10:
                break
    return items


def parse_reddit_rss(content: str, source: str) -> list:
    """Reddit RSS 텍스트 파싱"""
    items = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}T', line):
            date = line[:10]
            for j in range(i+1, min(i+5, len(lines))):
                title = re.sub(r'<[^>]+>', '', lines[j]).strip()
                if (len(title) > 20 and not title.startswith('http')
                        and not title.startswith('/') and '://' not in title):
                    items.append({"title": title, "date": date, "source": source})
                    break
        if len(items) >= 7:
            break
    return items


def parse_techcrunch_rss(content: str) -> list:
    """TechCrunch RSS 파싱"""
    items = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        date_m = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d+\s+\w+\s+2026', line)
        if date_m:
            date = line[:20]
            for k in range(i-1, max(i-5, -1), -1):
                prev = lines[k].strip()
                prev = re.sub(r'<[^>]+>', '', prev).strip()
                if (len(prev) > 20 and '://' not in prev
                        and not prev.startswith('http') and not prev.startswith('CBM')):
                    items.append({"title": prev, "date": date, "source": "TechCrunch AI"})
                    break
        if len(items) >= 7:
            break
    return items


def fetch_x_trends() -> list:
    """X(Twitter) AI 인플루언서 최신 트윗 수집 — fxtwitter API"""
    items = []
    # 주요 AI 인플루언서 계정
    accounts = ["sama", "AnthropicAI", "OpenAI", "GoogleDeepMind", "karpathy"]

    for account in accounts:
        url = f"https://api.fxtwitter.com/{account}"
        content = scrapling_fetch(url)
        if not content or "404" in content[:50]:
            continue
        # JSON 형태로 트윗 목록 파싱 시도
        tweet_texts = re.findall(r'"text"\s*:\s*"([^"]{30,200})"', content)
        dates = re.findall(r'"created_at"\s*:\s*"([^"]+)"', content)
        for j, text in enumerate(tweet_texts[:2]):
            text = text.replace('\\n', ' ').replace('\\"', '"').strip()
            if any(kw in text.lower() for kw in ['ai', 'model', 'llm', 'gpt', 'claude', 'gemini']):
                date = dates[j][:10] if j < len(dates) else ""
                items.append({"title": f"[X/{account}] {text[:100]}", "date": date, "source": f"X/@{account}"})
        if len(items) >= 4:
            break

    return items


def fetch_all_news() -> list:
    """모든 소스에서 최신 뉴스 수집"""
    all_news = []

    # 1. Google News 영어 (최근 7일)
    print("  📡 Google News (EN, 7일) 수집 중...")
    url = "https://news.google.com/rss/search?q=AI+LLM+Claude+GPT+Gemini+when:7d&hl=en-US&gl=US&ceid=US:en"
    content = scrapling_fetch(url)
    items = parse_google_news(content, "Google News EN")
    print(f"     → {len(items)}개")
    all_news.extend(items)

    # 2. Google News 한국어 (최근 30일)
    print("  📡 Google News (KO, 한달) 수집 중...")
    url = "https://news.google.com/rss/search?q=AI+인공지능+ChatGPT+Claude+when:30d&hl=ko&gl=KR&ceid=KR:ko"
    content = scrapling_fetch(url)
    items = parse_google_news(content, "Google News KO")
    print(f"     → {len(items)}개")
    all_news.extend(items)

    # 3. Reddit 주간 TOP
    reddit_sources = [
        ("https://www.reddit.com/r/artificial/top/.rss?t=week", "r/artificial"),
        ("https://www.reddit.com/r/MachineLearning/top/.rss?t=week", "r/MachineLearning"),
        ("https://www.reddit.com/r/singularity/top/.rss?t=week", "r/singularity"),
        ("https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week", "r/LocalLLaMA"),
    ]
    for url, name in reddit_sources:
        print(f"  📡 {name} 수집 중...")
        content = scrapling_fetch(url)
        items = parse_reddit_rss(content, name)
        print(f"     → {len(items)}개")
        all_news.extend(items)

    # 4. TechCrunch AI
    print("  📡 TechCrunch AI 수집 중...")
    content = scrapling_fetch("https://techcrunch.com/category/artificial-intelligence/feed/")
    items = parse_techcrunch_rss(content)
    print(f"     → {len(items)}개")
    all_news.extend(items)

    # 5. X 트렌드 (fxtwitter)
    print("  📡 X(Twitter) AI 인플루언서 수집 중...")
    items = fetch_x_trends()
    print(f"     → {len(items)}개")
    all_news.extend(items)

    return all_news


def select_best_topic(news_items: list) -> dict:
    today = datetime.date.today().strftime("%Y년 %m월 %d일")

    news_text = "\n".join([
        f"[{item['source']}] {item['title']} ({item.get('date','')})"
        for item in news_items[:30]
    ])

    prompt = f"""오늘은 {today}입니다.

아래는 Reddit, Google News, TechCrunch, X(Twitter)에서 수집한 실제 최신 AI/기술 뉴스입니다.

[최신 뉴스 목록]
{news_text}

AI키퍼 블로그(한국어 AI/기술 전문)에 가장 적합한 주제를 선정해주세요.

요구사항:
1. 반드시 위 뉴스 목록에 실제로 있는 소식 기반일 것
2. 단순 뉴스 요약 X → "왜 중요한가", "어떻게 활용할까" 각도
3. 한국 독자가 실제로 궁금해할 주제
4. 2026년 현재 시점에 맞는 최신성 필수

아래 형식으로 정확히 응답하세요:

===TOPIC===
블로그 주제 (한국어, 구체적으로)
===KEYWORDS===
키워드1,키워드2,키워드3,키워드4
===REASON===
선택 이유 (어떤 뉴스 기반인지 포함)
===ANGLE===
한국 독자를 위한 차별화된 글쓰기 각도
===SOURCE_NEWS===
참고한 원본 뉴스 제목 (그대로)
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
    print(f"\n✅ 총 {len(news)}개 수집 완료")

    if len(news) < 3:
        # 폴백
        print("TOPIC:2026년 AI 최신 트렌드 — Claude·GPT·Gemini 무엇이 달라졌나")
        print("KEYWORDS:AI트렌드,Claude,GPT,Gemini,2026")
        print("ANGLE:실제 사용자 관점의 비교 분석")
        sys.exit(0)

    print("\n🤖 최적 주제 선정 중...")
    result = select_best_topic(news)

    print(f"\n📌 선정된 주제: {result['topic']}")
    print(f"   키워드: {', '.join(result['keywords'])}")
    print(f"   원본 뉴스: {result['source_news']}")
    print(f"   이유: {result['reason']}")

    print(f"\nTOPIC:{result['topic']}")
    print(f"KEYWORDS:{','.join(result['keywords'])}")
    print(f"ANGLE:{result['angle']}")
