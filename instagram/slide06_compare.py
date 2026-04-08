from PIL import Image, ImageDraw, ImageFont
import os, shutil

BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
REG_PATH  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H = 1080, 1080
PAD = 60
OUT = "/tmp/carousel_gg_v6"

BG      = (14, 14, 20)
BG2     = (24, 24, 34)
BG3     = (34, 34, 48)
WHITE   = (255, 255, 255)
ORANGE  = (255, 135, 20)
GRAY_L  = (160, 160, 180)
GRAY_M  = (90,  90,  110)
SILVER  = (185, 185, 210)
BRONZE  = (170, 120, 45)

def F(size, bold=True):
    return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size, index=3)
def tw(f,t):
    b=f.getbbox(t); return b[2]-b[0]
def shrink(f,text,max_w):
    while tw(f,text)>max_w and f.size>12:
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

def s6():
    img = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(img)
    top_bar(d); bot_bar(d)

    mm(d,"꿀통몬 PICKS",W//2,30,F(26),ORANGE)
    ct(d,"한눈에 비교",54,F(60),WHITE)
    divider(d,128,width=130,h=4)

    # 열 설정 — 3번째 헤더: "익스트림듀얼"
    CX   = [68,  305, 558, 810]
    CW   = [228, 244, 244, 240]
    ROW_TOP = 144
    ROW_H   = 86

    # 헤더 — 3번째: "익스트림듀얼" (공간 제약으로 줄임)
    hdrs  = ["항목", "뉴트리코스트", "잠백이", "익스트림듀얼"]
    hcols = [GRAY_L, ORANGE, SILVER, BRONZE]
    d.rectangle([PAD, ROW_TOP, W-PAD, ROW_TOP+ROW_H], fill=(18,18,28))
    for cx,cw,hdr,hcol in zip(CX,CW,hdrs,hcols):
        lm(d, hdr, cx, ROW_TOP+ROW_H//2, shrink(F(25),hdr,cw-8), hcol)

    # 정확한 제품 데이터 (포스트 원문 기반)
    # 뉴트리코스트: 19,500원 / 크레아틴 모노하이드레이트 / 분말 / 500g(100회분) / 195원/회 / 미국 GMP / 입문자
    # 잠백이: 13,900원 / 크레아틴 모노하이드레이트 / 분말 / 소용량 / 단가 높음 / 국내 식약처 / 국산 선호
    # 익스트림 듀얼 아르기닌 플러스 1000mg: 27,500원 / 아르기닌 1000mg (듀얼 포뮬러) / 정제(태블릿) / - / - / 국내 기준 / 중급자

    rows = [
        ("가격",       "19,500원",          "13,900원",        "27,500원"),
        ("주요 성분",  "크레아틴100%",      "크레아틴100%",    "아르기닌1000mg"),
        ("제형",       "분말",              "분말",            "정제(태블릿)"),
        ("용량/횟수",  "500g / 100회분",    "소용량",          "듀얼 포뮬러"),
        ("1회 단가",   "195원 (최저)",      "단가 높음",       "비교 불가"),
        ("인증",       "미국 GMP",          "국내 식약처",     "국내 기준"),
        ("추천 대상",  "입문자 1순위",      "국산 선호자",     "중급자 추가"),
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
    mm(d,"입문자 순위 :  뉴트리코스트  >  잠백이  |  중급자 → 익스트림듀얼",
       W//2, sum_y1+(sum_y2-sum_y1)//2, F(24), WHITE, max_w=W-PAD*2-30)

    slide_no(d,6,8); add_grain(img,5)
    img.save(f"{OUT}/slide_06_compare.jpg",quality=96); print("OK s6")

s6()
