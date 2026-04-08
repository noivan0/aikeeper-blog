"""
v5 → v6 패치 (3개 슬라이드만 수정)
1. s2: "이것만 알면..." ~ 표 사이 간격 확대 (divider y 조정 + 카드 재배치)
2. s6: 비교표 데이터 정확히 (포스트 원문 기반) + 3번째 상품명 수정
3. s8: 텍스트 간격 확대
"""
from PIL import Image, ImageDraw, ImageFont
import os, shutil

# v5 코드 전체 import를 위해 직접 함수 재정의
BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
REG_PATH  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H = 1080, 1080
PAD = 60
SRC = "/tmp/carousel_gg_v5"
OUT = "/tmp/carousel_gg_v6"
IMG_DIR = "/tmp/carousel_gg_v2"
os.makedirs(OUT, exist_ok=True)

# v5에서 변경 없는 슬라이드 복사
for n in [1,3,4,5,7]:
    fname = f"slide_{n:02d}_p.jpg" if n in [3,4,5] else (
            f"slide_{n:02d}_cover.jpg" if n==1 else
            f"slide_{n:02d}_quote.jpg" if n==7 else "")
    if not fname:
        continue
    src = f"{SRC}/{fname}"
    if os.path.exists(src):
        shutil.copy(src, f"{OUT}/{fname}")
        print(f"copy {fname}")
shutil.copy(f"{SRC}/slide_01_cover.jpg",   f"{OUT}/slide_01_cover.jpg")
shutil.copy(f"{SRC}/slide_03_p.jpg",       f"{OUT}/slide_03_p.jpg")
shutil.copy(f"{SRC}/slide_04_p.jpg",       f"{OUT}/slide_04_p.jpg")
shutil.copy(f"{SRC}/slide_05_p.jpg",       f"{OUT}/slide_05_p.jpg")
shutil.copy(f"{SRC}/slide_07_quote.jpg",   f"{OUT}/slide_07_quote.jpg")

BG      = (14, 14, 20)
BG2     = (24, 24, 34)
BG3     = (34, 34, 48)
WHITE   = (255, 255, 255)
ORANGE  = (255, 135, 20)
GRAY_L  = (160, 160, 180)
GRAY_M  = (90,  90,  110)
GRAY_D  = (40,  40,  56)
SILVER  = (185, 185, 210)
BRONZE  = (170, 120, 45)

def F(size, bold=True):
    return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size, index=3)
def tw(f,t):
    b=f.getbbox(t); return b[2]-b[0]
def th(f,t="가나다"):
    b=f.getbbox(t); return b[3]-b[1]
def shrink(f,text,max_w):
    while tw(f,text)>max_w and f.size>14:
        f=ImageFont.truetype(f.path,f.size-2,index=3)
    return f
