#!/usr/bin/env python3
"""
naver_lib/publisher.py — 네이버 블로그 발행 핵심 엔진 v3
─────────────────────────────────────────────────────────
변경 이력:
  v3 (2026-04-17): banidad 포맷 이미지 분산 방식 전면 개선 (노이반님 지시)
    - IMAGE_HERE 마커 완전 제거 (parse_body_to_sections에서 제거)
    - IMAGE_HERE_SLOT 완전 제거
    - 이미지 분산: TEXT 컴포넌트 사이 1:1 교차 삽입 (banidad 실측 패턴)
    - 단락 N개 → 이미지 N-1개 (단락마다 1장씩, 마지막 단락 제외)
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
    FS, para, para_link, empty_para, text_comp, image_comp, oglink_comp,
    brand_card_comp, build_document_model, make_pop
)
from .uploader import download_image, upload_image_file
from .api import oglink_fetch, autosave, rabbit_write


def parse_body_to_sections(body: str, og_map: dict) -> tuple[list, list]:
    """
    본문 → SE 컴포넌트 목록 변환.
    - 쿠팡 링크 줄 → IMAGE_MARKER + OGLINK
    - 일반 텍스트 → TEXT
    - OG_MAP 없는 링크(브랜드커넥트) → PLAIN_LINK (텍스트 링크로 처리)

    v3 변경:
    - IMAGE_HERE 마커 완전 제거 (이미지 분산은 publish()에서 처리)
    - IMAGE_HERE_SLOT 제거
    반환: (components, image_upload_urls)
    """
    LINK_PAT  = re.compile(r'https?://(?:link\.coupang\.com|naver\.me|brand\.naver\.com)\S+')
    A_TAG_PAT = re.compile(r'<a\s+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
    # 링크 박스 구분선 패턴 (━━━ 3개 이상)
    DIVIDER_PAT = re.compile(r'^━{3,}$')

    HEADING_EMOJIS = ('🛒', '✅', '⚠', '📌', '🎯', '💡', '🔍', '📊', '🏷', '💰', '👍', '❌', '🔑', '📋', '🎁',
                      '🛍', '💬', '🔧', '📦', '⭐', '🌟', '💫', '🏆', '🎪', '📝', '🚀', '💎', '🎉', '👉', '✨', '🔥')

    def _line_to_para(s: str) -> dict:
        """단일 줄 → para 객체 (bold/heading/tiny 자동 판별)."""
        if not s:
            return empty_para()
        # 브랜드커넥트 고지문, 해시태그
        if '파트너스 활동' in s or s.startswith('📢') or (s.startswith('#') and s.count('#') >= 3):
            return para(s, fs=FS["tiny"])
        # 소제목 판별: 이모지로 시작하는 짧은 줄 (실제 포스팅 기준)
        is_heading = (
            3 <= len(s) <= 60
            and not any(s.endswith(e) for e in ('요.', '요!', '요?', '네요.', '다.', '다!', '습니다.', '어요.', '어요!', '더라고요.', '거든요.', '거든요'))
            and any(s.startswith(em) for em in HEADING_EMOJIS)
        )
        if is_heading:
            return para(s, bold=True, fs=FS["heading"])
        return para(s, fs=FS["normal"])

    image_upload_urls = []
    sections = []
    components = []
    first_image = True
    url_seen_count: dict[str, int] = {}

    # ── v5: 링크 박스 선처리 ─────────────────────────────────────────
    # 패턴: ━━━\n내용\n👉 링크\n━━━ → 링크만 추출하고 나머지는 버림
    # 링크 박스 전체를 하나의 LINK_BOX 마커로 교체
    def _normalize_link_boxes(text: str) -> str:
        """━━━ 링크 박스를 '링크 URL만 남기고' 구분선 제거."""
        lines_in = text.split('\n')
        lines_out = []
        i = 0
        while i < len(lines_in):
            s = lines_in[i].strip()
            # 구분선 시작 감지
            if DIVIDER_PAT.match(s):
                # 다음 줄들에서 링크 URL 찾기 (다음 구분선까지)
                j = i + 1
                found_url = None
                while j < len(lines_in) and not DIVIDER_PAT.match(lines_in[j].strip()):
                    m = LINK_PAT.search(lines_in[j])
                    if m:
                        found_url = m.group(0).rstrip('.,)')
                    j += 1
                # 닫는 구분선 소비
                if j < len(lines_in) and DIVIDER_PAT.match(lines_in[j].strip()):
                    j += 1
                # 구분선 블록 전체를 링크 한 줄로 교체
                if found_url:
                    lines_out.append(found_url)
                i = j
            else:
                lines_out.append(lines_in[i])
                i += 1
        return '\n'.join(lines_out)

    # 링크 박스 정규화 적용
    body = _normalize_link_boxes(body)

    # ── v4: 이중 줄바꿈으로 문단 블록 분리 ──────────────────────────────
    raw_blocks = re.split(r'\n{2,}', body.strip())

    for block in raw_blocks:
        lines = block.split('\n')
        # IMAGE_HERE 마커 줄 제거
        lines = [l for l in lines if l.strip() not in ('IMAGE_HERE', '[IMAGE]')]
        if not lines:
            continue

        # 블록 안에 링크/a태그가 있는지 확인
        block_has_link = any(
            LINK_PAT.search(l.strip()) or A_TAG_PAT.search(l.strip())
            for l in lines
        )

        if block_has_link:
            # 링크 포함 블록: 줄 단위로 처리 (링크 줄 전후 분리)
            pending_text_lines = []

            def _flush_pending():
                nonlocal pending_text_lines
                if pending_text_lines:
                    paras = [_line_to_para(l.strip()) for l in pending_text_lines if l.strip()]
                    if paras:
                        sections.append(('block_paras', paras))
                    pending_text_lines = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                a_match = A_TAG_PAT.search(stripped)
                if a_match:
                    _flush_pending()
                    sections.append(('para_link', (a_match.group(1).strip(), a_match.group(2).strip() or "구매하기")))
                    continue

                m = LINK_PAT.search(stripped)
                if m:
                    _flush_pending()
                    sections.append(('link', m.group(0).rstrip('.,)')))
                else:
                    pending_text_lines.append(line)

            _flush_pending()

        else:
            # 순수 텍스트 블록 → 블록 전체를 하나의 TEXT 컴포넌트로
            non_empty = [l.strip() for l in lines if l.strip()]
            if non_empty:
                sections.append(('block_paras', [_line_to_para(s) for s in non_empty]))

    # ── 섹션 → 컴포넌트 변환 ──────────────────────────────────────────
    for sec_type, sec_content in sections:

        if sec_type == 'block_paras':
            # 문단 블록 전체를 하나의 TEXT 컴포넌트로
            if sec_content:
                components.append({'_type': 'TEXT', '_paras': sec_content})

        elif sec_type == 'para_link':
            a_url, a_text = sec_content
            components.append({'_type': 'PARA_LINK', '_url': a_url, '_text': a_text})

        elif sec_type == 'link':
            url = sec_content
            url_seen_count[url] = url_seen_count.get(url, 0) + 1
            count = url_seen_count[url]

            if url in og_map:
                if count == 1:
                    image_upload_urls.append(url)
                    components.append({'_type': 'IMAGE_MARKER', '_url': url, '_is_first': first_image})
                    first_image = False
                else:
                    components.append({'_type': 'OGLINK', '_url': url})
            else:
                components.append({'_type': 'PLAIN_LINK', '_url': url})

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
    product_info: dict | None = None,  # P005 brand_card fallback용 상품 정보
    shorten_url_override: str | None = None,  # OG카드 클릭 시 이동 URL (naver.me)
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

        # ── STEP 1: se-auth 캡처 (쿠팡 링크 또는 naver.me 링크) ──
        # se-auth: OGLink API 헤더에서 캡처 → OG카드 생성에 필요
        # P005: naver.me 링크도 oglink API로 OG카드 생성 가능 (2026-04-16 확인)
        import re as _re
        _naver_me_links = list(dict.fromkeys(
            m.group(0).rstrip('.,)')
            for m in _re.finditer(r'https://naver\.me/\S+', body)
        ))
        _trigger_link = (_product_links + _naver_me_links + [None])[0]

        if _trigger_link:
            be = await page.query_selector(".se-component.se-text")
            if be:
                box = await be.bounding_box()
                await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
            await page.keyboard.type(_trigger_link, delay=5)
            await page.keyboard.press("Enter")
            print(f"  se-auth 캡처 대기 (최대 15s)...")
            await page.wait_for_timeout(15000)
        else:
            await page.wait_for_timeout(2000)

        se_auth   = captured["se_auth"]
        se_app_id = captured["se_app_id"]
        print(f"  se-auth: {'있음' if se_auth else '없음 (OG카드 없는 발행)'}")

        # ── STEP 2: OGLink 수집 (쿠팡 + naver.me) ───────────────
        og_map: dict[str, dict] = {}
        if se_auth:
            _all_og_targets = list(dict.fromkeys(_product_links + _naver_me_links))
            if _all_og_targets:
                print(f"  OG카드 수집 ({len(_all_og_targets)}개)...")
                for link in _all_og_targets:
                    og = await oglink_fetch(page, link, se_auth, se_app_id)
                    if og:
                        og_map[link] = og
                        print(f"    ✅ OG카드: {og['title'][:40]}")
                    else:
                        print(f"    ⚠️ OG 실패 → 텍스트링크로 대체: {link[:50]}")

        # ── STEP 3: 썸네일 다운로드 ─────────────────────────────
        thumb_local: dict[str, str] = {}
        for link, og in og_map.items():
            turl = og.get("thumb_url", "")
            if turl:
                idx = list(og_map.keys()).index(link)
                local = download_image(turl, tmpdir, idx)
                if local:
                    thumb_local[link] = local

        # extra_image_urls 다운로드
        # 규칙 2: 프로필/배너 이미지 URL 필터 (노이반님 지시 2026-04-17)
        _SKIP_IMG_PATTERNS = [
            'blogpfthumb', 'profileImage', 'profile_img',
            'MjAyNjA0MTVf',  # 특정 프로필 썸네일 패턴
        ]
        _filtered_urls = [
            u for u in (extra_image_urls or [])
            if not any(p in u for p in _SKIP_IMG_PATTERNS)
        ]
        if len(_filtered_urls) < len(extra_image_urls or []):
            print(f"  프로필 이미지 {len(extra_image_urls or []) - len(_filtered_urls)}장 필터링")
        extra_local = []
        if _filtered_urls:
            try:
                import requests as _req
                for ei, eurl in enumerate(_filtered_urls[:15]):
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
                        if r.status_code == 200 and len(r.content) > 10000:
                            save_path = _os.path.join(tmpdir, f"extra_{ei}.jpg")
                            with open(save_path, "wb") as f:
                                f.write(r.content)
                            extra_local.append(save_path)
                            print(f"    ✅ 추가이미지 {ei+1}: {len(r.content)//1024}KB")
                    except Exception as e:
                        print(f"    ⚠️ 추가이미지 실패: {e}")
            except ImportError:
                pass

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

        # 커서 활성화
        be = await page.query_selector(".se-component.se-text")
        if be:
            box = await be.bounding_box()
            await page.mouse.click(box['x'] + 50, box['y'] + box['height'] / 2)
        await page.keyboard.type(".", delay=5)

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
                    # shorten_url_override: 카드 클릭 시 naver.me로 이동 (노이반님 원칙)
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
                # URL 단독 줄 → OG카드 (og_map에 있으면) 또는 brand_card 또는 하이퍼링크
                url = item['_url']
                # og_map에 naver.me 또는 smartstore URL이 있으면 OG카드 우선
                if url in og_map:
                    og = og_map[url]
                    try:
                        from urllib.parse import urlparse as _up
                        _domain = _up(url).netloc
                    except Exception:
                        _domain = "naver.me"
                    # shorten_url_override: 카드 클릭 시 naver.me로 이동 (노이반님 원칙)
                    _card_link = shorten_url_override if shorten_url_override else url
                    final_comps.append(oglink_comp(
                        og_sign=og["oglinkSign"],
                        title=og["title"],
                        desc=og["description"],
                        thumb_url=og["thumb_url"],
                        link=_card_link,
                        domain=_domain,
                    ))
                elif product_info:
                    # OG카드 없음 + 상품 정보 있음 → brand_card_comp (카드형)
                    p_name  = product_info.get("productName", "")[:30]
                    p_price = product_info.get("discountedPrice") or product_info.get("salePrice", 0)
                    p_disc  = product_info.get("discountedRate", 0)
                    price_str = f"{p_price:,}원" if p_price else ""
                    disc_str  = f" ({p_disc}% 할인)" if p_disc else ""
                    desc = f"{price_str}{disc_str}" if price_str else "지금 바로 확인하세요"
                    final_comps.append(brand_card_comp(
                        title=p_name, desc=desc, thumb_url="", link=url
                    ))
                else:
                    final_comps.append(text_comp([para_link("🔗 지금 네이버에서 확인하기", url)]))

        # ── 이미지 분산 삽입 (v5: TEXT 각각 뒤에 1장씩 균등 교차) ──────
        # 목표: TEXT → IMAGE → TEXT → IMAGE → TEXT → IMAGE ...
        # 단락 12~16개, 이미지 10~14장 → 각 TEXT 뒤에 1장씩
        # TEXT 수 >= 이미지 수: 균등 간격으로 이미지 있는 단락 선택
        # TEXT 수 < 이미지 수: 모든 단락 뒤에 이미지 + 남은 이미지는 TEXT 사이에 추가
        extra_queue = list(extra_uploaded)
        if extra_queue:
            text_indices = [
                i for i, c in enumerate(final_comps)
                if isinstance(c, dict) and c.get('_type') == 'TEXT'
            ]
            n_text = len(text_indices)
            n_imgs = len(extra_queue)

            if n_text < 1:
                for eu in extra_queue:
                    final_comps.append(image_comp(
                        src=eu["src"], path=eu["path"],
                        width=eu["width"], height=eu["height"],
                        filename=eu["fileName"], represent=False, file_size=eu["fileSize"]
                    ))
            else:
                # 각 TEXT 뒤를 삽입 후보로 사용 (n_text개 슬롯)
                # n_imgs <= n_text: 균등 간격 선택
                # n_imgs > n_text: 전부 사용 + 초과분은 마지막에 추가
                n_insert = min(n_imgs, n_text)

                if n_insert >= n_text:
                    # 이미지가 TEXT 수와 같거나 많음 → 모든 TEXT 뒤에 1장씩
                    selected_text_idx = list(range(n_text))
                else:
                    # 이미지가 부족 → 균등 간격으로 TEXT 선택
                    step = n_text / n_insert
                    selected_text_idx = sorted(set(
                        min(int(step * i + step / 2), n_text - 1)
                        for i in range(n_insert)
                    ))
                    # 중복 제거 후 부족분 보완
                    all_idx = set(range(n_text))
                    remaining_slots = sorted(all_idx - set(selected_text_idx))
                    while len(selected_text_idx) < n_insert and remaining_slots:
                        selected_text_idx.append(remaining_slots.pop(0))
                    selected_text_idx = sorted(selected_text_idx[:n_insert])

                # text_indices[k] 이후에 이미지 삽입 (뒤에서부터, 인덱스 밀림 방지)
                insert_positions = [text_indices[k] for k in selected_text_idx]
                imgs_to_insert = extra_queue[:len(insert_positions)]

                for text_pos, eu in zip(sorted(insert_positions, reverse=True),
                                        list(reversed(imgs_to_insert))):
                    final_comps.insert(text_pos + 1, image_comp(
                        src=eu["src"], path=eu["path"],
                        width=eu["width"], height=eu["height"],
                        filename=eu["fileName"], represent=False, file_size=eu["fileSize"]
                    ))

                print(f"  이미지 분산: {len(insert_positions)}장 TEXT 뒤 삽입 (단락당 1장 교차)")

                # 남은 이미지 (TEXT 수보다 이미지가 더 많은 경우)
                remaining = extra_queue[len(insert_positions):]
                if remaining:
                    step2 = max(2, len(final_comps) // (len(remaining) + 1))
                    for i, eu in enumerate(remaining):
                        pos = min(step2 * (i + 1), len(final_comps))
                        final_comps.insert(pos, image_comp(
                            src=eu["src"], path=eu["path"],
                            width=eu["width"], height=eu["height"],
                            filename=eu["fileName"], represent=False, file_size=eu["fileSize"]
                        ))
                    print(f"  남은 이미지 {len(remaining)}장 → 균등 분산 추가")

        doc_str = build_document_model(title, final_comps, category_no=category_no)
        pop_save = make_pop(category_no=category_no, auto_save_no=None)

        print(f"  documentModel: {len(doc_str)}자, 컴포넌트 {len(final_comps)+1}개")

        # ── STEP 7: 자동저장 ────────────────────────────────────
        save_result = await autosave(page, blog_id, doc_str, pop_save)
        if not save_result:
            await browser.close()
            return None

        auto_save_no = save_result.get("autoSaveNo")
        print(f"  ✅ autoSaveNo={auto_save_no}")

        # ── STEP 8: 발행 ────────────────────────────────────────
        # 확인된 사실: tokenId는 세션 쿠키에 내재 → 빈 문자열로도 발행 성공
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
