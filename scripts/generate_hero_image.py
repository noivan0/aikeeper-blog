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
import random
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

# Bold 전용 폰트 (카피 텍스트용)
FONT_BOLD_CANDIDATES = [
    str(FONTS_DIR / "NotoSansKR-Bold.otf"),
    str(FONTS_DIR / "NotoSansKR.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
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
        "brand": "AI KEEPER",
        "bg_color":    (8, 14, 31),
        "point_color": (79, 142, 247),
        "credit":      "AI\ucf00\ud37c",
    },
    "allsweep": {
        "brand": "ALL SWEEP",
        "bg_color":    (10, 10, 10),
        "point_color": (245, 166, 35),
        "credit":      "\uc62c\uc2a4\uc717",
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
        api_url = f"{base_url}/v1/messages"

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
    """사용 가능한 폰트 중 첫 번째를 로드. bold=True 시 Bold 전용 폰트 우선."""
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES
    for path in candidates:
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
    1200x630 PNG (Trendy Dark Style):
    - Dark solid bg + point color radial glow
    - Top 3px accent line
    - Top-left brand pill button
    - Bold left-aligned copy text + vertical accent bar
    - Bottom-left post title (32px, gray)
    - Bottom-right large semi-transparent "2026" decoration
    """
    theme = BLOG_THEMES.get(blog, BLOG_THEMES["aikeeper"])
    W, H = 1200, 630
    PAD = 60

    bg = theme["bg_color"]
    pc = theme["point_color"]

    # ── Step 1: Solid dark background ──────────────────────────
    img = Image.new("RGB", (W, H), bg)

    # ── Step 2: Point color radial glow (multi-layer, immersive) ─
    # Center glow
    cx, cy = W // 2, H // 2
    glow_radii = [500, 380, 260, 170, 90]
    glow_alphas = [22, 35, 50, 65, 80]
    for radius, alpha in zip(glow_radii, glow_alphas):
        glow_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_ov)
        gd.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(pc[0], pc[1], pc[2], alpha),
        )
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, glow_ov)
        img = img.convert("RGB")
    # Left-side secondary glow (카피 텍스트 영역 강조)
    lx, ly = W // 5, H // 2
    for radius, alpha in zip([300, 180, 90], [15, 25, 38]):
        glow_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_ov)
        gd.ellipse(
            [lx - radius, ly - radius, lx + radius, ly + radius],
            fill=(pc[0], pc[1], pc[2], alpha),
        )
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, glow_ov)
        img = img.convert("RGB")

    draw = ImageDraw.Draw(img)

    # ── Step 3: Top 4px point color line ───────────────────────
    draw.rectangle([0, 0, W, 4], fill=pc)

    # ── Step 4: Top-left brand pill button ─────────────────────
    # bar_x 는 Step 5와 동일하게 PAD 사용 (좌측 정렬 기준점 공유)
    bar_x = PAD
    bar_w = 6

    brand_font = _load_font(24, bold=True)
    brand_text = theme["brand"]

    # textbbox: (x0, y0, x1, y1) — y0 은 폰트 내부 상단 여백(ascent offset)
    bb = draw.textbbox((0, 0), brand_text, font=brand_font)
    # 실제 글리프 너비/높이 (내부 여백 포함하지 않음)
    glyph_w = bb[2] - bb[0]   # 실제 문자 폭
    glyph_h = bb[3] - bb[1]   # 실제 문자 높이
    pill_pad_x = 20            # 좌우 패딩
    pill_pad_y = 10            # 상하 패딩

    pill_x0 = bar_x + bar_w + 12
    pill_y0 = PAD              # PAD(60)만큼 내려서 상단 여백 확보
    pill_x1 = pill_x0 + glyph_w + pill_pad_x * 2
    pill_y1 = pill_y0 + glyph_h + pill_pad_y * 2

    pill_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd_draw = ImageDraw.Draw(pill_ov)
    try:
        pd_draw.rounded_rectangle(
            [pill_x0, pill_y0, pill_x1, pill_y1],
            radius=22,
            fill=(pc[0], pc[1], pc[2], 230),
        )
    except AttributeError:
        pd_draw.rectangle(
            [pill_x0, pill_y0, pill_x1, pill_y1],
            fill=(pc[0], pc[1], pc[2], 230),
        )
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, pill_ov)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    # 텍스트 draw 위치: pill 상단 + pad - 폰트 내부 상단 여백(bb[1]) 보정
    draw.text(
        (pill_x0 + pill_pad_x - bb[0], pill_y0 + pill_pad_y - bb[1]),
        brand_text,
        font=brand_font,
        fill=(255, 255, 255),
    )

    # ── Step 5: Bold left-aligned copy text + vertical accent bar ──
    copy_font_size = 84
    copy_font = _load_font(copy_font_size, bold=True)
    # text_x = bar 오른쪽 + 간격 (pill_x0와 동일 기준)
    text_x = bar_x + bar_w + 12
    copy_max_width = W - text_x - PAD

    copy_lines = _wrap_text(copy_text, copy_font, copy_max_width, draw)
    if len(copy_lines) > 3:
        copy_font_size = 64
        copy_font = _load_font(copy_font_size, bold=True)
        copy_lines = _wrap_text(copy_text, copy_font, copy_max_width, draw)

    copy_line_h = copy_font_size + 14
    copy_total_h = len(copy_lines) * copy_line_h

    # vertical center: pill 아래 ~ 하단 title 위 영역에서 수직 중앙
    brand_bottom = pill_y1 + 24
    title_reserve = 90      # 하단 포스트 제목 영역 확보
    available_h = H - brand_bottom - title_reserve
    copy_start_y = brand_bottom + (available_h - copy_total_h) // 2

    # vertical accent bar: 첫/마지막 줄 실제 글리프 bbox 기준으로 정확히 정렬
    first_cb = draw.textbbox((0, 0), copy_lines[0], font=copy_font)
    last_cb  = draw.textbbox((0, 0), copy_lines[-1], font=copy_font)
    # bar top: 첫 줄 draw y + 폰트 내부 상단 여백(first_cb[1])
    bar_top = copy_start_y + first_cb[1]
    # bar bot: 마지막 줄 draw y + 폰트 내부 하단 (last_cb[3])
    last_line_y = copy_start_y + (len(copy_lines) - 1) * copy_line_h
    bar_bot = last_line_y + last_cb[3]
    draw.rectangle([bar_x, bar_top, bar_x + bar_w, bar_bot], fill=pc)

    # copy text lines (multi-layer shadow for depth)
    for i, line in enumerate(copy_lines):
        y = copy_start_y + i * copy_line_h
        # shadow layers
        for ox, oy in [(3, 3), (2, 2), (1, 1)]:
            draw.text((text_x + ox, y + oy), line, font=copy_font,
                      fill=(0, 0, 0))
        # main text
        draw.text((text_x, y), line, font=copy_font,
                  fill=(255, 255, 255))

    # ── Step 6: Post title bottom-left (32px, gray) ────────────
    title_font_size = 32
    title_font = _load_font(title_font_size)
    title_max_width = W * 3 // 4

    title_lines = _wrap_text(title, title_font, title_max_width, draw)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        if len(title_lines[1]) > 3:
            title_lines[1] = title_lines[1][:-3] + "..."

    title_line_h = title_font_size + 10
    title_total_h = len(title_lines) * title_line_h
    title_start_y = H - PAD - title_total_h

    for i, line in enumerate(title_lines):
        y = title_start_y + i * title_line_h
        draw.text((PAD, y), line, font=title_font,
                  fill=(160, 174, 192))

    # ── Step 7: Bottom-right "2026" large semi-transparent deco ─
    deco_font_size = 120
    deco_font = _load_font(deco_font_size)
    deco_text = "2026"

    deco_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    deco_draw = ImageDraw.Draw(deco_ov)
    db = deco_draw.textbbox((0, 0), deco_text, font=deco_font)
    dw = db[2] - db[0]
    dh = db[3] - db[1]
    deco_x = W - PAD - dw
    deco_y = H - PAD - dh
    deco_draw.text(
        (deco_x, deco_y),
        deco_text,
        font=deco_font,
        fill=(255, 255, 255, 20),
    )
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, deco_ov)
    img = img.convert("RGB")

    # BytesIO 반환
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
            "source_label": str,    # "🎨 AI키퍼" or "🎨 올스윕"
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

    brand_label = "🎨 AI키퍼" if blog == "aikeeper" else "🎨 올스윕"
    return {
        "url": url,
        "alt": f"{title} — {copy_text}",
        "credit": theme["credit"],
        "credit_url": f"https://noivan0.github.io/aikeeper-blog/",
        "source": "generated_hero",
        "source_label": brand_label,
    }




def generate_section_image(section_title: str, post_title: str, blog: str = "aikeeper", idx: int = 0) -> dict:
    """본문 섹션용 마케팅 카피 이미지 생성

    Args:
        section_title: h2 섹션 제목
        post_title: 포스트 전체 제목 (문맥용)
        blog: aikeeper or allsweep
        idx: 섹션 순서 (슬러그 고유성용)
    Returns:
        dict with url, alt, credit, source
    """
    # 섹션별 고유 슬러그
    slug_base = _make_slug(f"{post_title}-sec{idx}-{section_title}")
    slug = slug_base[:50]

    # 섹션 카피: 섹션 제목 중심으로 생성
    combined = f"{post_title}: {section_title}"
    copy_text = generate_marketing_copy(combined, blog)

    theme = BLOG_THEMES.get(blog, BLOG_THEMES["aikeeper"])
    buf = generate_image(
        title=section_title,
        copy_text=copy_text,
        blog=blog,
        slug=slug,
    )

    section_brand_label = "🎨 AI키퍼" if blog == "aikeeper" else "🎨 올스윕"
    try:
        url = upload_to_github(buf, slug)
    except Exception as e:
        print(f"  ❌ 섹션 이미지 업로드 실패: {e}")
        return {
            "url": "",
            "alt": section_title,
            "credit": theme["credit"],
            "credit_url": "https://noivan0.github.io/aikeeper-blog/",
            "source": "generated_section",
            "source_label": section_brand_label,
        }

    return {
        "url": url,
        "alt": f"{section_title} — {copy_text}",
        "credit": theme["credit"],
        "credit_url": "https://noivan0.github.io/aikeeper-blog/",
        "source": "generated_section",
        "source_label": section_brand_label,
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
