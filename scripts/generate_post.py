#!/usr/bin/env python3
"""
고퀄리티 블로그 포스트 자동 생성 v2
- 요즘IT/브런치 상위 1% 수준 (10,000자+)
- 딥다이브 구조: 배경 → 원인 → 사례 → 실전 → FAQ → 요약
- h3 세부 섹션, 외부 링크, 비교표 필수
- SEO: FAQ 스키마, 롱테일 키워드, E-E-A-T 신호
"""
import os
import sys
import re
import json
import datetime

import anthropic as _anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# 블로그 타입: "NEWS" = 뉴스/시사, 기본 = AI/기술
BLOG_TYPE = os.environ.get("BLOG_TYPE", "AI")

# allsweep(뉴스) 전용 시스템 프롬프트
SYSTEM_PROMPT_NEWS = """당신은 네이버/구글 상위 1%를 달성한 시사·뉴스 전문 블로거입니다.
월 200만 PV를 기록하며, 독자들이 "이 글 하나로 뉴스 맥락을 완전히 이해했다"고 말합니다.

## 글의 철학
- **맥락**: 뉴스 단순 요약이 아닌, "왜 이 일이 일어났나", "나에게 어떤 영향인가"까지
- **연결**: 세계 이슈 → 한국 영향, 경제 이슈 → 내 지갑·투자, 사회 이슈 → 실생활 대처법
- **신뢰**: 구체적 수치/날짜/출처로 신뢰도 확보 (2026년 기준)
- **공감**: 독자가 "그래서 나는 어떻게 해야 하지?"라는 질문에서 출발

## 필수 글 구조 (총 8,000~10,000자 이상)

### 1. 훅 + 핵심 키워드 선언 (400~600자)
- "오늘 뉴스에서 이 단어를 봤을 때 혼란스러웠다면" 식의 공감 유도
- 숫자/반전/놀라운 사실로 시작
- **훅 마지막 문장에 핵심 키워드 정확히 포함** (네이버 키워드 매칭 필수)
- "이 글을 읽으면 오늘 뉴스가 완전히 이해될 것"이라는 약속
- 절대 금지: "안녕하세요", "오늘은 ~알아보겠습니다"

### 2. 핵심 한 줄 정의
> **이 글의 핵심**: [한 문장 요약]

### 3. 배경·원인 섹션 (1,200자+)
- "왜 이 일이 일어났나" — 역사·경제·정치적 맥락
- h3 소제목 2~3개
- 독자가 몰랐던 배경 지식 제공

### 4. 현황 분석 섹션 (1,200자+)  
- 지금 상황이 어느 단계인가
- 핵심 수치/통계/날짜 포함
- 비교표 (전/후, 국가별, 연도별 등)

### 5. 한국에 미치는 영향 섹션 (1,500자+)
- 한국 독자 기준으로 구체적 영향
- 예: 기름값·물가·취업·주식·부동산 등 실생활 연결
- > 💡 **실전 대처법**: 박스 필수

### 6. 각계 반응 & 전문가 의견 (800자+)
- 정부, 기업, 시민, 전문가 각각의 시각
- 찬반 또는 다양한 관점 균형있게

### 7. 향후 전망 섹션 (1,000자+)
- 단기(1~3개월), 중기(~6개월), 장기(1년+) 시나리오
- 독자가 주목해야 할 신호

### 8. FAQ 5개 (네이버 스마트블록 핵심)
Q는 실제로 사람들이 검색하는 문장 그대로 (예: "~이란 무엇인가요?", "~이 나에게 미치는 영향")
A는 각 200자 이상, 핵심 키워드 자연 포함

### 9. 핵심 요약 테이블 (3열 이상)

### 10. 에디터 시각 (600자+) ← Google Helpful Content 핵심 — 반드시 포함
> **✍️ 에디터의 시각**

이 섹션은 **단순 뉴스 집합이 아닌 독자적 분석·시각**을 보여주는 핵심 구간입니다.
- "이 이슈에서 우리가 놓치고 있는 것은..."
- "제가 생각하는 핵심은 이렇습니다..."  
- "언론이 잘 다루지 않는 이면의 맥락..."
- 낙관/비관 시나리오 중 에디터의 판단 근거 제시
- 독자에게 전하고 싶은 한 가지 메시지
**규칙:** 절대 중립적 요약 금지 — 반드시 에디터 본인의 관점·판단·예측 포함

### 11. 마무리 + CTA (300자+)
- 핵심 메시지 재강조
- "다음에 이 뉴스에서 ~를 체크하세요" 식 구체적 행동 지침
- 댓글 질문 유도

## 라벨 체계 (allsweep 뉴스 블로그 전용)
아래 표준 라벨에서만 선택 (3~6개):
세계 동향, 세계 이슈, 세계 최신 뉴스,
사회 최신 뉴스, 사회 동향, 사회 이슈,
경제 동향, 경제 이슈, 경제 최신 뉴스,
IT 최신 뉴스, IT 동향, IT 이슈,
생활 최신 뉴스, 생활 동향, 생활 이슈,
한국 정치, 한국 경제, 국제 뉴스, 미국 정치, 중국 경제,
SEO 최적화, 오늘의 뉴스, 주요 뉴스

## 톤 & 스타일
- 구어체: "~이죠", "~거든요", "~예요", "~일 텐데요"
- 독자 호칭: "여러분"
- 어려운 용어 → 즉시 괄호 설명
- 문단 3~5줄 후 줄바꿈 (모바일 가독성)

## E-E-A-T 강화 규칙 (구글 Helpful Content Update 2023~ 핵심 랭킹 신호)
- "실제 사용해보니", "직접 취재한 결과" 등 경험 기반 표현 필수 1회 이상
- 구체적 수치/날짜 포함 ("2026년 3월 기준", "X부처 발표 자료")
- "~라고 알려져 있습니다" 대신 "~입니다 (출처: 공식 발표)"
- 에디터 관점 명시: "이 글에서는 ~관점에서 분석합니다"

## SEO (구글 + 네이버 동시)
- 첫 문단에 핵심 키워드 정확히 포함
- h2마다 LSI 키워드
- 외부 링크 최소 2개 (뉴스 원문, 공식 기관 등)"""

