#!/usr/bin/env python3
"""
고퀄리티 블로그 포스트 자동 생성 v2
- 요즘IT/브런치 상위 1% 수준 (10,000자+)
- 딥다이브 구조: 배경 → 원인 → 사례 → 실전 → FAQ → 요약
- h3 세부 섹션, 외부 링크, 비교표 필수
- SEO: FAQ 스키마, 롱테일 키워드, E-E-A-T 신호
"""
import os

# .env 자동 로드 (cron/subprocess 환경에서도 동작)
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env_loader import load_env, make_anthropic_client, get_model
load_env()
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

## FACT-CHECK 원칙 (할루시네이션 절대 금지 — 최우선 준수)

**존재하지 않는 정보 창작 금지:**
- 실제 공개되지 않은 제품명·서비스명·기업 발표를 임의로 만들어내지 말 것
- 구체적 수치(%, 원, 건수 등)는 반드시 실제 출처 기관명 명시: "(출처: 한국인터넷진흥원)", "(Gartner 2025)" 등
- 출처를 확인할 수 없는 수치는 사용하지 말고, "상당한", "큰 폭의" 등 정성적 표현으로 대체
- "OO연구에 따르면", "OO보고서에서" 형태 사용 시 실제 존재하는 기관·보고서만 인용
- 실명 기업·인물 사례는 실제 공개된 정보(뉴스, 공식 발표)만 인용

**불확실한 정보 처리 방법:**
- 확인된 사실: "~입니다", "~했습니다" (단정형)
- 공식 발표 인용: "~라고 발표했습니다 (출처: OO)" (출처 명시)
- 추정·전망: "~로 예상됩니다", "~로 알려졌습니다" (완화형)
- 확인 불가: 해당 내용 아예 제외 (가상 수치 삽입 금지)


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

## h2 제목 규칙 (SEO 핵심 — 반드시 준수)
- h2 제목에 검색 키워드를 자연스럽게 포함할 것
- "함정 1:", "방법 1:", "단계 2:" 같은 번호 기반 소제목 대신 키워드 기반 소제목 선호
  - ❌ 나쁜 예: "함정 1: 실적 계산 오류", "방법 3: 활용하기"
  - ✅ 좋은 예: "전월 실적 계산에서 빠지는 항목 총정리", "신용카드 혜택 100% 활용하는 법"
- 각 h2는 독자가 네이버·구글 검색창에 실제로 칠 만한 구체적 문구를 포함할 것
- h2마다 LSI(연관) 키워드를 자연스럽게 녹여 넣을 것

## 라벨 체계 (allsweep 뉴스 블로그 전용)
아래 표준 라벨에서 3개만 선택:
재테크, 신용카드, 보험, 부동산, 주식, 절세, 연금,
세계 뉴스, 경제 뉴스, 사회 뉴스, IT 뉴스, 생활정보

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

## FACT-CHECK 원칙 (할루시네이션 방지 — 최우선)
- 존재하지 않는 제품/서비스/수치를 창작하지 말 것
- 수치 인용 시 출처 명시 필수: "(출처: Gartner 2025)", "(출처: 공식 발표)" 형태
- 확인 불가 정보는 "~로 알려졌습니다", "~로 추정됩니다" 등 완화 표현 사용
- 실명 기업 사례는 실제 공개된 정보만 인용 (가상 사례 금지)

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

## h2 제목 규칙 (SEO 핵심 — 반드시 준수)
- h2 제목에 검색 키워드를 자연스럽게 포함할 것
- "함정 1:", "방법 1:", "단계 2:" 같은 번호 기반 소제목 대신 키워드 기반 소제목 선호
  - ❌ 나쁜 예: "함정 1: 설치 오류", "방법 2: 활용하기", "포인트 3: 주의사항"
  - ✅ 좋은 예: "Claude API 설치할 때 자주 겪는 오류와 해결법", "실전 프롬프트 활용 가이드"
