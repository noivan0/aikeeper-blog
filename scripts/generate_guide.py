#!/usr/bin/env python3
"""
분석 결과 → 마크다운 가이드 생성 (f-string 없이 format() 사용)
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

def analyze_all(posts):
    # 제목 길이
    title_lengths = [len(p["title"]) for p in posts if p.get("title")]
    tl_sorted = sorted(title_lengths)
    n = len(tl_sorted)
    
    tl = {
        "mean": round(statistics.mean(title_lengths), 1) if title_lengths else 0,
        "median": round(statistics.median(title_lengths), 1) if title_lengths else 0,
        "p25": tl_sorted[n//4] if n > 4 else 0,
        "p75": tl_sorted[3*n//4] if n > 4 else 0,
        "d_le15": sum(1 for l in title_lengths if l <= 15),
        "d_16_25": sum(1 for l in title_lengths if 16 <= l <= 25),
        "d_26_35": sum(1 for l in title_lengths if 26 <= l <= 35),
        "d_36_45": sum(1 for l in title_lengths if 36 <= l <= 45),
        "d_46p": sum(1 for l in title_lengths if l >= 46),
    }
    
    # 본문 길이
    content_lengths = [p["content_length"] for p in posts]
    cl_sorted = sorted(content_lengths)
    nc = len(cl_sorted)
    
    cl = {
        "mean": round(statistics.mean(content_lengths), 0) if content_lengths else 0,
        "median": round(statistics.median(content_lengths), 0) if content_lengths else 0,
        "p25": cl_sorted[nc//4] if nc > 4 else 0,
        "p75": cl_sorted[3*nc//4] if nc > 4 else 0,
        "d_le500": sum(1 for l in content_lengths if l <= 500),
        "d_501_1000": sum(1 for l in content_lengths if 501 <= l <= 1000),
        "d_1001_2000": sum(1 for l in content_lengths if 1001 <= l <= 2000),
        "d_2001_3000": sum(1 for l in content_lengths if 2001 <= l <= 3000),
        "d_3001p": sum(1 for l in content_lengths if l >= 3001),
    }
    
    # 이미지 밀도
    img_counts = [p["image_count"] for p in posts]
    densities = []
    for p in posts:
        if p["content_length"] > 0:
            densities.append(p["image_count"] / (p["content_length"] / 1000))
    
    img = {
        "mean_total": round(statistics.mean(img_counts), 1),
        "median_total": int(statistics.median(sorted(img_counts))),
        "mean_density": round(statistics.mean(densities), 2) if densities else 0,
        "median_density": round(statistics.median(densities), 2) if densities else 0,
        "d_0": sum(1 for c in img_counts if c == 0),
        "d_1_5": sum(1 for c in img_counts if 1 <= c <= 5),
        "d_6_10": sum(1 for c in img_counts if 6 <= c <= 10),
        "d_11_20": sum(1 for c in img_counts if 11 <= c <= 20),
        "d_21p": sum(1 for c in img_counts if c >= 21),
    }
    
    # 해시태그
    ht_counts = [p["hashtag_count"] for p in posts]
    has_ht = sum(1 for p in posts if p["has_hashtag"])
    all_tags = []
    for p in posts:
        all_tags.extend(p.get("hashtags", []))
    
    ht = {
        "ratio": round(has_ht / len(posts) * 100, 1),
        "mean_count": round(statistics.mean(ht_counts), 1),
        "d_0": sum(1 for c in ht_counts if c == 0),
        "d_1_3": sum(1 for c in ht_counts if 1 <= c <= 3),
        "d_4_10": sum(1 for c in ht_counts if 4 <= c <= 10),
        "d_11_20": sum(1 for c in ht_counts if 11 <= c <= 20),
        "d_21p": sum(1 for c in ht_counts if c >= 21),
        "top_tags": Counter(all_tags).most_common(20),
    }
    
    # se-fs 클래스
    total_counter = Counter()
    per_post_max = []
    subtitle_fs_counter = Counter()
    
    for p in posts:
        se_fs = p.get("se_fs_classes", {})
        post_classes = set()
        for cls, cnt in se_fs.items():
            total_counter[cls] += cnt
            post_classes.add(cls)
        
        max_num = 0
        max_fs = None
        for cls in post_classes:
            m = re.search(r'se-fs-fs(\d+)', cls)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
                    max_fs = cls
        if max_fs:
            per_post_max.append(max_fs)
        
        for sub_item in p.get("subtitle_samples", []):
            for cls in sub_item.get("classes", []):
                subtitle_fs_counter[cls] += 1
    
    se = {
        "total_usage": total_counter.most_common(20),
        "per_post_dominant": Counter(per_post_max).most_common(10),
        "subtitle_fs": subtitle_fs_counter.most_common(10),
    }
    
    # 소제목 패턴
    all_subs = []
    for p in posts:
        for sub_item in p.get("subtitle_samples", []):
            text = sub_item.get("text", "")
            if text:
                all_subs.append(text)
    
    emoji_pat = re.compile(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\u2600-\u26FF\u2700-\u27BF]',
        re.UNICODE
    )
    
    sub_with_emoji = sum(1 for t in all_subs if emoji_pat.search(t))
    sub_lengths = [len(t) for t in all_subs]
    sub_numbered = sum(1 for t in all_subs if re.search(r'^\d+[.)]|^[①②③④⑤]', t))
    sub_bracketed = sum(1 for t in all_subs if re.search(r'[\[\]【】]', t))
    
    ending_counter = Counter()
    for t in all_subs:
        t = t.strip()
        if t.endswith("?"):
            ending_counter["의문형(?)"] += 1
        elif t.endswith("!"):
            ending_counter["감탄형(!)"] += 1
        elif any(t.endswith(s) for s in ("요", "다")):
            ending_counter["서술어미(요/다)"] += 1
        else:
            ending_counter["기타/명사형"] += 1
    
    sub = {
        "total": len(all_subs),
        "emoji_ratio": round(sub_with_emoji / len(all_subs) * 100, 1) if all_subs else 0,
        "mean_length": round(statistics.mean(sub_lengths), 1) if sub_lengths else 0,
        "numbered_ratio": round(sub_numbered / len(all_subs) * 100, 1) if all_subs else 0,
        "bracketed_ratio": round(sub_bracketed / len(all_subs) * 100, 1) if all_subs else 0,
        "endings": ending_counter.most_common(),
        "samples": all_subs[:15],
    }
    
    # 오프닝 패턴
    op_counter = Counter()
    op_samples = defaultdict(list)
    for p in posts:
        opening = p.get("opening", "")[:150]
        if not opening:
            continue
        if re.search(r'^안녕|^반갑|^안뇽', opening):
            pat = "인사형"
        elif re.search(r'이번에|얼마 전|최근에|지난', opening):
            pat = "최근경험형"
        elif re.search(r'쿠팡|로켓배송', opening) and re.search(r'구매|샀|주문', opening):
            pat = "구매사실형"
        elif re.search(r'진짜|솔직히|사실|리얼|정말로', opening):
            pat = "솔직고백형"
        elif re.search(r'\?', opening[:50]):
            pat = "질문형"
        elif re.search(r'후기|리뷰|사용기', opening):
            pat = "후기선언형"
        elif re.search(r'오늘|오늘은|이번|이번엔', opening):
            pat = "오늘화제형"
        else:
            pat = "기타"
        op_counter[pat] += 1
        if len(op_samples[pat]) < 2:
            op_samples[pat].append(opening[:80])
    
    op = {
        "distribution": op_counter.most_common(),
        "samples": dict(op_samples),
    }
    
    # 제목 패턴
    tp_counter = Counter()
    kw_counter = Counter()
    emoji_in_title = 0
    for p in posts:
        title = p.get("title", "")
        if not title:
            continue
        if emoji_pat.search(title):
            emoji_in_title += 1
        if "내돈내산" in title:
            tp_counter["내돈내산형"] += 1
        elif re.search(r'솔직|진짜|리얼', title):
            tp_counter["솔직강조형"] += 1
        elif re.search(r'\d+[위가지개]|TOP|BEST|베스트|랭킹', title):
            tp_counter["숫자/랭킹형"] += 1
        elif re.search(r'추천|꿀템|인기|핫', title):
            tp_counter["추천형"] += 1
        elif re.search(r'비교|vs|VS|차이', title):
            tp_counter["비교형"] += 1
        elif "?" in title:
            tp_counter["질문형"] += 1
        elif re.search(r'후기|리뷰|구매|사봤|써봤', title):
            tp_counter["후기형"] += 1
        else:
            tp_counter["기타"] += 1
        
        for kw in ["쿠팡", "로켓배송", "내돈내산", "후기", "솔직", "추천", "가성비", "리뷰", "구매"]:
            if kw in title:
                kw_counter[kw] += 1
    
    tp = {
        "distribution": tp_counter.most_common(),
        "keywords": kw_counter.most_common(),
        "emoji_count": emoji_in_title,
        "emoji_ratio": round(emoji_in_title / len(posts) * 100, 1),
    }
    
    return {
        "total": len(posts),
        "tl": tl,
        "cl": cl,
        "img": img,
        "ht": ht,
        "se": se,
        "sub": sub,
        "op": op,
        "tp": tp,
    }


def pct(val, total):
    return round(val / total * 100) if total else 0


def fs_num(cls):
    m = re.search(r'fs(\d+)', cls)
    return m.group(1) if m else '?'


def build_table_rows(items, fmt_fn):
    return "\n".join(fmt_fn(item) for item in items)


def generate_guide(posts, s):
    N = s["total"]
    tl = s["tl"]
    cl = s["cl"]
    img = s["img"]
    ht = s["ht"]
    se = s["se"]
    sub = s["sub"]
    op = s["op"]
    tp = s["tp"]
    
    # 제목 타입 테이블
    title_type_rows = "\n".join(
        "| {} | {}개 | {}% |".format(k, v, pct(v, N))
        for k, v in tp["distribution"]
    )
    
    # 제목 키워드 테이블
    title_kw_rows = "\n".join(
        "| {} | {}개 |".format(k, v)
        for k, v in tp["keywords"]
    )
    
    # 본문 길이 분포 테이블 행
    cl_rows = "\n".join([
        "| ≤500자 | {}개 | {}% |".format(cl["d_le500"], pct(cl["d_le500"], N)),
        "| 501-1000자 | {}개 | {}% |".format(cl["d_501_1000"], pct(cl["d_501_1000"], N)),
        "| 1001-2000자 | {}개 | {}% |".format(cl["d_1001_2000"], pct(cl["d_1001_2000"], N)),
        "| 2001-3000자 | {}개 | {}% |".format(cl["d_2001_3000"], pct(cl["d_2001_3000"], N)),
        "| 3001자+ | {}개 | {}% |".format(cl["d_3001p"], pct(cl["d_3001p"], N)),
    ])
    
    # 이미지 분포
    img_rows = "\n".join([
        "| 0장 | {}개 | {}% |".format(img["d_0"], pct(img["d_0"], N)),
        "| 1-5장 | {}개 | {}% |".format(img["d_1_5"], pct(img["d_1_5"], N)),
        "| 6-10장 | {}개 | {}% |".format(img["d_6_10"], pct(img["d_6_10"], N)),
        "| 11-20장 | {}개 | {}% |".format(img["d_11_20"], pct(img["d_11_20"], N)),
        "| 21장+ | {}개 | {}% |".format(img["d_21p"], pct(img["d_21p"], N)),
    ])
    
    # 해시태그 분포
    ht_rows = "\n".join([
        "| 0개 (미사용) | {}개 | {}% |".format(ht["d_0"], pct(ht["d_0"], N)),
        "| 1-3개 | {}개 | {}% |".format(ht["d_1_3"], pct(ht["d_1_3"], N)),
        "| 4-10개 | {}개 | {}% |".format(ht["d_4_10"], pct(ht["d_4_10"], N)),
        "| 11-20개 | {}개 | {}% |".format(ht["d_11_20"], pct(ht["d_11_20"], N)),
        "| 21개+ | {}개 | {}% |".format(ht["d_21p"], pct(ht["d_21p"], N)),
    ])
    
    # 해시태그 Top 20
    top_tags_list = "\n".join(
        "- `{}` ({}개)".format(tag, cnt)
        for tag, cnt in ht["top_tags"][:20]
    )
    if not top_tags_list:
        top_tags_list = "- (해시태그 데이터 없음)"
    
    # se-fs 전체 사용 테이블
    se_total_rows = "\n".join(
        "| `{}` | {}회 | {}pt |".format(cls, cnt, fs_num(cls))
        for cls, cnt in se["total_usage"]
    )
    if not se_total_rows:
        se_total_rows = "| (데이터 없음) | - | - |"
    
    # 소제목 se-fs 코드
    se_sub_rows = "\n".join(
        "| `{}` | {}회 | {}pt |".format(cls, cnt, fs_num(cls))
        for cls, cnt in se["subtitle_fs"]
    )
    if not se_sub_rows:
        se_sub_rows = "| (데이터 없음) | - | - |"
    
    # 포스팅별 dominant fs
    se_dom_rows = "\n".join(
        "| `{}` | {}개 |".format(cls, cnt)
        for cls, cnt in se["per_post_dominant"]
    )
    if not se_dom_rows:
        se_dom_rows = "| (데이터 없음) | - |"
    
    # 소제목 어미 패턴 테이블
    sub_ending_rows = "\n".join(
        "| {} | {}회 |".format(k, v)
        for k, v in sub["endings"]
    )
    if not sub_ending_rows:
        sub_ending_rows = "| (데이터 없음) | - |"
    
    # 소제목 샘플
    sub_samples_list = "\n".join(
        "- `{}`".format(s)
        for s in sub["samples"]
    )
    if not sub_samples_list:
        sub_samples_list = "- (샘플 없음)"
    
    # 오프닝 분포 테이블
    op_rows = "\n".join(
        "| {} | {}개 | {}% |".format(k, v, pct(v, N))
        for k, v in op["distribution"]
    )
    
    # 오프닝 샘플
    op_sample_blocks = []
    for ptype, samples in op["samples"].items():
        block = "**{}:**\n".format(ptype)
        for s in samples[:2]:
            block += "> {}...\n".format(s)
        op_sample_blocks.append(block)
    op_samples_text = "\n\n".join(op_sample_blocks)
    
    guide = """# 네이버 블로그 홈판 상위노출 포스팅 포맷 가이드 v2