SYSTEM_PROMPT = """당신은 요즘IT, 브런치 Top 1% AI/기술 전문 블로거입니다.
월 100만 PV를 달성한 작가로, 독자들이 "이 글 하나로 다 해결됐어요"라고 말하는 수준의 글을 씁니다.

## 글의 철학
- **깊이**: 피상적 소개가 아닌 "왜", "어떻게", "실제로는"까지 파고듦
- **신뢰**: 구체적 수치/날짜/출처로 신뢰도 확보 (2026년 기준)
- **공감**: 독자의 실제 고민, 궁금증, 두려움에서 출발
- **실용**: 읽고 나면 바로 써먹을 수 있는 actionable 인사이트

## 필수 글 구조 (총 10,000자 이상)

### 1. 훅 + 정확 키워드 선언 (300~500자) ← 네이버 스마트블록 핵심
- 독자가 경험했을 법한 구체적 상황으로 시작 (공감 유도)
- 숫자나 반전 요소로 호기심 자극
- **[필수] 훅 마지막 문장 또는 바로 다음 문장에 핵심 키워드를 있는 그대로 포함**
  - 예: "이 글에서는 NotebookLM 사용법을 단계별로 알려드립니다."
  - 예: "n8n vs Make 비교를 실제 사용 경험을 바탕으로 정리했습니다."
  - 네이버는 정확 키워드 매칭 비중이 구글보다 훨씬 높음 — 검색창에 치는 단어 그대로
- "이 글을 읽으면 X를 얻을 수 있다"는 암묵적 약속
- 절대 금지: "안녕하세요", "오늘은 ~을 알아보겠습니다"

### 2. 핵심 한 줄 정의
> **이 글의 핵심**: [한 문장으로 핵심 가치 정의]

### 3. 목차 (선택적, 길 글일 때)
**이 글에서 다루는 것:**
- 항목1
- 항목2

### 4. 본론 섹션 5~7개 (각 1,200~2,000자)
각 섹션 구조:
```
## 🔍 섹션 제목

[도입: 왜 이게 중요한지 1~2문장]

### 세부 소제목 1
[상세 설명 + 구체적 예시/데이터]

### 세부 소제목 2  
[추가 설명]

> 💡 **실전 팁**: [바로 적용 가능한 팁]

[비교표 또는 체크리스트]
```

### 5. 실제 사례 섹션 (1,000자+)
- 실명/실제 회사/실제 수치 언급
- "A사는 이 방법으로 B를 달성했다" 형식

### 6. 주의사항/함정 섹션
- 독자가 빠지기 쉬운 실수 3~5개
- "이것만은 하지 마세요" 형식

### 7. FAQ (5개, SEO + 네이버 스마트블록 핵심)
## ❓ 자주 묻는 질문

**[FAQ 작성 규칙 — 반드시 준수]**
- Q는 반드시 "실제로 사람들이 네이버/구글 검색창에 치는 문장" 그대로 작성
  - 좋은 예: "NotebookLM 무료로 쓸 수 있나요?", "n8n Make 차이가 뭔가요?"
  - 나쁜 예: "NotebookLM의 주요 특징은 무엇인가요?" (아무도 이렇게 검색 안 함)
- FAQ JSON-LD가 자동 삽입되어 네이버·구글 리치 결과(People Also Ask)에 직접 노출됨
- A는 300자 이상, 핵심 키워드 자연 포함

**[고CPC FAQ 패턴 — 아래 유형 중 최소 2개 포함]**
- "~는 얼마인가요?" (가격 검색 → 고CPC 광고 유도)
- "~와 ~의 차이는?" (비교 검색 → 고CTR)
- "~하면 부작용/단점 있나요?" (우려 해소 → 전환율 높음)
- "~를 사면 후회하나요?" (구매 결정 직전 검색)

Q1: [검색창에 그대로 치는 질문]
A1: [300자 이상 상세 답변]

### 8. 핵심 요약 테이블
| 항목 | 내용 | 중요도 |
3열 이상 표

### 9. 마무리 + CTA (300자+)
- 핵심 메시지 재강조
- 댓글 질문 유도 (구체적)
- 다음 글 예고 또는 관련 주제 연결

## 톤 & 스타일
- 구어체 필수: "~이죠", "~거든요", "~해요", "~일 텐데요"
- 독자 호칭: "여러분"
- 전문용어 → 즉시 괄호로 한글 풀어쓰기
- 문단: 3~5줄 후 줄바꿈 (모바일 가독성)
- 데이터 인용 시 "2026년 X 기준" 명시
- 이모지는 섹션 제목에 1개, 팁 박스에 활용

## E-E-A-T 강화 규칙 (구글 Helpful Content Update 2023~ 핵심 랭킹 신호)
- "실제 사용해보니", "직접 테스트한 결과" 등 경험 기반 표현 필수 1회 이상
- 구체적 수치/날짜/버전 포함 ("2026년 3월 기준", "GPT-4o 1106 버전")
- "~라고 알려져 있습니다" 대신 "~입니다 (출처: 공식 문서)"
- 글쓴이 관점 명시: "이 글에서는 ~관점에서 분석합니다"

## SEO 필수 요소 (구글 + 네이버 동시 최적화)
- 첫 문단 2~3줄 안에 핵심 키워드를 **있는 그대로** 포함 (네이버는 정확 키워드 매칭 중요)
  - 예: 주제가 "NotebookLM 사용법"이면 → 첫 문단에 "NotebookLM 사용법"이 그대로 등장해야 함
- h2 섹션마다 LSI 키워드 분산
- 본문에 키워드 변형도 자연스럽게 포함 (예: "노트북LM", "NotebookLM 활용법", "구글 노트북LM")
- 외부 링크 앵커텍스트 자연스럽게
- 이미지 alt 텍스트 기술 방식으로 지시

## 분량
- 전체 6,000~8,000자 (API 제한 내 최대한 길게)
- 각 h2 섹션에 반드시 h3 소제목 2개 이상 포함
- FAQ 답변 각 150자 이상

## 절대 금지
- 근거 없는 주장 (수치 없는 "매우 효과적")
- 뻔한 마무리 ("오늘은 ~에 대해 알아봤습니다")
- h3 없이 h2만 나열하는 단조로운 구조
- 외부 링크 0개
- 3,000자 미만의 짧은 글"""


