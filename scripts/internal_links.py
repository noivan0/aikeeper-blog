#!/usr/bin/env python3
"""
internal_links.py — 내부링크 자동삽입 시스템 (aikeeper + allsweep 공통)

핵심 기능:
  1. Blogger API로 최근 포스트 목록 가져오기 (최대 100개)
  2. 현재 포스트 제목/키워드와 자카드 유사도 계산
  3. 라벨/카테고리 일치 + 최신성 가중치 반영
  4. 관련 포스트 3~5개 선택
  5. 포스트 본문 끝 (FAQ 이전)에 카드형 CTA "관련 글" 섹션 삽입
  6. 본문 내 자연스러운 앵커링크 1~2개 삽입 (키워드 매칭)

환경변수:
  TARGET_BLOG_ID  — Blogger 블로그 ID (필수)
  BLOGGER_REFRESH_TOKEN, BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET
"""

import os
import re
import json
import sys
import math
import datetime
import gzip
import urllib.request
import urllib.parse

# ── 환경변수 ───────────────────────────────────────────────────────────────
BLOG_ID       = os.environ.get("TARGET_BLOG_ID", "3598676904202320050")
BLOG_URL      = os.environ.get("TARGET_BLOG_URL", "https://aikeeper.allsweep.xyz")
BLOG_NAME     = os.environ.get("TARGET_BLOG_NAME", "AI키퍼")
THEME_COLOR   = "#4f6ef7"   # 블로그 CSS와 통일

CLIENT_ID     = os.environ.get("BLOGGER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN", "")

# 최대 가져올 포스트 수
MAX_POSTS = 100
# 삽입할 관련 포스트 수 (최소 3, 최대 5)
MIN_RELATED = 3
MAX_RELATED = 5


# ══════════════════════════════════════════════════════════════════════════════
# 1. Google OAuth2 — Access Token 획득
# ══════════════════════════════════════════════════════════════════════════════

def get_access_token() -> str:
    """refresh_token → access_token"""
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        raise RuntimeError(
            "BLOGGER_CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN 환경변수가 설정되지 않았습니다."
        )
    data = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


# ══════════════════════════════════════════════════════════════════════════════
# 2. Blogger API — 포스트 목록 가져오기
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_posts_for_blog(token: str, blog_id: str, max_results: int = MAX_POSTS) -> list:
    """Blogger API v3 — blog_id를 직접 지정해서 포스트 가져오기 (내부용)"""
    posts = []
    page_token = None

    while len(posts) < max_results:
        fetch = min(max_results - len(posts), 500)
        params = {
            "maxResults": fetch,
            "status": "LIVE",
            "fetchBodies": "false",
            "fields": "items(id,title,url,published,labels),nextPageToken",
        }
        if page_token:
            params["pageToken"] = page_token

        qs = urllib.parse.urlencode(params)
        url = f"https://blogger.googleapis.com/v3/blogs/{blog_id}/posts?{qs}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw)

        items = data.get("items", [])
        for item in items:
            posts.append({
                "id":        item.get("id", ""),
                "title":     item.get("title", ""),
                "url":       item.get("url", ""),
                "published": item.get("published", ""),
                "labels":    item.get("labels", []),
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return posts


def fetch_posts(token: str, max_results: int = MAX_POSTS) -> list:
    """Blogger API v3 — 최근 포스트 최대 max_results개 가져오기 (환경변수 BLOG_ID 사용)
    
    반환: [{"id", "title", "url", "published", "labels"}, ...]
    """
    return _fetch_posts_for_blog(token, BLOG_ID, max_results)





# ══════════════════════════════════════════════════════════════════════════════
# 3. 유사도 계산
# ══════════════════════════════════════════════════════════════════════════════

# 한국어 불용어 (너무 흔해서 유사도에 영향 없는 단어)
STOP_WORDS = {
    "의", "이", "가", "을", "를", "에", "서", "에서", "으로", "로", "와", "과",
    "은", "는", "도", "만", "에게", "한", "하는", "하여", "하고", "하지",
    "이다", "있다", "없다", "그", "이", "저", "것", "수", "때", "및", "또",
    "방법", "방식", "가이드", "완벽", "완전", "총정리", "정리", "정보",
    "2024", "2025", "2026", "최신", "최고", "추천",
}


def tokenize(text: str) -> set:
    """제목/키워드 → 의미있는 토큰 집합"""
    # 영문 단어, 한글 2자 이상 단어 추출
    tokens = set()

    # 영문: 대소문자 무시
    for w in re.findall(r'[a-zA-Z]{2,}', text):
        tokens.add(w.lower())

    # 한글: 2자 이상
    for w in re.findall(r'[가-힣]{2,}', text):
        if w not in STOP_WORDS:
            tokens.add(w)

    return tokens


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """자카드 유사도 — |A∩B| / |A∪B|"""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def label_overlap(labels_a: list, labels_b: list) -> float:
    """라벨 일치 비율 (0.0 ~ 1.0)"""
    if not labels_a or not labels_b:
        return 0.0
    set_a = {l.strip().lower() for l in labels_a}
    set_b = {l.strip().lower() for l in labels_b}
    intersection = len(set_a & set_b)
    return intersection / max(len(set_a), 1)


def recency_weight(published_iso: str) -> float:
    """최신성 가중치 — 최근 30일: 1.0, 90일: 0.7, 그 이상: 0.4"""
    if not published_iso:
        return 0.5
    try:
        dt = datetime.datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        days = (now - dt).days
        if days <= 30:
            return 1.0
        elif days <= 90:
            return 0.7
        elif days <= 180:
            return 0.55
        else:
            return 0.4
    except Exception:
        return 0.5


def score_post(target_tokens: set, target_labels: list, candidate: dict) -> float:
    """후보 포스트 종합 점수 계산

    가중치:
      - 자카드 유사도: 60%
      - 라벨 일치:     25%
      - 최신성:        15%
    """
    cand_tokens = tokenize(candidate["title"])
    j_sim = jaccard_similarity(target_tokens, cand_tokens)
    l_sim = label_overlap(target_labels, candidate["labels"])
    r_wt  = recency_weight(candidate["published"])

    return 0.60 * j_sim + 0.25 * l_sim + 0.15 * r_wt


def find_related_posts(
    current_title: str,
    current_labels: list,
    current_url: str,
    all_posts: list,
    n: int = MAX_RELATED,
) -> list:
    """관련 포스트 상위 n개 선택"""
    target_tokens = tokenize(current_title)

    scored = []
    for post in all_posts:
        # 자기 자신 제외
        if post["url"] == current_url:
            continue
        s = score_post(target_tokens, current_labels, post)
        if s > 0.05:   # 너무 낮은 관련성은 제외
            scored.append((s, post))

    # 점수 내림차순 정렬
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:n]]


