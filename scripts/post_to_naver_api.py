#!/usr/bin/env python3
"""
네이버 블로그 API 발행 v4 — JS fetch 방식
────────────────────────────────────────────
Playwright 브라우저 안에서 JS fetch()로 직접 API 호출:
  1. 에디터 로드 (세션 체크 + 팝업 처리)
  2. 더미 입력 → 자동저장 트리거 → tokenId 캡처
  3. JS fetch: RabbitAutoSaveWrite.naver (자동저장 → autoSaveNo)
  4. JS fetch: RabbitWrite.naver (발행)

브라우저 쿠키/CSRF 세션을 그대로 사용하므로 세션 불일치 없음
긴 본문 입력 없이 API 직접 호출 → 자동저장 실패 없음

환경변수:
  NAVER_ID, NAVER_PW
  NAVER_BLOG_ID (default: prosweep)
  NAVER_CATEGORY_NO (default: 6)
  NAVER_TITLE
  NAVER_BODY_PATH 또는 NAVER_BODY
"""
import os, sys, json, time, uuid, asyncio, random, string, urllib.parse
from pathlib import Path

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":99"

sys.path.insert(0, str(Path(__file__).parent))
from env_loader import load_env
load_env()

from playwright.async_api import async_playwright

NAVER_ID     = os.environ.get("NAVER_ID", "")
NAVER_PW     = os.environ.get("NAVER_PW", "")
BLOG_ID      = os.environ.get("NAVER_BLOG_ID", "prosweep")
CATEGORY_NO  = int(os.environ.get("NAVER_CATEGORY_NO", "6"))
POST_TITLE   = os.environ.get("NAVER_TITLE", "")
BODY_PATH    = os.environ.get("NAVER_BODY_PATH", "")
SESSION_FILE = str(Path(__file__).parent.parent / "naver_session.json")
LOG_PATH     = str(Path(__file__).parent.parent / "results" / "naver_simple_posts.jsonl")

WRITE_URL       = f"https://blog.naver.com/{BLOG_ID}/postwrite?categoryNo={CATEGORY_NO}"
AUTOSAVE_URL    = "https://blog.naver.com/RabbitAutoSaveWrite.naver"
RABBIT_WRITE_URL = "https://blog.naver.com/RabbitWrite.naver"


def _uid():
    return "SE-" + str(uuid.uuid4())


def _docid():
    chars = string.digits + string.ascii_uppercase
    return "".join(random.choices(chars, k=26))


def build_document_model(title: str, body: str) -> str:
    """SE 에디터 documentModel JSON 문자열 반환"""
    doc = {
        "documentId": "",
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": _docid(),
            "components": [
                {
                    "id": _uid(),
                    "layout": "default",
                    "title": [{
                        "id": _uid(),
                        "nodes": [{"id": _uid(), "value": title, "@ctype": "textNode"}],
                        "@ctype": "paragraph"
                    }],
                    "subTitle": None,
                    "align": "left",
                    "@ctype": "documentTitle"
                },
                {
                    "id": _uid(),
                    "layout": "default",
                    "value": [{
                        "id": _uid(),
                        "nodes": [{
                            "id": _uid(),
                            "value": body,
                            "style": {"fontSizeCode": "fs16", "@ctype": "nodeStyle"},
                            "@ctype": "textNode"
                        }],
                        "@ctype": "paragraph"
                    }],
                    "@ctype": "text"
                }
            ],
            "di": {
                "dif": False,
                "dio": [
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": len(title), "sk": 1}},
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": len(body), "sk": 1}}
                ]
            }
        }
    }
    return json.dumps(doc, ensure_ascii=False, separators=(',', ':'))


