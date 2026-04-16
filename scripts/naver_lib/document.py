#!/usr/bin/env python3
"""
naver_lib/document.py — SE 에디터 documentModel 컴포넌트 빌더
"""
import uuid
import json
import random
import string

# 폰트 사이즈 코드 (네이버 SE 실측 기반)
# normal=15pt(본문), heading=19pt(소제목) — 2026-04-16 수정
# 네이버 SE 실제 렌더링 기준 (2026-04-12 역공학 확정)
# fs11=11pt, fs13=13pt, fs15=15pt, fs16=16pt(실제 11px 렌더링 버그), fs19=19pt(소제목), fs28=28pt
# 검색 상위 100개 분석: fs15가 1116회 사용 = 실제 15pt 안전 코드 (fs16은 11px 버그)
FS = {"tiny": "fs11", "normal": "fs15", "heading": "fs19", "large": "fs28"}
# 폰트 색상: 검은색 (#000000)
FONT_COLOR = "#000000"


def _uid() -> str:
    return "SE-" + str(uuid.uuid4())


def _docid() -> str:
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=26))


def para(text: str, bold: bool = False, fs: str = FS["normal"], color: str = FONT_COLOR, align: str = "center") -> dict:
    """
    SE 에디터 paragraph 컴포넌트.
    align: "center" (기본, banidad 스타일) | "left" | "right"
    align="center"만 paragraph에 align 속성 추가 (left/right는 SE 기본값 사용).
    """
    style = {"fontSizeCode": fs, "color": color, "@ctype": "nodeStyle"}
    if bold:
        style["bold"] = True
    paragraph = {
        "id": _uid(),
        "nodes": [{"id": _uid(), "value": text, "style": style, "@ctype": "textNode"}],
        "@ctype": "paragraph"
    }
    if align == "center":
        paragraph["align"] = "center"
    elif align == "right":
        paragraph["align"] = "right"
    # left는 SE 기본값이므로 align 속성 생략
    return paragraph


def para_link(text: str, url: str) -> dict:
    # 링크 텍스트: 본문 폰트 fs15 + 검은색
    return {
        "id": _uid(),
        "nodes": [{
            "id": _uid(), "value": text,
            "style": {"fontSizeCode": FS["normal"], "color": FONT_COLOR, "@ctype": "nodeStyle"},
            "link": {"url": url, "@ctype": "urlLink"},
            "@ctype": "textNode"
        }],
        "@ctype": "paragraph"
    }


def empty_para() -> dict:
    return para("", fs=FS["normal"])  # fs15


def empty_paras(n: int = 2) -> list:
    """문단 사이 n개 빈 줄 (banidad 스타일 — 시각적 여백)."""
    return [para("", fs=FS["normal"]) for _ in range(n)]


def text_comp(paras: list) -> dict:
    return {"id": _uid(), "layout": "default", "value": paras, "@ctype": "text"}


def image_comp(src: str, path: str, width: int, height: int,
               filename: str, represent: bool = False, file_size: int = 0) -> dict:
    return {
        "id": _uid(),
        "layout": "default",
        "src": src,
        "internalResource": True,
        "represent": represent,
        "path": path,
        "domain": "https://blogfiles.pstatic.net",
        "fileSize": file_size,
        "width": width,
        "widthPercentage": 0,
        "height": height,
        "originalWidth": width,
        "originalHeight": height,
        "fileName": filename,
        "caption": None,
        "format": "normal",
        "displayFormat": "normal",
        "imageLoaded": True,
        "contentMode": "normal",
        "origin": {"srcFrom": "local", "@ctype": "imageOrigin"},
        "ai": False,
        "@ctype": "image"
    }


def brand_card_comp(title: str, desc: str, thumb_url: str, link: str) -> dict:
    """
    브랜드커넥트 상품 카드 컴포넌트 (OGLink sign 없이 구현).
    naver.me 링크용 — 이미지 + 제목 + 설명 + 링크 텍스트 조합.
    SE editor의 text 컴포넌트에 이미지 블록 + 링크 버튼 텍스트를 묶어 카드처럼 표시.
    """
    # 빈 줄 + [카드 헤더 박스 텍스트] + 구매 링크 텍스트 형태로 카드 구현
    return text_comp([
        para("━" * 20, fs=FS["tiny"]),
        para(title, bold=True, fs=FS["heading"]),
        para(desc, fs=FS["normal"]),
        para_link("👉 지금 네이버에서 확인하기 →", link),
        para("━" * 20, fs=FS["tiny"]),
    ])


def oglink_comp(og_sign: str, title: str, desc: str,
                thumb_url: str, link: str, domain: str = "link.coupang.com") -> dict:
    return {
        "id": _uid(),
        "layout": "large_image",
        "title": title,
        "domain": domain,
        "link": link,
        "thumbnail": {
            "src": thumb_url, "width": 492, "height": 492,
            "@ctype": "thumbnail"
        },
        "description": desc,
        "video": False,
        "oglinkSign": og_sign,
        "@ctype": "oglink"
    }


def build_document_model(title: str, components: list, category_no: int = 6) -> str:
    doc = {
        "documentId": "",
        "document": {
            "version": "2.9.0", "theme": "default", "language": "ko-KR",
            "id": _docid(),
            "components": [
                {
                    "id": _uid(), "layout": "default",
                    "title": [{"id": _uid(), "nodes": [{"id": _uid(), "value": title, "@ctype": "textNode"}], "@ctype": "paragraph"}],
                    "subTitle": None, "align": "left", "@ctype": "documentTitle"
                }
            ] + components,
            "di": {
                "dif": False,
                "dio": [
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": len(title), "sk": 1}},
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": 100, "sk": 1}}
                ]
            }
        }
    }
    return json.dumps(doc, ensure_ascii=False, separators=(',', ':'))


def make_pop(category_no: int = 6, auto_save_no=None) -> str:
    return json.dumps({
        "configuration": {
            "openType": 2, "commentYn": True, "searchYn": True,
            "sympathyYn": False, "scrapType": 2, "outSideAllowYn": True,
            "twitterPostingYn": False, "facebookPostingYn": False, "cclYn": False
        },
        "populationMeta": {
            "categoryId": category_no, "logNo": None, "directorySeq": 21,
            "directoryDetail": None, "mrBlogTalkCode": None,
            "postWriteTimeType": "now", "tags": "",
            "moviePanelParticipation": False, "greenReviewBannerYn": False,
            "continueSaved": False, "noticePostYn": False, "autoByCategoryYn": False,
            "postLocationSupportYn": False, "postLocationJson": None,
            "prePostDate": None, "thisDayPostInfo": None, "scrapYn": False,
            "autoSaveNo": auto_save_no
        },
        "editorSource": "be1Cpvv4FXCRGUPtcaiPhQ=="
    }, ensure_ascii=False, separators=(',', ':'))
