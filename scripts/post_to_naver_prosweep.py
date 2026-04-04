"""
꿀통몬스터 → prosweep 네이버 블로그 크로스포스팅 v2
- 네이버 C-RANK / VIEW탭 / 스마트블록 최적화 포맷
- 쿠팡 파트너스 링크 직접 삽입 + 백링크 병행 전략
- Xvfb + headed Playwright (SE 에디터 렌더링)

사용법:
  NAVER_ID=xxx NAVER_PW=xxx \\
  POST_TITLE="제목" POST_URL="https://..." POST_SUMMARY="요약" \\
  COUPANG_LINKS="url1|url2|url3" COUPANG_PRICES="7,360원|12,900원|10,900원" \\
  LABELS="태그1,태그2" \\
  python3 post_to_naver_prosweep.py
"""
import os, sys, asyncio, json, time, re
from pathlib import Path

# ── 환경변수 ──────────────────────────────────────────────────────
NAVER_ID        = os.environ.get("NAVER_ID", "")
NAVER_PW        = os.environ.get("NAVER_PW", "")
BLOG_ID         = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO     = os.environ.get("NAVER_CATEGORY_NO", "6")
POST_TITLE      = os.environ.get("POST_TITLE", "")
POST_URL        = os.environ.get("POST_URL", "")           # ggultongmon 원본 URL (백링크)
POST_SUMMARY    = os.environ.get("POST_SUMMARY", "")
LABELS_STR      = os.environ.get("LABELS", "")
COUPANG_LINKS   = os.environ.get("COUPANG_LINKS", "")      # "|" 구분 쿠팡 링크들
COUPANG_PRICES  = os.environ.get("COUPANG_PRICES", "")     # "|" 구분 가격들
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


# ── 네이버 C-RANK / VIEW탭 최적화 포맷 v2 ─────────────────────────
def build_naver_content(
    title: str, summary: str, original_url: str,
    labels: list, coupang_links: list, coupang_prices: list
) -> str:
    """
    네이버 VIEW탭 / 스마트블록 최적화 전략:
    1. 체류시간 확보 — 충분한 본문 길이 (500자 이상)
    2. 키워드 반복 — 제목 키워드를 본문 3회 이상 자연스럽게
    3. 쿠팡 링크 중간 삽입 (1~2개) — 체류 중 전환 유도
    4. 백링크는 하단 1개 — 자연스러운 외부 연결
    5. 볼드 강조 — 스크롤 중 핵심 키워드 눈에 띄게
    6. 공감 유도 문구 — 마지막에 배치
    7. 해시태그 — 본문 끝, 8개 이하
    """
    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels \
                else "#쿠팡추천 #가성비 #쿠팡파트너스"
    
    # 쿠팡 링크 블록 구성 (최대 2개 — 중간 삽입용)
    coupang_mid = ""
    if coupang_links:
        link_lines = []
        for i, (link, price) in enumerate(zip(coupang_links[:2], coupang_prices[:2] or [""] * 2)):
            price_str = f" — {price}" if price else ""
            link_lines.append(f"  → 쿠팡 최저가 확인{price_str}: {link}")
        coupang_mid = "\n".join(link_lines)

    # 3번째 링크 (있을 경우 하단 추가)
    coupang_bottom = ""
    if len(coupang_links) >= 3:
        p = coupang_prices[2] if len(coupang_prices) > 2 else ""
        price_str = f" ({p})" if p else ""
        coupang_bottom = f"\n  → 3번째 상품 쿠팡 바로가기{price_str}: {coupang_links[2]}"

    content = f"""안녕하세요, 쇼핑정보 모아보기 소모입니다 :)

오늘은 **{title}** 정보를 정리해 드리려고요.
쿠팡에서 직접 비교해 보면 생각보다 가격 차이나 성분 차이가 꽤 크더라고요.
구매 전에 이 글 한 번만 읽으시면 후회 없는 선택 하실 수 있을 거예요!

이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.


◆ 핵심 요약 ◆

{summary}


◆ 이런 분들께 추천드려요 ◆

✔ **{title.split(' ')[0]}** 구매를 고민 중이신 분
✔ 여러 제품을 비교하고 싶은데 시간이 없는 분
✔ 가성비와 품질 두 마리 토끼를 잡고 싶은 분
✔ 실제 사용자 후기와 성분 정보가 궁금한 분
"""

    # 쿠팡 링크 중간 삽입
    if coupang_mid:
        content += f"""

◆ 쿠팡 최저가 바로 확인 ◆

{coupang_mid}
"""

    content += f"""

◆ 상품 선택 팁 ◆

**첫 번째로 확인할 것은 가격 대비 용량**입니다.
같은 브랜드라도 묶음 구성에 따라 장당 단가가 크게 달라집니다.
쿠팡에서는 정기배송을 활용하면 추가 5~10% 할인을 받을 수 있어요.

**두 번째는 성분과 인증 여부**입니다.
민감한 피부라면 알레르기 유발 성분이 없는지 꼭 확인하세요.
KC 인증 / 무형광 / 무향 여부를 체크하는 습관을 들이면 좋습니다.

**세 번째는 시트 두께와 사이즈**입니다.
한 장으로 넓은 면적을 닦을 수 있는 두껍고 큰 시트가 실용적이에요.
실제 리뷰 사진을 꼭 확인해 보시길 권장드립니다.{coupang_bottom}


◆ 자세한 비교 분석 보기 ◆

더 꼼꼼한 상품 비교, 실제 사용 후기, 쿠팡 최저가 정보는
아래 꿀통몬스터 포스팅에서 확인하실 수 있어요.

▶ {original_url}


오늘도 현명한 쇼핑 되세요! 😊
도움이 됐다면 공감 꾹 눌러주세요 — 다음 포스팅에 큰 힘이 됩니다 ♥

{label_str}"""

    return content.strip()


