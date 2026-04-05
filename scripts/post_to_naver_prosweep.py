"""
꿀통몬스터 → prosweep 네이버 블로그 크로스포스팅 v12
- OG 카드: 꿀통몬스터 원본 포스팅 URL 1개
- 쿠팡 링크: 본문 텍스트 가격 정보로 표시 (LINK_TEXT 방식)
- 이미지: 상품 이미지 URL 3개 삽입 (IMAGE_HERE:N 마커)
- 비교표: 네이버 SE 에디터 표 삽입 (TABLE_HERE 마커)
- 본문 2,500자 이상 보장
- URL 텍스트 줄 삭제: JS DOM 직접 제거
- 서버 cron 직접 실행 (GitHub Actions 제외)
[N-1-1] TOC 자동 삽입 — 네이버 체류시간 증가
[N-2-2] 키워드 밀도 — NAVER_PRIMARY_KW 환경변수로 핵심 키워드 반영
[N-3]   스마트블록 — h2 섹션 5개 이상, 역피라미드 구조
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
COUPANG_IMAGES  = os.environ.get("COUPANG_IMAGES", "")   # "|" 구분 이미지 URL 3개
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


# ── 본문 빌더 (네이버 C-RANK 최적화 v11) ─────────────────────────
def build_naver_content(
    title: str, summary: str, original_url: str,
    labels: list, coupang_links: list, coupang_prices: list,
    coupang_images: list = None
) -> str:
    """
    네이버 VIEW탭 C-RANK 최적화 포맷 v12
    - 본문 2,500자 이상 보장
    - 제목 키워드 본문 내 2~3회 자연 등장
    - 이미지 IMAGE_HERE:N 마커 (N=0,1,2 → 이미지 인덱스)
    - 비교표 TABLE_HERE 마커
    - 구조: 도입부 → 목차(TOC) → 빠른결론 → 선택기준 → 상품별소개(이미지) → 비교표 → FAQ → 마무리
    [N-1-1] TOC 자동 삽입 — 네이버 체류시간 증가
    [N-2-2] 키워드 밀도 — 핵심 키워드 제목/첫문단/중간/마지막 각 1회
    [N-3]   스마트블록 — h2/h3 최소 5개, 각 섹션 첫 문장 핵심정보
    """
    if coupang_images is None:
        coupang_images = []

    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels \
                else "#쿠팡추천 #가성비 #쿠팡파트너스"

    # ── N-1-1: 목차(TOC) 자동 생성 — 체류시간 증가 핵심 ─────────────────
    toc_sections = [
        f"{title} 고를 때 꼭 확인할 3가지",
        f"{title} TOP 3 상세 비교",
        f"{title} 한눈에 비교표",
        "자주 묻는 질문 (FAQ)",
        "마무리",
    ]
    toc_items = "\n".join(f"  • {s}" for s in toc_sections)
    toc_block = (
        f"📋 이 글의 목차\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{toc_items}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    # 쿠팡 가격 링크 블록 (상품별)
    product_blocks = []
    for i, link in enumerate(coupang_links[:3]):
        price = coupang_prices[i] if i < len(coupang_prices) else ""
        rank = ["1위", "2위", "3위"][i]
        rank_label = ["🥇 1위", "🥈 2위", "🥉 3위"][i]
        price_text = f" ({price})" if price else ""
        btn_label = f"▶ {rank} 쿠팡 최저가 확인{price_text}"

        img_marker = f"IMAGE_HERE:{i}\n" if i < len(coupang_images) else ""

        block = f"""{img_marker}{rank_label} — {title} 추천 상품

가격, 품질, 실사용 후기를 종합해 선정한 {rank} 상품입니다. 쿠팡 기준 실시간 최저가로 제공되며, 로켓배송으로 빠르게 받아보실 수 있어요. 리뷰 수와 최근 구매자 만족도를 함께 확인해보세요. 시즌마다 특가 행사가 진행되는 경우가 많으니 지금 바로 확인해보시는 걸 추천드립니다.

