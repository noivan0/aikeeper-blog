"""
꿀통몬스터 블로그 주제 발굴
- 쿠팡 인기 카테고리 기반 키워드 생성
- 검색 의도 최적화: "가성비", "추천", "비교", "후기", "특가" 키워드 조합
- Claude로 블로그 포스트 주제 + 상품 키워드 선정
"""
import os
import json
import random
import urllib.request
import anthropic
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# 쿠팡 인기 카테고리 & 키워드 풀
CATEGORY_KEYWORDS = {
    "식품/건강": [
        "단백질 보충제", "유산균 추천", "다이어트 보조제", "비타민 추천",
        "오메가3 추천", "콜라겐 추천", "프로틴 파우더", "홍삼 추천",
        "녹용 추천", "글루타치온 추천",
    ],
    "주방/생활": [
        "에어프라이어 추천", "전기레인지 추천", "냄비 세트 추천",
        "블렌더 추천", "전기포트 추천", "식기세척기 추천",
        "밥솥 추천", "커피머신 추천", "착즙기 추천", "제빙기 추천",
    ],
    "가전/디지털": [
        "로봇청소기 추천", "공기청정기 추천", "제습기 추천",
        "가습기 추천", "선풍기 추천", "스탠드 선풍기",
        "블루투스 이어폰 추천", "무선 청소기 추천", "안마기 추천",
    ],
    "뷰티/스킨케어": [
        "선크림 추천", "토너 추천", "세럼 추천", "마스크팩 추천",
        "립밤 추천", "클렌징폼 추천", "보습크림 추천",
        "탈모샴푸 추천", "자외선차단제 추천",
    ],
    "육아/유아동": [
        "유아 장난감 추천", "아기 물티슈 추천", "분유 추천",
        "유아 매트 추천", "아기 카시트 추천", "젖병 추천",
        "유아 책 추천", "아기 로션 추천",
    ],
    "스포츠/레저": [
        "요가매트 추천", "운동화 추천", "헬스 장갑 추천",
        "폼롤러 추천", "덤벨 추천", "줄넘기 추천",
        "캠핑 텐트 추천", "등산화 추천",
    ],
    "반려동물": [
        "강아지 사료 추천", "고양이 사료 추천", "강아지 간식 추천",
        "고양이 화장실 추천", "강아지 장난감 추천", "반려동물 하네스",
    ],
    "시즌특가": [
        "봄 특가 추천템", "가성비 생필품", "쿠팡 로켓배송 추천",
        "쿠팡 골드박스", "주말 특가", "인기 급상승 상품",
    ],
}

SEARCH_INTENT_SUFFIXES = [
    " 가성비 추천", " TOP5 추천", " 비교 후기",
    " 구매 가이드", " 솔직 리뷰", " 인기 순위",
    " 저렴하게 사는 법", " 할인 특가",
]


def pick_keyword() -> tuple[str, str, str]:
    """카테고리 + 키워드 + 검색의도 랜덤 선택"""
    category = random.choice(list(CATEGORY_KEYWORDS.keys()))
    base_kw = random.choice(CATEGORY_KEYWORDS[category])
    intent = random.choice(SEARCH_INTENT_SUFFIXES)
    
    # 검색 키워드 (API용): base_kw만
    search_kw = base_kw
    # 포스트 주제 (Claude용): base_kw + intent
    topic = base_kw + intent
    
    return category, search_kw, topic


def generate_topic_with_claude(category: str, keyword: str, products: list) -> dict:
    """Claude로 포스트 주제 + 앵글 + 라벨 생성"""
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y년 %m월 %d일")
    
    product_summary = "\n".join([
        f"- {p['productName'][:40]} / {p['productPrice']:,}원 / 로켓:{p['isRocket']}"
        for p in products[:5]
    ])
    
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url=ANTHROPIC_BASE_URL,
    )
    
    prompt = f"""오늘은 {today}. 쿠팡 파트너스 블로그 '꿀통 몬스터'를 위한 포스트 주제를 선정해주세요.

카테고리: {category}
기본 키워드: {keyword}
검색된 쿠팡 상품:
{product_summary}

아래 형식으로 정확히 응답하세요:

===TOPIC===
포스트 제목 (50자 이내, 이모지 금지, 검색의도 최적화, 숫자/비교/순위 활용)
===SEARCH_KEYWORD===
쿠팡 API 검색에 사용할 핵심 키워드 (1~3단어, 한국어)
===ANGLE===
포스트 작성 각도 (50자, 독자 관점에서 구체적으로)
===LABELS===
SEO 검색 키워드 라벨 (6~9개, 쉼표 구분, 실제 검색어 기반, 카테고리어 금지)
예: 에어프라이어 추천, 에어프라이어 가성비, 에어프라이어 순위, 쿠팡 에어프라이어
===META===
구글/네이버 검색결과 설명 (150~160자, 핵심 키워드 포함)"""
    
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text
    
    def extract(tag):
        start = text.find(f"==={tag}===")
        if start == -1:
            return ""
        start += len(f"==={tag}===")
        end = text.find("===", start)
        return text[start:end if end != -1 else None].strip()
    
    return {
        "topic": extract("TOPIC"),
        "search_keyword": extract("SEARCH_KEYWORD") or keyword,
        "angle": extract("ANGLE"),
        "labels": [l.strip() for l in extract("LABELS").split(",") if l.strip()],
        "meta_desc": extract("META"),
        "category": category,
        "base_keyword": keyword,
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from coupang_api import search_products
    
    category, search_kw, topic_hint = pick_keyword()
    print(f"카테고리: {category}")
    print(f"검색 키워드: {search_kw}")
    print(f"주제 힌트: {topic_hint}")
    
    products = search_products(search_kw, limit=5)
    print(f"검색된 상품: {len(products)}개")
    
    topic_data = generate_topic_with_claude(category, search_kw, products)
    print(f"\n선정 주제: {topic_data['topic']}")
    print(f"라벨: {topic_data['labels']}")
    
    # CI용 output
    output_file = os.environ.get("GITHUB_OUTPUT", "/tmp/ggultongmon_topic.txt")
    with open(output_file, "a") as f:
        f.write(f"topic={topic_data['topic']}\n")
        f.write(f"search_keyword={topic_data['search_keyword']}\n")
        f.write(f"angle={topic_data['angle']}\n")
        f.write(f"category={topic_data['category']}\n")
        f.write(f"labels={','.join(topic_data['labels'])}\n")
        f.write(f"meta_desc={topic_data['meta_desc']}\n")
    print(f"\n주제 저장 완료 → {output_file}")
