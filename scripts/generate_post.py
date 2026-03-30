#!/usr/bin/env python3
"""
고퀄리티 블로그 포스트 자동 생성
- 실제 상위 블로그 분석 기반 (요즘IT, 브런치 스타일)
- 구어체, 스토리텔링, 실용 정보 균형
- SEO + 가독성 동시 최적화
"""
import os
import sys
import json
import datetime

import anthropic as _anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ── 실제 상위 블로그 분석 기반 시스템 프롬프트 ──────────────────
SYSTEM_PROMPT = """당신은 요즘IT, 브런치 인기 작가 수준의 AI/기술 전문 블로거입니다.

## 실제 상위 블로그 포맷 (반드시 준수)

### 제목 공식 (클릭률 최적화)
- 호기심 자극형: "생각만으로 글 쓰는 시대 올까? 뇌-컴퓨터 인터페이스 혁명"
- 숫자+혜택형: "ChatGPT로 업무 자동화하는 7가지 방법 (2025 최신)"
- 반전형: "개발자가 사라진다고? AI 시대 프로그래머의 생존법"
- 공감형: "나만 모르는 건가요? 요즘 뜨는 AI 도구 총정리"

### 글 구조 (요즘IT/브런치 상위 포맷)

**1. 훅 (3~5문장)**
- 독자가 공감할 일상적 상황이나 질문으로 시작
- 영화, 뉴스, 실제 경험 사례 인용
- "혹시 여러분도 이런 경험 있으신가요?" 식의 공감 유도

**2. 핵심 정의 박스 (인용구)**
> 이 글의 핵심 주제를 한 문장으로 정의

**3. 본론 섹션 (3~5개)**
각 섹션 구조:
- ## 🔍 소제목 (이모지 1개)
- 핵심 개념 설명 (쉬운 비유 포함)
- 실제 사례/데이터 인용
- ### 세부 소제목으로 심화
- > 팁 또는 주의사항

**4. 핵심 요약 테이블**
| 항목 | 내용 |
형식의 표로 핵심 정보 정리

**5. 마무리 + CTA**
- 미래 전망 1~2문장
- "여러분은 어떻게 생각하시나요?" 식 댓글 유도
- 관련 글 추천 언급

### 글쓰기 톤 (매우 중요)
- **구어체**: "~이죠", "~해요", "~거든요", "~인데요"
- **독자에게 말 걸기**: "여러분", "혹시", "이런 경험 있으신가요?"
- **감탄/공감**: "놀랍게도", "사실은", "그런데 말이죠"
- **전문용어 즉시 설명**: 어려운 단어 → 괄호로 쉬운 말 부연
- **문단 길이**: 최대 3~4문장, 한 줄 띄어쓰기로 호흡 유지

### 분량
- 2000~3000자 (10분 읽기 분량)
- 섹션당 400~600자
- 소제목 3~5개"""


def generate_post(topic: str, keywords: list = None, angle: str = "") -> dict:
    keywords_str = ", ".join(keywords) if keywords else topic

    prompt = f"""아래 주제로 상위 블로그 수준의 완성도 높은 글을 작성해주세요.

**주제**: {topic}
**핵심 키워드**: {keywords_str}
{f'**글쓰기 각도**: {angle}' if angle else ''}

## 필수 포함 요소

1. **훅 문단**: 영화/뉴스/실제 사례로 독자 몰입 유도 (구어체)
2. **핵심 정의**: `>` 인용구로 주제 한 줄 정의
3. **본론 3~5 섹션**: 각 `## 이모지 소제목` 형식
   - 쉬운 비유로 개념 설명
   - 실제 데이터/사례 포함
   - `>` 팁 박스 최소 1개
4. **비교 표**: 핵심 정보를 마크다운 표로 정리
5. **핵심 요약**: `## ✅ 이것만 기억하세요` 섹션 (bullet 3~5개)
6. **마무리 CTA**: 독자 질문 + 댓글 유도

## 절대 금지
- 딱딱한 문어체 (보고서 느낌 X)
- 한 문단 5문장 이상
- 근거 없는 주장 (데이터/사례 없이)
- 뻔한 결론 ("AI는 중요합니다" 식)

아래 형식으로 정확히 응답하세요. 각 섹션은 구분자로 구분합니다:

===TITLE===
클릭 유발 제목 (50자 이내, 이모지 가능)
===LABELS===
라벨1,라벨2,라벨3
===META===
검색결과 설명 (150자 이내, 키워드+혜택 포함)
===IMAGE===
대표 이미지 영문 검색어 (2~3단어)
===CONTENT===
완성된 마크다운 본문 (2500자 이상, 여기서부터 끝까지)
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
        start_tag = f"==={key}==="
        end_candidates = ["===LABELS===", "===META===", "===IMAGE===", "===CONTENT===", "===END===", "===TITLE==="]
        s = t.find(start_tag)
        if s == -1:
            return ""
        s += len(start_tag)
        e = len(t)
        for tag in end_candidates:
            if tag == start_tag:
                continue
            pos = t.find(tag, s)
            if pos != -1 and pos < e:
                e = pos
        return t[s:e].strip()

    title = extract_section(text, "TITLE")
    labels_raw = extract_section(text, "LABELS")
    labels = [l.strip() for l in labels_raw.split(",") if l.strip()]
    meta_desc = extract_section(text, "META")
    image_query = extract_section(text, "IMAGE")
    content = extract_section(text, "CONTENT")

    return {
        "title": title or "AI 블로그 포스트",
        "labels": labels or ["AI", "기술"],
        "content": content,
        "meta_description": meta_desc,
        "image_query": image_query or "artificial intelligence technology"
    }


def save_as_markdown(post_data: dict, topic: str) -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    # 슬러그: ASCII만
    slug = "".join(c if c.isascii() and (c.isalnum() or c == "-") else "-" for c in topic.lower().replace(" ", "-"))
    slug = "-".join(filter(None, slug.split("-")))[:40] or "post"
    filename = f"posts/{today}-{slug}.md"

    labels_yaml = json.dumps(post_data["labels"], ensure_ascii=False)
    # 제목/메타의 큰따옴표 이스케이프
    safe_title = post_data['title'].replace('"', '\\"')
    safe_meta = post_data.get('meta_description', '').replace('"', '\\"')
    content = f"""---
title: "{safe_title}"
labels: {labels_yaml}
draft: false
meta_description: "{safe_meta}"
image_query: "{post_data.get('image_query', 'technology AI')}"
---

{post_data['content']}
"""

    os.makedirs("posts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ 글 생성 완료")
    print(f"   제목: {post_data['title']}")
    print(filename)   # 마지막 줄: posts/YYYY-MM-DD-slug.md
    return filename


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI 최신 트렌드"
    keywords = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    angle = sys.argv[3] if len(sys.argv) > 3 else ""

    print(f"📝 주제: {topic}")
    post_data = generate_post(topic, keywords, angle)
    filename = save_as_markdown(post_data, topic)
    print(filename)