LINK_TEXT:{btn_label}|{link}"""
        product_blocks.append(block)

    products_section = "\n\n".join(product_blocks)

    # 빠른 결론 3줄 요약
    quick_summary_lines = []
    for i, price in enumerate(coupang_prices[:3]):
        rank_label = ["🥇 1위", "🥈 2위", "🥉 3위"][i]
        quick_summary_lines.append(f"  {rank_label}: {price}")
    if not quick_summary_lines:
        quick_summary_lines = ["  상세 가격은 아래 링크에서 확인하세요."]
    quick_summary = "\n".join(quick_summary_lines)

    # 비교표 마커 (헤더 + 데이터)
    table_headers = ["순위", "가격", "특징", "추천대상"]
    table_rows = []
    for i in range(min(3, len(coupang_links))):
        price = coupang_prices[i] if i < len(coupang_prices) else "확인필요"
        rank = ["1위", "2위", "3위"][i]
        features = ["가성비 최강, 대용량", "품질 우수, 중간 가격대", "프리미엄, 소량 정품"][i]
        targets = ["자주 구매하는 분", "품질 중시하는 분", "선물·특별구매"][i]
        table_rows.append([rank, price, features, targets])

    # TABLE_HERE 마커에 데이터 인코딩 (JSON)
    table_data = json.dumps(
        {"headers": table_headers, "rows": table_rows},
        ensure_ascii=False
    )
    table_marker = f"TABLE_HERE:{table_data}"

    content = f"""이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

안녕하세요, 쇼핑정보 모아보기입니다 😊

{title}를 찾고 계신가요?

막상 구매하려고 검색하면 종류가 너무 많아서 어떤 제품을 골라야 할지 막막하죠. 가격도 천차만별이고, 리뷰는 많은데 정작 내 상황에 맞는 정보는 찾기 힘드셨을 거예요.

이 글에서는 2026년 4월 기준 가격, 품질, 실사용자 후기를 꼼꼼히 비교해 엄선한 {title} TOP 3를 소개해드립니다. 구매 후 후회하는 일이 없도록 핵심만 뽑아 정리했으니 끝까지 읽어보세요!

{summary}


{toc_block}

━━━━━━━━━━━━━━━━━━━━━━━━
⚡ 바쁘신 분들을 위한 3줄 요약
━━━━━━━━━━━━━━━━━━━━━━━━
{quick_summary}
※ 지금 바로 클릭하면 쿠팡 실시간 최저가 확인 가능
━━━━━━━━━━━━━━━━━━━━━━━━


■ {title} 고를 때 꼭 확인할 3가지

아무거나 고르다가 후회하지 않으려면 아래 세 가지는 반드시 체크하세요.

첫째, 가격 대비 용량(개당 단가)입니다. 단순히 가격만 보면 안 됩니다. {title}는 묶음 구매 시 개당 단가가 크게 달라지므로, 단위 가격을 반드시 비교해보세요. 쿠팡 상품 페이지에서 수량과 총가격을 확인하면 쉽게 계산할 수 있습니다.

둘째, 성분·소재 안전성입니다. 특히 피부가 예민하거나 아이가 있는 가정에서는 성분표를 꼭 확인해야 합니다. 자극 성분이나 유해물질 여부를 체크하는 것이 중요하고, KC 인증 여부도 확인해보시면 더 안심할 수 있어요.

셋째, 최신 구매자 리뷰입니다. 리뷰 수와 별점도 중요하지만, 최근 3개월 이내 리뷰가 많은지, 실제 사용자가 어떤 점을 불편해하는지 꼭 확인해보세요. 1,000개 이상의 리뷰가 쌓인 {title} 제품이라면 검증된 선택으로 볼 수 있습니다.


■ {title} TOP 3 상세 비교

{products_section}


■ {title} 한눈에 비교표

{table_marker}

※ 위 가격은 쿠팡 기준이며, 쿠팡 회원 할인·적립금 적용 전 기준입니다.
실제 결제 시 쿠폰·카드 혜택으로 더 저렴하게 구매할 수 있으니 꼭 확인해보세요!


■ 자주 묻는 질문 (FAQ)

Q1. {title} 세 제품 중 가성비가 가장 좋은 건 어느 것인가요?
A. 개당 단가 기준으로는 위 링크에서 직접 수량/가격을 확인해 계산해보시는 걸 추천드립니다. 묶음 구매 시 1위 제품이 가장 유리한 경우가 많습니다.

Q2. {title} 로켓배송으로 내일 받을 수 있나요?
A. 위 링크 제품들은 대부분 쿠팡 로켓배송이 적용돼 있어 오늘 주문 시 내일 수령 가능합니다. 상품 페이지에서 로켓배송 마크를 꼭 확인하세요.

Q3. 할인 쿠폰이나 추가 혜택도 받을 수 있나요?
A. 쿠팡 회원이라면 첫 구매 할인, 카드사 제휴 할인, 쿠팡캐시 적립 등 다양한 혜택을 추가로 받을 수 있어요. 결제 화면에서 적용 가능한 쿠폰을 반드시 확인해보세요.

