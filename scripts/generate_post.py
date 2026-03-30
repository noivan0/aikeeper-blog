#!/usr/bin/env python3
"""
Claude API로 고퀄리티 블로그 글 자동 생성
- 상위 블로그 포맷 적용 (네이버/브런치/MIT Tech Review 스타일)
- SEO 최적화
- 가독성 극대화 구조
"""
import os
import sys
import json
import datetime
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


SYSTEM_PROMPT = """당신은 월 100만 PV를 달성한 대한민국 최고의 AI/기술 블로거입니다.

## 당신의 글쓰기 철학
- 독자가 3초 안에 "이 글 읽어야겠다"고 느끼게 만든다
- 어려운 개념을 누구나 이해할 수 있게 풀어쓴다
- 실용적 정보와 인사이트를 함께 제공한다
- 읽는 내내 지루하지 않게 흐름을 유지한다

## 상위 블로그 포맷 (반드시 준수)

### 제목 공식
- [숫자] + [핵심키워드] + [독자 혜택] 형식
- 예: "ChatGPT로 하루 2시간 아끼는 5가지 방법"
- 예: "2025년 AI 트렌드 완벽 정리 - 지금 알아야 할 것들"

### 글 구조 (반드시 이 순서로)
1. **훅(Hook)**: 독자의 고통/궁금증을 건드리는 첫 문단 (3~4문장)
2. **목차**: 이 글에서 다룰 내용 미리보기 (3~5개 항목)
3. **본론**: 소제목별 핵심 내용 (각 섹션 300~400자)
4. **핵심 요약 박스**: 전체 내용 3줄 요약
5. **CTA**: 독자 행동 유도 마무리

### 가독성 규칙
- 한 문단 = 최대 3문장
- 소제목마다 핵심 포인트 1개 강조 (굵게)
- 숫자/통계 적극 활용
- 전문용어는 반드시 쉬운 말로 부연
- 이모지 적절히 활용 (과하지 않게, 소제목당 1개)"""


def generate_post(topic: str, keywords: list = None, angle: str = "") -> dict:
    keywords_str = ", ".join(keywords) if keywords else topic

    prompt = f"""아래 주제로 고퀄리티 블로그 글을 작성해주세요.

주제: {topic}
핵심 키워드: {keywords_str}
{f'글쓰기 각도: {angle}' if angle else ''}

## 반드시 포함할 요소

1. **훅 문단**: 독자가 공감할 질문이나 상황으로 시작
2. **목차 섹션**: "## 📋 이 글에서 다루는 내용" 형식
3. **본론 3~5개 섹션**: 각각 ## 소제목 사용
4. **핵심 요약**: "## ✅ 핵심 요약" 섹션으로 3줄 bullet
5. **마무리 CTA**: 댓글/공유 유도

## 마크다운 스타일 규칙
- 중요 개념은 **굵게** 표시
- 팁/주의사항은 > 인용구 블록 사용
- 비교할 때는 표(table) 사용
- 단계별 설명은 번호 목록 사용
- 핵심 문장은 별도 줄로 강조

반드시 아래 JSON 형식으로만 응답:
{{
  "title": "SEO 최적화 제목 (50자 이내, 숫자 포함)",
  "labels": ["라벨1", "라벨2", "라벨3"],
  "content": "완성된 마크다운 본문 (2000자 이상)",
  "meta_description": "검색결과 설명 (150자 이내, 키워드 포함)",
  "image_query": "대표 이미지 검색어 (영문 2~3단어)"
}}"""

    data = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT,
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
    return json.loads(text[start:end])


def save_as_markdown(post_data: dict, topic: str) -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    slug = topic.lower().replace(" ", "-")[:30]
    # 한글 제거
    slug = "".join(c for c in slug if c.isascii())
    slug = slug.strip("-") or "post"
    filename = f"posts/{today}-{slug}.md"

    labels = post_data["labels"]
    labels_yaml = json.dumps(labels, ensure_ascii=False)

    content = f"""---
title: "{post_data['title']}"
labels: {labels_yaml}
draft: false
meta_description: "{post_data.get('meta_description', '')}"
image_query: "{post_data.get('image_query', 'technology AI')}"
---

{post_data['content']}
"""

    os.makedirs("posts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 글 생성 완료: {filename}")
    print(f"   제목: {post_data['title']}")
    return filename


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 최신 트렌드"
    keywords = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    angle = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"📝 주제: {topic}")
    post_data = generate_post(topic, keywords, angle)
    filename = save_as_markdown(post_data, topic)
    print(filename)
