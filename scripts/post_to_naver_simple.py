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


async def dismiss_draft_popup(page):
    """'작성 중인 글이 있습니다' 팝업 — 취소 클릭 (새 글 작성)"""
    for _ in range(10):
        pos = await page.evaluate("""
        () => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
                const txt = (btn.innerText || btn.textContent || '').trim();
                if (txt === '취소') {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }
        """)
        if pos:
            await page.mouse.click(pos['x'], pos['y'])
            print("  [팝업] '작성 중인 글' → 취소 클릭 (새 글 작성)")
            await page.wait_for_timeout(1500)
            return True
        await page.wait_for_timeout(300)
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

        # '작성 중인 글' 팝업 처리 (반드시 취소 선택 — 확인 시 이전 글 로드)
        await dismiss_draft_popup(page)

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
    """본문 텍스트 입력 — keyboard.type 방식 (포커스 유지, 청크 단위)"""
    # 1. 본문 첫 텍스트 컴포넌트 클릭으로 포커스 획득
    body_comp = await page.query_selector(".se-component.se-text")
    if body_comp:
        box = await body_comp.bounding_box()
        await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
    else:
        await page.mouse.click(600, 370)
    await page.wait_for_timeout(600)

    # 2. 청크 단위 입력 (줄바꿈은 Enter 키)
    lines = body.split('\n')
    total = len(lines)
    chunk_size = 30  # 30줄씩 처리

    for chunk_start in range(0, total, chunk_size):
        chunk = lines[chunk_start:chunk_start + chunk_size]
        chunk_end = min(chunk_start + chunk_size, total)

        for i, line in enumerate(chunk):
            line_idx = chunk_start + i
            if line:
                await page.keyboard.type(line, delay=8)
            if line_idx < total - 1:
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(30)

        # 청크 완료 후 글자수 확인
        chars = await page.evaluate("""
            () => {
                const paras = document.querySelectorAll('.se-text-paragraph');
                return Array.from(paras).reduce((s, el) => s + (el.innerText||'').replace(/[\\s\\n]/g,'').length, 0);
            }
        """)
        title_chars = await page.evaluate("""
            () => (document.querySelector('.se-title-text')?.innerText||'').replace(/[\\s\\n]/g,'').length
        """)
        body_chars_so_far = chars - title_chars
        print(f"    본문 진행: {chunk_end}/{total}줄, 에디터 본문 {body_chars_so_far}자")

        # 포커스 손실 감지
        if body_chars_so_far < 5 and chunk_end > 30:
            print("    ⚠️ 포커스 손실 감지 — 재설정 후 재입력")
            if body_comp:
                await page.mouse.click(box['x'] + 50, box['y'] + 50)
            await page.wait_for_timeout(400)

    await page.wait_for_timeout(800)

    # 최종 글자수
    final_chars = await page.evaluate("""
        () => {
            const paras = document.querySelectorAll('.se-text-paragraph');
            return Array.from(paras).reduce((s, el) => s + (el.innerText||'').replace(/[\\s\\n]/g,'').length, 0);
        }
    """)
    title_chars = await page.evaluate("""
        () => (document.querySelector('.se-title-text')?.innerText||'').replace(/[\\s\\n]/g,'').length
    """)
    body_chars = final_chars - title_chars
    print(f"  본문 입력 완료: {body_chars}자")
    return body_chars


async def publish(page) -> str | None:
    """발행 — 우상단 publish_btn 클릭 → 패널 → confirm_btn 클릭"""
    # 1. 우상단 발행 버튼 (publish_btn__m9KHH)
    pub_btn = await page.query_selector(".publish_btn__m9KHH")
    if not pub_btn:
        print("  ❌ 발행 버튼(.publish_btn__m9KHH) 없음")
        await page.screenshot(path="/tmp/naver_simple_fail.png")
        return None

    await pub_btn.click()
    print("  발행 버튼 클릭")
    await page.wait_for_timeout(3000)
    await page.screenshot(path="/tmp/naver_simple_panel.png")

    # 2. 패널 내 확인(발행) 버튼 (confirm_btn__WEaBq) 대기
    confirm_btn = None
    for attempt in range(3):
        confirm_btn = await page.query_selector(".confirm_btn__WEaBq")
        if confirm_btn:
            box = await confirm_btn.bounding_box()
            if box and box['width'] > 0:
                break
        print(f"  패널 미열림 ({attempt+1}/3) — 재클릭")
        await pub_btn.click()
        await page.wait_for_timeout(3000)

    if not confirm_btn:
        print("  ❌ 확인 버튼(.confirm_btn__WEaBq) 없음")
        await page.screenshot(path="/tmp/naver_simple_fail.png")
        return None

    box = await confirm_btn.bounding_box()
    print(f"  확인 버튼 클릭 @ ({box['x']:.0f},{box['y']:.0f})")
    await confirm_btn.click()

    # 3. 발행 완료 대기 — URL에 logNo 포함 또는 PostView로 이동 (최대 60초)
    for i in range(60):
        await page.wait_for_timeout(1000)
        cur_url = page.url
        if "PostView" in cur_url or ("logNo" in cur_url and "postwrite" not in cur_url):
            return cur_url
        if i > 3 and "postwrite" not in cur_url and "blog.naver.com" in cur_url:
            # 에러 페이지 감지
            page_text = await page.evaluate("() => document.body.innerText || ''")
            if "페이지를 찾을 수 없습니다" in page_text or "에러가 발생했습니다" in page_text:
                print(f"  ⚠️ 네이버 서버 에러 — URL: {cur_url}")
                await page.screenshot(path="/tmp/naver_simple_fail.png")
                return None
            if cur_url != WRITE_URL:
                return cur_url
    cur_url = page.url
    if "logNo" in cur_url:
        return cur_url
    print(f"  타임아웃(60s) — 최종 URL: {cur_url}")
    await page.screenshot(path="/tmp/naver_simple_fail.png")
    return None


async def main():
    title = POST_TITLE

    if not title:
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

    # 제목 길이 검증 (네이버 한도 ~38자)
    if len(title) > 38:
        title = title[:38]
        print(f"  [경고] 제목 38자로 자름: {title}")

    print(f"\n[네이버 발행 시작]")
    print(f"  제목: {title[:50]}")
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
        await type_title(page, title)

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
                "title": title,
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
