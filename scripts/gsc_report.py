#!/usr/bin/env python3
"""
Google Search Console 주간 성과 리포트
- Search Analytics: 포스트별 클릭/노출/CTR/순위
- 결과: output/reports/gsc_report_YYYY-WW.md
"""
import os
import json
import datetime
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BLOG_URL = "https://aikeeper.allsweep.xyz"
BLOG_ID  = os.environ.get("ALLSWEEP_BLOG_ID", "3598676904202320050")


def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/blogger",
            "https://www.googleapis.com/auth/webmasters",
        ],
    )
    creds.refresh(Request())
    return creds


def get_search_analytics(token: str, days: int = 28) -> list:
    """Search Analytics: 최근 N일 페이지별 클릭/노출/CTR/순위"""
    today     = datetime.date.today()
    end_date  = (today - datetime.timedelta(days=3)).isoformat()   # GSC는 3일 지연
    start_date = (today - datetime.timedelta(days=days + 3)).isoformat()

    site_url = requests.utils.quote(BLOG_URL + "/", safe="")
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

    payload = {
        "startDate": start_date,
        "endDate":   end_date,
        "dimensions": ["page"],
        "rowLimit":   50,
        "dataState":  "all",
    }

    r = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )

    if r.status_code != 200:
        print(f"  ⚠️  Search Analytics 오류 [{r.status_code}]: {r.text[:150]}")
        return []

    rows = r.json().get("rows", [])
    results = []
    for row in rows:
        keys    = row.get("keys", [""])
        page    = keys[0]
        clicks  = row.get("clicks", 0)
        imps    = row.get("impressions", 0)
        ctr     = row.get("ctr", 0) * 100
        pos     = row.get("position", 0)
        results.append({
            "page":        page,
            "clicks":      int(clicks),
            "impressions": int(imps),
            "ctr":         round(ctr, 2),
            "position":    round(pos, 1),
        })

    # 클릭 수 기준 정렬
    results.sort(key=lambda x: x["clicks"], reverse=True)
    return results


def get_top_queries(token: str, days: int = 28) -> list:
    """Search Analytics: 상위 검색어"""
    today      = datetime.date.today()
    end_date   = (today - datetime.timedelta(days=3)).isoformat()
    start_date = (today - datetime.timedelta(days=days + 3)).isoformat()

    site_url = requests.utils.quote(BLOG_URL + "/", safe="")
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

    payload = {
        "startDate":  start_date,
        "endDate":    end_date,
        "dimensions": ["query"],
        "rowLimit":   20,
        "dataState":  "all",
    }

    r = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )

    if r.status_code != 200:
        return []

    rows = r.json().get("rows", [])
    results = []
    for row in rows:
        results.append({
            "query":       row.get("keys", [""])[0],
            "clicks":      int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr":         round(row.get("ctr", 0) * 100, 2),
            "position":    round(row.get("position", 0), 1),
        })
    results.sort(key=lambda x: x["clicks"], reverse=True)
    return results


def submit_sitemap(token: str) -> None:
    """Sitemap 제출"""
    site_url    = requests.utils.quote(BLOG_URL + "/", safe="")
    sitemap_url = requests.utils.quote(f"{BLOG_URL}/sitemap.xml", safe="")
    endpoint    = f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/sitemaps/{sitemap_url}"
    r = requests.put(endpoint, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if r.status_code in (200, 204):
        print(f"  ✅ Sitemap 제출 완료")
    else:
        print(f"  ⚠️  Sitemap 제출 [{r.status_code}]: {r.text[:80]}")


def build_report(pages: list, queries: list, days: int) -> str:
    today   = datetime.date.today()
    year_ww = today.strftime("%Y-W%V")

    total_clicks = sum(p["clicks"] for p in pages)
    total_imps   = sum(p["impressions"] for p in pages)
    avg_ctr      = round(total_clicks / total_imps * 100, 2) if total_imps else 0
    avg_pos      = round(sum(p["position"] * p["impressions"] for p in pages) /
                         max(sum(p["impressions"] for p in pages), 1), 1)

    lines = [
        f"# AI키퍼 GSC 주간 리포트 — {year_ww}",
        f"_생성: {today.isoformat()} | 기간: 최근 {days}일_",
        "",
        "## 📊 전체 요약",
        "",
        f"| 항목 | 수치 |",
        f"|------|------|",
        f"| 총 클릭 | {total_clicks:,} |",
        f"| 총 노출 | {total_imps:,} |",
        f"| 평균 CTR | {avg_ctr}% |",
        f"| 평균 순위 | {avg_pos}위 |",
        "",
        "## 🏆 상위 포스트 (클릭 기준)",
        "",
        "| 순위 | 페이지 | 클릭 | 노출 | CTR | 평균순위 |",
        "|------|--------|------|------|-----|---------|",
    ]

    for i, p in enumerate(pages[:15], 1):
        page_short = p["page"].replace(BLOG_URL, "").strip("/") or "홈"
        lines.append(
            f"| {i} | {page_short} | {p['clicks']:,} | {p['impressions']:,} | {p['ctr']}% | {p['position']} |"
        )

    lines += [
        "",
        "## 🔍 상위 검색어 (클릭 기준)",
        "",
        "| 순위 | 검색어 | 클릭 | 노출 | CTR | 평균순위 |",
        "|------|--------|------|------|-----|---------|",
    ]

    for i, q in enumerate(queries[:15], 1):
        lines.append(
            f"| {i} | {q['query']} | {q['clicks']:,} | {q['impressions']:,} | {q['ctr']}% | {q['position']} |"
        )

    lines += [
        "",
        "---",
        f"_자동 생성 by AI키퍼 GSC 리포터_",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    print(f"📊 GSC 주간 리포트 생성 중...")

    try:
        creds = get_credentials()
        print(f"  ✅ 인증 성공")
    except Exception as e:
        print(f"  ❌ 인증 실패: {e}")
        exit(1)

    token = creds.token

    # Sitemap 제출
    print("  📡 Sitemap 제출...")
    submit_sitemap(token)

    # Search Analytics
    print("  📡 Search Analytics 조회 중...")
    pages   = get_search_analytics(token, days=28)
    queries = get_top_queries(token, days=28)
    print(f"  ✅ 페이지 {len(pages)}개, 검색어 {len(queries)}개")

    if not pages and not queries:
        print("  ⚠️  데이터 없음 (신규 사이트이거나 scope 문제)")
        print("  → 다음 주 재시도 예정")
        exit(0)

    # 리포트 생성
    report_md = build_report(pages, queries, days=28)

    today   = datetime.date.today()
    year_ww = today.strftime("%Y-W%V")
    out_dir = "output/reports"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/gsc_report_{year_ww}.md"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"  ✅ 리포트 저장: {out_path}")
    print()
    print(report_md[:500])
