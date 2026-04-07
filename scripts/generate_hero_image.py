#!/usr/bin/env python3
"""
마케팅 카피 기반 Hero 이미지 생성기
────────────────────────────────────
- Claude API로 포스트 주제에 맞는 한국어 마케팅 카피 문구 생성
- Python Pillow로 1200×630px PNG 생성 (그라디언트 배경 + 텍스트)
- GitHub Pages(noivan0/aikeeper-blog)에 업로드 후 URL 반환

사용법:
    python3 scripts/generate_hero_image.py --title "ChatGPT vs Claude" --blog aikeeper
    python3 scripts/generate_hero_image.py --title "오늘의 경제 뉴스" --blog allsweep
    python3 scripts/generate_hero_image.py --title "AI 최신 트렌드" --slug custom-slug --blog aikeeper
"""

import os
import sys
import re
import json
import base64
import hashlib
import argparse
import textwrap
import urllib.request
import urllib.error
from pathlib import Path
from io import BytesIO
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow 미설치. pip3 install Pillow 실행")
    sys.exit(1)

# ── 경로 설정 ─────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
FONTS_DIR = SCRIPT_DIR / "fonts"

# 한국어 폰트 경로 (우선순위 순)
FONT_CANDIDATES = [
    str(FONTS_DIR / "NotoSansKR.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/unifont/unifont.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

# ── 환경변수 로드 ─────────────────────────────────────────────────
def _load_env():
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL  = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_MODEL     = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GITHUB_PAT          = os.environ.get("GITHUB_PAT", "")
GITHUB_REPO         = "noivan0/aikeeper-blog"
GITHUB_BRANCH       = "gh-pages"

# ── 블로그별 디자인 설정 ──────────────────────────────────────────
BLOG_THEMES = {
    "aikeeper": {
        "brand": "AI키퍼",
        "color_top":    (13,  27,  75),   # #0D1B4B
        "color_bottom": (21, 101, 192),   # #1565c0
        "accent":       (99, 179, 237),   # 밝은 파란색 강조
        "credit":       "AI키퍼",
    },
    "allsweep": {
        "brand": "올스윕 뉴스",
        "color_top":    (26,  10,   0),   # #1a0a00
        "color_bottom": (139,  0,   0),   # #8B0000
        "accent":       (255, 160,  64),  # 주황/골드 강조
        "credit":       "올스윕",
    },
}

# ── 1. 마케팅 카피 생성 (Claude API) ─────────────────────────────
def generate_marketing_copy(title: str, blog: str = "aikeeper") -> str:
    """Claude API로 포스트 제목에 맞는 한국어 마케팅 카피 1줄 생성"""
    theme = BLOG_THEMES.get(blog, BLOG_THEMES["aikeeper"])
    
    if blog == "allsweep":
        system_prompt = (
            "당신은 뉴스 미디어 광고 카피라이터입니다. "
            "포스트 제목을 보고 독자의 클릭 욕구를 자극하는 한국어 마케팅 문구를 "
            "딱 1줄(20자 이내)로 생성하세요. "
            "예: '놓치면 후회하는 오늘의 핵심', '지금 이 뉴스 모르면 뒤처진다'"
            "문구만 출력하고 따옴표나 설명은 절대 넣지 마세요."
        )
    else:
        system_prompt = (
            "당신은 AI/테크 블로그 광고 카피라이터입니다. "
            "포스트 제목을 보고 독자의 호기심을 자극하는 한국어 마케팅 문구를 "
            "딱 1줄(20자 이내)로 생성하세요. "
            "예: '지금 당신이 쓰는 AI, 진짜 최선입니까?', '모르면 손해, AI 완벽 가이드'"
            "문구만 출력하고 따옴표나 설명은 절대 넣지 마세요."
        )

    if not ANTHROPIC_API_KEY:
        print("  ⚠️  ANTHROPIC_API_KEY 없음 — 기본 카피 사용")
        return _default_copy(title, blog)

    try:
        payload = json.dumps({
            "model": ANTHROPIC_MODEL,
            "max_tokens": 80,
            "system": system_prompt,
            "messages": [{"role": "user", "content": f"포스트 제목: {title}"}]
        }).encode("utf-8")

        base_url = ANTHROPIC_BASE_URL.rstrip("/")
        api_url = f"{base_url}/messages"

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        
        copy_text = data["content"][0]["text"].strip()
        # 따옴표 제거
        copy_text = copy_text.strip('"\'"""')
        # 20자 초과 시 절삭
        if len(copy_text) > 25:
            copy_text = copy_text[:22] + "..."
        print(f"  ✅ 카피 생성: {copy_text}")
        return copy_text

    except Exception as e:
        print(f"  ⚠️  Claude API 실패: {e}")
        return _default_copy(title, blog)


def _default_copy(title: str, blog: str) -> str:
    """API 실패 시 기본 카피 반환"""
    defaults_aikeeper = [
        "AI 시대, 뒤처지지 말자",
        "지금 알아야 할 AI 핵심",
        "AI 완벽 활용 가이드",
        "모르면 손해, AI 트렌드",
        "당신의 AI, 제대로 쓰고 있나요?",
    ]
    defaults_allsweep = [
        "놓치면 후회하는 오늘의 뉴스",
        "지금 꼭 알아야 할 소식",
        "오늘의 핵심 뉴스 한눈에",
        "세상이 이렇게 돌아가고 있다",
        "당신이 몰랐던 오늘의 이슈",
    ]
    seed = int(hashlib.md5(title.encode()).hexdigest(), 16)
    if blog == "allsweep":
        return defaults_allsweep[seed % len(defaults_allsweep)]
    return defaults_aikeeper[seed % len(defaults_aikeeper)]


# ── 2. 폰트 로드 ─────────────────────────────────────────────────
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """사용 가능한 폰트 중 첫 번째를 로드"""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 최후 폴백: PIL 기본 폰트 (한국어 깨질 수 있음)
    return ImageFont.load_default()


# ── 3. 그라디언트 배경 생성 ───────────────────────────────────────
def _make_gradient(width: int, height: int,
                   color_top: tuple, color_bottom: tuple) -> Image.Image:
    """위→아래 선형 그라디언트 이미지 생성"""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    r1, g1, b1 = color_top
    r2, g2, b2 = color_bottom
    for y in range(height):
        t = y / (height - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        for x in range(width):
            pixels[x, y] = (r, g, b)
    return img


# ── 4. 텍스트 래핑 헬퍼 ──────────────────────────────────────────
def _wrap_text(text: str, font: ImageFont.FreeTypeFont,
               max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """텍스트를 max_width에 맞게 줄바꿈 (한국어 음절 단위 지원)"""
    lines = []
    # 공백 기준 우선 분리
    words = text.split()
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            # 단어 자체가 너무 길면 음절 단위 분리
            if draw.textbbox((0,0), word, font=font)[2] > max_width:
                sub = ""
                for ch in word:
                    test_ch = sub + ch
                    if draw.textbbox((0,0), test_ch, font=font)[2] <= max_width:
                        sub = test_ch
                    else:
                        if sub:
                            lines.append(sub)
                        sub = ch
                current = sub
            else:
                current = word
    if current:
        lines.append(current)
    return lines


# ── 5. PNG 이미지 생성 ───────────────────────────────────────────
def generate_image(title: str, copy_text: str, blog: str = "aikeeper",
                   slug: str = "") -> BytesIO:
    """
    1200×630 PNG 생성:
    - 그라디언트 배경
    - 좌상단: 브랜드명
    - 중앙: 마케팅 카피 (크고 굵게)
    - 하단: 포스트 제목 (작게, 줄바꿈)
    """
    theme = BLOG_THEMES.get(blog, BLOG_THEMES["aikeeper"])
    W, H = 1200, 630
    PAD = 60

    # 배경 그라디언트
    img = _make_gradient(W, H, theme["color_top"], theme["color_bottom"])
    
    # 반투명 오버레이 (가독성 향상)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 60))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # ── 상단 좌측: 브랜드명 ────────────────────────────────────────
    brand_font = _load_font(32)
    brand_text = theme["brand"]
    draw.text((PAD, PAD), brand_text, font=brand_font, fill=(255, 255, 255, 200))

    # ── 상단 우측: 장식 점 ────────────────────────────────────────
    accent = theme["accent"]
    for i, r in enumerate([6, 4, 3]):
        draw.ellipse(
            [W - PAD - 20 - i*18, PAD + 8, W - PAD - 8 - i*18, PAD + 8 + r*2],
            fill=accent
        )

    # ── 구분선 ───────────────────────────────────────────────────
    line_y = PAD + 55
    draw.line([(PAD, line_y), (W - PAD, line_y)], fill=(*accent, 120), width=1)

    # ── 중앙: 마케팅 카피 (크고 굵게) ────────────────────────────
    copy_font_size = 78
    copy_font = _load_font(copy_font_size)

    copy_max_width = W - PAD * 2 - 40
    copy_lines = _wrap_text(copy_text, copy_font, copy_max_width, draw)
    
    # 카피가 너무 길면 폰트 축소
    if len(copy_lines) > 3:
        copy_font_size = 58
        copy_font = _load_font(copy_font_size)
        copy_lines = _wrap_text(copy_text, copy_font, copy_max_width, draw)

    copy_line_h = copy_font_size + 12
    copy_total_h = len(copy_lines) * copy_line_h

    # 수직 중앙 배치 (전체 영역 기준, 약간 위)
    center_y = H // 2 - 40
    copy_start_y = center_y - copy_total_h // 2

    for i, line in enumerate(copy_lines):
        bbox = draw.textbbox((0, 0), line, font=copy_font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = copy_start_y + i * copy_line_h

        # 그림자 효과
        draw.text((x + 3, y + 3), line, font=copy_font, fill=(0, 0, 0, 100))
        # 메인 텍스트
        draw.text((x, y), line, font=copy_font, fill=(255, 255, 255))

    # ── 하단 구분선 ───────────────────────────────────────────────
    bottom_line_y = H - PAD - 80
    draw.line([(PAD, bottom_line_y), (W - PAD, bottom_line_y)],
              fill=(*accent, 80), width=1)

    # ── 하단: 포스트 제목 ────────────────────────────────────────
    title_font_size = 34
    title_font = _load_font(title_font_size)
    title_max_width = W - PAD * 2 - 40

    title_lines = _wrap_text(title, title_font, title_max_width, draw)
    # 최대 2줄
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        if len(title_lines[1]) > 3:
            title_lines[1] = title_lines[1][:-3] + "..."

    title_line_h = title_font_size + 8
    title_start_y = bottom_line_y + 16

    for i, line in enumerate(title_lines):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = title_start_y + i * title_line_h
        # 그림자
        draw.text((x + 2, y + 2), line, font=title_font, fill=(0, 0, 0, 80))
        # 텍스트
        draw.text((x, y), line, font=title_font, fill=(220, 220, 220))

    # ── 좌하단: 출처 라벨 ────────────────────────────────────────
    label_font = _load_font(22)
    label_text = f"© {theme['brand']} | 마케팅 카피 이미지"
    draw.text((PAD, H - PAD - 4), label_text,
              font=label_font, fill=(180, 180, 180))

    # BytesIO로 반환
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── 6. GitHub Pages 업로드 ───────────────────────────────────────
def upload_to_github(image_buf: BytesIO, slug: str) -> str:
    """PNG를 GitHub Pages(gh-pages 브랜치)에 업로드하고 URL 반환"""
    if not GITHUB_PAT:
        raise ValueError("GITHUB_PAT 환경변수가 없습니다")

    path = f"images/hero/{slug}.png"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    image_b64 = base64.b64encode(image_buf.read()).decode("utf-8")

    # 기존 파일 SHA 조회 (업데이트 시 필요)
    sha = None
    try:
        get_req = urllib.request.Request(
            api_url,
            headers={
                "Authorization": f"token {GITHUB_PAT}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AIkeeper-Blog/1.0",
            }
        )
        with urllib.request.urlopen(get_req, timeout=15) as resp:
            existing = json.loads(resp.read())
            sha = existing.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  ⚠️  GitHub GET 오류: {e.code}")
    except Exception as e:
        print(f"  ⚠️  GitHub GET 실패: {e}")

    # PUT 요청
    put_payload = {
        "message": f"feat: hero image for {slug}",
        "content": image_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        put_payload["sha"] = sha

    put_data = json.dumps(put_payload).encode("utf-8")
    put_req = urllib.request.Request(
        api_url,
        data=put_data,
        headers={
            "Authorization": f"token {GITHUB_PAT}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "AIkeeper-Blog/1.0",
        },
        method="PUT"
    )

    try:
        with urllib.request.urlopen(put_req, timeout=30) as resp:
            result = json.loads(resp.read())
            download_url = result.get("content", {}).get("download_url", "")
            # GitHub Pages URL로 변환
            pages_url = f"https://noivan0.github.io/aikeeper-blog/{path}"
            print(f"  ✅ GitHub Pages 업로드 성공: {pages_url}")
            return pages_url
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub PUT 실패: {e.code} — {body[:200]}")


# ── 7. 슬러그 생성 ──────────────────────────────────────────────
def _make_slug(title: str) -> str:
    """제목에서 URL-safe 슬러그 생성 (영문+숫자+해시만, 한글 제외)
    
    GitHub API URL에 한글이 포함되면 ascii 인코딩 오류 발생하므로
    반드시 영문+숫자+하이픈만으로 구성.
    """
    # 영문/숫자만 추출
    ascii_only = re.sub(r'[^a-z0-9\s-]', ' ', title.lower())
    words = ascii_only.split()
    # 의미 있는 단어만 (2글자 이상)
    words = [w for w in words if len(w) >= 2][:6]
    slug = '-'.join(words) if words else "hero"
    # 해시 접미사로 유일성 보장
    h = hashlib.md5(title.encode()).hexdigest()[:8]
    return f"{slug}-{h}"


# ── 8. 메인 함수 ─────────────────────────────────────────────────
def generate_and_upload(title: str, blog: str = "aikeeper",
                        slug: Optional[str] = None) -> dict:
    """
    전체 파이프라인 실행:
    1. Claude API → 마케팅 카피 생성
    2. Pillow → PNG 생성
    3. GitHub Pages → 업로드
    4. 결과 dict 반환

    Returns:
        {
            "url": str,             # GitHub Pages URL
            "alt": str,             # 이미지 대체 텍스트
            "credit": str,          # 출처명
            "source": str,          # "generated_hero"
            "source_label": str,    # "🎨 마케팅 카피 이미지"
        }
    """
    theme = BLOG_THEMES.get(blog, BLOG_THEMES["aikeeper"])
    
    if not slug:
        slug = _make_slug(title)

    print(f"  🎨 Hero 이미지 생성 시작: [{blog}] {title}")

    # Step 1: 마케팅 카피 생성
    print(f"  📝 Claude API → 마케팅 카피 생성 중...")
    copy_text = generate_marketing_copy(title, blog)

    # Step 2: PNG 생성
    print(f"  🖼️  Pillow → PNG 생성 중 (1200×630)...")
    image_buf = generate_image(title, copy_text, blog, slug)

    # Step 3: GitHub Pages 업로드
    print(f"  📤 GitHub Pages 업로드 중...")
    try:
        url = upload_to_github(image_buf, slug)
    except Exception as e:
        print(f"  ❌ GitHub 업로드 실패: {e}")
        # 업로드 실패 시 로컬 저장 후 None URL 반환
        local_path = SCRIPT_DIR / "fonts" / f"hero_{slug}.png"
        image_buf.seek(0)
        local_path.write_bytes(image_buf.read())
        print(f"  💾 로컬 저장: {local_path}")
        url = f"[local] {local_path}"

    return {
        "url": url,
        "alt": f"{title} — {copy_text}",
        "credit": theme["credit"],
        "credit_url": f"https://noivan0.github.io/aikeeper-blog/",
        "source": "generated_hero",
        "source_label": "🎨 마케팅 카피 이미지",
    }


# ── CLI 진입점 ────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="마케팅 카피 기반 Hero 이미지 생성 및 GitHub Pages 업로드"
    )
    parser.add_argument("--title", required=True, help="포스트 제목")
    parser.add_argument(
        "--blog",
        choices=["aikeeper", "allsweep"],
        default="aikeeper",
        help="블로그 종류 (기본: aikeeper)",
    )
    parser.add_argument("--slug", default="", help="커스텀 슬러그 (선택)")
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="GitHub 업로드 없이 로컬 PNG 저장만",
    )
    args = parser.parse_args()

    if args.no_upload:
        # 로컬 저장 모드
        slug = args.slug or _make_slug(args.title)
        copy_text = generate_marketing_copy(args.title, args.blog)
        print(f"  📝 카피: {copy_text}")
        buf = generate_image(args.title, copy_text, args.blog, slug)
        out_path = Path(f"hero_{slug}.png")
        out_path.write_bytes(buf.read())
        print(f"  💾 저장됨: {out_path.absolute()}")
    else:
        result = generate_and_upload(
            title=args.title,
            blog=args.blog,
            slug=args.slug or None,
        )
        print("\n── 결과 ─────────────────────────────────────────────")
        for k, v in result.items():
            print(f"  {k}: {v}")