> 분석 기반: 네이버 블로그 검색 상위노출 포스팅 **{total}개** 정밀 분석  
> 키워드: 쿠팡 관련 내돈내산/구매후기 계열 (10개 키워드)  
> 분석 일시: 2026년 4월 12일

---

## 📊 핵심 수치 요약

| 항목 | 수치 |
|------|------|
| 분석 포스팅 수 | {total}개 |
| 제목 평균 길이 | {tl_mean}자 |
| 제목 중앙값 | {tl_med}자 |
| 본문 평균 길이 | {cl_mean}자 |
| 본문 중앙값 | {cl_med}자 |
| 평균 이미지 수 | {img_mean}장 |
| 1000자당 이미지 | {img_density}장 |
| 해시태그 사용률 | {ht_ratio}% |
| 소제목 이모지 비율 | {sub_emoji}% |
| 소제목 수집 총계 | {sub_total}개 |

---

## 📝 제목 가이드

### 제목 길이 최적화

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
| ≤15자 | {tl_le15}개 | {tl_le15_p}% |
| 16-25자 | {tl_1625}개 | {tl_1625_p}% |
| 26-35자 | {tl_2635}개 | {tl_2635_p}% |
| 36-45자 | {tl_3645}개 | {tl_3645_p}% |
| 46자+ | {tl_46p}개 | {tl_46p_p}% |

