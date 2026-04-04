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


# ── 본문 빌더 (네이버 C-RANK 최적화 v10) ─────────────────────────
def build_naver_content(
    title: str, summary: str, original_url: str,
    labels: list, coupang_links: list, coupang_prices: list
) -> str:
    """
    네이버 VIEW탭 C-RANK 최적화 포맷
    - 본문 2,000자 이상 (최소 1,500자)
    - 제목 키워드 본문 내 2~3회 자연 등장
    - 구조: 인트로 → 선택 기준 → 가격 비교 → 추천 → OG카드 → 마무리
    - 정보성 단락 + 질문→답변 패턴 + 소항목 구조
    """
    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels \
                else "#쿠팡추천 #가성비 #쿠팡파트너스"

    # 쿠팡 가격 링크 블록
    price_block = ""
    for i, link in enumerate(coupang_links[:3]):
        price = coupang_prices[i] if i < len(coupang_prices) else ""
        rank = ["1위", "2위", "3위"][i]
        btn_label = f"▶ {rank} 쿠팡 최저가 확인 ({price})" if price else f"▶ {rank} 쿠팡 최저가 확인"
        price_block += f"LINK_TEXT:{btn_label}|{link}\n\n"

    # 가격 요약 텍스트
    price_summary = ""
    if coupang_prices:
        for i, price in enumerate(coupang_prices[:3]):
            rank = ["1위", "2위", "3위"][i]
            price_summary += f"{rank}: {price}\n"

    content = f"""이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

안녕하세요, 쇼핑정보 모아보기입니다 😊

오늘은 {title}에 대해 직접 비교하고 정리한 내용을 공유해드립니다.

막상 구매하려고 검색하면 종류가 너무 많아서 어떤 제품을 골라야 할지 막막하죠. 가격도 천차만별이고, 리뷰는 많은데 정작 내 상황에 맞는 정보는 찾기 힘들었습니다. 그래서 직접 발로 뛰며 비교해봤습니다.

{summary}

이 글에서는 실제로 중요한 기준인 가격, 품질, 가성비를 중심으로 핵심만 뽑아서 정리했습니다. 아래 내용이 {title} 선택에 도움이 되길 바랍니다.


■ 지금 바로 가격이 궁금하다면?

시간이 없으신 분들을 위해 결론부터 드립니다. 아래 링크에서 쿠팡 기준 실시간 최저가를 바로 확인하실 수 있어요. 가격은 재고 상황이나 프로모션에 따라 수시로 변동되니, 지금 바로 확인해보시는 게 가장 정확합니다.

{price_block}※ 위 가격은 쿠팡 기준이며 쿠팡 회원 할인·적립금 적용 전 가격입니다. 실제 결제 시 더 저렴할 수 있습니다.


■ {title} — 선택할 때 꼭 확인해야 할 3가지

아무거나 고르다가 후회하지 않으려면 아래 세 가지는 꼭 확인해야 합니다.

첫째, 가격 대비 용량입니다. 단순히 가격만 보면 안 되고, 개당 단가를 꼭 계산해봐야 합니다. 용량이 많아 보여도 개수가 적으면 결국 단가가 높아집니다.

둘째, 성분과 안전성입니다. 특히 피부가 예민한 분들이나 아이가 있는 가정에서는 성분표를 꼭 확인해야 합니다. 자극적인 성분이나 형광 증백제 여부를 체크하는 게 좋습니다.

셋째, 브랜드 신뢰도와 후기입니다. 리뷰 수와 별점 못지않게, 실제 사용자들이 어떤 점을 좋아하고 불편해하는지 확인하는 것이 중요합니다. 리뷰 1,000개 이상의 제품이라면 어느 정도 검증된 제품으로 볼 수 있습니다.


■ 현재 쿠팡 최저가 한눈에 보기

{price_summary}
※ 쿠팡 로켓배송 제품은 오늘 주문 시 내일 도착 가능한 경우가 많습니다. 빠른 배송이 필요하다면 로켓배송 여부도 꼭 확인하세요.


■ 자주 묻는 질문 (FAQ)

Q. 세 제품 중 가격 대비 가장 가성비가 좋은 건 어느 것인가요?
A. 단가 기준으로는 위에 링크된 제품들을 직접 비교해보시는 걸 추천드립니다. 쿠팡 상품 페이지에서 수량과 가격을 보고 개당 단가를 계산해보세요.

Q. 로켓배송으로 받을 수 있나요?
A. 위 링크 제품들은 대부분 쿠팡 로켓배송이 적용돼 있어 빠르게 받아보실 수 있습니다. 상품 페이지에서 로켓배송 마크를 꼭 확인하세요.

Q. 할인 쿠폰이나 추가 할인도 받을 수 있나요?
A. 쿠팡 회원이라면 첫 구매 할인, 카드사 할인, 쿠팡캐시 적립 등 다양한 혜택을 추가로 받을 수 있습니다. 결제 시 적용 가능한 쿠폰을 반드시 확인해보세요.


■ 더 자세한 비교 분석 보기

성분 구성, 실제 사용 후기, 항목별 가성비 비교를 더 꼼꼼하게 확인하고 싶은 분들을 위해 별도 포스팅을 정리해뒀습니다. 구매 전에 한번 읽어보시면 후회 없는 선택을 하실 수 있을 거예요 👇

CARD_URL:{original_url}


■ 마무리

오늘 소개해드린 제품들은 모두 쿠팡에서 빠르게 받아볼 수 있고, 실제 구매자 리뷰도 많아 신뢰할 수 있는 제품들입니다.

{title}로 고민하고 계신 분들께 이 글이 조금이라도 도움이 됐으면 좋겠습니다. 구매 후 실제로 사용해보신 분들은 댓글로 후기 남겨주시면 저도 참고하겠습니다 😊

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
