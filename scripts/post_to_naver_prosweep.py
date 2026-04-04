"""
꿀통몬스터 → prosweep 네이버 블로그 크로스포스팅 v9
- OG 카드: 꿀통몬스터 원본 포스팅 URL 1개
- 쿠팡 링크: 본문 텍스트 가격 정보로 표시 (LINK_TEXT 방식)
- URL 텍스트 줄 삭제: JS DOM 직접 제거
- 서버 cron 직접 실행 (GitHub Actions 제외)
"""
import os, sys, asyncio, json, time, re
from pathlib import Path

NAVER_ID        = os.environ.get("NAVER_ID", "")
NAVER_PW        = os.environ.get("NAVER_PW", "")
BLOG_ID         = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO     = os.environ.get("NAVER_CATEGORY_NO", "6")
POST_TITLE      = os.environ.get("POST_TITLE", "")
POST_URL        = os.environ.get("POST_URL", "")
POST_SUMMARY    = os.environ.get("POST_SUMMARY", "")
LABELS_STR      = os.environ.get("LABELS", "")
COUPANG_LINKS   = os.environ.get("COUPANG_LINKS", "")
COUPANG_PRICES  = os.environ.get("COUPANG_PRICES", "")
SESSION_FILE    = os.environ.get("NAVER_SESSION_FILE",
                   str(Path(__file__).parent.parent / "naver_session.json"))

BASE_DIR     = Path(__file__).parent.parent
CHROME_PATH  = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
LAUNCH_ARGS  = [
    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--ignore-certificate-errors", "--ignore-ssl-errors",
    "--disable-blink-features=AutomationControlled",
]
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}"


# ── 본문 빌더 ────────────────────────────────────────────────────
def build_naver_content(
    title: str, summary: str, original_url: str,
    labels: list, coupang_links: list, coupang_prices: list
) -> str:
    """
    구조:
      파트너스 고지
      후킹 인트로
      요약 (summary)
      쿠팡 가격 정보 텍스트 (링크는 LINK_TEXT 방식으로 별도 처리)
      CARD_URL:{original_url}   ← 꿀통몬스터 원본 OG 카드 1개
      공감 요청
      해시태그

    본문에 쿠팡 링크는 LINK_TEXT:텍스트|URL 형식으로 삽입
    """
    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels \
                else "#쿠팡추천 #가성비 #쿠팡파트너스"

    # 쿠팡 가격 정보 블록 (LINK_TEXT 방식)
    price_block = ""
    for i, link in enumerate(coupang_links[:3]):
        price = coupang_prices[i] if i < len(coupang_prices) else ""
        rank = ["1위", "2위", "3위"][i]
        label = f"쿠팡에서 확인하기 ({price})" if price else "쿠팡에서 확인하기"
        price_block += f"💰 {rank}: LINK_TEXT:{label}|{link}\n"

    content = f"""이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

안녕하세요, 쇼핑정보 모아보기입니다 😊

{title}를 찾고 계신가요? 저도 고민 많이 했는데 직접 비교해봤습니다.

{summary}

가격 비교 먼저 보실 분들을 위해 쿠팡 최저가 링크부터 공유드립니다 👇

{price_block}
더 꼼꼼한 성분 비교, 사용 후기, 가성비 분석이 궁금하다면 아래 포스팅을 확인해 주세요. 실제로 써보고 정리한 내용입니다.

CARD_URL:{original_url}

도움이 됐다면 공감 ❤️ 한 번 눌러주시면 큰 힘이 됩니다!

{label_str}"""
    return content.strip()