# ══════════════════════════════════════════════════════════════════════════════
# 4. CTA "관련 글" 카드 섹션 HTML 생성
# ══════════════════════════════════════════════════════════════════════════════

def make_card_description(title: str, labels: list) -> str:
    """카드 한줄 설명 — 제목 기반 자연어 생성 (CTA 최적화)"""
    import hashlib, re as _re

    # 제목에서 핵심 키워드 추출
    # 이모지 제거
    clean = _re.sub(r'[^\w\s가-힣]', ' ', title).strip()
    tokens = [t for t in clean.split() if len(t) >= 2][:4]
    keyword = " ".join(tokens[:2]) if tokens else ""

    # 제목 패턴별 CTA 문구 (다양성 확보)
    cta_templates = [
        lambda k: f"{k} 핵심만 빠르게 — 3분이면 충분합니다.",
        lambda k: f"이 글과 함께 읽으면 이해가 두 배로 깊어집니다.",
        lambda k: f"{k} 놓치면 아쉬운 내용, 지금 바로 확인하세요.",
        lambda k: f"관련 트렌드와 실전 팁을 한 번에 정리했습니다.",
        lambda k: f"{k} 완전 정복 — 실제 사례와 함께 설명합니다.",
    ]

    # 제목 해시로 템플릿 선택 (같은 제목은 항상 같은 문구)
    idx = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(cta_templates)
    return cta_templates[idx](keyword)