def make_pop(auto_save_no=None, for_publish=False) -> str:
    """populationParams JSON 문자열"""
    return json.dumps({
        "configuration": {
            "openType": 2, "commentYn": True, "searchYn": True,
            "sympathyYn": False, "scrapType": 2, "outSideAllowYn": True,
            "twitterPostingYn": False, "facebookPostingYn": False, "cclYn": False
        },
        "populationMeta": {
            "categoryId": CATEGORY_NO, "logNo": None, "directorySeq": 21,
            "directoryDetail": None, "mrBlogTalkCode": None,
            "postWriteTimeType": "now", "tags": "",
            "moviePanelParticipation": False, "greenReviewBannerYn": False,
            "continueSaved": False, "noticePostYn": False, "autoByCategoryYn": False,
            "postLocationSupportYn": False, "postLocationJson": None,
            "prePostDate": None, "thisDayPostInfo": None, "scrapYn": False,
            "autoSaveNo": auto_save_no
        },
        "editorSource": "be1Cpvv4FXCRGUPtcaiPhQ=="
    }, ensure_ascii=False, separators=(',', ':'))


async def publish(title: str, body: str) -> str | None:
    """Playwright JS fetch 방식으로 자동저장 + 발행"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"]
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

        # 에디터 로드
        await page.goto(WRITE_URL, timeout=40000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        # 로그인 필요 시
        if "nidlogin" in page.url or "login" in page.url.lower():
            print("  세션 만료 — 재로그인")
            await page.goto("https://nid.naver.com/nidlogin.login?mode=form", timeout=20000)
            await page.wait_for_timeout(2000)
            await page.locator("#id").click()
            for c in NAVER_ID:
                await page.keyboard.type(c)
                await asyncio.sleep(0.12)
            await page.locator("#pw").click()
            for c in NAVER_PW:
                await page.keyboard.type(c)
                await asyncio.sleep(0.10)
            await page.wait_for_timeout(1000)
            btn = await page.query_selector(".btn_login")
            if btn:
                await btn.click()
            await page.wait_for_timeout(6000)
            if "nidlogin" in page.url:
                print("  ❌ 로그인 실패")
                await browser.close()
                return None
            await context.storage_state(path=SESSION_FILE)
            await page.goto(WRITE_URL, timeout=40000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)

        # 팝업 취소
        for _ in range(12):
            pos = await page.evaluate("""() => {
                for (const btn of document.querySelectorAll('button')) {
                    if ((btn.innerText||'').trim() === '취소') {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 0) return {x: r.x+r.width/2, y: r.y+r.height/2};
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

        # 에디터 준비
        try:
            await page.wait_for_selector(".se-component.se-text, .se-documentTitle", timeout=25000)
        except Exception:
            print("  ❌ 에디터 로드 실패")
            await browser.close()
            return None
        await page.wait_for_timeout(1000)

        # tokenId 캡처: 더미 입력 → 자동저장 대기 → 발행 버튼
        captured_token = {"id": ""}
        async def on_request(req):
            if "RabbitWrite.naver" in req.url and req.method == "POST":
                params = urllib.parse.parse_qs(req.post_data or "", keep_blank_values=True)
                tok = params.get("tokenId", [""])[0]
                if tok:
                    captured_token["id"] = tok
        context.on("request", on_request)

        tc = await page.query_selector(".se-title-text")
        if tc:
            box = await tc.bounding_box()
            await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
        await page.keyboard.type("_", delay=10)

        body_el = await page.query_selector(".se-component.se-text")
        if body_el:
            box = await body_el.bounding_box()
            await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
        await page.keyboard.type("_", delay=10)

        # 자동저장 + tokenId 캡처 대기
        print("  자동저장 대기 (8s)...")
        await page.wait_for_timeout(8000)

        pub_btn = await page.query_selector(".publish_btn__m9KHH")
        if pub_btn:
            await pub_btn.click()
            await page.wait_for_timeout(3000)
            confirm = await page.query_selector(".confirm_btn__WEaBq")
            if confirm:
                await confirm.click()
                await page.wait_for_timeout(5000)

        token_id = captured_token["id"]
        print(f"  tokenId: {token_id[:20] if token_id else '없음'}...")

        if not token_id:
            print("  ❌ tokenId 없음")
            await browser.close()
            return None

        # ── JS fetch: 자동저장 ──────────────────────────────────────────
        doc_str = build_document_model(title, body)
        pop_save = make_pop(auto_save_no=None)

        # JSON.stringify로 안전하게 JS에 전달
        autosave_result = await page.evaluate("""
            async ([autosave_url, blog_id, doc_str, media, pop_str, write_url]) => {
                const params = new URLSearchParams();
                params.append('blogId', blog_id);
                params.append('documentModel', doc_str);
                params.append('mediaResources', media);
                params.append('populationParams', pop_str);
                const resp = await fetch(autosave_url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded', 'Referer': write_url},
                    body: params.toString(),
                    credentials: 'include'
                });
                return await resp.json();
            }
        """, [AUTOSAVE_URL, BLOG_ID, doc_str, '{"image":[],"video":[],"file":[]}', pop_save, WRITE_URL])

        print(f"  자동저장: {autosave_result}")

        if not autosave_result or not autosave_result.get("isSuccess"):
            print("  ❌ 자동저장 실패")
            await browser.close()
            return None

        auto_save_no = autosave_result["result"]["autoSaveNo"]
        print(f"  ✅ autoSaveNo={auto_save_no}")

        # ── JS fetch: 발행 ──────────────────────────────────────────────
        pop_pub = make_pop(auto_save_no=auto_save_no, for_publish=True)

        publish_result = await page.evaluate("""
            async ([rabbit_url, blog_id, doc_str, media, pop_str, token_id, api_ver, write_url]) => {
                const params = new URLSearchParams();
                params.append('blogId', blog_id);
                params.append('documentModel', doc_str);
                params.append('mediaResources', media);
                params.append('populationParams', pop_str);
                params.append('productApiVersion', api_ver);
                params.append('tokenId', token_id);
                const resp = await fetch(rabbit_url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded', 'Referer': write_url},
                    body: params.toString(),
                    credentials: 'include'
                });
                const text = await resp.text();
                return {status: resp.status, url: resp.url, body: text.substring(0, 1000)};
            }
        """, [RABBIT_WRITE_URL, BLOG_ID, doc_str, '{"image":[],"video":[],"file":[]}', pop_pub, token_id, "v1", WRITE_URL])

        print(f"  발행 응답: {publish_result}")

        await context.storage_state(path=SESSION_FILE)
        await browser.close()

        # URL 추출
        result_body = publish_result.get("body", "")
        try:
            rj = json.loads(result_body.strip())
            if rj.get("isSuccess"):
                redirect = rj.get("result", {}).get("redirectUrl", "")
                if redirect:
                    return redirect
        except Exception:
            pass

        import re
        m = re.search(r'logNo[=:](\d+)', result_body)
        if m:
            return f"https://blog.naver.com/PostView.naver?blogId={BLOG_ID}&logNo={m.group(1)}"

        return None


async def main():
    title = POST_TITLE
    if not title:
        print("❌ NAVER_TITLE 필요")
        sys.exit(1)

    if len(title) > 38:
        title = title[:38]
        print(f"  [경고] 제목 38자 자름: {title}")

    body = ""
    if BODY_PATH and Path(BODY_PATH).exists():
        body = Path(BODY_PATH).read_text(encoding='utf-8')
    else:
        body = os.environ.get("NAVER_BODY", "")

    if not body:
        print("❌ 본문 없음")
        sys.exit(1)

    print(f"\n[네이버 API 발행 v4]")
    print(f"  제목: {title[:50]}")
    print(f"  본문: {len(body)}자")

    result_url = await publish(title, body)

    if result_url:
        print(f"\n✅ 발행 성공!")
        print(f"  URL: {result_url}")
        out = {
            "success": True,
            "naver_url": result_url,
            "title": title,
            "body_chars": len(body),
            "method": "api_v4_jsfetch",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        Path(LOG_PATH).parent.mkdir(exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"  로그 저장: {LOG_PATH}")
        print(result_url)
    else:
        print("\n❌ 발행 실패")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
