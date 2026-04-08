"""
ggultongmon 카드뉴스 자동 생성기 v1
=========================================
용도: post_to_blogger_ggultongmon.py 발행 완료 후 자동 호출
입력: 발행된 Blogger 포스트 URL, 상품 목록 (dict list), 주제명
출력: /tmp/carousel_out/{timestamp}/ 에 8장 JPG 저장 + 경로 반환

사용법 (직접 실행):
  python3 carousel_auto.py \
    --url "https://ggultongmon.allsweep.xyz/..." \
    --topic "크레아틴 비교" \
    --md_file "posts-ggultongmon/2026-04-08-....md"

사용법 (import):
  from instagram.carousel_auto import generate_carousel
  paths = generate_carousel(post_url, topic, products, md_file=None)
"""

import os, sys, re, json, argparse, urllib.request
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── 경로 ──────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent          # p004-blogger/
FONT_BOLD  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG   = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SPEC_DIR   = Path(__file__).parent / "carousel-format"

W, H  = 1080, 1080
PAD   = 60

# ── 컬러 시스템 ───────────────────────────────────────────────────
BG       = (14,  14,  20)
BG2      = (24,  24,  34)
BG3      = (34,  34,  48)
WHITE    = (255, 255, 255)
CREAM    = (255, 245, 225)
ORANGE   = (255, 135, 20)
GRAY_L   = (160, 160, 180)
GRAY_M   = (90,  90,  110)
GRAY_D   = (40,  40,  56)
SILVER   = (185, 185, 210)
BRONZE   = (170, 120, 45)


# ── 폰트 헬퍼 ─────────────────────────────────────────────────────
def F(size, bold=True):
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size, index=3)

def tw(f, t):
    b = f.getbbox(t); return b[2] - b[0]

def th(f, t="가나다"):
    b = f.getbbox(t); return b[3] - b[1]

def shrink(f, text, max_w):
    while tw(f, text) > max_w and f.size > 12:
        f = ImageFont.truetype(f.path, f.size - 2, index=3)
    return f