def mm(draw,text,cx,cy,f,color,max_w=None):
    if max_w: f=shrink(f,text,max_w)
    w_=tw(f,text); b=f.getbbox(text)
    vis_cy=(b[1]+b[3])/2
    draw.text((cx-w_//2, cy-int(vis_cy)), text, font=f, fill=color)
def lm(draw,text,x,cy,f,color,max_w=None):
    if max_w: f=shrink(f,text,max_w)
    b=f.getbbox(text); vis_cy=(b[1]+b[3])/2
    draw.text((x, cy-int(vis_cy)), text, font=f, fill=color)
    return f
def ct(draw,text,y_top,f,color,max_w=W-PAD*2):
    if max_w: f=shrink(f,text,max_w)
    w_=tw(f,text); b=f.getbbox(text)
    draw.text(((W-w_)//2, y_top-b[1]), text, font=f, fill=color)
    return b[3]-b[1]
def divider(draw,y,width=160,col=ORANGE,h=4):
    draw.rectangle([(W//2-width//2,y),(W//2+width//2,y+h)], fill=col)
def top_bar(draw,col=ORANGE):  draw.rectangle([0,0,W,6],fill=col)
def bot_bar(draw,col=ORANGE):  draw.rectangle([0,H-6,W,H],fill=col)
def slide_no(draw,n,t):
    draw.text((W-PAD,H-36),f"{n} / {t}",font=F(22,False),fill=GRAY_M,anchor="rm")
def add_grain(img,a=5):
    import random; p=img.load()
    for _ in range(W*H//35):
        x,y=random.randint(0,W-1),random.randint(0,H-1)
        d=random.randint(-a,a)
        p[x,y]=tuple(max(0,min(255,c+d)) for c in p[x,y])
    return img

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 2 수정 — 간격 확대
# 헤더: 0~162 / 카드: 172~H-50
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s2():
    # 사용 가능 카드 영역: 172 ~ 1030 = 858px / 5카드 = 171px per card
    CARD_H = 163
    CARDS_TOP = 175
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    # 헤더
    mm(d,"꿀통몬 PICKS",W//2,30,F(26),ORANGE)
    ct(d,"사기 전 체크 5가지",54,F(56),WHITE)

    # 서브 텍스트 — 간격 충분히
    ct(d,"이것만 알면 절대 후회 없다",118,F(29,False),GRAY_L)

    # 구분선 — 서브 텍스트와 카드 사이 충분히
    divider(d,155,width=120,h=3)

    items = [
        ("성분 순도",  "크레아틴 모노하이드레이트 100% 단일 확인"),
        ("실제 함량",  "1회 제공량 중 순수 크레아틴 g수 확인"),
        ("1회 단가",   "총 중량 ÷ 가격 직접 계산 필수"),
        ("제형 선택",  "분말(저렴·조절) vs 정제(휴대 간편)"),
        ("목적 구분",  "크레아틴 = 근력   /   아르기닌 = 펌핑"),
    ]

    y = CARDS_TOP
    for i,(main,sub) in enumerate(items):
        bg_ = BG2 if i%2==0 else BG3
        card_y2 = y + CARD_H - 5
        d.rounded_rectangle([PAD, y, W-PAD, card_y2], radius=14, fill=bg_)
        d.rounded_rectangle([PAD, y, PAD+7, card_y2], radius=3, fill=ORANGE)

        card_cy = y + (CARD_H-5)//2
        num_cx = PAD + 54
        d.ellipse([num_cx-23, card_cy-23, num_cx+23, card_cy+23], fill=ORANGE)
        mm(d,str(i+1),num_cx,card_cy,F(27),BG)

        text_x = PAD + 98
        avail_w = W - PAD - text_x - 14
        # 메인: 카드 37% 지점
        lm(d, main, text_x, y+(CARD_H-5)*37//100, F(36), WHITE, max_w=avail_w)
        # 서브: 카드 67% 지점
        lm(d, sub,  text_x, y+(CARD_H-5)*67//100, F(25,False), GRAY_L, max_w=avail_w)
        y += CARD_H

    slide_no(d,2,8); add_grain(img,5)
    img.save(f"{OUT}/slide_02_checklist.jpg",quality=96); print("OK s2")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 6 수정 — 정확한 제품 데이터
# 포스트 원문 기반:
#   뉴트리코스트: 19,500원 / 500g(100회) / 분말 / GMP / 1회 195원
#   잠백이: 13,900원 / 소용량 / 분말 / 국내 식약처 / 단가 높음
#   익스트림 듀얼 아르기닌: 27,500원 / 정제 / 국내 / 아르기닌 1000mg
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s6():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d,"꿀통몬 PICKS",W//2,30,F(26),ORANGE)
    ct(d,"한눈에 비교",54,F(60),WHITE)
    divider(d,128,width=130,h=4)

    # 열 설정
    CX   = [68,  305, 558, 810]   # 각 열 텍스트 시작 x
    CW   = [228, 244, 244, 240]   # 각 열 최대 너비
    ROW_TOP = 144
    ROW_H   = 86

    # 헤더
    hdrs  = ["항목", "뉴트리코스트", "잠백이", "아르기닌"]
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROW_TOP, W-PAD, ROW_TOP+ROW_H], fill=(18,18,28))
    for cx,cw,hdr,hcol in zip(CX,CW,hdrs,hcols):
        lm(d, hdr, cx, ROW_TOP+ROW_H//2, shrink(F(26),hdr,cw-8), hcol)

    # 정확한 데이터 (포스트 원문 기반)
    rows = [
        ("가격",       "19,500원",     "13,900원",   "27,500원"),
        ("주요 성분",  "크레아틴",     "크레아틴",   "아르기닌"),
        ("제형",       "분말",         "분말",       "정제(태블릿)"),
        ("용량",       "500g / 100회", "소용량",     "아르기닌 1000mg"),
        ("1회 단가",   "195원 최저",   "단가 높음",  "-"),
        ("인증",       "미국 GMP",     "국내 식약처","국내 기준"),
        ("추천 대상",  "입문자",       "국산 선호",  "중급자 추가"),
    ]
    vcols = [GRAY_L, ORANGE, SILVER, BRONZE]

    y = ROW_TOP + ROW_H
    for ri, row in enumerate(rows):
        bg_ = BG2 if ri%2==0 else BG3
        row_y2 = y + ROW_H - 2
        d.rectangle([PAD, y, W-PAD, row_y2], fill=bg_)
        # 1위 열 미묘한 강조
        d.rectangle([CX[1]-8, y, CX[1]+CW[1]-6, row_y2], fill=(28,16,4))
        for ci,(val,vc) in enumerate(zip(row, vcols)):
            fv = shrink(F(23 if ci==0 else 21, bold=(ci==0)), val, CW[ci]-12)
            lm(d, val, CX[ci], y+ROW_H//2, fv, vc)
        y += ROW_H

    # 추천 요약 박스
    sum_y1 = y + 10; sum_y2 = y + 78
    d.rounded_rectangle([PAD, sum_y1, W-PAD, sum_y2], radius=12, fill=(32,18,4))
    d.rectangle([PAD, sum_y1, PAD+6, sum_y2], fill=ORANGE)
    mm(d,"입문자 순위 :  뉴트리코스트  >  잠백이  >  아르기닌",
       W//2, sum_y1+(sum_y2-sum_y1)//2, F(26), WHITE, max_w=W-PAD*2-30)

    slide_no(d,6,8); add_grain(img,5)
    img.save(f"{OUT}/slide_06_compare.jpg",quality=96); print("OK s6")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLIDE 8 수정 — 텍스트 간격 확대
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
def s8():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    glow = Image.new("RGBA",(W,H),(0,0,0,0))
    gd = ImageDraw.Draw(glow)
    for r in range(380,0,-6):
        ratio=r/380; a=int((1-ratio**2)*85)
        gd.ellipse([W//2-r,H//2-r,W//2+r,H//2+r],
                   fill=(255,int(135*(1-ratio)),0,a))
    img=Image.alpha_composite(img.convert("RGBA"),glow).convert("RGB")
    d=ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    # 저장 아이콘
    ic_cx=W//2; ic_top=160; ic_h=80
    d.rectangle([ic_cx-36,ic_top,ic_cx+36,ic_top+ic_h], fill=ORANGE)
    d.polygon([(ic_cx-36,ic_top+ic_h),(ic_cx+36,ic_top+ic_h),(ic_cx,ic_top+ic_h+38)], fill=ORANGE)

    # 텍스트 블록 — 아이콘 아래부터
    GAP_LARGE = 28   # 큰 간격 (제목 사이)
    GAP_MED   = 20   # 중간 (제목~서브)
    GAP_SMALL = 16   # 작은 (서브~버튼)

    f_main = F(76); f_sub = F(68); f_note = F(34,False); f_hash = F(27,False)
    h_main = th(f_main,"저장"); h_sub = th(f_sub,"쿠팡")
    h_note = th(f_note,"링크"); h_hash = th(f_hash,"#")
    BTN_H = 74

    y = ic_top + ic_h + 38 + GAP_LARGE

    # 메인 카피 1
    ct(d,"저장해두고",y,f_main,WHITE)
    y += h_main + GAP_LARGE

    # 메인 카피 2
    ct(d,"쿠팡에서 확인하세요",y,f_sub,ORANGE)
    y += h_sub + GAP_MED + 10   # 서브카피와 안내문 사이 여유

    # 서브 안내
    ct(d,"링크는 프로필에 있어요",y,f_note,GRAY_L)
    y += h_note + GAP_MED + 6

    # 팔로우 버튼
    btn_w = 490
    btn_x = (W-btn_w)//2
    d.rounded_rectangle([btn_x, y, btn_x+btn_w, y+BTN_H], radius=37, fill=ORANGE)
    mm(d,"팔로우  @ggultongmon",W//2,y+BTN_H//2,F(36),BG)
    y += BTN_H + GAP_MED + 6

    # 해시태그
    ct(d,"#크레아틴추천  #헬스보충제  #쿠팡직구",y,f_hash,GRAY_M)

    slide_no(d,8,8); add_grain(img,5)
    img.save(f"{OUT}/slide_08_cta.jpg",quality=96); print("OK s8")

s2(); s6(); s8()
print(f"\n완료 → {OUT}/")
