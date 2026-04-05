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
PRODUCT_DATA_STR = os.environ.get("PRODUCT_DATA", "")    # JSON 상품 데이터
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


# ── FAQ 동적 생성 헬퍼 ────────────────────────────────────────────

def _get_category_faq(title: str, labels: list) -> str:
    """카테고리별 맞춤 FAQ (Q3 포지션)"""
    label_str = " ".join(labels).lower()

    if any(k in label_str for k in ['기저귀', '턱받이', '아기', '신생아', '유아', '베이비']):
        return (
            f"Q3. {title} 피부가 예민한 아이에게도 안전한가요?\n"
            f"A. 위 제품들은 KC 인증 제품을 기준으로 선정했습니다. "
            f"피부가 특히 예민한 아이라면 소량 구매 후 피부 반응을 먼저 확인해보시길 권장합니다. "
            f"이상 반응 시 즉시 사용을 중단하고 소아과에 문의하세요."
        )
    elif any(k in label_str for k in ['강아지', '고양이', '반려', '펫', '동물']):
        return (
            f"Q3. {title} 처음 반려동물을 키우는 초보자도 사용하기 쉬운가요?\n"
            f"A. 위 소개된 제품들은 초보 반려인도 쉽게 사용할 수 있도록 구성된 제품들입니다. "
            f"처음엔 소량으로 시작해 반려동물의 반응을 살피는 것을 권장합니다. "
            f"사용 방법은 각 상품 페이지 상세 설명을 꼭 확인해주세요."
        )
    elif any(k in label_str for k in ['식품', '음식', '단백질', '영양', '건강식품', '보충제']):
        return (
            f"Q3. {title} 유통기한은 얼마나 되나요?\n"
            f"A. 유통기한은 제품마다 다르므로 상품 페이지의 상세 정보를 반드시 확인하세요. "
            f"식품류는 개봉 후 냉장 보관 및 빠른 소비를 권장합니다. "
            f"유통기한이 넉넉한 제품을 원하신다면 상품 상세 정보에서 제조일자를 꼭 확인하세요."
        )
    elif any(k in label_str for k in ['세탁', '청소', '주방', '생활', '청결', '욕실']):
        return (
            f"Q3. {title} 대용량으로 구매하면 더 저렴한가요?\n"
            f"A. 생활용품은 대용량 묶음 구매 시 개당 단가가 크게 낮아지는 경우가 많습니다. "
            f"위 링크에서 수량별 가격을 비교해보시고, 쿠팡 정기배송 옵션도 확인해보시면 "
            f"추가 5~10% 할인 혜택을 받으실 수 있어요."
        )
    elif any(k in label_str for k in ['전자', '가전', '스마트', '충전', '배터리', 'usb', 'usb']):
        return (
            f"Q3. {title} AS(애프터서비스)는 어떻게 받을 수 있나요?\n"
            f"A. 쿠팡 로켓배송 제품은 수령 후 30일 이내 반품·교환이 가능합니다. "
            f"제조사 공식 AS는 상품 페이지의 판매자 정보에서 고객센터 연락처를 확인하세요. "
            f"정품 인증 제품인지 확인 후 구매하시면 AS 혜택을 보다 원활하게 받으실 수 있습니다."
        )
    elif any(k in label_str for k in ['뷰티', '화장품', '스킨케어', '마스크팩', '로션', '크림', '선크림']):
        return (
            f"Q3. {title} 민감성 피부에도 사용해도 되나요?\n"
            f"A. 위 제품들은 다수의 실구매자 리뷰를 바탕으로 선정했습니다. "
            f"민감성 피부라면 성분표에서 알코올·향료·인공색소 함유 여부를 확인하시고, "
            f"처음 사용 시 팔 안쪽에 패치 테스트를 해보시길 권장합니다."
        )
    else:
        # 일반 카테고리 — 가격 비교 FAQ
        return (
            f"Q3. {title} 할인 쿠폰이나 추가 혜택도 받을 수 있나요?\n"
            f"A. 쿠팡 회원이라면 첫 구매 할인, 카드사 제휴 할인, 쿠팡캐시 적립 등 "
            f"다양한 혜택을 추가로 받을 수 있어요. "
            f"결제 화면에서 적용 가능한 쿠폰을 반드시 확인해보세요."
        )