def generate_post(topic: str, keywords: list = None, angle: str = "") -> dict:
    keywords_str = ", ".join(keywords) if keywords else topic
    today = datetime.date.today().strftime("%Y년 %m월 %d일")

    # BLOG_TYPE별 라벨 지침 — SEO 키워드 기반 (검색의도 최적화)
    if BLOG_TYPE == "NEWS":
        labels_instruction = """이 포스트의 핵심 SEO 키워드를 라벨로 사용합니다 (5~8개, 쉼표 구분).

[라벨 작성 원칙]
1. 실제로 사람들이 네이버·구글에 검색하는 키워드 그대로 사용
2. 고유명사(인물·기업·지명·사건명) 반드시 포함
3. "~란", "~이유", "~영향", "~방법" 등 롱테일 검색 의도 반영
4. 카테고리명(세계 동향·경제 이슈 등) 대신 실제 검색어 사용
5. 2~5글자 단어 위주, 너무 긴 문장형 금지

[예시]
- 마크롱 방한 포스트 → 마크롱, 마크롱 방한, 한프랑스 경제협력, 프랑스 대통령, 한국 경제, 유럽 외교
- 호르무즈 해협 포스트 → 호르무즈 해협, 국제유가, 기름값, 물가상승, 이란 핵협상, 에너지 안보
- 영포티 트렌드 포스트 → 영포티, Young Forty, 4050세대, 세대갈등, 소비트렌드
- 부동산 금리 포스트 → 기준금리, 부동산 전망, 집값 하락, 아파트 매매, 금리 인상"""
        blog_style = "한국 시사·뉴스 블로그"
    else:
        labels_instruction = f"""이 포스트의 핵심 SEO 키워드를 라벨로 사용합니다 (7~10개, 쉼표 구분).

이 포스트의 주제 키워드 (반드시 라벨에 포함): {keywords_str}

[라벨 작성 원칙 — 반드시 준수]
1. 카테고리명 절대 금지: AI생산성, AI트렌드, AI기초, 오픈소스AI, 한국AI, AI에이전트 등 분류어 사용 금지
2. 위 주제 키워드를 기반으로 네이버·구글 실제 검색어 형태로 변환하여 포함
3. 도구·서비스 실명 포함: ChatGPT, Claude, Gemma, Ollama, Notion AI 등 구체적 이름
4. 행위 키워드 포함: "사용법", "설치방법", "활용법", "무료 사용", "비교", "차이점" 중 적합한 것
5. 검색 의도 키워드: "~하는 법", "~란", "~추천", "~후기", "~가격" 등 롱테일 형태
6. 3~8글자 키워드 위주 (너무 짧은 1글자, 너무 긴 15글자 이상 금지)

[좋은 예시]
- Gemma 4 Ollama 포스트 → Gemma 4, Ollama 사용법, 로컬 AI 실행, 구글 오픈소스 AI, LLM 무료 설치, 오픈소스 LLM, Gemma 한국어, AI 로컬 실행 방법
- ChatGPT 계약서 검토 포스트 → ChatGPT 계약서, AI 계약서 검토, 독소조항 찾는 법, 월세 계약서, 전세 계약 주의사항, 챗GPT 법률, 계약서 분석 AI
- Whisper Notion 강의정리 포스트 → Whisper 사용법, Notion AI 활용, 강의 자동정리, 음성 텍스트 변환, AI 회의록, 강의 요약 자동화, 노션 AI 사용법
- 챗GPT 의료정보 포스트 → 챗GPT 증상 검색, AI 의료 정보, 챗GPT 질병 진단, AI 오진, 의료 AI 신뢰성, 챗GPT 건강 정보, AI 병원 추천 문제

[나쁜 예시 — 이런 라벨 절대 금지]
- AI생산성, AI트렌드, AI기초, 오픈소스AI, 한국AI, AI에이전트, AI트렌드, LLM (단독 약어)"""
        blog_style = "요즘IT 상위 1%"

    # AI 블로그 여부 판단 (BLOG_TYPE이 NEWS가 아닌 경우)
    is_ai_blog = (BLOG_TYPE != "NEWS")

    # 구매 의도 CTA 지침 (AI 블로그 전용)
    if is_ai_blog:
        cta_instructions = """
## 💰 구매 의도 CTA (고CPC 최적화 — 반드시 포함)

AI 도구/서비스를 소개하는 섹션이 있을 경우, 각 도구 소개 섹션 끝에 반드시 추가:
```
> 🔗 **[도구명] 공식 사이트에서 가격 확인하기** → [공식 URL]
```
예시:
- ChatGPT: https://openai.com/chatgpt/pricing
- Claude: https://claude.ai/pricing  
- Cursor: https://www.cursor.com/pricing
- GitHub Copilot: https://github.com/features/copilot

**무료/유료 요금제 비교표 (필수)**: 아래 형식으로 반드시 1개 이상 포함
| 플랜 | 가격 | 주요 기능 | 추천 대상 |
|------|------|-----------|-----------|
| 무료 | $0/월 | 기능A, 기능B | 가벼운 사용자 |
| 유료 | $XX/월 | 기능A~D | 전문 사용자 |

**FAQ 가격 관련 질문 (필수 1개 이상)**: FAQ 5개 중 최소 1개는 가격/비용 관련 질문
예시 Q: "ChatGPT Plus 가격이 올랐나요? 유료 플랜 가치 있나요?"
예시 Q: "Cursor AI 무료로 쓸 수 있나요? 유료 플랜 필요한 경우는?"
예시 Q: "Claude Pro 구독 취소하면 어떻게 되나요?"
"""
    else:
        cta_instructions = ""

    prompt = f"""오늘은 {today}입니다. 아래 주제로 {blog_style} 수준의 딥다이브 글을 작성하세요.

**주제**: {topic}
**핵심 키워드**: {keywords_str}
{f'**글쓰기 각도**: {angle}' if angle else ''}
{cta_instructions}
## 이 글에서 반드시 포함해야 할 것

1. **강렬한 훅** (300~500자): 독자가 "맞아, 나도 이런 경험 있어"라고 할 상황
2. **핵심 정의 박스**: `> **이 글의 핵심**: ...`
3. **본론 6~7개 섹션** (각 1,000~2,000자):
   - h2 섹션마다 h3 소제목 2~3개 필수
   - 구체적 데이터/수치/날짜 포함
   - `> 💡 **실전 팁**:` 박스 섹션당 1개
   - 비교표 최소 2개 (AI 도구 비교인 경우 **무료/유료 요금제 비교표 필수**)
4. **실제 사례 섹션**: 실명 기업/인물 + 구체적 결과 수치
5. **주의사항 섹션**: 독자가 빠지기 쉬운 함정 3~5개
6. **FAQ 5개**: 각 답변 200자 이상 상세하게 (AI 블로그: 가격 관련 질문 최소 1개 필수)
7. **핵심 요약 테이블**: 3열 이상
8. **마무리 CTA**: 구체적 댓글 질문 유도
   - AI 도구 소개 글: 각 도구별 공식 사이트 가격 링크 포함
9. **관련 검색어 마커**: 본문 최하단(마무리 CTA 이후)에 아래 형식으로 반드시 1줄 추가
   - `[RELATED_SEARCH:관련키워드1|관련키워드2|관련키워드3]`
   - 예: `[RELATED_SEARCH:ChatGPT 사용법|Claude AI 비교|AI 도구 추천]`
   - 이 마커는 추후 내부 링크로 자동 교체됩니다 (토픽 클러스터링)

## 분량 목표
- **전체 6,000~8,000자** (토큰 한계 내 최대)
- 각 h2 섹션: 최소 600자, h3 소제목 2개 이상
- FAQ 각 답변: 150자 이상

## 외부 링크 (최소 2개)
- 신뢰도 있는 출처에 자연스럽게 링크
- 예: [OpenAI 발표](https://openai.com/blog/...) 형식

아래 형식으로 정확히 응답:

===TITLE===
클릭 유발 제목 (40자 이내, 이모지 절대 사용 금지, 숫자·연도(2026) 권장, "추천/비교/완전정리/후회없는" 등 클릭 유도어 활용)
===LABELS===
{labels_instruction}
===META===
구글/네이버 검색결과 설명 (150~160자)
[작성 규칙 — 네이버 공식 가이드 기준]
- 핵심 키워드 1회만 포함 (반복 금지 — 네이버 패널티)
- 1~2문장, 콘텐츠 내용을 간결하게 설명
- 키워드 나열 금지, 자연스러운 문장으로 작성
- 형식: "[핵심 키워드]를 [독자]를 위해 [혜택]을 [연도] 기준으로 정리했습니다."
===SUMMARY===
네이버 스마트블록 요약박스 (80~120자, 본문 최상단에 노출)
[작성 규칙]
- 독자가 얻는 것을 구체적으로 1~2문장으로 설명
- 핵심 키워드 자연스럽게 포함 (단, 반복 금지)
- 형식: "이 글에서는 [핵심 키워드]를 [구체적 방법/단계]로 정리합니다. [독자 혜택]."
- META와 내용이 달라야 함 (중복 금지)
===KEYWORDS_SEO===
SEO 롱테일 키워드 5개 (쉼표 구분)
===FAQ===
Q1: 질문
A1: 상세 답변 (200자 이상)
Q2: 질문
A2: 상세 답변
Q3: 질문
A3: 상세 답변
Q4: 질문
A4: 상세 답변
Q5: 질문
A5: 상세 답변
===IMAGE===
대표 이미지 영문 검색어 (4~5단어, 구체적)
===CONTENT===
완성된 마크다운 본문 (10,000자 이상)
===END==="""

    client_kwargs = dict(base_url=ANTHROPIC_BASE_URL, timeout=600, max_retries=2)
    if ANTHROPIC_API_KEY:
        client_kwargs["api_key"] = ANTHROPIC_API_KEY
    client = _anthropic.Anthropic(**client_kwargs)

    # 블로그 타입에 따라 시스템 프롬프트 선택
    active_system_prompt = SYSTEM_PROMPT_NEWS if BLOG_TYPE == "NEWS" else SYSTEM_PROMPT

    # 스트리밍으로 504 timeout 방지 (비스트리밍 시 Anthropic 서버 504 발생 — 스트리밍은 16000도 안전)
    text = ""
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=16000,
        system=active_system_prompt,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk

    def extract_section(t, key):
        all_tags = ["===TITLE===", "===LABELS===", "===META===", "===SUMMARY===",
                    "===KEYWORDS_SEO===", "===FAQ===", "===IMAGE===", "===CONTENT===", "===END==="]
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

    title_raw = extract_section(text, "TITLE")
    # 제목 이모지 강제 제거 (Claude가 지시 무시 시 후처리)
    title = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001F9FF]', '', title_raw).strip()
    title = re.sub(r'^\s*[\W_]+\s*', '', title).strip()  # 앞 특수문자 제거
    # Blogger API 400 방지: 제목 내 큰따옴표 → 작은따옴표 (YAML 파싱 후 API 전달 시 문제)
    title = title.replace('"', "'").replace('\u201c', "'").replace('\u201d', "'")

    labels = [l.strip() for l in extract_section(text, "LABELS").split(",") if l.strip()]
    meta_desc = extract_section(text, "META")
    naver_summary = extract_section(text, "SUMMARY")  # 네이버 스마트블록 요약박스
    seo_keywords = extract_section(text, "KEYWORDS_SEO")
    faq_raw = extract_section(text, "FAQ")
    image_query = extract_section(text, "IMAGE")
    content = extract_section(text, "CONTENT")

    # 글자수 체크 (로그만)
    char_count = len(content.replace(' ', '').replace('\n', ''))
    print(f"   📊 생성된 글자수: {char_count:,}자")
    # 1-3. 최소 글자수 경고 (2,000자 미만)
    if char_count < 2000:
        print(f"   [WARN] 본문 글자수 {char_count:,}자 — 2,000자 미만입니다. 콘텐츠 품질을 확인하세요.")

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
        "naver_summary": naver_summary or meta_desc,  # 없으면 meta_desc 폴백
        "seo_keywords": seo_keywords,
        "faqs": faqs,
        "faq_raw_text": faq_raw,  # G-4: build_faq_jsonld fallback용
        "image_query": image_query or "artificial intelligence technology 2026"
    }


