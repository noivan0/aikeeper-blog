# ggultongmon 카드뉴스 포맷 스펙 (v6 확정)

> 최종 확정: 2026-04-08  
> 레퍼런스: @dy1.mag, @ai.trend.kr, @growth_recipe, @itsjinakim_academy

---

## 캔버스

- 크기: **1080 × 1080px** (정방형)
- 포맷: JPEG, quality=96
- 슬라이드 수: **8장**

---

## 컬러 시스템

| 역할 | 색상 | HEX |
|---|---|---|
| 배경 | BG | `#0E0E14` |
| 배경 카드1 | BG2 | `#18181E` |
| 배경 카드2 | BG3 | `#222230` |
| 포인트(쿠팡) | ORANGE | `#FF8714` |
| 흰색 | WHITE | `#FFFFFF` |
| 서브텍스트 | GRAY_L | `#A0A0B4` |
| 캡션 | GRAY_M | `#5A5A6E` |
| 구분선 | GRAY_D | `#282838` |
| 2위 컬러 | SILVER | `#B9B9D2` |
| 3위 컬러 | BRONZE | `#AA7828` |

---

## 폰트

- **Bold**: NotoSansCJK-Bold.ttc (index=3, KR)
- **Regular**: NotoSansCJK-Regular.ttc (index=3, KR)

| 용도 | 크기 |
|---|---|
| 메인 타이틀 | 76~78px Bold |
| 섹션 제목 | 54~60px Bold |
| 카드 메인 | 36~42px Bold |
| 본문 | 28~32px Regular |
| 캡션/태그 | 24~26px Bold |
| 슬라이드번호 | 22px Regular |

---

## 레이아웃 원칙

- 좌우 마진: **PAD = 60px** 고정
- 상하 바: **6px** (top/bottom)
- 텍스트 배치: 모든 텍스트 **시각적 수직 중앙** 기준 (`getbbox` top/bottom 평균)
- 폰트 자동 축소: 영역 초과 시 2px씩 축소 (최소 14px)

---

## 슬라이드 구조

| 슬라이드 | 타입 | 내용 |
|---|---|---|
| 01 | 커버 | 카테고리 뱃지 + 상품 3종 이미지 + 메인 제목 + 서브 |
| 02 | 체크리스트 | 구매 전 확인 5가지 카드 |
| 03 | 1위 제품 | 상품 이미지 + 스펙 + 태그 + 평가 |
| 04 | 2위 제품 | 동일 구조 (SILVER 컬러) |
| 05 | 3위 제품 | 동일 구조 (BRONZE 컬러) + warning |
| 06 | 비교표 | 7행 비교 테이블 + 추천 요약 |
| 07 | 핵심 메시지 | 격자 배경 + 2줄 강조 문구 |
| 08 | CTA | 글로우 + 저장 아이콘 + 팔로우 버튼 |

---

## 제품 슬라이드 (03~05) 레이아웃

```
y=6~106   : 순위 헤더 띠 (수직 중앙 텍스트)
y=106~555 : 제품 정보
  - 우측: 상품 이미지 238px (cx=832, cy=318)
  - 좌측: 제품명 / 가격뱃지 / 스펙 4개
y=555     : 구분선
y=562~615 : 태그 행
y=618~800 : 평가 카드 (warning 없음: 2등분 / warning 있음: 3등분)
y=820~    : 링크 안내
```

---

## 상품 이미지 소스

- Blogger 실제 발행 HTML에서 쿠팡 CDN URL 추출
- `https://ggultongmon.allsweep.xyz/...` 페이지에서 `src=` img 태그 파싱
- 라운드 코너 마스크 (radius=24) 적용

---

## 파일 경로

```
instagram/
  CAROUSEL_SPEC.md         ← 이 파일
  carousel_generator.py    ← v5 메인 생성 코드
  slide_patches.py         ← v6 패치 (s2/s6/s8)
  slide06_compare.py       ← 비교표 단독 수정 코드
  carousel-format/         ← 최종 확정 이미지 8장
    slide_01_cover.jpg
    slide_02_checklist.jpg
    slide_03_p.jpg
    slide_04_p.jpg
    slide_05_p.jpg
    slide_06_compare.jpg
    slide_07_quote.jpg
    slide_08_cta.jpg
```

---

## 다음 단계 (미구현)

- [ ] 블로그 포스트 → 카드뉴스 자동 생성 파이프라인
  - `posts-ggultongmon/*.md` 파싱 → 상품 이미지 추출 → 슬라이드 자동 생성
- [ ] Instagram API 자동 업로드 (Meta Graph API)
- [ ] aikeeper / allsweep 버전 포맷 별도 제작
