#!/usr/bin/env python3
"""
YouTube 커뮤니티 게시글 자동 업로드 스크립트
@ggultongmon (UCRzs2UKVyqHyWbv_oAICdxA) 브랜드 계정

== 사용 방법 ==

1. 브라우저에서 YouTube Studio 로그인 (studio.youtube.com)
2. 꿀통몬 브랜드 계정으로 전환
3. 개발자 도구 > Application > Cookies > youtube.com 에서 아래 쿠키 복사:
   - SID
   - HSID  
   - SSID
   - APISID
   - SAPISID
4. .env 파일에 추가 또는 직접 이 스크립트에 입력
5. python3 upload_youtube_community.py "게시글 내용" [이미지 경로]

== 기술 상세 ==

YouTube Studio는 InnerTube API를 사용:
- 엔드포인트: https://studio.youtube.com/youtubei/v1/backstage/create_post
- 인증: SAPISIDHASH (sha1 기반) + 세션 쿠키
- DELEGATED_SESSION_ID: Studio 페이지 ytcfg에서 추출

== 제약사항 ==

- YouTube Data API v3에 community posts 엔드포인트 없음 (공개 API 미지원)
- OAuth2 Bearer 토큰만으로는 작동 불가 (SAPISID 쿠키 필수)
- 쿠키 만료 시 재추출 필요 (보통 수 주 ~ 수 개월)
- Google 로그인 자동화(Playwright)는 봇 감지로 차단됨

Author: OpenClaw Research - 2026-04-13
"""

import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path

# ============================================================
# 설정
# ============================================================

# .env 파일에서 쿠키 로드
ENV_PATH = Path(__file__).parent.parent / '.env'

def load_env(env_path):
    """Load environment variables from .env file."""
    env = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    env[key.strip()] = value.strip().strip('"').strip("'")
    return env

env = load_env(ENV_PATH)

# YouTube Studio 쿠키 (브라우저에서 추출 필요)
# .env에 YT_SID, YT_HSID, YT_SSID, YT_APISID, YT_SAPISID 로 저장
SID = env.get('YT_SID', '')
HSID = env.get('YT_HSID', '')
SSID = env.get('YT_SSID', '')
APISID = env.get('YT_APISID', '')
SAPISID = env.get('YT_SAPISID', '')
LOGIN_INFO = env.get('YT_LOGIN_INFO', '')

# 채널 정보
CHANNEL_ID = env.get('YT_CHANNEL_ID', 'UCRzs2UKVyqHyWbv_oAICdxA')  # 꿀통몬

# YouTube Studio URL
YT_STUDIO_URL = 'https://studio.youtube.com'

# User Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'


# ============================================================
# SAPISIDHASH 생성
# ============================================================

def generate_sapisidhash(sapisid: str, origin: str = YT_STUDIO_URL) -> str:
    """Generate SAPISIDHASH from SAPISID cookie and origin."""
    timestamp = str(int(time.time()))
    hash_input = f"{timestamp} {sapisid} {origin}"
    sha1_hash = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"{timestamp}_{sha1_hash}"


# ============================================================
# 인증 헤더 생성
# ============================================================

def build_headers(sapisid: str, cookie_str: str) -> dict:
    """Build authentication headers for YouTube Studio API."""
    sapisidhash = generate_sapisidhash(sapisid)
    return {
        'authorization': f'SAPISIDHASH {sapisidhash}',
        'content-type': 'application/json',
        'cookie': cookie_str,
        'x-origin': YT_STUDIO_URL,
        'origin': YT_STUDIO_URL,
        'referer': f'{YT_STUDIO_URL}/channel/{CHANNEL_ID}/community',
        'user-agent': USER_AGENT,
        'x-goog-authuser': '0',
    }


def build_cookie_string() -> str:
    """Build cookie string from environment variables."""
    parts = []
    if SID: parts.append(f'SID={SID}')
    if HSID: parts.append(f'HSID={HSID}')
    if SSID: parts.append(f'SSID={SSID}')
    if APISID: parts.append(f'APISID={APISID}')
    if SAPISID: parts.append(f'SAPISID={SAPISID}')
    if LOGIN_INFO: parts.append(f'LOGIN_INFO={LOGIN_INFO}')
    return '; '.join(parts)


# ============================================================
# YouTube Studio 설정 추출
# ============================================================

