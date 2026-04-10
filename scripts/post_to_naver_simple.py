#!/usr/bin/env python3
"""
네이버 블로그 심플 발행 v1 — 홈판 최적화 전용
────────────────────────────────────────────────
복잡한 SE 에디터 조작 없이 순수 텍스트 + 이미지만 사용.
이미지 업로드/표/OG카드 등 불안정 요소 제거.

발행 흐름:
1. 제목 입력
2. 커버 이미지 1장 삽입 (선택적)
3. 본문 텍스트 입력 (줄바꿈 + 해시태그 포함)
4. 발행 버튼 → 확인 버튼
"""
import os, sys, asyncio, json, time
from pathlib import Path

# Xvfb DISPLAY 강제 설정
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":99"

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

from playwright.async_api import async_playwright

# ── 환경변수 ───────────────────────────────────────────
NAVER_ID   = os.environ.get("NAVER_ID", "")
NAVER_PW   = os.environ.get("NAVER_PW", "")
BLOG_ID    = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO = os.environ.get("NAVER_CATEGORY_NO", "6")

POST_TITLE = os.environ.get("NAVER_TITLE", "")
BODY_PATH  = os.environ.get("NAVER_BODY_PATH", "")
COVER_IMG  = os.environ.get("NAVER_COVER_IMAGE_URL", "")   # 커버 이미지 URL (선택)
SESSION_FILE = str(Path(__file__).parent.parent / "naver_session.json")

WRITE_URL = f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}"
LOG_PATH  = str(Path(__file__).parent.parent / "results" / "naver_simple_posts.jsonl")


async def ensure_session(page, context) -> bool:
    """세션 확인 — 에디터 URL로 직접 접근"""
    await page.goto(WRITE_URL, timeout=40000)
    try:
        await page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    await page.wait_for_timeout(3000)
    url = page.url
    if "nidlogin" in url or "login" in url.lower():
        print("  세션 만료 — 로그인 시도")
        return await do_login(page, context)
    editor = await page.query_selector(".se-oglink-toolbar-button, #SE-titleInput, .se-main-container")
    if editor:
        print("  세션 유효 ✅")
        return True
    return False


async def do_login(page, context) -> bool:
    await page.goto("https://nid.naver.com/nidlogin.login?mode=form", timeout=20000)
    await page.wait_for_timeout(2000)
    await page.locator("#id").click()
    for c in NAVER_ID:
        await page.keyboard.type(c)
        await asyncio.sleep(0.12)
    await page.wait_for_timeout(300)
    await page.locator("#pw").click()
    for c in NAVER_PW:
        await page.keyboard.type(c)
        await asyncio.sleep(0.10)
    await page.wait_for_timeout(1000)
    btn = await page.query_selector(".btn_login")
    if btn:
        await btn.click()
    await page.wait_for_timeout(6000)
    if "nidlogin" not in page.url:
        await context.storage_state(path=SESSION_FILE)
        print("  로그인 성공 ✅")
        return True
    print("  로그인 실패 ❌")
    return False