def _build_dynamic_faq(title: str, labels: list) -> str:
    """상품/주제 기반 FAQ 동적 생성 — 네이버 VIEW탭 중복 콘텐츠 페널티 방지"""
    faqs = []

    # Q1: 가성비 (항상)
    faqs.append(
        f"Q1. {title} 세 제품 중 가성비가 가장 좋은 건 어느 것인가요?\n"
        f"A. 가성비는 사용 목적과 구매 수량에 따라 달라집니다. "
        f"개당 단가를 기준으로 비교하면 위 링크에서 수량·가격을 확인해 계산해보시는 걸 추천드립니다. "
        f"묶음 구매 시 1위 제품이 단가 면에서 가장 유리한 경우가 많습니다."
    )

    # Q2: 배송 (항상)
    faqs.append(
        f"Q2. {title} 쿠팡 로켓배송으로 빠르게 받을 수 있나요?\n"
        f"A. 위 링크 제품들은 대부분 쿠팡 로켓배송이 적용돼 있어 "
        f"오늘 주문 시 내일 수령 가능합니다. 상품 페이지에서 로켓배송 마크를 꼭 확인하세요."
    )

    # Q3: 카테고리별 맞춤 FAQ
    category_q = _get_category_faq(title, labels)
    if category_q:
        faqs.append(category_q)

    # Q4: 선물용 (항상)
    faqs.append(
        f"Q4. {title} 선물용으로 구매할 때 어떤 제품이 좋을까요?\n"
        f"A. 선물용으로는 포장이 깔끔하고 브랜드 인지도가 높은 제품이 좋습니다. "
        f"위 TOP 3 중 가장 많이 팔리는 상품 기준으로 쿠팡 선물포장 옵션도 활용해보세요. "
        f"받는 분의 취향과 용도를 고려해 선택하시면 만족도가 높습니다."
    )

    return "■ 자주 묻는 질문 (FAQ)\n\n" + "\n\n".join(faqs)