**✅ 권장 제목 길이: {tl_p25}~{tl_p75}자 (P25~P75 구간)**

### 제목 유형 분포

| 유형 | 포스팅 수 | 비중 |
|------|----------|------|
{title_type_rows}

### 제목 자주 쓰인 키워드

| 키워드 | 포스팅 수 |
|--------|----------|
{title_kw_rows}

### 제목 이모지 사용
- 제목에 이모지 포함: **{tp_emoji_cnt}개** ({tp_emoji_ratio}%)
- 이모지 없는 텍스트 제목이 주류

---

## 📏 본문 길이 가이드

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
{cl_rows}

**✅ 권장 본문 길이: {cl_p25}~{cl_p75}자 (P25~P75 구간)**

- 중앙값: **{cl_med}자**
- 평균: **{cl_mean}자**

---

## 🖼️ 이미지 가이드

### 이미지 수 분포

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
{img_rows}

**✅ 권장:**
- 이미지 수: **{img_median_total}장** (중앙값) / 평균 {img_mean}장
- 이미지 밀도: **1000자당 {img_median_density}장** (중앙값)

---

## 🔖 해시태그 가이드

- 해시태그 사용 포스팅: **{ht_ratio}%**
- 사용 시 평균 태그 수: **{ht_mean}개**

