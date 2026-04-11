#!/usr/bin/env python3
"""
네이버 블로그 API 발행 v6 — 이미지/OG링크/스타일 완전 지원
─────────────────────────────────────────────────────────────
핵심 흐름:
1. Playwright 에디터 로드 → tokenId / se-auth 캡처
2. 쿠팡 상품 이미지를 로컬에 다운로드 → #hidden-file input으로 업로드
3. 업로드 결과(src/path) 수집 → image 컴포넌트 구성
4. oglink API 호출 → oglinkSign 수집
5. documentModel JSON 구성 (text + image + oglink 컴포넌트)
6. RabbitAutoSaveWrite → autoSaveNo
7. RabbitWrite → 발행

확정 사실 (재조사 금지):
- file input: #hidden-file (이미지 버튼 클릭 후 생성)
- 업로드 API: blog.upphoto.naver.com (XML 응답)
- 이미지 src: blogfiles.pstatic.net
- represent: True (첫 번째만), False (나머지)
- se-authorization: platform.editor.naver.com 요청 헤더
- not acceptable: documentModel 구조 오류 시 (크기 아님)
- page.evaluate 배열 인자로 큰 데이터 전달 가능 (window 주입도 OK)

환경변수:
  NAVER_ID, NAVER_PW
  NAVER_BLOG_ID (default: prosweep)
  NAVER_CATEGORY_NO (default: 6)
  NAVER_TITLE
  NAVER_BODY_PATH 또는 NAVER_BODY
  NAVER_PRODUCTS_JSON (JSON 배열, shortenUrl 또는 coupang_url 포함)
"""
import os, sys, json, time, uuid, asyncio, random, string, urllib.parse, re, tempfile, struct, zlib
from pathlib import Path
from urllib.request import urlretrieve, Request, urlopen

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":99"

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

from playwright.async_api import async_playwright

NAVER_ID      = os.environ.get("NAVER_ID", "")
NAVER_PW      = os.environ.get("NAVER_PW", "")
BLOG_ID       = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO   = int(os.environ.get("NAVER_CATEGORY_NO", "6"))
POST_TITLE    = os.environ.get("NAVER_TITLE", "")
BODY_PATH     = os.environ.get("NAVER_BODY_PATH", "")
PRODUCTS_JSON = os.environ.get("NAVER_PRODUCTS_JSON", "[]")
SESSION_FILE  = str(Path(__file__).parent.parent / "naver_session.json")
LOG_PATH      = str(Path(__file__).parent.parent / "results" / "naver_simple_posts.jsonl")

WRITE_URL        = f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}"
AUTOSAVE_URL     = "https://blog.naver.com/RabbitAutoSaveWrite.naver"
RABBIT_WRITE_URL = "https://blog.naver.com/RabbitWrite.naver"
OGLINK_API       = "https://platform.editor.naver.com/api/blogpc001/v1/oglink"

# 실제 네이버 SE 모바일 렌더링 역공학 (2026-04-12, 100개 포스팅 분석)
# 상위 노출 포스팅 실제 폰트:
#   se-fs-fs11 → 13px (파트너스고지/해시태그)
#   se-fs-fs13 → 15px (본문 — 상위노출 포스팅 실제 값)
#   se-fs-fs19 → 20px (소제목 heading)
#   se-fs-(빈값) → 20px (소제목, se-fs-fs19와 동일 크기)
#   se-fs-fs28 → 23px (대제목)
# se-fs-fs20 → 11px (절대 사용 금지)
FS = {"tiny": "fs11", "normal": "fs13", "heading": "fs19", "large": "fs28"}


def _uid():
    return "SE-" + str(uuid.uuid4())


def _docid():
    return "".join(random.choices(string.digits + string.ascii_uppercase, k=26))


