#!/usr/bin/env python3
"""
ggultongmon 기존 포스팅 → prosweep 네이버 블로그 일괄 예약발행 v3
- sitemap 기반 전체 포스팅 수집 (505개+)
- 발행 간격: 3시간 (C-RANK 최적화, 스팸 방지)
- 중복 방지: naver_posts.jsonl 대조
- 우선순위: 2026년 비교형 포스팅 우선, 2025년 단품 제외
- v3: 이미지 삽입 (IMAGE_HERE 마커), 비교표 (TABLE_HERE 마커) 지원
"""
import os, sys, asyncio, json, datetime, re, ssl, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# post_to_naver_prosweep.py의 공통 함수 import
sys.path.insert(0, str(Path(__file__).parent))
from post_to_naver_prosweep import (
    build_naver_content,
    insert_image_by_url,
    insert_table_block,
)

os.environ['DISPLAY'] = ':99'

BASE_DIR     = Path(__file__).parent.parent
SESSION_FILE = str(BASE_DIR / "naver_session.json")
RESULTS_FILE = BASE_DIR / "results" / "naver_posts.jsonl"
CATEGORY_NO  = "6"
BLOG_ID      = "prosweep"
CHROME_PATH  = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
LAUNCH_ARGS  = ["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
                "--ignore-certificate-errors","--disable-blink-features=AutomationControlled"]

