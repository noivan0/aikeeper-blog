"""
prosweep 네이버 예약발행 글 summary 수정 스크립트
- naver_posts.jsonl에서 예약발행 글 추출
- 원본 꿀통몬스터 URL에서 올바른 summary 재추출 (script/style 제거)
- Playwright로 네이버 예약발행 관리 페이지 접근해 본문 수정

실행: python3 fix_naver_reserved.py
"""
import os, sys, asyncio, json, re, time
import urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

NAVER_ID       = os.environ.get("NAVER_ID", "")
NAVER_PW       = os.environ.get("NAVER_PW", "")
BLOG_ID        = os.environ.get("NAVER_BLOG_ID", "prosweep")
SESSION_FILE   = os.environ.get("NAVER_SESSION_FILE",
                   str(Path(__file__).parent.parent / "naver_session.json"))
BASE_DIR       = Path(__file__).parent.parent
CHROME_PATH    = "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
LAUNCH_ARGS    = [
    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--ignore-certificate-errors", "--ignore-ssl-errors",
    "--disable-blink-features=AutomationControlled",
]


def extract_summary(content: str) -> str:
    """HTML content에서 <script>/<style> 제거 후 순수 텍스트 200자 추출"""
    clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    plain = re.sub(r'<[^>]+>', ' ', clean)
    plain = re.sub(r'&nbsp;', ' ', plain)
    plain = re.sub(r'&[a-z]+;', '', plain)
    plain = re.sub(r'\s+', ' ', plain).strip()
    return plain[:200].strip()


