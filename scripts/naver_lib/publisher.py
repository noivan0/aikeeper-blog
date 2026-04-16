#!/usr/bin/env python3
"""
naver_lib/publisher.py — 네이버 블로그 발행 핵심 엔진 v2
─────────────────────────────────────────────────────────
변경 이력:
  v2 (2026-04-15): naver_lib 분리, tokenId 캡처 버그 수정
    - Ctrl+S 후 팝업 처리 순서 보정 (poll 기반으로 변경)
    - OG 링크 없는 발행 지원 (P005 브랜드커넥트용)
    - blog_id, category_no 파라미터화

확정 사실 (재조사 금지):
  - tokenId: RabbitAutoSaveWrite.naver 요청에서 캡처
  - se-authorization: platform.editor.naver.com 요청 헤더
  - file input: #hidden-file (이미지 버튼 클릭 후 생성)
  - 업로드 API: blog.upphoto.naver.com (XML 응답)
  - not acceptable: documentModel 구조 오류 시
"""
import os
import re
import json
import asyncio
import tempfile
import urllib.parse

from playwright.async_api import async_playwright

from .session import load_session, save_session, login_if_needed, dismiss_popups
from .document import (
    FS, para, para_link, empty_para, empty_paras, text_comp, image_comp, oglink_comp,
    brand_card_comp, build_document_model, make_pop
)
from .uploader import download_image, upload_image_file
from .api import oglink_fetch, autosave, rabbit_write


def _split_long_line(text: str, target_len: int = 50) -> list[str]:
    """
    긴 줄(100자 이상)을 자연스러운 위치에서 2~3줄로 분리.
    쉼표, 마침표, 조사/어미 단위로 끊음.
    banidad 스타일: 짧은 줄 단위로 줄바꿈.
    """
    if len(text) <= target_len:
        return [text]

    # 분리 기준 패턴 (우선순위 순)
    split_markers = [
        r'(?<=[.!?])\s+',           # 문장 끝 후 공백
        r'(?<=[,，])\s+',           # 쉼표 후 공백
        r'(?<=요\.)\s+',             # ~요. 후 공백
        r'(?<=다\.)\s+',             # ~다. 후 공백
        r'(?<=어요\.)\s+',           # ~어요. 후 공백
        r'(?<=더라고요\.)\s+',       # ~더라고요. 후
        r'(?<=거든요\.)\s+',         # ~거든요. 후
        r'(?<=[는은이가을를에서])\s+', # 조사 후 공백
    ]

    import re as _re
    for pattern in split_markers:
        parts = _re.split(pattern, text)
        if len(parts) >= 2:
            # 적절한 길이로 재조합
            result = []
            current = ""
            for part in parts:
                if not current:
                    current = part
                elif len(current) + len(part) + 1 <= target_len * 2:
                    current += " " + part
                else:
                    result.append(current)
                    current = part
            if current:
                result.append(current)
            if len(result) >= 2:
                return result

    # 패턴 분리 실패 시 단순 글자 수로 분리
    chunks = []
    while len(text) > target_len * 2:
        # 가장 가까운 공백에서 끊기
        cut = target_len * 2
        space_pos = text.rfind(' ', target_len, cut)
        if space_pos > 0:
            chunks.append(text[:space_pos].strip())
            text = text[space_pos:].strip()
        else:
            chunks.append(text[:cut])
            text = text[cut:]
    if text:
        chunks.append(text)
    return chunks if chunks else [text]


