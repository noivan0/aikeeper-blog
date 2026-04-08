"""
ggultongmon 카드뉴스 자동 생성기 v3 (v7 포맷 확정)
=========================================
변경 이력:
  v1: 초기 구현
  v2: v6 확정 포맷 반영 (박스 수직중앙, 그리드 시스템)
  v3: v7 확정 포맷 반영
      - 제품 슬라이드(3/4/5): 특징 키워드 불릿 + 하단 박스(요약/주의/별점 3등분)
      - 비교표(6): 포스트 원문 데이터 정확 반영, 동적 컬럼 헤더
      - generate_carousel() 인자에 keywords/box_lines 지원 추가

사용법 (import):
  from instagram.carousel_auto import generate_carousel
  result = generate_carousel(post_url, topic, products)

사용법 (CLI):
  python3 carousel_auto.py \
    --url "https://ggultongmon.allsweep.xyz/..." \
    --topic "크레아틴 비교" \
    --products '[{"productName":"...","productPrice":"19500",...}]'

products 항목 지원 필드:
  productName, productPrice, name1(표시명1), name2(표시명2), name_short(6자이내)
  ingredient, form, volume, unit_price, cert, target
  keywords(불릿 4개), tags(태그 3개), box_title, box_lines(2개), stars
"""

import os, sys, re, json, argparse, urllib.request, random
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── 경로 ──────────────────────────────────────────────────────
BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
REG_PATH  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H = 1080, 1080
PAD  = 60