- 각 h2는 독자가 네이버·구글 검색창에 실제로 칠 만한 구체적 문구를 포함할 것
- h2마다 LSI(연관) 키워드를 자연스럽게 녹여 넣을 것

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
        labels_instruction = f"""이 포스트에 맞는 라벨 3개만 작성합니다 (쉼표 구분).

[라벨 작성 원칙]
- 반드시 이 글의 실제 핵심 주제를 대표하는 구체적 라벨 사용 (제네릭 라벨 금지)
- "IT 뉴스", "경제 뉴스", "사회 뉴스", "생활정보" 같은 매우 넓은 라벨은 사용 금지
- 이 글의 주제: {topic} — 이 주제와 직접 연관된 구체적 키워드로 선택
- 독자가 비슷한 글을 모아볼 때 클릭할 만한 분류어
- 예시 (주제에 맞게 선택):
  · 사이버보안 주제 → "사이버보안", "AI 보안", "랜섬웨어 대응"
  · 재테크 주제 → "ISA", "연금저축", "세금 절약"
  · 부동산 주제 → "전세보증금", "임대차보호법", "집값 전망"
  · AI 기술 주제 → "ChatGPT", "AI 에이전트", "생성형 AI"
  · 보험 주제 → "실손보험", "보험료 절약", "보험 비교"
- 절대 금지 라벨: "IT 뉴스", "경제 뉴스", "사회 뉴스", "생활정보", "뉴스", "정보"(단독)"""
        blog_style = "한국 시사·뉴스 블로그"
    else:
        labels_instruction = f"""이 포스트에 맞는 라벨 3개만 작성합니다 (쉼표 구분).

[라벨 작성 원칙]
- 이 글의 핵심 주제를 대표하는 카테고리 3개
- 독자가 비슷한 글을 모아볼 때 클릭할 만한 분류어
- 예: ChatGPT, AI 활용법, 업무자동화"""
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
클릭 유발 제목 (40자 이내, 이모지 절대 사용 금지, 큰따옴표 절대 사용 금지)
[제목 다양성 필수] 아래 형식 중 하나를 선택 (매번 다른 형식 사용, '완전정리' 남발 금지):
- 숫자형: '2026 ChatGPT API 연동 5단계 실전 가이드'
- 비교형: 'Claude vs GPT-4o, 실제로 써보니 이게 달랐다'
- 질문형: 'AI 에이전트, 챗봇과 뭐가 다를까? 한 번에 이해하기'
- 방법형: '재택근무자가 Make로 반복 업무 3개 없애는 법'
- 결과형: 'ISA 1년 운용 후기 -- 세금 얼마나 아꼈나'
- 경고형: 'AI 보안 도입 전 반드시 알아야 할 5가지 함정'
- 완전정리형: 불가피할 때만, 주당 최대 2회 제한
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

    client = make_anthropic_client(timeout=600, max_retries=2)

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


def slugify_heading(text: str) -> str:
    """h2 헤딩 텍스트를 anchor id로 변환 (한글 포함 slugify).
    - 이모지/특수문자 제거, 공백->하이픈, 소문자
    - 한글은 그대로 유지 (URL 인코딩은 브라우저가 처리)
    """
    # 이모지 제거
    text = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001F9FF]', '', text)
    # 마크다운 강조 기호 제거
    text = re.sub(r'[*_`#]', '', text)
    # 앞뒤 공백 제거
    text = text.strip()
    # 영문 소문자로
    text = text.lower()
    # 영문/숫자/한글 이외 -> 하이픈
    text = re.sub(r'[^\w\uAC00-\uD7A3a-z0-9]', '-', text)
    # 연속 하이픈 압축
    text = re.sub(r'-+', '-', text).strip('-')
    return text or 'section'


