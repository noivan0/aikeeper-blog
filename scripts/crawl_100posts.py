#!/usr/bin/env python3
"""
네이버 블로그 상위 노출 포스팅 100개 크롤링 + 패턴 분석
- 5개 키워드 × 20개 URL = 100개
- 로그인 세션 사용
- se-fs CSS 클래스 분석 포함
"""

import json
import re
import time
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = "/root/.openclaw/workspace/paperclip-company/projects/p004-blogger/naver_session.json"
OUTPUT_FILE = "/tmp/naver_100posts.json"

KEYWORDS = [
    "내돈내산 쿠팡 솔직후기",
    "쿠팡 직접써봄 구매후기",
    "로켓배송 내돈내산 추천",
    "쿠팡 가성비 실사용후기",
    "쿠팡 내돈내산 비교",
]

def load_session():
    with open(SESSION_FILE, "r") as f:
        return json.load(f)

def collect_urls(page, keyword, max_count=20):
    """네이버 블로그 검색에서 URL 수집"""
    from urllib.parse import quote
    encoded = quote(keyword)
    url = f"https://search.naver.com/search.naver?where=blog&query={encoded}&sm=tab_jum"
    
    print(f"\n🔍 키워드: {keyword}")
    print(f"   URL: {url}")
    
    urls = []
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    
    # 여러 페이지에서 수집
    page_num = 1
    while len(urls) < max_count and page_num <= 3:
        # 블로그 링크 추출
        links = page.query_selector_all("a[href*='blog.naver.com']")
        
        for link in links:
            href = link.get_attribute("href") or ""
            # blog.naver.com/{user}/{postId} 패턴 매칭
            match = re.search(r'blog\.naver\.com/([^/?&]+)/(\d+)', href)
            if match:
                user = match.group(1)
                post_id = match.group(2)
                canonical = f"https://blog.naver.com/{user}/{post_id}"
                if canonical not in urls:
                    urls.append(canonical)
        
        print(f"   페이지 {page_num}: {len(urls)}개 수집")
        
        if len(urls) >= max_count:
            break
        
        # 다음 페이지
        next_btn = page.query_selector("a.btn_next, a[aria-label='다음'], .pg_next a")
        if next_btn:
            next_btn.click()
            time.sleep(2)
            page_num += 1
        else:
            # 스크롤로 더 로드 시도
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            new_links = page.query_selector_all("a[href*='blog.naver.com']")
            new_urls_found = False
            for link in new_links:
                href = link.get_attribute("href") or ""
                match = re.search(r'blog\.naver\.com/([^/?&]+)/(\d+)', href)
                if match:
                    user = match.group(1)
                    post_id = match.group(2)
                    canonical = f"https://blog.naver.com/{user}/{post_id}"
                    if canonical not in urls:
                        urls.append(canonical)
                        new_urls_found = True
            
            if not new_urls_found:
                break
    
    result = urls[:max_count]
    print(f"   최종 수집: {len(result)}개")
    return result

def to_mobile_url(url):
    """blog.naver.com → m.blog.naver.com"""
    return url.replace("://blog.naver.com/", "://m.blog.naver.com/")

