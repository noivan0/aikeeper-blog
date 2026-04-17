#!/usr/bin/env python3
"""
네이버 세션 갱신 도구 v2
─────────────────────────────────────────────────────────────────
전략: IP 차단 우회 + 세션 장기 유지

1. 세션이 유효하면 → 그냥 재사용 (로그인 시도 안 함)
2. 세션이 만료됐을 때만 → 로그인 시도
3. 로그인 실패 시 → Telegram 알림 발송 (노이반님이 수동으로 세션 갱신)

세션 유효 기간: NID_AUT 기준 약 30일 (네이버 정책)
→ 월 1회만 갱신하면 됨
"""
import os, sys, asyncio, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

from playwright.async_api import async_playwright
try:
    from playwright_stealth import Stealth
    USE_STEALTH = True
except ImportError:
    USE_STEALTH = False

NAVER_ID   = os.environ.get("NAVER_ID", "")
NAVER_PW   = os.environ.get("NAVER_PW", "")
BLOG_ID    = os.environ.get("NAVER_BLOG_ID", "prosweep")
SESSION_FILE = Path(__file__).parent.parent / "naver_session.json"
CHROME_PATH  = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
LAUNCH_ARGS  = ["--no-sandbox", "--disable-dev-shm-usage",
                "--ignore-certificate-errors", "--ignore-ssl-errors"]


# ── 세션 유효성 확인 ──────────────────────────────────────────────
async def check_session_valid(page) -> bool:
    """세션 파일로 prosweep 에디터 직접 접근 시도"""
    try:
        await page.goto(f"https://blog.naver.com/{BLOG_ID}/postwrite", timeout=20000)
        await page.wait_for_timeout(3000)
        url = page.url
        if "nidlogin" in url or "login" in url.lower():
            return False
        # 에디터 UI 확인
        editor = await page.query_selector(".se-main-container, .se-editor, #SE-titleInput")
        return editor is not None or "blog.naver.com" in url
    except Exception:
        return False


# ── CAPTCHA 해결 (Claude Vision) ──────────────────────────────────
async def solve_captcha(page) -> str | None:
    import base64
    try:
        from env_loader import make_anthropic_client, get_model
        body = await page.inner_text("body")
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        question = next(
            (l for l in lines if '?' in l and len(l) > 8
             and any(w in l.lower() for w in ['what','how','which','fill','the','number','price','kind','unit','location','third','second','first','cheapest','least','most'])),
            ""
        )
        print(f"  CAPTCHA 질문: {question}")
        screenshot_bytes = await page.screenshot(full_page=True)
        img_b64 = base64.b64encode(screenshot_bytes).decode()
        client = make_anthropic_client(timeout=30)
        answer = ""
        with client.messages.stream(
            model=get_model(), max_tokens=8,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": f"Naver login CAPTCHA. Look at the receipt image carefully.\nQuestion: {question}\nAnswer with ONLY the answer word or number. Single word/number only, no explanation."}
            ]}]
        ) as stream:
            for chunk in stream.text_stream:
                answer += chunk
        return answer.strip().replace(",", "").replace(" ", "")
    except Exception as e:
        print(f"  CAPTCHA 해결 실패: {e}")
        return None


