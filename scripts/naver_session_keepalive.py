#!/usr/bin/env python3
"""
네이버 세션 Keepalive v1
────────────────────────
세션이 유효한 동안 주기적으로 네이버 페이지 방문 → 세션 연장 저장
실행: python3 scripts/naver_session_keepalive.py
크론: 0 */6 * * * (6시간마다)
"""
import asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

SESSION_FILE = Path(__file__).parent.parent / "naver_session.json"
BLOG_ID = os.environ.get("NAVER_BLOG_ID", "prosweep")
CHROME_PATH = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"

async def keepalive():
    from playwright.async_api import async_playwright
    import time

    if not SESSION_FILE.exists():
        print("세션 파일 없음 — 스킵")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, executable_path=CHROME_PATH,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        ctx = await browser.new_context(
            storage_state=str(SESSION_FILE),
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        # 세션 유효성 확인
        try:
            await page.goto(f"https://blog.naver.com/{BLOG_ID}/postwrite", timeout=20000)
            await page.wait_for_timeout(3000)
            url = page.url
            if "nidlogin" in url or "login" in url.lower():
                print("⚠️ 세션 만료 — naver_session_refresh.py 실행 필요")
                await browser.close()
                return False
        except Exception as e:
            print(f"접근 실패: {e}")
            await browser.close()
            return False

        # 유효 → 주요 페이지 순회로 세션 연장
        pages_to_visit = [
            "https://www.naver.com",
            f"https://blog.naver.com/{BLOG_ID}",
            "https://brandconnect.naver.com",
        ]
        for url in pages_to_visit:
            try:
                await page.goto(url, timeout=15000, wait_until="commit")
                await page.wait_for_timeout(2000)
                print(f"  방문: {url}")
            except Exception:
                pass

        # 갱신된 세션 저장
        await ctx.storage_state(path=str(SESSION_FILE))

        # 쿠키 만료 확인
        state = json.loads(SESSION_FILE.read_text())
        now = time.time()
        for c in state.get("cookies", []):
            if c["name"] in ("NID_AUT", "NID_SES"):
                exp = c.get("expires", -1)
                if exp > 0:
                    days = int((exp - now) / 86400)
                    print(f"✅ {c['name']}: 영구쿠키 {days}일 유효")
                else:
                    print(f"ℹ️  {c['name']}: 세션쿠키 (서버에서 유효)")

        print("✅ Keepalive 완료 — 세션 갱신 저장")
        await browser.close()
        return True

if __name__ == "__main__":
    result = asyncio.run(keepalive())
    sys.exit(0 if result else 1)
