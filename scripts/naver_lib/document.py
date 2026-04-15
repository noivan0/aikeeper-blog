#!/usr/bin/env python3
"""
naver_lib/document.py — SE 에디터 documentModel 컴포넌트 빌더
"""
import uuid
import json
import random
import string

# 폰트 사이즈 코드 (네이버 SE 실측 기반)
# normal=16pt(본문), heading=20pt(소제목) — 노이반님 지시 2026-04-15
# 네이버 SE 실제 렌더링 기준 (2026-04-12 역공학 확정)
# fs11=13px(파트너스고지), fs13=15px(본문), fs19=20px(소제목), fs28=23px(대제목)
# ⚠️ fs16/fs20 사용 금지: fs20=11px로 렌더링됨
FS = {"tiny": "fs11", "normal": "fs13", "heading": "fs19", "large": "fs28"}


def _uid() -> str:
    return "SE-" + str(uuid.uuid4())


def _docid() -> str:
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=26))


def para(text: str, bold: bool = False, fs: str = "fs16") -> dict:
    style = {"fontSizeCode": fs, "@ctype": "nodeStyle"}
    if bold:
        style["bold"] = True
    return {
        "id": _uid(),
        "nodes": [{"id": _uid(), "value": text, "style": style, "@ctype": "textNode"}],
        "@ctype": "paragraph"
    }


def para_link(text: str, url: str) -> dict:
    # 링크 텍스트도 본문 폰트(fs16) 적용
    return {
        "id": _uid(),
        "nodes": [{
            "id": _uid(), "value": text,
            "style": {"fontSizeCode": "fs16", "@ctype": "nodeStyle"},
            "link": {"url": url, "@ctype": "urlLink"},
            "@ctype": "textNode"
        }],
        "@ctype": "paragraph"
    }


def empty_para() -> dict:
    return para("", fs="fs16")


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
