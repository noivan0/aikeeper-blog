#!/usr/bin/env python3
"""
naver_lib/document.py — SE 에디터 documentModel 컴포넌트 빌더
"""
import uuid
import json
import random
import string

# 폰트 사이즈 코드 (네이버 SE 실측 확정 — 2026-04-16 직접 실측)
# 실제 발행 포스팅 CSS 실측:
#   se-fs-fs11=11px / se-fs-fs13=13px / se-fs-fs16=16px / se-fs-fs19=19px
#   fs15 = CSS 클래스 미정의 → 기본값(빈 클래스=11px) 렌더링
# 노이반님 지시: 본문 16pt, 소제목 19pt, 검은색
FS = {"tiny": "fs11", "normal": "fs16", "heading": "fs19", "large": "fs28"}
# 폰트 색상: 검은색
FONT_COLOR = "#000000"


def _uid() -> str:
    return "SE-" + str(uuid.uuid4())


def _docid() -> str:
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=26))


def para(text: str, bold: bool = False, fs: str = FS["normal"], color: str = FONT_COLOR) -> dict:
    style = {"fontSizeCode": fs, "color": color, "@ctype": "nodeStyle"}
    if bold:
        style["bold"] = True
    return {
        "id": _uid(),
        "nodes": [{"id": _uid(), "value": text, "style": style, "@ctype": "textNode"}],
        "@ctype": "paragraph"
    }


def para_link(text: str, url: str) -> dict:
    # 링크 텍스트: 본문 폰트 fs16 + 검은색
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
    return para("", fs=FS["normal"])  # fs16


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


def brand_card_comp(title: str, desc: str, thumb_url: str, link: str) -> dict:
    """
    브랜드커넥트 상품 카드 컴포넌트.
    OGLink sign 없이 구현 — 상품명 + 설명 + 링크 버튼 텍스트 조합.
    """
    return text_comp([
        para("━" * 20, fs=FS["tiny"]),
        para(title, bold=True, fs=FS["heading"]),
        para(desc, fs=FS["normal"]),
        para_link("👉 지금 네이버에서 확인하기 →", link),
        para("━" * 20, fs=FS["tiny"]),
    ])