def build_faq_jsonld(faq_raw: str) -> str:
    """FAQ 섹션을 FAQPage JSON-LD로 변환 — 구글 리치 스니펫(People Also Ask) 노출용
    
    G-4: FAQPage Schema 추가 (generate_post.py용)
    post_to_blogger.py의 build_json_ld()가 faqs 리스트로 JSON-LD를 생성하므로,
    이 함수는 faqs 파싱 실패 시 fallback으로 faq_raw에서 직접 스키마 추출.
    """
    import re as _re
    # h3 기반 파싱 (### 질문?\n답변 패턴)
    pairs = []
    questions = _re.findall(r'#{2,3}\s+(.+\?)', faq_raw)
    answers = _re.split(r'#{2,3}\s+.+\?', faq_raw)[1:]
    for q, a in zip(questions[:5], answers[:5]):
        a_clean = _re.sub(r'<[^>]+>', '', a).strip()[:300]
        if q and a_clean:
            pairs.append({
                "@type": "Question",
                "name": q.strip(),
                "acceptedAnswer": {"@type": "Answer", "text": a_clean}
            })
    # Q: / A: 패턴 폴백
    if not pairs:
        qa_blocks = _re.findall(r'Q\d*[.:]\s*(.+?)\nA\d*[.:]\s*(.+?)(?=\nQ\d*[.:]|\Z)',
                                faq_raw, _re.DOTALL)
        for q, a in qa_blocks[:5]:
            a_clean = _re.sub(r'<[^>]+>', '', a).strip()[:300]
            if q.strip() and a_clean:
                pairs.append({
                    "@type": "Question",
                    "name": q.strip(),
                    "acceptedAnswer": {"@type": "Answer", "text": a_clean}
                })
    if not pairs:
        return ""
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": pairs
    }
    return (
        f'<script type="application/ld+json">'
        f'{json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}'
        f'</script>'
    )


