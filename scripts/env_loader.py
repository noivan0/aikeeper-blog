"""
env_loader.py — 공통 .env 로더 + Anthropic 클라이언트 팩토리
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
모든 스크립트에서:
    from env_loader import load_env, make_anthropic_client

특징:
- 스크립트 실행 방식(bash/sh/cron/subprocess)에 무관하게 동작
- openclaw.json custom provider와 동일한 base_url/api_key 사용
- 한 번 로드하면 캐시 (모듈 레벨)
"""
import os
import re
from pathlib import Path

# ── .env 파일 경로 ─────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent   # p004-blogger/
_ENV_FILE = _BASE_DIR / ".env"

_loaded = False


def load_env(force: bool = False) -> None:
    """
    .env 파일을 읽어 os.environ에 설정.
    이미 로드된 경우 스킵 (force=True로 재로드 가능).
    JSON 값(다중줄) 안전 처리.
    """
    global _loaded
    if _loaded and not force:
        return

    if not _ENV_FILE.exists():
        return

    text = _ENV_FILE.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        # 주석/빈 줄 스킵
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        if "=" not in line:
            i += 1
            continue

        key, _, val = line.partition("=")
        key = key.strip()

        # 유효한 환경변수 이름인지 검사
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            i += 1
            continue

        # JSON 값 처리: { 로 시작하면 } 가 나올 때까지 병합
        if val.strip().startswith("{"):
            json_lines = [val]
            while i + 1 < len(lines) and "}" not in val:
                i += 1
                val = lines[i]
                json_lines.append(val)
            val = "\n".join(json_lines)

        # 따옴표 제거 (선택적)
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]

        # 이미 설정된 환경변수는 덮어쓰지 않음 (런타임 우선)
        if key not in os.environ:
            os.environ[key] = val

        i += 1

    _loaded = True


def make_anthropic_client(timeout: int = 120, max_retries: int = 2):
    """
    Anthropic 클라이언트 생성.
    openclaw.json custom provider와 동일한 설정 사용.
    """
    load_env()

    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic 패키지가 없습니다: pip install anthropic")

    api_key  = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "")

    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. "
            f".env 파일({_ENV_FILE})을 확인하세요."
        )

    kwargs = dict(timeout=timeout, max_retries=max_retries)
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    return anthropic.Anthropic(**kwargs)


def get_model() -> str:
    """ANTHROPIC_MODEL 환경변수 반환. 기본값: claude-sonnet-4-6"""
    load_env()
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# 모듈 import 시 자동 로드
load_env()