def build_related_section(related_posts: list) -> str:
    """카드형 CTA 관련 글 섹션 HTML 생성 v2

    디자인 개선:
      - 상단 진한 구분선 + 배경색으로 본문과 명확히 분리
      - 섹션 헤더: 아이콘 + "함께 읽으면 좋은 글" 텍스트
      - 카드: 좌측 강조 바 + 제목 + 설명 + 화살표
      - target="_blank" 제거 (애드센스 CTR 최적화)
      - 모바일 최적화 (1열 그리드)
    """
    if not related_posts:
        return ""

    cards_html = ""
    for post in related_posts:
        title = post["title"].replace('"', "&quot;").replace("'", "&#39;")
        url   = post["url"]
        desc  = make_card_description(post["title"], post["labels"])
        desc  = desc.replace('"', "&quot;")

        cards_html += f"""
  <a href="{url}" class="il-card" rel="noopener" title="{title}">
    <div class="il-card-inner">
      <div class="il-card-accent"></div>
      <div class="il-card-body">
        <p class="il-card-title">{title}</p>
        <p class="il-card-desc">{desc}</p>
      </div>
      <span class="il-arrow" aria-hidden="true">&#8594;</span>
    </div>
  </a>"""

    section = f"""
<!-- 내부링크: 관련 글 카드 섹션 (internal_links.py 자동 생성) -->
<div class="il-related-section" style="margin:2.5em 0 2.5em;border:2px solid {THEME_COLOR};border-radius:16px;overflow:hidden;box-shadow:0 4px 18px rgba(67,97,238,0.10);">
  <div class="il-related-header" style="background:{THEME_COLOR};padding:14px 20px;display:flex;align-items:center;gap:10px;">
    <span style="font-size:1.3em;">📚</span>
    <span style="font-size:1em;font-weight:800;color:#fff;letter-spacing:-0.3px;">함께 읽으면 좋은 글</span>
  </div>
  <div class="il-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:0;background:#f4f6ff;padding:16px;gap:12px;">
    {cards_html}
  </div>
</div>
<style>
  .il-card {{
    display:block;text-decoration:none;color:inherit;
    background:#fff;border:1.5px solid #dde4ff;border-radius:12px;
    transition:box-shadow 0.18s,border-color 0.18s,transform 0.15s;overflow:hidden;
  }}
  .il-card:hover {{
    box-shadow:0 6px 20px rgba(79,110,247,0.18);border-color:{THEME_COLOR};
    transform:translateY(-3px);text-decoration:none;
  }}
  .il-card-inner {{display:flex;align-items:stretch;gap:0;}}
  .il-card-accent {{width:5px;flex-shrink:0;background:{THEME_COLOR};transition:background 0.15s;}}
  .il-card:hover .il-card-accent {{background:#2a4fff;}}
  .il-card-body {{flex:1;min-width:0;padding:13px 14px;}}
  .il-card-title {{
    font-size:0.9em;font-weight:700;color:#1a237e;margin:0 0 5px;line-height:1.45;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  }}
  .il-card-desc {{
    font-size:0.76em;color:#777;margin:0;line-height:1.5;
    display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;
  }}
  .il-arrow {{
    font-size:1.1em;color:{THEME_COLOR};flex-shrink:0;font-weight:700;
    padding:13px 12px 13px 0;transition:transform 0.15s;align-self:center;
  }}
  .il-card:hover .il-arrow {{transform:translateX(4px);}}
  @media(max-width:500px) {{
    .il-related-section {{margin:2em 0!important;}}
    .il-grid {{grid-template-columns:1fr!important;}}
    .il-card-title {{font-size:0.86em;}}
  }}
</style>
<!-- /내부링크 -->
"""
    return section


# ══════════════════════════════════════════════════════════════════════════════
# 5. 본문 내 앵커링크 삽입 (키워드 매칭)
# ══════════════════════════════════════════════════════════════════════════════

def build_protected_ranges(html: str) -> list:
    """앵커링크 삽입 불가 구간 목록 반환
    
    보호 대상:
      - 모든 HTML 태그 (<tag ...>)
      - <a>...</a> 전체 블록 (이미 링크된 곳)
      - <h1>~<h6> 전체 블록 (제목에 링크 금지)
      - <script>, <style>, <ins> 전체 블록
    """
    ranges = []
    # 블록 태그 전체 (a, h1-h6, script, style, ins, figure)
    for m in re.finditer(
        r'<(a|h[1-6]|script|style|ins|figure)\b[^>]*>.*?</\1>',
        html, re.S | re.I
    ):
        ranges.append((m.start(), m.end()))
    # 단일 태그 (<img>, <br>, 등)
    for m in re.finditer(r'<[^>]+>', html):
        ranges.append((m.start(), m.end()))
    return ranges