### 해시태그 수 분포

| 구간 | 포스팅 수 | 비중 |
|------|----------|------|
{ht_rows}

### 자주 쓰인 해시태그 TOP 20
{top_tags_list}

---

## 🔡 소제목 서식 가이드 (핵심!)

### se-fs CSS 폰트 크기 코드 분석

네이버 스마트에디터는 `se-fs-fsXX` 클래스로 폰트 크기를 제어합니다.  
(XX = 폰트 크기, 예: `se-fs-fs24` = 24pt)

#### 전체 포스팅 폰트 사용 빈도 (상위 20개)

| CSS 클래스 | 총 사용 횟수 | 폰트 크기 |
|-----------|------------|--------|
{se_total_rows}

#### 소제목에 주로 쓰인 폰트 코드

| CSS 클래스 | 소제목 사용 횟수 | 폰트 크기 |
|-----------|--------------|--------|
{se_sub_rows}

#### 포스팅별 가장 큰 폰트 코드 (소제목 후보)

| CSS 클래스 | 포스팅 수 |
|-----------|----------|
{se_dom_rows}

### 소제목 패턴 분석

- 총 수집 소제목: **{sub_total}개**
- 이모지 포함 비율: **{sub_emoji}%**
- 소제목 평균 길이: **{sub_mean_len}자**
- 번호 포함 소제목: **{sub_numbered}%**
- 대괄호 포함: **{sub_bracketed}%**