# ── atom.xml에서 쿠팡 링크/가격 추출 ─────────────────────────────
def extract_coupang_data_from_blogger(post_url: str) -> tuple[list, list]:
    import urllib.request, xml.etree.ElementTree as ET
    try:
        req = urllib.request.Request(
            "https://ggultongmon.allsweep.xyz/atom.xml",
            headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
        target = None
        for e in entries:
            c = e.findtext('atom:content', namespaces=ns) or ''
            if re.search(re.escape(post_url), c):
                target = e; break
        if not target:
            target = entries[0]
        content = target.findtext('atom:content', namespaces=ns) or ''
        all_links = re.findall(r'href=["\']+(https://link\.coupang\.com/[^"\'>\s]+)', content)
        unique_links = list(dict.fromkeys(all_links))[:3]
        prices_raw = re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+)원', content)
        unique_prices = [p + "원" for p in list(dict.fromkeys(prices_raw))[:3]]
        return unique_links, unique_prices
    except Exception as ex:
        print(f"  [warn] 쿠팡 데이터 추출 실패: {ex}")
        return [], []


# ── 로그인 & 세션 ─────────────────────────────────────────────────
async def ensure_session(context, page) -> bool:
    await page.goto("https://blog.naver.com", timeout=20000)
    await page.wait_for_timeout(2000)
    login_ok = await page.evaluate("() => document.cookie.includes('NID_SES')")
    if login_ok:
        print("  세션 유효 ✅")
        return True
    return await do_login(page, context)

async def do_login(page, context) -> bool:
    if not NAVER_ID or not NAVER_PW:
        print("  ❌ NAVER_ID/PW 없음")
        return False
    await page.goto("https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com", timeout=20000)
    await page.wait_for_timeout(3000)
    await page.locator("#id").click()
    for c in NAVER_ID:
        await page.keyboard.press(c); await asyncio.sleep(0.12)
    await page.wait_for_timeout(400)
    await page.locator("#pw").click()
    for c in NAVER_PW:
        await page.keyboard.press(c); await asyncio.sleep(0.1)
    await page.wait_for_timeout(400)
    btn = await page.query_selector(".btn_login")
    if btn: await btn.click()
    await page.wait_for_timeout(5000)
    if "nidlogin" not in page.url:
        await context.storage_state(path=SESSION_FILE)
        print(f"  세션 저장: {SESSION_FILE}")
        return True
    print("  ❌ 로그인 실패")
    return False


# ── 팝업 처리 ─────────────────────────────────────────────────────
async def handle_popups(page):
    await page.evaluate("""
        () => {
            const p = document.querySelector('.__se-pop-layer');
            if (p) {
                for (const b of p.querySelectorAll('button')) {
                    if (b.innerText.trim() === '취소') { b.click(); break; }
                }
            }
        }
    """)
    await page.wait_for_timeout(1200)
    hb = await page.query_selector(".se-help-panel-close-button")
    if hb: await hb.click(); await page.wait_for_timeout(400)
    await page.evaluate("() => document.querySelectorAll('.layer_popup__i0QOY').forEach(el=>el.style.display='none')")
    await page.wait_for_timeout(300)


# ── 제목 입력 ─────────────────────────────────────────────────────
async def type_title(page, title: str):
    title_comp = await page.query_selector(".se-component.se-documentTitle")
    if title_comp:
        box = await title_comp.bounding_box()
        await page.mouse.click(box['x'] + 200, box['y'] + box['height'] / 2)
    else:
        await page.mouse.click(590, 232)
    await page.wait_for_timeout(400)
    await page.keyboard.type(title, delay=40)
    await page.wait_for_timeout(300)


# ── LINK_TEXT 하이퍼링크 삽입 ─────────────────────────────────────
async def insert_text_link(page, text: str, url: str):
    """텍스트 입력 → se-link-toolbar-button으로 하이퍼링크 연결"""
    await page.keyboard.type(text, delay=25)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Home")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Shift+End")
    await page.wait_for_timeout(200)
    await page.evaluate("""
        () => {
            const btn = document.querySelector('.se-link-toolbar-button');
            if (!btn) return;
            btn.addEventListener('mousedown', (e) => e.preventDefault(), {once: true});
            btn.click();
        }
    """)
    await page.wait_for_timeout(1500)
    url_input = await page.query_selector(".se-custom-layer-link-input")
    if url_input:
        await url_input.click()
        await page.keyboard.type(url, delay=10)
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(400)
    else:
        await page.keyboard.press("Escape")
    await page.keyboard.press("End")
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(100)


