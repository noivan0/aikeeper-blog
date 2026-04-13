#!/usr/bin/env python3
"""
GitHub Pages 이미지 업로드 공통 유틸리티
upload_instagram.py, post_to_tistory.py 등에서 공유

환경변수:
  GITHUB_PAT          GitHub Personal Access Token
  GITHUB_PAGES_REPO   레포 (기본: noivan0/aikeeper-blog)
  GITHUB_PAGES_BRANCH 브랜치 (기본: gh-pages)
  GITHUB_PAGES_BASE   공개 URL base (기본: https://noivan0.github.io/aikeeper-blog)
"""
import os, json, base64, urllib.request


def upload_bytes_to_github_pages(
    data: bytes,
    remote_path: str,
    commit_msg: str = "upload",
    *,
    gh_token: str = "",
    repo: str = "",
    branch: str = "",
    base_url: str = "",
) -> str:
    """
    bytes 데이터를 GitHub Pages gh-pages 브랜치에 업로드.
    성공 시 공개 URL 반환, 실패 시 빈 문자열 반환.
    """
    gh_token = gh_token or os.environ.get("GITHUB_PAT", "")
    repo     = repo     or os.environ.get("GITHUB_PAGES_REPO", "noivan0/aikeeper-blog")
    branch   = branch   or os.environ.get("GITHUB_PAGES_BRANCH", "gh-pages")
    base_url = base_url or os.environ.get("GITHUB_PAGES_BASE", "https://noivan0.github.io/aikeeper-blog")

    if not gh_token or not data:
        return ""

    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    payload = json.dumps({
        "message": commit_msg,
        "content": base64.b64encode(data).decode(),
        "branch": branch,
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
        urllib.request.urlopen(req, timeout=30)
        return f"{base_url.rstrip('/')}/{remote_path}"
    except Exception as e:
        print(f"  [github_utils] 업로드 실패 ({remote_path}): {e}")
        return ""


def upload_file_to_github_pages(
    file_path,
    remote_path: str,
    commit_msg: str = "upload",
    **kwargs,
) -> str:
    """
    로컬 파일을 GitHub Pages에 업로드.
    성공 시 공개 URL 반환, 실패 시 빈 문자열 반환.
    """
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        print(f"  [github_utils] 파일 없음: {file_path}")
        return ""
    return upload_bytes_to_github_pages(p.read_bytes(), remote_path, commit_msg, **kwargs)


def check_url_available(url: str, timeout: int = 5) -> bool:
    """URL이 접근 가능한지 확인."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def wait_for_github_pages(urls: list, max_wait_sec: int = 300, interval: int = 30) -> bool:
    """
    GitHub Pages CDN 반영 대기.
    urls 중 첫 번째 URL이 접근 가능해질 때까지 대기.
    max_wait_sec 초 내에 가능하면 True, 아니면 False 반환.
    """
    import time
    if not urls:
        return False

    check_url = urls[0]
    print(f"  [github_utils] CDN 반영 대기 중: {check_url} (최대 {max_wait_sec}초)")

    # 초기 대기 (60초)
    time.sleep(min(60, max_wait_sec))

    elapsed = 60
    while elapsed < max_wait_sec:
        if check_url_available(check_url):
            print(f"  [github_utils] CDN 반영 확인 완료 ({elapsed}초 경과)")
            return True
        print(f"  [github_utils] 대기 중... ({elapsed}/{max_wait_sec}초)")
        time.sleep(interval)
        elapsed += interval

    # 마지막 한 번 더 확인
    if check_url_available(check_url):
        print(f"  [github_utils] CDN 반영 확인 완료 ({elapsed}초 경과)")
        return True

    print(f"  [github_utils] CDN 반영 타임아웃 ({max_wait_sec}초) — 진행 계속")
    return False