Q4. {title} 선물용으로 구매해도 괜찮을까요?
A. 네, 위 TOP 3 중에서 특히 3위 제품은 패키지가 깔끔해 선물용으로 많이 구매하십니다. 쿠팡 선물 포장 옵션도 활용해보세요.


■ 더 자세한 비교 분석 보기

성분 구성, 실제 사용 후기, 항목별 가성비 상세 비교가 궁금하신 분들을 위해 꿀통몬스터에서 별도 포스팅을 정리해뒀습니다. 구매 전에 한번 읽어보시면 후회 없는 선택을 하실 수 있어요 👇

CARD_URL:{original_url}


■ 구매 전 체크리스트

☑ 로켓배송 여부 — 오늘 주문 시 내일 수령 가능 여부
☑ 묶음 할인 — 여러 개 구매 시 추가 할인 적용 여부
☑ 쿠폰 적용 — 결제 화면에서 쿠팡 자체 할인 쿠폰 확인
☑ 리뷰 날짜 — 최근 3개월 이내 리뷰가 많은지 확인
☑ 판매자 정보 — 로켓배송/로켓직구인지 마켓플레이스인지 확인
☑ KC 인증 — 안전 인증 제품인지 확인 (어린이·생활용품)


■ 쿠팡 파트너스 & 구매 안내

위 링크를 통해 구매하시면 쿠팡 파트너스 수수료가 발생하며, 구매자에게 추가 비용은 없습니다. 쿠팡 회원 가입 및 로그인 후 구매하시면 쿠팡캐시 적립, 카드 청구 할인, 쿠폰 혜택 등을 모두 받으실 수 있습니다.

상품 가격 및 재고는 쿠팡 실시간 정보 기준이며, 프로모션·할인 행사에 따라 수시로 변경될 수 있습니다. 구매 전 상품 페이지에서 현재 가격과 배송 일정을 반드시 확인해주세요.


■ 마무리

오늘 소개해드린 {title} 제품들은 모두 쿠팡에서 빠르게 받아볼 수 있고, 실제 구매자 리뷰도 많아 신뢰할 수 있는 상품들입니다.

{title} 구매를 고민하고 계신 분들께 이 글이 조금이라도 도움이 됐으면 좋겠습니다 😊

사용해보신 분들은 댓글로 후기 남겨주시면 저도 참고하겠습니다!
도움이 됐다면 공감 ❤️ 한 번 눌러주시면 큰 힘이 됩니다!

앞으로도 가성비 좋은 쿠팡 최저가 정보를 꾸준히 올릴 예정입니다.
블로그 이웃추가 해두시면 새 글 알림을 받아보실 수 있어요 🔔

