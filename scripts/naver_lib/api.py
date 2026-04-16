#!/usr/bin/env python3
"""
naver_lib/api.py — 네이버 블로그 API 호출 (OGLink / AutoSave / RabbitWrite)
"""
import json

OGLINK_API       = "https://platform.editor.naver.com/api/blogpc001/v1/oglink"
AUTOSAVE_URL     = "https://blog.naver.com/RabbitAutoSaveWrite.naver"
RABBIT_WRITE_URL = "https://blog.naver.com/RabbitWrite.naver"


async def oglink_fetch(page, link: str, se_auth: str, se_app_id: str) -> dict | None:
    """
    OGLink API 호출. 성공 시 {"title", "description", "thumb_url", "oglinkSign"} 반환.
    """
    og_r = await page.evaluate(
        "([api, link, sa, sid]) => fetch(api+'?url='+encodeURIComponent(link), "
        "{credentials:'include', headers:{'se-authorization':sa,'se-app-id':sid,'accept':'application/json'}})"
        ".then(r=>r.json()).catch(e=>({error:e.message}))",
        [OGLINK_API, link, se_auth, se_app_id]
    )
    if og_r and og_r.get("oglinkSign"):
        s = og_r.get("oglink", {}).get("summary", {})
        return {
            "title": s.get("title", ""),
            "description": s.get("description", ""),
            "thumb_url": s.get("image", {}).get("url", ""),
            "oglinkSign": og_r["oglinkSign"],
        }
    return None


async def autosave(page, blog_id: str, doc_str: str, pop_str: str,
                   uploaded_images: list | None = None) -> dict | None:
    """
    RabbitAutoSaveWrite.naver 호출.
    성공 시 {"autoSaveNo": ...} 포함 dict 반환, 실패 시 None.
    uploaded_images: [{"src":..., "path":..., "fileName":...}, ...] 업로드된 이미지 정보
    """
    # mediaResources: 업로드된 이미지 정보 포함 시 성공률 개선
    if uploaded_images:
        media_res = json.dumps({
            "image": [
                {"src": ui.get("src", ""), "path": ui.get("path", ""),
                 "fileName": ui.get("fileName", "")}
                for ui in uploaded_images
            ],
            "video": [],
            "file": []
        }, ensure_ascii=False)
    else:
        media_res = '{"image":[],"video":[],"file":[]}'

    await page.evaluate(
        "([d, ps, mr]) => { window.__nv_doc=d; window.__nv_ps=ps; window.__nv_mr=mr; }",
        [doc_str, pop_str, media_res]
    )
    result = await page.evaluate(f"""async () => {{
        const params = new URLSearchParams();
        params.append('blogId', {json.dumps(blog_id)});
        params.append('documentModel', window.__nv_doc);
        params.append('mediaResources', window.__nv_mr);
        params.append('populationParams', window.__nv_ps);
        const resp = await fetch({json.dumps(AUTOSAVE_URL)}, {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: params.toString()
        }});
        const text = await resp.text();
        return {{status: resp.status, body: text.substring(0, 2000)}};
    }}""")

    # 상세 로깅 (HTTP 상태코드 + 응답 본문)
    http_status = result.get("status", 0) if result else 0
    raw_body = result.get("body", "") if result else ""
    print(f"  [autosave raw] status={http_status} body={raw_body[:500]}")

    try:
        parsed = json.loads(raw_body)
    except Exception:
        parsed = None

    if parsed and parsed.get("isSuccess"):
        return parsed.get("result", {})
    print(f"  ❌ 자동저장 실패: {parsed or raw_body[:200]}")
    return None


async def rabbit_write(page, blog_id: str, doc_str: str, pop_str: str, token_id: str = "") -> dict:
    """
    RabbitWrite.naver 호출 (실제 발행).
    반환: {"status": int, "body": str}

    확인된 사실 (2026-04-15):
    - tokenId는 세션 쿠키에 내재되어 있어 명시적 전송 불필요
    - tokenId 파라미터를 생략해도 발행 성공
    """
    await page.evaluate(
        "([d, pp]) => { window.__nv_doc=d; window.__nv_pp=pp; }",
        [doc_str, pop_str]
    )
    result = await page.evaluate(f"""async () => {{
        const params = new URLSearchParams();
        params.append('blogId', {json.dumps(blog_id)});
        params.append('documentModel', window.__nv_doc);
        params.append('mediaResources', '{{"image":[],"video":[],"file":[]}}');
        params.append('populationParams', window.__nv_pp);
        params.append('productApiVersion', 'v1');
        // tokenId: 세션 쿠키에 내재 → 생략 가능 (2026-04-15 확인)
        const resp = await fetch({json.dumps(RABBIT_WRITE_URL)}, {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
            body: params.toString()
        }});
        const text = await resp.text();
        return {{status: resp.status, body: text.substring(0, 1000)}};
    }}""")
    return result or {"status": 0, "body": ""}