# ── 컬러 (v6/v7 확정) ─────────────────────────────────────────
BG      = (14,  14,  20)
BG2     = (24,  24,  34)
BG3     = (34,  34,  48)
WHITE   = (255, 255, 255)
CREAM   = (255, 245, 225)
ORANGE  = (255, 135, 20)
GRAY_L  = (160, 160, 180)
GRAY_M  = (90,  90,  110)
GRAY_D  = (40,  40,  56)
SILVER  = (185, 185, 210)
BRONZE  = (170, 120, 45)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 폰트 / 텍스트 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    """완전 중앙 — getbbox 시각적 중앙"""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text); b = f.getbbox(text)
    vis_cy = (b[1] + b[3]) / 2
    draw.text((cx - w_ // 2, cy - int(vis_cy)), text, font=f, fill=color)

def lm(draw, text, x, cy, f, color, max_w=None):
    """좌측정렬, 수직중앙"""
    if max_w: f = shrink(f, text, max_w)
    b = f.getbbox(text); vis_cy = (b[1] + b[3]) / 2
    draw.text((x, cy - int(vis_cy)), text, font=f, fill=color)

def ct(draw, text, y_top, f, color, max_w=W - PAD * 2):
    """상단y 기준 중앙정렬. 반환: 시각 높이"""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text); b = f.getbbox(text)
    draw.text(((W - w_) // 2, y_top - b[1]), text, font=f, fill=color)
    return b[3] - b[1]

def badge(draw, text, cx, cy, f, bg_col, fg_col, pad_x=22, pad_y=0, radius=26):
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10; bw = w_ + pad_x * 2
    x1 = cx - bw // 2; x2 = cx + bw // 2
    y1 = cy - bh // 2; y2 = cy + bh // 2
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_col)
    mm(draw, text, cx, cy, f, fg_col)

def badge_left(draw, text, x, cy, f, bg_col, fg_col, pad_x=18, pad_y=0, radius=24):
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10; bw = w_ + pad_x * 2
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
        print(f"[carousel] 이미지 실패: {e}")
        d = ImageDraw.Draw(img)
        x_, y_ = cx - size // 2, cy - size // 2
        d.rounded_rectangle([x_, y_, x_ + size, y_ + size], radius=24, fill=GRAY_D)
        d.text((cx, cy), "IMG", font=F(28), fill=GRAY_M, anchor="mm")

def add_grain(img, a=5):
    p = img.load()
    for _ in range(W * H // 35):
        x, y = random.randint(0, W - 1), random.randint(0, H - 1)
        dv = random.randint(-a, a)
        p[x, y] = tuple(max(0, min(255, c + dv)) for c in p[x, y])
    return img


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이미지 다운로드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 1 — 커버 (v6 확정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_s1(out, img_paths, topic_line1, topic_line2, sub_line):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = y / H
        d.line([(0, y), (W, y)], fill=(int(14 + v * 28), int(14 + v * 14), int(20 + v * 8)))
    top_bar(d); bot_bar(d)

    BADGE_H=50; IMG_H=230; TITLE1_H=88; TITLE2_H=88; SUB1_H=38; SUB2_H=36
    G1=28; G2=36; G3=14; G4=8; G5=28
    total_h = BADGE_H+G1+IMG_H+G2+SUB1_H+G3+TITLE1_H+G4+TITLE2_H+G5+SUB2_H
    y = (H - total_h) // 2

    badge(d, "쿠팡 추천  ·  비교 리뷰", W // 2, y + BADGE_H // 2, F(27), ORANGE, BG, pad_x=24, pad_y=6)
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
    ct(d, topic_line1, y, F(78), WHITE);       y += TITLE1_H + G4
    ct(d, topic_line2, y, F(78), ORANGE);      y += TITLE2_H + G5
    ct(d, "쿠팡 로켓배송  |  꿀통몬 추천", y, F(30, False), GRAY_L)

    mm(d, "꿀통몬 PICKS", W // 2, H - 32, F(26), ORANGE)
    slide_no(d, 1, 8)
    add_grain(img)
    path = out / "slide_01_cover.jpg"
    img.save(path, quality=96); print("OK s1")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 2 — 체크리스트 (v6 확정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_s2(out, items=None):
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
        text_x = PAD + 98; avail_w = W - PAD - text_x - 14
        lm(d, main, text_x, y + (CARD_H - 5) * 37 // 100, F(36), WHITE,      max_w=avail_w)
        lm(d, sub,  text_x, y + (CARD_H - 5) * 67 // 100, F(25, False), GRAY_L, max_w=avail_w)
        y += CARD_H

    slide_no(d, 2, 8); add_grain(img, 5)
    path = out / "slide_02_checklist.jpg"
    img.save(path, quality=96); print("OK s2")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 3/4/5 — 제품 슬라이드 (v7 확정)
#
# [레이아웃]
#  헤더띠    y=6~106   : 순위
#  좌측      y=106~555 : 제품명 + 가격 + 특징 키워드 4개
#  우상단              : 상품 이미지
#  구분선    y=552~555
#  태그행    y=562~615 : 태그 3개
#  하단박스  y=618~855 : box_title / box_line1 / box_line2 / 별점 (4등분)
#  링크      y=박스+20
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_product_slide(out, n,
                       rank_txt, rank_bg, rank_fg,
                       img_path,
                       name1, name2, price, price_bg,
                       keywords,        # list[str] 특징 키워드 4개
                       tags, tag_col,
                       box_title,       # 하단 박스 제목
                       box_lines,       # list[str] 설명 1~2줄
                       stars, star_col,
                       sum_bg):

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d, rank_bg); bot_bar(d)

    # 헤더 띠
    d.rectangle([0, 6, W, 106], fill=rank_bg)
    mm(d, rank_txt, W // 2, 56, F(46), rank_fg)

    # 상품 이미지
    IMG_SZ = 238; IMG_CX = 832; IMG_CY = 318
    if img_path:
        paste_img(img, img_path, IMG_CX, IMG_CY, IMG_SZ)
    d = ImageDraw.Draw(img)
    TEXT_MAX_W = IMG_CX - IMG_SZ // 2 - PAD - 20  # ~630px

    # 제품명 + 가격
    lm(d, name1, PAD, 155, F(54), WHITE,          max_w=TEXT_MAX_W)
    lm(d, name2, PAD, 215, F(30, False), GRAY_L,  max_w=TEXT_MAX_W)
    badge_left(d, price, PAD, 272, F(38), price_bg,
               rank_fg if rank_fg == BG else WHITE, pad_x=20, pad_y=8, radius=26)

    # 특징 키워드 불릿 4개
    sy = 322
    for kw in keywords[:4]:
        cy_ = sy + 18
        dot_col = rank_bg if rank_bg not in [BG, BG2, BG3] else ORANGE
        d.ellipse([PAD, cy_ - 7, PAD + 14, cy_ + 7], fill=dot_col)
        lm(d, kw, PAD + 24, cy_, F(28, False), WHITE, max_w=TEXT_MAX_W - 10)
        sy += 50

    # 구분선
    d.rectangle([PAD, 552, W - PAD, 555], fill=GRAY_D)

    # 태그 행
    tx = PAD; ty_tag = 585
    for tag in tags:
        ft = F(24)
        tw_ = tw(ft, tag) + 26; th_ = th(ft, tag) + 14
        ty1 = ty_tag - th_ // 2; ty2 = ty_tag + th_ // 2
        d.rounded_rectangle([tx, ty1, tx + tw_, ty2], radius=18, fill=GRAY_D)
        d.rectangle([tx, ty1, tx + 6, ty2], fill=tag_col)
        lm(d, tag, tx + 14, ty_tag, ft, tag_col)
        tx += tw_ + 12

    # 하단 큰 박스 — box_title + box_lines(1~2줄) + 별점
    EVAL_Y1 = 618
    n_lines = len(box_lines[:2])
    ROW_COUNT = 1 + n_lines + 1       # 제목 + 설명 + 별점
    EVAL_Y2 = min(EVAL_Y1 + ROW_COUNT * 58 + 24, 860)
    d.rounded_rectangle([PAD, EVAL_Y1, W - PAD, EVAL_Y2], radius=16, fill=sum_bg)
    d.rectangle([PAD, EVAL_Y1, PAD + 7, EVAL_Y2], fill=tag_col)

    row_h = (EVAL_Y2 - EVAL_Y1) // ROW_COUNT
    ey = EVAL_Y1 + row_h // 2
    mm(d, box_title,       W // 2, ey, F(32),        WHITE,   max_w=W - PAD * 2 - 40); ey += row_h
    for bl in box_lines[:2]:
        mm(d, bl,          W // 2, ey, F(26, False),  GRAY_L,  max_w=W - PAD * 2 - 40); ey += row_h
    mm(d, stars,           W // 2, ey, F(32),         star_col, max_w=W - PAD * 2 - 40)

    link_y = EVAL_Y2 + 18 if EVAL_Y2 < H - 75 else H - 62
    mm(d, "쿠팡 로켓배송  /  링크는 프로필 참고", W // 2, link_y, F(24, False), GRAY_M)

    slide_no(d, n, 8); add_grain(img)
    path = out / f"slide_{n:02d}_product.jpg"
    img.save(path, quality=96); print(f"OK s{n}")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 6 — 비교표 (v7 확정: 포스트 원문 기반)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_s6(out, products):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W // 2, 30, F(26), ORANGE)
    ct(d, "한눈에 비교", 54, F(60), WHITE)
    divider(d, 128, width=130, h=4)

    CX = [68, 305, 558, 810]
    CW = [228, 244, 244, 240]
    ROW_TOP = 144; ROW_H = 86

    # 헤더 — 제품 name_short 동적 적용
    def get_short(p):
        return str(p.get("name_short", p.get("productName", "상품")[:8]))

    hdrs  = ["항목"] + [get_short(p) for p in products[:3]]
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROW_TOP, W - PAD, ROW_TOP + ROW_H], fill=(18, 18, 28))
    for cx, cw, hdr, hcol in zip(CX, CW, hdrs, hcols):
        f_ = shrink(F(25), hdr, cw - 8)
        b_ = f_.getbbox(hdr); vis_cy = (b_[1] + b_[3]) / 2
        d.text((cx, ROW_TOP + ROW_H // 2 - int(vis_cy)), hdr, font=f_, fill=hcol)

    def pv(p, key, default="-"):
        v = p.get(key)
        return str(v) if v else default

    def price_str(p):
        v = p.get("price_str")
        if v: return v
        try: return f"{int(float(p.get('productPrice', 0))):,}원"
        except: return "-"

    rows = [
        ("가격",)      + tuple(price_str(p) for p in products[:3]),
        ("주요 성분",) + tuple(pv(p, "ingredient", "확인 필요") for p in products[:3]),
        ("제형",)      + tuple(pv(p, "form", "분말") for p in products[:3]),
        ("용량",)      + tuple(pv(p, "volume", "-") for p in products[:3]),
        ("1회 단가",)  + tuple(pv(p, "unit_price", "-") for p in products[:3]),
        ("인증",)      + tuple(pv(p, "cert", "-") for p in products[:3]),
        ("추천 대상",) + tuple(pv(p, "target", "-") for p in products[:3]),
    ]
    vcols = [GRAY_L, ORANGE, SILVER, BRONZE]

    y = ROW_TOP + ROW_H
    for ri, row in enumerate(rows):
        bg_ = BG2 if ri % 2 == 0 else BG3
        row_y2 = y + ROW_H - 2
        d.rectangle([PAD, y, W - PAD, row_y2], fill=bg_)
        # 1위 컬럼 강조 배경
        d.rectangle([CX[1] - 8, y, CX[1] + CW[1] - 6, row_y2], fill=(28, 16, 4))
        for ci, (val, vc) in enumerate(zip(row, vcols)):
            fv = shrink(F(23 if ci == 0 else 20, bold=(ci == 0)), str(val), CW[ci] - 12)
            b_ = fv.getbbox(str(val)); vis_cy = (b_[1] + b_[3]) / 2
            d.text((CX[ci], y + ROW_H // 2 - int(vis_cy)), str(val), font=fv, fill=vc)
        y += ROW_H

    # 추천 순위 요약
    sum_y1 = y + 10; sum_y2 = y + 78
    d.rounded_rectangle([PAD, sum_y1, W - PAD, sum_y2], radius=12, fill=(32, 18, 4))
    d.rectangle([PAD, sum_y1, PAD + 6, sum_y2], fill=ORANGE)
    rank_names = "  >  ".join(get_short(p) for p in products[:3])
    txt_ = f"추천 순위 :  {rank_names}"
    f_ = shrink(F(24), txt_, W - PAD * 2 - 30)
    b_ = f_.getbbox(txt_); vis_cy = (b_[1] + b_[3]) / 2; w_ = tw(f_, txt_)
    d.text(((W - w_) // 2, sum_y1 + (sum_y2 - sum_y1) // 2 - int(vis_cy)),
           txt_, font=f_, fill=WHITE)

    slide_no(d, 6, 8); add_grain(img, 5)
    path = out / "slide_06_compare.jpg"
    img.save(path, quality=96); print("OK s6")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 7 — 핵심 메시지 (v6 확정: 밑줄 없음)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_s7(out, line1="비싸다고", line2="좋은 건 아닙니다"):
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

    slide_no(d, 7, 8); add_grain(img, 5)
    path = out / "slide_07_quote.jpg"
    img.save(path, quality=96); print("OK s7")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 슬라이드 8 — CTA (v6 확정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_s8(out, account="@ggultongmon"):
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

    h_ = ct(d, "저장해두고",          y, f_main, WHITE);  y += h_ + GAP_L
    h_ = ct(d, "쿠팡에서 확인하세요", y, f_sub_, ORANGE); y += h_ + GAP_M + 10
    h_ = ct(d, "링크는 프로필에 있어요", y, f_note, GRAY_L); y += h_ + GAP_M + 6

    BTN_H = 74; btn_w = 490; btn_x = (W - btn_w) // 2
    d.rounded_rectangle([btn_x, y, btn_x + btn_w, y + BTN_H], radius=37, fill=ORANGE)
    mm(d, f"팔로우  {account}", W // 2, y + BTN_H // 2, F(36), BG)
    y += BTN_H + GAP_M + 6

    ct(d, "#쿠팡추천  #가성비  #꿀통몬", y, f_hash, GRAY_M)
    slide_no(d, 8, 8); add_grain(img, 5)
    path = out / "slide_08_cta.jpg"
    img.save(path, quality=96); print("OK s8")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 제품 정보 빌더 (v7 확정 기본값)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFAULTS = [
    {   # 1위
        "name1": "1위 추천 상품", "name2": "쿠팡 베스트",
        "name_short": "1위 상품",
        "ingredient": "주성분 100%", "form": "분말",
        "volume": "대용량",         "unit_price": "최저가",
        "cert": "글로벌 인증",       "target": "입문자 1순위",
        "keywords": [
            "주성분 100% 단일 구성",
            "대용량 — 장기 복용 최적",
            "1회 단가 최저 수준",
            "글로벌 인증 시설 생산",
        ],
        "tags": ["1위", "입문자", "장기 복용"],
        "box_title": "입문자 1순위 추천",
        "box_lines": ["상세 스펙은 블로그 참고"],
        "stars": "★★★★★",
        "sum_bg": (36, 20, 4),
    },
    {   # 2위
        "name1": "2위 추천 상품", "name2": "쿠팡 인기",
        "name_short": "2위 상품",
        "ingredient": "주성분 100%", "form": "분말",
        "volume": "소용량",          "unit_price": "단가 확인",
        "cert": "국내 인증",          "target": "국산 선호",
        "keywords": [
            "국내 인증 제품",
            "단일 성분 구성",
            "찬물 용해 우수",
            "국내 A/S 편리",
        ],
        "tags": ["2위", "국산 선호", "입문자"],
        "box_title": "국산 선호라면 최선택",
        "box_lines": ["장기 복용 시 대용량 단가 비교 권장"],
        "stars": "★★★★☆",
        "sum_bg": (22, 22, 42),
    },
    {   # 3위
        "name1": "3위 추천 상품", "name2": "쿠팡 인기",
        "name_short": "3위 상품",
        "ingredient": "복합 성분",  "form": "정제",
        "volume": "포뮬러",          "unit_price": "비교 불가",
        "cert": "국내 기준",          "target": "중급자 추가",
        "keywords": [
            "고함량 복합 성분",
            "정제형 — 휴대 간편",
            "운동 전 30~60분 복용",
            "기본 보충제와 병행 가능",
        ],
        "tags": ["3위", "중급자", "정제형"],
        "box_title": "중급자 이상 추천",
        "box_lines": ["입문자 비권장 — 기본 보충제 먼저"],
        "stars": "★★★☆☆",
        "sum_bg": (22, 14, 4),
    },
]

RANK_CONFIGS = [
    {"rank_txt": "1위  추천",       "rank_bg": ORANGE,      "rank_fg": BG,
     "price_bg": ORANGE,            "tag_col": ORANGE,      "star_col": ORANGE},
    {"rank_txt": "2위",             "rank_bg": (88,88,124), "rank_fg": WHITE,
     "price_bg": (88,88,130),       "tag_col": SILVER,      "star_col": SILVER},
    {"rank_txt": "3위  (중급자용)", "rank_bg": (72,48,10),  "rank_fg": CREAM,
     "price_bg": (68,44,8),         "tag_col": BRONZE,      "star_col": BRONZE},
]


def split_title(topic: str, max_w: int = W - 100) -> tuple:
    """
    주제 문자열을 커버 2줄로 분리.
    Claude API로 한국어 문법에 맞는 자연스러운 줄바꿈 위치를 결정.
    API 실패 시 단어 절반으로 폴백.
    """
    words = topic.split()
    if len(words) <= 1:
        return topic, "완전 비교"

    # Claude API로 문법적 줄바꿈 판단
    try:
        import urllib.request, urllib.parse, json as _json, os as _os
        api_key    = _os.environ.get("ANTHROPIC_API_KEY", "")
        api_base   = _os.environ.get("ANTHROPIC_BASE_URL",
                                     "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude")
        model      = _os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        prompt = (
            f"아래 한국어 제목을 인스타그램 카드뉴스용 2줄로 나눠주세요.\n"
            f"규칙:\n"
            f"- 한국어 문법과 의미 단위에 맞게 자연스럽게\n"
            f"- 조사나 어미가 다음 줄 첫 단어가 되지 않도록\n"
            f"- 두 줄 길이가 최대한 비슷하게\n"
            f"- JSON으로만 응답: {{\"line1\": \"...\", \"line2\": \"...\"}}\n\n"
            f"제목: {topic}"
        )
        payload = _json.dumps({
            "model": model,
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            f"{api_base}/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        resp = urllib.request.urlopen(req, timeout=10).read()
        data = _json.loads(resp)
        text = data["content"][0]["text"].strip()
        # JSON 추출
        import re as _re
        m = _re.search(r'\{.*?\}', text, _re.DOTALL)
        if m:
            result = _json.loads(m.group())
            l1 = result.get("line1", "").strip()
            l2 = result.get("line2", "").strip()
            if l1 and l2:
                print(f"[split_title] Claude: [{l1}] / [{l2}]")
                return l1, l2
    except Exception as e:
        print(f"[split_title] Claude 실패, 폴백: {e}")

    # 폴백: 단어 절반으로 분리
    mid = max(1, len(words) // 2)
    return " ".join(words[:mid]), " ".join(words[mid:])


def build_products(raw_list: list) -> list:
    """raw products → 슬라이드용 dict (없는 필드는 DEFAULTS로 채움)"""
    result = []
    for i, raw in enumerate(raw_list[:3]):
        d = dict(DEFAULTS[i])
        name = raw.get("productName", d["name1"])
        try:   price = int(float(raw.get("productPrice", 0)))
        except: price = 0
        d.update({
            "name1":       raw.get("name1", name[:22]),
            "name2":       raw.get("name2", name[:30]),
            "name_short":  raw.get("name_short", name[:8]),
            "price_str":   raw.get("price_str",
                                   f"{price:,}원" if price else d.get("unit_price", "-")),
        })
        # 원문 제공 필드 우선 적용
        for k in ["ingredient","form","volume","unit_price","cert","target",
                  "keywords","tags","box_title","box_lines","stars","sum_bg"]:
            if k in raw:
                d[k] = raw[k]
        result.append(d)
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 생성 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_carousel(
    post_url: str,
    topic: str,
    products: list,
    out_dir: str = None,
) -> dict:
    """
    카드뉴스 8장 자동 생성 (v7 확정 포맷)

    Returns:
        {"slides": [Path,...], "out_dir": Path, "topic": str, "post_url": str}
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(out_dir) if out_dir else Path(f"/tmp/carousel_out/{ts}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"[carousel] 출력: {out}")

    prods = build_products(products)
    print("[carousel] 상품 이미지 다운로드...")
    img_paths = fetch_product_images(post_url, out, count=3)

    # 주제 → 커버 2줄 (폰트 너비 기준 자동 분리)
    tl1, tl2 = split_title(topic)
    sub = f"2026 최신  |  {len(prods)}종 직접 비교"

    print("[carousel] 슬라이드 생성...")
    slides = []
    slides.append(make_s1(out, img_paths, tl1, tl2, sub))
    slides.append(make_s2(out))

    for i, (prod, cfg) in enumerate(zip(prods, RANK_CONFIGS)):
        slides.append(make_product_slide(
            out, n=3 + i,
            rank_txt=cfg["rank_txt"],
            rank_bg=cfg["rank_bg"], rank_fg=cfg["rank_fg"],
            img_path=img_paths[i] if i < len(img_paths) else None,
            name1=prod["name1"],   name2=prod["name2"],
            price=prod["price_str"], price_bg=cfg["price_bg"],
            keywords=prod.get("keywords", []),
            tags=prod.get("tags", []), tag_col=cfg["tag_col"],
            box_title=prod.get("box_title", ""),
            box_lines=prod.get("box_lines", []),
            stars=prod.get("stars", "★★★☆☆"),
            star_col=cfg["star_col"],
            sum_bg=prod.get("sum_bg", (22, 22, 42)),
        ))

    slides.append(make_s6(out, prods))
    slides.append(make_s7(out))
    slides.append(make_s8(out))

    print(f"[carousel] 완료! {len(slides)}장")
    return {"slides": slides, "out_dir": out, "topic": topic, "post_url": post_url}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