def fetch_summary_from_url(url: str) -> str:
    """URL 직접 fetch해서 summary 추출 (atom.xml에 없는 글용)"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', 'ignore')
        # <article> 또는 .post-body 찾기
        body_match = re.search(r'<div[^>]+class=["\'][^"\']*post-body[^"\']*["\'][^>]*>(.*?)</div>', html, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        content = body_match.group(1) if body_match else html
        return extract_summary(content)
    except Exception as ex:
        print(f"    [warn] URL fetch 실패 ({url}): {ex}")
        return ""


def build_reserved_list() -> list:
    """naver_posts.jsonl에서 예약발행 글 추출 + atom.xml에서 올바른 summary 매핑"""
    # 1. atom.xml 로드
    try:
        req = urllib.request.Request(
            'https://ggultongmon.allsweep.xyz/atom.xml',
            headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        atom_map = {}
        for e in root.findall('atom:entry', ns):
            url = ''
            for link in e.findall('atom:link', ns):
                if link.get('rel') == 'alternate':
                    url = link.get('href', '')
                    break
            if not url: continue
            content = e.findtext('atom:content', namespaces=ns) or ''
            atom_map[url] = extract_summary(content)
        print(f"  atom.xml 로드: {len(atom_map)}개 항목")
    except Exception as ex:
        print(f"  [warn] atom.xml 로드 실패: {ex}")
        atom_map = {}

    # 2. 예약발행 글 추출
    posts_path = BASE_DIR / "results" / "naver_posts.jsonl"
    reserved = []
    seen = set()
    with open(posts_path) as f:
        for line in f:
            if not line.strip(): continue
            p = json.loads(line)
            if not p.get('naver_url', '').startswith('[예약]'):
                continue
            orig_url = p.get('original_url', '')
            key = (orig_url, p.get('reserve_dt', p.get('naver_url','')))
            if key in seen:
                continue
            seen.add(key)

            summary = atom_map.get(orig_url, '')
            reserved.append({
                'title': p['title'],
                'reserve_dt': p.get('reserve_dt', ''),
                'original_url': orig_url,
                'correct_summary': summary,
                'labels': p.get('labels', []),
            })

    # 3. atom에 없는 글은 직접 fetch
    missing = [r for r in reserved if not r['correct_summary']]
    if missing:
        print(f"  atom.xml 미포함 {len(missing)}개 → 직접 fetch")
        for r in missing:
            r['correct_summary'] = fetch_summary_from_url(r['original_url'])
            time.sleep(0.5)

    matched = sum(1 for r in reserved if r['correct_summary'])
    print(f"  예약발행 {len(reserved)}개 / summary 확보: {matched}개")
    return reserved


async def fix_post(page, reserve_dt: str, title: str, new_summary: str, idx: int, total: int) -> bool:
    """
    네이버 예약발행 관리 페이지에서 해당 글 찾아 본문의 summary 부분 수정
    전략: 예약발행 목록 → 글 제목 클릭 → 편집 → summary 텍스트 교체 → 재발행
    """
    print(f"\n[{idx}/{total}] {title[:40]} ({reserve_dt})")

    # 예약발행 관리 목록 페이지
    mgmt_url = f"https://blog.naver.com/{BLOG_ID}/manage/posts?filterType=scheduled"
    await page.goto(mgmt_url, timeout=30000)
    await page.wait_for_timeout(3000)

    # 제목으로 글 찾기
    try:
        # 목록에서 제목 텍스트 검색
        post_link = await page.query_selector(f"a[title*='{title[:20]}'], a:has-text('{title[:20]}')")
        if not post_link:
            # iframe 내부 확인
            frames = page.frames
            for frame in frames:
                post_link = await frame.query_selector(f"a:has-text('{title[:15]}')")
                if post_link:
                    break

        if not post_link:
            print(f"  ❌ 글 찾기 실패: {title[:30]}")
            await page.screenshot(path=f"/tmp/fix_notfound_{idx}.png")
            return False

        await post_link.click()
        await page.wait_for_timeout(4000)
    except Exception as ex:
        print(f"  ❌ 클릭 실패: {ex}")
        return False

    # 편집 모드 진입 확인
    if "postwrite" not in page.url and "edit" not in page.url.lower():
        # 수정 버튼 찾기
        edit_btn = await page.query_selector("button:has-text('수정'), a:has-text('수정편집')")
        if edit_btn:
            await edit_btn.click()
            await page.wait_for_timeout(4000)

    if "postwrite" not in page.url:
        print(f"  ❌ 편집 모드 진입 실패: {page.url}")
        return False

    print(f"  편집 모드 진입 ✅")

    # 본문에서 JSON-LD로 시작하는 텍스트 단락 찾아 교체
    # summary 단락은 본문 초반부에 있음 — 에디터 텍스트 검색
    replaced = await page.evaluate(f"""
        () => {{
            const paras = Array.from(document.querySelectorAll('.se-text-paragraph'));
            const target = paras.find(p => {{
                const t = (p.innerText || '').trim();
                return t.startsWith('{{') || t.startsWith('@context') || t.includes('schema.org');
            }});
            if (!target) return false;
            // 내용 교체 시도 (contenteditable)
            target.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, {json.dumps(new_summary)});
            return true;
        }}
    """)

    if not replaced:
        print(f"  ⚠️ JSON-LD 단락 못 찾음 — summary 이미 정상이거나 구조 다름")
        return True  # 이미 수정됐을 수 있으므로 True 처리

    await page.wait_for_timeout(1000)

    # 재발행 (예약 유지)
    publish_btn = await page.query_selector(".publish_btn__m9KHH, button[class*='publish_btn']")
    if publish_btn:
        await page.evaluate("btn => btn.click()", publish_btn)
        await page.wait_for_timeout(2500)
        confirm_btn = await page.query_selector(".confirm_btn__WEaBq, button[class*='confirm_btn']")
        if confirm_btn:
            await page.evaluate("btn => btn.click()", confirm_btn)
            await page.wait_for_timeout(4000)
            print(f"  ✅ 수정 완료")
            return True

    print(f"  ❌ 발행 버튼 없음")
    return False


async def main():
    os.environ['DISPLAY'] = ':99'

    print("=== prosweep 예약발행 글 summary 수정 ===\n")
    reserved = build_reserved_list()

    # summary가 확보된 것만 처리
    to_fix = [r for r in reserved if r['correct_summary']]
    print(f"\n수정 대상: {len(to_fix)}개\n")

    if not to_fix:
        print("수정할 글이 없습니다.")
        return

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path=CHROME_PATH, args=LAUNCH_ARGS
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        if Path(SESSION_FILE).exists():
            ctx_kwargs["storage_state"] = SESSION_FILE

        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        page = await context.new_page()

        # 세션 확인
        await page.goto("https://blog.naver.com", timeout=20000)
        await page.wait_for_timeout(2000)
        login_ok = await page.evaluate("() => document.cookie.includes('NID_SES')")
        if not login_ok:
            print("❌ 로그인 필요 — NAVER_SESSION_FILE 확인")
            await browser.close()
            return
        print("세션 유효 ✅\n")

        success, fail = 0, 0
        for i, r in enumerate(to_fix, 1):
            ok = await fix_post(
                page,
                r['reserve_dt'], r['title'], r['correct_summary'],
                i, len(to_fix)
            )
            if ok:
                success += 1
            else:
                fail += 1
            await page.wait_for_timeout(2000)

        await context.storage_state(path=SESSION_FILE)
        await browser.close()

    print(f"\n=== 완료: 성공 {success}개 / 실패 {fail}개 ===")


if __name__ == "__main__":
    asyncio.run(main())
