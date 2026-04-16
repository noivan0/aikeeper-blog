# 네이버 블로그 발행 기준 (확정, 2026-04-16)

> 이 문서는 실패 역공학 + 성공 사례 기반으로 확정된 기준입니다.  
> **재조사 금지** — 이미 검증된 사실입니다.

---

## 1. API 흐름 요약

```
[브라우저 세션 로그인]
    ↓
[이미지 업로드] blog.upphoto.naver.com (XML 응답)
    ↓
[OGLink 카드] platform.editor.naver.com/api/blogpc001/v1/oglink
    ↓
[autosave]   RabbitAutoSaveWrite.naver → autoSaveNo 획득
    ↓
[publish]    RabbitWrite.naver → redirectUrl (logNo 포함)
```

---

## 2. autosave (RabbitAutoSaveWrite) 한계 — 확정

### documentModel 크기 제한
| documentModel 크기 | 결과 |
|---------------------|------|
| ~15,000자 (컴포넌트 14개) | ✅ 성공 (2026-04-15 확인) |
| ~40,000자 이하 | ✅ 안전 추정 |
| ~50,000자 초과 | ⚠️ UNKNOWN 위험 |
| 79,127자 (컴포넌트 24개) | ❌ UNKNOWN (2026-04-16 확인) |
| 165,486자 (컴포넌트 96개) | ❌ UNKNOWN (2026-04-16 확인) |

**MAX_DOC_SIZE = 50,000자** (publisher.py 적용값)

### 이미지 수 제한
| 이미지 수 | IMAGE_HERE 수 | 결과 |
|-----------|---------------|------|
| 0장 | 0개 | ✅ 성공 |
| 2장 이하 | 2개 이하 | ✅ 성공 (추정 — 2장 기준 적용 중) |
| 4장 | 4개 | ❌ UNKNOWN (2026-04-16 확인) |
| 13장+ | 28개 | ❌ UNKNOWN (2026-04-16 확인) |

**MAX_NAVER_IMAGES = 2** (pipeline.py 적용값)  
**MAX_EXTRA_IMGS = 2** (publisher.py 적용값)  
**IMAGE_HERE 최대 2개** (generate_naver_post.py 적용값)

### mediaResources 파라미터
- 빈 배열 `{"image":[],"video":[],"file":[]}` → autosave 시도 가능하나 UNKNOWN 위험
- 업로드된 이미지 정보 포함 버전 → 성공률 개선 기대 (2026-04-16 코드 반영, 미검증)

---

## 3. 발행 폴백 순서 (3단계)

```
[1단계] autosave(이미지 포함, mediaResources에 업로드 정보 포함)
    → autoSaveNo 획득 시 → RabbitWrite 발행 ✅
    → UNKNOWN 시 → [2단계]

[2단계] autosave(이미지 컴포넌트 전부 제거한 minimal documentModel)
    → autoSaveNo 획득 시 → RabbitWrite 발행 (이미지 없는 버전) ✅
    → UNKNOWN 시 → [3단계]

[3단계] autoSaveNo=None으로 RabbitWrite 직접 발행
    → tokenId는 세션 쿠키에 내재 → 생략 가능 (2026-04-15 확인)
    → 성공 여부는 응답 body에서 logNo 파싱으로 판단
```

**코드 위치:** `naver_lib/publisher.py` STEP 7

---

## 4. 성공 사례 기준 (2026-04-15 검증)

- documentModel: **~15,000자**
- 컴포넌트 수: **14개**
- 이미지: **2장 이하**
- IMAGE_HERE: **2개 이하**
- 본문 비어있지 않은 줄: **70줄 이내**
- tokenId: 세션 쿠키 내재 → 명시 전송 불필요

---

## 5. 실패 사례 목록 (2026-04-16 확인)

| 날짜 | documentModel | 컴포넌트 | 이미지 | IMAGE_HERE | 결과 |
|------|--------------|---------|--------|------------|------|
| 2026-04-15 이전 | 165,486자 | 96개 | 13장 | 28개 | ❌ UNKNOWN |
| 2026-04-16 | 79,127자 | 24개 | 4장 | 4개 | ❌ UNKNOWN |
| 2026-04-15 | ~15,000자 | 14개 | 2장 | 2개 | ✅ 성공 |

---

## 6. 줄 수와 documentModel 크기의 관계

```
줄당 UUID 오버헤드: ~550자
본문 69줄  → documentModel ~27,000자 (성공)
본문 277줄 → documentModel ~154,000자 (실패)
```

**결론:** 줄 수 최소화가 documentModel 크기 제어의 핵심.  
각 섹션 내용은 반드시 **하나의 긴 단락(한 줄)**으로 작성.

---

## 7. 각 파일별 적용 기준값

| 파일 | 변수/설정 | 값 | 비고 |
|------|---------|-----|------|
| `pipeline.py` | `MAX_NAVER_IMAGES` | 2 | 파이프라인 이미지 전달 최대 |
| `publisher.py` | `MAX_EXTRA_IMGS` | 2 | 실제 다운로드/업로드 최대 |
| `publisher.py` | `MAX_DOC_SIZE` | 50,000자 | 초과 시 이미지 순차 제거 |
| `generate_naver_post.py` | `img_count` | min(2, total) | IMAGE_HERE 생성 최대 |
| `generate_naver_post.py` | `max_img_here` | min(2, total) | _enforce_image_limit 인자 |
| `api.py` | `autosave()` | uploaded_images 파라미터 추가 | mediaResources에 이미지 정보 포함 |

---

## 8. api.py autosave 로깅 (2026-04-16 추가)

autosave 실패 시 아래 형식으로 상세 로그 출력:

```
[autosave raw] status=200 body={"isSuccess":false,"result":"UNKNOWN"}
❌ 자동저장 실패: {'isSuccess': False, 'result': 'UNKNOWN'}
```

HTTP 상태코드가 200이어도 `isSuccess: false`인 경우 → documentModel 크기/구조 문제.  
HTTP 상태코드가 4xx인 경우 → 세션 만료 또는 파라미터 형식 오류.

---

## 9. 알려진 미해결 문제

1. **autosave UNKNOWN 근본 원인 미확정**
   - documentModel 크기 문제인지 이미지 컴포넌트 구조 문제인지 미분리
   - 다음 테스트 시 `[autosave raw]` 로그로 HTTP status 확인 필요

2. **mediaResources 이미지 정보 포함 효과 미검증**
   - 코드 반영 완료 (2026-04-16), 실제 발행 테스트 미시행

3. **폴백 2단계(이미지 제거 재시도) 실제 효과 미검증**
   - 이론상 minimal documentModel은 성공해야 하나 세션 문제일 경우 동일 실패 가능

---

## 10. 변경 이력

| 날짜 | 변경 내용 | 담당 |
|------|---------|------|
| 2026-04-15 | tokenId 세션 쿠키 내재 확인, 첫 발행 성공 | pipeResLeadbot |
| 2026-04-16 | autosave 상세 로깅 추가 (HTTP status + body) | pipeResLeadbot |
| 2026-04-16 | 3단계 폴백 로직 구현 | pipeResLeadbot |
| 2026-04-16 | 이미지 최대 2장으로 축소 (4장→UNKNOWN 확인) | pipeResLeadbot |
| 2026-04-16 | generate_naver_post.py IMAGE_HERE 3→2개로 조정 | pipeResLeadbot |
| 2026-04-16 | mediaResources에 업로드 이미지 정보 포함 | pipeResLeadbot |
