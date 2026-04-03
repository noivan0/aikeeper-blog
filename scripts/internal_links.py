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

def fetch_posts(token: str, max_results: int = MAX_POSTS) -> list:
    """Blogger API v3 — 최근 포스트 최대 max_results개 가져오기
    
    반환: [{"id", "title", "url", "published", "labels"}, ...]
    """
    posts = []
    page_token = None

    while len(posts) < max_results:
        fetch = min(max_results - len(posts), 500)
        params = {
            "maxResults": fetch,
            "status": "LIVE",
            "fetchBodies": "false",   # 본문 불필요 — 속도 절감
            "fields": "items(id,title,url,published,labels),nextPageToken",
        }
        if page_token:
            params["pageToken"] = page_token

        qs = urllib.parse.urlencode(params)
        url = f"https://blogger.googleapis.com/v3/blogs/{BLOG_ID}/posts?{qs}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw)

        for item in data.get("items", []):
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
    """카드 한줄 설명 — 라벨 기반 자동 생성"""
    if labels:
        label_str = ", ".join(labels[:2])
        return f"{label_str} 관련 심층 분석 — 지금 바로 확인하세요."
    # 제목에서 핵심어 추출
    tokens = list(tokenize(title))
    if tokens:
        return f"{tokens[0]} 완벽 정리 — 실전 활용법까지 한 번에."
    return "관련 내용을 더 깊게 알아보세요."


def build_related_section(related_posts: list) -> str:
    """카드형 CTA 관련 글 섹션 HTML 생성
    
    디자인:
      - 카드형 레이아웃 (CSS Grid, 모바일 최적화)
      - 제목 + 한줄 설명 + 화살표 아이콘
      - "이 글도 읽어보세요 →" 헤더
      - 색상: #4f6ef7 계열
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
      <div class="il-card-body">
        <p class="il-card-title">{title}</p>
        <p class="il-card-desc">{desc}</p>
      </div>
      <span class="il-arrow" aria-hidden="true">→</span>
    </div>
  </a>"""

    section = f"""
<!-- 내부링크: 관련 글 카드 섹션 (internal_links.py 자동 생성) -->
<div class="il-related-section">
  <style>
    .il-related-section {{
      margin: 3em 0 2em;
      padding: 0;
    }}
    .il-related-header {{
      font-size: 1.05em;
      font-weight: 700;
      color: #0d1b4b;
      margin: 0 0 1.1em;
      padding-bottom: 0.5em;
      border-bottom: 2px solid #e8ecf4;
      position: relative;
    }}
    .il-related-header::after {{
      content: '';
      position: absolute;
      bottom: -2px;
      left: 0;
      width: 80px;
      height: 2px;
      background: {THEME_COLOR};
    }}
    .il-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }}
    .il-card {{
      display: block;
      text-decoration: none;
      color: inherit;
      background: #f8f9ff;
      border: 1px solid #e0e6ff;
      border-radius: 12px;
      transition: box-shadow 0.18s, border-color 0.18s, transform 0.15s;
    }}
    .il-card:hover {{
      box-shadow: 0 4px 18px rgba(79,110,247,0.15);
      border-color: {THEME_COLOR};
      transform: translateY(-2px);
      text-decoration: none;
    }}
    .il-card-inner {{
      display: flex;
      align-items: center;
      padding: 14px 16px;
      gap: 10px;
    }}
    .il-card-body {{
      flex: 1;
      min-width: 0;
    }}
    .il-card-title {{
      font-size: 0.93em;
      font-weight: 600;
      color: #1a237e;
      margin: 0 0 5px;
      line-height: 1.45;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .il-card-desc {{
      font-size: 0.78em;
      color: #666;
      margin: 0;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .il-arrow {{
      font-size: 1.2em;
      color: {THEME_COLOR};
      flex-shrink: 0;
      font-weight: 700;
      transition: transform 0.15s;
    }}
    .il-card:hover .il-arrow {{
      transform: translateX(4px);
    }}
    @media (max-width: 500px) {{
      .il-grid {{
        grid-template-columns: 1fr;
        gap: 10px;
      }}
      .il-card-title {{
        font-size: 0.88em;
      }}
    }}
  </style>
  <p class="il-related-header">📚 이 글도 읽어보세요</p>
  <div class="il-grid">{cards_html}
  </div>
</div>
<!-- /내부링크 -->
"""
    return section


# ══════════════════════════════════════════════════════════════════════════════
# 5. 본문 내 앵커링크 삽입 (키워드 매칭)
# ══════════════════════════════════════════════════════════════════════════════

