#!/usr/bin/env python3
"""
Unsplash API로 이미지를 검색해 마크다운에 자동 삽입
SEO: alt 태그, 캡션 자동 설정
"""
import os
import sys
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")


def search_image(query: str, count: int = 3) -> list:
    """Unsplash에서 이미지 검색"""
    if not UNSPLASH_ACCESS_KEY:
        print("⚠️  UNSPLASH_ACCESS_KEY 없음 — 이미지 스킵")
        return []

    url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page={count}&orientation=landscape"
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"})

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    images = []
    for photo in data.get("results", []):
        images.append({
            "url": photo["urls"]["regular"],
            "alt": photo.get("alt_description") or query,
            "author": photo["user"]["name"],
            "author_link": photo["user"]["links"]["html"]
        })
    return images


def parse_front_matter(content: str):
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except ImportError:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()
    return meta, body


def inject_images(file_path: str) -> str:
    """마크다운 파일에 이미지 자동 삽입"""
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    image_query = meta.get("image_query", meta.get("title", "technology AI"))
    images = search_image(image_query, count=3)

    if not images:
        return file_path

    # 대표 이미지 (글 상단)
    hero = images[0]
    hero_md = f'\n![{hero["alt"]}]({hero["url"]})\n*📷 Photo by [{hero["author"]}]({hero["author_link"]}) on Unsplash*\n\n'

    # 본문 중간 이미지 삽입 (## 소제목 2번째 이후)
    h2_positions = [m.start() for m in re.finditer(r'^## ', body, re.MULTILINE)]

    if len(images) > 1 and len(h2_positions) >= 2:
        insert_pos = h2_positions[1]
        img = images[1]
        img_md = f'\n![{img["alt"]}]({img["url"]})\n*📷 Photo by [{img["author"]}]({img["author_link"]}) on Unsplash*\n\n'
        body = body[:insert_pos] + img_md + body[insert_pos:]

    # 최종 조합
    new_content = content.split("---", 2)[0] + "---" + content.split("---", 2)[1] + "---\n\n" + hero_md + body

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ 이미지 삽입 완료: {len(images)}장")
    return file_path


if __name__ == "__main__":
    file_path = sys.argv[1]
    inject_images(file_path)
