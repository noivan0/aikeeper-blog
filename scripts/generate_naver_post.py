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

SYSTEM_PROMPT = """당신은 네이버 블로그 홈판 상위 노출에 특화된 콘텐츠 전문가입니다.

아래는 실제 네이버 홈판 상위 노출 포스팅 100개를 분석한 정밀 데이터입니다.

━━━━ 100개 실제 데이터 기반 원칙 ━━━━

【본문 길이】 목표 1,500~2,000자 (100개 중앙값 1,787자)
【이미지 전략】 상품당 쿠팡 링크 2~3개 삽입 → 이미지+OG카드 6개 이상 목표
  - 첫 번째: 메인 상품 링크
  - 두 번째: 동일 상품 다른 용량/구성 링크 or 관련 상품 링크
  - 세 번째: 비교 상품 or 함께 사면 좋은 상품 링크
【제목】 28~42자 (중앙값 34자)
【해시태그】 없거나 4~8개 최소화 (상위 노출 포스팅 절반이 해시태그 없음)

【오프닝 유형 — 3가지 중 선택, 매번 다르게】
A) 상황 서술형 (가장 자연스러움): "약 5년 쓰던 청소기가 망가졌다. 갑자기 사려니 돈이 아까운 ㅋㅋ"
B) 공감질문형: "여러분은 키친타월 어떻게 고르세요?"
C) 구매 계기 바로 서술: "쿠팡 장보다가 우연히 발견한 제품인데 후기가 너무 좋아서 질렀습니다"

【본문 5파트 구조】
1. 오프닝 + 구매 계기 (200~400자)
2. 구매 결정 과정 (150~300자)
3. 상품별 상세 후기 — 소제목 + 150~250자 + 쿠팡링크 (반복)
4. 장단점 정리 — 단점 반드시 1개 이상 포함
5. 마무리 + 추천대상 명시 (100~200자)

━━━━ 절대 규칙 ━━━━

1. 마크다운 완전 금지: **, ##, ---, >, *, _, ~~~, ` 없음
2. 소제목: 명사형 키워드 15자 이내
   예: "곰곰 반숙란 장점" / "🛒 코멧 키친타월 — 6,990원"
3. 쿠팡 링크: 각 상품마다 2개씩 삽입 (이미지 밀도 확보)
   - 첫 번째: 메인 상품 소개 150~200자 후 → "지금 쿠팡에서 확인하기 → [링크1]"
   - 두 번째: 사용 후기 100~150자 후 → "같이 보면 좋은 제품 → [링크2 or 변형링크]"
   형식: "지금 쿠팡에서 확인하기 → [링크URL]"
4. 단점 1개 이상 필수 (신뢰도 핵심)
5. 가격 구체적으로 (구입가 직접 명시 — "내돈내산! 83,630원에 구매했어요")
6. 파트너스 고지: 첫 줄 고정
7. 해시태그: 없거나 4~6개만 (과도한 해시태그 = 스팸 신호)

━━━━ 실제 예시 (이 포맷 그대로) ━━━━

[예시 제목] 비브르 무선청소기 V17 쿠팡 내돈내산 후기 — 5년 쓴 청소기 교체기

[예시 본문]
📢 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

약 5년 전 자취선물로 받았던 청소기가 수명을 다했어요. 아무리 충전해도 작동이 안 되더라고요.

갑자기 사려니까 돈이 왜 이렇게 아까운지 ㅋㅋㅋ 쿠팡에서 대충 비교해보고 원룸 가성비 청소기 중에 골랐습니다.

내돈내산! 83,630원에 구매했어요.

비브르 무선청소기 V17

받자마자 조립했는데 생각보다 간단했어요. 설명서 없이도 됩니다.

흡입력은 원룸 청소 기준으로 충분해요. 강모드로 카펫 청소해도 잘 됩니다.

지금 쿠팡에서 확인하기 → https://link.coupang.com/a/상품1링크

장단점 솔직하게

솔직히 좋은 점: 가볍고 배터리가 생각보다 오래 감. USB-C 충전이라 편해요.

아쉬운 점: 조금 무거워서 들고 다니면 팔이 좀 피로해요. 남편한테도 써보라 했더니 "무겁다"는 말 한마디 남기고 돌아갔습니다 ㅋㅋ

원룸 자취생이나 1~2인 가구에게는 가성비 괜찮은 선택. 3인 이상은 비추.

지금 같은 가격이면 충분히 만족스러운 제품이에요!

#무선청소기추천 #쿠팡 #내돈내산 #가성비청소기 #솔직후기

━━━━ 예시 끝 ━━━━"""


