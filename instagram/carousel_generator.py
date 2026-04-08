"""
v5 수정사항:
1. 1페이지: 전체 콘텐츠 수직 중앙 재배치
2. 모든 박스 텍스트: draw_text_mm(cx, cy) 방식으로 완전 수직중앙 통일
3. 3페이지: 별점 영역 내 배치 확인, 4페이지: warning 박스 높이 늘려 별점 보호
4. 7페이지: 밑줄 완전 제거
"""
from PIL import Image, ImageDraw, ImageFont
import os

BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
REG_PATH  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H = 1080, 1080
PAD = 60
OUT = "/tmp/carousel_gg_v5"
IMG_DIR = "/tmp/carousel_gg_v2"
os.makedirs(OUT, exist_ok=True)

BG      = (14, 14, 20)
BG2     = (24, 24, 34)
BG3     = (34, 34, 48)
WHITE   = (255, 255, 255)
CREAM   = (255, 245, 225)
ORANGE  = (255, 135, 20)
GRAY_L  = (160, 160, 180)
GRAY_M  = (90,  90,  110)
GRAY_D  = (40,  40,  56)
RED     = (220, 60,  50)
SILVER  = (185, 185, 210)
BRONZE  = (170, 120, 45)

def F(size, bold=True):
    return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size, index=3)

def tw(f, t):
    b = f.getbbox(t); return b[2] - b[0]

def th(f, t="가나다"):
    """폰트 실제 렌더 높이 (ascent 기준, 더 정확)"""
    b = f.getbbox(t)
    return b[3] - b[1]

def shrink(f, text, max_w):
    while tw(f, text) > max_w and f.size > 14:
        f = ImageFont.truetype(f.path, f.size - 2, index=3)
    return f

