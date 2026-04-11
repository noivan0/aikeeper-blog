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

아래는 실제 홈판에 노출된 쿠팡 제품 리뷰 포스팅의 예시입니다. 이 포맷을 정확히 따라 작성하세요.

━━━━ 실제 포스팅 예시 ━━━━

[예시 제목] 6,990원 vs 12,770원 키친타월, 흡수력 차이 직접 확인했습니다

[예시 본문]
📢 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

매달 장바구니에 습관처럼 담는 키친타월, 가격 차이를 그냥 무시하고 계셨나요?

6,990원짜리와 12,770원짜리 사이에 약 6,000원 차이가 있는데, 1년이면 72,000원 가까이 됩니다.

막상 두 제품을 나란히 놓고 쓰다 보면 "내가 비싼 걸 사는 이유가 뭔가?" 하는 의문이 드는 게 사실입니다.

실제로 배송받아서 직접 써보고 나서야 이래서 가격이 다르구나를 이해하게 됐습니다.

오늘은 코멧 두 종류와 모나리자 한 종류, 총 세 가지 키친타월을 흡수력·내구성·경제성 측면에서 낱낱이 비교해 드립니다.

키친타월 고를 때 꼭 확인해야 할 4가지

1. 원단 소재 — 천연펄프 vs 재생펄프

천연펄프는 원목을 직접 가공한 섬유를 사용해 흡수력과 내구성이 상대적으로 높습니다.

재생펄프는 가격은 저렴하지만 물에 닿으면 쉽게 뭉개지는 경우가 있습니다.

요리 중 기름기나 물기를 빠르게 닦아야 한다면 천연펄프 소재를 우선시하는 것이 낫습니다.

코멧 깨끗한 천연펄프 키친타월 — 6,990원의 실력

배송받아서 처음 꺼냈을 때 인상은 두께감이 생각보다 괜찮다였습니다.

흡수 속도가 꽤 빠른 편이라 소형견이 한 번에 소변을 보는 양 정도는 충분히 감당합니다.

다만 패드를 재사용해서 두 번, 세 번 소변을 봤을 때 세 번째부터는 모서리 쪽에서 약간 번짐이 발생했습니다.

지금 쿠팡에서 확인하기 → https://link.coupang.com/a/상품1링크

모나리자 스마트 다용도 키친타올 250매 — 12,770원의 프리미엄

가격이 두 배 가까이 되는 만큼 무엇이 다른지 직접 비교해봤습니다.

두께가 확실히 다릅니다. 같은 힘으로 물기를 닦았을 때 한 장으로도 충분한 경우가 많았어요.

지금 쿠팡에서 확인하기 → https://link.coupang.com/a/상품2링크

세 제품 한눈에 비교

6,990원짜리: 가성비, 빠른 흡수, 무향, 타일 바닥에서 약간 밀림
12,770원짜리: 두께감, 한 장으로 충분, 소취 기능, 가격 부담

어떤 분께 추천할까요?

매달 자주 교체하고 비용 부담이 되신다면 6,990원짜리가 맞습니다.

주방에서 기름기나 국물 흘림을 한 장에 해결하고 싶다면 12,770원짜리를 선택하세요.

이 글이 도움됐다면 공감 한 번 눌러주세요. 댓글로 어떤 키친타월 쓰시는지 알려주시면 저도 반응할게요!

#키친타월추천 #쿠팡 #내돈내산 #주방용품 #가성비 #로켓배송 #키친타월비교 #솔직후기 #쿠팡추천 #생활용품

━━━━ 예시 끝 ━━━━

위 예시의 포맷을 반드시 따를 것:
- 마크다운 절대 금지: **, ##, ---, >, * 기호 사용 금지
- 이모지 가능 (📢, 🛒 등)
- 단락 구분: 빈 줄 하나로
- 쿠팡 링크: "지금 쿠팡에서 확인하기 → [링크URL]" 형태로 텍스트에 그대로 삽입
- 파트너스 고지: 본문 맨 앞에 반드시 포함
- 해시태그: 마지막 줄, 공백으로 구분"""


def build_prompt(topic: str, products: list, labels: list, original_url: str) -> str:
    prod_summary = ""
    for i, p in enumerate(products[:3]):
        name = p.get("productName", p.get("name", "상품"))
        price = p.get("price", "")
        url = p.get("shortenUrl", p.get("coupang_url", ""))
        prod_summary += f"\n상품{i+1}: {name} / {price}\n링크{i+1}: {url}\n"

    labels_str = ", ".join(labels[:5]) if labels else topic

    return f"""아래 상품 정보로 네이버 홈판 포스팅을 작성해주세요.

주제: {topic}
카테고리: {labels_str}
원본 글: {original_url}

상품 정보:
{prod_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
필수 형식 규칙:

1. 첫 줄: "📢 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
2. 빈 줄 하나 후 본문 시작
3. 마크다운 완전 금지 (**, ##, ---, >, *, _ 사용 금지)
4. 각 상품 설명 후 구매 링크 삽입: "지금 쿠팡에서 확인하기 → [링크URL]"
5. 단락 간 빈 줄 하나씩
6. 마지막 줄: 해시태그 (공백으로 구분, 12-15개)

본문 구조 (이 순서로):
- 오프닝: 독자 공감 상황 (2-3줄)
- 구매 계기 스토리 (2-3줄)  
- 결론 먼저 요약 (1-2줄)
- 상품1 리뷰 + "지금 쿠팡에서 확인하기 → 링크1"
- 상품2 리뷰 + "지금 쿠팡에서 확인하기 → 링크2"
- 상품3 리뷰 + "지금 쿠팡에서 확인하기 → 링크3" (있는 경우)
- 예산별 선택 가이드 (3-5줄)
- 마무리 + 공감/댓글 유도
- 해시태그

분량: 1,800~2,500자
문체: 대화체 (~요, ~네요, ~더라고요)
제목: 25-40자, 숫자/경험담형

지금 바로 제목과 본문 전체를 작성해주세요."""


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
