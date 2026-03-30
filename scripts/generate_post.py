#!/usr/bin/env python3
"""
고퀄리티 블로그 포스트 자동 생성
- SEO 최적화: FAQ 스키마 데이터, 시맨틱 키워드, LSI 키워드
- 요즘IT/브런치 스타일 포맷
- 구어체, 스토리텔링, 실용 정보 균형
"""
import os
import sys
import re
import json
import datetime

import anthropic as _anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """당신은 요즘IT, 브런치 상위 1% AI/기술 전문 블로거입니다.

## 글 구조 (필수 준수)

**1. 훅 (2~4문장)**
- 독자 일상 속 공감 가능한 상황/질문으로 시작
- "혹시 이런 경험 있으신가요?" 공감 유도
- 절대 "안녕하세요, 오늘은 ~에 대해 알아보겠습니다" 금지

**2. 핵심 정의 박스**
> 한 문장으로 이 글의 핵심 인사이트 정의

**3. 본론 섹션 (4~5개)**
- ## 🔍 이모지 소제목
- 쉬운 비유로 개념 설명
- 실제 데이터/사례
- > 💡 팁 박스 최소 1개

**4. FAQ 섹션 (SEO 필수)**
## ❓ 자주 묻는 질문
Q: 독자가 실제로 검색할 법한 질문 3개
A: 간결하고 정확한 답변

**5. 핵심 요약 테이블**
| 항목 | 내용 |
형식의 표

**6. 마무리 CTA**
- 댓글 유도 + 공유 요청

## 톤
- 구어체: "~이죠", "~해요", "~거든요"
- 독자 호칭: "여러분"
- 전문용어 즉시 한글 설명

## 분량
- 2500~3500자
- 읽는 시간 10~12분"""


def generate_post(topic: str, keywords: list = None, angle: str = "") -> dict:
    keywords_str = ", ".join(keywords) if keywords else topic
    today = datetime.date.today().strftime("%Y년 %m월 %d일")

    prompt = f"""오늘은 {today}입니다. 아래 주제로 완성도 높은 글을 작성해주세요.

**주제**: {topic}
**핵심 키워드**: {keywords_str}
{f'**글쓰기 각도**: {angle}' if angle else ''}

## 필수 포함 요소

1. **훅 문단**: 공감 가는 상황으로 시작 (구어체)
2. **핵심 정의**: `>` 인용구
3. **본론 4~5 섹션**: 각 `## 이모지 소제목`
   - 쉬운 비유로 개념 설명
   - 2026년 최신 데이터/사례
   - `> 💡 팁` 박스 최소 2개
4. **FAQ 섹션**: `## ❓ 자주 묻는 질문` (Q/A 형식 3개 — SEO용)
5. **비교/요약 표**: 마크다운 표
6. **핵심 요약**: `## ✅ 이것만 기억하세요` (bullet 3~5개)
7. **마무리 CTA**: 댓글 유도

## 절대 금지
- "안녕하세요, 오늘은" 식 시작
- 딱딱한 문어체
- 근거 없는 주장
- 뻔한 마무리

아래 형식으로 정확히 응답:

===TITLE===
클릭 유발 제목 (50자 이내, 이모지 포함 권장)
===LABELS===
라벨1,라벨2,라벨3
===META===
구글 검색결과 설명문 (140~160자, 핵심키워드+혜택+연도 포함)
===KEYWORDS_SEO===
SEO 롱테일 키워드 5개 (쉼표 구분, 실제 검색어 형식)
===FAQ===
Q1: 질문
A1: 답변
Q2: 질문
A2: 답변
Q3: 질문
A3: 답변
===IMAGE===
대표 이미지 영문 검색어 (3~4단어, 구체적으로)
===CONTENT===
완성된 마크다운 본문
===END==="""

    client = _anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        timeout=300,
        max_retries=2,
    )

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text

    def extract_section(t, key):
        all_tags = ["===TITLE===", "===LABELS===", "===META===", "===KEYWORDS_SEO===",
                    "===FAQ===", "===IMAGE===", "===CONTENT===", "===END==="]
        tag = f"==={key}==="
        s = t.find(tag)
        if s == -1:
            return ""
        s += len(tag)
        e = len(t)
        for other in all_tags:
            if other == tag:
                continue
            pos = t.find(other, s)
            if pos != -1 and pos < e:
                e = pos
        return t[s:e].strip()

    title = extract_section(text, "TITLE")
    labels = [l.strip() for l in extract_section(text, "LABELS").split(",") if l.strip()]
    meta_desc = extract_section(text, "META")
    seo_keywords = extract_section(text, "KEYWORDS_SEO")
    faq_raw = extract_section(text, "FAQ")
    image_query = extract_section(text, "IMAGE")
    content = extract_section(text, "CONTENT")

    # FAQ 파싱
    faqs = []
    for block in re.split(r'\nQ\d+:', "\n" + faq_raw):
        block = block.strip()
        if not block:
            continue
        parts = re.split(r'\nA\d*:', block, 1)
        if len(parts) == 2:
            faqs.append({"q": parts[0].strip(), "a": parts[1].strip()})

    return {
        "title": title or "AI 블로그 포스트",
        "labels": labels or ["AI", "기술"],
        "content": content,
        "meta_description": meta_desc,
        "seo_keywords": seo_keywords,
        "faqs": faqs,
        "image_query": image_query or "artificial intelligence technology 2026"
    }


def save_as_markdown(post_data: dict, topic: str) -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    slug = "".join(
        c if c.isascii() and (c.isalnum() or c == "-") else "-"
        for c in topic.lower().replace(" ", "-")
    )
    slug = "-".join(filter(None, slug.split("-")))[:40] or "post"
    filename = f"posts/{today}-{slug}.md"

    safe_title = post_data['title'].replace('"', '\\"')
    safe_meta = post_data.get('meta_description', '').replace('"', '\\"')
    labels_yaml = json.dumps(post_data["labels"], ensure_ascii=False)
    faq_yaml = json.dumps(post_data.get("faqs", []), ensure_ascii=False)

    content = f"""---
title: "{safe_title}"
labels: {labels_yaml}
draft: false
meta_description: "{safe_meta}"
seo_keywords: "{post_data.get('seo_keywords', '').replace('"', '')}"
faqs: {faq_yaml}
image_query: "{post_data.get('image_query', 'technology AI')}"
---

{post_data['content']}
"""

    os.makedirs("posts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 글 생성 완료")
    print(f"   제목: {post_data['title']}")
    print(filename)
    return filename


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 최신 트렌드"
    keywords = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    angle = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"📝 주제: {topic}")
    post_data = generate_post(topic, keywords, angle)
    filename = save_as_markdown(post_data, topic)
    print(filename)