async def load_editor(page) -> bool:
    """에디터 로드 — 최대 3회 재시도"""
    for attempt in range(3):
        await page.goto(WRITE_URL, timeout=40000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        if "nidlogin" in page.url or "login" in page.url.lower():
            print(f"  [에디터 {attempt+1}/3] 로그인 페이지 — 재로그인 필요")
            return False

        # .se-component.se-text 또는 .se-documentTitle 로 에디터 판단
        try:
            await page.wait_for_selector(".se-component.se-text, .se-documentTitle", timeout=30000)
            print(f"  [에디터 {attempt+1}/3] 로드 완료 ✅")
            # 도움말 패널 닫기
            await page.evaluate("""
                () => {
                    document.querySelectorAll('.se-help-panel, [class*="helpPanel"]').forEach(el=>el.style.display='none');
                }
            """)
            await page.wait_for_timeout(500)
            return True
        except Exception:
            print(f"  [에디터 {attempt+1}/3] 타임아웃 — 재시도")
            await page.wait_for_timeout(3000)
    return False


async def type_title(page, title: str):
    """제목 입력 — .se-title-text 위치 클릭"""
    tc = await page.query_selector(".se-title-text, .se-documentTitle")
    if tc:
        box = await tc.bounding_box()
        await page.mouse.click(box['x'] + 200, box['y'] + box['height'] / 2)
    else:
        await page.mouse.click(500, 232)
    await page.wait_for_timeout(400)
    await page.keyboard.type(title, delay=25)
    await page.wait_for_timeout(300)
    print(f"  제목 입력 완료: {title[:40]}")


async def insert_cover_image(page, img_url: str) -> bool:
    """커버 이미지 1장 삽입 — 파일 다운로드 후 업로드"""
    import tempfile, urllib.request as _req
    try:
        suffix = ".jpg"
        for ext in [".png", ".webp", ".gif"]:
            if ext in img_url.lower():
                suffix = ext
                break

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()

        req = _req.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with _req.urlopen(req, timeout=15) as resp:
            with open(tmp_path, 'wb') as f:
                f.write(resp.read())

        print(f"    이미지 다운로드: {tmp_path}")

        # 이미지 버튼 클릭
        img_btn = await page.query_selector(".se-image-toolbar-button")
        if not img_btn:
            return False
        await page.evaluate("btn => btn.click()", img_btn)
        await page.wait_for_timeout(1500)

        # 파일 업로드
        file_input = await page.query_selector("input[type=file][accept*='image']")
        if not file_input:
            # JS로 찾기
            file_input = await page.evaluate_handle("""
                () => document.querySelector('input[type=file]')
            """)

        if file_input and hasattr(file_input, 'set_input_files'):
            await file_input.set_input_files(tmp_path)
            await page.wait_for_timeout(5000)
            print("    이미지 업로드 완료 ✅")
            return True
        else:
            print("    이미지 업로드 입력창 없음 — 스킵")
            return False
    except Exception as e:
        print(f"    이미지 업로드 실패: {e}")
        return False
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


async def type_body(page, body: str):
    """본문 텍스트 입력 — 줄바꿈 단위로 안전하게"""
    # 에디터 본문 영역 클릭 (.se-component.se-text 위치)
    body_comp = await page.query_selector(".se-component.se-text")
    body_click_y = 360  # 기본 fallback
    if body_comp:
        box = await body_comp.bounding_box()
        body_click_y = box['y'] + 10
        await page.mouse.click(box['x'] + 200, body_click_y)
    else:
        await page.mouse.click(500, body_click_y)
    await page.wait_for_timeout(500)

    def count_chars(text_list):
        return sum(len(t.replace(' ','').replace('\n','')) for t in text_list)

    lines = body.split('\n')
    total = len(lines)
    for i, line in enumerate(lines):
        if line:
            await page.keyboard.type(line, delay=12)
        if i < total - 1:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(50)
        # 매 50줄마다 글자수 확인 (.se-text-paragraph 기준)
        if i > 0 and i % 50 == 0:
            texts = await page.evaluate("""
                () => Array.from(document.querySelectorAll('.se-text-paragraph')).map(el=>(el.innerText||'').replace(/\\s/g,'').length)
            """)
            chars = sum(texts)
            print(f"    본문 진행: {i}/{total}줄, 에디터 {chars}자")
            if chars < 5 and i > 30:
                print("    포커스 재설정")
                await page.mouse.click(500, body_click_y + 50)
                await page.wait_for_timeout(300)

    await page.wait_for_timeout(1000)
    # 최종 글자수 — se-text-paragraph 합산
    texts = await page.evaluate("""
        () => Array.from(document.querySelectorAll('.se-text-paragraph')).map(el=>(el.innerText||''))
    """)
    final_chars = sum(len(t.replace('\n','').replace(' ','')) for t in texts)
    # 제목 제외 (제목 글자수는 se-title-text에 있음)
    title_chars = await page.evaluate("""
        () => (document.querySelector('.se-title-text')?.innerText||'').replace(/\\s/g,'').length
    """)
    body_chars = final_chars - title_chars
    print(f"  본문 입력 완료: {body_chars}자 (제목 포함 {final_chars}자)")
    return body_chars


async def publish(page) -> str | None:
    """발행 — 패널 열고 확인 버튼 클릭"""
    # 플로팅 패널 JS로 숨김
    await page.evaluate("""
        () => {
            document.querySelectorAll('.layer_popup__i0QOY, .se-help-panel').forEach(el=>el.style.display='none');
            document.querySelectorAll('.se-floating-layer, .se-search-panel, .se-moment-panel, .se-library-panel').forEach(el=>{el.style.display='none';});
        }
    """)
    await page.wait_for_timeout(800)

    # 발행 버튼 마우스 클릭
    pub_btn = await page.query_selector(".publish_btn__m9KHH, button[class*='publish_btn']")
    if not pub_btn:
        print("  ❌ 발행 버튼 없음")
        await page.screenshot(path="/tmp/naver_simple_fail.png")
        return None

    pub_box = await pub_btn.bounding_box()
    await page.mouse.click(pub_box['x'] + pub_box['width']/2, pub_box['y'] + pub_box['height']/2)
    print(f"  발행 버튼 클릭 @ ({pub_box['x']:.0f},{pub_box['y']:.0f})")
    await page.wait_for_timeout(5000)
    await page.screenshot(path="/tmp/naver_simple_panel.png")

    # confirm 버튼 위치 확인
    async def get_confirm():
        return await page.evaluate("""
            () => {
                const btn = document.querySelector('.confirm_btn__WEaBq, button[class*="confirm_btn"]');
                if (!btn) return null;
                const r = btn.getBoundingClientRect();
                if (r.width === 0) return null;
                return {x: r.x + r.width/2, y: r.y + r.height/2};
            }
        """)

    pos = await get_confirm()
    if not pos:
        print("  패널 미열림 — 재클릭")
        await page.mouse.click(pub_box['x'] + pub_box['width']/2, pub_box['y'] + pub_box['height']/2)
        await page.wait_for_timeout(5000)
        pos = await get_confirm()

    if not pos:
        print("  ❌ confirm 버튼 없음")
        await page.screenshot(path="/tmp/naver_simple_fail.png")
        return None

    # 확인 버튼 클릭 전 패널 열린 상태 재확인
    panel_open = await page.evaluate("""
        () => {
            // 발행 패널 (우측 슬라이드)이 열려있는지 확인
            const panel = document.querySelector('.publish_layer__t6JRl, [class*="publish_layer"], [class*="publishLayer"]');
            return panel ? panel.getBoundingClientRect().width > 0 : false;
        }
    """)
    print(f"  발행 패널 열림: {panel_open}")

    await page.mouse.click(pos['x'], pos['y'])
    print(f"  확인 버튼 클릭 @ ({pos['x']:.0f},{pos['y']:.0f})")

    # 발행 완료 대기 — URL 변화 또는 에러 감지
    for _ in range(30):
        await page.wait_for_timeout(1000)
        cur_url = page.url
        if "PostView" in cur_url or ("logNo" in cur_url and "postwrite" not in cur_url):
            return cur_url
        # 에러 페이지 감지
        if "error" in cur_url.lower() or "찾을 수 없" in (await page.evaluate("() => document.body.innerText||''")):
            print(f"  ⚠️ 에러 페이지 감지: {cur_url}")
            return None
    return None


async def main():
    if not POST_TITLE:
        print("❌ NAVER_TITLE 환경변수 필요")
        sys.exit(1)

    # 본문 읽기
    body = ""
    if BODY_PATH and Path(BODY_PATH).exists():
        body = Path(BODY_PATH).read_text(encoding='utf-8')
    else:
        body = os.environ.get("NAVER_BODY", "")

    if not body:
        print("❌ 본문 없음 (NAVER_BODY_PATH 또는 NAVER_BODY 필요)")
        sys.exit(1)

    print(f"\n[네이버 발행 시작]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  본문: {len(body)}자")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"]
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        if Path(SESSION_FILE).exists():
            ctx_kwargs["storage_state"] = SESSION_FILE

        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await context.new_page()

        # 세션 확인
        session_ok = await ensure_session(page, context)
        if not session_ok:
            await browser.close()
            sys.exit(1)

        # 에디터 로드
        editor_ok = await load_editor(page)
        if not editor_ok:
            await browser.close()
            sys.exit(1)

        # 제목 입력
        await type_title(page, POST_TITLE)

        # 커버 이미지 (선택)
        if COVER_IMG:
            print("  커버 이미지 삽입 중...")
            await insert_cover_image(page, COVER_IMG)
            # 이미지 후 포커스 재설정
            await page.keyboard.press("End")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

        # 본문 입력
        print("  본문 입력 중...")
        chars = await type_body(page, body)

        if chars < 50:
            print(f"  ⚠️ 본문 글자수 부족 ({chars}자) — 발행 중단")
            await page.screenshot(path="/tmp/naver_simple_fail.png")
            await browser.close()
            sys.exit(1)

        # 발행
        await page.screenshot(path="/tmp/naver_simple_before_publish.png")
        print("  발행 중...")
        result_url = await publish(page)

        if result_url:
            print(f"\n✅ 발행 성공!")
            print(f"  URL: {result_url}")
            await context.storage_state(path=SESSION_FILE)

            out = {
                "success": True,
                "naver_url": result_url,
                "title": POST_TITLE,
                "body_chars": chars,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            Path(LOG_PATH).parent.mkdir(exist_ok=True)
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"  로그 저장: {LOG_PATH}")
        else:
            print("\n❌ 발행 실패")
            await page.screenshot(path="/tmp/naver_simple_fail.png")
            await browser.close()
            sys.exit(1)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