def parse_body_to_sections(body: str, og_map: dict) -> tuple[list, list]:
    """
    본문 → SE 컴포넌트 목록 변환.
    - 쿠팡 링크 줄 → IMAGE_MARKER + OGLINK
    - 일반 텍스트 → TEXT
    - OG_MAP 없는 링크(브랜드커넥트) → PLAIN_LINK (텍스트 링크로 처리)
    반환: (components, image_upload_urls)
    """
    # ── 본문 전처리: HTML 태그 완전 제거 (AI 생성 HTML이 텍스트로 출력되는 문제 방지) ──
    # 1단계: <span style=...> 등 래퍼 태그로 감싸진 <a href> 처리
    #   예: <span style="..."><a href="URL">텍스트</a></span>
    #   → URL만 추출해서 단독 줄로 교체
    def _replace_a_tag(m):
        url = m.group(1).split('"')[0].split("'")[0].strip()  # 혹시 모를 trailing 문자 제거
        return f"\n지금 네이버에서 확인하기 → {url}\n"
    # a href 포함된 span 블록 전체 제거 후 URL 보존 (DOTALL로 멀티라인 대응)
    body = re.sub(r'<span[^>]*>\s*<a\s+href=["\']([^"\']+)["\'][^>]*>[^<]*</a>\s*</span>',
                  _replace_a_tag, body, flags=re.IGNORECASE | re.DOTALL)
    # 단독 <a href> 태그 처리
    body = re.sub(r'<a\s+href=["\']([^"\']+)["\'][^>]*>[^<]*</a>',
                  _replace_a_tag, body, flags=re.IGNORECASE)
    # 2단계: 나머지 모든 HTML 태그 제거 (<span>, <b>, <br>, <p>, <div> 등)
    body = re.sub(r'<[^>]+>', '', body)
    # 3단계: HTML 엔티티 복원
    body = body.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')
    # 4단계: --- 구분선 제거
    body = re.sub(r'^-{3,}$', '', body, flags=re.MULTILINE)

    LINK_PAT  = re.compile(r'https?://(?:link\.coupang\.com|naver\.me|brand\.naver\.com)\S+')
    A_TAG_PAT = re.compile(r'<a\s+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)

    image_upload_urls = []
    sections = []
    current_lines = []

    def flush():
        if current_lines:
            sections.append(('lines', list(current_lines)))
            current_lines.clear()

    LINK_TEXT_PAT = re.compile(r'^LINK_TEXT:(.+)\|(.+)$')

    for line in body.split('\n'):
        stripped = line.strip()
        # IMAGE_HERE 마커: 소제목 직후 이미지 배치 위치 표시
        if stripped == 'IMAGE_HERE':
            flush()
            sections.append(('image_marker', ''))
            continue
        # LINK_TEXT:텍스트|URL 마커 → urlLink 하이퍼링크 (P005 링크 방식)
        lt_match = LINK_TEXT_PAT.match(stripped)
        if lt_match:
            lt_text = lt_match.group(1).strip()
            lt_url  = lt_match.group(2).strip().rstrip('.,)')
            flush()
            sections.append(('para_link', (lt_url, lt_text)))
            continue
        # C: <a href="URL">텍스트</a> 패턴 명시 파싱 → PARA_LINK
        a_match = A_TAG_PAT.search(stripped)
        if a_match:
            a_url  = a_match.group(1).strip()
            a_text = a_match.group(2).strip() or "구매하기"
            flush()
            sections.append(('para_link', (a_url, a_text)))
            continue
        m = LINK_PAT.search(stripped)
        if m:
            url = m.group(0).rstrip('.,)')
            flush()
            sections.append(('link', url))
        else:
            current_lines.append(line)
    flush()

    HEADING_EMOJIS = (
        '🛒', '✅', '⚠', '📌', '🎯', '💡', '🔍', '📊', '🏷', '💰', '👍', '❌', '🔑', '📋', '🎁',
        '🥚', '🔩', '⏱', '🍠', '💬', '🧹', '🔧', '📋', '🏆', '🌟', '💎', '🎪', '🔑', '🛍',
        '🎁', '💝', '🔥', '⚡', '🌈', '🎨', '📱', '🖥', '🏠', '🍳', '🥘', '🧺', '🪣', '🧴',
        # P005 추가 이모지 (generate_naver_post.py 프롬프트 기반)
        '📦', '💨', '🔋', '🤲', '🌿', '✍️', '📷', '🎬', '🎮', '🧩', '🪴', '🫖', '🧇', '🥗',
        '🎀', '🪄', '🔮', '🧸', '🪆', '🌻', '🍀', '🌙', '☀️', '🌊', '🏖', '🏕', '🎭', '🎸',
        # P005 소제목 패턴 추가 (2026-04-16)
        '🌀', '💸', '🎖', '🏅', '🛠', '🧪', '📐', '🧲', '🪝', '🫙', '🧊', '🌡', '⚙',
        '🪤', '🪜', '🔬', '🏋', '🧘', '🤸', '🚴', '🏃', '🚶', '🧳', '🎒', '👜', '👝',
    )
    components = []
    first_image = True
    url_seen_count: dict[str, int] = {}

    # IMAGE_HERE 마커 카운트 (extra_image 배치용)
    image_here_count = sum(1 for t, _ in sections if t == 'image_marker')
    image_here_idx = [0]  # mutable counter

    for sec_type, sec_content in sections:
        if sec_type == 'image_marker':
            # IMAGE_HERE: extra_image 배치 예약 (실제 이미지는 STEP5에서 삽입)
            components.append({'_type': 'IMAGE_HERE_SLOT'})
            image_here_idx[0] += 1
            continue

        if sec_type == 'para_link':
            # C: <a href="URL">텍스트</a> → urlLink 하이퍼링크 컴포넌트
            a_url, a_text = sec_content
            components.append({'_type': 'PARA_LINK', '_url': a_url, '_text': a_text})
            continue

        if sec_type == 'link':
            url = sec_content
            url_seen_count[url] = url_seen_count.get(url, 0) + 1
            count = url_seen_count[url]

            if url in og_map:
                # 쿠팡 링크: 이미지 + OG카드
                if count == 1:
                    image_upload_urls.append(url)
                    components.append({'_type': 'IMAGE_MARKER', '_url': url, '_is_first': first_image})
                    first_image = False
                else:
                    components.append({'_type': 'OGLINK', '_url': url})
            else:
                # OG카드 없는 링크(브랜드커넥트 naver.me 등) → 텍스트 링크로 삽입
                components.append({'_type': 'PLAIN_LINK', '_url': url})

        else:  # 'lines'
            paras = []
            for line in sec_content:
                s = line.strip()
                if not s:
                    paras.extend(empty_paras(2))  # banidad 스타일: 빈 줄 2개로 시각적 여백
                    continue
                if '파트너스 활동' in s or s.startswith('📢') or (s.startswith('#') and s.count('#') >= 3):
                    paras.append(para(s, fs=FS["tiny"]))
                    continue
                is_heading = (
                    5 <= len(s) <= 60
                    and not any(s.endswith(e) for e in ('요.', '요!', '요?', '네요.', '다.', '다!', '습니다.', '어요.', '어요!', '더라고요.', '거든요.', '있어요.', '없어요.'))
                    and (
                        any(s.startswith(em) for em in HEADING_EMOJIS)
                        or '—' in s
                        or any(c in s for c in ['가이드', '비교', '정리', '선택', '체크', '기준', '방법', '포인트', '결론'])
                    )
                )
                if is_heading:
                    # 소제목: 중앙 정렬 (banidad 스타일)
                    paras.append(para(s, bold=True, fs=FS["heading"], align="center"))
                elif len(s) >= 100:
                    # 긴 줄(100자 이상): 자동으로 2~3줄로 split하여 가독성 향상
                    # 자연스러운 위치(쉼표, 마침표, 조사 뒤)에서 분리
                    split_lines = _split_long_line(s)
                    for sl in split_lines:
                        if sl.strip():
                            paras.append(para(sl.strip(), fs=FS["normal"]))
                else:
                    paras.append(para(s, fs=FS["normal"]))
            if paras:
                components.append({'_type': 'TEXT', '_paras': paras})

    return components, image_upload_urls


async def publish(
    title: str,
    body: str,
    blog_id: str,
    category_no: int = 6,
    product_links: list | None = None,
    extra_image_urls: list | None = None,
    session_file: str | None = None,
    naver_id: str | None = None,
    naver_pw: str | None = None,
    product_info: dict | None = None,   # P005 브랜드커넥트 카드형 링크용 상품 정보
    shorten_url_override: str | None = None,  # 개선-1: OG카드 클릭 시 이동 URL override (naver.me)
) -> str | None:
    """
    네이버 블로그 발행 메인 함수.
    성공 시 발행된 URL 반환, 실패 시 None.

    Args:
        title: 포스트 제목
        body: 본문 (링크 줄 포함)
        blog_id: 네이버 블로그 ID (e.g. "prosweep", "kjjhad")
        category_no: 카테고리 번호
        product_links: OG카드 추출용 쿠팡 링크 목록 (없으면 본문에서 자동 파싱)
        extra_image_urls: 추가 이미지 URL 목록 (최대 4개)
        session_file: 세션 파일 경로 (None이면 환경변수/기본값)
        naver_id: 네이버 ID (None이면 환경변수)
        naver_pw: 네이버 PW (None이면 환경변수)
    """
    _id = naver_id or os.environ.get("NAVER_ID", "")
    _pw = naver_pw or os.environ.get("NAVER_PW", "")
    _session = load_session(session_file)
    _product_links = product_links or []

    # 본문에서도 쿠팡 링크 추출
    for bl in re.findall(r'https://link\.coupang\.com/\S+', body):
        bl = bl.rstrip('.,)')
        if bl not in _product_links:
            _product_links.append(bl)

    WRITE_URL = f"https://blog.naver.com/{blog_id}/postwrite?categoryNo={category_no}"
    tmpdir = tempfile.mkdtemp()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        ctx_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 900},
        }
        import os as _os
        from pathlib import Path as _Path
        if _Path(_session).exists():
            ctx_kwargs["storage_state"] = _session

        context = await browser.new_context(**ctx_kwargs)
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        captured = {"se_auth": "", "se_app_id": ""}

        async def on_req(req):
            if "oglink" in req.url and "platform.editor" in req.url:
                if not captured["se_auth"]:
                    captured["se_auth"] = req.headers.get("se-authorization", "")
                    captured["se_app_id"] = req.headers.get("se-app-id", "")

        context.on("request", on_req)
        page = await context.new_page()

        # ── 에디터 로드 ─────────────────────────────────────────
        await page.goto(WRITE_URL, timeout=40000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        # 로그인 체크
        ok = await login_if_needed(page, context, WRITE_URL, _id, _pw, _session)
        if not ok:
            await browser.close()
            return None

        # 팝업 처리 (에디터 진입 시)
        await dismiss_popups(page)

        try:
            await page.wait_for_selector(".se-component.se-text, .se-documentTitle", timeout=25000)
        except Exception:
            print("  ❌ 에디터 로드 실패")
            await browser.close()
            return None
        await page.wait_for_timeout(1000)

        # ── STEP 1: se-auth 캡처 (쿠팡 링크 또는 naver.me 링크 있을 때) ──
        # 확인된 사실: tokenId는 세션 쿠키로 대체 가능 → 캡처 불필요
        # se-auth: OGLink API 헤더에서 캡처
        # P005: naver.me 링크도 oglink API로 카드 생성 시도
        import re as _re
        _naver_me_links = list({
            m.group(0).rstrip('.,)')
            for m in _re.finditer(r'https://naver\.me/\S+', body)
        })
        _trigger_link = (_product_links or _naver_me_links or [None])[0]

        if _trigger_link:
            # 링크 타이핑 → OGLink 요청 트리거 → se-auth 캡처
            be = await page.query_selector(".se-component.se-text")
            if be:
                box = await be.bounding_box()
                await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
            await page.keyboard.type(_trigger_link, delay=5)
            await page.keyboard.press("Enter")
            print("  se-auth 캡처 대기 (최대 15s)...")
            await page.wait_for_timeout(10000)
            # 10초 후에도 se-auth 없으면 추가 5초 대기
            if not captured["se_auth"]:
                print("  se-auth 미캡처 — 추가 5초 대기...")
                await page.wait_for_timeout(5000)
        else:
            # 링크 없는 경우: 에디터 활성화만
            await page.wait_for_timeout(2000)

        se_auth   = captured["se_auth"]
        se_app_id = captured["se_app_id"]
        print(f"  se-auth: {'있음' if se_auth else '없음 (OG카드 없는 발행)'}")

        # ── STEP 2: OGLink 수집 (쿠팡 링크 + naver.me 링크) ─────
        og_map: dict[str, dict] = {}
        if se_auth:
            all_og_links = list(dict.fromkeys(_product_links + _naver_me_links))
            if all_og_links:
                print(f"  OG카드 수집 ({len(all_og_links)}개: 쿠팡 {len(_product_links)}개 + naver.me {len(_naver_me_links)}개)...")
                for link in all_og_links:
                    og = await oglink_fetch(page, link, se_auth, se_app_id)
                    if og:
                        og_map[link] = og
                        print(f"    ✅ OG카드: {og['title'][:35]}")
                    else:
                        print(f"    ⚠️ OG 실패 (하이퍼링크로 대체): {link[:50]}")

        # ── STEP 3: 썸네일 다운로드 ─────────────────────────────
        thumb_local: dict[str, str] = {}
        for link, og in og_map.items():
            turl = og.get("thumb_url", "")
            if turl:
                idx = list(og_map.keys()).index(link)
                local = download_image(turl, tmpdir, idx)
                if local:
                    thumb_local[link] = local

        # extra_image_urls 다운로드 (최대 4장 제한 — documentModel payload 크기 제한)
        # 네이버 RabbitAutoSaveWrite: payload ~100KB 초과 시 UNKNOWN 오류
        # 이미지 1장 업로드 후 document 반영 크기 ~15KB → 4장 = ~60KB (안전)
        # 기존 6장에서 4장으로 축소 (95KB → UNKNOWN 오류 방지)
        MAX_EXTRA_IMGS = 4
        extra_local = []
        if extra_image_urls:
            try:
                import requests as _req
                for ei, eurl in enumerate(extra_image_urls[:MAX_EXTRA_IMGS]):
                    if len(extra_local) >= MAX_EXTRA_IMGS:
                        break
                    try:
                        # URL 도메인에 맞는 Referer 자동 선택
                        if 'naver' in eurl or 'pstatic' in eurl:
                            _ref = 'https://smartstore.naver.com/'
                        elif 'coupang' in eurl:
                            _ref = 'https://www.coupang.com/'
                        else:
                            _ref = 'https://www.naver.com/'
                        r = _req.get(eurl, timeout=8, allow_redirects=True,
                                     headers={"Referer": _ref, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                        if r.status_code == 200 and 10000 < len(r.content) < 3_000_000:
                            save_path = _os.path.join(tmpdir, f"extra_{ei}.jpg")
                            with open(save_path, "wb") as f:
                                f.write(r.content)
                            extra_local.append(save_path)
                            print(f"    ✅ 추가이미지 {ei+1}: {len(r.content)//1024}KB")
                        elif r.status_code == 200:
                            print(f"    ⚠️ 추가이미지 {ei+1} 스킵: {len(r.content)//1024}KB (크기 부적합)")
                    except Exception as e:
                        print(f"    ⚠️ 추가이미지 실패: {e}")
            except ImportError:
                pass
        print(f"  이미지 다운로드 완료: {len(extra_local)}/{min(len(extra_image_urls or []), MAX_EXTRA_IMGS)}장")

        # ── STEP 4: 새 에디터 페이지로 이동 ─────────────────────
        await page.goto(WRITE_URL, timeout=40000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        await dismiss_popups(page)
        await page.wait_for_selector(".se-component.se-text", timeout=20000)
        await page.wait_for_timeout(1000)

        # 커서 활성화 — 에디터 본문 클릭 + 텍스트 입력으로 툴바 활성화
        be = await page.query_selector(".se-component.se-text")
        if be:
            box = await be.bounding_box()
            await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
        # 여러 줄 입력해 에디터 충분히 활성화 (이미지 버튼 노출 보장)
        await page.keyboard.type(".", delay=5)
        await page.keyboard.press("Enter")
        await page.keyboard.type(".", delay=5)
        await page.wait_for_timeout(500)
        # 툴바 이미지 버튼 강제 노출 시도
        await page.evaluate("""() => {
            const btn = document.querySelector('.se-image-toolbar-button');
            if (btn) { btn.style.display = 'block'; btn.style.visibility = 'visible'; }
        }""")

        # ── STEP 5: 이미지 업로드 ───────────────────────────────
        section_comps, image_upload_urls = parse_body_to_sections(body, og_map)
        image_upload_urls = [u for u in image_upload_urls if u in thumb_local]

        uploaded_images: dict[str, dict] = {}
        first_upload = True

        if image_upload_urls:
            print(f"  이미지 업로드 ({len(image_upload_urls)}개)...")
            for link in image_upload_urls:
                result = await upload_image_file(page, thumb_local[link])
                if result:
                    result["represent"] = first_upload
                    uploaded_images[link] = result
                    first_upload = False

        # extra 이미지 업로드
        extra_uploaded = []
        if extra_local:
            print(f"  추가 이미지 업로드 ({len(extra_local)}개)...")
            for local_path in extra_local:
                result = await upload_image_file(page, local_path)
                if result:
                    extra_uploaded.append(result)
                else:
                    print(f"    ⚠️ 업로드 실패: {local_path}")
        if not extra_uploaded:
            print(f"  ⚠️ 추가 이미지 없음 — IMAGE_HERE_SLOT {sum(1 for c in section_comps if c.get('_type') == 'IMAGE_HERE_SLOT')}개 빈 상태로 스킵됨")

        # ── STEP 6: documentModel 구성 ──────────────────────────
        final_comps = []
        for item in section_comps:
            t = item['_type']
            if t == 'TEXT':
                final_comps.append(text_comp(item['_paras']))
            elif t == 'IMAGE_MARKER':
                link = item['_url']
                if link in uploaded_images:
                    ui = uploaded_images[link]
                    final_comps.append(image_comp(
                        src=ui["src"], path=ui["path"],
                        width=ui["width"], height=ui["height"],
                        filename=ui["fileName"],
                        represent=ui["represent"],
                        file_size=ui["fileSize"]
                    ))
            elif t == 'OGLINK':
                link = item['_url']
                if link in og_map:
                    og = og_map[link]
                    # 도메인 추출
                    try:
                        from urllib.parse import urlparse
                        _domain = urlparse(link).netloc
                    except Exception:
                        _domain = "link.coupang.com"
                    # 개선-1: shorten_url_override가 있으면 카드 클릭 → naver.me로 이동
                    card_link = shorten_url_override if shorten_url_override else link
                    final_comps.append(oglink_comp(
                        og_sign=og["oglinkSign"],
                        title=og["title"],
                        desc=og["description"],
                        thumb_url=og["thumb_url"],
                        link=card_link,
                        domain=_domain,
                    ))
            elif t == 'PARA_LINK':
                # C: <a href> 파싱 결과 → urlLink 하이퍼링크
                final_comps.append(text_comp([para_link(item['_text'], item['_url'])]))
            elif t == 'PLAIN_LINK':
                # URL 단독 줄 → oglink 카드 (OG 성공 시) → brand_card → 하이퍼링크 순 우선
                url = item['_url']
                if url in og_map:
                    # naver.me OGLink 성공 → 실제 oglink 카드 컴포넌트
                    og = og_map[url]
                    try:
                        from urllib.parse import urlparse as _up
                        _domain = _up(url).netloc
                    except Exception:
                        _domain = "naver.me"
                    final_comps.append(empty_para())
                    final_comps.append(oglink_comp(
                        og_sign=og["oglinkSign"],
                        title=og["title"],
                        desc=og["description"],
                        thumb_url=og["thumb_url"],
                        link=url,
                        domain=_domain,
                    ))
                    final_comps.append(empty_para())
                elif product_info:
                    # OGLink 실패 + 상품 정보 있음 → brand_card_comp (카드형 텍스트 박스)
                    p_name  = product_info.get("productName", "")[:30]
                    p_price = product_info.get("discountedPrice") or product_info.get("salePrice", 0)
                    p_disc  = product_info.get("discountedRate", 0)
                    price_str = f"{p_price:,}원" if p_price else ""
                    disc_str  = f" ({p_disc}% 할인)" if p_disc else ""
                    desc = f"{price_str}{disc_str}" if price_str else "지금 바로 확인하세요"
                    final_comps.append(empty_para())
                    final_comps.append(brand_card_comp(
                        title=p_name, desc=desc, thumb_url="", link=url
                    ))
                    final_comps.append(empty_para())
                else:
                    # 기본: 하이퍼링크 텍스트
                    link_text = "👉 지금 네이버에서 확인하기"
                    final_comps.append(text_comp([para_link(link_text, url)]))
            elif t == 'IMAGE_HERE_SLOT':
                # IMAGE_HERE 마커: extra_uploaded 이미지 순서대로 배치 (placeholder)
                final_comps.append({'_type': 'IMAGE_HERE_SLOT'})

        # IMAGE_HERE_SLOT을 extra_uploaded 이미지로 교체
        # ⚠️ 빈줄 자동 삽입 제거 — 컴포넌트 수 폭증 방지 (96개 → 14개 목표)
        # 이미지 앞뒤 빈줄만 유지, 텍스트 간 빈줄은 AI 생성 본문에서 처리
        extra_queue = list(extra_uploaded)
        new_final = []
        for comp in final_comps:
            is_slot = isinstance(comp, dict) and comp.get('_type') == 'IMAGE_HERE_SLOT'
            if is_slot:
                if extra_queue:
                    eu = extra_queue.pop(0)
                    new_final.append(empty_para())   # 이미지 앞 빈줄 1개
                    new_final.append(image_comp(
                        src=eu["src"], path=eu["path"],
                        width=eu["width"], height=eu["height"],
                        filename=eu["fileName"],
                        represent=(len(new_final) == 0),
                        file_size=eu["fileSize"]
                    ))
                    new_final.append(empty_para())   # 이미지 뒤 빈줄 1개
                # else: 이미지 없으면 슬롯 스킵
            else:
                new_final.append(comp)
        final_comps = new_final

        # 남은 extra 이미지 본문 중간 분산 삽입 (IMAGE_HERE_SLOT 소화 후 남은 것)
        if extra_queue:
            # IMAGE_HERE_SLOT으로 이미 소화된 이미지 제외한 나머지를 분산
            real_comps = [c for c in final_comps if not (isinstance(c, dict) and c.get('@ctype') == 'image')]
            total = len(final_comps)
            per = max(total // (len(extra_queue) + 1), 1)
            for i, eu in enumerate(extra_queue):
                pos = min(per * (i + 1), len(final_comps))
                ic = image_comp(
                    src=eu["src"], path=eu["path"],
                    width=eu["width"], height=eu["height"],
                    filename=eu["fileName"],
                    represent=False, file_size=eu["fileSize"]
                )
                final_comps.insert(pos, ic)

        doc_str = build_document_model(title, final_comps, category_no=category_no)
        pop_save = make_pop(category_no=category_no, auto_save_no=None)

        print(f"  documentModel: {len(doc_str)}자, 컴포넌트 {len(final_comps)+1}개")

        # ── STEP 7: 자동저장 (실패해도 직접 발행으로 폴백) ─────
        save_result = await autosave(page, blog_id, doc_str, pop_save)
        auto_save_no = None
        if save_result:
            auto_save_no = save_result.get("autoSaveNo")
            print(f"  ✅ autoSaveNo={auto_save_no}")
        else:
            print(f"  ⚠️ 자동저장 실패 — autoSaveNo=None으로 직접 발행 시도 (폴백)")

        # ── STEP 8: 발행 ────────────────────────────────────────
        # 확인된 사실: tokenId는 세션 쿠키에 내재 → 빈 문자열로도 발행 성공
        # autoSaveNo=None이어도 RabbitWrite 발행 시도 가능
        pop_pub = make_pop(category_no=category_no, auto_save_no=auto_save_no)
        publish_result = await rabbit_write(page, blog_id, doc_str, pop_pub, "")
        print(f"  발행: {publish_result.get('status')} | {publish_result.get('body','')[:100]}")

        await save_session(context, _session)
        await browser.close()

        result_body = publish_result.get("body", "")
        try:
            rj = json.loads(result_body.strip())
            if rj.get("isSuccess"):
                return rj.get("result", {}).get("redirectUrl", "")
        except Exception:
            pass

        m = re.search(r'logNo[=:](\d+)', result_body)
        if m:
            return f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={m.group(1)}"

        print(f"  발행 응답: {result_body[:300]}")
        return None