def inject_anchor_links(html: str, related_posts: list, max_anchors: int = 2) -> str:
    """본문 내 자연스러운 앵커링크 삽입 (최대 max_anchors개)
    
    전략:
      - 각 관련 포스트 제목의 핵심 키워드를 <p> 본문에서만 탐색
      - h1~h6, <a>, <script>, <ins> 안은 절대 건드리지 않음
      - 첫 번째 등장하는 텍스트에만 링크 삽입 (포스트당 1회)
    """
    inserted = 0

    for post in related_posts:
        if inserted >= max_anchors:
            break

        # 핵심 키워드 추출 (가장 긴 토큰 우선)
        tokens = sorted(tokenize(post["title"]), key=len, reverse=True)
        keyword = None
        for tok in tokens:
            if len(tok) >= 3:
                keyword = tok
                break

        if not keyword:
            continue

        post_url   = post["url"]
        post_title = post["title"].replace('"', "&quot;")

        # 보호 구간 수집 (매 반복마다 갱신 — 이전 삽입으로 위치가 바뀌므로)
        protected_ranges = build_protected_ranges(html)

        def is_in_protected(start: int, end: int) -> bool:
            for ps, pe in protected_ranges:
                if ps <= start < pe or ps < end <= pe:
                    return True
            return False

        # 키워드 패턴
        if re.search(r'[가-힣]', keyword):
            pattern = re.compile(re.escape(keyword))
        else:
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)

        # <p>...</p> 블록 내에서만 탐색
        found = False
        for p_match in re.finditer(r'<p[^>]*>(.*?)</p>', html, re.S | re.I):
            p_start = p_match.start(1)  # <p> 내용 시작
            inner = p_match.group(1)

            kw_match = pattern.search(inner)
            if not kw_match:
                continue

            # 절대 위치 계산
            abs_start = p_start + kw_match.start()
            abs_end   = p_start + kw_match.end()

            if is_in_protected(abs_start, abs_end):
                continue

            # 앵커 삽입
            original_text = html[abs_start:abs_end]
            anchor = (
                f'<a href="{post_url}" '
                f'rel="noopener" '
                f'title="{post_title}" '
                f'style="color:{THEME_COLOR};text-decoration:underline;text-decoration-style:dotted;">'
                f'{original_text}</a>'
            )
            html = html[:abs_start] + anchor + html[abs_end:]
            inserted += 1
            found = True
            break  # 이 포스트는 1회만 삽입

        # <p> 안에서 못 찾으면 건너뜀
        _ = found  # suppress lint

    return html


# ══════════════════════════════════════════════════════════════════════════════
# 6. 관련 글 섹션 삽입 위치 결정 (FAQ 이전, 본문 끝)
# ══════════════════════════════════════════════════════════════════════════════

def find_insert_position(html: str) -> int:
    """관련 글 섹션 삽입 위치 결정 v3

    목표: 본문 읽기 흐름 중간 — 독자가 충분히 읽은 후 자연스럽게 노출
    → 본문 중간 h2 직후에 삽입 (읽다가 자연스럽게 연관글 발견)
    → AdSense 광고와 혼동 없도록 광고 블록과 충분히 거리 둠

    우선순위:
      1. 본문 전체 h2 중 60~70% 위치의 h2 직전 (본문 중간 적절한 위치)
      2. FAQ/마치며 h2 직전 (글 마무리 직전)
      3. 두 번째 AdSense 광고 블록 직전 (광고 사이)
      4. HTML 끝 직전
    """
    # 전체 h2 목록 수집 (본문 40% 이후에 있는 h2만 유효 — quickbar/카드 영역 제외)
    all_h2 = list(re.finditer(r'<h2[^>]*>', html, re.I))
    cutoff = int(len(html) * 0.35)
    h2_matches = [m for m in all_h2 if m.start() >= cutoff]

    # 1. 본문 h2 중 60~70% 위치 선택 (가장 자연스러운 중간 위치)
    if len(h2_matches) >= 2:
        # 전체 HTML 기준 60~65% 지점에 가장 가까운 h2 선택
        target_pos = int(len(html) * 0.62)
        closest = min(h2_matches, key=lambda m: abs(m.start() - target_pos))
        h2_end = html.find('</h2>', closest.start())
        if h2_end != -1:
            return h2_end + len('</h2>')

    # h2가 부족하면 HTML 전체 길이 60% 지점으로 강제 삽입
    if not h2_matches and all_h2:
        # 어떤 h2든 있으면 60% 지점
        target_pos = int(len(html) * 0.60)
        pos_in_text = html.find('<p', target_pos)
        if pos_in_text != -1:
            return pos_in_text

    # 2. FAQ/마치며 h2 직전
    faq_match = re.search(
        r'<h2[^>]*>[^<]*(?:자주\s*묻|FAQ|Q&amp;A|자주하는|마치며|정리하며)[^<]*</h2>',
        html, re.I | re.S
    )
    if faq_match:
        return faq_match.start()

    # 3. 두 번째 AdSense 블록 직전
    ad_matches = list(re.finditer(r'<ins\s[^>]*class="adsbygoogle"', html, re.I))
    if len(ad_matches) >= 2:
        second_ad = ad_matches[1]
        pre_ad = html[:second_ad.start()].rfind('<div style="margin:')
        if pre_ad != -1:
            return pre_ad
        return second_ad.start()

    # 4. 첫 번째 AdSense 직전
    if ad_matches:
        pre_ad = html[:ad_matches[0].start()].rfind('<div style="margin:')
        if pre_ad != -1:
            return pre_ad
        return ad_matches[0].start()

    # 5. HTML 끝 직전
    pos = html.rfind('</div>')
    return pos if pos != -1 else len(html)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 메인 통합 함수
