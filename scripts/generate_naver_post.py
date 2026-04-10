#!/usr/bin/env python3
"""
네이버 홈판 최적화 포스팅 생성기 v1
────────────────────────────────────────
홈판 알고리즘 분석 기반 (2026-04-11):
- 대화체 1인칭 경험담 문체
- 2-3줄 짧은 단락 (모바일 최적화)
- 체류시간 최대화 구조
- 해시태그 10-15개
- 공감/댓글 유도 문장
- 결론 선제시 구조
"""
import os, sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env, make_anthropic_client, get_model
load_env()

# ── 환경변수 ───────────────────────────────────────────
TOPIC      = os.environ.get("TOPIC", "")
LABELS     = os.environ.get("LABELS", "")
PRODUCTS_JSON = os.environ.get("PRODUCTS_JSON", "")
POST_URL   = os.environ.get("POST_URL", "")   # ggultongmon 원본 URL

SYSTEM_PROMPT = """당신은 네이버 블로그 홈판(홈피드) 노출에 특화된 콘텐츠 전문가입니다.

## 실제 홈판 노출 포스팅 109개 분석 결과 (2026-04-11)

### 홈판 알고리즘이 보는 핵심 지표
- 체류시간 (스크롤 깊이) > 공감수 > 댓글수 > 클릭률

### 제목 공식 (실제 데이터 기반)
- **경험담형 50%**: "[내돈내산] [제품명] 솔직 후기 | [카테고리] 추천"
- **숫자형 16%**: "쿠팡 [카테고리] 추천 TOP N | 내돈내산 후기"
- **추천형 10%**: "이건 무조건 사야해! 쿠팡 [카테고리] 가성비 꿀템"
- **질문형 7%**: "[제품명] 정말 효과 있을까? 직접 써봤어요"
- 최적 제목 길이: **25~40자** (평균 34.2자)
- 반드시 포함: 내돈내산 OR 솔직후기 OR 직접써봤 OR TOP N

### 본문 구조 (실제 홈판 노출 포스팅 표준)
1. **친근한 오프닝** (3줄 이내): "안녕하세요! 오늘은..." / "혹시 이런 경험 있으시죠?"
2. **구매 계기** (2-3줄): 왜 찾게 됐는지 공감 스토리
3. **결론 먼저** (1-2줄): "결론부터 말하면..." / "솔직히 말할게요"
4. **상품별 리뷰** (각 10-15줄): 장점 2-3개 + 단점 1개 (솔직하게)
5. **이런 분께 추천** (3-5줄): 구체적 대상 명시
6. **마무리 CTA** (2-3줄): 댓글/공감 유도 + 쿠팡 링크
7. **파트너스 고지**: "이 포스팅은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다."
8. **해시태그 12-15개**: #쿠팡 #내돈내산 #[제품명] #[카테고리] #솔직후기 #로켓배송 #쿠팡추천 #가성비 #꿀템 ...

### 본문 길이: 1,500~2,500자 (평균 2376자)

### 반드시 지킬 문체 규칙
- ✅ 대화체: "~요", "~네요", "~죠", "~더라고요", "~거든요"
- ✅ 1인칭: "제가", "저는", "저도", "직접 써봤는데"
- ✅ 짧은 단락: 2-3줄마다 줄바꿈
- ✅ 독자 질문: "어떠세요?", "혹시 이런 분들 계시죠?"
- ❌ 격식체 금지: "~합니다, ~입니다" 과다 사용 금지
- ❌ 표/HTML 태그 금지
- ❌ 5줄 이상 연속 단락 금지

### 쿠팡 링크 삽입 방식 (자연스럽게)
- "쿠팡에서 확인해보시면 → [링크]"
- "로켓배송으로 빠르게 받을 수 있어요 👇 [링크]"
- "현재 가격이 더 내렸을 수도 있으니 확인해보세요 → [링크]"

### 고지 문구 (필수 포함)
이 포스팅은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다."""