# ─── 전체 포스팅 수집 (sitemap + atom) ──────────────────────────
def collect_all_posts(max_posts: int = 200) -> list:
    """sitemap에서 URL 수집 → atom에서 메타 보강 → 우선순위 정렬"""
    ctx     = ssl._create_unverified_context()
    headers = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}

    # 1) sitemap에서 전체 URL
    req = urllib.request.Request("https://ggultongmon.allsweep.xyz/sitemap.xml", headers=headers)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        data = r.read().decode('utf-8','ignore')
    all_urls = re.findall(r'<loc>([^<]+)</loc>', data)
    # 포스팅 URL만 (날짜 포함)
    post_urls = [u for u in all_urls if re.search(r'/\d{4}/\d{2}/', u)]
    print(f"  sitemap 포스팅 URL: {len(post_urls)}개")

    # 2) atom.xml에서 메타데이터 (최근 25개 상세)
    req2 = urllib.request.Request("https://ggultongmon.allsweep.xyz/atom.xml", headers=headers)
    with urllib.request.urlopen(req2, timeout=15, context=ctx) as r:
        atom_data = r.read().decode('utf-8','ignore')
    root = ET.fromstring(atom_data)
    ns   = {'atom': 'http://www.w3.org/2005/Atom'}
    meta_map = {}  # url → {title, summary, coupang_links, prices, labels}
    for e in root.findall('atom:entry', ns):
        link_el = e.find("atom:link[@rel='alternate']", ns)
        url     = link_el.get('href','') if link_el else ''
        if not url: continue
        content = e.findtext('atom:content', namespaces=ns) or ''
        links   = list(dict.fromkeys(re.findall(
            r'href=["\']+(https://link\.coupang\.com/[^"\'>\s]+)', content)))[:3]
        prices  = [p+"원" for p in list(dict.fromkeys(
            re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+)원', content)))[:3]]
        # <script>...</script> 블록 전체 제거 (JSON-LD 등이 summary에 노출되는 문제 방지)
        clean   = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        text    = re.sub(r'<[^>]+>',' ', clean)
        text    = re.sub(r'\s+',' ', text).strip()
        cats    = [c.get('term','') for c in e.findall('atom:category', ns)]
        # 이미지 URL 추출 (쿠팡 이미지 우선)
        img_urls     = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
        coupang_imgs = [u for u in img_urls if 'coupang' in u or 'thumbnail' in u]
        other_imgs   = [u for u in img_urls if u not in coupang_imgs]
        images       = (coupang_imgs + other_imgs)[:3]
        meta_map[url] = {
            "title": e.findtext('atom:title', namespaces=ns) or '',
            "summary": text[:200],
            "coupang_links": links,
            "coupang_prices": prices,
            "coupang_images": images,
            "labels": cats[:5],
        }

    # 3) URL 우선순위 정렬: 2026 > 2025, 비교형(복수상품) 우선
    def priority(url):
        year = int(re.search(r'/(\d{4})/', url).group(1)) if re.search(r'/(\d{4})/', url) else 0
        return year  # 최신 연도 우선

    sorted_urls = sorted(post_urls, key=priority, reverse=True)

    # 4) 메타 없는 URL은 기본값으로 채움
    posts = []
    for url in sorted_urls[:max_posts]:
        if url in meta_map:
            m = meta_map[url]
            # 쿠팡링크 없는 단순 단품은 제외 (2025년 구형 로켓프레시류)
            if '/2025/' in url and len(m['coupang_links']) == 0:
                continue
            posts.append({"url": url, **m})
        else:
            # atom에 없는 글 — URL만으로 기본 정보 구성
            # 2025년 이전 단품글은 제외
            if '/2025/08/' in url or '/2025/04/' in url:
                continue
            title = url.split('/')[-1].replace('.html','').replace('-',' ').replace('_',' ')
            posts.append({
                "url": url, "title": title,
                "summary": "", "coupang_links": [], "coupang_prices": [], "coupang_images": [], "labels": []
            })

    print(f"  발행 대상 후보: {len(posts)}개 (최대 {max_posts}개)")
    return posts


# ─── 예약 시간 계산 (KST, 3시간 간격) ──────────────────────────
def calc_schedule(n: int, start_hour: int = 9, interval_h: int = 3) -> list:
    KST   = datetime.timezone(datetime.timedelta(hours=9))
    now   = datetime.datetime.now(KST)
    start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    if start <= now + datetime.timedelta(minutes=30):
        start += datetime.timedelta(days=1)
    return [(start + datetime.timedelta(hours=interval_h * i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)]


# ─── 이미 발행된 원본 URL ────────────────────────────────────────
def get_published() -> set:
    s = set()
    if RESULTS_FILE.exists():
        for line in RESULTS_FILE.read_text().splitlines():
            try:
                d = json.loads(line)
                u = d.get("original_url","")
                if u: s.add(u)
            except: pass
    return s


# ─── 로그 저장 ──────────────────────────────────────────────────
def log_result(post, naver_url, reserve_dt):
    entry = {"success": True, "naver_url": naver_url, "title": post["title"],
             "original_url": post["url"], "reserve_dt": reserve_dt,
             "posted_at": datetime.datetime.now().isoformat(),
             "coupang_links": post.get("coupang_links", [])}
    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── 본문 빌더 (v11 공통 함수 위임) ────────────────────────────
def build_content(title, summary, original_url, labels, coupang_links, coupang_prices,
                  coupang_images=None) -> str:
    """post_to_naver_prosweep.build_naver_content에 위임 (v11 포맷)"""
    return build_naver_content(
        title, summary, original_url, labels, coupang_links, coupang_prices,
        coupang_images or []
    )


# ─── SE 에디터 함수들 ────────────────────────────────────────────
async def handle_popups(page):
    await page.evaluate("""() => {
        const p = document.querySelector('.__se-pop-layer');
        if (p) for (const b of p.querySelectorAll('button'))
            if (b.innerText.trim()==='취소'){b.click();break;}
        document.querySelectorAll('.layer_popup__i0QOY').forEach(e=>e.style.display='none');
    }""")
    await page.wait_for_timeout(800)
    hb = await page.query_selector(".se-help-panel-close-button")
    if hb: await hb.click(); await page.wait_for_timeout(400)

async def type_title(page, title):
    tc = await page.query_selector(".se-component.se-documentTitle")
    if tc:
        box = await tc.bounding_box()
        await page.mouse.click(box['x']+200, box['y']+box['height']/2)
    else:
        await page.mouse.click(590, 232)
    await page.wait_for_timeout(400)
    await page.keyboard.type(title, delay=40)

async def insert_text_link(page, text, url):
    await page.keyboard.type(text, delay=25)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Home"); await page.wait_for_timeout(80)
    await page.keyboard.press("Shift+End"); await page.wait_for_timeout(150)
    await page.evaluate("""() => {
        const btn = document.querySelector('.se-link-toolbar-button');
        if (!btn) return;
        btn.addEventListener('mousedown', e=>e.preventDefault(), {once:true});
        btn.click();
    }""")
    await page.wait_for_timeout(1500)
    ui = await page.query_selector(".se-custom-layer-link-input")
    if ui:
        await ui.click()
        await page.keyboard.type(url, delay=10)
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter"); await page.wait_for_timeout(400)
    else:
        await page.keyboard.press("Escape")
    await page.keyboard.press("End")
    await page.keyboard.press("Enter"); await page.wait_for_timeout(80)

async def insert_og_card(page, url):
    await page.keyboard.type(url, delay=12)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(7000)
    for _ in range(5):
        info = await page.evaluate("""() => {
            for (const p of document.querySelectorAll('.se-text-paragraph')) {
                const t = p.innerText || '';
                if (t.trim().match(/^https?:\/\//) && t.trim().length > 5) {
                    const r = p.getBoundingClientRect();
                    if (r.width < 10) continue;
                    return {x:Math.round(r.x+60), y:Math.round(r.y+r.height/2), h:Math.round(r.height)};
                }
            }
            return null;
        }""")
        if not info: break
        await page.mouse.click(info['x'], info['y']); await page.wait_for_timeout(150)
        await page.keyboard.press("Home"); await page.wait_for_timeout(60)
        await page.keyboard.press("Shift+End"); await page.wait_for_timeout(60)
        await page.keyboard.press("Backspace"); await page.wait_for_timeout(300)
    le = await page.evaluate("""() => {
        const ps = Array.from(document.querySelectorAll('.se-text-paragraph'));
        for (let i=ps.length-1;i>=0;i--){
            const r=ps[i].getBoundingClientRect();
            if((ps[i].innerText||'').trim()===''&&r.width>0&&r.y>200)
                return {x:Math.round(r.x+60),y:Math.round(r.y+5)};
        }
        return null;
    }""")
    if le:
        await page.mouse.click(le['x'],le['y']); await page.wait_for_timeout(200)
        await page.keyboard.press("End")

async def type_body(page, content, image_urls=None):
    """
    content 마커:
    - IMAGE_HERE:N  → N번 이미지 삽입
    - TABLE_HERE:{json}  → 표 삽입
    - CARD_URL:URL  → OG 카드
    - LINK_TEXT:텍스트|URL  → 하이퍼링크
    """
    if image_urls is None:
        image_urls = []
    bc = await page.query_selector(".se-component.se-text")
    if bc:
        box = await bc.bounding_box()
        await page.mouse.click(box['x']+200, box['y']+box['height']/2)
    else:
        await page.mouse.click(590, 380)
    await page.wait_for_timeout(500)
    for i, line in enumerate(content.split('\n')):
        s = line.strip()

        # IMAGE_HERE:N 마커
        if s.startswith("IMAGE_HERE:"):
            try:
                idx = int(s[len("IMAGE_HERE:"):].strip())
            except ValueError:
                idx = 0
            if idx < len(image_urls) and image_urls[idx]:
                await insert_image_by_url(page, image_urls[idx])
            continue

        # TABLE_HERE:{json} 마커
        if s.startswith("TABLE_HERE:"):
            table_json = s[len("TABLE_HERE:"):].strip()
            try:
                table_data = json.loads(table_json)
                await insert_table_block(page, table_data.get("headers",[]), table_data.get("rows",[]))
            except Exception as e:
                print(f"    [warn] 표 파싱 실패: {e}")
            continue

        if s.startswith("CARD_URL:"):
            await insert_og_card(page, s[len("CARD_URL:"):])
        elif "LINK_TEXT:" in s:
            before  = s[:s.index("LINK_TEXT:")]
            payload = s[s.index("LINK_TEXT:")+len("LINK_TEXT:"):]
            if before: await page.keyboard.type(before, delay=18)
            if "|" in payload:
                lt, lu = payload.split("|", 1)
                await insert_text_link(page, lt.strip(), lu.strip())
            else:
                await page.keyboard.type(payload, delay=18)
                await page.keyboard.press("Enter")
        elif line:
            await page.keyboard.type(line, delay=18)
            await page.keyboard.press("Enter"); await asyncio.sleep(0.07)
        else:
            await page.keyboard.press("Enter"); await asyncio.sleep(0.07)

async def publish_reserved(page, reserve_dt) -> str | None:
    await page.evaluate("""() => {
        document.querySelectorAll('.layer_popup__i0QOY').forEach(e=>e.style.display='none');
        const hp=document.querySelector('.container__HW_tc,.se-help-panel');
        if(hp)hp.style.display='none';
    }""")
    await page.wait_for_timeout(600)

    pub = await page.query_selector(".publish_btn__m9KHH") or \
          await page.query_selector("button[class*='publish_btn']")
    if not pub: print("  ❌ 발행 버튼 없음"); return None
    await page.evaluate("btn=>btn.click()", pub)
    await page.wait_for_timeout(2500)

    # 예약 라디오 클릭
    await page.evaluate("()=>{const r=document.querySelector('#radio_time2');if(r)r.click();}")
    await page.wait_for_timeout(1500)

    rdt = datetime.datetime.strptime(reserve_dt, "%Y-%m-%d %H:%M")

    # 날짜 input 클릭 후 선택 → 타이핑
    date_str = rdt.strftime("%Y. %m. %d")
    date_el  = await page.query_selector(".input_date__QmA0s")
    if date_el:
        box = await date_el.bounding_box()
        # 트리플클릭 → 마우스 3번 클릭으로 전체 선택
        await page.mouse.click(box['x']+box['width']/2, box['y']+box['height']/2, click_count=3)
        await page.wait_for_timeout(200)
        await page.keyboard.type(date_str, delay=50)
        await page.keyboard.press("Tab"); await page.wait_for_timeout(300)
        print(f"  날짜: {date_str}")

    # 시/분 SELECT
    set_log = await page.evaluate(f"""() => {{
        const log = [];
        function sv(sel, val) {{
            const el = document.querySelector(sel);
            if (!el) return;
            const ns = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set;
            ns.call(el, String(val));
            el.dispatchEvent(new Event('change',{{bubbles:true}}));
            log.push(sel.replace('.','')+'='+val);
        }}
        sv('.hour_option__J_heO', {rdt.hour});
        sv('.minute_option__Vb3xB', {rdt.minute});
        return log;
    }}""")
    print(f"  시/분: {set_log}")
    await page.wait_for_timeout(800)

    # 확인(발행) 버튼
    confirm = await page.query_selector(".confirm_btn__WEaBq") or \
              await page.query_selector("button[class*='confirm_btn']")
    if not confirm: print("  ❌ 확인 버튼 없음"); return None
    await page.evaluate("btn=>btn.click()", confirm)
    await page.wait_for_timeout(5000)

    url = page.url
    if "PostView" in url or "logNo" in url:
        return url
    return f"[예약] {reserve_dt} KST"


# ─── 메인 ────────────────────────────────────────────────────────
async def main():
    # 옵션: --max N (최대 발행 수)
    max_per_run = 50  # 기본 최대 50개씩
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i+1 < len(sys.argv):
            max_per_run = int(sys.argv[i+1])

    print("[ggultongmon → prosweep 일괄 예약발행]")
    print(f"최대 {max_per_run}개, 3시간 간격")
    print()

    print("포스팅 수집 중...")
    all_posts  = collect_all_posts(max_posts=500)
    published  = get_published()
    queue      = [p for p in all_posts if p["url"] not in published][:max_per_run]

    if not queue:
        print("✅ 발행할 신규 포스팅 없음"); return

    schedules = calc_schedule(len(queue), start_hour=9, interval_h=3)

    print(f"\n[예약발행 계획] 총 {len(queue)}개 / 간격 3시간")
    print(f"  시작: {schedules[0]} KST")
    print(f"  종료: {schedules[-1]} KST")
    print()
    for i,(p,s) in enumerate(zip(queue,schedules)):
        print(f"  [{i+1:2d}] {s} — {p['title'][:43]}")
    print()

    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, executable_path=CHROME_PATH, args=LAUNCH_ARGS)
        ctx_kw  = {"user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                   "ignore_https_errors":True, "viewport":{"width":1280,"height":900}}
        if Path(SESSION_FILE).exists(): ctx_kw["storage_state"] = SESSION_FILE
        context = await browser.new_context(**ctx_kw)
        await context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await context.new_page()

        # 세션 확인
        await page.goto("https://blog.naver.com", timeout=25000)
        await page.wait_for_timeout(2000)
        ok = await page.evaluate("()=>document.cookie.includes('NID_SES')")
        if not ok: print("❌ 세션 만료"); await browser.close(); sys.exit(1)
        print("세션 유효 ✅\n")

        ok_cnt = fail_cnt = 0
        for i,(post,sched) in enumerate(zip(queue,schedules)):
            print(f"[{i+1}/{len(queue)}] {sched} — {post['title'][:45]}")
            post_images = post.get("coupang_images", [])
            content = build_content(
                post["title"], post.get("summary",""),
                post["url"], post.get("labels",[]),
                post.get("coupang_links",[]), post.get("coupang_prices",[]),
                post_images,
            )
            try:
                await page.goto(
                    f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}",
                    timeout=30000, wait_until="networkidle")
                await page.wait_for_timeout(4000)
                await handle_popups(page)
                await type_title(page, post["title"])
                await page.keyboard.press("Tab"); await page.wait_for_timeout(300)
                await type_body(page, content, post_images)
                result = await publish_reserved(page, sched)
                if result:
                    print(f"  ✅ {result}")
                    log_result(post, result, sched)
                    ok_cnt += 1
                else:
                    print(f"  ❌ 실패"); fail_cnt += 1
            except Exception as ex:
                import traceback
                print(f"  ❌ 오류: {ex}"); traceback.print_exc(); fail_cnt += 1

            if i < len(queue)-1:
                print(f"  ⏳ 30초 대기...")
                await asyncio.sleep(30)

        await browser.close()

    print(f"\n[완료] 성공:{ok_cnt} / 실패:{fail_cnt}")
    if ok_cnt:
        print(f"예약 범위: {schedules[0]} ~ {schedules[ok_cnt-1]} KST")
        KST = datetime.timezone(datetime.timedelta(hours=9))
        end = datetime.datetime.strptime(schedules[ok_cnt-1], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        delta = end - datetime.datetime.now(KST)
        days  = delta.days
        print(f"모든 글 발행 완료까지: 약 {days}일 후 ({end.strftime('%m/%d %H:%M')} KST)")

if __name__ == "__main__":
    asyncio.run(main())
