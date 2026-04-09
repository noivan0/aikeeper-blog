#!/usr/bin/env python3
"""
Threads 스레드형 연속 포스팅 자동화
캐러셀 내용을 Threads 포맷(훅 + 상품별 reply + CTA)으로 발행
"""

import os
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API_BASE  = "https://graph.threads.net/v1.0"
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env()

TOKEN   = os.environ.get("THREADS_ACCESS_TOKEN", "")
USER_ID = os.environ.get("THREADS_USER_ID", "")


def _api(path: str, params: dict = None, post_data: dict = None) -> dict:
    """Threads Graph API 호출"""
    params = params or {}
    params["access_token"] = TOKEN
    url = f"{API_BASE}/{path}?{urllib.parse.urlencode(params)}"
    if post_data:
        data = urllib.parse.urlencode(post_data).encode()
        req = urllib.request.Request(url, data=data, method="POST")
    else:
        req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Threads API {path} 오류 {e.code}: {body}")


def _create_container(text: str, image_url: str = None, reply_to_id: str = None) -> str:
    """미디어 컨테이너 생성 → container_id 반환"""
    payload = {
        "media_type": "IMAGE" if image_url else "TEXT",
        "text": text,
    }
    if image_url:
        payload["image_url"] = image_url
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    resp = _api(f"{USER_ID}/threads", post_data=payload)
    container_id = resp.get("id")
    if not container_id:
        raise RuntimeError(f"컨테이너 생성 실패: {resp}")
    return container_id


def _publish_container(container_id: str) -> str:
    """컨테이너 게시 → post_id 반환"""
    # 컨테이너 상태 대기 (최대 30초)
    for _ in range(6):
        time.sleep(5)
        status = _api(container_id, params={"fields": "status,error_message"})
        if status.get("status") == "FINISHED":
            break
        if status.get("status") == "ERROR":
            raise RuntimeError(f"컨테이너 오류: {status.get('error_message')}")

    resp = _api(f"{USER_ID}/threads_publish", post_data={"creation_id": container_id})
    post_id = resp.get("id")
    if not post_id:
        raise RuntimeError(f"게시 실패: {resp}")
    return post_id


def publish_thread(
    topic: str,
    products: list,
    image_urls: list,
    post_url: str,
    labels: list = None,
) -> dict:
    """
    스레드형 연속 포스팅

    params:
      topic      : 포스트 주제 (예: "크레아틴 추천 TOP3")
      products   : [{"productName": "...", "productPrice": 19500, ...}, ...]
      image_urls : 슬라이드 이미지 URL 리스트 (products 순서와 일치)
      post_url   : 블로그 포스트 URL
      labels     : 포스트 라벨 (해시태그로 활용)
    """
    if not TOKEN or not USER_ID:
        raise RuntimeError("THREADS_ACCESS_TOKEN / THREADS_USER_ID 환경변수 없음")

    labels = labels or []
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in labels[:3]) if labels else "#꿀통몬 #쿠팡추천 #가성비"

    results = []

    # ── Thread 1: 훅 (텍스트만)
    hook_text = (
        f"💡 {topic}\n\n"
        f"뭐가 진짜 가성비일까? 직접 비교해봤습니다 👇\n\n"
        f"{hashtags}"
    )
    print(f"[threads] 훅 포스트 작성 중...")
    hook_container = _create_container(hook_text)
    hook_id = _publish_container(hook_container)
    print(f"[threads] 훅 게시 완료: {hook_id}")
    results.append({"type": "hook", "post_id": hook_id})
    time.sleep(3)

    # ── Reply 1~N: 상품별 이미지 + 텍스트
    reply_to = hook_id
    for i, prod in enumerate(products):
        name  = prod.get("productName", prod.get("name", f"상품 {i+1}"))
        price = prod.get("productPrice", prod.get("price", 0))
        price_str = f"{int(price):,}원" if price else ""
        emoji = EMOJI_NUMS[i] if i < len(EMOJI_NUMS) else f"{i+1}."
        img_url = image_urls[i] if i < len(image_urls) else None

        prod_text = f"{emoji} {name}"
        if price_str:
            prod_text += f"\n✔ {price_str}"
        prod_text += f"\n→ {post_url}"

        print(f"[threads] 상품 {i+1} reply 작성 중: {name[:30]}...")
        prod_container = _create_container(prod_text, image_url=img_url, reply_to_id=reply_to)
        prod_id = _publish_container(prod_container)
        print(f"[threads] 상품 {i+1} 게시 완료: {prod_id}")
        results.append({"type": f"product_{i+1}", "post_id": prod_id})
        reply_to = prod_id
        time.sleep(3)

    # ── 마지막 Reply: CTA
    cta_text = (
        f"📌 전체 비교 + 구매 가이드\n"
        f"→ {post_url}\n\n"
        f"프로필 링크에서 쿠팡 상품 바로 확인 가능합니다 🛒"
    )
    print(f"[threads] CTA reply 작성 중...")
    cta_container = _create_container(cta_text, reply_to_id=reply_to)
    cta_id = _publish_container(cta_container)
    print(f"[threads] CTA 게시 완료: {cta_id}")
    results.append({"type": "cta", "post_id": cta_id})

    permalink = f"https://www.threads.net/@ggultongmon/post/{hook_id}"
    print(f"\n✅ Threads 스레드 게시 완료!")
    print(f"   메인 포스트: {permalink}")
    print(f"   총 {len(results)}개 (훅 1 + 상품 {len(products)} + CTA 1)")

    return {
        "success":   True,
        "hook_id":   hook_id,
        "permalink": permalink,
        "posts":     results,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",    default="테스트 상품 TOP3 비교")
    parser.add_argument("--post-url", default="https://ggultongmon.allsweep.xyz/")
    args = parser.parse_args()

    # 테스트용 더미 데이터
    test_products = [
        {"productName": "테스트 상품 A", "productPrice": 19500},
        {"productName": "테스트 상품 B", "productPrice": 25000},
        {"productName": "테스트 상품 C", "productPrice": 32000},
    ]
    test_images = []  # 텍스트 전용 테스트

    result = publish_thread(
        topic=args.topic,
        products=test_products,
        image_urls=test_images,
        post_url=args.post_url,
        labels=["가성비", "쿠팡추천", "꿀통몬"],
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