def build_prompt(topic: str, products: list, labels: list, original_url: str) -> str:
    prod_summary = ""
    for i, p in enumerate(products[:3]):
        name = p.get("productName", p.get("name", "상품"))
        price = p.get("price", "")
        url = p.get("shortenUrl", p.get("coupang_url", ""))
        prod_summary += f"\n상품{i+1}: {name} / {price}\n링크{i+1}: {url}\n"

    labels_str = ", ".join(labels[:5]) if labels else topic

    return f"""다음 상품 비교를 주제로 네이버 홈판 최적화 블로그 포스팅을 작성해주세요.

주제: {topic}
카테고리/키워드: {labels_str}
원본 상세글: {original_url}

상품 정보:
{prod_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
작성 조건:

[제목] 25-40자, 경험담형 필수
좋은 예: "6,990원 키친타월이 12,770원이랑 흡수력 차이 날까? 직접 써봤어요"
         "이건 무조건 사야해! 쿠팡 [카테고리] 가성비 꿀템 추천"
         "[내돈내산] [제품명] 솔직 후기 — 3개 다 써봤습니다"

[본문 구조 — 반드시 이 순서로, 2-3줄 단락 유지]

1. 공감 오프닝 (3-5줄)
   "안녕하세요! 오늘은..." 또는 "혹시 이런 고민 있으시죠?"
   독자가 겪는 구매 고민 상황 묘사

2. 구매 계기 스토리 (3-5줄)
   왜 이 제품을 찾게 됐는지 1인칭으로
   "저도 처음엔..." "우연히 발견했는데..."

3. 결론 먼저 (2-3줄)
   "결론부터 말하면..." 또는 "솔직히 말할게요"
   3개 중 어떤 걸 추천하는지 한 줄 요약

4. 상품별 솔직 리뷰 (각 상품 10-15줄)
   - 상품명 + 가격 자연스럽게 언급
   - 장점 2-3개 (구체적, 경험담)
   - 단점 1개 (솔직하게)
   - "이런 분께 추천" 1-2줄
   - 쿠팡 링크: "쿠팡에서 확인해보시면 → {'{링크URL}'}"

5. 예산별/상황별 선택 가이드 (5-8줄)
   "가성비 원하면 XX, 프리미엄 원하면 XX"

6. 마무리 CTA (3-4줄)
   "어떤 거 선택하셨나요? 댓글로 알려주세요 :)"
   "도움됐다면 공감 눌러주세요 ♥"
   자세한 내용: {original_url}

7. 파트너스 고지 (필수, 본문 하단)
   "이 포스팅은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받을 수 있습니다."

8. 해시태그 (12-15개, 마지막 줄에 붙여서)
   #쿠팡 #내돈내산 #솔직후기 #[제품카테고리] #쿠팡추천 #로켓배송 #가성비 #꿀템 #[제품명] #비교후기 + 상황키워드 추가

[분량] 전체 1,800~2,500자
[문체] 대화체 필수, "~요 ~네요 ~더라고요 ~거든요" 어미 사용

지금 바로 완성본을 작성해주세요. 제목부터 해시태그까지 하나의 완성된 포스팅으로."""


def generate_naver_post(topic: str, products: list, labels: list, original_url: str) -> dict:
    client = make_anthropic_client(timeout=120, max_retries=2)
    prompt = build_prompt(topic, products, labels, original_url)

    full_text = ""
    with client.messages.stream(
        model=get_model(),
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for chunk in stream.text_stream:
            full_text += chunk

    # 제목 추출
    lines = full_text.strip().split('\n')
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('[제목]') or stripped.startswith('제목:') or stripped.startswith('**제목'):
            title = stripped.replace('[제목]','').replace('제목:','').replace('**제목**','').replace('**','').strip()
            body_start = i + 1
            break
        elif i == 0 and len(stripped) < 50:
            title = stripped.replace('#','').strip()
            body_start = 1
            break

    if not title:
        title = topic[:40]

    body = '\n'.join(lines[body_start:]).strip()

    return {"title": title, "body": body, "full": full_text}


if __name__ == "__main__":
    if not TOPIC:
        print("TOPIC 환경변수 필요")
        sys.exit(1)

    products = []
    if PRODUCTS_JSON:
        try:
            products = json.loads(PRODUCTS_JSON)
        except Exception:
            pass

    labels = [l.strip() for l in LABELS.split(',') if l.strip()]

    print(f"[네이버 포스트 생성] 주제: {TOPIC}")
    result = generate_naver_post(TOPIC, products, labels, POST_URL)

    print(f"\n=== 제목 ===\n{result['title']}")
    print(f"\n=== 본문 ({len(result['body'])}자) ===\n{result['body'][:500]}...")

    # GITHUB_OUTPUT에 저장
    output_file = os.environ.get("GITHUB_OUTPUT", "/tmp/naver_post.txt")
    with open(output_file, "w") as f:
        f.write(f"naver_title={result['title']}\n")
        # body는 별도 파일로
        body_path = output_file.replace('.txt', '_body.txt')
        with open(body_path, 'w') as bf:
            bf.write(result['body'])
        f.write(f"naver_body_path={body_path}\n")
    print(f"\n저장 완료 → {output_file}")