# ── atom.xml에서 쿠팡 링크/가격 추출 ─────────────────────────────
def extract_coupang_data_from_blogger(post_url: str) -> tuple[list, list]:
    """ggultongmon 포스트에서 쿠팡 링크·가격 추출"""
    import urllib.request
    try:
        feed_req = urllib.request.Request(
            "https://ggultongmon.allsweep.xyz/atom.xml",
            headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        )
        import xml.etree.ElementTree as ET
        with urllib.request.urlopen(feed_req, timeout=10) as r:
            raw = r.read().decode()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)

        # URL로 매칭되는 entry 탐색 (없으면 최신글)
        target = None
        for e in entries:
            c = e.findtext('atom:content', namespaces=ns) or ''
            canon = re.search(r'"url"\s*:\s*"(' + re.escape(post_url) + r')"', c)
            if canon:
                target = e
                break
        if not target:
            target = entries[0]

        content = target.findtext('atom:content', namespaces=ns) or ''

        # 유니크 쿠팡 링크
        all_links = re.findall(r'href=["\']+(https://link\.coupang\.com/[^"\'>\s]+)', content)
        unique_links = list(dict.fromkeys(all_links))[:3]

        # 가격
        prices_raw = re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+)원', content)
        unique_prices = [p + "원" for p in list(dict.fromkeys(prices_raw))[:3]]

        return unique_links, unique_prices
    except Exception as ex:
        print(f"  [warn] 쿠팡 데이터 추출 실패: {ex}")
        return [], []


# ── 로그인 & 세션 관리 ────────────────────────────────────────────
async def ensure_session(context, page) -> bool:
    await page.goto("https://blog.naver.com", timeout=20000)
    await page.wait_for_timeout(2000)
    for frame in page.frames:
        try:
            logout = await frame.query_selector("a[href*='nidlogin.logout']")
            if logout:
                print("  세션 유효 ✅")
                return True
        except:
            pass
    print("  세션 만료 → 재로그인...")
    return await do_login(page, context)


