#!/usr/bin/env python3
"""
Blogger 테마 <head>에 WebSite + SearchAction 스키마 삽입
- 사이트 수준 JSON-LD (포스팅 레벨 아닌 전체 테마)
- 실행: python3 scripts/setup_blogger_theme_schema.py [aikeeper|allsweep|ggultongmon]

WebSite 스키마 효과:
- Google 사이트명(Site Name) 인식 강화
- SearchAction → Google 검색결과에 사이트 내 검색박스 표시 가능
"""
import os, sys, json, re
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = Path(__file__).parent.parent

# .env 로드
for line in (BASE_DIR / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

BLOG_CONFIGS = {
    "aikeeper": {
        "blog_id":   "3598676904202320050",
        "url":       "https://aikeeper.allsweep.xyz",
        "name":      "AI키퍼",
        "search_url": "https://aikeeper.allsweep.xyz/search?q={search_term_string}",
        "cid":   "AIKEEPER_CLIENT_ID",
        "csec":  "AIKEEPER_CLIENT_SECRET",
        "rt":    "AIKEEPER_REFRESH_TOKEN",
    },
    "allsweep": {
        "blog_id":   "8772490249452917821",
        "url":       "https://www.allsweep.xyz",
        "name":      "모든정보 쓸어담기",
        "search_url": "https://www.allsweep.xyz/search?q={search_term_string}",
        "cid":   "ALLSWEEP_CLIENT_ID",
        "csec":  "ALLSWEEP_CLIENT_SECRET",
        "rt":    "ALLSWEEP_REFRESH_TOKEN",
    },
    "ggultongmon": {
        "blog_id":   "4422596386410826373",
        "url":       "https://ggultongmon.allsweep.xyz",
        "name":      "꿀통 몬스터",
        "search_url": "https://ggultongmon.allsweep.xyz/search?q={search_term_string}",
        "cid":   "GGULTONGMON_CLIENT_ID",
        "csec":  "GGULTONGMON_CLIENT_SECRET",
        "rt":    "GGULTONGMON_REFRESH_TOKEN",
    },
}


def get_token(cfg: dict) -> str:
    creds = Credentials(
        token=None,
        refresh_token=os.environ[cfg["rt"]],
        client_id=os.environ[cfg["cid"]],
        client_secret=os.environ[cfg["csec"]],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/blogger"],
    )
    creds.refresh(Request())
    return creds.token


def build_website_schema(cfg: dict) -> str:
    """WebSite + SearchAction JSON-LD"""
    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": cfg["name"],
        "url": cfg["url"],
        "inLanguage": "ko-KR",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": cfg["search_url"]
            },
            "query-input": "required name=search_term_string"
        }
    }
    return (
        '\n<!-- WebSite Schema for Google Search -->\n'
        f'<script type="application/ld+json">\n'
        f'{json.dumps(schema, ensure_ascii=False, indent=2)}\n'
        f'</script>\n'
        '<!-- /WebSite Schema -->\n'
    )


def inject_schema_to_theme(blog_name: str, dry_run: bool = False):
    import requests

    cfg = BLOG_CONFIGS[blog_name]
    token = get_token(cfg)

    print(f"[{blog_name}] 현재 테마 조회 중...")
    r = requests.get(
        f"https://www.googleapis.com/blogger/v3/blogs/{cfg['blog_id']}/themes",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15
    )

    if r.status_code != 200:
        # themes 엔드포인트 대신 template 엔드포인트
        print(f"  themes API 실패 ({r.status_code}), template API 시도...")
        r = requests.get(
            f"https://blogger.googleapis.com/v3/blogs/{cfg['blog_id']}/templates/page",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        if r.status_code != 200:
            print(f"  ❌ 테마 조회 실패: {r.status_code} — {r.text[:200]}")
            print(f"  ℹ️  Blogger 테마 API는 일부 블로그에서 제한됩니다.")
            print(f"  ℹ️  대신 WebSite 스키마를 Blogger 테마 편집기에 수동으로 삽입하세요:")
            print(f"\n  Blogger 관리 → 테마 → HTML 편집 → <head> 태그 안에 아래 코드 삽입:\n")
            print(build_website_schema(cfg))
            return

    theme = r.json()
    theme_html = theme.get("html", "")

    website_schema = build_website_schema(cfg)
    marker = "<!-- WebSite Schema for Google Search -->"

    if marker in theme_html:
        print(f"  ✅ WebSite 스키마 이미 삽입됨")
        return

    # </head> 직전에 삽입
    if "</head>" in theme_html:
        new_html = theme_html.replace("</head>", website_schema + "</head>", 1)
    else:
        print(f"  ⚠️  </head> 태그 없음 — 삽입 위치 찾기 실패")
        return

    if dry_run:
        print(f"  [DRY RUN] 삽입할 스키마:\n{website_schema}")
        return

    # 테마 업데이트
    patch_r = requests.patch(
        f"https://blogger.googleapis.com/v3/blogs/{cfg['blog_id']}/templates/page",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"html": new_html},
        timeout=20
    )
    if patch_r.status_code in (200, 201):
        print(f"  ✅ WebSite 스키마 테마 삽입 완료!")
    else:
        print(f"  ❌ 테마 업데이트 실패: {patch_r.status_code}")
        print(f"  ℹ️  수동 삽입 코드:")
        print(build_website_schema(cfg))


def print_manual_guide():
    """모든 블로그 수동 삽입 가이드 출력"""
    print("\n" + "="*60)
    print("📋 WebSite 스키마 수동 삽입 가이드")
    print("="*60)
    print("Blogger 관리자 → 테마 → HTML 편집 → </head> 바로 위에 삽입\n")
    for name, cfg in BLOG_CONFIGS.items():
        print(f"\n--- {name} ({cfg['url']}) ---")
        print(build_website_schema(cfg))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) >= 2 else "all"
    dry_run = "--dry-run" in sys.argv

    if target == "guide":
        print_manual_guide()
    elif target == "all":
        for name in BLOG_CONFIGS:
            inject_schema_to_theme(name, dry_run=dry_run)
    elif target in BLOG_CONFIGS:
        inject_schema_to_theme(target, dry_run=dry_run)
    else:
        print(f"Usage: {sys.argv[0]} [aikeeper|allsweep|ggultongmon|all|guide] [--dry-run]")
