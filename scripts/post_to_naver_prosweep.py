"""
꿀통몬스터 → prosweep 네이버 블로그 크로스포스팅
- ggultongmon Blogger 포스트 발행 후 호출
- prosweep 블로그 쿠팡 카테고리(categoryNo=6)에 요약 + 원본 링크 발행
- Xvfb + headed Playwright 방식 (SE 에디터 정상 렌더링)

사용법:
  NAVER_ID=xxx NAVER_PW=xxx \
  POST_TITLE="제목" POST_URL="https://..." POST_SUMMARY="요약" \
  python3 post_to_naver_prosweep.py
"""
import os, sys, asyncio, json, time
from pathlib import Path

# ── 환경변수 ──────────────────────────────────────────────────────
NAVER_ID       = os.environ.get("NAVER_ID", "")
NAVER_PW       = os.environ.get("NAVER_PW", "")
BLOG_ID        = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO    = os.environ.get("NAVER_CATEGORY_NO", "6")   # 쿠팡 카테고리
POST_TITLE     = os.environ.get("POST_TITLE", "")
POST_URL       = os.environ.get("POST_URL", "")
POST_SUMMARY   = os.environ.get("POST_SUMMARY", "")
LABELS_STR     = os.environ.get("LABELS", "")
SESSION_FILE   = os.environ.get("NAVER_SESSION_FILE",
                  str(Path(__file__).parent.parent / "naver_session.json"))

BASE_DIR       = Path(__file__).parent.parent
CHROME_PATH    = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
LAUNCH_ARGS    = [
    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--ignore-certificate-errors", "--ignore-ssl-errors",
    "--disable-blink-features=AutomationControlled",
]
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}"

# ── 네이버 블로그 전용 포맷 ────────────────────────────────────────
def build_naver_content(title: str, summary: str, original_url: str, labels: list) -> str:
    """
    네이버 VIEW탭 최적화 포맷
    - 도입 훅 (공감 유도)
    - 핵심 요약 (3줄)
    - 원본 링크 (꿀통몬스터)
    - 태그 나열 (네이버 검색 최적화)
    """
    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels else "#쿠팡추천 #가성비 #쿠팡파트너스"
    
    content = f"""안녕하세요, 쇼핑정보 모아보기 소모입니다 :)

오늘은 요즘 핫한 쿠팡 상품 정보를 가져왔어요.
실제 구매 전에 꼭 한 번 읽어보시면 후회 없는 선택을 하실 수 있을 거예요!

---

📌 **{title}**

{summary}

---

🔗 **전체 리뷰 & 상품 비교 보기**
더 자세한 내용과 실제 가격 비교는 아래 링크에서 확인하세요.

{original_url}

---

오늘도 좋은 쇼핑 되세요! 😊
유용한 정보였다면 공감 꾹 눌러주세요 ♥

{label_str}
"""
    return content.strip()


# ── 로그인 & 세션 관리 ─────────────────────────────────────────────
async def ensure_session(context, page) -> bool:
    """세션 유효성 확인, 필요 시 재로그인"""
    await page.goto("https://blog.naver.com", timeout=20000)
    await page.wait_for_timeout(2000)
    
    # 로그인 상태 확인 (로그아웃 링크 또는 블로그 쓰기 링크로 판단)
    frame = next((f for f in page.frames if f.url and "blog.naver.com" in f.url), None)
    if frame:
        logout_link = await frame.query_selector("a[href*='nidlogin.logout']")
        if logout_link:
            print("  세션 유효 ✅")
            return True
    
    print("  세션 만료 → 재로그인 시도...")
    return await do_login(page, context)


async def do_login(page, context) -> bool:
    """네이버 로그인 수행"""
    if not NAVER_ID or not NAVER_PW:
        print("  ❌ NAVER_ID / NAVER_PW 없음")
        return False
    
    await page.goto("https://nid.naver.com/nidlogin.login", timeout=20000)
    await page.wait_for_timeout(3000)
    
    await page.locator("#id").click()
    await page.keyboard.type(NAVER_ID, delay=100)
    await page.locator("#pw").click()
    await page.keyboard.type(NAVER_PW, delay=100)
    await page.locator(".btn_login").first.click()
    await page.wait_for_timeout(5000)
    
    if "nidlogin" not in page.url:
        # 세션 저장
        await context.storage_state(path=SESSION_FILE)
        print(f"  세션 저장: {SESSION_FILE}")
        return True
    
    print("  ❌ 로그인 실패")
    return False