async def do_login(page, context) -> bool:
    if not NAVER_ID or not NAVER_PW:
        print("  ❌ NAVER_ID/PW 없음")
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
        await context.storage_state(path=SESSION_FILE)
        print(f"  세션 저장: {SESSION_FILE}")
        return True
    print("  ❌ 로그인 실패")
    return False


# ── SE 에디터 조작 ───────────────────────────────────────────────
async def handle_popups(page):
    try:
        close_btn = await page.query_selector(".se-help-panel-close-button")
        if close_btn:
            await close_btn.click()
            await page.wait_for_timeout(300)
    except:
        pass
    await page.evaluate("""
        () => {
            const p = document.querySelector('.__se-pop-layer');
            if (!p) return;
            const btns = p.querySelectorAll('button');
            for (const b of btns) { if (b.innerText.trim() === '취소') { b.click(); break; } }
        }
    """)
    await page.wait_for_timeout(1500)
    # layer_popup 제거
    await page.evaluate("document.querySelectorAll('.layer_popup__i0QOY').forEach(el=>el.style.display='none')")
    await page.wait_for_timeout(300)


async def type_title(page, title: str):
    await page.mouse.click(400, 232)
    await page.wait_for_timeout(400)
    await page.keyboard.type(title, delay=50)
    await page.wait_for_timeout(300)


async def type_body(page, content: str):
    await page.mouse.click(400, 340)
    await page.wait_for_timeout(400)
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line:
            await page.keyboard.type(line, delay=20)
        if i < len(lines) - 1:
            await page.keyboard.press("Enter")
    await page.wait_for_timeout(300)


async def publish(page) -> str | None:
    # layer_popup 한번 더 제거 후 JS 클릭
    await page.evaluate("document.querySelectorAll('.layer_popup__i0QOY').forEach(el=>el.style.display='none')")
    await page.evaluate("document.querySelector('.publish_btn__m9KHH').click()")
    await page.wait_for_timeout(3000)

    confirm_btn = await page.query_selector(".confirm_btn__WEaBq")
    if not confirm_btn:
        print("  ❌ 확인 버튼 없음")
        return None
    await page.evaluate("document.querySelector('.confirm_btn__WEaBq').click()")
    await page.wait_for_timeout(6000)

    url = page.url
    return url if ("PostView" in url or "logNo" in url) else None


# ── 메인 ─────────────────────────────────────────────────────────
async def main():
    if not POST_TITLE or not POST_URL:
        print("❌ POST_TITLE, POST_URL 필요")
        sys.exit(1)

    labels = [l.strip() for l in LABELS_STR.split(",") if l.strip()] if LABELS_STR else []

    # 쿠팡 링크/가격 우선순위: 환경변수 > atom.xml 자동 추출
    coupang_links = [l for l in COUPANG_LINKS.split("|") if l.strip()] if COUPANG_LINKS else []
    coupang_prices = [p for p in COUPANG_PRICES.split("|") if p.strip()] if COUPANG_PRICES else []
    if not coupang_links:
        print("  쿠팡 링크 자동 추출 중...")
        coupang_links, coupang_prices = extract_coupang_data_from_blogger(POST_URL)

    content = build_naver_content(POST_TITLE, POST_SUMMARY, POST_URL, labels, coupang_links, coupang_prices)

    print(f"[포스팅 준비]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  원본(백링크): {POST_URL[:60]}")
    print(f"  쿠팡 링크: {len(coupang_links)}개")
    print(f"  가격: {coupang_prices}")
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
            await browser.close()
            sys.exit(1)

        print(f"\n[에디터 로드] {WRITE_URL}")
        await page.goto(WRITE_URL, timeout=30000)
        await page.wait_for_timeout(8000)
        await handle_popups(page)

        print("[입력 중...]")
        await type_title(page, POST_TITLE)
        await type_body(page, content)

        print("[발행 중...]")
        result_url = await publish(page)

        if result_url:
            print(f"\n✅ 발행 성공!")
            print(f"  URL: {result_url}")
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
            sys.exit(1)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
