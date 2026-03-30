#!/usr/bin/env python3
"""
이미지 자동 수집 및 삽입
우선순위:
  1. Wikimedia Commons — 무료 라이선스 (CC)
  2. Unsplash API — UNSPLASH_ACCESS_KEY 있을 때
  3. scrapling으로 관련 뉴스 페이지에서 og:image 추출
  4. 이모지 배너로 대체 (이미지 없을 때)
"""
import os
import sys
import re
import json
import subprocess
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path


UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()


# ── 파싱 헬퍼 ────────────────────────────────────────────────────

def parse_front_matter(content: str):
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"')
            body = parts[2].strip()
    return meta, body


# ── 1순위: Wikimedia Commons ─────────────────────────────────────

def search_wikimedia(query: str) -> list:
    """Wikimedia Commons에서 무료 이미지 검색 (API, 키 불필요)"""
    try:
        encoded = urllib.parse.quote(query)
        url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&generator=search&gsrnamespace=6"
            f"&gsrsearch={encoded}&gsrlimit=5&prop=imageinfo"
            f"&iiprop=url|extmetadata&iiurlwidth=800&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "AIkeeper-Blog/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        images = []
        for page in (data.get("query", {}).get("pages", {}).values()):
            ii = page.get("imageinfo", [{}])[0]
            img_url = ii.get("thumburl") or ii.get("url", "")
            if not img_url or not img_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            meta_ext = ii.get("extmetadata", {})
            author = meta_ext.get("Artist", {}).get("value", "Wikimedia Commons")
            author = re.sub(r"<[^>]+>", "", author).strip()[:40]
            license_name = meta_ext.get("LicenseShortName", {}).get("value", "CC")
            images.append({
                "url": img_url,
                "alt": query,
                "credit": f"{author} / Wikimedia Commons ({license_name})",
                "source": "wikimedia"
            })
            if len(images) >= 3:
                break
        return images
    except Exception as e:
        print(f"  ⚠️  Wikimedia 오류: {e}")
        return []


# ── 2순위: Unsplash API ───────────────────────────────────────────

def search_unsplash(query: str) -> list:
    if not UNSPLASH_ACCESS_KEY:
        return []
    try:
        url = (
            f"https://api.unsplash.com/search/photos"
            f"?query={urllib.parse.quote(query)}&per_page=3&orientation=landscape"
        )
        req = urllib.request.Request(
            url, headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        images = []
        for photo in data.get("results", []):
            images.append({
                "url": photo["urls"]["regular"],
                "alt": photo.get("alt_description") or query,
                "credit": f"{photo['user']['name']} / Unsplash",
                "credit_url": photo["user"]["links"]["html"],
                "source": "unsplash"
            })
        return images
    except Exception as e:
        print(f"  ⚠️  Unsplash 오류: {e}")
        return []


# ── 3순위: scrapling으로 뉴스 og:image 수집 ──────────────────────

def scrapling_fetch(url: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ["scrapling", "extract", "get", url, tmp,
             "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=20
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def search_news_image(query: str) -> list:
    """Google News 검색 결과 페이지에서 og:image 추출"""
    try:
        encoded = urllib.parse.quote(query + " site:techcrunch.com OR site:venturebeat.com")
        url = f"https://news.google.com/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        content = scrapling_fetch(url)
        if not content:
            return []

        # og:image 또는 이미지 URL 추출
        imgs = re.findall(r'https://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>]*', content)
        imgs = [i for i in imgs if "logo" not in i.lower() and len(i) > 40]
        results = []
        for img in imgs[:3]:
            results.append({
                "url": img,
                "alt": query,
                "credit": "출처: 관련 뉴스",
                "source": "news"
            })
        return results
    except Exception:
        return []


# ── 이모지 배너 폴백 ─────────────────────────────────────────────

TOPIC_EMOJI_MAP = {
    "ai": "🤖", "claude": "🤖", "gpt": "🤖", "llm": "🧠",
    "robot": "🤖", "chip": "💻", "data": "📊", "security": "🔒",
    "money": "💰", "startup": "🚀", "google": "🔍", "apple": "🍎",
    "medical": "🏥", "health": "💊", "education": "📚", "future": "🔮",
}

def make_emoji_banner(query: str, title: str) -> str:
    """이미지 없을 때 CSS 이모지 배너 HTML 반환"""
    q_lower = query.lower()
    emoji = "🤖"
    for kw, em in TOPIC_EMOJI_MAP.items():
        if kw in q_lower:
            emoji = em
            break
    short = title[:40] + "..." if len(title) > 40 else title
    return (
        f'<div style="background:linear-gradient(135deg,#1a237e 0%,#283593 50%,#1565c0 100%);'
        f'border-radius:16px;padding:48px 32px;text-align:center;margin:0 0 2em;'
        f'color:#fff;">'
        f'<div style="font-size:4rem;margin-bottom:16px">{emoji}</div>'
        f'<div style="font-size:1.1rem;opacity:.85;font-weight:500">{short}</div>'
        f'</div>'
    )


# ── 메인 로직 ────────────────────────────────────────────────────

def build_image_html(img: dict) -> str:
    """이미지 딕셔너리 → HTML 문자열"""
    url = img["url"]
    alt = img.get("alt", "")
    credit = img.get("credit", "")
    credit_url = img.get("credit_url", "")

    credit_html = (
        f'<a href="{credit_url}" target="_blank" rel="noopener">{credit}</a>'
        if credit_url else credit
    )

    return (
        f'<figure style="margin:0 0 2em;text-align:center;">'
        f'<img src="{url}" alt="{alt}" '
        f'style="width:100%;max-width:760px;border-radius:12px;'
        f'box-shadow:0 4px 20px rgba(0,0,0,.12);" loading="lazy"/>'
        f'<figcaption style="font-size:.82em;color:#888;margin-top:.5em;">'
        f'📷 {credit_html}'
        f'</figcaption></figure>\n\n'
    )


def inject_images(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(content)

    query = meta.get("image_query", meta.get("title", "artificial intelligence"))
    title = meta.get("title", "")

    print(f"  🔍 이미지 검색: {query}")

    # 수집 시도 순서
    images = search_wikimedia(query)
    if not images:
        print("  → Unsplash 시도")
        images = search_unsplash(query)
    if not images:
        print("  → 뉴스 og:image 시도 (scrapling)")
        images = search_news_image(query)

    # ── 대표 이미지 (hero) ──
    if images:
        hero_html = build_image_html(images[0])
        print(f"  ✅ 대표 이미지: {images[0]['source']} — {images[0]['url'][:60]}")
    else:
        hero_html = make_emoji_banner(query, title) + "\n\n"
        print("  → 이모지 배너로 대체")

    # ── 본문 중간 이미지 (2번째 h2 앞) ──
    h2_positions = [m.start() for m in re.finditer(r'^## ', body, re.MULTILINE)]
    if len(images) > 1 and len(h2_positions) >= 2:
        img2_html = build_image_html(images[1])
        insert_pos = h2_positions[1]
        body = body[:insert_pos] + img2_html + body[insert_pos:]

    # front matter 재조합
    if content.startswith("---"):
        parts = content.split("---", 2)
        new_content = "---" + parts[1] + "---\n\n" + hero_html + body
    else:
        new_content = hero_html + body

    Path(file_path).write_text(new_content, encoding="utf-8")
    print(f"  ✅ 이미지 삽입 완료")
    return file_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_images.py <markdown_file>")
        sys.exit(0)
    print(f"🖼️  이미지 처리: {sys.argv[1]}")
    inject_images(sys.argv[1])