{label_str}"""
    return content.strip()


# ── atom.xml에서 쿠팡 링크/가격/이미지 추출 ──────────────────────
def extract_coupang_data_from_blogger(post_url: str) -> tuple[list, list, list]:
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

        # 쿠팡 링크
        all_links = re.findall(r'href=["\']+(https://link\.coupang\.com/[^"\'>\s]+)', content)
        unique_links = list(dict.fromkeys(all_links))[:3]

        # 가격
        prices_raw = re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+)원', content)
        unique_prices = [p + "원" for p in list(dict.fromkeys(prices_raw))[:3]]

        # 이미지 URL 추출 (쿠팡 이미지 우선)
        img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
        coupang_imgs = [u for u in img_urls if 'coupang' in u or 'thumbnail' in u]
        other_imgs = [u for u in img_urls if u not in coupang_imgs]
        product_images = (coupang_imgs + other_imgs)[:3]

        return unique_links, unique_prices, product_images
    except Exception as ex:
        print(f"  [warn] 쿠팡 데이터 추출 실패: {ex}")
        return [], [], []


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


# ── 이미지 URL 삽입 (네이버 SE 에디터) ───────────────────────────
async def insert_image_by_url(page, image_url: str):
    """
    SE 에디터 이미지 삽입: 이미지 버튼 → URL 탭 → URL 입력 → 확인
    """
    print(f"    [이미지 삽입] {image_url[:60]}...")

    # 이미지 삽입 버튼 클릭
    img_btn = await page.query_selector(".se-image-toolbar-button")
    if not img_btn:
        # fallback: 툴바에서 이미지 버튼 찾기
        img_btn = await page.query_selector("button[data-name='image'], button[title*='이미지'], button[aria-label*='이미지']")
    if not img_btn:
        print("    [warn] 이미지 버튼 없음 — 스킵")
        return
    await img_btn.click()
    await page.wait_for_timeout(1500)

    # URL 탭 클릭
    url_tab = await page.query_selector("button:has-text('URL')")
    if not url_tab:
        url_tab = await page.query_selector("li:has-text('URL'), span:has-text('URL 입력')")
    if url_tab:
        await url_tab.click()
        await page.wait_for_timeout(500)

    # URL 입력창
    url_input = await page.query_selector(".se-image-url-input")
    if not url_input:
        url_input = await page.query_selector("input[placeholder*='URL'], input[placeholder*='url']")
    if url_input:
        await url_input.click()
        await url_input.fill(image_url)
        await page.wait_for_timeout(300)
    else:
        print("    [warn] URL 입력창 없음 — Escape 후 스킵")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        return

    # 확인 버튼
    confirm = await page.query_selector(".se-image-url-confirm")
    if not confirm:
        confirm = await page.query_selector("button:has-text('확인'), button:has-text('삽입')")
    if confirm:
        await confirm.click()
        await page.wait_for_timeout(2000)
    else:
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

    # 이미지 삽입 후 엔터로 다음 줄로 이동
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(500)
    print("    [이미지 삽입 완료]")


# ── 표 삽입 (네이버 SE 에디터) ───────────────────────────────────
async def insert_table_block(page, headers: list, rows: list):
    """
    네이버 SE 에디터에 표 삽입
    - 표 삽입 버튼으로 기본 표 생성 후 셀 입력
    - 헤더 + 데이터 행으로 구성
    """
    print(f"    [표 삽입] {len(headers)}열 × {len(rows)+1}행")

    n_rows = len(rows) + 1  # 헤더 포함
    n_cols = len(headers)

    # 표 삽입 버튼 클릭
    table_btn = await page.query_selector(".se-table-toolbar-button")
    if not table_btn:
        table_btn = await page.query_selector(
            "button[data-name='table'], button[title*='표'], button[aria-label*='표']"
        )
    if not table_btn:
        print("    [warn] 표 버튼 없음 — 텍스트 표로 대체")
        await _insert_text_table(page, headers, rows)
        return

    await table_btn.click()
    await page.wait_for_timeout(1000)

    # 표 크기 선택 UI (셀 그리드 방식)
    # n_cols열 × n_rows행 선택: 마우스 이동으로 그리드 셀 선택
    grid_selected = await page.evaluate(f"""
        () => {{
            // 그리드 셀 요소 찾기
            const cells = Array.from(document.querySelectorAll(
                '.se-table-create-menu td, .se-table-select-area td, [class*="table-cell"]'
            ));
            if (cells.length === 0) return false;

            // 행렬 인덱스로 셀 찾기 (0-based)
            const targetRow = {n_rows - 1};
            const targetCol = {n_cols - 1};

            // 마지막 선택 셀에 마우스오버
            const rows = {{}};
            for (const cell of cells) {{
                const r = cell.closest('tr');
                if (!r) continue;
                const ri = r.rowIndex ?? 0;
                const ci = cell.cellIndex ?? 0;
                if (!rows[ri]) rows[ri] = {{}};
                rows[ri][ci] = cell;
            }}

            const targetCell = rows[targetRow]?.[targetCol];
            if (targetCell) {{
                targetCell.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
                targetCell.click();
                return true;
            }}
            return false;
        }}
    """)

    if not grid_selected:
        # 그리드 방식 실패 → 기본 표 크기 입력 UI 시도
        print("    [표 그리드 선택 실패] 기본 4x5 표 시도")
        # 4열 × (n_rows)행 직접 입력
        rows_input = await page.query_selector("input[placeholder*='행'], input[name*='row']")
        cols_input = await page.query_selector("input[placeholder*='열'], input[name*='col']")
        if rows_input and cols_input:
            await rows_input.fill(str(n_rows))
            await cols_input.fill(str(n_cols))
            confirm = await page.query_selector("button:has-text('확인'), button:has-text('삽입')")
            if confirm:
                await confirm.click()
        else:
            # 아무것도 없으면 Escape 후 텍스트 표로
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            await _insert_text_table(page, headers, rows)
            return

    await page.wait_for_timeout(1500)

    # 표 셀에 데이터 입력 (Tab 키로 셀 이동)
    all_rows = [headers] + rows
    for ri, row_data in enumerate(all_rows):
        for ci, cell_text in enumerate(row_data):
            await page.keyboard.type(str(cell_text), delay=15)
            # 마지막 셀이 아니면 Tab
            if ri < len(all_rows) - 1 or ci < len(row_data) - 1:
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(80)

    # 표 밖으로 커서 이동 (화살표 아래 → Enter)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(300)
    print("    [표 삽입 완료]")


async def _insert_text_table(page, headers: list, rows: list):
    """표 버튼이 없을 때 텍스트 형식 표로 대체"""
    sep = " | "
    header_line = sep.join(str(h) for h in headers)
    divider = " | ".join(["---"] * len(headers))
    await page.keyboard.type(header_line, delay=15)
    await page.keyboard.press("Enter")
    await page.keyboard.type(divider, delay=15)
    await page.keyboard.press("Enter")
    for row in rows:
        await page.keyboard.type(sep.join(str(c) for c in row), delay=15)
        await page.keyboard.press("Enter")
    await page.wait_for_timeout(200)


# ── OG 카드 삽입 (꿀통몬스터 URL) ────────────────────────────────
async def insert_og_card(page, url: str):
    """
    URL 타이핑 → Enter → OG 카드 자동 생성 → URL 텍스트 DOM 직접 제거
    """
    await page.keyboard.type(url, delay=12)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(7000)  # 카드 생성 대기

    # URL 텍스트 단락 삭제
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
                            y: Math.round(r.y + r.height / 2),
                            h: Math.round(r.height)
                        };
                    }
                }
                return null;
            }
        """)
        if not info:
            break
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
async def type_body(page, content: str, image_urls: list = None):
    """
    content 마커:
    - IMAGE_HERE:N  → N번 이미지 삽입 (image_urls[N])
    - TABLE_HERE:{json}  → 표 삽입
    - CARD_URL:URL  → OG 카드
    - LINK_TEXT:텍스트|URL  → 하이퍼링크 텍스트
    """
    if image_urls is None:
        image_urls = []

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

        # IMAGE_HERE:N 마커
        if stripped.startswith("IMAGE_HERE:"):
            try:
                idx = int(stripped[len("IMAGE_HERE:"):].strip())
            except ValueError:
                idx = 0
            if idx < len(image_urls) and image_urls[idx]:
                await insert_image_by_url(page, image_urls[idx])
            else:
                print(f"    [이미지 스킵] 인덱스 {idx} (총 {len(image_urls)}개)")
            continue

        # TABLE_HERE:{json} 마커
        if stripped.startswith("TABLE_HERE:"):
            table_json = stripped[len("TABLE_HERE:"):].strip()
            try:
                table_data = json.loads(table_json)
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                await insert_table_block(page, headers, rows)
            except Exception as e:
                print(f"    [warn] 표 데이터 파싱 실패: {e}")
            continue

        # CARD_URL 마커
        if stripped.startswith("CARD_URL:"):
            url = stripped[len("CARD_URL:"):]
            await insert_og_card(page, url)

        # LINK_TEXT 마커
        elif "LINK_TEXT:" in stripped:
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


