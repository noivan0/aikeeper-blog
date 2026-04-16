# P004 shortenUrl 절대 규칙 (2026-04-16 확정)

## 절대 원칙
- **모든 쿠팡 제품 링크는 반드시 `link.coupang.com/a/xxxxx` 형태의 shortenUrl 사용**
- `coupang.com/vp/products/...` raw URL 절대 금지
- `link.coupang.com/re/AFFSDP...` AFFSDP URL 절대 금지

## 기술 구조 (2026-04-16 역공학 확정)

### 문제: HMG 방화벽
- 서버(Docker) → `api-gateway.coupang.com` → 302 Redirect → `secinfo.hmg-corp.io/webfilter_block.html`
- 서버에서 직접 deeplink API 호출 **영구 불가**

### 해결: GitHub Actions 경유
- **GitHub Actions 환경은 외부망 직접 접근 가능**
- `ggultongmon-auto.yml` → `shortenUrl 발급` step에서 deeplink API 호출
  - 엔드포인트: `POST https://api-gateway.coupang.com/v2/providers/affiliate_open_api/apis/openapi/deeplink`
  - 요청 바디: `{"coupangUrls": [...], "subId": "ggultongmon"}`
  - 응답: `{"data": [{"shortenUrl": "https://link.coupang.com/a/xxxxx", "originalUrl": "..."}]}`
- shortenUrl 확보 후 `products_json_b64` (base64)로 다음 step 전달

### 파이프라인 순서
```
find_topics_ggultongmon.py (로컬) → PRODUCTS_JSON (shortenUrl 없음)
  ↓ GitHub Actions
shortenUrl 발급 step (Actions) → deeplink API → link.coupang.com/a/ 확보
  ↓
post_to_blogger_ggultongmon.py (Actions) → 발행 (shortenUrl 포함)
```

### AFFSDP 잔존 포스팅 처리
- `fix-coupang-links.yml` Actions: 기존 AFFSDP URL → 공식 shortenUrl 교체
- 수동 트리거: GitHub Actions → fix-coupang-links → Run workflow

## 코드 위치
- deeplink 발급: `coupang_api.py` → `_get_deeplink_shorten_urls()`
- 발행 시 검증: `post_to_blogger_ggultongmon.py` → shortenUrl 없으면 skip
- Actions deeplink step: `.github/workflows/ggultongmon-auto.yml` → `shortenUrl 발급` step

## 검증 방법
발행된 포스팅 HTML에서:
- ✅ `link.coupang.com/a/` 포함 → 정상
- ❌ `AFFSDP` 포함 → fix-coupang-links Actions 실행
- ❌ `coupang.com/vp/` 포함 → 코드 점검 필요
