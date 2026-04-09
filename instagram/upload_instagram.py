"""
Instagram 캐러셀 자동 업로드 v1
=========================================
흐름:
  1. 슬라이드 이미지 → GitHub Pages (공개 URL) 또는 임시 HTTP 서버로 호스팅
  2. 각 이미지 media_id 생성 (POST /media)
  3. 캐러셀 컨테이너 생성
  4. 게시 (POST /media_publish)

의존:
  - INSTAGRAM_ACCOUNT_ID
  - INSTAGRAM_PAGE_TOKEN  (60일 유효 — 갱신 필요 시 refresh_token() 호출)
  - 슬라이드 이미지 공개 URL 목록

사용법:
  python3 upload_instagram.py \
    --slides_dir /tmp/carousel_gg_v7/ \
    --caption "캡션 텍스트"
"""

import os, sys, json, time, argparse, subprocess, threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request, urllib.parse

# ── 환경 변수 로드 ─────────────────────────────────────
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

ACCOUNT_ID  = os.environ.get("INSTAGRAM_ACCOUNT_ID", "17841473576603862")
PAGE_TOKEN  = os.environ.get("INSTAGRAM_PAGE_TOKEN", "")
API_BASE    = "https://graph.facebook.com/v19.0"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 토큰 갱신 (60일마다 필요)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def refresh_long_token():
    app_id     = os.environ.get("INSTAGRAM_APP_ID", "")
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET", "")
    long_token = os.environ.get("INSTAGRAM_LONG_TOKEN", "")
    if not all([app_id, app_secret, long_token]):
        print("[instagram] 토큰 갱신 스킵 (환경변수 없음)")
        return PAGE_TOKEN

    url = f"{API_BASE}/oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={long_token}"
    try:
        resp = urllib.request.urlopen(url, timeout=10).read()
        data = json.loads(resp)
        new_token = data.get("access_token", "")
        if new_token:
            print(f"[instagram] 토큰 갱신 완료 (expires_in: {data.get('expires_in',0)//86400}일)")
            # .env 업데이트
            env_path = Path(__file__).parent.parent / ".env"
            text = env_path.read_text()
            text = "\n".join(
                f"INSTAGRAM_LONG_TOKEN={new_token}" if l.startswith("INSTAGRAM_LONG_TOKEN=") else l
                for l in text.splitlines()
            )
            env_path.write_text(text)
            return new_token
    except Exception as e:
        print(f"[instagram] 토큰 갱신 실패: {e}")
    return PAGE_TOKEN


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이미지 호스팅 — 임시 HTTP 서버 (로컬 실행용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_server = None
_server_dir = None

def start_image_server(slides_dir: Path, port: int = 18888):
    """슬라이드 디렉토리를 임시 HTTP 서버로 노출"""
    global _server, _server_dir
    _server_dir = slides_dir

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(slides_dir), **kwargs)
        def log_message(self, format, *args): pass  # 로그 억제

    _server = HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    print(f"[instagram] 이미지 서버 시작: port {port}")
    return port