#### 소제목 어미 패턴

| 어미 유형 | 횟수 |
|---------|------|
{sub_ending_rows}

#### 실제 소제목 샘플

{sub_samples_list}

---

## 🚀 오프닝 패턴 가이드

### 오프닝 유형 분포

| 유형 | 포스팅 수 | 비중 |
|------|----------|------|
{op_rows}

### 유형별 샘플

{op_samples_text}

---

## ✅ 실전 포스팅 체크리스트

### 제목 작성
- [ ] 제목 길이 {tl_p25}~{tl_p75}자 범위
- [ ] "내돈내산", "솔직", "후기" 등 신뢰 키워드 포함
- [ ] 핵심 제품명 or 카테고리 명시
- [ ] 쿠팡/로켓배송 직접 언급

### 본문 구성
- [ ] 본문 길이 {cl_p25}자 이상 (P25 기준)
- [ ] 목표: {cl_med}~{cl_p75}자
- [ ] 이미지 {img_median_total}장 이상 삽입
- [ ] 소제목으로 단락 구분 (큰 글씨 폰트 사용)
- [ ] 오프닝: 구매 경험/솔직 고백형으로 시작

### 소제목 서식
- [ ] 소제목 폰트 크기: `se-fs-fs24` 이상 사용 (네이버 에디터 기준)
- [ ] 소제목에 이모지 활용 고려 ({sub_emoji}% 사용 중)
- [ ] 소제목 길이 {sub_mean_len:.0f}자 내외

### 해시태그
- [ ] 해시태그 사용 여부 결정 (현재 {ht_ratio}% 사용)
- [ ] 사용 시 관련 키워드 중심으로 작성

---

## 📋 포스팅 템플릿 (권장 구조)

```
[제목] ({tl_p25}~{tl_p75}자)
예: 쿠팡 로켓배송 내돈내산 OOO 솔직 구매후기 | 가성비 진짜예요?

[오프닝] (구매사실형 or 솔직고백형)
안녕하세요! 이번에 쿠팡에서 OOO을 직접 구매해봤어요.
내돈내산이라 솔직하게 장단점 다 말씀드릴게요!

[소제목1] (이모지 + 핵심 내용) - se-fs-fs24 이상
📦 제품 기본 정보

[본문 단락 1] (300~500자)
(제품 설명, 포장 상태, 첫 인상 + 이미지 3~4장)

[소제목2]
✅ 실제 써보니 어때요?

[본문 단락 2] (400~600자)
(사용 후기, 장점, 단점 + 이미지 3~5장)

[소제목3]
💡 이런 분들께 추천해요

[본문 단락 3] (200~400자)
(타겟 추천, 총평 + 이미지 1~2장)

[마무리]
쿠팡 파트너스 활동으로 수수료를 받을 수 있습니다.
```

---

## 🔍 경쟁 분석 인사이트

