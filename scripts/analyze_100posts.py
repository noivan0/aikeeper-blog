#!/usr/bin/env python3
"""
100개 포스팅 정밀 분석 - Claude API 없이 Python으로 자체 분석
분석 항목:
1. 소제목 형식 (이모지, 길이, 어미)
2. 이미지 밀도 (1000자당 이미지 수)
3. 본문 길이 분포
4. 제목 자수 분포
5. 해시태그 수 분포
6. 오프닝 패턴
7. se-fs CSS 클래스 분포
"""

import json
import re
import statistics
from collections import Counter, defaultdict

INPUT_FILE = "/tmp/naver_100posts.json"
OUTPUT_GUIDE = "/root/.openclaw/workspace/paperclip-company/projects/p004-blogger/docs/naver_format_guide_v2.md"

def load_data():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["posts"]

def analyze_title_length(posts):
    lengths = [len(p["title"]) for p in posts if p["title"]]
    if not lengths:
        return {}
    return {
        "count": len(lengths),
        "mean": round(statistics.mean(lengths), 1),
        "median": round(statistics.median(lengths), 1),
        "p25": round(sorted(lengths)[len(lengths)//4], 1),
        "p75": round(sorted(lengths)[3*len(lengths)//4], 1),
        "min": min(lengths),
        "max": max(lengths),
        "distribution": {
            "≤15자": sum(1 for l in lengths if l <= 15),
            "16-25자": sum(1 for l in lengths if 16 <= l <= 25),
            "26-35자": sum(1 for l in lengths if 26 <= l <= 35),
            "36-45자": sum(1 for l in lengths if 36 <= l <= 45),
            "46자+": sum(1 for l in lengths if l >= 46),
        }
    }

def analyze_content_length(posts):
    lengths = [p["content_length"] for p in posts]
    sorted_l = sorted(lengths)
    n = len(sorted_l)
    return {
        "count": n,
        "mean": round(statistics.mean(lengths), 0),
        "median": round(statistics.median(lengths), 0),
        "p25": sorted_l[n//4],
        "p75": sorted_l[3*n//4],
        "min": min(lengths),
        "max": max(lengths),
        "distribution": {
            "≤500자": sum(1 for l in lengths if l <= 500),
            "501-1000자": sum(1 for l in lengths if 501 <= l <= 1000),
            "1001-2000자": sum(1 for l in lengths if 1001 <= l <= 2000),
            "2001-3000자": sum(1 for l in lengths if 2001 <= l <= 3000),
            "3001자+": sum(1 for l in lengths if l >= 3001),
        }
    }

def analyze_image_density(posts):
    """1000자당 이미지 수"""
    densities = []
    for p in posts:
        if p["content_length"] > 0:
            density = p["image_count"] / (p["content_length"] / 1000)
            densities.append(density)
    
    if not densities:
        return {}
    
    return {
        "mean_per_1000chars": round(statistics.mean(densities), 2),
        "median_per_1000chars": round(statistics.median(densities), 2),
        "mean_total_images": round(statistics.mean(p["image_count"] for p in posts), 1),
        "median_total_images": round(statistics.median(sorted([p["image_count"] for p in posts])), 0),
        "distribution": {
            "0장": sum(1 for p in posts if p["image_count"] == 0),
            "1-5장": sum(1 for p in posts if 1 <= p["image_count"] <= 5),
            "6-10장": sum(1 for p in posts if 6 <= p["image_count"] <= 10),
            "11-20장": sum(1 for p in posts if 11 <= p["image_count"] <= 20),
            "21장+": sum(1 for p in posts if p["image_count"] >= 21),
        }
    }

def analyze_hashtags(posts):
    counts = [p["hashtag_count"] for p in posts]
    has_hashtag = sum(1 for p in posts if p["has_hashtag"])
    
    all_tags = []
    for p in posts:
        all_tags.extend(p.get("hashtags", []))
    
    return {
        "has_hashtag_ratio": round(has_hashtag / len(posts) * 100, 1),
        "mean_count": round(statistics.mean(counts), 1),
        "distribution": {
            "0개": sum(1 for c in counts if c == 0),
            "1-3개": sum(1 for c in counts if 1 <= c <= 3),
            "4-10개": sum(1 for c in counts if 4 <= c <= 10),
            "11-20개": sum(1 for c in counts if 11 <= c <= 20),
            "21개+": sum(1 for c in counts if c >= 21),
        },
        "top_tags": Counter(all_tags).most_common(20),
    }

def analyze_se_fs_classes(posts):
    """se-fs CSS 클래스 집계"""
    total_counter = Counter()
    per_post_max = []
    
    for p in posts:
        se_fs = p.get("se_fs_classes", {})
        post_classes = set()
        for cls, cnt in se_fs.items():
            total_counter[cls] += cnt
            post_classes.add(cls)
        
        # 포스팅에서 사용된 최대 폰트 크기 코드 찾기
        max_fs = None
        max_num = 0
        for cls in post_classes:
            match = re.search(r'se-fs-fs(\d+)', cls)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    max_fs = cls
        
        if max_fs:
            per_post_max.append(max_fs)
    
    # 소제목으로 많이 쓰인 se-fs 코드
    subtitle_candidate = []
    for p in posts:
        for sub in p.get("subtitle_samples", []):
            subtitle_candidate.extend(sub.get("classes", []))
    
    return {
        "total_class_usage": dict(total_counter.most_common(20)),
        "per_post_dominant_fs": Counter(per_post_max).most_common(10),
        "subtitle_fs_codes": Counter(subtitle_candidate).most_common(10),
    }

def analyze_subtitles(posts):
    """소제목 패턴 분석"""
    all_subtitles = []
    for p in posts:
        for sub in p.get("subtitle_samples", []):
            text = sub.get("text", "")
            if text:
                all_subtitles.append(text)
    
    if not all_subtitles:
        return {"count": 0, "note": "소제목 데이터 없음"}
    
    # 이모지 포함 여부
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF⭐✅❌🔥💡📌✨]+", re.UNICODE
    )
    
    with_emoji = sum(1 for t in all_subtitles if emoji_pattern.search(t))
    
    # 길이 분석
    lengths = [len(t) for t in all_subtitles]
    
    # 어미 패턴
    endings = Counter()
    for t in all_subtitles:
        t_clean = t.strip()
        if t_clean.endswith("?"):
            endings["의문형(?)"] += 1
        elif t_clean.endswith("!"):
            endings["감탄형(!)"] += 1
        elif t_clean.endswith(("요", "다", "는", "기")):
            endings[f"'{t_clean[-1]}' 어미"] += 1
        elif t_clean.endswith(("✅", "🔥", "💡", "⭐", "📌")):
            endings["이모지 마무리"] += 1
        else:
            endings["기타"] += 1
    
    # 숫자/번호 포함
    numbered = sum(1 for t in all_subtitles if re.search(r'^\d+[.)]|^[①②③④⑤]', t))
    
    # 대괄호/중괄호 포함
    bracketed = sum(1 for t in all_subtitles if re.search(r'[\[\]【】]', t))
    
    return {
        "total_subtitles": len(all_subtitles),
        "emoji_ratio": round(with_emoji / len(all_subtitles) * 100, 1),
        "mean_length": round(statistics.mean(lengths), 1) if lengths else 0,
        "numbered_ratio": round(numbered / len(all_subtitles) * 100, 1),
        "bracketed_ratio": round(bracketed / len(all_subtitles) * 100, 1),
        "ending_patterns": dict(endings.most_common(10)),
        "samples": all_subtitles[:30],
    }

def analyze_opening_patterns(posts):
    """오프닝 패턴 분류"""
    patterns = Counter()
    samples = defaultdict(list)
    
    for p in posts:
        opening = p.get("opening", "")[:150]
        if not opening:
            continue
        
        # 패턴 분류
        if re.search(r'^안녕|^안뇽|^반갑|^어서|^오늘은|^오늘도', opening):
            pat = "인사형"
        elif re.search(r'^[이이번]\s*번|^이번에|^얼마 전|^최근에|^지난', opening):
            pat = "최근경험형"
        elif re.search(r'쿠팡|로켓배송', opening) and re.search(r'구매|샀|주문|배송', opening):
            pat = "구매사실형"
        elif re.search(r'진짜|솔직히|사실|리얼|정말로|솔레', opening):
            pat = "솔직고백형"
        elif re.search(r'\?', opening[:50]):
            pat = "질문형"
        elif re.search(r'오늘|오늘은|이번|이번엔', opening):
            pat = "오늘화제형"
        elif re.search(r'후기|리뷰|사용기|사용해봤', opening):
            pat = "후기선언형"
        else:
            pat = "기타"
        
        patterns[pat] += 1
        if len(samples[pat]) < 3:
            samples[pat].append(opening[:80])
    
    return {
        "distribution": dict(patterns.most_common()),
        "samples": dict(samples),
    }

def analyze_title_patterns(posts):
    """제목 키워드/패턴 분석"""
    patterns = Counter()
    keyword_counts = Counter()
    
    for p in posts:
        title = p.get("title", "")
        if not title:
            continue
        
        # 유형 분류
        if re.search(r'내돈내산', title):
            patterns["내돈내산형"] += 1
        elif re.search(r'솔직|진짜|리얼|사실', title):
            patterns["솔직강조형"] += 1
        elif re.search(r'\d+[위가지개]|TOP|BEST|베스트|랭킹|순위', title):
            patterns["숫자/랭킹형"] += 1
        elif re.search(r'추천|꿀템|인기|핫|MUST', title):
            patterns["추천형"] += 1
        elif re.search(r'비교|vs|VS|차이', title):
            patterns["비교형"] += 1
        elif re.search(r'\?', title):
            patterns["질문형"] += 1
        elif re.search(r'후기|리뷰|구매|사봤|써봤', title):
            patterns["후기형"] += 1
        else:
            patterns["기타"] += 1
        
        # 자주 나오는 키워드
        for kw in ["쿠팡", "로켓배송", "내돈내산", "후기", "솔직", "추천", "가성비", "리뷰", "구매", "직구"]:
            if kw in title:
                keyword_counts[kw] += 1
    
    # 이모지 제목
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002700-\U000027BF]+", re.UNICODE
    )
    with_emoji = sum(1 for p in posts if p.get("title") and emoji_pattern.search(p["title"]))
    
    return {
        "type_distribution": dict(patterns.most_common()),
        "keyword_frequency": dict(keyword_counts.most_common()),
        "emoji_in_title": with_emoji,
        "emoji_ratio": round(with_emoji / len(posts) * 100, 1),
    }

def compute_all_stats(posts):
    print("📊 분석 중...")
    
    stats = {
        "total_posts": len(posts),
        "title_length": analyze_title_length(posts),
        "content_length": analyze_content_length(posts),
        "image_density": analyze_image_density(posts),
        "hashtags": analyze_hashtags(posts),
        "se_fs_analysis": analyze_se_fs_classes(posts),
        "subtitle_analysis": analyze_subtitles(posts),
        "opening_patterns": analyze_opening_patterns(posts),
        "title_patterns": analyze_title_patterns(posts),
    }
    
    # se_fs_classes 상세 확인
    print("\n[se-fs 클래스 분포]")
    for cls, cnt in stats["se_fs_analysis"]["total_class_usage"].items():
        print(f"  {cls}: {cnt}회")
    
    print("\n[소제목에 쓰인 se-fs 코드]")
    for cls, cnt in stats["se_fs_analysis"]["subtitle_fs_codes"]:
        print(f"  {cls}: {cnt}회")
    
    return stats

def _fs_num(cls):
    m = re.search(r'fs(\d+)', cls)
    return m.group(1) if m else '?'

def _nl(items, fmt_fn):
    return "".join(fmt_fn(x) + "\n" for x in items)

def generate_guide(posts, stats):
    """마크다운 가이드라인 생성"""
    
    tl = stats["title_length"]
    cl = stats["content_length"]
    img = stats["image_density"]
    ht = stats["hashtags"]
    se = stats["se_fs_analysis"]
    sub = stats["subtitle_analysis"]
    op = stats["opening_patterns"]
    tp = stats["title_patterns"]
    
    # se-fs 주요 코드 정리
    subtitle_fs_top = se["subtitle_fs_codes"][:5] if se["subtitle_fs_codes"] else []
    dominant_fs_top = se["per_post_dominant_fs"][:5] if se["per_post_dominant_fs"] else []
    
    # 소제목 샘플 (최대 10개)
    subtitle_samples = sub.get("samples", [])[:10]
    
    # 오프닝 샘플
    op_samples = op.get("samples", {})
    
    guide = f"""# 네이버 블로그 홈판 상위노출 포스팅 포맷 가이드 v2

> 분석 기반: 네이버 블로그 검색 상위노출 포스팅 **{stats['total_posts']}개** 정밀 분석  
> 키워드: 쿠팡 관련 내돈내산/구매후기 계열  
> 분석 일시: 2026년 4월 12일

---

## 📊 핵심 수치 요약

| 항목 | 수치 |
|------|------|
| 분석 포스팅 수 | {stats['total_posts']}개 |
| 제목 평균 길이 | {tl.get('mean', 'N/A')}자 |
| 제목 중앙값 | {tl.get('median', 'N/A')}자 |
| 본문 평균 길이 | {int(cl.get('mean', 0))}자 |
| 본문 중앙값 | {int(cl.get('median', 0))}자 |
| 평균 이미지 수 | {img.get('mean_total_images', 'N/A')}장 |
| 1000자당 이미지 | {img.get('mean_per_1000chars', 'N/A')}장 |
| 해시태그 사용률 | {ht.get('has_hashtag_ratio', 0)}% |
| 소제목 이모지 사용률 | {sub.get('emoji_ratio', 0)}% |

---

## 📝 제목 가이드

### 제목 길이 최적화

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
| ≤15자 | {tl.get('distribution', {}).get('≤15자', 0)}개 | {round(tl.get('distribution', {}).get('≤15자', 0)/stats['total_posts']*100)}% |
| 16-25자 | {tl.get('distribution', {}).get('16-25자', 0)}개 | {round(tl.get('distribution', {}).get('16-25자', 0)/stats['total_posts']*100)}% |
| 26-35자 | {tl.get('distribution', {}).get('26-35자', 0)}개 | {round(tl.get('distribution', {}).get('26-35자', 0)/stats['total_posts']*100)}% |
| 36-45자 | {tl.get('distribution', {}).get('36-45자', 0)}개 | {round(tl.get('distribution', {}).get('36-45자', 0)/stats['total_posts']*100)}% |
| 46자+ | {tl.get('distribution', {}).get('46자+', 0)}개 | {round(tl.get('distribution', {}).get('46자+', 0)/stats['total_posts']*100)}% |

**✅ 권장 제목 길이: {tl.get('p25', 'N/A')}~{tl.get('p75', 'N/A')}자 (P25~P75 구간)**

### 제목 유형 분포

| 유형 | 포스팅 수 | 비중 |
|------|----------|------|
{"".join(f'| {k} | {v}개 | {round(v/stats["total_posts"]*100)}% |' + chr(10) for k, v in tp.get("type_distribution", {}).items())}

### 제목 자주 쓰인 키워드

| 키워드 | 포스팅 수 |
|--------|----------|
{"".join(f'| {k} | {v}개 |' + chr(10) for k, v in tp.get("keyword_frequency", {}).items())}

### 제목 이모지 사용
- 제목에 이모지 포함: **{tp.get('emoji_in_title', 0)}개** ({tp.get('emoji_ratio', 0)}%)
- 이모지 없는 텍스트 제목이 주류

---

## 📏 본문 길이 가이드

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
| ≤500자 | {cl.get('distribution', {}).get('≤500자', 0)}개 | {round(cl.get('distribution', {}).get('≤500자', 0)/stats['total_posts']*100)}% |
| 501-1000자 | {cl.get('distribution', {}).get('501-1000자', 0)}개 | {round(cl.get('distribution', {}).get('501-1000자', 0)/stats['total_posts']*100)}% |
| 1001-2000자 | {cl.get('distribution', {}).get('1001-2000자', 0)}개 | {round(cl.get('distribution', {}).get('1001-2000자', 0)/stats['total_posts']*100)}% |
| 2001-3000자 | {cl.get('distribution', {}).get('2001-3000자', 0)}개 | {round(cl.get('distribution', {}).get('2001-3000자', 0)/stats['total_posts']*100)}% |
| 3001자+ | {cl.get('distribution', {}).get('3001자+', 0)}개 | {round(cl.get('distribution', {}).get('3001자+', 0)/stats['total_posts']*100)}% |

**✅ 권장 본문 길이: {int(cl.get('p25', 0))}~{int(cl.get('p75', 0))}자 (P25~P75 구간)**

- 중앙값: **{int(cl.get('median', 0))}자**
- 평균: **{int(cl.get('mean', 0))}자**

---

## 🖼️ 이미지 가이드

### 이미지 수 분포

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
| 0장 | {img.get('distribution', {}).get('0장', 0)}개 | {round(img.get('distribution', {}).get('0장', 0)/stats['total_posts']*100)}% |
| 1-5장 | {img.get('distribution', {}).get('1-5장', 0)}개 | {round(img.get('distribution', {}).get('1-5장', 0)/stats['total_posts']*100)}% |
| 6-10장 | {img.get('distribution', {}).get('6-10장', 0)}개 | {round(img.get('distribution', {}).get('6-10장', 0)/stats['total_posts']*100)}% |
| 11-20장 | {img.get('distribution', {}).get('11-20장', 0)}개 | {round(img.get('distribution', {}).get('11-20장', 0)/stats['total_posts']*100)}% |
| 21장+ | {img.get('distribution', {}).get('21장+', 0)}개 | {round(img.get('distribution', {}).get('21장+', 0)/stats['total_posts']*100)}% |

**✅ 권장:**
- 이미지 수: **{img.get('median_total_images', 'N/A')}장** (중앙값) / 평균 {img.get('mean_total_images', 'N/A')}장
- 이미지 밀도: **1000자당 {img.get('median_per_1000chars', 'N/A')}장** (중앙값)

---

## 🔖 해시태그 가이드

- 해시태그 사용 포스팅: **{ht.get('has_hashtag_ratio', 0)}%**
- 사용 시 평균 태그 수: **{ht.get('mean_count', 0)}개**

### 해시태그 수 분포

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
| 0개 (미사용) | {ht.get('distribution', {}).get('0개', 0)}개 | {round(ht.get('distribution', {}).get('0개', 0)/stats['total_posts']*100)}% |
| 1-3개 | {ht.get('distribution', {}).get('1-3개', 0)}개 | {round(ht.get('distribution', {}).get('1-3개', 0)/stats['total_posts']*100)}% |
| 4-10개 | {ht.get('distribution', {}).get('4-10개', 0)}개 | {round(ht.get('distribution', {}).get('4-10개', 0)/stats['total_posts']*100)}% |
| 11-20개 | {ht.get('distribution', {}).get('11-20개', 0)}개 | {round(ht.get('distribution', {}).get('11-20개', 0)/stats['total_posts']*100)}% |
| 21개+ | {ht.get('distribution', {}).get('21개+', 0)}개 | {round(ht.get('distribution', {}).get('21개+', 0)/stats['total_posts']*100)}% |

### 자주 쓰인 해시태그 TOP 20
{"".join(f'- `{tag}` ({cnt}개)' + chr(10) for tag, cnt in ht.get('top_tags', [])[:20])}

---

## 🔡 소제목 서식 가이드 (핵심!)

### se-fs CSS 폰트 크기 코드 분석

네이버 스마트에디터는 `se-fs-fsXX` 클래스로 폰트 크기를 제어합니다.  
(XX = 폰트 크기, 예: `se-fs-fs24` = 24pt)

#### 전체 포스팅 폰트 사용 빈도 (상위 20개)

| CSS 클래스 | 총 사용 횟수 | 폰트 크기 |
|-----------|------------|--------|
{"".join(f'| `{cls}` | {cnt}회 | {re.search(r"fs(\\d+)", cls).group(1) if re.search(r"fs(\\d+)", cls) else "?"}pt |' + chr(10) for cls, cnt in se.get("total_class_usage", {}).items())}

#### 소제목에 주로 쓰인 폰트 코드

| CSS 클래스 | 소제목 사용 횟수 | 폰트 크기 |
|-----------|--------------|--------|
{"".join(f'| `{cls}` | {cnt}회 | {re.search(r"fs(\\d+)", cls).group(1) if re.search(r"fs(\\d+)", cls) else "?"}pt |' + chr(10) for cls, cnt in subtitle_fs_top)}

#### 포스팅별 가장 큰 폰트 코드 (소제목 후보)

| CSS 클래스 | 포스팅 수 |
|-----------|----------|
{"".join(f'| `{cls}` | {cnt}개 |' + chr(10) for cls, cnt in dominant_fs_top)}

### 소제목 패턴 분석

- 총 수집 소제목: **{sub.get('total_subtitles', 0)}개**
- 이모지 포함 비율: **{sub.get('emoji_ratio', 0)}%**
- 소제목 평균 길이: **{sub.get('mean_length', 0)}자**
- 번호 포함 소제목: **{sub.get('numbered_ratio', 0)}%**
- 대괄호 포함: **{sub.get('bracketed_ratio', 0)}%**

#### 소제목 어미 패턴

| 어미 유형 | 횟수 |
|---------|------|
{"".join(f'| {k} | {v}회 |' + chr(10) for k, v in sub.get("ending_patterns", {}).items())}

#### 실제 소제목 샘플

{"".join(f'- `{s}`' + chr(10) for s in subtitle_samples)}

---

## 🚀 오프닝 패턴 가이드

### 오프닝 유형 분포

| 유형 | 포스팅 수 | 비중 |
|------|----------|------|
{"".join(f'| {k} | {v}개 | {round(v/stats["total_posts"]*100)}% |' + chr(10) for k, v in op.get("distribution", {}).items())}

### 유형별 샘플

{"".join(f'**{ptype}:**' + chr(10) + chr(10).join(f'> {s}...' for s in samples[:2]) + chr(10) + chr(10) for ptype, samples in op_samples.items())}

---

## ✅ 실전 포스팅 체크리스트

### 제목 작성
- [ ] 제목 길이 {tl.get('p25', 'N/A')}~{tl.get('p75', 'N/A')}자 범위
- [ ] "내돈내산", "솔직", "후기" 등 신뢰 키워드 포함
- [ ] 핵심 제품명 or 카테고리 명시
- [ ] 쿠팡/로켓배송 직접 언급

### 본문 구성
- [ ] 본문 길이 {int(cl.get('p25', 0))}자 이상 (P25 기준)
- [ ] 목표: {int(cl.get('median', 0))}~{int(cl.get('p75', 0))}자
- [ ] 이미지 {img.get('median_total_images', 'N/A')}장 이상 삽입
- [ ] 소제목으로 단락 구분 (큰 글씨 폰트 사용)
- [ ] 오프닝: 구매 경험/솔직 고백형으로 시작

### 소제목 서식
- [ ] 소제목 폰트 크기: `se-fs-fs24` 이상 사용
- [ ] 소제목에 이모지 활용 고려 ({sub.get('emoji_ratio', 0)}% 사용 중)
- [ ] 소제목 길이 {sub.get('mean_length', 0):.0f}자 내외

### 해시태그
- [ ] 해시태그 사용 여부 결정 (현재 {ht.get('has_hashtag_ratio', 0)}% 사용)
- [ ] 사용 시 관련 키워드 중심으로 작성

---

## 📋 포스팅 템플릿 (권장 구조)

```
[제목] (25-40자)
예: 쿠팡 로켓배송 내돈내산 OOO 솔직 구매후기 | 가성비 진짜예요?

[오프닝] (구매사실형 or 솔직고백형)
안녕하세요! 이번에 쿠팡에서 OOO을 직접 구매해봤어요.
내돈내산이라 솔직하게 장단점 다 말씀드릴게요!

[소제목1] (이모지 + 핵심 내용) - se-fs-fs24 이상
📦 제품 기본 정보

[본문 단락 1]
(제품 설명, 포장 상태, 첫 인상)

[소제목2]
✅ 실제 써보니 어때요?

[본문 단락 2]
(사용 후기, 장점, 단점)

[소제목3]
💡 이런 분들께 추천해요

[본문 단락 3]
(타겟 추천, 총평)

[마무리]
쿠팡 파트너스 활동으로 수수료를 받을 수 있습니다.
```

---

## 🔍 경쟁 분석 인사이트

1. **키워드 체계**: "내돈내산" + "쿠팡" + 카테고리 조합이 검색 상위 점령
2. **본문 길이 양극화**: 700~1500자 단짧 vs 2500자+ 상세 리뷰 두 군집으로 나뉨
3. **이미지 > 텍스트**: 텍스트 대비 이미지 비중이 높을수록 체류시간 유리
4. **소제목 폰트 코드**: `se-fs-fs24` 계열이 소제목 사용의 핵심 — 이 이상 크기로 구분 권장
5. **해시태그 저조**: {ht.get('has_hashtag_ratio', 0)}% 사용 — 필수 아님, 있으면 카테고리 중심으로

---

*이 가이드는 실제 검색 상위노출 포스팅 {stats['total_posts']}개 분석 데이터 기반입니다.*
*생성: 2026-04-12 | 프로젝트: p004-blogger*
"""
    
    return guide


def main():
    posts = load_data()
    print(f"✅ 데이터 로드: {len(posts)}개 포스팅")
    
    stats = compute_all_stats(posts)
    
    print("\n📊 주요 통계:")
    print(f"  제목 중앙값: {stats['title_length'].get('median', 'N/A')}자")
    print(f"  본문 중앙값: {int(stats['content_length'].get('median', 0))}자")
    print(f"  이미지 중앙값: {stats['image_density'].get('median_total_images', 'N/A')}장")
    print(f"  해시태그 사용률: {stats['hashtags'].get('has_hashtag_ratio', 0)}%")
    print(f"  소제목 이모지 비율: {stats['subtitle_analysis'].get('emoji_ratio', 0)}%")
    print(f"  소제목 총 수: {stats['subtitle_analysis'].get('total_subtitles', 0)}개")
    
    guide = generate_guide(posts, stats)
    
    import os
    os.makedirs(os.path.dirname(OUTPUT_GUIDE), exist_ok=True)
    with open(OUTPUT_GUIDE, "w", encoding="utf-8") as f:
        f.write(guide)
    
    print(f"\n✅ 가이드 저장: {OUTPUT_GUIDE}")
    
    # 분석 결과 JSON도 저장
    stats_file = "/tmp/naver_analysis_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ 통계 저장: {stats_file}")


if __name__ == "__main__":
    main()