# ── 로그인 시도 ────────────────────────────────────────────────────
async def do_login(page, context) -> bool:
    """로그인 + CAPTCHA 자동 해결 (최대 2회)"""
    await page.goto("https://nid.naver.com/nidlogin.login?mode=form", timeout=15000)
    await page.wait_for_timeout(2000)

    # ID/PW 입력
    await page.locator("#id").click()
    for c in NAVER_ID:
        await page.keyboard.type(c); await asyncio.sleep(0.15)
    await page.wait_for_timeout(400)
    await page.locator("#pw").click()
    for c in NAVER_PW:
        await page.keyboard.type(c); await asyncio.sleep(0.12)
    await page.wait_for_timeout(1500)

    btn = await page.query_selector(".btn_login")
    if btn: await btn.click()
    await page.wait_for_timeout(7000)

    # 최대 2회 CAPTCHA 해결 시도
    for attempt in range(2):
        url = page.url
        body = await page.inner_text("body")
        is_captcha = "Please enter the answer" in body or "자동입력 방지" in body or "receipt" in body.lower() or "virtually" in body.lower()

        if "nidlogin" not in url:
            await context.storage_state(path=str(SESSION_FILE))
            print(f"  ✅ 로그인 성공! 세션 저장: {SESSION_FILE}")
            return True

        if is_captcha:
            print(f"  CAPTCHA 감지 (시도 {attempt+1}/2)")
            answer = await solve_captcha(page)
            if not answer:
                return False

            # CAPTCHA 답 입력
            inp = None
            for sel in ["input[placeholder*='answer']", "input[placeholder*='Answer']"]:
                inp = await page.query_selector(sel)
                if inp: break
            if inp:
                await inp.click(); await inp.fill("")
                for c in answer: await page.keyboard.type(c); await asyncio.sleep(0.08)
                print(f"  CAPTCHA 입력: '{answer}'")

            # PW 재입력 (CAPTCHA 후 초기화됨)
            pw = await page.query_selector("#pw")
            if pw:
                val = await pw.input_value()
                if not val:
                    await pw.click()
                    for c in NAVER_PW:
                        await page.keyboard.type(c); await asyncio.sleep(0.1)
                    await page.wait_for_timeout(1000)
                    print("  PW 재입력 완료")

            await page.wait_for_timeout(500)
            btn = await page.query_selector(".btn_login")
            if btn: await btn.click()
            await page.wait_for_timeout(7000)
        else:
            print(f"  ❌ 로그인 실패 (IP 차단 또는 비밀번호 오류): {url}")
            return False

    return False


# ── Telegram 알림 ─────────────────────────────────────────────────
def send_telegram_alert(message: str):
    """세션 갱신 필요 알림"""
    try:
        import urllib.request, urllib.parse
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "420793033")
        if not token:
            return
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data
            ), timeout=10
        )
    except Exception:
        pass


# ── 메인 ──────────────────────────────────────────────────────────
async def main():
    print("=== 네이버 세션 상태 확인 ===")

    async def _run(p):
        browser = await p.chromium.launch(
            headless=False, executable_path=CHROME_PATH, args=LAUNCH_ARGS
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        if SESSION_FILE.exists():
            ctx_kwargs["storage_state"] = str(SESSION_FILE)

        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await context.new_page()

        # 1. 세션 유효성 먼저 확인
        if SESSION_FILE.exists():
            print("세션 파일 있음 — 유효성 확인 중...")
            valid = await check_session_valid(page)
            if valid:
                print("✅ 세션 유효 — 로그인 불필요")
                await browser.close()
                return True
            print("세션 만료 — 재로그인 시도")

        # 2. 로그인 시도
        ok = await do_login(page, context)
        if not ok:
            msg = ("⚠️ 네이버 블로그 세션 갱신 필요\n"
                   "IP 차단 또는 CAPTCHA 해결 실패로 자동 로그인 불가.\n"
                   "수동 세션 갱신이 필요합니다.")
            print(msg)
            send_telegram_alert(msg)
            await browser.close()
            return False

        # 3. prosweep 에디터 접근 확인
        await page.goto(
            f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo=6", timeout=20000
        )
        await page.wait_for_timeout(5000)
        if "nidlogin" not in page.url:
            print(f"✅ {BLOG_ID} 에디터 접근 성공!")
        else:
            print(f"⚠️ 로그인은 됐으나 {BLOG_ID} 에디터 접근 불가")

        await browser.close()
        return ok

    if USE_STEALTH:
        async with Stealth().use_async(async_playwright()) as p:
            return await _run(p)
    else:
        async with async_playwright() as p:
            return await _run(p)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