# ── 핵심 텍스트 배치 함수 ──────────────────────────────
def mm(draw, text, cx, cy, f, color, max_w=None):
    """완전 중앙(x,y). cy = 텍스트 시각적 중심 y."""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text)
    b  = f.getbbox(text)
    # getbbox는 (left,top,right,bottom) — top은 보통 양수(descender 공간 포함)
    # 시각적 중앙: cy - (top+bottom)/2
    vis_cy = (b[1] + b[3]) / 2
    draw.text((cx - w_ // 2, cy - int(vis_cy)), text, font=f, fill=color)

def lm(draw, text, x, cy, f, color, max_w=None):
    """좌측(x), 수직중앙(cy)."""
    if max_w: f = shrink(f, text, max_w)
    b = f.getbbox(text)
    vis_cy = (b[1] + b[3]) / 2
    draw.text((x, cy - int(vis_cy)), text, font=f, fill=color)
    return f

def ct(draw, text, y_top, f, color, max_w=W-PAD*2):
    """상단y 기준 중앙정렬. 반환: 텍스트 시각 높이."""
    if max_w: f = shrink(f, text, max_w)
    w_ = tw(f, text)
    b  = f.getbbox(text)
    draw.text(((W - w_) // 2, y_top - b[1]), text, font=f, fill=color)
    return b[3] - b[1]   # 시각 높이

def badge(draw, text, cx, cy, f, bg_col, fg_col, pad_x=22, pad_y=0, radius=26):
    """박스+텍스트 수직중앙. cy = 박스 수직 중심."""
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10   # 박스 높이 = 텍스트 높이 + 패딩*2 + 여유
    bw = w_ + pad_x * 2
    x1 = cx - bw // 2; x2 = cx + bw // 2
    y1 = cy - bh // 2; y2 = cy + bh // 2
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=bg_col)
    mm(draw, text, cx, cy, f, fg_col)
    return bw, bh, x1, y1, x2, y2

def badge_left(draw, text, x, cy, f, bg_col, fg_col, pad_x=18, pad_y=0, radius=24):
    """좌측정렬 박스+텍스트 수직중앙."""
    w_ = tw(f, text); h_ = th(f, text)
    bh = h_ + pad_y * 2 + 10
    bw = w_ + pad_x * 2
    y1 = cy - bh // 2; y2 = cy + bh // 2
    draw.rounded_rectangle([x, y1, x + bw, y2], radius=radius, fill=bg_col)
    lm(draw, text, x + pad_x, cy, f, fg_col)
    return x + bw  # 다음 태그 시작 x

def divider(draw, y, width=160, col=ORANGE, h=4):
    draw.rectangle([(W//2-width//2, y),(W//2+width//2, y+h)], fill=col)

def top_bar(draw, col=ORANGE):  draw.rectangle([0,0,W,6], fill=col)
def bot_bar(draw, col=ORANGE):  draw.rectangle([0,H-6,W,H], fill=col)
def slide_no(draw, n, t):
    draw.text((W-PAD, H-36), f"{n} / {t}", font=F(22,False), fill=GRAY_M, anchor="rm")

def paste_img(img, path, cx, cy, size):
    try:
        p = Image.open(path).convert("RGB").resize((size,size), Image.LANCZOS)
        mask = Image.new("L",(size,size),0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,size-1,size-1], radius=24, fill=255)
        img.paste(p, (cx-size//2, cy-size//2), mask)
    except:
        d = ImageDraw.Draw(img)
        x,y = cx-size//2, cy-size//2
        d.rounded_rectangle([x,y,x+size,y+size], radius=24, fill=GRAY_D)
        d.text((cx,cy), "IMG", font=F(28), fill=GRAY_M, anchor="mm")

def add_grain(img, a=5):
    import random; p=img.load()
    for _ in range(W*H//35):
        x,y=random.randint(0,W-1),random.randint(0,H-1)
        d=random.randint(-a,a)
        p[x,y]=tuple(max(0,min(255,c+d)) for c in p[x,y])
    return img

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 1 — 커버  (수직 중앙 재배치)
# 전체 콘텐츠 블록 높이 계산 후 중앙 정렬
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s1():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    for y in range(H):
        v=y/H; d.line([(0,y),(W,y)], fill=(int(14+v*28),int(14+v*14),int(20+v*8)))
    top_bar(d); bot_bar(d)

    # 전체 콘텐츠 높이 사전 계산:
    # 뱃지(50) + gap(28) + 이미지존(230) + gap(36) + 서브라인(36) + gap(14) + 타이틀1(88) + gap(8) + 타이틀2(88) + gap(28) + 서브2(38)
    BADGE_H = 50
    IMG_H   = 230   # 이미지 지름
    TITLE1_H = 88
    TITLE2_H = 88
    SUB1_H  = 38
    SUB2_H  = 36
    G1=28; G2=36; G3=14; G4=8; G5=28

    total_h = BADGE_H+G1+IMG_H+G2+SUB1_H+G3+TITLE1_H+G4+TITLE2_H+G5+SUB2_H
    y_start = (H - total_h) // 2  # 수직 중앙 시작 y

    y = y_start

    # 1. 카테고리 뱃지
    badge_cy = y + BADGE_H//2
    badge(d, "헬스 보충제  ·  비교 리뷰", W//2, badge_cy, F(27), ORANGE, BG, pad_x=24, pad_y=6)
    y += BADGE_H + G1

    # 2. 상품 이미지 3개 (이미지 중심 y)
    img_cy = y + IMG_H//2
    positions = [(W//2, img_cy), (W//2-262, img_cy+16), (W//2+262, img_cy+16)]
    sizes     = [215, 188, 188]
    prods     = [f"{IMG_DIR}/prod1.jpg", f"{IMG_DIR}/prod2.jpg", f"{IMG_DIR}/prod3.jpg"]
    for i,(cx,cy_) in enumerate(positions):
        paste_img(img, prods[i], cx, cy_, sizes[i])
    d = ImageDraw.Draw(img)
    rank_data = [
        (positions[0], sizes[0], "1위", ORANGE, BG),
        (positions[1], sizes[1], "2위", SILVER, BG),
        (positions[2], sizes[2], "3위", BRONZE, BG),
    ]
    for (cx,cy_),sz,label,bg_c,fg_c in rank_data:
        rc = cy_ - sz//2
        d.ellipse([cx-26, rc-20, cx+26, rc+20], fill=bg_c)
        mm(d, label, cx, rc, F(22), fg_c if fg_c==BG else WHITE)
    y += IMG_H + G2

    # 3. 서브라인(작은 텍스트 먼저)
    ct(d, "2026 완전 비교  |  3종 직접 테스트", y, F(28,False), GRAY_L)
    y += SUB1_H + G3

    # 4. 메인 타이틀 2줄
    ct(d, "크레아틴, 비싼 게", y, F(78), WHITE)
    y += TITLE1_H + G4
    ct(d, "정말 좋을까?", y, F(78), ORANGE)
    y += TITLE2_H + G5

    # 5. 서브 2
    ct(d, "뉴트리코스트  vs  잠백이  vs  아르기닌", y, F(32,False), GRAY_L)

    mm(d, "꿀통몬 PICKS", W//2, H-32, F(26), ORANGE)
    slide_no(d,1,8)
    add_grain(img); img.save(f"{OUT}/slide_01_cover.jpg",quality=96); print("OK s1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 2 — 체크리스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s2():
    CARD_H = 140
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    # 헤더존 (6~148)
    mm(d, "꿀통몬 PICKS", W//2, 34, F(26), ORANGE)
    ct(d, "사기 전 체크 5가지", 58, F(58), WHITE)
    ct(d, "이것만 알면 절대 후회 없다", 128, F(30,False), GRAY_L)
    divider(d, 150, width=120, h=3)

    items = [
        ("성분 순도",  "크레아틴 모노하이드레이트 100% 단일 확인"),
        ("실제 함량",  "1회 제공량 중 순수 크레아틴 g수 확인"),
        ("1회 단가",   "총 중량 ÷ 가격 직접 계산 필수"),
        ("제형 선택",  "분말(저렴·조절) vs 정제(휴대 간편)"),
        ("목적 구분",  "크레아틴 = 근력   /   아르기닌 = 펌핑"),
    ]

    y = 156
    for i,(main,sub) in enumerate(items):
        bg_ = BG2 if i%2==0 else BG3
        d.rounded_rectangle([PAD, y, W-PAD, y+CARD_H-4], radius=14, fill=bg_)
        d.rounded_rectangle([PAD, y, PAD+7, y+CARD_H-4], radius=3, fill=ORANGE)

        card_cy = y + (CARD_H-4)//2
        num_cx = PAD + 54
        d.ellipse([num_cx-22, card_cy-22, num_cx+22, card_cy+22], fill=ORANGE)
        mm(d, str(i+1), num_cx, card_cy, F(26), BG)

        text_x = PAD + 98
        # 메인: 카드 38% 지점
        lm(d, main, text_x, y+(CARD_H-4)*38//100, F(37), WHITE, max_w=W-PAD-text_x-12)
        # 서브: 카드 68% 지점
        lm(d, sub,  text_x, y+(CARD_H-4)*68//100, F(25,False), GRAY_L, max_w=W-PAD-text_x-12)
        y += CARD_H

    slide_no(d,2,8); add_grain(img,5)
    img.save(f"{OUT}/slide_02_checklist.jpg",quality=96); print("OK s2")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 공통 제품 슬라이드 (3,4,5)
# 레이아웃:
#   헤더띠   : y=6~106    (높이 100, 순위 표시)
#   제품정보 : y=106~555  (이미지+텍스트)
#   구분선   : y=555
#   태그     : y=562~615
#   평가카드 : y=622~800  (요약+warning+별점)
#   링크     : y=810~855
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def product_slide(n, rank_txt, rank_bg, rank_fg,
                  prod_path, name1, name2, price, price_bg,
                  specs, tags, tag_col,
                  summary, sum_bg, stars, star_col,
                  warning=None):

    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d, rank_bg); bot_bar(d)

    # ── 순위 헤더띠 ───────────────────
    HEADER_Y1, HEADER_Y2 = 6, 106
    d.rectangle([0, HEADER_Y1, W, HEADER_Y2], fill=rank_bg)
    mm(d, rank_txt, W//2, (HEADER_Y1+HEADER_Y2)//2, F(46), rank_fg)

    # ── 제품 이미지 (우측) ─────────────
    IMG_SZ = 238; IMG_CX = 832; IMG_CY = 318
    paste_img(img, prod_path, IMG_CX, IMG_CY, IMG_SZ)
    d = ImageDraw.Draw(img)

    TEXT_X = PAD  # 텍스트 시작 x
    TEXT_MAX_W = IMG_CX - IMG_SZ//2 - PAD - 20   # ~633px

    # 제품명
    lm(d, name1, TEXT_X, 155, F(54), WHITE,   max_w=TEXT_MAX_W)
    lm(d, name2, TEXT_X, 215, F(32,False), GRAY_L, max_w=TEXT_MAX_W)

    # 가격 뱃지 — badge_left 사용 (수직 중앙 보장)
    badge_left(d, price, TEXT_X, 272, F(38), price_bg,
               rank_fg if rank_fg==BG else WHITE, pad_x=20, pad_y=8, radius=26)

    # 스펙 리스트
    sy = 322
    for spec in specs:
        cy_ = sy + 18
        d.ellipse([TEXT_X, cy_-7, TEXT_X+14, cy_+7],
                  fill=rank_bg if rank_bg not in [BG,BG2,BG3] else ORANGE)
        lm(d, spec, TEXT_X+24, cy_, F(28,False), WHITE, max_w=TEXT_MAX_W-10)
        sy += 50

    # ── 구분선 ─────────────────────────
    d.rectangle([PAD, 552, W-PAD, 555], fill=GRAY_D)

    # ── 태그 행 ────────────────────────
    tx = PAD; ty_tag_cy = 585  # 태그 수직 중앙 y
    for tag in tags:
        ft = F(24)
        tw_ = tw(ft, tag) + 26
        th_ = th(ft, tag) + 14
        ty1 = ty_tag_cy - th_//2
        ty2 = ty_tag_cy + th_//2
        d.rounded_rectangle([tx, ty1, tx+tw_, ty2], radius=18, fill=GRAY_D)
        d.rectangle([tx, ty1, tx+6, ty2], fill=tag_col)
        lm(d, tag, tx+14, ty_tag_cy, ft, tag_col)
        tx += tw_ + 12

    # ── 평가 카드 ──────────────────────
    # warning 유무에 따라 레이아웃 조정
    EVAL_Y1 = 618
    if warning:
        # warning 있을 때: summary + warning + 별점 → 카드 높이 넉넉히
        EVAL_Y2 = 820
        d.rounded_rectangle([PAD, EVAL_Y1, W-PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD+7, EVAL_Y2], fill=tag_col)
        # 3등분: 요약/경고/별점
        row_h = (EVAL_Y2-EVAL_Y1)//3
        mm(d, summary, W//2, EVAL_Y1+row_h//2,      F(32), WHITE,   max_w=W-PAD*2-40)
        mm(d, warning, W//2, EVAL_Y1+row_h+row_h//2, F(25,False), GRAY_L, max_w=W-PAD*2-40)
        mm(d, stars,   W//2, EVAL_Y1+row_h*2+row_h//2, F(32), star_col, max_w=W-PAD*2-40)
    else:
        EVAL_Y2 = 800
        d.rounded_rectangle([PAD, EVAL_Y1, W-PAD, EVAL_Y2], radius=16, fill=sum_bg)
        d.rectangle([PAD, EVAL_Y1, PAD+7, EVAL_Y2], fill=tag_col)
        row_h = (EVAL_Y2-EVAL_Y1)//2
        mm(d, summary, W//2, EVAL_Y1+row_h//2,      F(34), WHITE,   max_w=W-PAD*2-40)
        mm(d, stars,   W//2, EVAL_Y1+row_h+row_h//2, F(34), star_col, max_w=W-PAD*2-40)

    # ── 링크 안내 ──────────────────────
    link_y = EVAL_Y2 + 20 if EVAL_Y2 < H-80 else H-66
    mm(d, "쿠팡 로켓배송  /  링크는 프로필 참고", W//2, link_y, F(24,False), GRAY_M)

    slide_no(d,n,8); add_grain(img)
    fname = f"slide_{n:02d}_p.jpg"
    img.save(f"{OUT}/{fname}",quality=96); print(f"OK s{n}")

def s3():
    product_slide(3, "1위  추천", ORANGE, BG,
        f"{IMG_DIR}/prod1.jpg", "뉴트리코스트", "정품 크레아틴 분말",
        "19,500원", ORANGE,
        ["500g / 약 100회분", "1회 단가 195원 — 3종 중 최저", "GMP 인증 시설 생산", "크레아틴 100% 단일 성분"],
        ["가성비 최고","헬스 입문자","장기 복용"], ORANGE,
        "입문자 1순위  |  글로벌 검증 브랜드", (36,20,4),
        "★★★★★", ORANGE)

def s4():
    product_slide(4, "2위", (88,88,124), WHITE,
        f"{IMG_DIR}/prod2.jpg", "잠백이", "저스트 크레아틴",
        "13,900원", (88,88,128),
        ["국내 식약처 기준 적용", "크레아틴 모노하이드레이트 단일", "찬물에도 잘 용해", "국내 A/S·교환·환불 편리"],
        ["국산 선호","소용량 입문","식약처 인증"], SILVER,
        "국산 선호라면 최선택", (22,22,42),
        "★★★★☆", SILVER,
        warning="주의: 대용량 장기 복용 시 단가 비교 필수")

def s5():
    product_slide(5, "3위  (중급자용)", (72,48,10), CREAM,
        f"{IMG_DIR}/prod3.jpg", "익스트림 듀얼", "아르기닌 플러스 1000mg",
        "27,500원", (68,44,8),
        ["고함량 아르기닌 1000mg", "정제형 — 휴대 편리", "운동 전 펌핑감 향상", "크레아틴과 병행 가능"],
        ["중급자 추가","펌핑감 향상","정제형"], BRONZE,
        "크레아틴 3~6개월 후 추가 도입 권장", (22,14,4),
        "★★★☆☆  (입문자 기준)", BRONZE,
        warning="입문자 비권장 — 크레아틴을 먼저 시작하세요")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 6 — 비교표
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s6():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d, "꿀통몬 PICKS", W//2, 30, F(26), ORANGE)
    ct(d, "한눈에 비교", 54, F(60), WHITE)
    divider(d, 128, width=130, h=4)

    CX = [78, 310, 570, 828]
    CW = [222, 248, 248, 234]
    ROWS_TOP = 144
    ROW_H    = 88

    hdrs = ["항목", "뉴트리코스트", "잠백이", "아르기닌"]
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROWS_TOP, W-PAD, ROWS_TOP+ROW_H], fill=(18,18,28))
    for cx,cw,hdr,hcol in zip(CX,CW,hdrs,hcols):
        lm(d, hdr, cx, ROWS_TOP+ROW_H//2, F(26), hcol, max_w=cw-10)

    rows = [
        ("가격",      "19,500원",   "13,900원",  "27,500원"),
        ("용량",      "500g/100회", "소용량",    "정제형"),
        ("1회 단가",  "195원 최저", "비교 필요", "-"),
        ("주성분",    "크레아틴",   "크레아틴",  "아르기닌"),
        ("제형",      "분말",       "분말",      "정제"),
        ("인증",      "미국 GMP",   "국내 식약처","국내 기준"),
        ("추천",      "입문자 1위", "국산 선호", "중급자 추가"),
    ]
    vcols = [GRAY_L, ORANGE, SILVER, BRONZE]

    y = ROWS_TOP + ROW_H
    for ri, row in enumerate(rows):
        bg_ = BG2 if ri%2==0 else BG3
        d.rectangle([PAD, y, W-PAD, y+ROW_H-2], fill=bg_)
        if ri < 7:
            d.rectangle([CX[1]-8, y, CX[1]+CW[1]-10, y+ROW_H-2], fill=(28,16,4))
        for ci,(val,vc) in enumerate(zip(row, vcols)):
            fv = F(24 if ci==0 else 22, bold=(ci==0))
            fv = shrink(fv, val, CW[ci]-14)
            lm(d, val, CX[ci], y+ROW_H//2-1, fv, vc)
        y += ROW_H

    # 추천 요약
    d.rounded_rectangle([PAD, y+8, W-PAD, y+74], radius=12, fill=(34,18,4))
    d.rectangle([PAD, y+8, PAD+6, y+74], fill=ORANGE)
    mm(d, "입문자 순위 :  뉴트리코스트  >  잠백이  >  아르기닌",
       W//2, y+8+(74-8)//2, F(26), WHITE, max_w=W-PAD*2-30)

    slide_no(d,6,8); add_grain(img,5)
    img.save(f"{OUT}/slide_06_compare.jpg",quality=96); print("OK s6")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 7 — 핵심 메시지  (밑줄 완전 제거)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s7():
    img = Image.new("RGB",(W,H),(10,6,2))
    d = ImageDraw.Draw(img)
    for x in range(0,W,90): d.line([(x,0),(x,H)], fill=(18,12,5), width=1)
    for y in range(0,H,90): d.line([(0,y),(W,y)], fill=(18,12,5), width=1)
    top_bar(d); bot_bar(d)

    d.text((38,-62), '"', font=F(280), fill=(38,24,6))

    # 콘텐츠 블록 높이 계산
    f1 = F(74); f2 = F(70); f_sub = F(36,False); f_cap = F(28,False)
    h1 = th(f1, "크레아틴 먼저,")
    h2 = th(f2, "아르기닌은  그 다음")
    h_div = 4
    h_sub = th(f_sub, "근력")
    h_cap = th(f_cap, "ACSM")
    total_h = h1+20+h2+32+h_div+24+h_sub+16+h_cap
    y = (H - total_h) // 2

    # 1행: 흰색
    ct(d, "크레아틴 먼저,", y, f1, WHITE)
    y += h1 + 20

    # 2행: "아르기닌은" 오렌지 + "  그 다음" 흰색 (밑줄 없음)
    p1="아르기닌은"; p2="  그 다음"
    w1_=tw(f2,p1); w2_=tw(f2,p2)
    x_s=(W-w1_-w2_)//2
    b_=f2.getbbox(p1); vis_cy=(b_[1]+b_[3])/2
    d.text((x_s, y-int(vis_cy-b_[3]//2)), p1, font=f2, fill=ORANGE)
    d.text((x_s+w1_, y-int(vis_cy-b_[3]//2)), p2, font=f2, fill=WHITE)
    # ★ 밑줄 없음 — 제거
    y += h2 + 32

    # 구분선
    divider(d, y, width=180, h=h_div)
    y += h_div + 24

    # 서브
    ct(d, "근력 향상 과학적 근거 1순위", y, f_sub, GRAY_L)
    y += h_sub + 16
    ct(d, "ACSM 미국스포츠의학회 권고 기준", y, f_cap, GRAY_M)

    slide_no(d,7,8); add_grain(img,5)
    img.save(f"{OUT}/slide_07_quote.jpg",quality=96); print("OK s7")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 8 — CTA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s8():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA",(W,H),(0,0,0,0))
    gd = ImageDraw.Draw(glow)
    for r in range(380,0,-6):
        ratio=r/380; a=int((1-ratio**2)*85)
        gd.ellipse([W//2-r,H//2-r,W//2+r,H//2+r], fill=(255,int(135*(1-ratio)),0,a))
    img=Image.alpha_composite(img.convert("RGBA"),glow).convert("RGB")
    d=ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    # 저장 아이콘
    ic_cx=W//2; ic_top=H//2-200; ic_h=80
    d.rectangle([ic_cx-36,ic_top,ic_cx+36,ic_top+ic_h], fill=ORANGE)
    d.polygon([(ic_cx-36,ic_top+ic_h),(ic_cx+36,ic_top+ic_h),(ic_cx,ic_top+ic_h+38)], fill=ORANGE)

    # 전체 텍스트 블록 중앙 배치
    f_main=F(76); f_sub_=F(68); f_note=F(32,False); f_hash=F(26,False)
    h_main=th(f_main,"저장"); h_sub_=th(f_sub_,"쿠팡"); h_note=th(f_note,"링")
    BTN_H=72; GAP=12
    total_h=h_main+GAP+h_sub_+GAP+h_note+GAP+BTN_H+GAP+th(f_hash,"#")
    cy_start = ic_top+ic_h+38+24

    y=cy_start
    ct(d,"저장해두고",y,f_main,WHITE); y+=h_main+GAP
    ct(d,"쿠팡에서 확인하세요",y,f_sub_,ORANGE); y+=h_sub_+GAP
    ct(d,"링크는 프로필에 있어요",y,f_note,GRAY_L); y+=h_note+GAP

    # 팔로우 버튼 — badge() 사용해 완전 수직 중앙
    btn_cy=y+BTN_H//2
    badge(d,"팔로우  @ggultongmon",W//2,btn_cy,F(36),ORANGE,BG, pad_x=60,pad_y=12,radius=36)
    y+=BTN_H+GAP

    ct(d,"#크레아틴추천  #헬스보충제  #쿠팡직구",y,f_hash,GRAY_M)
    slide_no(d,8,8); add_grain(img,5)
    img.save(f"{OUT}/slide_08_cta.jpg",quality=96); print("OK s8")

s1(); s2(); s3(); s4(); s5(); s6(); s7(); s8()
print(f"\n완료 → {OUT}/")