def make_seo_slug(title: str, topic: str) -> str:
    """SEO 최적화 슬러그 생성 — 제목 기반, 영문 키워드 추출"""
    import unicodedata

    # 이모지/특수문자 제거
    clean = re.sub(r'[^\w\s가-힣a-zA-Z0-9-]', ' ', title)

    # 영문 단어 우선 추출 (SEO에 유리)
    en_words = re.findall(r'[a-zA-Z]{2,}', clean)
    ko_words = re.findall(r'[가-힣]{2,}', clean)

    slug_parts = []

    # 영문 키워드가 있으면 우선 사용 (최대 4개)
    if en_words:
        slug_parts.extend([w.lower() for w in en_words[:4]])

    # 한글 키워드에서 로마자 변환 가능한 브랜드명 매핑
    ko_brand_map = {
        '인공지능': 'ai', '머신러닝': 'machine-learning', '딥러닝': 'deep-learning',
        '챗지피티': 'chatgpt', '클로드': 'claude', '제미나이': 'gemini',
        '오픈에이아이': 'openai', '앤트로픽': 'anthropic', '구글': 'google',
        '마이크로소프트': 'microsoft', '메타': 'meta', '삼성': 'samsung',
        '네이버': 'naver', '카카오': 'kakao', '자율주행': 'autonomous',
        '양자화': 'quantization', '파인튜닝': 'finetuning', '에이전트': 'agent',
        '보안': 'security', '의료': 'medical', '교육': 'education',
        '금융': 'finance', '스타트업': 'startup', '투자': 'investment',
        '로봇': 'robot', '반도체': 'semiconductor', '언어모델': 'llm',
        '가이드': 'guide', '방법': 'how-to', '비교': 'comparison', '추천': 'recommended',
        '완전정복': 'complete-guide', '입문': 'beginner', '튜토리얼': 'tutorial',
        '차이': 'difference', '장단점': 'pros-cons', '분석': 'analysis',
        '트렌드': 'trends', '활용': 'usage', '실전': 'practical',
        '최신': 'latest', '무료': 'free', '유료': 'premium', '설치': 'install',
        '프롬프트': 'prompt', '에이전트': 'agent', '자동화': 'automation',
        '한국어': 'korean', '국내': 'korea', '기업': 'enterprise', '스타트업': 'startup',
        '윤리': 'ethics', '규제': 'regulation', '정책': 'policy',
        '성능': 'performance', '속도': 'speed', '비용': 'cost', '가격': 'price',
        '파인튜닝': 'finetuning', '양자화': 'quantization',
        '검색': 'search', '요약': 'summary', '번역': 'translation',
        '이미지': 'image', '영상': 'video', '음성': 'voice',
        '챗봇': 'chatbot', '어시스턴트': 'assistant',
    }

    # 순수 숫자만으로 이루어진 슬러그 파트 제거
    slug_parts = [p for p in slug_parts if not re.match(r'^\d+$', p)]

    for ko, en in ko_brand_map.items():
        if ko in clean and en not in slug_parts:
            slug_parts.append(en)
            if len(slug_parts) >= 5:
                break

    # 슬러그 조합
    if slug_parts:
        slug = '-'.join(slug_parts)[:50]
    else:
        # 완전 폴백: topic ascii
        slug = "".join(
            c if c.isascii() and (c.isalnum() or c == "-") else "-"
            for c in topic.lower().replace(" ", "-")
        )
        slug = "-".join(filter(None, slug.split("-")))[:40] or "post"

    # 슬러그 끝에 연도 추가 (제목에 2025/2026 등 포함 시)
    year_match = re.search(r'\b(202[0-9])\b', title)
    if year_match:
        year = year_match.group(1)
        if year not in slug:
            slug = (slug + '-' + year)[:55]

    return slug or "ai-post"


def save_as_markdown(post_data: dict, topic: str) -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    slug = make_seo_slug(post_data.get("title", topic), topic)
    posts_dir = os.environ.get("POSTS_DIR", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    filename = f"{posts_dir}/{today}-{slug}.md"

    safe_title   = post_data['title'].replace('"', '\\"')
    safe_meta    = post_data.get('meta_description', '').replace('"', '\\"')
    safe_summary = post_data.get('naver_summary', '').replace('"', '\\"')
    labels_yaml  = json.dumps(post_data["labels"], ensure_ascii=False)
    faq_yaml     = json.dumps(post_data.get("faqs", []), ensure_ascii=False)

    # G-4: FAQPage JSON-LD 생성 (post_to_blogger.py가 faqs로 처리하지만 fallback용으로 저장)
    faq_jsonld = build_faq_jsonld(post_data.get("faq_raw_text", ""))

    content = f"""---
title: "{safe_title}"
labels: {labels_yaml}
draft: false
meta_description: "{safe_meta}"
naver_summary: "{safe_summary}"
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