# ══════════════════════════════════════════════════════════════════════════════

def add_internal_links(
    html: str,
    current_title: str,
    current_labels: list,
    current_url: str = "",
    token: str = "",
    cached_posts: list = None,
    verbose: bool = False,
    blog_id: str = "",
    blog_url: str = "",
) -> tuple:
    """포스트 HTML에 내부링크 자동 삽입 (메인 진입점)

    Args:
        html:           포스트 HTML 본문
        current_title:  현재 포스트 제목
        current_labels: 현재 포스트 라벨 목록
        current_url:    현재 포스트 URL (중복 제외용)
        token:          Blogger API access token (없으면 자동 획득)
        cached_posts:   외부에서 캐시된 포스트 목록 (반복 호출 최적화)
        verbose:        디버그 출력 여부
        blog_id:        대상 블로그 ID (명시적 지정 — 환경변수 우선)
        blog_url:       대상 블로그 URL (명시적 지정 — 환경변수 우선)

    Returns:
        (modified_html, related_posts_list)
    """
    # ── 블로그 ID/URL 동적 오버라이드 (모듈 상수 우회) ──
    # 모듈 임포트 시점에 BLOG_ID가 고정되는 문제 해결
    # blog_id 파라미터가 있으면 fetch_posts에서 직접 사용
    effective_blog_id = blog_id or BLOG_ID

    # ── 토큰 획득 ──
    if not token:
        try:
            token = get_access_token()
        except Exception as e:
            if verbose:
                print(f"[internal_links] 토큰 획득 실패 (스킵): {e}")
            return html, []

    # ── 포스트 목록 ──
    if cached_posts is None:
        try:
            all_posts = _fetch_posts_for_blog(token, effective_blog_id, MAX_POSTS)
            if verbose:
                print(f"[internal_links] 포스트 {len(all_posts)}개 로드 (blog: {effective_blog_id})")
        except Exception as e:
            if verbose:
                print(f"[internal_links] 포스트 목록 로드 실패 (스킵): {e}")
            return html, []
    else:
        all_posts = cached_posts

    # ── 관련 포스트 선택 ──
    related = find_related_posts(current_title, current_labels, current_url, all_posts)

    if not related:
        if verbose:
            print("[internal_links] 관련 포스트 없음 — 삽입 스킵")
        return html, []

    if verbose:
        print(f"[internal_links] 관련 포스트 {len(related)}개 선택:")
        for p in related:
            print(f"  - {p['title'][:60]}")

    # ── 앵커링크 삽입 (본문 내, 먼저 처리) ──
    html = inject_anchor_links(html, related, max_anchors=2)

    # ── 관련 글 카드 섹션 삽입 ──
    section_html = build_related_section(related)
    insert_pos   = find_insert_position(html)
    html = html[:insert_pos] + section_html + html[insert_pos:]

    return html, related


# ══════════════════════════════════════════════════════════════════════════════
# 8. update_existing_posts.py 소급 적용용 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def apply_to_existing_post(html: str, post_title: str, post_labels: list,
                            post_url: str, token: str,
                            cached_posts: list = None) -> tuple:
    """기존 포스트 HTML에 내부링크 소급 삽입
    
    이미 삽입된 경우 중복 방지:
      - il-related-section 마커가 있으면 스킵
    
    Returns:
        (new_html, changed: bool)
    """
    if "il-related-section" in html:
        return html, False  # 이미 삽입됨

    new_html, related = add_internal_links(
        html, post_title, post_labels, post_url,
        token=token, cached_posts=cached_posts, verbose=False
    )
    changed = new_html != html
    return new_html, changed


