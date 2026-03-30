#!/usr/bin/env python3
"""
Claude API로 블로그 글 자동 생성 스크립트
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def generate_post(topic: str, keywords: list = None) -> dict:
    """Claude API로 블로그 글 생성"""
    keywords_str = ", ".join(keywords) if keywords else topic

    prompt = f"""당신은 AI/기술 전문 블로거입니다. 아래 주제로 SEO에 최적화된 블로그 글을 작성해주세요.

주제: {topic}
키워드: {keywords_str}

요구사항:
1. 제목: SEO 친화적, 클릭을 유도하는 제목 (50자 이내)
2. 본문: 1500~2000자 분량
3. 구조: ## 소제목 사용, 리스트 활용
4. 도입부: 독자의 관심을 끄는 첫 문단
5. 결론: 핵심 요약 + 독자 행동 유도
6. 키워드를 자연스럽게 3~5회 포함
7. 마크다운 형식으로 작성

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "글 제목",
  "labels": ["라벨1", "라벨2", "라벨3"],
  "content": "마크다운 본문 내용",
  "meta_description": "검색결과에 표시될 설명 (150자 이내)",
  "image_query": "대표 이미지 검색어 (영문)"
}}"""

    data = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
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

    # JSON 추출
    start = text.find("{")
    end = text.rfind("}") + 1
    post_data = json.loads(text[start:end])
    return post_data


def save_as_markdown(post_data: dict, topic: str) -> str:
    """생성된 글을 마크다운 파일로 저장"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    slug = topic.lower().replace(" ", "-")[:30]
    filename = f"posts/{today}-{slug}.md"

    labels_str = str(post_data["labels"]).replace("'", '"')

    front_matter = f"""---
title: "{post_data['title']}"
labels: {labels_str}
draft: false
meta_description: "{post_data.get('meta_description', '')}"
image_query: "{post_data.get('image_query', topic)}"
---

"""
    content = front_matter + post_data["content"]

    os.makedirs("posts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 글 생성 완료: {filename}")
    print(f"   제목: {post_data['title']}")
    return filename


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 최신 트렌드"
    keywords = sys.argv[2].split(",") if len(sys.argv) > 2 else None

    print(f"📝 주제: {topic}")
    post_data = generate_post(topic, keywords)
    filename = save_as_markdown(post_data, topic)
    print(filename)  # 다음 스텝에서 사용