def build_prompt(topic: str, products: list, labels: list, original_url: str) -> str:
    prod_lines = []
    for i, prod in enumerate(products[:3], 1):
        name  = prod.get("productName", prod.get("name", "상품"))
        price = prod.get("price", "")
        url   = prod.get("shortenUrl", prod.get("coupang_url", ""))
        prod_lines.append(f"상품{i}: {name} / {price}\n링크{i}: {url}")
    prod_summary = "\n".join(prod_lines)
    labels_str   = ", ".join(labels[:5]) if labels else topic

    # 각 상품별 링크 삽입 지시 — 상품당 2번씩 삽입 (이미지 밀도 확보)
    link_rules = ""
    for i, prod in enumerate(products[:3], 1):
        name  = prod.get("productName", prod.get("name", "상품"))
        url   = prod.get("shortenUrl", prod.get("coupang_url", ""))
        price = prod.get("price", "")
        link_rules += f"\n상품{i}({name}):"
        link_rules += f"\n  - 소개 후 1번: 지금 쿠팡에서 확인하기 → {url}"
        link_rules += f"\n  - 후기 후 2번: 지금 쿠팡에서 확인하기 → {url}"

    return f"""아래 상품 정보로 네이버 홈판 최적화 블로그 포스팅을 작성해주세요.

주제: {topic}
카테고리: {labels_str}
원본 글: {original_url}

상품 정보:
{prod_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[절대 규칙 — 위반 시 재작성]

1. 마크다운 완전 금지: **, ##, ---, >, *, _ 사용 불가
2. 소제목 형식 (반드시 이 형태): 이모지 + 상품명 — 가격의 특징
   예: 🛒 코멧 키친타월 — 6,990원의 실력
3. 쿠팡 링크 — 각 상품 섹션 본문 2~3줄 후 반드시 아래 URL 그대로 삽입:{link_rules}
4. 해시태그 8~10개, 마지막 줄에만

[본문 구조 — 정확히 이 순서로]
① 📢 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
(빈 줄)
② 오프닝: 독자 공감 상황 3~4줄 (대화체)
(빈 줄)
③ 결론부터 말하면, ... (1~2줄)
(빈 줄)
④ [상품1 소제목] 🛒 상품명 — 가격의 특징
   상품 소개 + 첫인상 100~150자
   지금 쿠팡에서 확인하기 → [링크1URL 그대로]
   실사용 후기 100~150자 (장점 + 단점 솔직하게)
   지금 쿠팡에서 확인하기 → [링크1URL 그대로 한번 더]
(빈 줄)
⑤ [상품2 소제목] 🛒 상품명 — 가격의 특징
   상품 소개 + 첫인상 100~150자
   지금 쿠팡에서 확인하기 → [링크2URL 그대로]
   실사용 후기 100~150자 (장점 + 단점 솔직하게)
   지금 쿠팡에서 확인하기 → [링크2URL 그대로 한번 더]
(빈 줄)
⑥ (상품3 있으면 동일)
⑦ ✅ 예산별 선택 가이드
   비교 정리 3~5줄, 추천 대상 명시
(빈 줄)
⑧ 마무리 1~2줄
(빈 줄)
⑨ 해시태그 4~6개만 (없어도 됨, 과도한 해시태그 = 스팸 신호)

[분량] 1,800~2,200자
[문체] 대화체, 솔직한 장단점 (단점 1개 이상 필수), 유머 허용
[제목] 28~38자, 이모지 없이, 가격/vs/직접써봄/내돈내산 포함

지금 바로 제목과 본문 전체를 작성해주세요.
링크 URL은 반드시 위에 제공된 주소를 그대로, 각 상품마다 2번씩 사용할 것."""


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
        title = topic[:38]

    # 네이버 제목 한도: 30자 (초과 시 에러 페이지)
    # 단, 실제로는 약 40자까지 허용 — 안전하게 38자로 제한
    if len(title) > 38:
        # 마침표/느낌표/물음표 앞에서 자르기 시도
        cut = title[:38]
        for ch in ['!', '?', '.', ',']:
            idx = title.rfind(ch, 20, 38)
            if idx > 20:
                cut = title[:idx+1]
                break
        title = cut

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