# ── 컴포넌트 빌더 ────────────────────────────────────────────────────────────

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
    return {
        "id": _uid(),
        "nodes": [{
            "id": _uid(), "value": text,
            "style": {"fontSizeCode": "fs13", "@ctype": "nodeStyle"},
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
                thumb_url: str, link: str) -> dict:
    return {
        "id": _uid(),
        "layout": "large_image",
        "title": title,
        "domain": "link.coupang.com",
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


def build_document_model(title: str, components: list) -> str:
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


def make_pop(auto_save_no=None) -> str:
    return json.dumps({
        "configuration": {
            "openType": 2, "commentYn": True, "searchYn": True,
            "sympathyYn": False, "scrapType": 2, "outSideAllowYn": True,
            "twitterPostingYn": False, "facebookPostingYn": False, "cclYn": False
        },
        "populationMeta": {
            "categoryId": CATEGORY_NO, "logNo": None, "directorySeq": 21,
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


# ── 이미지 다운로드 ────────────────────────────────────────────────────────

def download_image(url: str, dest_dir: str, idx: int) -> str | None:
    """이미지 URL을 로컬에 다운로드. 실패 시 None 반환."""
    try:
        ext = url.split('?')[0].rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            ext = 'jpg'
        dest = os.path.join(dest_dir, f"product_{idx}.{ext}")
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.coupang.com/',
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


# ── 본문 → 컴포넌트 변환 ─────────────────────────────────────────────────

def parse_body_to_sections(body: str, og_map: dict) -> list:
    """
    본문을 SE 컴포넌트 목록으로 변환.
    - 쿠팡 링크 줄 → [IMAGE_UPLOAD_MARKER:url] + oglink 컴포넌트
    - 섹션 제목 → bold + fs20 (heading)
    - 해시태그/고지 → fs14
    - 나머지 → fs16

    반환: (컴포넌트 목록, 이미지_업로드_URL_목록)
    """
    LINK_PAT = re.compile(r'https://link\.coupang\.com/\S+')

    # 이미지 업로드가 필요한 URL 목록 (순서대로)
    image_upload_urls = []

    # 섹션 단위로 줄 묶기
    sections = []   # (type, content)
    # type: 'lines' | 'link'
    current_lines = []

    def flush():
        if current_lines:
            sections.append(('lines', list(current_lines)))
            current_lines.clear()

    for line in body.split('\n'):
        stripped = line.strip()
        m = LINK_PAT.search(stripped)
        if m:
            coupang_url = m.group(0).rstrip('.,)')
            flush()
            sections.append(('link', coupang_url))
        else:
            current_lines.append(line)
    flush()

    # 컴포넌트 조립
    components = []
    first_image = True

    for sec_type, sec_content in sections:
        if sec_type == 'link':
            url = sec_content
            # 이미지 업로드 마커 (실제 업로드는 Playwright에서)
            image_upload_urls.append(url)
            components.append({'_type': 'IMAGE_MARKER', '_url': url, '_is_first': first_image})
            first_image = False

            # OG카드
            if url in og_map:
                components.append({'_type': 'OGLINK', '_url': url})

        else:  # 'lines'
            paras = []
            for line in sec_content:
                s = line.strip()
                if not s:
                    paras.append(empty_para())
                    continue

                # 파트너스 고지 / 해시태그
                if '파트너스 활동' in s or s.startswith('📢') or (s.startswith('#') and s.count('#') >= 3):
                    paras.append(para(s, fs=FS["tiny"]))
                    continue

                # 소제목 감지: 이모지(🛒✅⚠️📌🎯💡🔍📊) 시작 OR "—" 포함 + 어미 없는 명사형
                HEADING_EMOJIS = ('🛒', '✅', '⚠', '📌', '🎯', '💡', '🔍', '📊', '🏷', '💰', '👍', '❌', '🔑', '📋', '🎁')
                is_heading = (
                    5 <= len(s) <= 45
                    and not any(s.endswith(e) for e in ('요.', '요!', '요?', '네요.', '다.', '다!', '습니다.', '어요.', '어요!', '더라고요.'))
                    and (
                        any(s.startswith(em) for em in HEADING_EMOJIS)
                        or '—' in s
                        or any(c in s for c in ['가이드', '비교', '정리', '선택', '체크', '기준', '방법', '포인트', '결론'])
                    )
                )
                if is_heading:
                    paras.append(para(s, bold=True, fs=FS["heading"]))
                else:
                    paras.append(para(s, fs=FS["normal"]))

            if paras:
                components.append({'_type': 'TEXT', '_paras': paras})

    return components, image_upload_urls


# ── Playwright 업로드 + 발행 ─────────────────────────────────────────────

async def publish(title: str, body: str, product_links: list, extra_image_urls: list | None = None) -> str | None:
    tmpdir = tempfile.mkdtemp()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        if Path(SESSION_FILE).exists():
            ctx_kwargs["storage_state"] = SESSION_FILE

        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        captured = {"token_id": "", "se_auth": "", "se_app_id": ""}

        async def on_req(req):
            if "RabbitWrite.naver" in req.url and req.method == "POST":
                pp = urllib.parse.parse_qs(req.post_data or "", keep_blank_values=True)
                if pp.get("tokenId"):
                    captured["token_id"] = pp["tokenId"][0]
            if "oglink" in req.url and "platform.editor" in req.url:
                if not captured["se_auth"]:
                    captured["se_auth"]   = req.headers.get("se-authorization", "")
                    captured["se_app_id"] = req.headers.get("se-app-id", "")

        context.on("request", on_req)
        page = await context.new_page()

        await page.goto(WRITE_URL, timeout=40000)
        try: await page.wait_for_load_state("networkidle", timeout=15000)
        except: pass
        await page.wait_for_timeout(3000)

        # 로그인 체크
        if "nidlogin" in page.url or "login" in page.url.lower():
            print("  세션 만료 — 재로그인")
            await page.goto("https://nid.naver.com/nidlogin.login?mode=form", timeout=20000)
            await page.wait_for_timeout(2000)
            await page.locator("#id").click()
            for c in NAVER_ID:
                await page.keyboard.type(c); await asyncio.sleep(0.12)
            await page.locator("#pw").click()
            for c in NAVER_PW:
                await page.keyboard.type(c); await asyncio.sleep(0.10)
            await page.wait_for_timeout(1000)
            btn = await page.query_selector(".btn_login")
            if btn: await btn.click()
            await page.wait_for_timeout(6000)
            if "nidlogin" in page.url:
                print("  ❌ 로그인 실패"); await browser.close(); return None
            await context.storage_state(path=SESSION_FILE)
            await page.goto(WRITE_URL, timeout=40000)
            try: await page.wait_for_load_state("networkidle", timeout=15000)
            except: pass
            await page.wait_for_timeout(3000)

        # 팝업 취소
        for _ in range(12):
            pos = await page.evaluate("() => { for (const b of document.querySelectorAll('button')) { if ((b.innerText||'').trim()==='취소') { const r=b.getBoundingClientRect(); if(r.width>0) return {x:r.x+r.width/2,y:r.y+r.height/2}; } } return null; }")
            if pos:
                await page.mouse.click(pos['x'], pos['y']); await page.wait_for_timeout(1500)
                print("  [팝업] 취소 ✅"); break
            await page.wait_for_timeout(300)

        try:
            await page.wait_for_selector(".se-component.se-text, .se-documentTitle", timeout=25000)
        except:
            print("  ❌ 에디터 로드 실패"); await browser.close(); return None
        await page.wait_for_timeout(1000)

        # ── 1단계: tokenId + se-auth 캡처 ──────────────────────────────
        # 제목에 더미 입력
        tc = await page.query_selector(".se-title-text")
        if tc:
            box = await tc.bounding_box()
            await page.mouse.click(box['x']+50, box['y']+box['height']/2)
        await page.keyboard.type("_", delay=10)

        # 본문에 쿠팡 링크 타이핑 → OG 트리거 + se-auth 캡처
        be = await page.query_selector(".se-component.se-text")
        if be:
            box = await be.bounding_box()
            await page.mouse.click(box['x']+50, box['y']+box['height']/2)
        if product_links:
            await page.keyboard.type(product_links[0], delay=5)
            await page.keyboard.press("Enter")
            print("  se-auth 캡처 대기 (9s)...")
            await page.wait_for_timeout(9000)
        else:
            await page.wait_for_timeout(5000)

        # 발행 버튼으로 tokenId 캡처
        pub_btn = await page.query_selector(".publish_btn__m9KHH")
        if pub_btn:
            await pub_btn.click(); await page.wait_for_timeout(3000)
            confirm = await page.query_selector(".confirm_btn__WEaBq")
            if confirm:
                await confirm.click(); await page.wait_for_timeout(6000)

        token_id = captured["token_id"]
        se_auth  = captured["se_auth"]
        se_app_id = captured["se_app_id"]
        print(f"  tokenId: {'있음' if token_id else '없음'}")
        print(f"  se-auth: {'있음' if se_auth else '없음'}")

        if not token_id:
            print("  ❌ tokenId 없음"); await browser.close(); return None

        # ── 2단계: 쿠팡 썸네일 다운로드 ───────────────────────────────
        # 먼저 oglink API로 썸네일 URL 수집
        og_map = {}
        if product_links and se_auth:
            print(f"  OG카드 수집 ({len(product_links)}개)...")
            for link in product_links:
                og_r = await page.evaluate(
                    "([api, link, sa, sid]) => fetch(api+'?url='+encodeURIComponent(link), {credentials:'include', headers:{'se-authorization':sa,'se-app-id':sid,'accept':'application/json'}}).then(r=>r.json()).catch(e=>({error:e.message}))",
                    [OGLINK_API, link, se_auth, se_app_id]
                )
                if og_r and og_r.get("oglinkSign"):
                    s = og_r.get("oglink", {}).get("summary", {})
                    og_map[link] = {
                        "title": s.get("title", ""),
                        "description": s.get("description", ""),
                        "thumb_url": s.get("image", {}).get("url", ""),
                        "oglinkSign": og_r["oglinkSign"],
                    }
                    print(f"    ✅ OG: {s.get('title','')[:35]}")
                else:
                    print(f"    ⚠️ OG 실패: {link[:50]}")

        # 썸네일 다운로드 (업로드용)
        thumb_local = {}  # link → 로컬 파일 경로
        for link, og in og_map.items():
            turl = og.get("thumb_url", "")
            if turl:
                idx = list(og_map.keys()).index(link)
                local = download_image(turl, tmpdir, idx)
                if local:
                    thumb_local[link] = local

        # extra_image_urls: 추가 상품 이미지 (이미지 밀도 확보용)
        # 쿠팡 API productImage URL → 직접 다운로드
        extra_local = []
        if extra_image_urls:
            import requests as _req
            for ei, eurl in enumerate(extra_image_urls[:4]):
                try:
                    r = _req.get(eurl, timeout=8, allow_redirects=True,
                        headers={"Referer":"https://www.coupang.com/","User-Agent":"Mozilla/5.0"})
                    if r.status_code == 200 and len(r.content) > 10000:
                        ext = "jpg"
                        save_path = os.path.join(tmpdir, f"extra_{ei}.{ext}")
                        with open(save_path, "wb") as f:
                            f.write(r.content)
                        extra_local.append(save_path)
                        print(f"    ✅ 추가이미지 {ei+1}: {len(r.content)//1024}KB")
                except Exception as e:
                    print(f"    ⚠️ 추가이미지 실패: {e}")
            print(f"  추가 이미지 확보: {len(extra_local)}개 (총 {len(thumb_local)+len(extra_local)}개)")

        print(f"  다운로드된 이미지: {len(thumb_local)}개 (+ 추가 {len(extra_local)}개)")

        # ── 3단계: 새 에디터 페이지로 이동 ────────────────────────────
        await page.goto(WRITE_URL, timeout=40000)
        try: await page.wait_for_load_state("networkidle", timeout=15000)
        except: pass
        await page.wait_for_timeout(3000)

        for _ in range(12):
            pos = await page.evaluate("() => { for (const b of document.querySelectorAll('button')) { if ((b.innerText||'').trim()==='취소') { const r=b.getBoundingClientRect(); if(r.width>0) return {x:r.x+r.width/2,y:r.y+r.height/2}; } } return null; }")
            if pos:
                await page.mouse.click(pos['x'], pos['y']); await page.wait_for_timeout(1500); break
            await page.wait_for_timeout(300)

        await page.wait_for_selector(".se-component.se-text", timeout=20000)
        await page.wait_for_timeout(1000)

        # ── 4단계: 이미지 업로드 (Playwright file input) ───────────────
        uploaded_images = {}  # link → image 컴포넌트 데이터

        # 본문 분석 → 이미지 마커 위치 파악
        section_comps, image_upload_urls = parse_body_to_sections(body, og_map)
        image_upload_urls = [u for u in image_upload_urls if u in thumb_local]

        if image_upload_urls:
            print(f"  이미지 업로드 ({len(image_upload_urls)}개)...")
            # 에디터 본문에 커서 위치 (이미지 버튼 활성화 필요)
            be = await page.query_selector(".se-component.se-text")
            if be:
                box = await be.bounding_box()
                await page.mouse.click(box['x']+50, box['y']+box['height']/2)
            await page.keyboard.type(".", delay=5)  # 커서 활성화

            first_upload = True
            for link in image_upload_urls:
                local_path = thumb_local[link]
                # 이미지 버튼 클릭
                img_btn = await page.query_selector(".se-image-toolbar-button")
                if not img_btn:
                    print(f"    이미지 버튼 없음 → 스킵")
                    continue
                box = await img_btn.bounding_box()
                await page.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2)
                await page.wait_for_timeout(1000)

                fi = await page.query_selector("input[type=file]")
                if not fi:
                    print(f"    file input 없음 → 스킵")
                    continue

                # 업로드 응답 캡처
                upload_resp = []
                async def on_upload_resp(resp):
                    if "upphoto.naver.com" in resp.url and resp.request.method == "POST":
                        try:
                            text = await resp.text()
                            upload_resp.append(text)
                        except: pass
                page.on("response", on_upload_resp)

                await fi.set_input_files(local_path)
                print(f"    업로드 중: {os.path.basename(local_path)}...")
                await page.wait_for_timeout(8000)

                page.remove_listener("response", on_upload_resp)

                # 업로드 결과에서 src/path 파싱
                if upload_resp:
                    xml = upload_resp[-1]
                    # XML에서 url 추출: <url>/MjAy...</url>
                    url_m = re.search(r'<url>([^<]+)</url>', xml)
                    if url_m:
                        path_val = url_m.group(1)
                        # XML 응답의 url은 path 값
                        src_url = f"https://blogfiles.pstatic.net{path_val}?type=w1"
                        # width/height 추출
                        w_m = re.search(r'<width>(\d+)</width>', xml)
                        h_m = re.search(r'<height>(\d+)</height>', xml)
                        sz_m = re.search(r'<fileSize>(\d+)</fileSize>', xml)
                        fn_m = re.search(r'<fileName>([^<]+)</fileName>', xml)
                        width  = int(w_m.group(1)) if w_m else 492
                        height = int(h_m.group(1)) if h_m else 492
                        fsize  = int(sz_m.group(1)) if sz_m else 0
                        fname  = fn_m.group(1) if fn_m else os.path.basename(local_path)
                        uploaded_images[link] = {
                            "src": src_url, "path": path_val,
                            "width": width, "height": height,
                            "fileSize": fsize, "fileName": fname,
                            "represent": first_upload
                        }
                        first_upload = False
                        print(f"    ✅ 업로드 완료: {src_url[:60]}")
                    else:
                        print(f"    ⚠️ XML 파싱 실패: {xml[:200]}")
                else:
                    print(f"    ⚠️ 업로드 응답 없음")

        # ── 5단계: documentModel 구성 ──────────────────────────────────
        final_comps = []
        for item in section_comps:
            t = item['_type']
            if t == 'TEXT':
                final_comps.append(text_comp(item['_paras']))
            elif t == 'IMAGE_MARKER':
                link = item['_url']
                if link in uploaded_images:
                    ui = uploaded_images[link]
                    final_comps.append(image_comp(
                        src=ui["src"], path=ui["path"],
                        width=ui["width"], height=ui["height"],
                        filename=ui["fileName"],
                        represent=ui["represent"],
                        file_size=ui["fileSize"]
                    ))
            elif t == 'OGLINK':
                link = item['_url']
                if link in og_map:
                    og = og_map[link]
                    final_comps.append(oglink_comp(
                        og_sign=og["oglinkSign"],
                        title=og["title"],
                        desc=og["description"],
                        thumb_url=og["thumb_url"],
                        link=link
                    ))

        # extra_local 이미지를 업로드하고 문서 앞부분에 삽입
        if extra_local:
            print(f"  추가 이미지 업로드 ({len(extra_local)}개)...")
            extra_uploaded = []
            for ei, local_path in enumerate(extra_local):
                upload_resp2 = []
                async def on_upload_resp2(resp):
                    if "upphoto.naver.com" in resp.url and resp.request.method == "POST":
                        try:
                            text = await resp.text()
                            upload_resp2.append(text)
                        except: pass
                page.on("response", on_upload_resp2)

                img_btn2 = await page.query_selector(".se-image-toolbar-button")
                if img_btn2:
                    box2 = await img_btn2.bounding_box()
                    await page.mouse.click(box2['x']+box2['width']/2, box2['y']+box2['height']/2)
                    await page.wait_for_timeout(800)
                    fi2 = await page.query_selector("input[type=file]")
                    if fi2:
                        await fi2.set_input_files(local_path)
                        print(f"    업로드 중: extra_{ei}.jpg...")
                        await page.wait_for_timeout(8000)

                page.remove_listener("response", on_upload_resp2)

                if upload_resp2:
                    xml = upload_resp2[-1]
                    url_m = re.search(r'<url>([^<]+)</url>', xml)
                    if url_m:
                        path_val = url_m.group(1)
                        src_url = f"https://blogfiles.pstatic.net{path_val}?type=w1"
                        w_m = re.search(r'<width>(\d+)</width>', xml)
                        h_m = re.search(r'<height>(\d+)</height>', xml)
                        sz_m = re.search(r'<fileSize>(\d+)</fileSize>', xml)
                        fn_m = re.search(r'<fileName>([^<]+)</fileName>', xml)
                        extra_uploaded.append({
                            "src": src_url, "path": path_val,
                            "width":  int(w_m.group(1)) if w_m else 492,
                            "height": int(h_m.group(1)) if h_m else 492,
                            "fileSize": int(sz_m.group(1)) if sz_m else 0,
                            "fileName": fn_m.group(1) if fn_m else f"extra_{ei}.jpg",
                        })
                        print(f"    ✅ extra 업로드 완료: {src_url[:60]}")

            # extra 이미지를 본문 중간에 분산 삽입
            if extra_uploaded:
                insert_positions = [len(final_comps)//3, 2*len(final_comps)//3]
                for idx, eu in zip(insert_positions, extra_uploaded):
                    ic = image_comp(
                        src=eu["src"], path=eu["path"],
                        width=eu["width"], height=eu["height"],
                        filename=eu["fileName"],
                        represent=False, file_size=eu["fileSize"]
                    )
                    final_comps.insert(min(idx, len(final_comps)), ic)
                print(f"  추가 이미지 {len(extra_uploaded)}개 본문 중간 삽입 완료")

        doc_str = build_document_model(title, final_comps)
        pop_save = make_pop(auto_save_no=None)
        print(f"  documentModel: {len(doc_str)}자, 컴포넌트 {len(final_comps)+1}개")
        print(f"    이미지 컴포넌트: {sum(1 for c in final_comps if c.get('@ctype')=='image')}개")
        print(f"    OG링크 컴포넌트: {sum(1 for c in final_comps if c.get('@ctype')=='oglink')}개")

        # ── 6단계: 자동저장 ────────────────────────────────────────────
        await page.evaluate("([d, ps]) => { window.__nv_doc=d; window.__nv_ps=ps; }", [doc_str, pop_save])

        autosave_result = await page.evaluate(f"""async () => {{
            const params = new URLSearchParams();
            params.append('blogId', {json.dumps(BLOG_ID)});
            params.append('documentModel', window.__nv_doc);
            params.append('mediaResources', '{{"image":[],"video":[],"file":[]}}');
            params.append('populationParams', window.__nv_ps);
            const resp = await fetch({json.dumps(AUTOSAVE_URL)}, {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: params.toString()
            }});
            return await resp.json();
        }}""")
        print(f"  자동저장: {autosave_result}")

        if not autosave_result or not autosave_result.get("isSuccess"):
            print("  ❌ 자동저장 실패"); await browser.close(); return None

        auto_save_no = autosave_result["result"]["autoSaveNo"]
        print(f"  ✅ autoSaveNo={auto_save_no}")

        # ── 7단계: 발행 ────────────────────────────────────────────────
        pop_pub = make_pop(auto_save_no=auto_save_no)
        await page.evaluate("([pp, t]) => { window.__nv_pp=pp; window.__nv_t=t; }", [pop_pub, token_id])

        publish_result = await page.evaluate(f"""async () => {{
            const params = new URLSearchParams();
            params.append('blogId', {json.dumps(BLOG_ID)});
            params.append('documentModel', window.__nv_doc);
            params.append('mediaResources', '{{"image":[],"video":[],"file":[]}}');
            params.append('populationParams', window.__nv_pp);
            params.append('productApiVersion', 'v1');
            params.append('tokenId', window.__nv_t);
            const resp = await fetch({json.dumps(RABBIT_WRITE_URL)}, {{
                method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: params.toString()
            }});
            const text = await resp.text();
            return {{status: resp.status, body: text.substring(0, 500)}};
        }}""")

        print(f"  발행: {publish_result.get('status')} | {publish_result.get('body','')[:100]}")

        await context.storage_state(path=SESSION_FILE)
        await browser.close()

        result_body = publish_result.get("body", "")
        try:
            rj = json.loads(result_body.strip())
            if rj.get("isSuccess"):
                return rj.get("result", {}).get("redirectUrl", "")
        except: pass

        m = re.search(r'logNo[=:](\d+)', result_body)
        if m:
            return f"https://blog.naver.com/PostView.naver?blogId={BLOG_ID}&logNo={m.group(1)}"

        print(f"  발행 응답: {result_body[:300]}")
        return None


async def main():
    title = POST_TITLE
    if not title:
        print("❌ NAVER_TITLE 필요"); sys.exit(1)
    if len(title) > 38:
        title = title[:38]

    body = ""
    if BODY_PATH and Path(BODY_PATH).exists():
        body = Path(BODY_PATH).read_text(encoding='utf-8')
    else:
        body = os.environ.get("NAVER_BODY", "")
    if not body:
        print("❌ 본문 없음"); sys.exit(1)

    product_links = []
    try:
        products = json.loads(PRODUCTS_JSON)
        for prod in products:
            url = prod.get("shortenUrl") or prod.get("coupang_url") or prod.get("url", "")
            if url and "coupang.com" in url:
                product_links.append(url)
    except: pass

    # 본문에서도 추출
    for bl in re.findall(r'https://link\.coupang\.com/\S+', body):
        bl = bl.rstrip('.,)')
        if bl not in product_links:
            product_links.append(bl)

    # 추가 이미지 URL (naver_homefeed_runner에서 전달)
    extra_image_urls = []
    try:
        raw_extra = os.environ.get("EXTRA_IMAGE_URLS", "[]")
        extra_image_urls = [u for u in json.loads(raw_extra) if u]
    except: pass

    print(f"\n[네이버 API 발행 v6]")
    print(f"  제목: {title[:50]}")
    print(f"  본문: {len(body)}자")
    print(f"  상품링크: {len(product_links)}개")
    print(f"  추가이미지: {len(extra_image_urls)}개")

    result_url = await publish(title, body, product_links, extra_image_urls=extra_image_urls)

    if result_url:
        print(f"\n✅ 발행 성공!")
        print(f"  URL: {result_url}")
        out = {
            "success": True, "naver_url": result_url, "title": title,
            "body_chars": len(body), "og_links": len(product_links),
            "method": "api_v6", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        Path(LOG_PATH).parent.mkdir(exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(result_url)
    else:
        print("\n❌ 발행 실패"); sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
