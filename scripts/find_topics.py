#!/usr/bin/env python3
"""
주제 자동 발굴 스크립트
1. Google Trends RSS (실시간 트렌드)
2. AI 뉴스 RSS (Ars Technica, TechCrunch AI, VentureBeat)
3. Claude로 최적 주제 선택
"""
import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def fetch_google_trends_kr() -> list:
    """Google Trends 한국 실시간 인기 검색어 RSS"""
    url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
        
        trends = []
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", "")
            traffic = item.findtext("{https://trends.google.com/trends/trendingsearches/daily}approx_traffic", "")
            trends.append({"title": title, "traffic": traffic})
        return trends
    except Exception as e:
        print(f"⚠️  Google Trends 오류: {e}")
        return []


def fetch_rss(url: str, max_items: int = 5) -> list:
    """RSS 피드 파싱"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            root = ET.fromstring(resp.read())
        
        items = []
        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")[:200]
            link = item.findtext("link", "")
            items.append({"title": title, "desc": desc, "link": link})
        return items
    except Exception as e:
        print(f"⚠️  RSS 오류 ({url}): {e}")
        return []


def fetch_ai_news() -> list:
    """AI 관련 최신 뉴스 RSS"""
    feeds = [
        ("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("VentureBeat AI",  "https://venturebeat.com/category/ai/feed/"),
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ]
    
    all_news = []
    for source, url in feeds:
        items = fetch_rss(url, max_items=3)
        for item in items:
            item["source"] = source
            all_news.append(item)
    return all_news


def select_best_topic(trends: list, ai_news: list) -> dict:
    """Claude로 최적 블로그 주제 선택"""
    
    trends_text = "\n".join([f"- {t['title']} ({t['traffic']})" for t in trends]) or "없음"
    news_text = "\n".join([f"- [{n['source']}] {n['title']}" for n in ai_news]) or "없음"
    
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    
    prompt = f"""오늘은 {today}입니다.

아래 데이터를 참고해서 AI키퍼 블로그(AI/기술 전문)에 올릴 최적의 주제를 선택해주세요.

[한국 Google 트렌드 TOP 10]
{trends_text}

[AI 최신 뉴스]
{news_text}

선택 기준:
1. AI/기술과 연관성이 높을 것
2. 한국 독자들이 관심 가질 주제
3. 아직 많이 다뤄지지 않은 신선한 각도
4. SEO 검색량이 높을 것으로 예상되는 주제

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "topic": "블로그 주제 (한국어, 구체적으로)",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "reason": "선택 이유 (1줄)",
  "angle": "차별화된 글쓰기 각도"
}}"""

    data = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        f"{ANTHROPIC_BASE_URL.rstrip('/')}/messages",
        data=data,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    text = result["content"][0]["text"]
    start = text.find("{")
    end = text.rfind("}") + 1
    topic_data = json.loads(text[start:end])
    return topic_data


if __name__ == "__main__":
    print("🔍 트렌드 & 뉴스 수집 중...")
    trends = fetch_google_trends_kr()
    ai_news = fetch_ai_news()

    print(f"  - Google Trends: {len(trends)}개")
    print(f"  - AI 뉴스: {len(ai_news)}개")

    print("\n🤖 Claude가 최적 주제 선택 중...")
    topic_data = select_best_topic(trends, ai_news)

    print(f"\n✅ 선택된 주제: {topic_data['topic']}")
    print(f"   키워드: {', '.join(topic_data['keywords'])}")
    print(f"   이유: {topic_data['reason']}")
    print(f"   각도: {topic_data['angle']}")

    # generate_post.py에서 사용할 수 있도록 출력
    print(f"\nTOPIC:{topic_data['topic']}")
    print(f"KEYWORDS:{','.join(topic_data['keywords'])}")