def get_studio_config(headers: dict) -> dict:
    """Fetch YouTube Studio config (INNERTUBE_API_KEY, DELEGATED_SESSION_ID, etc.)."""
    req = urllib.request.Request(
        f'{YT_STUDIO_URL}/channel/{CHANNEL_ID}',
        headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        config = {}
        
        # INNERTUBE_API_KEY
        match = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
        if match:
            config['INNERTUBE_API_KEY'] = match.group(1)
        
        # DELEGATED_SESSION_ID (브랜드 계정의 숫자 ID)
        match = re.search(r'"DELEGATED_SESSION_ID"\s*:\s*"([^"]+)"', html)
        if match:
            config['DELEGATED_SESSION_ID'] = match.group(1)
        
        # CHANNEL_ID
        match = re.search(r'"CHANNEL_ID"\s*:\s*"([^"]+)"', html)
        if match:
            config['CHANNEL_ID'] = match.group(1)
        
        # VISITOR_DATA
        match = re.search(r'"VISITOR_DATA"\s*:\s*"([^"]+)"', html)
        if match:
            config['VISITOR_DATA'] = match.group(1)
        
        return config
    except Exception as e:
        raise RuntimeError(f"Failed to get Studio config: {e}")


# ============================================================
# 이미지 업로드
# ============================================================

def upload_image(image_path: str, headers: dict, config: dict) -> str | None:
    """Upload image to YouTube Studio and return backstage image ID."""
    if not image_path or not Path(image_path).exists():
        return None
    
    # 이미지 읽기
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    ext = Path(image_path).suffix.lower()
    mime_type = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }.get(ext, 'image/jpeg')
    
    innertube_key = config.get('INNERTUBE_API_KEY', 'AIzaSyBUPetSUmoZL-OhlxA7wSac5XinrygCqMo')
    
    # YouTube Studio 이미지 업로드 엔드포인트
    upload_url = f'{YT_STUDIO_URL}/youtubei/v1/backstage/upload_image?key={innertube_key}'
    
    upload_headers = dict(headers)
    upload_headers['content-type'] = mime_type
    upload_headers['x-goog-upload-command'] = 'start, upload, finalize'
    upload_headers['x-goog-upload-protocol'] = 'raw'
    
    req = urllib.request.Request(
        upload_url,
        data=image_data,
        headers=upload_headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            image_id = result.get('backstageImageId') or result.get('imageId')
            print(f"Image uploaded: {image_id}")
            return image_id
    except Exception as e:
        print(f"Image upload failed: {e}")
        return None


# ============================================================
# 커뮤니티 게시글 생성
# ============================================================

def create_community_post(
    text: str,
    image_path: str = None,
    headers: dict = None,
    config: dict = None
) -> dict:
    """Create a YouTube community post."""
    
    innertube_key = config.get('INNERTUBE_API_KEY', 'AIzaSyBUPetSUmoZL-OhlxA7wSac5XinrygCqMo')
    delegated_session_id = config.get('DELEGATED_SESSION_ID', '')
    channel_id = config.get('CHANNEL_ID', CHANNEL_ID)
    visitor_data = config.get('VISITOR_DATA', '')
    
    # 이미지 업로드
    image_id = None
    if image_path:
        image_id = upload_image(image_path, headers, config)
    
    # 요청 본문 구성
    body = {
        "context": {
            "client": {
                "clientName": "WEB_CREATOR",
                "clientVersion": "1.20240401.09.00",
                "hl": "ko",
                "gl": "KR",
                "originalUrl": f"{YT_STUDIO_URL}/channel/{channel_id}/community",
                "mainAppWebInfo": {
                    "graftUrl": f"{YT_STUDIO_URL}/channel/{channel_id}/community",
                    "webDisplayMode": "WEB_DISPLAY_MODE_BROWSER",
                    "isWebNativeShareAvailable": False
                },
                "visitorData": visitor_data
            },
            "user": {
                "onBehalfOfUser": delegated_session_id,
                "lockedSafetyMode": False,
                "delegationContext": {
                    "externalChannelId": channel_id,
                    "roleType": {
                        "channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"
                    }
                }
            },
            "request": {
                "returnLogEntry": True,
                "internalExperimentFlags": [],
                "useSsl": True
            }
        },
        "externalChannelId": channel_id,
        "postText": text,
        "allowedCommenters": "ALL_COMMENTS_ALLOWED"
    }
    
    # 이미지 첨부
    if image_id:
        body["backstageImageId"] = image_id
    
    url = f'{YT_STUDIO_URL}/youtubei/v1/backstage/create_post?key={innertube_key}'
    
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code}: {error_body}")


# ============================================================
# 메인 실행
# ============================================================

def validate_cookies():
    """Validate that required cookies are set."""
    missing = []
    for name, value in [('SID', SID), ('HSID', HSID), ('SSID', SSID), 
                         ('APISID', APISID), ('SAPISID', SAPISID)]:
        if not value:
            missing.append(name)
    return missing