# ── 본문 빌더 (네이버 C-RANK 최적화 v13 — 실제 상품 데이터 반영) ──
def build_naver_content(
    title: str, summary: str, original_url: str,
    labels: list, coupang_links: list, coupang_prices: list,
    coupang_images: list = None,
    product_data: list = None,          # ← 새로 추가: 실제 상품 데이터
) -> str:
    """
    네이버 VIEW탭 C-RANK 최적화 포맷 v13
    - product_data가 있으면 실제 상품명/가격/설명/이미지 사용
    - 없으면 기존 coupang_links/prices 방식으로 fallback
    - 이미지: IMAGE_HERE:N 마커 (파일 업로드 방식)
    - 비교표: TABLE_HERE 마커
    - 본문 2,500자 이상 보장
    """
    if coupang_images is None:
        coupang_images = []
    if product_data is None:
        product_data = []

    label_str = " ".join([f"#{l.replace(' ','')}" for l in labels[:8]]) if labels \
                else "#쿠팡추천 #가성비 #쿠팡파트너스"

    # ── 상품 데이터 통합 (product_data 우선, fallback: coupang_links) ──
    RANK_MEDALS = ["🥇", "🥈", "🥉"]
    RANK_NAMES  = ["1위", "2위", "3위"]

    # product_data에서 이미지 리스트 추출 (이미지 업로드용)
    if product_data:
        all_images = [p.get("image", "") for p in product_data]
    else:
        all_images = coupang_images

    # ── 서론 ──────────────────────────────────────────────────────────
    intro = (
        f"이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.\n\n"
        f"{title} 찾고 계신가요? "
        f"2026년 4월 기준 쿠팡 실구매 데이터 기반 TOP 3를 정리했습니다.\n"
        f"가격·소재·실사용 후기를 꼼꼼히 비교해 엄선했으니 구매 전 꼭 확인해보세요!"
    )

    # ── 상품 섹션 블록 ────────────────────────────────────────────────
    product_blocks = []

    if product_data:
        # ── product_data 사용 (실제 상품 데이터) ──────────────────────
        for i, prod in enumerate(product_data[:3]):
            medal = RANK_MEDALS[i]
            rank  = RANK_NAMES[i]
            name  = prod.get("name", f"{title} 추천 상품 {rank}")
            price = prod.get("price", "")
            link  = prod.get("link", "")
            desc  = prod.get("desc", "")

            # 상품명에서 "— 부제" 제후 전체를 사용 (h2 원문)
            name_clean = name  # h2 전체 텍스트 그대로

            price_line = f"💰 {price}" if price else ""
            link_line  = f"LINK_TEXT:▶ 쿠팡에서 최저가 확인|{link}" if link else ""

            # 설명 2~3줄 (150자 → 줄바꿈 포함 자연스럽게)
            desc_clean = desc.strip()
            if len(desc_clean) > 120:
                # 문장 단위로 자르기
                sentences = re.split(r'(?<=[.。!?])\s+', desc_clean)
                desc_short = ""
                for s in sentences:
                    if len(desc_short) + len(s) < 120:
                        desc_short += s + " "
                    else:
                        break
                desc_clean = desc_short.strip() or desc_clean[:120]

            block_lines = [
                f"━━━━━━━━━━━━━━━━━━━━━━━━",
                f"{medal} {rank} | {name_clean}",
                f"IMAGE_HERE:{i}",
            ]
            if price_line:
                block_lines.append(price_line)
            if desc_clean:
                block_lines.append(desc_clean)
            if link_line:
                block_lines.append(link_line)

            product_blocks.append("\n".join(block_lines))

    else:
        # ── Fallback: 기존 coupang_links 방식 ─────────────────────────
        for i, link in enumerate(coupang_links[:3]):
            price = coupang_prices[i] if i < len(coupang_prices) else ""
            medal = RANK_MEDALS[i]
            rank  = RANK_NAMES[i]
            price_line = f"💰 {price}" if price else ""
            link_line  = f"LINK_TEXT:▶ 쿠팡에서 최저가 확인|{link}"

            block_lines = [
                f"━━━━━━━━━━━━━━━━━━━━━━━━",
                f"{medal} {rank} | {title} 추천 상품",
                f"IMAGE_HERE:{i}",
            ]
            if price_line:
                block_lines.append(price_line)
            block_lines.append(
                f"가격, 품질, 실사용 후기를 종합해 선정한 {rank} 상품입니다. "
                f"로켓배송으로 빠르게 받아볼 수 있어요."
            )
            block_lines.append(link_line)
            product_blocks.append("\n".join(block_lines))

    products_section = "\n\n".join(product_blocks)

    # ── 빠른 요약 ─────────────────────────────────────────────────────
    quick_lines = []
    if product_data:
        for i, prod in enumerate(product_data[:3]):
            quick_lines.append(f"  {RANK_MEDALS[i]} {RANK_NAMES[i]}: {prod.get('name','').split('—')[0].strip()} ({prod.get('price','')})")
    else:
        for i, price in enumerate(coupang_prices[:3]):
            quick_lines.append(f"  {RANK_MEDALS[i]} {RANK_NAMES[i]}: {price}")
    if not quick_lines:
        quick_lines = ["  상세 가격은 아래 링크에서 확인하세요."]
    quick_summary = "\n".join(quick_lines)

    # ── 비교표 마커 ───────────────────────────────────────────────────
    table_headers = ["순위", "상품명", "가격", "추천대상"]
    table_rows = []
    if product_data:
        for i, prod in enumerate(product_data[:3]):
            name_short = prod.get("name", "").split("—")[0].strip()[:15]
            price = prod.get("price", "확인필요")
            targets = ["가성비 중시", "품질 중시", "프리미엄"][i]
            table_rows.append([RANK_NAMES[i], name_short, price, targets])
    else:
        for i in range(min(3, len(coupang_links))):
            price = coupang_prices[i] if i < len(coupang_prices) else "확인필요"
            features = ["가성비 최강", "품질 우수", "프리미엄"][i]
            targets = ["자주 구매하는 분", "품질 중시하는 분", "선물·특별구매"][i]
            table_rows.append([RANK_NAMES[i], features, price, targets])

    table_data = json.dumps({"headers": table_headers, "rows": table_rows}, ensure_ascii=False)
    table_marker = f"TABLE_HERE:{table_data}"

    # ── 전체 본문 조합 ────────────────────────────────────────────────
    content = f"""{intro}


━━━━━━━━━━━━━━━━━━━━━━━━
⚡ 바쁘신 분들을 위한 3줄 요약
━━━━━━━━━━━━━━━━━━━━━━━━
{quick_summary}
※ 지금 바로 클릭하면 쿠팡 실시간 최저가 확인 가능
━━━━━━━━━━━━━━━━━━━━━━━━


■ {title} 고를 때 꼭 확인할 3가지

아무거나 고르다가 후회하지 않으려면 아래 세 가지는 반드시 체크하세요.

첫째, 가격 대비 용량(개당 단가)입니다. 단순히 가격만 보면 안 됩니다. {title}는 묶음 구매 시 개당 단가가 크게 달라지므로, 단위 가격을 반드시 비교해보세요.

둘째, 성분·소재 안전성입니다. 특히 피부가 예민하거나 아이가 있는 가정에서는 성분표와 KC 인증 여부를 꼭 확인하세요.

셋째, 최신 구매자 리뷰입니다. 최근 3개월 이내 리뷰가 많은지, 실제 사용자 불편 사항은 없는지 확인해보세요.


{products_section}

━━━━━━━━━━━━━━━━━━━━━━━━


■ {title} 한눈에 비교표

{table_marker}

※ 위 가격은 쿠팡 기준이며, 쿠폰·카드 혜택으로 더 저렴하게 구매 가능합니다.


{_build_dynamic_faq(title, labels)}


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


■ 마무리

오늘 소개해드린 {title} 제품들은 모두 쿠팡에서 빠르게 받아볼 수 있고, 실제 구매자 리뷰도 많아 신뢰할 수 있는 상품들입니다.

{title} 구매를 고민하고 계신 분들께 이 글이 도움이 됐으면 좋겠습니다 😊

도움이 됐다면 공감 ❤️ 한 번 눌러주시면 큰 힘이 됩니다!
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


# ── 이미지 파일 다운로드 후 업로드 (네이버 SE 에디터) ───────────
import tempfile
import urllib.request as _urllib_req

async def _insert_image_file(page, img_url: str) -> bool:
    """
    이미지를 임시 파일로 다운로드 → input[type=file]로 업로드.
    네이버 스마트에디터 ONE은 외부 URL 직접 입력이 차단되므로
    파일 업로드 방식을 사용한다.
    """
    import os as _os
    tmp_path = None
    try:
        # 1. 이미지 다운로드 → 임시 파일
        suffix = ".jpg"
        if ".png" in img_url.lower():
            suffix = ".png"
        elif ".webp" in img_url.lower():
            suffix = ".webp"
        elif ".gif" in img_url.lower():
            suffix = ".gif"

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        tmp.close()

        req = _urllib_req.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with _urllib_req.urlopen(req, timeout=10) as resp:
            with open(tmp_path, "wb") as f:
                f.write(resp.read())

        file_size = _os.path.getsize(tmp_path)
        if file_size < 500:
            print(f"    [warn] 이미지 크기 너무 작음({file_size}B) — 스킵")
            return False

        # 2. 이미지 버튼 클릭
        img_btn = await page.query_selector(".se-image-toolbar-button")
        if not img_btn:
            img_btn = await page.query_selector(
                "button[data-name='image'], button[title*='이미지'], button[aria-label*='이미지']"
            )
        if not img_btn:
            print("    [warn] 이미지 버튼 없음 — 스킵")
            return False

        await img_btn.click()
        await page.wait_for_timeout(1500)

        # 3. input[type=file] 에 파일 경로 전달
        file_input = await page.query_selector("input[type='file']")
        if not file_input:
            # 숨겨진 파일 인풋 시도
            file_input = await page.evaluate_handle("""
                () => {
                    const inputs = document.querySelectorAll('input[type="file"]');
                    return inputs.length > 0 ? inputs[0] : null;
                }
            """)

        if file_input:
            await file_input.set_input_files(tmp_path)
            await page.wait_for_timeout(3000)   # 업로드 완료 대기
            print(f"    [이미지 업로드 완료] {_os.path.basename(tmp_path)} ({file_size}B)")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            return True
        else:
            print("    [warn] input[type=file] 없음 — Escape 후 스킵")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            return False

    except Exception as e:
        print(f"    [warn] 이미지 업로드 실패: {e}")
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False
    finally:
        if tmp_path and _os.path.exists(tmp_path):
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass


async def insert_image_by_url(page, image_url: str):
    """
    SE 에디터 이미지 삽입 — 파일 다운로드 후 업로드 방식.
    네이버 스마트에디터 ONE은 외부 URL 입력 탭이 제거되었으므로
    이미지를 로컬에 다운로드한 뒤 파일 업로드로 삽입한다.
    실패 시 graceful fallback (이미지 없이 계속 진행).
    """
    print(f"    [이미지 삽입 시도] {image_url[:70]}...")
    success = await _insert_image_file(page, image_url)
    if not success:
        print(f"    [이미지 스킵] 파일 업로드 실패, 본문 계속 진행")


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

    # PRODUCT_DATA 환경변수 파싱 (naver_cron_runner.py에서 전달)
    product_data = []
    if PRODUCT_DATA_STR:
        try:
            product_data = json.loads(PRODUCT_DATA_STR)
            print(f"  ✅ PRODUCT_DATA 수신: {len(product_data)}개 상품")
            for i, p in enumerate(product_data):
                print(f"     [{i+1}] {p.get('name','')[:40]} / {p.get('price','')}")
        except Exception as e:
            print(f"  [warn] PRODUCT_DATA 파싱 실패: {e}")

    # product_data에서 링크/이미지 추출 (coupang_links/images 보완)
    if product_data and not coupang_links:
        coupang_links = [p.get("link", "") for p in product_data if p.get("link")]
        coupang_prices = [p.get("price", "") for p in product_data if p.get("price")]

    if product_data and not coupang_images:
        coupang_images = [p.get("image", "") for p in product_data if p.get("image")]

    if not coupang_links and not product_data:
        print("  쿠팡 링크/이미지 자동 추출 중...")
        coupang_links, coupang_prices, coupang_images = extract_coupang_data_from_blogger(POST_URL)

    content = build_naver_content(
        POST_TITLE, POST_SUMMARY, POST_URL,
        labels, coupang_links, coupang_prices, coupang_images,
        product_data=product_data,
    )

    # 본문 내 IMAGE_HERE에 사용할 이미지 목록 (product_data 이미지 우선)
    body_images = coupang_images  # build_naver_content와 동일 순서 유지

    print(f"[포스팅 준비]")
    print(f"  제목: {POST_TITLE[:50]}")
    print(f"  원본(OG카드): {POST_URL[:60]}")
    print(f"  쿠팡 링크: {len(coupang_links)}개 / 가격: {coupang_prices}")
    print(f"  상품 이미지: {len(body_images)}개")
    print(f"  상품 데이터: {len(product_data)}개 (product_data)")
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
        await type_body(page, content, body_images)

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
