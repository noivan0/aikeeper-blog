#!/usr/bin/env python3
"""
naver_lib/uploader.py — 이미지 다운로드 + 네이버 블로그 업로드
"""
import os
import re
from urllib.request import urlopen, Request


def download_image(url: str, dest_dir: str, idx: int) -> str | None:
    """이미지 URL을 로컬에 다운로드. 실패 시 None 반환."""
    try:
        ext = url.split('?')[0].rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            ext = 'jpg'
        dest = os.path.join(dest_dir, f"product_{idx}.{ext}")
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.naver.com/',
        })
        with urlopen(req, timeout=15) as resp, open(dest, 'wb') as f:
            f.write(resp.read())
        size = os.path.getsize(dest)
        if size < 200:
            return None
        print(f"    이미지 다운로드: {dest} ({size}bytes)")
        return dest
    except Exception as e:
        print(f"    이미지 다운로드 실패: {url[:60]} → {e}")
        return None


async def upload_image_file(page, local_path: str) -> dict | None:
    """
    Playwright를 통해 네이버 블로그 에디터에 이미지 파일 업로드.
    성공 시 {"src", "path", "width", "height", "fileSize", "fileName"} 반환.
    실패 시 None 반환.
    """
    import asyncio

    # 이미지 버튼 클릭 (없으면 JS로 강제 노출 시도)
    img_btn = await page.query_selector(".se-image-toolbar-button")
    if not img_btn:
        # JS로 툴바 이미지 버튼 강제 클릭 시도
        clicked = await page.evaluate("""() => {
            const selectors = [
                '.se-image-toolbar-button',
                '[data-action="insertImage"]',
                '.se-toolbar-btn-image',
                'button[title="사진"]',
                'button[aria-label="사진"]',
            ];
            for (const sel of selectors) {
                const btn = document.querySelector(sel);
                if (btn) { btn.click(); return true; }
            }
            return false;
        }""")
        if not clicked:
            print(f"    이미지 버튼 없음 (JS fallback도 실패) → 스킵")
            return None
        await page.wait_for_timeout(1000)
    else:
        box = await img_btn.bounding_box()
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        await page.wait_for_timeout(1000)

    fi = await page.query_selector("input[type=file]")
    if not fi:
        print(f"    file input 없음 → 스킵")
        return None

    upload_resp = []

    async def on_upload_resp(resp):
        if "upphoto.naver.com" in resp.url and resp.request.method == "POST":
            try:
                text = await resp.text()
                upload_resp.append(text)
            except Exception:
                pass

    page.on("response", on_upload_resp)
    await fi.set_input_files(local_path)
    print(f"    업로드 중: {os.path.basename(local_path)}...")
    await page.wait_for_timeout(8000)
    page.remove_listener("response", on_upload_resp)

    if not upload_resp:
        print(f"    ⚠️ 업로드 응답 없음")
        return None

    xml = upload_resp[-1]
    url_m = re.search(r'<url>([^<]+)</url>', xml)
    if not url_m:
        print(f"    ⚠️ XML 파싱 실패: {xml[:200]}")
        return None

    path_val = url_m.group(1)
    src_url = f"https://blogfiles.pstatic.net{path_val}?type=w1"
    w_m = re.search(r'<width>(\d+)</width>', xml)
    h_m = re.search(r'<height>(\d+)</height>', xml)
    sz_m = re.search(r'<fileSize>(\d+)</fileSize>', xml)
    fn_m = re.search(r'<fileName>([^<]+)</fileName>', xml)

    result = {
        "src": src_url,
        "path": path_val,
        "width": int(w_m.group(1)) if w_m else 492,
        "height": int(h_m.group(1)) if h_m else 492,
        "fileSize": int(sz_m.group(1)) if sz_m else 0,
        "fileName": fn_m.group(1) if fn_m else os.path.basename(local_path),
    }
    print(f"    ✅ 업로드 완료: {src_url[:60]}")
    return result
