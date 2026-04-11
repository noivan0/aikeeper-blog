#!/usr/bin/env python3
"""
티스토리 TSSESSION 자동 갱신 스크립트
카카오계정 로그인 → TSSESSION 쿠키 추출 → .env 업데이트

실행:
  python3 scripts/refresh_tistory_session.py

크론 등록 (매일 KST 06:00):
  OpenClaw 크론으로 등록 권장
"""
import asyncio, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

KAKAO_ID   = os.environ.get("KAKAO_ID", "")
KAKAO_PW   = os.environ.get("KAKAO_PW", "")
BLOG_NAME  = os.environ.get("TISTORY_BLOG_NAME", "banidad")
ENV_FILE   = Path(__file__).parent.parent / ".env"

if not KAKAO_ID or not KAKAO_PW:
    print("❌ KAKAO_ID / KAKAO_PW 환경변수 없음")
    sys.exit(1)


async def get_tssession() -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"]
        )
        ctx = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()

        print("  티스토리 로그인 페이지 이동...")
        await page.goto("https://www.tistory.com/auth/login", timeout=20000)
        await page.wait_for_timeout(2000)

        print("  카카오계정으로 로그인 클릭...")
        await page.click(".link_kakao_id")
        await page.wait_for_timeout(3000)

        # 카카오 로그인 폼
        print("  카카오 ID 입력...")
        await page.fill("#loginId--1", KAKAO_ID)
        await page.fill("#password--2", KAKAO_PW)
        await page.wait_for_timeout(500)

        # 로그인 버튼 클릭
        print("  로그인 버튼 클릭...")
        await page.click("button.btn_g.highlight.submit")
        await page.wait_for_timeout(5000)

        # 2차 인증 or 기기 등록 팝업 처리
        cur_url = page.url
        print(f"  로그인 후 URL: {cur_url}")

        # 기기 등록 안내 팝업 ("나중에 하기" 버튼)
        try:
            skip_btn = await page.wait_for_selector("button:has-text('나중에')", timeout=3000)
            if skip_btn:
                await skip_btn.click()
                await page.wait_for_timeout(2000)
                print("  기기 등록 팝업 닫기 완료")
        except Exception:
            pass

        # tistory.com으로 리다이렉트 대기
        try:
            await page.wait_for_url("*tistory.com*", timeout=10000)
        except Exception:
            pass

        await page.wait_for_timeout(2000)
        final_url = page.url
        print(f"  최종 URL: {final_url}")

        # TSSESSION 쿠키 수집
        cookies = await ctx.cookies()
        tssession = ""
        for c in cookies:
            if c["name"] == "TSSESSION":
                tssession = c["value"]
                print(f"  ✅ TSSESSION 추출 완료 ({len(tssession)}자)")
                break

        if not tssession:
            # 세션 쿠키 이름이 다를 수 있으니 전체 출력
            names = [c["name"] for c in cookies if "tistory" in c.get("domain","").lower() or "kakao" in c.get("domain","").lower()]
            print(f"  ⚠️ TSSESSION 없음. 쿠키 목록: {names}")
            await page.screenshot(path="/tmp/tistory_login_fail.png")

        await browser.close()
        return tssession


def update_env(session: str) -> bool:
    """
    .env 파일에서 TISTORY_SESSION 값을 새 세션으로 교체.
    없으면 추가.
    """
    text = ENV_FILE.read_text()
    new_line = f"TISTORY_SESSION={session}"

    if re.search(r"^TISTORY_SESSION=", text, re.MULTILINE):
        text = re.sub(r"^TISTORY_SESSION=.*$", new_line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"

    ENV_FILE.write_text(text)
    print(f"  ✅ .env 업데이트 완료 (TISTORY_SESSION={session[:10]}...)")
    return True


async def main():
    print("=== 티스토리 세션 자동 갱신 ===")

    session = await get_tssession()
    if not session:
        print("❌ 세션 획득 실패")
        sys.exit(1)

    update_env(session)

    # 발행 테스트 (세션 유효성 검증)
    import requests
    s = requests.Session()
    s.verify = False
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    s.cookies.set("TSSESSION", session, domain=f"{BLOG_NAME}.tistory.com")
    r = s.get(f"https://{BLOG_NAME}.tistory.com/manage/", timeout=10)
    if "manage" in r.url and "login" not in r.url.lower():
        print(f"✅ 세션 유효 확인 완료")
    else:
        print(f"⚠️ 세션 확인 실패: {r.url}")


if __name__ == "__main__":
    os.environ.setdefault("DISPLAY", ":99")
    asyncio.run(main())