def stop_image_server():
    global _server
    if _server:
        _server.shutdown()
        print("[instagram] 이미지 서버 종료")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GitHub Pages 업로드 (공개 URL 방식 — 권장)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def upload_to_github_pages(slides: list, timestamp: str) -> list:
    """
    슬라이드를 GitHub 레포의 carousel/ 폴더에 커밋해서 공개 URL 생성
    GitHub Pages가 활성화된 레포 필요
    """
    import base64

    gh_token = os.environ.get("GITHUB_PAT", "")
    repo     = "noivan0/aikeeper-blog"   # GitHub Pages 레포
    branch   = "gh-pages"               # GitHub Pages 브랜치
    base_url = "https://noivan0.github.io/aikeeper-blog"

    if not gh_token:
        print("[instagram] GITHUB_PAT 없음 — GitHub Pages 스킵")
        return []

    urls = []
    for slide_path in slides:
        fname = slide_path.name
        remote_path = f"carousel/{timestamp}/{fname}"
        content = base64.b64encode(slide_path.read_bytes()).decode()

        api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
        payload = json.dumps({
            "message": f"carousel: {timestamp}/{fname}",
            "content": content,
            "branch": branch
        }).encode()

        req = urllib.request.Request(
            api_url, data=payload, method="PUT",
            headers={
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
            }
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            public_url = f"{base_url}/{remote_path}"
            urls.append(public_url)
            print(f"[instagram] 업로드: {fname} → {public_url}")
        except Exception as e:
            print(f"[instagram] GitHub 업로드 실패 {fname}: {e}")
            urls.append(None)

    return urls


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Instagram API 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def ig_post(endpoint: str, data: dict, token: str) -> dict:
    data["access_token"] = token
    url = f"{API_BASE}/{endpoint}"
    # urlencode로 인코딩 (이미지 URL 등 특수문자 안전 처리)
    payload = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=payload)
    try:
        resp = urllib.request.urlopen(req, timeout=30).read()
        return json.loads(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[instagram] API 오류 {e.code}: {body}")
        return json.loads(body) if body else {"error": str(e)}

def ig_get(endpoint: str, params: dict, token: str) -> dict:
    params["access_token"] = token
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}/{endpoint}?{qs}"
    try:
        resp = urllib.request.urlopen(url, timeout=15).read()
        return json.loads(resp)
    except Exception as e:
        return {"error": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 캐러셀 업로드 메인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def upload_carousel(
    image_urls: list,
    caption: str,
    token: str = None,
    account_id: str = None,
) -> dict:
    """
    Instagram 캐러셀 업로드

    Args:
        image_urls: 공개 접근 가능한 이미지 URL 목록 (최대 10개)
        caption: 게시물 캡션
        token: PAGE_TOKEN (없으면 환경변수에서)
        account_id: Instagram 계정 ID (없으면 환경변수에서)

    Returns:
        {"success": bool, "post_id": str, "permalink": str}
    """
    token      = token or PAGE_TOKEN
    account_id = account_id or ACCOUNT_ID

    if not token:
        return {"success": False, "error": "PAGE_TOKEN 없음"}

    valid_urls = [u for u in image_urls if u]
    if not valid_urls:
        return {"success": False, "error": "유효한 이미지 URL 없음"}

    print(f"[instagram] 캐러셀 업로드 시작: {len(valid_urls)}장")

    # 1. 각 이미지 media_id 생성
    children_ids = []
    for i, url in enumerate(valid_urls[:10]):
        print(f"[instagram] 이미지 {i+1}/{len(valid_urls)}: {url[:60]}...")
        result = ig_post(
            f"{account_id}/media",
            {"image_url": url, "is_carousel_item": "true"},
            token
        )
        if "id" in result:
            children_ids.append(result["id"])
            print(f"[instagram]   → media_id: {result['id']}")
        else:
            print(f"[instagram]   → 실패: {result}")
        time.sleep(1)

    if not children_ids:
        return {"success": False, "error": "media_id 생성 실패"}

    # 2. 캐러셀 컨테이너 생성
    print(f"[instagram] 캐러셀 컨테이너 생성 ({len(children_ids)}개)")
    container = ig_post(
        f"{account_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
        },
        token
    )
    container_id = container.get("id")
    if not container_id:
        return {"success": False, "error": f"컨테이너 생성 실패: {container}"}
    print(f"[instagram] 컨테이너 ID: {container_id}")

    # 3. 상태 확인 (처리 완료 대기)
    for attempt in range(12):
        time.sleep(5)
        status = ig_get(
            container_id,
            {"fields": "status_code,status"},
            token
        )
        code = status.get("status_code", "")
        print(f"[instagram] 상태 확인 {attempt+1}: {code}")
        if code == "FINISHED":
            break
        elif code in ["ERROR", "EXPIRED"]:
            return {"success": False, "error": f"미디어 처리 실패: {status}"}
    else:
        return {"success": False, "error": "미디어 처리 타임아웃"}

    # 4. 게시
    print("[instagram] 게시 중...")
    publish = ig_post(
        f"{account_id}/media_publish",
        {"creation_id": container_id},
        token
    )
    post_id = publish.get("id")
    if not post_id:
        return {"success": False, "error": f"게시 실패: {publish}"}

    print(f"[instagram] 게시 완료! post_id: {post_id}")

    # 5. 퍼머링크 조회
    info = ig_get(post_id, {"fields": "permalink"}, token)
    permalink = info.get("permalink", "")

    return {
        "success": True,
        "post_id": post_id,
        "permalink": permalink,
        "slides_count": len(children_ids),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 파이프라인 통합 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def publish_carousel_from_dir(
    slides_dir: Path,
    caption: str,
    topic: str = "",
    post_url: str = "",
) -> dict:
    """
    carousel_auto.py 결과 디렉토리를 받아서 Instagram에 게시

    Args:
        slides_dir: 슬라이드 JPG가 있는 디렉토리
        caption: 게시물 캡션
        topic: 포스트 주제 (캡션 자동 생성에 사용)
        post_url: 블로그 포스트 URL

    Returns:
        upload_carousel() 결과
    """
    slides_dir = Path(slides_dir)
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    if not slides:
        return {"success": False, "error": f"슬라이드 없음: {slides_dir}"}

    print(f"[instagram] 슬라이드 {len(slides)}장 발견")

    # 캡션 자동 생성 (없으면)
    if not caption and topic:
        caption = f"{topic}\n\n쿠팡 추천 상품 링크 → 프로필 참고\n\n#쿠팡추천 #가성비 #꿀통몬 #헬스보충제"

    # GitHub Pages에 업로드해서 공개 URL 생성
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_urls = upload_to_github_pages(slides, ts)

    if not any(image_urls):
        return {"success": False, "error": "이미지 공개 URL 생성 실패"}

    # 잠시 대기 (GitHub Pages 반영 시간)
    print("[instagram] GitHub Pages 반영 대기 (180초)...")
    time.sleep(180)

    return upload_carousel(image_urls, caption)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slides_dir", required=True, help="슬라이드 JPG 디렉토리")
    parser.add_argument("--caption",    default="",    help="게시물 캡션")
    parser.add_argument("--topic",      default="",    help="주제 (캡션 자동 생성)")
    parser.add_argument("--post_url",   default="",    help="블로그 포스트 URL")
    parser.add_argument("--dry_run",    action="store_true", help="업로드 없이 URL만 확인")
    args = parser.parse_args()

    slides_dir = Path(args.slides_dir)
    slides = sorted(slides_dir.glob("slide_*.jpg"))
    print(f"슬라이드 {len(slides)}장: {[s.name for s in slides]}")

    if args.dry_run:
        print("\n[dry_run] 실제 업로드 생략")
        sys.exit(0)

    result = publish_carousel_from_dir(
        slides_dir=slides_dir,
        caption=args.caption,
        topic=args.topic,
        post_url=args.post_url,
    )
    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