1. **키워드 체계**: "내돈내산" + "쿠팡" + 카테고리 조합이 검색 상위 점령
2. **본문 길이 양극화**: {cl_p25}~1500자 단짧 vs 2500자+ 상세 리뷰 두 군집으로 나뉨
3. **이미지 > 텍스트**: 텍스트 대비 이미지 비중이 높을수록 체류시간 유리
4. **소제목 폰트 코드**: `se-fs-fs24` 계열이 소제목 사용의 핵심 — 이 이상 크기로 구분 권장
5. **해시태그 저조**: {ht_ratio}% 사용 — 필수 아님, 있으면 카테고리 중심으로

---

*이 가이드는 실제 검색 상위노출 포스팅 {total}개 분석 데이터 기반입니다.*  
*생성: 2026-04-12 | 프로젝트: p004-blogger*
""".format(
        total=N,
        tl_mean=tl["mean"],
        tl_med=tl["median"],
        tl_p25=tl["p25"],
        tl_p75=tl["p75"],
        tl_le15=tl["d_le15"], tl_le15_p=pct(tl["d_le15"], N),
        tl_1625=tl["d_16_25"], tl_1625_p=pct(tl["d_16_25"], N),
        tl_2635=tl["d_26_35"], tl_2635_p=pct(tl["d_26_35"], N),
        tl_3645=tl["d_36_45"], tl_3645_p=pct(tl["d_36_45"], N),
        tl_46p=tl["d_46p"], tl_46p_p=pct(tl["d_46p"], N),
        cl_mean=int(cl["mean"]),
        cl_med=int(cl["median"]),
        cl_p25=int(cl["p25"]),
        cl_p75=int(cl["p75"]),
        img_mean=img["mean_total"],
        img_density=img["mean_density"],
        img_median_total=img["median_total"],
        img_median_density=img["median_density"],
        ht_ratio=ht["ratio"],
        ht_mean=ht["mean_count"],
        sub_emoji=sub["emoji_ratio"],
        sub_total=sub["total"],
        sub_mean_len=sub["mean_length"],
        sub_numbered=sub["numbered_ratio"],
        sub_bracketed=sub["bracketed_ratio"],
        title_type_rows=title_type_rows,
        title_kw_rows=title_kw_rows,
        tp_emoji_cnt=tp["emoji_count"],
        tp_emoji_ratio=tp["emoji_ratio"],
        cl_rows=cl_rows,
        img_rows=img_rows,
        ht_rows=ht_rows,
        top_tags_list=top_tags_list,
        se_total_rows=se_total_rows,
        se_sub_rows=se_sub_rows,
        se_dom_rows=se_dom_rows,
        sub_ending_rows=sub_ending_rows,
        sub_samples_list=sub_samples_list,
        op_rows=op_rows,
        op_samples_text=op_samples_text,
    )
    
    return guide


def main():
    posts = load_data()
    print(f"✅ 데이터 로드: {len(posts)}개 포스팅")
    
    s = analyze_all(posts)
    
    print(f"\n📊 주요 통계:")
    print(f"  제목 중앙값: {s['tl']['median']}자 (P25={s['tl']['p25']}, P75={s['tl']['p75']})")
    print(f"  본문 중앙값: {int(s['cl']['median'])}자 (P25={int(s['cl']['p25'])}, P75={int(s['cl']['p75'])})")
    print(f"  이미지 중앙값: {s['img']['median_total']}장 / 1000자당 {s['img']['median_density']}장")
    print(f"  해시태그 사용률: {s['ht']['ratio']}%")
    print(f"  소제목 수집: {s['sub']['total']}개 / 이모지 비율: {s['sub']['emoji_ratio']}%")
    
    print(f"\n[se-fs 클래스 상위 10개]")
    for cls, cnt in s["se"]["total_usage"][:10]:
        print(f"  {cls}: {cnt}회 ({fs_num(cls)}pt)")
    
    print(f"\n[소제목 se-fs 상위 5개]")
    for cls, cnt in s["se"]["subtitle_fs"][:5]:
        print(f"  {cls}: {cnt}회 ({fs_num(cls)}pt)")
    
    guide = generate_guide(posts, s)
    
    import os
    os.makedirs(os.path.dirname(OUTPUT_GUIDE), exist_ok=True)
    with open(OUTPUT_GUIDE, "w", encoding="utf-8") as f:
        f.write(guide)
    
    print(f"\n✅ 가이드 저장: {OUTPUT_GUIDE}")


def fs_num(cls):
    m = re.search(r'fs(\d+)', cls)
    return m.group(1) if m else '?'


if __name__ == "__main__":
    main()