# ── OG 카드 삽입 (꿀통몬스터 URL) ────────────────────────────────
async def insert_og_card(page, url: str):
    """
    URL 타이핑 → Enter → OG 카드 자동 생성 → URL 텍스트 DOM 직접 제거
    """
    await page.keyboard.type(url, delay=12)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(7000)  # 카드 생성 대기

    # ── URL 텍스트 단락 DOM 직접 제거 (JS) ────────────────────────
    # SE 에디터의 React 상태를 건드리지 않고 DOM만 제거하면
    # 발행 시 서버에서 재렌더링되므로 실제 포스트에서는 사라짐
    # URL 텍스트 단락 삭제 — 단락이 한 줄(h≈29)이므로 Home→Shift+End→Backspace 정확히 삭제
    for attempt in range(5):
        info = await page.evaluate("""
            () => {
                const paras = Array.from(document.querySelectorAll('.se-text-paragraph'));
                for (const para of paras) {
                    const txt = para.innerText || '';
                    if (txt.trim().match(/^https?:\\/\\//) && txt.trim().length > 5) {
                        const r = para.getBoundingClientRect();
                        if (r.width < 10) continue;
                        return {
                            x: Math.round(r.x + 60),
                            y: Math.round(r.y + r.height / 2),  // 단락 중앙
                            h: Math.round(r.height)
                        };
                    }
                }
                return null;
            }
        """)
        if not info:
            break
        # 단락 중앙 클릭 → Home → Shift+End → Backspace
        await page.mouse.click(info['x'], info['y'])
        await page.wait_for_timeout(150)
        await page.keyboard.press("Home")
        await page.wait_for_timeout(60)
        await page.keyboard.press("Shift+End")
        await page.wait_for_timeout(60)
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(300)
        print(f"    URL 단락 삭제 (attempt {attempt+1}, h={info['h']})")
    await page.wait_for_timeout(300)

    # 커서를 마지막 빈 단락으로 이동
    last_empty = await page.evaluate("""
        () => {
            const paras = Array.from(document.querySelectorAll('.se-text-paragraph'));
            for (let i = paras.length - 1; i >= 0; i--) {
                const txt = (paras[i].innerText || '').trim();
                const r = paras[i].getBoundingClientRect();
                if (txt === '' && r.width > 0 && r.y > 200) {
                    return {x: Math.round(r.x + 60), y: Math.round(r.y + 5)};
                }
            }
            return null;
        }
    """)
    if last_empty:
        await page.mouse.click(last_empty['x'], last_empty['y'])
        await page.wait_for_timeout(200)
        await page.keyboard.press("End")


# ── 본문 입력 ─────────────────────────────────────────────────────
async def type_body(page, content: str):
    # 본문 첫 단락 클릭
    body_comp = await page.query_selector(".se-component.se-text")
    if body_comp:
        box = await body_comp.bounding_box()
        await page.mouse.click(box['x'] + 200, box['y'] + box['height'] / 2)
    else:
        await page.mouse.click(590, 380)
    await page.wait_for_timeout(500)

    lines = content.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("CARD_URL:"):
            url = stripped[len("CARD_URL:"):]
            await insert_og_card(page, url)

        elif "LINK_TEXT:" in stripped:
            # 줄 앞 텍스트 처리
            before = stripped[:stripped.index("LINK_TEXT:")]
            payload = stripped[stripped.index("LINK_TEXT:") + len("LINK_TEXT:"):]
            if before:
                await page.keyboard.type(before, delay=18)
            if "|" in payload:
                link_text, link_url = payload.split("|", 1)
                await insert_text_link(page, link_text.strip(), link_url.strip())
            else:
                await page.keyboard.type(payload, delay=18)
                await page.keyboard.press("Enter")

        elif line:
            await page.keyboard.type(line, delay=18)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(70)
        else:
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(70)

    await page.wait_for_timeout(500)