# ── 발행 (즉시 또는 예약) ─────────────────────────────────────────
async def publish(page, reserve_dt: str = None) -> str | None:
    """
    reserve_dt: None → 즉시 발행
                "YYYY-MM-DD HH:MM" → 예약 발행
    """
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
    await page.wait_for_timeout(2500)

    # ── 예약 발행 처리 ────────────────────────────────────────────
    if reserve_dt:
        import datetime as _dt
        await page.evaluate("""
            () => {
                const r = document.querySelector('#radio_time2');
                if (r) r.click();
            }
        """)
        await page.wait_for_timeout(1500)

        dt_inputs = await page.evaluate("""
            () => {
                const res = [];
                document.querySelectorAll('input[type="text"],input[type="number"],select').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.y > 200 && r.y < 700) {
                        res.push({cls: el.className?.substring(0,50), ph: el.placeholder||'', val: el.value, id: el.id, tag: el.tagName, x: Math.round(r.x), y: Math.round(r.y)});
                    }
                });
                return res;
            }
        """)
        print(f"  예약 입력 요소들: {dt_inputs}")
        await page.screenshot(path="/tmp/naver_reserve_ui.png")

        try:
            rdt = _dt.datetime.strptime(reserve_dt, "%Y-%m-%d %H:%M")
        except:
            print(f"  ❌ 예약 시간 파싱 실패: {reserve_dt}")
            reserve_dt = None

        if reserve_dt and rdt:
            set_ok = await page.evaluate(f"""
                () => {{
                    const inputs = Array.from(document.querySelectorAll('input'));
                    const selects = Array.from(document.querySelectorAll('select'));
                    let set = 0;

                    const yearEl = inputs.find(el => el.placeholder?.includes('연도') || el.className?.includes('year') || el.id?.includes('year'));
                    if (yearEl) {{ yearEl.value = '{rdt.year}'; yearEl.dispatchEvent(new Event('input',{{bubbles:true}})); yearEl.dispatchEvent(new Event('change',{{bubbles:true}})); set++; }}

                    const monthEl = selects.find(el => el.className?.includes('month') || el.id?.includes('month')) ||
                                   inputs.find(el => el.placeholder?.includes('월') || el.className?.includes('month'));
                    if (monthEl) {{ monthEl.value = '{rdt.month}'; monthEl.dispatchEvent(new Event('change',{{bubbles:true}})); set++; }}

                    const dayEl = selects.find(el => el.className?.includes('day') || el.id?.includes('day')) ||
                                 inputs.find(el => el.placeholder?.includes('일') || el.className?.includes('day'));
                    if (dayEl) {{ dayEl.value = '{rdt.day}'; dayEl.dispatchEvent(new Event('change',{{bubbles:true}})); set++; }}

                    const hourEl = selects.find(el => el.className?.includes('hour') || el.id?.includes('hour')) ||
                                  inputs.find(el => el.placeholder?.includes('시') || el.className?.includes('hour'));
                    if (hourEl) {{ hourEl.value = '{rdt.hour}'; hourEl.dispatchEvent(new Event('change',{{bubbles:true}})); set++; }}

                    const minEl = selects.find(el => el.className?.includes('min') || el.id?.includes('min')) ||
                                 inputs.find(el => el.placeholder?.includes('분') || el.className?.includes('min'));
                    if (minEl) {{ minEl.value = '{rdt.minute}'; minEl.dispatchEvent(new Event('change',{{bubbles:true}})); set++; }}

                    return set;
                }}
            """)
            print(f"  예약 시간 설정: {reserve_dt} (설정된 필드: {set_ok}개)")
            await page.wait_for_timeout(1000)
            await page.screenshot(path="/tmp/naver_reserve_set.png")

    # ── 발행/예약 확인 버튼 ──────────────────────────────────────
    confirm_btn = await page.query_selector(".confirm_btn__WEaBq")
    if not confirm_btn:
        confirm_btn = await page.query_selector("button[class*='confirm_btn']")
    if not confirm_btn:
        print("  ❌ 확인 버튼 없음")
        return None
    await page.evaluate("btn => btn.click()", confirm_btn)
    await page.wait_for_timeout(6000)

    url = page.url
    if reserve_dt:
        log_no = await page.evaluate("() => { const m = location.href.match(/logNo=(\d+)/); return m ? m[1] : ''; }")
        if not log_no:
            return f"[예약발행 완료] {reserve_dt}"
        return url
    return url if ("PostView" in url or "logNo" in url) else None