def inject_anchor_links(html: str, related_posts: list, max_anchors: int = 2) -> str:
    """본문 내 자연스러운 앵커링크 삽입 (최대 max_anchors개)
    
    전략:
      - 각 관련 포스트 제목의 핵심 키워드를 본문에서 탐색
      - 이미 링크가 걸린 텍스트는 건드리지 않음
      - h태그, 광고 블록, script 태그 안은 건드리지 않음
      - 첫 번째 등장하는 텍스트에만 링크 삽입 (포스트당 1회)
    """
    inserted = 0

    for post in related_posts:
        if inserted >= max_anchors:
            break

        # 핵심 키워드 추출 (길이 3자 이상 영문 또는 2자 이상 한글)
        tokens = sorted(tokenize(post["title"]), key=len, reverse=True)
        # 가장 긴 의미있는 키워드를 대상으로
        keyword = None
        for tok in tokens:
            if len(tok) >= 3:  # 영문 3자 이상 or 한글 2자 이상은 tokenize에서 보장
                keyword = tok
                break

        if not keyword:
            continue

        post_url   = post["url"]
        post_title = post["title"].replace('"', "&quot;")

        # 본문에서 키워드 검색 (대소문자 무시)
        # HTML 태그 내부, <a> 태그 안, 광고/스크립트 블록 제외
        # 단순 regex: 태그 밖의 텍스트에서만 치환

        # 먼저 html에서 "보호 구간" 수집 (태그 전체, <a>...</a>)
        protected = set()
        for m in re.finditer(r'<[^>]+>|<a\b[^>]*>.*?</a>', html, re.S | re.I):
            protected.add((m.start(), m.end()))

        def is_in_protected(start, end):
            for ps, pe in protected:
                if ps <= start < pe or ps < end <= pe:
                    return True
            return False

        # 키워드 패턴 (단어 경계: 한글은 경계 없음, 영문은 \b)
        if re.search(r'[가-힣]', keyword):
            pattern = re.compile(re.escape(keyword))
        else:
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)

        match = pattern.search(html)
        if not match:
            continue

        ms, me = match.start(), match.end()

        # 보호 구간 내부이면 건너뜀
        if is_in_protected(ms, me):
            # 다음 등장 탐색
            search_start = me
            found = False
            while True:
                match2 = pattern.search(html, search_start)
                if not match2:
                    break
                ms2, me2 = match2.start(), match2.end()
                if not is_in_protected(ms2, me2):
                    ms, me, found = ms2, me2, True
                    break
                search_start = me2
            if not found:
                continue

        # 앵커 링크로 교체 (CTA 스타일)
        original_text = html[ms:me]
        anchor = (
            f'<a href="{post_url}" '
            f'rel="noopener" '
            f'title="{post_title}" '
            f'style="color:{THEME_COLOR};text-decoration:underline;text-decoration-style:dotted;">'
            f'{original_text}</a>'
        )
        html = html[:ms] + anchor + html[me:]
        inserted += 1

    return html


# ══════════════════════════════════════════════════════════════════════════════
# 6. 관련 글 섹션 삽입 위치 결정 (FAQ 이전, 본문 끝)
# ══════════════════════════════════════════════════════════════════════════════

def find_insert_position(html: str) -> int:
    """관련 글 섹션 삽입 위치 결정
    
    우선순위:
      1. FAQ 섹션 (<h2>자주 묻는 질문 / FAQ) 바로 직전
      2. 마지막 광고 블록 직전
      3. </div> 마지막 직전 (ak-post 래퍼)
      4. HTML 끝
    """
    # 1. FAQ 섹션 탐색
    faq_match = re.search(
        r'<h2[^>]*>[^<]*(?:자주\s*묻|FAQ|Q&amp;A|자주하는)[^<]*</h2>',
        html, re.I | re.S
    )
    if faq_match:
        return faq_match.start()

    # 2. 마지막 AdSense ins 블록 직전
    ad_matches = list(re.finditer(r'<div[^>]*class="adsbygoogle"', html, re.I))
    if ad_matches:
        # 마지막 광고 블록의 부모 <div> 찾기 (il-ad-wrap 또는 margin:2.5em)
        last_ad = ad_matches[-1]
        # 광고 div 전체 블록 찾기 (앞 <div style="margin:...)
        pre_ad = html[:last_ad.start()].rfind('<div style="margin:')
        if pre_ad != -1:
            return pre_ad

    # 3. ak-post 닫는 태그 직전
    ak_close = html.rfind('</div>')
    if ak_close != -1:
        return ak_close

    return len(html)


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

    Returns:
        (modified_html, related_posts_list)
    """
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
            all_posts = fetch_posts(token, MAX_POSTS)
            if verbose:
                print(f"[internal_links] 포스트 {len(all_posts)}개 로드")
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
