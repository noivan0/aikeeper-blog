#!/usr/bin/env python3
"""
litt.ly 상품 자동 등록 스크립트 (v1)
- POST /v0/media -> presigned S3 URL 발급
- S3에 이미지 업로드
- PATCH /v0/page/{id} 로 productLink 블록에 상품 추가

사용법:
  python3 upload_littly.py --products-json '<json>' --images prod1.jpg prod2.jpg prod3.jpg

환경변수:
  LITTLY_EMAIL, LITTLY_PASSWORD
"""

import os, sys, json, ssl, random, string, argparse
from pathlib import Path

import requests
requests.packages.urllib3.disable_warnings()

LITTLY_BASE  = "https://api.litt.ly/v0"
LITTLY_EMAIL = os.environ.get("LITTLY_EMAIL", "")
LITTLY_PW    = os.environ.get("LITTLY_PASSWORD", "")
PAGE_ID      = int(os.environ.get("LITTLY_PAGE_ID", "0"))


def rand_key(n=7):
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


class LittlyClient:
    def __init__(self):
        self.sess = requests.Session()
        self.sess.verify = False
        self.sess.headers.update({
            "Origin": "https://app.litt.ly",
            "Referer": "https://app.litt.ly/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        self.token = None

    def login(self):
        r = self.sess.post(
            f"{LITTLY_BASE}/token/email",
            json={"email": LITTLY_EMAIL, "password": LITTLY_PW},
        ).json()
        self.token = r["token"]
        self.sess.headers["Authorization"] = f"Bearer {self.token}"
        print(f"[littly] 로그인 OK (token: {self.token[:8]}...)")

    def get_page(self):
        return self.sess.get(f"{LITTLY_BASE}/page/{PAGE_ID}").json()

    def patch_page(self, data):
        return self.sess.patch(f"{LITTLY_BASE}/page/{PAGE_ID}", json={"data": data}).json()

    def upload_image_from_url(self, public_url: str) -> dict:
        """외부 공개 URL을 image 필드에 직접 사용 (S3 우회, HMG 방화벽 환경)"""
        print(f"[littly] 외부URL 이미지 등록: {public_url[-50:]}")
        return {"mediaId": None, "url": public_url}

    def upload_image(self, img_path: Path) -> dict:
        """이미지를 S3에 업로드하고 {mediaId, url} 반환
        HMG 방화벽 환경에서는 S3 직접 업로드가 차단되므로
        img_path와 함께 public_url을 제공하면 S3 우회.
        """
        # 1단계: presigned URL 발급
        media = self.sess.post(
            f"{LITTLY_BASE}/media",
            json={"pageId": PAGE_ID, "type": "image"},
        ).json()
        media_id  = media["id"]
        media_url = media["url"]
        presigned = media["presignedPost"]

        print(f"[littly] presigned 발급: mediaId={media_id}")

        # 2단계: S3 업로드
        img_data  = img_path.read_bytes()
        mime_type = "image/jpeg"

        fields = {k: (None, v) for k, v in presigned["fields"].items()}
        fields["Content-Type"] = (None, mime_type)
        fields["file"] = (img_path.name, img_data, mime_type)

        r = requests.post(
            presigned["url"],
            files=fields,
            verify=False,
            timeout=30,
        )
        if r.status_code not in (200, 204):
            raise RuntimeError(f"S3 업로드 실패: HTTP {r.status_code} — {r.text[:200]}")

        print(f"[littly] S3 업로드 OK: {media_url}")
        return {"mediaId": media_id, "url": media_url}

    def register_products(self, products: list, image_paths: list, public_urls: list = None):
        """
        products: [{"title": str, "url": str, "tags": [str]}, ...]
        image_paths: [Path or None, ...] — products와 순서 동일
        public_urls: [str or None, ...] — GitHub Pages 등 공개 이미지 URL (S3 우회용)
                     제공 시 S3 업로드 생략하고 URL 직접 사용
        """
        page   = self.get_page()
        blocks = page["data"]["blocks"]
        pl_idx = next(i for i, b in enumerate(blocks) if b["type"] == "productLink")
        pl_block = blocks[pl_idx]

        new_links = []
        for i, (prod, img_path) in enumerate(zip(products, image_paths)):
            print(f"\n[littly] 상품 {i+1}/{len(products)}: {prod['title']}")
            image_field = None
            try:
                # 1순위: 공개 URL 직접 사용 (HMG S3 차단 우회)
                pub_url = (public_urls[i] if public_urls and i < len(public_urls) else None)
                if pub_url:
                    img_info = self.upload_image_from_url(pub_url)
                    image_field = {"url": img_info["url"], "mediaId": img_info["mediaId"]}
                elif img_path:
                    img_info = self.upload_image(Path(img_path))
                    image_field = {"url": img_info["url"], "mediaId": img_info["mediaId"]}
            except Exception as e:
                print(f"  ⚠️  이미지 등록 실패 (스킵): {e}")
                image_field = None

            new_links.append({
                "key":      rand_key(),
                "url":      prod["url"],
                "use":      True,          # ON 상태 (기본값이 OFF인 경우 방지)
                "tags":     prod.get("tags", []),
                "image":    image_field,
                "title":    prod["title"],
                "currency": "KRW",
            })

        # 맨 앞에 추가 (최신 포스트 상단)
        pl_block["links"] = new_links + pl_block.get("links", [])
        blocks[pl_idx] = pl_block
        page["data"]["blocks"] = blocks

        result = self.patch_page(page["data"])
        if result.get("_err"):
            raise RuntimeError(f"PATCH 실패: {result}")

        print(f"\n[littly] ✅ {len(new_links)}개 등록 완료")
        for lk in new_links:
            status = "🖼️" if lk["image"] else "📝(이미지없음)"
            print(f"  {status} {lk['title']}")

        return new_links


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--products-json", required=True, help="상품 JSON 배열")
    parser.add_argument("--images", nargs="+", required=True, help="상품 이미지 경로 (순서 일치)")
    args = parser.parse_args()

    products = json.loads(args.products_json)
    images   = args.images

    if len(products) != len(images):
        print(f"❌ 상품 수({len(products)})와 이미지 수({len(images)}) 불일치")
        sys.exit(1)

    client = LittlyClient()
    client.login()
    client.register_products(products, images)


if __name__ == "__main__":
    main()
