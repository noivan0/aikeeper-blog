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

아래는 실제 네이버 홈판 상위 노출 포스팅 20개를 분석한 결과입니다. 이 패턴을 정확히 따라 작성하세요.

━━━━ 실제 분석 기반 글쓰기 원칙 ━━━━

[절대 금지]
- 마크다운 기호: **, ##, ---, >, *, _, ~~~, ` 완전 금지
- 본문 앞쪽에 구매링크 삽입 금지 (스토리 흐름 중간에 자연스럽게)
- 광고티 나는 표현 금지 ("지금 구매하세요!" 등)

[제목 규칙 — 실제 상위 노출 패턴]
- 25~38자, 숫자(가격) + 경험담형
- "내돈내산", "솔직후기", "직접써봤어요" 중 하나 포함
- 상품명 풀네임 포함
- 예: "3단우산 기본형 vs 초대형 직접 써본 솔직 후기"

[소제목 규칙 — 핵심]
- 이모지 + 명사형 종결 (10~25자)
- 예: "🛒 3단우산 기본형 — 8,380원의 실력"
- 예: "⚠️ 아쉬운 점도 솔직하게"
- 예: "✅ 예산별 선택 가이드"
- 소제목 아래는 반드시 빈 줄 없이 바로 본문 시작

[이미지 배치 규칙 — 중요]
- 소제목 아래 텍스트 2~3줄 후 반드시 쿠팡 링크(이미지 삽입 위치) 삽입
- 1000자당 이미지 4~15개가 상위 노출 기준
- 링크 형식: "지금 쿠팡에서 확인하기 → [실제URL]"
- 이 링크는 시스템이 자동으로 상품 이미지+OG카드로 변환함

[본문 구조 — 실제 상위 노출 순서]
1. 파트너스 고지 (첫 줄 고정)
2. 독자 공감 오프닝 — 구매 고민 상황 (3~4줄)
3. 구매 배경 스토리 — 왜 이 상품을 찾게 됐는지 (2~3줄)
4. 결론 먼저 — "결론부터 말하면..." (1~2줄)
5. 상품1 소제목 + 본문 + 쿠팡 링크
6. 상품2 소제목 + 본문 + 쿠팡 링크
7. (상품3 있으면 동일)
8. 선택 가이드 소제목 + 비교 정리 (3~5줄)
9. 마무리 + 공감/댓글 유도 (1~2줄)
10. 해시태그 (6~12개, 마지막 줄)

[문체]
- 대화체: ~요, ~네요, ~더라고요, ~습니다
- 솔직한 장단점 모두 기재 (신뢰도 ↑)
- 구체적 수치 포함: 가격, 크기, 사용 기간
- 유머/자조적 표현 허용: "뭐야 이게 ㅋㅋ", "솔직히..."

━━━━ 실제 포스팅 예시 ━━━━

[예시 제목] 6,990원 vs 12,770원 키친타월, 흡수력 차이 직접 확인했습니다

[예시 본문]
📢 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

매달 장바구니에 습관처럼 담는 키친타월, 가격 차이를 그냥 무시하고 계셨나요?

6,990원짜리와 12,770원짜리 사이에 약 6,000원 차이가 있는데, 1년이면 72,000원 가까이 됩니다.

막상 두 제품을 나란히 놓고 쓰다 보면 "내가 비싼 걸 사는 이유가 뭔가?" 하는 의문이 드는 게 사실입니다.

결론부터 말하면, 가성비를 원한다면 6,990원짜리로 충분하고, 한 장으로 해결하고 싶다면 12,770원짜리가 맞습니다.

🛒 코멧 깨끗한 천연펄프 키친타월 — 6,990원의 실력

배송받아서 처음 꺼냈을 때 인상은 두께감이 생각보다 괜찮다였습니다.

흡수 속도가 꽤 빠른 편이라 소형견이 한 번에 소변을 보는 양 정도는 충분히 감당합니다.

다만 세 번 이상 사용하면 모서리 쪽에서 약간 번짐이 생기더라고요. 솔직히 이 점은 아쉬웠어요.

지금 쿠팡에서 확인하기 → https://link.coupang.com/a/상품1링크

🛒 모나리자 스마트 다용도 키친타올 250매 — 12,770원의 두께감

가격이 두 배 가까이 되는 만큼 무엇이 다른지 직접 비교해봤습니다.

두께가 확실히 다릅니다. 같은 힘으로 물기를 닦았을 때 한 장으로도 충분한 경우가 많았어요.

지금 쿠팡에서 확인하기 → https://link.coupang.com/a/상품2링크

✅ 예산별 선택 가이드

매달 자주 교체하고 비용이 부담되신다면 6,990원짜리가 딱 맞아요.

주방에서 기름기나 국물을 한 장에 해결하고 싶다면 12,770원짜리를 선택하세요.

이 글이 도움됐다면 공감 한 번 눌러주세요! 댓글로 어떤 키친타월 쓰시는지 알려주시면 저도 반응할게요.

#키친타월추천 #쿠팡 #내돈내산 #주방용품 #가성비 #로켓배송 #키친타월비교 #솔직후기 #쿠팡추천 #생활용품

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

    # 각 상품별 소제목+링크 삽입 위치 명시 (Claude가 빠뜨리지 못하도록)
    link_rules = ""
    for i, prod in enumerate(products[:3], 1):
        name  = prod.get("productName", prod.get("name", "상품"))
        url   = prod.get("shortenUrl", prod.get("coupang_url", ""))
        price = prod.get("price", "")
        link_rules += f"\n상품{i} 섹션 끝에 반드시: 지금 쿠팡에서 확인하기 → {url}"

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
   상품1 솔직 후기 2~3줄
   지금 쿠팡에서 확인하기 → [링크1URL 그대로]
(빈 줄)
⑤ [상품2 소제목] 🛒 상품명 — 가격의 특징
   상품2 솔직 후기 2~3줄
   지금 쿠팡에서 확인하기 → [링크2URL 그대로]
(빈 줄)
⑥ (상품3 있으면 동일)
⑦ ✅ 예산별 선택 가이드
   비교 정리 3~5줄
(빈 줄)
⑧ 마무리 + 공감/댓글 유도 1~2줄
(빈 줄)
⑨ #해시태그 #형식으로 #8개~10개

[분량] 1,800~2,500자
[문체] 대화체, 솔직한 장단점 포함 (단점도 1개 이상)
[제목] 25~38자, 이모지 없이, 가격/vs/직접써봄 포함

지금 바로 제목과 본문 전체를 작성해주세요.
링크 URL은 반드시 위에 제공된 주소를 그대로 사용할 것."""


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
