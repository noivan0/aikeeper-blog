"""
ggultongmon 카드뉴스 자동 생성기 v2
=========================================
베이스: v6 확정 포맷 (노이반님 최종 승인본)
- 박스 텍스트 수직 중앙 정렬
- 그리드 시스템 (헤더/콘텐츠/푸터 분리)
- 간격/강조 v6 기준 완전 반영

사용법 (import):
  from instagram.carousel_auto import generate_carousel
  result = generate_carousel(post_url, topic, products)

사용법 (CLI):
  python3 carousel_auto.py \
    --url "https://ggultongmon.allsweep.xyz/..." \
    --topic "크레아틴 비교" \
    --products '[{"productName":"...","productPrice":"19500",...}]'
"""

import os, sys, re, json, argparse, urllib.request, random
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── 경로 설정 ──────────────────────────────────────────────────
BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
REG_PATH  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H  = 1080, 1080
PAD   = 60

# ── 컬러 (v6 확정) ─────────────────────────────────────────────
BG      = (14,  14,  20)
BG2     = (24,  24,  34)
BG3     = (34,  34,  48)
WHITE   = (255, 255, 255)
CREAM   = (255, 245, 225)
ORANGE  = (255, 135, 20)
GRAY_L  = (160, 160, 180)
GRAY_M  = (90,  90,  110)
GRAY_D  = (40,  40,  56)
RED     = (220, 60,  50)
SILVER  = (185, 185, 210)
BRONZE  = (170, 120, 45)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 폰트 / 텍스트 헬퍼 (v5/v6 동일)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def F(size, bold=True):
    return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size, index=3)

def tw(f, t):
    b = f.getbbox(t); return b[2] - b[0]

def th(f, t="가나다"):
    b = f.getbbox(t); return b[3] - b[1]

def shrink(f, text, max_w):
    while tw(f, text) > max_w and f.size > 12:
        f = ImageFont.truetype(f.path, f.size - 2, index=3)
    return f

