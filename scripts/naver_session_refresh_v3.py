#!/usr/bin/env python3
"""
P005 네이버 세션 갱신 v3 — 로그인 없는 쿠키 활성화 방식

전략:
1. 세션 파일로 블로그 방문 → 쿠키 자동 갱신 저장 (로그인 불필요)
2. 유효성 확인: 블로그 에디터 접근 가능 여부
3. 세션 만료 시에만 Telegram 알림 (수동 쿠키 주입 요청)

세션 유효 기간: NID_AUT 기준 노이반님 부여 시점 기준
→ 만료 7일 전 경보, 만료 시 알림
"""
import os, sys, json, asyncio, time
from pathlib import Path
from datetime import datetime

SESSION_FILE = os.environ.get(
    "NAVER_SESSION_FILE",
    str(Path(__file__).parent.parent / "naver_session.json")
)
LOG_PREFIX = "[P004 세션갱신]"
FORCE = "--force" in sys.argv


def check_nid_expiry(session_file: str) -> tuple[float, int]:
    """NID_AUT 만료 시각과 남은 일수 반환"""
    try:
        data = json.loads(Path(session_file).read_text())
        for c in data.get("cookies", []):
            if c.get("name") == "NID_AUT":
                exp = c.get("expires", -1)
                if exp > 0:
                    days_left = int((exp - time.time()) / 86400)
                    return exp, days_left
    except Exception:
        pass
    return -1, -999


async def refresh_session(session_file: str) -> bool:
    """블로그 방문으로 세션 쿠키 갱신 (로그인 없음)"""
    from playwright.async_api import async_playwright

    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":99"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"]
        )
        try:
            ctx = await browser.new_context(
                storage_state=session_file,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ignore_https_errors=True,
            )
            page = await ctx.new_page()

            # 블로그 방문 (세션 활성화)
            print(f"{LOG_PREFIX} 블로그 방문으로 세션 활성화 중...")
            await page.goto("https://blog.naver.com/prosweep", timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 로그인 상태 확인
            url = page.url
            title = await page.title()
            if "login" in url.lower() or "nidlogin" in url.lower():
                print(f"{LOG_PREFIX} ❌ 세션 만료 — 로그인 페이지로 리다이렉트")
                await browser.close()
                return False

            # 에디터 접근 확인
            await page.goto("https://blog.naver.com/prosweep/postwrite", timeout=15000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            editor_url = page.url
            if "login" in editor_url.lower():
                print(f"{LOG_PREFIX} ❌ 에디터 접근 불가 (세션 만료)")
                await browser.close()
                return False

            # 갱신된 세션 저장
            await ctx.storage_state(path=session_file)
            print(f"{LOG_PREFIX} ✅ 세션 갱신 완료 (로그인 없이)")
            print(f"{LOG_PREFIX} 페이지: {title[:40]}")
            await browser.close()
            return True

        except Exception as e:
            print(f"{LOG_PREFIX} ❌ 갱신 오류: {e}")
            await browser.close()
            return False


def send_telegram_alert(msg: str):
    """세션 만료 임박/만료 시 Telegram 알림"""
    try:
        import subprocess
        # OpenClaw message tool 활용
        subprocess.run(
            ["openclaw", "message", "send", "--channel", "telegram",
             "--target", "420793033", "--message", msg],
            timeout=10, capture_output=True
        )
    except Exception:
        print(f"{LOG_PREFIX} Telegram 알림 실패 (무시): {msg[:50]}")


def main():
    print(f"\n{LOG_PREFIX} {'=' * 50}")
    print(f"{LOG_PREFIX} 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not Path(SESSION_FILE).exists():
        print(f"{LOG_PREFIX} ❌ 세션 파일 없음: {SESSION_FILE}")
        sys.exit(1)

    # NID_AUT 만료 확인
    exp_ts, days_left = check_nid_expiry(SESSION_FILE)
    if exp_ts > 0:
        print(f"{LOG_PREFIX} NID_AUT 만료: {datetime.fromtimestamp(exp_ts).strftime('%Y-%m-%d')} ({days_left}일 남음)")
    else:
        print(f"{LOG_PREFIX} NID_AUT 만료 정보 없음")

    # 만료 7일 전 경보
    if 0 < days_left <= 7:
        send_telegram_alert(
            f"⚠️ [P005] 네이버 세션 {days_left}일 후 만료 예정\n"
            f"NID_AUT/NID_SES 쿠키를 개발팀장에게 전달해 주세요."
        )

    # 만료됐으면 알림 후 종료
    if days_left <= 0 and exp_ts > 0:
        send_telegram_alert(
            "🚨 [P005] 네이버 세션 만료!\n"
            "Chrome에서 blog.naver.com 접속 후\n"
            "NID_AUT / NID_SES 쿠키를 @pipeDevLeadbot에게 전달해 주세요."
        )
        print(f"{LOG_PREFIX} ❌ 세션 만료 — 알림 발송 완료")
        sys.exit(1)

    # 세션 갱신 (방문 방식)
    result = asyncio.run(refresh_session(SESSION_FILE))
    if result:
        print(f"{LOG_PREFIX} ✅ 완료")
        sys.exit(0)
    else:
        send_telegram_alert(
            "🚨 [P005] 네이버 세션 갱신 실패!\n"
            "NID_AUT / NID_SES 쿠키를 @pipeDevLeadbot에게 전달해 주세요."
        )
        print(f"{LOG_PREFIX} ❌ 실패 — 알림 발송 완료")
        sys.exit(1)


if __name__ == "__main__":
    main()