def build_toc_and_cta(content: str, blog_type: str) -> str:
    """포스트 본문 마크다운에서 ## 헤딩을 추출해 목차+CTA HTML을 생성,
    첫 번째 ## 헤딩 직전에 삽입해서 반환.

    - blog_type == 'NEWS' -> allsweep CTA
    - 그 외              -> aikeeper CTA
    """
    # 모든 ## 헤딩 추출 (### 이상 제외)
    h2_pattern = re.compile(r'^## (.+)$', re.MULTILINE)
    headings = h2_pattern.findall(content)

    if not headings:
        return content  # ## 헤딩 없으면 원본 반환

    # 목차 아이템 생성
    items_html = ''
    for heading in headings:
        anchor = slugify_heading(heading)
        # 이모지/마크다운 제거한 표시용 텍스트
        display = re.sub(r'[\U00010000-\U0010ffff\U00002600-\U000027BF\U0001F300-\U0001F9FF]', '', heading)
        display = re.sub(r'[*_`#]', '', display).strip()
        items_html += (
            '<li>'
            '<a href="#' + anchor + '" style="color:#4f6ef7;text-decoration:none;">'
            + display +
            '</a></li>\n    '
        )

    toc_html = (
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;'
        'padding:20px 24px;margin:2em 0;">\n'
        '<p style="font-weight:700;font-size:1em;margin:0 0 12px;color:#1a202c;">'
        '\U0001F4CB \ubaa9\ucc28'  # 📋 목차
        '</p>\n'
        '<ol style="margin:0;padding-left:20px;color:#4a5568;line-height:2;">\n    '
        + items_html.rstrip() + '\n'
        '</ol>\n'
        '</div>\n'
    )

    # CTA HTML (blog_type 분기)
    if blog_type == 'NEWS':
        cta_html = (
            '<div style="background:linear-gradient(135deg,#1a0a00,#8B0000);border-radius:12px;'
            'padding:20px 24px;margin:1em 0 2em;text-align:center;">\n'
            '<p style="color:#fff;font-weight:700;font-size:1em;margin:0 0 8px;">'
            '\U0001F4F0 \uc62c\uc2a4\uc715 \u2014 \ub9e4\uc77c \ud575\uc2ec \ub274\uc2a4\ub97c \ube60\ub974\uac8c \uc815\ub9ac\ud569\ub2c8\ub2e4'
            '</p>\n'
            '<a href="https://www.allsweep.xyz" style="color:#ffa040;font-size:.9em;">'
            'allsweep.xyz \ubc14\ub85c\uac00\uae30 \u2192'
            '</a>\n'
            '</div>\n'
        )
    else:
        cta_html = (
            '<div style="background:linear-gradient(135deg,#0D1B4B,#1565c0);border-radius:12px;'
            'padding:20px 24px;margin:1em 0 2em;text-align:center;">\n'
            '<p style="color:#fff;font-weight:700;font-size:1em;margin:0 0 8px;">'
            '\U0001F916 AI\ud0a4\ud37c \u2014 \ub9e4\uc77c \ucd5c\uc2e0 AI \ud2b8\ub80c\ub4dc\ub97c \ud55c\uad6d\uc5b4\ub85c \uc815\ub9ac\ud569\ub2c8\ub2e4'
            '</p>\n'
            '<a href="https://aikeeper.allsweep.xyz" style="color:#63b3ed;font-size:.9em;">'
            'aikeeper.allsweep.xyz \ubc14\ub85c\uac00\uae30 \u2192'
            '</a>\n'
            '</div>\n'
        )

    insert_block = toc_html + cta_html

    # 첫 번째 ## 헤딩 직전에 삽입
    match = h2_pattern.search(content)
    insert_pos = match.start()
    new_content = content[:insert_pos] + insert_block + content[insert_pos:]
    return new_content


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

    # 목차 + CTA 자동 삽입
    body_content = build_toc_and_cta(post_data['content'], BLOG_TYPE)

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

{body_content}
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
