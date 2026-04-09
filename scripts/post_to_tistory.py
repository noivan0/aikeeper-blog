#!/usr/bin/env python3
"""
ggultongmon → 티스토리 크로스포스팅
원문 기반으로 다른 앵글의 완결형 포스트 생성 후 banidad.tistory.com 발행
"""
import os, sys, json, re, requests
from pathlib import Path
from anthropic import Anthropic

BASE_DIR = Path(__file__).parent.parent

# .env 로드
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

TSSESSION    = os.environ.get("TISTORY_SESSION", "")
BLOG_NAME    = "banidad"
API_BASE     = f"https://{BLOG_NAME}.tistory.com/manage"
GGULTONGMON  = "https://ggultongmon.allsweep.xyz"

requests.packages.urllib3.disable_warnings()


def _sess():
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "Cookie":           f"TSSESSION={TSSESSION}",
        "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Origin":           f"https://{BLOG_NAME}.tistory.com",
        "Referer":          f"{API_BASE}/newpost/",
        "Content-Type":     "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def generate_cross_post(topic: str, products: list, post_url: str, labels: list) -> dict:
    """Claude로 다른 앵글의 완결형 크로스포스팅 생성"""
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

    prod_list = "\n".join(
        f"- {p.get('productName','')}: {int(p.get('productPrice',0)):,}원"
        for p in products
    )

    prompt = f"""아래 쿠팡 추천 포스트를 기반으로 티스토리 크로스포스팅용 글을 작성해주세요.

원문 주제: {topic}
원문 URL: {post_url}
상품 목록:
{prod_list}

작성 조건:
1. 원문과 다른 각도의 제목 (질문형 또는 문제해결형)
2. 완결된 콘텐츠 1,500~2,000자 (독립적으로 읽을 수 있어야 함)
3. 구매 포인트 3~5가지 본문에 포함
4. 마지막에 "→ 전체 비교 + 최저가 구매링크: {post_url}" CTA
5. HTML 형식으로 작성 (<h2>, <p>, <strong>, <a> 태그 사용)
6. 태그: 쉼표 구분 5~8개

아래 JSON 형식으로만 응답:
{{
  "title": "제목",
  "content": "HTML 본문",
  "tag": "태그1,태그2,태그3"
}}"""

    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    # JSON 추출
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"JSON 파싱 실패: {text[:200]}")


def publish_to_tistory(title: str, content: str, tag: str = "", category: str = "0") -> dict:
    """티스토리 API로 글 발행"""
    if not TSSESSION:
        raise RuntimeError("TISTORY_SESSION 환경변수 없음")

    s = _sess()
    payload = {
        "title":          title,
        "content":        content,
        "visibility":     "20",   # 공개
        "category":       category,
        "tag":            tag,
        "acceptComment":  "1",
        "acceptTrackback":"0",
        "published":      "1",
    }
    r = s.post(f"{API_BASE}/post.json", json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"발행 실패 {r.status_code}: {r.text[:200]}")

    result = r.json()
    entry_url = result.get("entryUrl", "")
    print(f"  ✅ 티스토리 발행 완료: {entry_url}")
    return {"success": True, "url": entry_url}


def cross_post(topic: str, products: list, post_url: str, labels: list = None) -> dict:
    """전체 크로스포스팅 플로우"""
    labels = labels or []
    print(f"[tistory] 크로스포스팅 시작: {topic[:40]}...")

    # Claude로 크로스포스트 생성
    print("[tistory] Claude 크로스포스트 생성 중...")
    data = generate_cross_post(topic, products, post_url, labels)
    print(f"[tistory] 제목: {data['title']}")

    # 발행
    result = publish_to_tistory(
        title=data["title"],
        content=data["content"],
        tag=data.get("tag", ",".join(labels)),
    )
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",    required=True)
    parser.add_argument("--post-url", required=True)
    parser.add_argument("--products", default="[]")
    args = parser.parse_args()

    products = json.loads(args.products)
    result = cross_post(args.topic, products, args.post_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