# ── SE 에디터 조작 ──────────────────────────────────────────────────
async def handle_popups(page):
    """도움말 / 임시저장 팝업 처리"""
    # 도움말 닫기
    try:
        close_btn = await page.query_selector(".se-help-panel-close-button")
        if close_btn:
            await close_btn.click()
            await page.wait_for_timeout(300)
    except:
        pass
    
    # 임시저장 팝업 → '취소' (새 글 작성)
    await page.evaluate("""
        () => {
            const p = document.querySelector('.__se-pop-layer');
            if (!p) return;
            const btns = p.querySelectorAll('button');
            for (const btn of btns) {
                if (btn.innerText.trim() === '취소') { btn.click(); break; }
            }
        }
    """)
    await page.wait_for_timeout(1500)


async def type_title(page, title: str):
    """제목 입력"""
    # SE 에디터 제목 영역 클릭 (Xvfb 렌더링 기준 y≈232)
    await page.mouse.click(400, 232)
    await page.wait_for_timeout(400)
    await page.keyboard.type(title, delay=60)
    await page.wait_for_timeout(300)


async def type_body(page, content: str):
    """본문 입력"""
    await page.mouse.click(400, 340)
    await page.wait_for_timeout(400)
    # 줄바꿈 처리
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line:
            await page.keyboard.type(line, delay=30)
        if i < len(lines) - 1:
            await page.keyboard.press("Enter")
    await page.wait_for_timeout(300)


async def add_tags(page, labels: list):
    """태그 입력 (발행 패널에서)"""
    if not labels:
        return
    # 태그 입력창 탐색
    tag_input = await page.query_selector(
        ".publish_tag_area__UJIlZ input, [placeholder*='태그'], [placeholder*='#']"
    )
    if tag_input:
        for tag in labels[:8]:
            clean_tag = tag.replace(' ', '').replace('#', '')
            await tag_input.click()
            await page.keyboard.type(clean_tag, delay=40)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(200)


async def publish(page) -> str | None:
    """발행 버튼 클릭 → 최종 발행 → 포스트 URL 반환"""
    # 1. 발행 패널 열기
    pub_btn = await page.query_selector(".publish_btn__m9KHH")
    if not pub_btn:
        print("  ❌ 발행 버튼 없음")
        return None
    await pub_btn.click()
    await page.wait_for_timeout(3000)
    
    # 2. 최종 발행 클릭
    confirm_btn = await page.query_selector(".confirm_btn__WEaBq")
    if not confirm_btn:
        print("  ❌ 확인 버튼 없음")
        return None
    await confirm_btn.click()
    await page.wait_for_timeout(6000)
    
    # 3. 발행 후 URL 확인
    final_url = page.url
    if "PostView" in final_url or "logNo" in final_url:
        return final_url
    return None


# ── 메인 ──────────────────────────────────────────────────────────
async def main():
    # 환경 확인
    if not POST_TITLE or not POST_URL:
        print("❌ POST_TITLE, POST_URL 환경변수 필요")
        sys.exit(1)
    
    labels = [l.strip() for l in LABELS_STR.split(",") if l.strip()] if LABELS_STR else []
    content = build_naver_content(POST_TITLE, POST_SUMMARY, POST_URL, labels)
    
    print(f"[포스팅 준비]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  원본: {POST_URL[:60]}")
    print(f"  카테고리: {CATEGORY_NO} (쿠팡)")
    
    os.environ['DISPLAY'] = ':99'
    
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            executable_path=CHROME_PATH,
            args=LAUNCH_ARGS
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        # 세션 파일이 있으면 로드
        if Path(SESSION_FILE).exists():
            ctx_kwargs["storage_state"] = SESSION_FILE
        
        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await context.new_page()
        
        # 세션 확인 / 재로그인
        session_ok = await ensure_session(context, page)
        if not session_ok:
            await browser.close()
            sys.exit(1)
        
        # 글쓰기 페이지 이동
        print(f"\n[에디터 로드] {WRITE_URL}")
        await page.goto(WRITE_URL, timeout=30000)
        await page.wait_for_timeout(8000)
        
        # 팝업 처리
        await handle_popups(page)
        
        # 제목 + 본문 입력
        print("[입력 시작]")
        await type_title(page, POST_TITLE)
        await type_body(page, content)
        
        # 발행 패널 → 태그 → 발행
        print("[발행 시도]")
        pub_btn = await page.query_selector(".publish_btn__m9KHH")
        if pub_btn:
            await pub_btn.click()
            await page.wait_for_timeout(3000)
            await add_tags(page, labels)
        
        result_url = await publish(page)
        
        if result_url:
            print(f"\n✅ 발행 성공!")
            print(f"  URL: {result_url}")
            # 결과 저장
            out = {
                "success": True,
                "naver_url": result_url,
                "title": POST_TITLE,
                "original_url": POST_URL,
                "category": CATEGORY_NO,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            out_path = BASE_DIR / "results" / "naver_posts.jsonl"
            out_path.parent.mkdir(exist_ok=True)
            with open(out_path, "a") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"  로그: {out_path}")
        else:
            print(f"\n❌ 발행 실패 (URL 변화 없음)")
            sys.exit(1)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