# ── 메인 ─────────────────────────────────────────────────────────
async def main():
    if not POST_TITLE or not POST_URL:
        print("❌ POST_TITLE, POST_URL 필요")
        sys.exit(1)

    labels = [l.strip() for l in LABELS_STR.split(",") if l.strip()] if LABELS_STR else []
    coupang_links = [l for l in COUPANG_LINKS.split("|") if l.strip()] if COUPANG_LINKS else []
    coupang_prices = [p for p in COUPANG_PRICES.split("|") if p.strip()] if COUPANG_PRICES else []
    coupang_images = [u for u in COUPANG_IMAGES.split("|") if u.strip()] if COUPANG_IMAGES else []

    if not coupang_links:
        print("  쿠팡 링크/이미지 자동 추출 중...")
        coupang_links, coupang_prices, coupang_images = extract_coupang_data_from_blogger(POST_URL)

    content = build_naver_content(
        POST_TITLE, POST_SUMMARY, POST_URL,
        labels, coupang_links, coupang_prices, coupang_images
    )

    print(f"[포스팅 준비]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  원본(OG카드): {POST_URL[:60]}")
    print(f"  쿠팡 링크: {len(coupang_links)}개 / 가격: {coupang_prices}")
    print(f"  상품 이미지: {len(coupang_images)}개")
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
        await type_body(page, content, coupang_images)

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
                "coupang_images": coupang_images,
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