def mm(draw, text, cx, cy, f, color, max_w=None):
    """완전 중앙(x,y) — getbbox 기반 시각적 중앙"""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text)
    b  = f.getbbox(text)
    vis_cy = (b[1] + b[3]) / 2
    draw.text((cx - w_ // 2, cy - int(vis_cy)), text, font=f, fill=color)

def lm(draw, text, x, cy, f, color, max_w=None):
    """좌측(x), 수직중앙(cy)"""
    if max_w: f = shrink(f, text, max_w)
    b = f.getbbox(text)
    vis_cy = (b[1] + b[3]) / 2
    draw.text((x, cy - int(vis_cy)), text, font=f, fill=color)

def ct(draw, text, y_top, f, color, max_w=W - PAD * 2):
    """상단y 기준 중앙정렬. 반환: 시각 높이"""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text)
    b  = f.getbbox(text)
    draw.text(((W - w_) // 2, y_top - b[1]), text, font=f, fill=color)
    return b[3] - b[1]

def badge(draw, text, cx, cy, f, bg_col, fg_col, pad_x=22, pad_y=0, radius=26):
    """박스+텍스트 — cy = 박스 수직 중심"""
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10
    bw = w_ + pad_x * 2
    x1 = cx - bw // 2; x2 = cx + bw // 2
    y1 = cy - bh // 2; y2 = cy + bh // 2
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_col)
    mm(draw, text, cx, cy, f, fg_col)

def badge_left(draw, text, x, cy, f, bg_col, fg_col, pad_x=18, pad_y=0, radius=24):
    """좌측 박스+텍스트 수직중앙"""
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10
    bw = w_ + pad_x * 2
    y1 = cy - bh // 2; y2 = cy + bh // 2
    draw.rounded_rectangle([x, y1, x + bw, y2], radius=radius, fill=bg_col)
    lm(draw, text, x + pad_x, cy, f, fg_col)
    return x + bw

def divider(draw, y, width=160, col=ORANGE, h=4):
    draw.rectangle([(W // 2 - width // 2, y), (W // 2 + width // 2, y + h)], fill=col)

def top_bar(draw, col=ORANGE): draw.rectangle([0, 0, W, 6], fill=col)
def bot_bar(draw, col=ORANGE): draw.rectangle([0, H - 6, W, H], fill=col)

def slide_no(draw, n, t):
    draw.text((W - PAD, H - 36), f"{n} / {t}", font=F(22, False), fill=GRAY_M, anchor="rm")

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

def add_grain(img, a=5):
    p = img.load()
    for _ in range(W * H // 35):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        d = random.randint(-a, a)
        p[x, y] = tuple(max(0, min(255, c + d)) for c in p[x, y])
    return img


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 생성 (v6 확정 코드 그대로)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def make_s1(out, img_paths, topic_line1, topic_line2, sub_line):
    """커버 — v6 확정 (수직 중앙, 뱃지 수직 중앙)"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = y / H
        d.line([(0, y), (W, y)], fill=(int(14 + v * 28), int(14 + v * 14), int(20 + v * 8)))
    top_bar(d); bot_bar(d)

    BADGE_H = 50; IMG_H = 230; TITLE1_H = 88; TITLE2_H = 88
    SUB1_H = 38; SUB2_H = 36
    G1=28; G2=36; G3=14; G4=8; G5=28
    total_h = BADGE_H+G1+IMG_H+G2+SUB1_H+G3+TITLE1_H+G4+TITLE2_H+G5+SUB2_H
    y = (H - total_h) // 2

    badge_cy = y + BADGE_H // 2
    badge(d, "쿠팡 추천  ·  비교 리뷰", W // 2, badge_cy, F(27), ORANGE, BG, pad_x=24, pad_y=6)
    y += BADGE_H + G1

    img_cy = y + IMG_H // 2
    positions = [(W//2, img_cy), (W//2-262, img_cy+16), (W//2+262, img_cy+16)]
    sizes     = [215, 188, 188]
    for i, (cx, cy_) in enumerate(positions):
        if i < len(img_paths) and img_paths[i]:
            paste_img(img, img_paths[i], cx, cy_, sizes[i])
    d = ImageDraw.Draw(img)

    rank_data = [
        (positions[0], sizes[0], "1위", ORANGE, BG),
        (positions[1], sizes[1], "2위", SILVER, BG),
        (positions[2], sizes[2], "3위", BRONZE, BG),
    ]
    for (cx, cy_), sz, label, bg_c, fg_c in rank_data:
        rc = cy_ - sz // 2
        d.ellipse([cx - 26, rc - 20, cx + 26, rc + 20], fill=bg_c)
        mm(d, label, cx, rc, F(22), fg_c if fg_c == BG else WHITE)
    y += IMG_H + G2

    ct(d, sub_line, y, F(28, False), GRAY_L); y += SUB1_H + G3
    ct(d, topic_line1, y, F(78), WHITE); y += TITLE1_H + G4
    ct(d, topic_line2, y, F(78), ORANGE); y += TITLE2_H + G5
    ct(d, "쿠팡 로켓배송  |  꿀통몬 추천", y, F(30, False), GRAY_L)

    mm(d, "꿀통몬 PICKS", W // 2, H - 32, F(26), ORANGE)
    slide_no(d, 1, 8)
    add_grain(img)
    path = out / "slide_01_cover.jpg"
    img.save(path, quality=96); print("OK s1")
    return path


def make_s2(out, items=None):
    """체크리스트 — v6 확정 (간격 163px, 헤더~카드 175px)"""
    CARD_H = 163; CARDS_TOP = 175
    if items is None:
        items = [
            ("성분 순도",  "크레아틴 모노하이드레이트 100% 단일 확인"),
            ("실제 함량",  "1회 제공량 중 순수 크레아틴 g수 확인"),
            ("1회 단가",   "총 중량 나누기 가격 직접 계산 필수"),
            ("제형 선택",  "분말(저렴·조절) vs 정제(휴대 간편)"),
            ("목적 구분",  "크레아틴 = 근력   /   아르기닌 = 펌핑"),
        ]

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W // 2, 30, F(26), ORANGE)
    ct(d, "사기 전 체크 5가지", 54, F(56), WHITE)
    ct(d, "이것만 알면 절대 후회 없다", 118, F(29, False), GRAY_L)
    divider(d, 155, width=120, h=3)

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
    img.save(path, quality=96); print("OK s2")
    return path


def make_product_slide(out, n,
                       rank_txt, rank_bg, rank_fg,
                       img_path, name1, name2, price, price_bg,
                       specs, tags, tag_col,
                       summary, sum_bg, stars, star_col,
                       warning=None):
    """제품 슬라이드 — v6 확정 (박스 수직중앙, 평가카드 3등분)"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d, rank_bg); bot_bar(d)

    HEADER_Y1, HEADER_Y2 = 6, 106
    d.rectangle([0, HEADER_Y1, W, HEADER_Y2], fill=rank_bg)
    mm(d, rank_txt, W // 2, (HEADER_Y1 + HEADER_Y2) // 2, F(46), rank_fg)

    IMG_SZ = 238; IMG_CX = 832; IMG_CY = 318
    if img_path:
        paste_img(img, img_path, IMG_CX, IMG_CY, IMG_SZ)
    d = ImageDraw.Draw(img)

    TEXT_MAX_W = IMG_CX - IMG_SZ // 2 - PAD - 20

    lm(d, name1, PAD, 155, F(54), WHITE,      max_w=TEXT_MAX_W)
    lm(d, name2, PAD, 215, F(32, False), GRAY_L, max_w=TEXT_MAX_W)
    badge_left(d, price, PAD, 272, F(38), price_bg,
               rank_fg if rank_fg == BG else WHITE, pad_x=20, pad_y=8, radius=26)

    sy = 322
    for spec in specs[:4]:
        cy_ = sy + 18
        d.ellipse([PAD, cy_ - 7, PAD + 14, cy_ + 7],
                  fill=rank_bg if rank_bg not in [BG, BG2, BG3] else ORANGE)
        lm(d, spec, PAD + 24, cy_, F(28, False), WHITE, max_w=TEXT_MAX_W - 10)
        sy += 50

    d.rectangle([PAD, 552, W - PAD, 555], fill=GRAY_D)

    tx = PAD; ty_tag_cy = 585
    for tag in tags:
        ft = F(24)
        tw_ = tw(ft, tag) + 26
        th_ = th(ft, tag) + 14
        ty1 = ty_tag_cy - th_ // 2; ty2 = ty_tag_cy + th_ // 2
        d.rounded_rectangle([tx, ty1, tx + tw_, ty2], radius=18, fill=GRAY_D)
        d.rectangle([tx, ty1, tx + 6, ty2], fill=tag_col)
        lm(d, tag, tx + 14, ty_tag_cy, ft, tag_col)
        tx += tw_ + 12

    EVAL_Y1 = 618
    if warning:
        EVAL_Y2 = 820
        d.rounded_rectangle([PAD, EVAL_Y1, W - PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD + 7, EVAL_Y2], fill=tag_col)
        row_h = (EVAL_Y2 - EVAL_Y1) // 3
        mm(d, summary, W // 2, EVAL_Y1 + row_h // 2,         F(32), WHITE,   max_w=W - PAD * 2 - 40)
        mm(d, warning, W // 2, EVAL_Y1 + row_h + row_h // 2,  F(25, False), GRAY_L, max_w=W - PAD * 2 - 40)
        mm(d, stars,   W // 2, EVAL_Y1 + row_h * 2 + row_h // 2, F(32), star_col, max_w=W - PAD * 2 - 40)
    else:
        EVAL_Y2 = 800
        d.rounded_rectangle([PAD, EVAL_Y1, W - PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD + 7, EVAL_Y2], fill=tag_col)
        row_h = (EVAL_Y2 - EVAL_Y1) // 2
        mm(d, summary, W // 2, EVAL_Y1 + row_h // 2,          F(34), WHITE,   max_w=W - PAD * 2 - 40)
        mm(d, stars,   W // 2, EVAL_Y1 + row_h + row_h // 2,   F(34), star_col, max_w=W - PAD * 2 - 40)

    link_y = EVAL_Y2 + 20 if EVAL_Y2 < H - 80 else H - 66
    mm(d, "쿠팡 로켓배송  /  링크는 프로필 참고", W // 2, link_y, F(24, False), GRAY_M)

    slide_no(d, n, 8)
    add_grain(img)
    path = out / f"slide_{n:02d}_product.jpg"
    img.save(path, quality=96); print(f"OK s{n}")
    return path


def make_s6(out, products):
    """비교표 — v6 확정 (익스트림듀얼 포함, 정확한 데이터)"""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W // 2, 30, F(26), ORANGE)
    ct(d, "한눈에 비교", 54, F(60), WHITE)
    divider(d, 128, width=130, h=4)

    CX = [68, 305, 558, 810]
    CW = [228, 244, 244, 240]
    ROW_TOP = 144; ROW_H = 86

    # 헤더 — 제품명 동적 (최대 6자)
    p_names = [p.get("name_short", p.get("productName", "?")[:8]) for p in products[:3]]
    hdrs  = ["항목"] + p_names
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROW_TOP, W - PAD, ROW_TOP + ROW_H], fill=(18, 18, 28))
    for cx, cw, hdr, hcol in zip(CX, CW, hdrs, hcols):
        lm(d, hdr, cx, ROW_TOP + ROW_H // 2, shrink(F(25), hdr, cw - 8), hcol)

    # 행 데이터 — 제품 정보에서 자동 추출
    def pval(p, key, default="-"):
        return str(p.get(key, default)) if p.get(key) else default

    rows = [
        ("가격",      ) + tuple(p.get("price_str", f"{int(float(p.get('productPrice',0))):,}원") for p in products[:3]),
        ("주요 성분", ) + tuple(pval(p, "ingredient", "확인 필요") for p in products[:3]),
        ("제형",      ) + tuple(pval(p, "form", "분말") for p in products[:3]),
        ("용량",      ) + tuple(pval(p, "volume", "-") for p in products[:3]),
        ("1회 단가",  ) + tuple(pval(p, "unit_price", "-") for p in products[:3]),
        ("인증",      ) + tuple(pval(p, "cert", "-") for p in products[:3]),
        ("추천",      ) + tuple(pval(p, "target", "-") for p in products[:3]),
    ]
    vcols = [GRAY_L, ORANGE, SILVER, BRONZE]

    y = ROW_TOP + ROW_H
    for ri, row in enumerate(rows):
        bg_ = BG2 if ri % 2 == 0 else BG3
        row_y2 = y + ROW_H - 2
        d.rectangle([PAD, y, W - PAD, row_y2], fill=bg_)
        d.rectangle([CX[1] - 8, y, CX[1] + CW[1] - 6, row_y2], fill=(28, 16, 4))
        for ci, (val, vc) in enumerate(zip(row, vcols)):
            fv = shrink(F(23 if ci == 0 else 21, bold=(ci == 0)), str(val), CW[ci] - 12)
            lm(d, str(val), CX[ci], y + ROW_H // 2, fv, vc)
        y += ROW_H

    sum_y1 = y + 10; sum_y2 = y + 78
    d.rounded_rectangle([PAD, sum_y1, W - PAD, sum_y2], radius=12, fill=(32, 18, 4))
    d.rectangle([PAD, sum_y1, PAD + 6, sum_y2], fill=ORANGE)
    rank_txt = "  >  ".join(p.get("name_short", "?") for p in products[:3])
    mm(d, f"추천 순위 :  {rank_txt}", W // 2, sum_y1 + (sum_y2 - sum_y1) // 2,
       F(24), WHITE, max_w=W - PAD * 2 - 30)

    slide_no(d, 6, 8)
    add_grain(img, 5)
    path = out / "slide_06_compare.jpg"
    img.save(path, quality=96); print("OK s6")
    return path


def make_s7(out, line1="비싸다고", line2="좋은 건 아닙니다"):
    """핵심 메시지 — v6 확정 (밑줄 없음, 수직 중앙)"""
    img = Image.new("RGB", (W, H), (10, 6, 2))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 90): d.line([(x, 0), (x, H)], fill=(18, 12, 5), width=1)
    for y in range(0, H, 90): d.line([(0, y), (W, y)], fill=(18, 12, 5), width=1)
    top_bar(d); bot_bar(d)

    d.text((38, -62), '"', font=F(280), fill=(38, 24, 6))

    f1 = F(74); f2 = F(70); f_sub = F(36, False); f_cap = F(28, False)
    h1 = th(f1, line1); h2 = th(f2, line2)
    h_sub = th(f_sub); h_cap = th(f_cap)
    total_h = h1 + 20 + h2 + 32 + 4 + 24 + h_sub + 16 + h_cap
    y = (H - total_h) // 2

    ct(d, line1, y, f1, WHITE); y += h1 + 20
    ct(d, line2, y, f2, ORANGE); y += h2 + 32

    divider(d, y, width=180, h=4); y += 4 + 24
    ct(d, "목적에 맞는 제품이 진짜 가성비", y, f_sub, GRAY_L); y += h_sub + 16
    ct(d, "블로그 전문 비교 리뷰 기반", y, f_cap, GRAY_M)

    slide_no(d, 7, 8)
    add_grain(img, 5)
    path = out / "slide_07_quote.jpg"
    img.save(path, quality=96); print("OK s7")
    return path


def make_s8(out, account="@ggultongmon"):
    """CTA — v6 확정 (텍스트 간격 확대, badge 수직중앙)"""
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

    ic_cx, ic_top, ic_h = W // 2, 160, 80
    d.rectangle([ic_cx - 36, ic_top, ic_cx + 36, ic_top + ic_h], fill=ORANGE)
    d.polygon([(ic_cx - 36, ic_top + ic_h), (ic_cx + 36, ic_top + ic_h),
               (ic_cx, ic_top + ic_h + 38)], fill=ORANGE)

    GAP_L, GAP_M = 28, 20
    f_main, f_sub_, f_note, f_hash = F(76), F(68), F(34, False), F(27, False)
    y = ic_top + ic_h + 38 + GAP_L

    h_ = ct(d, "저장해두고",     y, f_main, WHITE);  y += h_ + GAP_L
    h_ = ct(d, "쿠팡에서 확인하세요", y, f_sub_, ORANGE); y += h_ + GAP_M + 10
    h_ = ct(d, "링크는 프로필에 있어요", y, f_note, GRAY_L);  y += h_ + GAP_M + 6

    BTN_H = 74; btn_w = 490; btn_x = (W - btn_w) // 2
    d.rounded_rectangle([btn_x, y, btn_x + btn_w, y + BTN_H], radius=37, fill=ORANGE)
    mm(d, f"팔로우  {account}", W // 2, y + BTN_H // 2, F(36), BG)
    y += BTN_H + GAP_M + 6

    ct(d, "#쿠팡추천  #가성비  #꿀통몬", y, f_hash, GRAY_M)
    slide_no(d, 8, 8)
    add_grain(img, 5)
    path = out / "slide_08_cta.jpg"
    img.save(path, quality=96); print("OK s8")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이미지 다운로드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fetch_product_images(post_url: str, out: Path, count: int = 3) -> list:
    paths = []
    try:
        req = urllib.request.Request(post_url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        imgs = re.findall(r'src=["\']([^"\']+coupangcdn[^"\']+)["\']', html)
        seen = set(); unique = []
        for img in imgs:
            base = img.split("?")[0]
            if base not in seen:
                seen.add(base); unique.append(img)
        print(f"[carousel] 이미지 URL {len(unique)}개 발견")

        for i, url in enumerate(unique[:count]):
            dest = out / f"_prod{i+1}.jpg"
            try:
                req2 = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0", "Referer": "https://www.coupang.com"})
                data = urllib.request.urlopen(req2, timeout=12).read()
                dest.write_bytes(data)
                print(f"[carousel] prod{i+1}: {len(data)//1024}KB")
                paths.append(dest)
            except Exception as e:
                print(f"[carousel] prod{i+1} 실패: {e}")
                paths.append(None)
    except Exception as e:
        print(f"[carousel] HTML 수집 실패: {e}")

    while len(paths) < count:
        paths.append(None)
    return paths


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 제품 정보 구성 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_product_info(products: list) -> list:
    """
    raw products 리스트 → 슬라이드용 dict 변환
    없는 필드는 기본값으로 채움
    """
    defaults = [
        {  # 1위
            "name1": "1위 추천 상품",
            "name2": "쿠팡 인기 상품",
            "name_short": "1위 상품",
            "price_str": "-",
            "ingredient": "확인 필요",
            "form": "분말",
            "volume": "-",
            "unit_price": "-",
            "cert": "-",
            "target": "입문자",
            "specs": ["쿠팡 로켓배송", "상세 정보 블로그 참고"],
            "tags": ["1위", "입문자", "추천"],
            "summary": "1순위 추천",
            "stars": "★★★★★",
        },
        {  # 2위
            "name1": "2위 추천 상품",
            "name2": "쿠팡 인기 상품",
            "name_short": "2위 상품",
            "price_str": "-",
            "ingredient": "확인 필요",
            "form": "분말",
            "volume": "-",
            "unit_price": "-",
            "cert": "-",
            "target": "국산 선호",
            "specs": ["쿠팡 로켓배송", "상세 정보 블로그 참고"],
            "tags": ["2위", "안정적", "추천"],
            "summary": "안정적인 2위",
            "stars": "★★★★☆",
            "warning": "장기 복용 시 단가 비교 권장",
        },
        {  # 3위
            "name1": "3위 추천 상품",
            "name2": "쿠팡 인기 상품",
            "name_short": "3위 상품",
            "price_str": "-",
            "ingredient": "확인 필요",
            "form": "정제",
            "volume": "-",
            "unit_price": "-",
            "cert": "-",
            "target": "중급자",
            "specs": ["쿠팡 로켓배송", "상세 정보 블로그 참고"],
            "tags": ["3위", "중급자", "특수 목적"],
            "summary": "중급자 이상 추천",
            "stars": "★★★☆☆",
            "warning": "입문자 비권장 — 기본 상품 먼저",
        },
    ]

    result = []
    for i, raw in enumerate(products[:3]):
        d = dict(defaults[i])  # 기본값
        name = raw.get("productName", d["name1"])
        price = int(float(raw.get("productPrice", 0)))
        d.update({
            "name1": name[:22],
            "name2": raw.get("productName", "")[:30],
            "name_short": name[:10],
            "price_str": f"{price:,}원" if price else d["price_str"],
            "productPrice": price,
        })
        result.append(d)
    return result


RANK_CONFIGS = [
    {"rank_txt": "1위  추천", "rank_bg": ORANGE,      "rank_fg": BG,
     "price_bg": ORANGE,      "tag_col": ORANGE,
     "sum_bg": (36,20,4),     "star_col": ORANGE},
    {"rank_txt": "2위",       "rank_bg": (88,88,124), "rank_fg": WHITE,
     "price_bg": (88,88,130), "tag_col": SILVER,
     "sum_bg": (22,22,42),    "star_col": SILVER},
    {"rank_txt": "3위  (중급자용)", "rank_bg": (72,48,10), "rank_fg": CREAM,
     "price_bg": (68,44,8),   "tag_col": BRONZE,
     "sum_bg": (22,14,4),     "star_col": BRONZE},
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 생성 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_carousel(
    post_url: str,
    topic: str,
    products: list,
    out_dir: str = None,
) -> dict:
    """
    카드뉴스 8장 자동 생성 (v6 확정 포맷)

    Returns:
        {"slides": [Path,...], "out_dir": Path, "topic": str, "post_url": str}
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(out_dir) if out_dir else Path(f"/tmp/carousel_out/{ts}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"[carousel] 출력: {out}")

    # 상품 정보 구성
    prods = build_product_info(products)

    # 상품 이미지 다운로드
    print("[carousel] 상품 이미지 다운로드...")
    img_paths = fetch_product_images(post_url, out, count=3)

    # 주제 → 커버 2줄 분리
    words = topic.split()
    mid = max(1, len(words) // 2)
    tl1 = " ".join(words[:mid])
    tl2 = " ".join(words[mid:]) if len(words) > mid else "완전 비교"
    sub = f"2026 최신  |  {len(prods)}종 직접 비교"

    # 슬라이드 생성
    slides = []
    print("[carousel] 슬라이드 생성...")

    slides.append(make_s1(out, img_paths, tl1, tl2, sub))
    slides.append(make_s2(out))

    for i, (prod, cfg) in enumerate(zip(prods, RANK_CONFIGS)):
        slides.append(make_product_slide(
            out, n=3 + i,
            rank_txt=cfg["rank_txt"], rank_bg=cfg["rank_bg"], rank_fg=cfg["rank_fg"],
            img_path=img_paths[i] if i < len(img_paths) else None,
            name1=prod["name1"], name2=prod["name2"],
            price=prod["price_str"], price_bg=cfg["price_bg"],
            specs=prod.get("specs", []),
            tags=prod.get("tags", []), tag_col=cfg["tag_col"],
            summary=prod.get("summary", "추천"), sum_bg=cfg["sum_bg"],
            stars=prod.get("stars", "★★★☆☆"), star_col=cfg["star_col"],
            warning=prod.get("warning"),
        ))

    slides.append(make_s6(out, prods))
    slides.append(make_s7(out))
    slides.append(make_s8(out))

    print(f"[carousel] 완료! {len(slides)}장")
    return {"slides": slides, "out_dir": out, "topic": topic, "post_url": post_url}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",      required=True)
    parser.add_argument("--topic",    required=True)
    parser.add_argument("--products", default="[]")
    parser.add_argument("--out_dir",  default=None)
    args = parser.parse_args()

    result = generate_carousel(
        post_url=args.url,
        topic=args.topic,
        products=json.loads(args.products),
        out_dir=args.out_dir,
    )
    print(f"\n출력: {result['out_dir']}")
