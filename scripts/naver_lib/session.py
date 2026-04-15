#!/usr/bin/env python3
"""
naver_lib/session.py — 네이버 세션 로드/저장/로그인
"""
import os
import asyncio
from pathlib import Path

DEFAULT_SESSION_FILE = "/root/.openclaw/workspace/paperclip-company/projects/p004-blogger/naver_session.json"


def load_session(session_file: str | None = None) -> str:
    return session_file or os.environ.get("NAVER_SESSION_FILE", DEFAULT_SESSION_FILE)


def save_session(context, session_file: str | None = None):
    path = session_file or os.environ.get("NAVER_SESSION_FILE", DEFAULT_SESSION_FILE)
    return context.storage_state(path=path)


async def login_if_needed(page, context, write_url: str,
                           naver_id: str, naver_pw: str,
                           session_file: str | None = None) -> bool:
    """
    로그인이 필요하면 수행. 성공 시 True, 실패 시 False.
    page는 이미 write_url로 이동한 상태여야 함.
    """
    if "nidlogin" not in page.url and "login" not in page.url.lower():
        return True  # 이미 로그인됨

    print("  세션 만료 — 재로그인")
    await page.goto("https://nid.naver.com/nidlogin.login?mode=form", timeout=20000)
    await page.wait_for_timeout(2000)

    await page.locator("#id").click()
    for c in naver_id:
        await page.keyboard.type(c)
        await asyncio.sleep(0.12)
    await page.locator("#pw").click()
    for c in naver_pw:
        await page.keyboard.type(c)
        await asyncio.sleep(0.10)
    await page.wait_for_timeout(1000)

    btn = await page.query_selector(".btn_login")
    if btn:
        await btn.click()
    await page.wait_for_timeout(6000)

    if "nidlogin" in page.url:
        print("  ❌ 로그인 실패")
        return False

    await save_session(context, session_file)
    await page.goto(write_url, timeout=40000)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(3000)
    return True


async def dismiss_popups(page, max_tries: int = 12):
    """에디터 진입 시 "작성 중인 글이 있습니다" 등 팝업 취소 처리."""
    for _ in range(max_tries):
        pos = await page.evaluate("""() => {
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText || '').trim();
                if (t === '취소' || t === '닫기') {
                    const r = b.getBoundingClientRect();
                    if (r.width > 0) return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }""")
        if pos:
            await page.mouse.click(pos['x'], pos['y'])
            await page.wait_for_timeout(1500)
            print("  [팝업] 취소 ✅")
            break
        await page.wait_for_timeout(300)
