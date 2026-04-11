#!/usr/bin/env python3
"""최종 보충 - 100개 달성"""

import json
import re
import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright

SESSION_FILE = "/root/.openclaw/workspace/paperclip-company/projects/p004-blogger/naver_session.json"
EXISTING_JSON = "/tmp/naver_100posts.json"
OUTPUT_FILE = "/tmp/naver_100posts.json"

EXTRA_KEYWORDS = [
    "쿠팡 내돈내산",
    "쿠팡파트너스 후기",
    "쿠팡 리뷰 솔직",
    "쿠팡 내돈내산 리뷰",
]

def load_session():
    with open(SESSION_FILE) as f:
        return json.load(f)

def collect_urls_deep(page, keyword, max_count=30):
    encoded = quote(keyword)
    base_url = f"https://search.naver.com/search.naver?where=blog&query={encoded}&sm=tab_jum"
    
    print(f"\n🔍 키워드: {keyword}")
    urls = []
    
    for page_num in range(1, 6):
        if len(urls) >= max_count:
            break
        
        paged_url = base_url if page_num == 1 else f"{base_url}&start={1 + (page_num-1)*10}"
        page.goto(paged_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.5)
        
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(0.4)
        
        links = page.query_selector_all("a[href*='blog.naver.com']")
        prev = len(urls)
        
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r'blog\.naver\.com/([^/?&"\']+)/(\d{5,})', href)
            if match:
                user, post_id = match.group(1), match.group(2)
                if user in ['NewsStand', 'news', 'connect', 'PostDetail']:
                    continue
                canonical = f"https://blog.naver.com/{user}/{post_id}"
                if canonical not in urls:
                    urls.append(canonical)
        
        print(f"   p{page_num}: {len(urls)}개 (신규 {len(urls)-prev}개)")
        if len(urls) == prev:
            break
    
    return urls[:max_count]

def extract_post_data(page, url, keyword):
    mobile_url = url.replace("://blog.naver.com/", "://m.blog.naver.com/")
    try:
        page.goto(mobile_url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(1.2)
        
        title = ""
        for sel in [".se-title-text", ".tit_h3", "h2.title"]:
            el = page.query_selector(sel)
            if el:
                title = el.inner_text().strip()
                if title: break
        
        content = ""
        el = page.query_selector(".se-main-container")
        if el:
            content = el.inner_text().strip()
        
        if len(content) < 300:
            return None
        
        img_count = page.evaluate("""
            () => {
                let count = 0;
                document.querySelectorAll('.se-main-container img').forEach(img => {
                    const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width') || '0');
                    if (w > 100) count++;
                });
                return count;
            }
        """)
        
        hashtag_list = [el.inner_text().strip() for el in page.query_selector_all(".se-hashtag, .post_tag") if el.inner_text().strip()]
        
        se_fs_classes = page.evaluate("""
            () => {
                const counts = {};
                document.querySelectorAll('.se-main-container span[class*="se-fs-"]').forEach(span => {
                    span.classList.forEach(cls => {
                        if (cls.startsWith('se-fs-')) counts[cls] = (counts[cls] || 0) + 1;
                    });
                });
                return counts;
            }
        """)
        
        subtitle_data = page.evaluate("""
            () => {
                const result = [];
                document.querySelectorAll(
                    '.se-main-container span[class*="se-fs-fs2"], ' +
                    '.se-main-container span[class*="se-fs-fs3"], ' +
                    '.se-main-container .se-heading'
                ).forEach(el => {
                    const text = el.innerText.trim();
                    if (text.length > 0 && text.length < 100) {
                        const classes = Array.from(el.classList).filter(c => c.startsWith('se-fs-'));
                        result.push({ text: text.substring(0, 50), classes });
                    }
                });
                return result.slice(0, 20);
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
            "has_hashtag": len(hashtag_list) > 0,
            "hashtag_count": len(hashtag_list),
            "hashtags": hashtag_list[:20],
            "opening": content[:200],
            "se_fs_classes": se_fs_classes,
            "subtitle_samples": subtitle_data,
            "links": [],
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        print(f"   ❌ {e}")
        return None

def main():
    with open(EXISTING_JSON) as f:
        existing = json.load(f)
    
    existing_posts = existing["posts"]
    existing_urls = {p["url"] for p in existing_posts}
    print(f"기존: {len(existing_posts)}개 → {100 - len(existing_posts)}개 더 필요")
    
    new_posts = []
    session_data = load_session()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            storage_state=session_data,
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            viewport={"width": 390, "height": 844},
        )
        page = context.new_page()
        
        for keyword in EXTRA_KEYWORDS:
            urls = collect_urls_deep(page, keyword, max_count=30)
            
            for i, url in enumerate(urls, 1):
                if url in existing_urls:
                    continue
                existing_urls.add(url)
                
                total = len(existing_posts) + len(new_posts)
                if total >= 100:
                    break
                
                print(f"   [{i}] {url}")
                post = extract_post_data(page, url, keyword)
                if post:
                    new_posts.append(post)
                    print(f"   ✅ {len(post['content'])}자 (총 {len(existing_posts)+len(new_posts)}개)")
                time.sleep(1.0)
            
            if len(existing_posts) + len(new_posts) >= 100:
                break
        
        browser.close()
    
    all_posts = existing_posts + new_posts
    print(f"\n📊 최종: {len(all_posts)}개")
    
    output = {
        "meta": {
            "total_posts": len(all_posts),
            "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
        "posts": all_posts,
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 저장: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