def main():
    # 인수 파싱
    if len(sys.argv) < 2:
        print("""
사용법: python3 upload_youtube_community.py <게시글 텍스트> [이미지 경로]

예시:
  python3 upload_youtube_community.py "안녕하세요! 새 콘텐츠 올라왔어요 🎮"
  python3 upload_youtube_community.py "새 영상 썸네일 미리보기!" /path/to/image.jpg

쿠키 설정:
  .env 파일에 YT_SID, YT_HSID, YT_SSID, YT_APISID, YT_SAPISID 추가
  (YouTube Studio 브라우저에서 개발자 도구 > Application > Cookies 에서 복사)
""")
        sys.exit(1)
    
    post_text = sys.argv[1]
    image_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"=== YouTube 커뮤니티 게시글 업로드 ===")
    print(f"채널: {CHANNEL_ID}")
    print(f"텍스트: {post_text[:50]}...")
    if image_path:
        print(f"이미지: {image_path}")
    
    # 쿠키 검증
    missing = validate_cookies()
    if missing:
        print(f"\n❌ 오류: 쿠키가 설정되지 않았습니다: {', '.join(missing)}")
        print("""
[쿠키 추출 방법]
1. 브라우저에서 studio.youtube.com 접속
2. 꿀통몬 (@ggultongmon) 브랜드 계정으로 전환
3. 개발자 도구 열기 (F12)
4. Application 탭 > Storage > Cookies > https://studio.youtube.com
5. 아래 쿠키 값을 .env 파일에 추가:
   YT_SID=...
   YT_HSID=...
   YT_SSID=...
   YT_APISID=...
   YT_SAPISID=...
""")
        sys.exit(1)
    
    print(f"✅ 쿠키 확인 완료")
    
    # 헤더 빌드
    cookie_str = build_cookie_string()
    headers = build_headers(SAPISID, cookie_str)
    
    # Studio 설정 가져오기
    print("YouTube Studio 설정 로드 중...")
    try:
        config = get_studio_config(headers)
        print(f"✅ Studio config 로드 완료:")
        print(f"   INNERTUBE_API_KEY: {config.get('INNERTUBE_API_KEY', 'N/A')[:20]}...")
        print(f"   DELEGATED_SESSION_ID: {config.get('DELEGATED_SESSION_ID', 'N/A')}")
        print(f"   CHANNEL_ID: {config.get('CHANNEL_ID', 'N/A')}")
    except Exception as e:
        print(f"❌ Studio config 로드 실패: {e}")
        print("쿠키가 만료되었거나 올바르지 않을 수 있습니다.")
        sys.exit(1)
    
    if not config.get('DELEGATED_SESSION_ID'):
        print("⚠️  DELEGATED_SESSION_ID를 찾지 못했습니다.")
        print("   브랜드 계정으로 전환된 상태에서 쿠키를 추출했는지 확인하세요.")
    
    # 게시글 작성
    print("커뮤니티 게시글 업로드 중...")
    try:
        result = create_community_post(
            text=post_text,
            image_path=image_path,
            headers=headers,
            config=config
        )
        
        if 'postId' in result or 'backstagePostId' in result:
            post_id = result.get('postId') or result.get('backstagePostId')
            print(f"✅ 게시글 업로드 성공!")
            print(f"   Post ID: {post_id}")
            print(f"   URL: https://www.youtube.com/post/{post_id}")
        elif result.get('error'):
            error = result['error']
            print(f"❌ 오류: {error.get('code')} - {error.get('message')}")
        else:
            print(f"⚠️  응답: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
    except Exception as e:
        print(f"❌ 업로드 실패: {e}")
        sys.exit(1)


def publish_community_from_dir(slides_dir: str, text: str = "", image_path: str = None) -> dict:
    """slides_dir의 첫 번째 슬라이드 이미지를 YouTube 커뮤니티 게시글로 업로드"""
    try:
        from pathlib import Path as _Path
        slides = sorted(_Path(slides_dir).glob("slide_*.jpg"))
        img = str(slides[0]) if slides else image_path
        if not img:
            return {"success": False, "error": "이미지 없음"}

        # 쿠키 검증
        missing = validate_cookies()
        if missing:
            return {"success": False, "error": f"YouTube 쿠키 미설정: {missing}"}

        # 헤더 및 설정 구성
        cookie_str = build_cookie_string()
        headers = build_headers(SAPISID, cookie_str)
        config = get_studio_config(headers)

        result = create_community_post(
            text=text,
            image_path=img,
            headers=headers,
            config=config,
        )

        post_id = result.get("postId") or result.get("backstagePostId")
        if post_id:
            return {
                "success": True,
                "post_id": post_id,
                "url": f"https://www.youtube.com/post/{post_id}",
            }
        elif result.get("error"):
            err = result["error"]
            return {"success": False, "error": f"{err.get('code')} - {err.get('message')}"}
        else:
            return {"success": False, "error": f"알 수 없는 응답: {str(result)[:200]}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == '__main__':
    main()