def mm(draw, text, cx, cy, f, color, max_w=None):
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text); b = f.getbbox(text)
    vis_cy = (b[1] + b[3]) / 2
    draw.text((cx - w_ // 2, cy - int(vis_cy)), text, font=f, fill=color)

def lm(draw, text, x, cy, f, color, max_w=None):
    if max_w: f = shrink(f, text, max_w)
    b = f.getbbox(text); vis_cy = (b[1] + b[3]) / 2
    draw.text((x, cy - int(vis_cy)), text, font=f, fill=color)

def ct(draw, text, y_top, f, color, max_w=W - PAD * 2):
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text); b = f.getbbox(text)
    draw.text(((W - w_) // 2, y_top - b[1]), text, font=f, fill=color)
    return b[3] - b[1]

def divider(draw, y, width=160, col=ORANGE, h=4):
    draw.rectangle([(W // 2 - width // 2, y), (W // 2 + width // 2, y + h)], fill=col)

def top_bar(draw, col=ORANGE): draw.rectangle([0, 0, W, 6], fill=col)
def bot_bar(draw, col=ORANGE): draw.rectangle([0, H - 6, W, H], fill=col)

def slide_no(draw, n, t):
    draw.text((W - PAD, H - 36), f"{n} / {t}", font=F(22, False), fill=GRAY_M, anchor="rm")

def add_grain(img, a=5):
    import random; p = img.load()
    for _ in range(W * H // 35):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        d = random.randint(-a, a)
        p[x, y] = tuple(max(0, min(255, c + d)) for c in p[x, y])
    return img


# ── 상품 이미지 다운로드 ──────────────────────────────────────────
def fetch_product_images(post_url: str, out_dir: Path, count: int = 3) -> list:
    """Blogger 발행 HTML에서 쿠팡 이미지 URL 추출 후 다운로드"""
    paths = []
    try:
        req = urllib.request.Request(
            post_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        imgs = re.findall(r'src=["\']([^"\']+coupangcdn[^"\']+)["\']', html)
        # 중복 제거
        seen = set(); unique_imgs = []
        for img in imgs:
            base = img.split("?")[0]
            if base not in seen:
                seen.add(base); unique_imgs.append(img)
        print(f"[carousel] 이미지 URL {len(unique_imgs)}개 발견")

        for i, img_url in enumerate(unique_imgs[:count]):
            dest = out_dir / f"prod{i+1}.jpg"
            try:
                req2 = urllib.request.Request(
                    img_url,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.coupang.com"}
                )
                data = urllib.request.urlopen(req2, timeout=12).read()
                dest.write_bytes(data)
                print(f"[carousel] 이미지 다운로드: prod{i+1}.jpg ({len(data)//1024}KB)")
                paths.append(dest)
            except Exception as e:
                print(f"[carousel] 이미지 다운로드 실패 prod{i+1}: {e}")
                paths.append(None)
    except Exception as e:
        print(f"[carousel] HTML 수집 실패: {e}")

    # 부족분 None으로 채우기
    while len(paths) < count:
        paths.append(None)
    return paths


# ── 상품 정보 파싱 ────────────────────────────────────────────────
def parse_products(products: list) -> list:
    """products 리스트에서 카드뉴스용 데이터 추출"""
    result = []
    for i, p in enumerate(products[:3]):
        name = p.get("productName", f"상품 {i+1}")
        price = int(float(p.get("productPrice", 0)))
        result.append({
            "rank": i + 1,
            "name": name[:20],           # 길면 자름
            "name_short": name[:12],     # 매우 짧게
            "price": f"{price:,}원",
            "url": p.get("shortenUrl", p.get("productUrl", "")),
        })
    return result


# ── 상품 이미지 붙이기 ────────────────────────────────────────────
def paste_img(img, path, cx, cy, size):
    try:
        p = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=24, fill=255)
        img.paste(p, (cx - size // 2, cy - size // 2), mask)
    except Exception as e:
        print(f"[carousel] 이미지 붙이기 실패: {e}")
        d = ImageDraw.Draw(img)
        x, y = cx - size // 2, cy - size // 2
        d.rounded_rectangle([x, y, x + size, y + size], radius=24, fill=GRAY_D)
        d.text((cx, cy), "IMG", font=F(28), fill=GRAY_M, anchor="mm")


# ══════════════════════════════════════════════════════════════
# 슬라이드 생성 함수들
# ══════════════════════════════════════════════════════════════

def make_s1_cover(out, topic, products, img_paths):
    """커버: 주제 + 상품 3종 이미지"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = y / H
        d.line([(0, y), (W, y)], fill=(int(14 + v * 28), int(14 + v * 14), int(20 + v * 8)))
    top_bar(d); bot_bar(d)

    # 카테고리 뱃지
    badge = "쿠팡 추천  |  비교 리뷰"
    fb = F(26)
    bw = tw(fb, badge) + 48
    bx = (W - bw) // 2
    d.rounded_rectangle([bx, 18, bx + bw, 68], radius=25, fill=ORANGE)
    mm(d, badge, W // 2, 43, fb, BG)

    # 상품 이미지
    positions = [(W//2, 295), (W//2-262, 312), (W//2+262, 312)]
    sizes     = [210, 185, 185]
    for i, (cx, cy) in enumerate(positions):
        if img_paths[i]:
            paste_img(img, img_paths[i], cx, cy, sizes[i])
    d = ImageDraw.Draw(img)

    # 순위 뱃지
    rank_data = [
        (positions[0], sizes[0], "1위", ORANGE, BG),
        (positions[1], sizes[1], "2위", SILVER, BG),
        (positions[2], sizes[2], "3위", BRONZE, BG),
    ]
    for (cx, cy), sz, label, bg_c, fg_c in rank_data:
        badge_cy = cy - sz // 2
        d.ellipse([cx - 26, badge_cy - 20, cx + 26, badge_cy + 20], fill=bg_c)
        mm(d, label, cx, badge_cy, F(22), fg_c if fg_c == BG else WHITE)

    # 타이틀 — 주제에서 자동 생성
    # 주제가 길면 두 줄로 분리
    words = topic.split()
    mid = len(words) // 2
    line1 = " ".join(words[:max(1, mid)])
    line2 = " ".join(words[max(1, mid):]) if len(words) > 1 else ""

    # 서브라인
    n_prods = len([p for p in products if p])
    ct(d, f"2026 최신  |  {n_prods}종 직접 비교", 448, F(28, False), GRAY_L)

    # 메인 타이틀
    y_title = 490
    h1 = ct(d, line1, y_title, F(72), WHITE, max_w=W - 80)
    if line2:
        ct(d, line2, y_title + h1 + 8, F(72), ORANGE, max_w=W - 80)
    else:
        # 단일 줄일 때 타이틀 + 부제 구성
        ct(d, topic, y_title, F(68), WHITE, max_w=W - 80)

    # 제품명 나열
    names = "  vs  ".join([p["name_short"] for p in products if p])
    ct(d, names, 670, F(30, False), GRAY_L, max_w=W - 80)

    mm(d, "꿀통몬 PICKS", W // 2, H - 32, F(26), ORANGE)
    slide_no(d, 1, 8)
    add_grain(img)
    path = out / "slide_01_cover.jpg"
    img.save(path, quality=96)
    return path


def make_s2_checklist(out, topic):
    """체크리스트: 구매 전 확인 5가지"""
    CARD_H = 163
    CARDS_TOP = 175
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W // 2, 30, F(26), ORANGE)
    ct(d, "사기 전 체크 5가지", 54, F(56), WHITE)
    ct(d, "이것만 알면 절대 후회 없다", 118, F(29, False), GRAY_L)
    divider(d, 155, width=120, h=3)

    items = [
        ("성분 순도",  "주성분 100% 단일 구성인지 확인"),
        ("실제 함량",  "1회 제공량 중 순수 함량 g수 확인"),
        ("1회 단가",   "총 중량 나누기 가격 직접 계산 필수"),
        ("제형 선택",  "분말(저렴·조절) vs 정제(휴대 간편)"),
        ("목적 구분",  "근력 향상 vs 펌핑·회복 목적 먼저 정하기"),
    ]

    y = CARDS_TOP
    for i, (main, sub) in enumerate(items):
        bg_ = BG2 if i % 2 == 0 else BG3
        card_y2 = y + CARD_H - 5
        d.rounded_rectangle([PAD, y, W - PAD, card_y2], radius=14, fill=bg_)
        d.rounded_rectangle([PAD, y, PAD + 7, card_y2], radius=3, fill=ORANGE)

        card_cy = y + (CARD_H - 5) // 2
        num_cx = PAD + 54
        d.ellipse([num_cx - 23, card_cy - 23, num_cx + 23, card_cy + 23], fill=ORANGE)
        mm(d, str(i + 1), num_cx, card_cy, F(27), BG)

        text_x = PAD + 98
        avail_w = W - PAD - text_x - 14
        lm(d, main, text_x, y + (CARD_H - 5) * 37 // 100, F(36), WHITE, max_w=avail_w)
        lm(d, sub,  text_x, y + (CARD_H - 5) * 67 // 100, F(25, False), GRAY_L, max_w=avail_w)
        y += CARD_H

    slide_no(d, 2, 8)
    add_grain(img, 5)
    path = out / "slide_02_checklist.jpg"
    img.save(path, quality=96)
    return path


def make_product_slide(out, n, prod, img_path,
                       rank_txt, rank_bg, rank_fg,
                       price_bg, tags, tag_col,
                       summary, sum_bg, stars, star_col,
                       warning=None):
    """제품 슬라이드 (3/4/5)"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d, rank_bg); bot_bar(d)

    # 헤더 띠
    d.rectangle([0, 6, W, 106], fill=rank_bg)
    mm(d, rank_txt, W // 2, 56, F(46), rank_fg)

    # 이미지
    IMG_SZ = 238; IMG_CX = 832; IMG_CY = 318
    if img_path:
        paste_img(img, img_path, IMG_CX, IMG_CY, IMG_SZ)
    d = ImageDraw.Draw(img)

    TEXT_MAX_W = IMG_CX - IMG_SZ // 2 - PAD - 20

    # 제품명
    lm(d, prod["name_short"], PAD, 155, F(52), WHITE, max_w=TEXT_MAX_W)
    lm(d, prod["name"], PAD, 214, F(28, False), GRAY_L, max_w=TEXT_MAX_W)

    # 가격
    fp = F(38)
    pw = tw(fp, prod["price"]) + 44
    d.rounded_rectangle([PAD, 246, PAD + pw, 306], radius=26, fill=price_bg)
    mm(d, prod["price"], PAD + pw // 2, 276, fp, rank_fg if rank_fg == BG else WHITE)

    # 스펙 (prod 딕셔너리에 specs 없으면 기본값)
    specs = prod.get("specs", [
        "상세 스펙은 블로그 참고",
        "쿠팡 로켓배송 가능",
        "리뷰 별점 4.0 이상",
        "쿠팡 파트너스 추천 상품",
    ])
    sy = 326
    for spec in specs[:4]:
        cy_ = sy + 18
        d.ellipse([PAD, cy_ - 7, PAD + 14, cy_ + 7], fill=rank_bg if rank_bg not in [BG, BG2, BG3] else ORANGE)
        lm(d, spec, PAD + 24, cy_, F(28, False), WHITE, max_w=TEXT_MAX_W - 10)
        sy += 50

    # 구분선
    d.rectangle([PAD, 552, W - PAD, 555], fill=GRAY_D)

    # 태그
    tx = PAD; ty_tag = 585
    for tag in tags:
        ft = F(24)
        tw_ = tw(ft, tag) + 26
        th_ = th(ft, tag) + 14
        ty1 = ty_tag - th_ // 2; ty2 = ty_tag + th_ // 2
        d.rounded_rectangle([tx, ty1, tx + tw_, ty2], radius=18, fill=GRAY_D)
        d.rectangle([tx, ty1, tx + 6, ty2], fill=tag_col)
        lm(d, tag, tx + 14, ty_tag, ft, tag_col)
        tx += tw_ + 12

    # 평가 카드
    EVAL_Y1 = 618
    if warning:
        EVAL_Y2 = 820
        d.rounded_rectangle([PAD, EVAL_Y1, W - PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD + 7, EVAL_Y2], fill=tag_col)
        row_h = (EVAL_Y2 - EVAL_Y1) // 3
        mm(d, summary, W // 2, EVAL_Y1 + row_h // 2, F(32), WHITE, max_w=W - PAD * 2 - 40)
        mm(d, warning, W // 2, EVAL_Y1 + row_h + row_h // 2, F(24, False), GRAY_L, max_w=W - PAD * 2 - 40)
        mm(d, stars,   W // 2, EVAL_Y1 + row_h * 2 + row_h // 2, F(32), star_col, max_w=W - PAD * 2 - 40)
    else:
        EVAL_Y2 = 800
        d.rounded_rectangle([PAD, EVAL_Y1, W - PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD + 7, EVAL_Y2], fill=tag_col)
        row_h = (EVAL_Y2 - EVAL_Y1) // 2
        mm(d, summary, W // 2, EVAL_Y1 + row_h // 2, F(34), WHITE, max_w=W - PAD * 2 - 40)
        mm(d, stars,   W // 2, EVAL_Y1 + row_h + row_h // 2, F(34), star_col, max_w=W - PAD * 2 - 40)

    link_y = EVAL_Y2 + 20
    mm(d, "쿠팡 로켓배송  /  링크는 프로필 참고", W // 2, link_y, F(24, False), GRAY_M)

    slide_no(d, n, 8)
    add_grain(img)
    path = out / f"slide_{n:02d}_product.jpg"
    img.save(path, quality=96)
    return path


def make_s6_compare(out, products):
    """비교표"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W // 2, 30, F(26), ORANGE)
    ct(d, "한눈에 비교", 54, F(60), WHITE)
    divider(d, 128, width=130, h=4)

    CX  = [68, 305, 558, 810]
    CW  = [228, 244, 244, 240]
    ROW_TOP = 144
    ROW_H   = 86

    # 헤더 (제품명 자동)
    p_names = [p["name_short"] for p in products]
    hdrs  = ["항목"] + p_names
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROW_TOP, W - PAD, ROW_TOP + ROW_H], fill=(18, 18, 28))
    for cx, cw, hdr, hcol in zip(CX, CW, hdrs, hcols):
        lm(d, hdr, cx, ROW_TOP + ROW_H // 2, shrink(F(24), hdr, cw - 8), hcol)

    # 행 데이터 — 제품 정보에서 자동 채우기
    rows = [
        ("가격",)    + tuple(p["price"] for p in products),
        ("주요 성분",) + tuple(p.get("ingredient", "-") for p in products),
        ("제형",)    + tuple(p.get("form", "-") for p in products),
        ("용량",)    + tuple(p.get("volume", "-") for p in products),
        ("1회 단가",)+ tuple(p.get("unit_price", "-") for p in products),
        ("인증",)    + tuple(p.get("cert", "-") for p in products),
        ("추천",)    + tuple(p.get("target", "-") for p in products),
    ]
    vcols = [GRAY_L, ORANGE, SILVER, BRONZE]

    y = ROW_TOP + ROW_H
    for ri, row in enumerate(rows):
        bg_ = BG2 if ri % 2 == 0 else BG3
        row_y2 = y + ROW_H - 2
        d.rectangle([PAD, y, W - PAD, row_y2], fill=bg_)
        d.rectangle([CX[1] - 8, y, CX[1] + CW[1] - 6, row_y2], fill=(28, 16, 4))
        for ci, (val, vc) in enumerate(zip(row, vcols)):
            fv = shrink(F(23 if ci == 0 else 20, bold=(ci == 0)), str(val), CW[ci] - 12)
            lm(d, str(val), CX[ci], y + ROW_H // 2, fv, vc)
        y += ROW_H

    # 요약
    sum_y1 = y + 10; sum_y2 = y + 78
    d.rounded_rectangle([PAD, sum_y1, W - PAD, sum_y2], radius=12, fill=(32, 18, 4))
    d.rectangle([PAD, sum_y1, PAD + 6, sum_y2], fill=ORANGE)
    rank_txt = "  >  ".join(p["name_short"] for p in products)
    mm(d, f"추천 순위:  {rank_txt}", W // 2, sum_y1 + (sum_y2 - sum_y1) // 2,
       F(24), WHITE, max_w=W - PAD * 2 - 30)

    slide_no(d, 6, 8)
    add_grain(img, 5)
    path = out / "slide_06_compare.jpg"
    img.save(path, quality=96)
    return path


def make_s7_quote(out, topic):
    """핵심 메시지"""
    img = Image.new("RGB", (W, H), (10, 6, 2))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 90): d.line([(x, 0), (x, H)], fill=(18, 12, 5), width=1)
    for y in range(0, H, 90): d.line([(0, y), (W, y)], fill=(18, 12, 5), width=1)
    top_bar(d); bot_bar(d)

    d.text((38, -62), '"', font=F(280), fill=(38, 24, 6))

    # 주제에서 핵심 문구 자동 생성
    f1 = F(74); f2 = F(68)
    h1 = th(f1); h2 = th(f2)
    f_sub = F(36, False); f_cap = F(28, False)
    h_sub = th(f_sub); h_cap = th(f_cap)
    total_h = h1 + 20 + h2 + 32 + 4 + 24 + h_sub + 16 + h_cap
    y = (H - total_h) // 2

    ct(d, "비싸다고 무조건 좋은 건", y, f1, WHITE); y += h1 + 20
    ct(d, "아닙니다", y, f2, ORANGE); y += h2 + 32

    divider(d, y, width=180, h=4); y += 4 + 24
    ct(d, "목적에 맞는 제품이 진짜 가성비", y, f_sub, GRAY_L); y += h_sub + 16
    ct(d, "블로그 전문 비교 리뷰 기반", y, f_cap, GRAY_M)

    slide_no(d, 7, 8)
    add_grain(img, 5)
    path = out / "slide_07_quote.jpg"
    img.save(path, quality=96)
    return path


def make_s8_cta(out, blog_name="꿀통몬"):
    """CTA"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(380, 0, -6):
        ratio = r / 380; a = int((1 - ratio ** 2) * 85)
        gd.ellipse([W//2-r, H//2-r, W//2+r, H//2+r],
                   fill=(255, int(135 * (1 - ratio)), 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    # 저장 아이콘
    ic_cx, ic_top, ic_h = W // 2, 160, 80
    d.rectangle([ic_cx - 36, ic_top, ic_cx + 36, ic_top + ic_h], fill=ORANGE)
    d.polygon([(ic_cx - 36, ic_top + ic_h), (ic_cx + 36, ic_top + ic_h), (ic_cx, ic_top + ic_h + 38)], fill=ORANGE)

    GAP_L, GAP_M = 28, 20
    f_main, f_sub_, f_note, f_hash = F(76), F(68), F(34, False), F(27, False)

    y = ic_top + ic_h + 38 + GAP_L
    h_ = ct(d, "저장해두고", y, f_main, WHITE); y += h_ + GAP_L
    h_ = ct(d, "쿠팡에서 확인하세요", y, f_sub_, ORANGE); y += h_ + GAP_M + 10
    h_ = ct(d, "링크는 프로필에 있어요", y, f_note, GRAY_L); y += h_ + GAP_M + 6

    BTN_H = 74; btn_w = 490
    btn_x = (W - btn_w) // 2
    d.rounded_rectangle([btn_x, y, btn_x + btn_w, y + BTN_H], radius=37, fill=ORANGE)
    mm(d, f"팔로우  @{blog_name}", W // 2, y + BTN_H // 2, F(36), BG)
    y += BTN_H + GAP_M + 6

    ct(d, "#쿠팡추천  #가성비  #꿀통몬", y, f_hash, GRAY_M)
    slide_no(d, 8, 8)
    add_grain(img, 5)
    path = out / "slide_08_cta.jpg"
    img.save(path, quality=96)
    return path


# ══════════════════════════════════════════════════════════════
# 메인 생성 함수
# ══════════════════════════════════════════════════════════════
def generate_carousel(
    post_url: str,
    topic: str,
    products: list,
    md_file: str = None,
    out_dir: str = None,
) -> dict:
    """
    카드뉴스 8장 자동 생성
    Returns: {
        "slides": [Path, ...],  # 8장 경로
        "out_dir": Path,
        "topic": str,
        "post_url": str,
    }
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if out_dir:
        out = Path(out_dir)
    else:
        out = Path(f"/tmp/carousel_out/{ts}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"[carousel] 출력 디렉토리: {out}")

    # 상품 정보 파싱
    prods = parse_products(products)
    # 기본 스펙 자동 채우기 (포스트 md 파싱 시 더 정확하게)
    rank_configs = [
        {"tags": ["가성비 최고", "1위 추천", "입문자"], "tag_col": ORANGE,
         "summary": "입문자 1순위  |  가성비 최고",
         "sum_bg": (36,20,4), "stars": "★★★★★", "star_col": ORANGE,
         "rank_bg": ORANGE, "rank_fg": BG, "price_bg": ORANGE},
        {"tags": ["2위", "국산 선호", "안정적 선택"], "tag_col": SILVER,
         "summary": "안정적인 2순위 선택",
         "sum_bg": (22,22,42), "stars": "★★★★☆", "star_col": SILVER,
         "rank_bg": (88,88,124), "rank_fg": WHITE, "price_bg": (88,88,130),
         "warning": "장기 복용 시 단가 비교 권장"},
        {"tags": ["3위", "중급자", "특수 목적"], "tag_col": BRONZE,
         "summary": "중급자 이상 추천",
         "sum_bg": (22,14,4), "stars": "★★★☆☆", "star_col": BRONZE,
         "rank_bg": (72,48,10), "rank_fg": CREAM,  "price_bg": (68,44,8),
         "warning": "입문자 비권장 — 기본 보충제 먼저"},
    ]

    # 상품 이미지 다운로드
    print(f"[carousel] 상품 이미지 다운로드 중...")
    img_paths = fetch_product_images(post_url, out, count=3)

    # 슬라이드 생성
    slides = []
    print("[carousel] 슬라이드 생성 시작...")

    slides.append(make_s1_cover(out, topic, prods, img_paths))
    slides.append(make_s2_checklist(out, topic))

    # 제품 슬라이드 3장
    for i, (prod, cfg) in enumerate(zip(prods, rank_configs)):
        rank_labels = ["1위  추천", "2위", "3위  (중급자용)"]
        slide = make_product_slide(
            out, n=3+i, prod=prod, img_path=img_paths[i],
            rank_txt=rank_labels[i],
            rank_bg=cfg["rank_bg"], rank_fg=cfg["rank_fg"],
            price_bg=cfg["price_bg"],
            tags=cfg["tags"], tag_col=cfg["tag_col"],
            summary=cfg["summary"], sum_bg=cfg["sum_bg"],
            stars=cfg["stars"], star_col=cfg["star_col"],
            warning=cfg.get("warning"),
        )
        slides.append(slide)

    slides.append(make_s6_compare(out, prods))
    slides.append(make_s7_quote(out, topic))
    slides.append(make_s8_cta(out))

    print(f"[carousel] 완료! {len(slides)}장 생성 → {out}/")
    for s in slides:
        print(f"  {s.name}")

    return {
        "slides": slides,
        "out_dir": out,
        "topic": topic,
        "post_url": post_url,
    }


# ══════════════════════════════════════════════════════════════
# CLI 진입점
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ggultongmon 카드뉴스 자동 생성")
    parser.add_argument("--url",     required=True, help="Blogger 포스트 URL")
    parser.add_argument("--topic",   required=True, help="포스트 주제")
    parser.add_argument("--products", default="[]",  help="상품 JSON 문자열")
    parser.add_argument("--md_file", default=None,   help="마크다운 파일 경로")
    parser.add_argument("--out_dir", default=None,   help="출력 디렉토리")
    args = parser.parse_args()

    products = json.loads(args.products)
    result = generate_carousel(
        post_url=args.url,
        topic=args.topic,
        products=products,
        md_file=args.md_file,
        out_dir=args.out_dir,
    )
    print(f"\n출력 경로: {result['out_dir']}")