# ── 발행 ─────────────────────────────────────────────────────────
async def publish(page) -> str | None:
    await page.evaluate("""
        () => {
            document.querySelectorAll('.layer_popup__i0QOY').forEach(el=>el.style.display='none');
            const hp = document.querySelector('.container__HW_tc, .se-help-panel');
            if (hp) hp.style.display = 'none';
        }
    """)
    await page.wait_for_timeout(600)

    publish_btn = await page.query_selector(".publish_btn__m9KHH")
    if not publish_btn:
        publish_btn = await page.query_selector("button[class*='publish_btn']")
    if not publish_btn:
        print("  ❌ 발행 버튼 없음")
        await page.screenshot(path="/tmp/naver_publish_fail.png")
        return None

    await page.evaluate("btn => btn.click()", publish_btn)
    await page.wait_for_timeout(3000)

    confirm_btn = await page.query_selector(".confirm_btn__WEaBq")
    if not confirm_btn:
        confirm_btn = await page.query_selector("button[class*='confirm_btn']")
    if not confirm_btn:
        print("  ❌ 확인 버튼 없음")
        return None
    await page.evaluate("btn => btn.click()", confirm_btn)
    await page.wait_for_timeout(6000)

    url = page.url
    return url if ("PostView" in url or "logNo" in url) else None


# ── 메인 ─────────────────────────────────────────────────────────
async def main():
    if not POST_TITLE or not POST_URL:
        print("❌ POST_TITLE, POST_URL 필요")
        sys.exit(1)

    labels = [l.strip() for l in LABELS_STR.split(",") if l.strip()] if LABELS_STR else []
    coupang_links = [l for l in COUPANG_LINKS.split("|") if l.strip()] if COUPANG_LINKS else []
    coupang_prices = [p for p in COUPANG_PRICES.split("|") if p.strip()] if COUPANG_PRICES else []
    if not coupang_links:
        print("  쿠팡 링크 자동 추출 중...")
        coupang_links, coupang_prices = extract_coupang_data_from_blogger(POST_URL)

    content = build_naver_content(POST_TITLE, POST_SUMMARY, POST_URL, labels, coupang_links, coupang_prices)

    print(f"[포스팅 준비]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  원본(OG카드): {POST_URL[:60]}")
    print(f"  쿠팡 링크: {len(coupang_links)}개 / 가격: {coupang_prices}")
    print(f"  본문 길이: {len(content)}자")

    os.environ['DISPLAY'] = ':99'
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=CHROME_PATH, args=LAUNCH_ARGS)
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

        session_ok = await ensure_session(context, page)
        if not session_ok:
            await browser.close(); sys.exit(1)

        print(f"\n[에디터 로드] {WRITE_URL}")
        await page.goto(WRITE_URL, timeout=30000)
        await page.wait_for_selector(".se-oglink-toolbar-button", timeout=20000)
        await page.wait_for_timeout(3000)

        if "nidlogin" in page.url or "login" in page.url.lower():
            if not await do_login(page, context):
                await browser.close(); sys.exit(1)

        await handle_popups(page)

        print("[제목 입력...]")
        await type_title(page, POST_TITLE)

        print("[본문 입력 중...]")
        await type_body(page, content)

        await page.screenshot(path="/tmp/naver_before_publish.png")
        print("[발행 중...]")
        result_url = await publish(page)

        if result_url:
            print(f"\n✅ 발행 성공!")
            print(f"  URL: {result_url}")
            await context.storage_state(path=SESSION_FILE)
            out = {
                "success": True,
                "naver_url": result_url,
                "title": POST_TITLE,
                "original_url": POST_URL,
                "coupang_links": coupang_links,
                "category": CATEGORY_NO,
                "content_len": len(content),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            out_path = BASE_DIR / "results" / "naver_posts.jsonl"
            out_path.parent.mkdir(exist_ok=True)
            with open(out_path, "a") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            print(f"  로그: {out_path}")
        else:
            print("\n❌ 발행 실패")
            await page.screenshot(path="/tmp/naver_fail.png")
            sys.exit(1)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