# ══════════════════════════════════════════════════════════════════════════════
# 9. 단독 실행 테스트
# ══════════════════════════════════════════════════════════════════════════════

def _cli_test():
    """단독 실행 시 동작 테스트
    
    사용법:
        python3 scripts/internal_links.py
        python3 scripts/internal_links.py "AI 챗봇 만들기"
        python3 scripts/internal_links.py "AI 챗봇 만들기" "AI,ChatGPT"
    """
    print("=" * 60)
    print(f"🔗 내부링크 시스템 테스트")
    print(f"   BLOG_ID  : {BLOG_ID}")
    print(f"   BLOG_URL : {BLOG_URL}")
    print(f"   BLOG_NAME: {BLOG_NAME}")
    print("=" * 60)

    # 제목/라벨 파라미터
    test_title  = sys.argv[1] if len(sys.argv) > 1 else "AI 챗봇 제작 가이드"
    test_labels_raw = sys.argv[2] if len(sys.argv) > 2 else "AI,ChatGPT,자동화"
    test_labels = [l.strip() for l in test_labels_raw.split(",") if l.strip()]

    print(f"\n📋 테스트 포스트: {test_title}")
    print(f"   라벨: {test_labels}")

    # 토큰 획득
    print("\n🔑 토큰 획득 중...")
    try:
        token = get_access_token()
        print("   ✅ 토큰 획득 성공")
    except Exception as e:
        print(f"   ❌ 실패: {e}")
        print("   → 환경변수 확인: BLOGGER_REFRESH_TOKEN, BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET")
        sys.exit(1)

    # 포스트 목록 로드
    print(f"\n📥 포스트 목록 로드 중 (최대 {MAX_POSTS}개)...")
    try:
        all_posts = fetch_posts(token, MAX_POSTS)
        print(f"   ✅ {len(all_posts)}개 로드 완료")
    except Exception as e:
        print(f"   ❌ 실패: {e}")
        sys.exit(1)

    # 관련 포스트 선택
    print(f"\n🔍 관련 포스트 분석 중...")
    related = find_related_posts(test_title, test_labels, "", all_posts)

    if not related:
        print("   ⚠️  관련 포스트 없음 — 유사도 임계값 미달")
    else:
        print(f"   ✅ {len(related)}개 선택:\n")
        for i, p in enumerate(related, 1):
            t_tokens = tokenize(test_title)
            c_tokens = tokenize(p["title"])
            j_sim = jaccard_similarity(t_tokens, c_tokens)
            l_sim = label_overlap(test_labels, p["labels"])
            r_wt  = recency_weight(p["published"])
            total = score_post(t_tokens, test_labels, p)
            print(f"   [{i}] {p['title'][:55]}")
            print(f"        URL: {p['url']}")
            print(f"        점수: {total:.3f} (자카드={j_sim:.2f}, 라벨={l_sim:.2f}, 최신성={r_wt:.2f})")
            print()

    # 샘플 HTML에 삽입 테스트
    print("🧪 샘플 HTML 삽입 테스트...")
    sample_html = f"""
<div class="ak-post">
<p>이 글에서는 <strong>AI 챗봇</strong>을 직접 만드는 방법을 설명합니다.</p>
<h2>ChatGPT API 연동</h2>
<p>ChatGPT API를 활용하면 간단한 챗봇을 빠르게 구축할 수 있습니다.</p>
<h2>자동화 파이프라인 구성</h2>
<p>자동화를 위한 파이프라인을 구성해 봅시다.</p>
<h2>자주 묻는 질문</h2>
<p><strong>Q. API 키는 어디서 발급받나요?</strong></p>
<p>A. OpenAI 공식 사이트에서 발급받을 수 있습니다.</p>
</div>
"""
    modified_html, inserted_related = add_internal_links(
        sample_html,
        test_title,
        test_labels,
        current_url="",
        token=token,
        cached_posts=all_posts,
        verbose=True,
    )

    if inserted_related:
        print(f"\n   ✅ 삽입 완료!")
        print(f"   삽입된 관련글 {len(inserted_related)}개:")
        for p in inserted_related:
            print(f"    - {p['title'][:55]}")
        print(f"\n   삽입 결과 HTML 크기: {len(sample_html):,} → {len(modified_html):,} 바이트")
        print(f"\n--- 삽입 HTML 미리보기 (앞 2000자) ---")
        print(modified_html[:2000])
    else:
        print("   ⚠️  삽입할 내용 없음")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")


if __name__ == "__main__":
    _cli_test()