def extract_post_data(page, url, keyword):
    """포스팅 본문 데이터 추출"""
    mobile_url = to_mobile_url(url)
    
    try:
        page.goto(mobile_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        
        # 제목 추출
        title = ""
        title_el = page.query_selector(".se-title-text, .tit_h3, h2.title, .se-module-text h2")
        if title_el:
            title = title_el.inner_text().strip()
        
        if not title:
            title_el = page.query_selector("title")
            if title_el:
                raw = title_el.inner_text()
                title = raw.split(":")[0].strip() if ":" in raw else raw.strip()
        
        # 본문 추출 (.se-main-container)
        content = ""
        content_el = page.query_selector(".se-main-container")
        if content_el:
            content = content_el.inner_text().strip()
        
        if len(content) < 300:
            print(f"   ⚠️  본문 {len(content)}자 - 스킵")
            return None
        
        # 이미지 수 (width > 100인 img)
        img_count = page.evaluate("""
            () => {
                const imgs = document.querySelectorAll('.se-main-container img');
                let count = 0;
                imgs.forEach(img => {
                    const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width') || '0');
                    if (w > 100) count++;
                });
                return count;
            }
        """)
        
        # 해시태그 여부
        has_hashtag = bool(page.query_selector(".se-hashtag, .post_tag, [class*='hashtag']"))
        hashtag_text = ""
        hashtag_el = page.query_selector_all(".se-hashtag, .post_tag")
        hashtag_list = []
        for el in hashtag_el:
            t = el.inner_text().strip()
            if t:
                hashtag_list.append(t)
        hashtag_count = len(hashtag_list)
        
        # se-fs CSS 클래스 분석 (소제목 폰트 크기 코드)
        se_fs_classes = page.evaluate("""
            () => {
                const allSpans = document.querySelectorAll('.se-main-container span[class*="se-fs-"]');
                const classCount = {};
                allSpans.forEach(span => {
                    span.classList.forEach(cls => {
                        if (cls.startsWith('se-fs-')) {
                            classCount[cls] = (classCount[cls] || 0) + 1;
                        }
                    });
                });
                return classCount;
            }
        """)
        
        # 소제목 단락 분석 (큰 글씨 단락)
        subtitle_data = page.evaluate("""
            () => {
                const result = [];
                // se-fs-fs24 이상인 것들 = 소제목 후보
                const bigTexts = document.querySelectorAll(
                    '.se-main-container span[class*="se-fs-fs2"], ' +
                    '.se-main-container span[class*="se-fs-fs3"], ' +
                    '.se-main-container .se-heading'
                );
                bigTexts.forEach(el => {
                    const text = el.innerText.trim();
                    if (text.length > 0 && text.length < 100) {
                        const classes = Array.from(el.classList).filter(c => c.startsWith('se-fs-'));
                        result.push({
                            text: text.substring(0, 50),
                            classes: classes
                        });
                    }
                });
                return result.slice(0, 20);
            }
        """)
        
        # 오프닝 (첫 200자)
        opening = content[:200] if content else ""
        
        # 본문에서 링크 위치 분석
        links_html = page.evaluate("""
            () => {
                const container = document.querySelector('.se-main-container');
                if (!container) return [];
                const links = container.querySelectorAll('a[href]');
                const containerText = container.innerText || '';
                const totalLen = containerText.length;
                const result = [];
                links.forEach(link => {
                    const href = link.href;
                    if (href && !href.includes('blog.naver.com') && !href.startsWith('#')) {
                        // 링크 위치 추정
                        const linkText = link.innerText;
                        const parentText = container.innerText;
                        const idx = parentText.indexOf(linkText);
                        const pos = totalLen > 0 ? idx / totalLen : 0;
                        result.push({
                            href: href.substring(0, 100),
                            position_ratio: pos
                        });
                    }
                });
                return result;
            }
        """)
        
        return {
            "url": url,
            "mobile_url": mobile_url,
            "keyword": keyword,
            "title": title,
            "content": content,
            "content_length": len(content),
            "image_count": img_count,
            "has_hashtag": has_hashtag,
            "hashtag_count": hashtag_count,
            "hashtags": hashtag_list[:20],
            "opening": opening,
            "se_fs_classes": se_fs_classes,
            "subtitle_samples": subtitle_data,
            "links": links_html[:10],
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        
    except Exception as e:
        print(f"   ❌ 오류: {e}")
        return None


def main():
    print("=" * 60)
    print("네이버 블로그 100개 크롤링 시작")
    print("=" * 60)
    
    session_data = load_session()
    
    all_urls = {}  # keyword -> [url]
    all_posts = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            storage_state=session_data,
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            viewport={"width": 390, "height": 844},
        )
        page = context.new_page()
        
        # === 단계 1: URL 수집 ===
        print("\n📋 단계 1: URL 수집")
        for keyword in KEYWORDS:
            urls = collect_urls(page, keyword, max_count=20)
            all_urls[keyword] = urls
        
        # 통계
        total_urls = sum(len(v) for v in all_urls.values())
        print(f"\n✅ 총 수집 URL: {total_urls}개")
        
        # === 단계 2: 본문 수집 ===
        print("\n📄 단계 2: 본문 수집")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        seen_urls = set()
        
        for keyword, urls in all_urls.items():
            print(f"\n[{keyword}] {len(urls)}개 처리")
            for i, url in enumerate(urls, 1):
                if url in seen_urls:
                    print(f"   [{i}/{len(urls)}] 중복 스킵: {url}")
                    continue
                seen_urls.add(url)
                
                print(f"   [{i}/{len(urls)}] {url}")
                post = extract_post_data(page, url, keyword)
                
                if post:
                    all_posts.append(post)
                    success_count += 1
                    print(f"   ✅ {len(post['content'])}자, 이미지 {post['image_count']}개, 해시태그 {post['hashtag_count']}개")
                else:
                    skip_count += 1
                
                # 요청 간격
                time.sleep(1.5)
        
        browser.close()
    
    print(f"\n📊 수집 결과: 성공 {success_count}개, 스킵 {skip_count}개")
    
    # 저장
    output = {
        "meta": {
            "total_posts": len(all_posts),
            "keywords": KEYWORDS,
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "url_collection": {k: v for k, v in all_urls.items()},
        "posts": all_posts,
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 저장 완료: {OUTPUT_FILE}")
    return all_posts


if __name__ == "__main__":
    main()
