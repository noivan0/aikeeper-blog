#!/bin/bash
# ================================================================
# 꿀통 몬스터 블로그 자동 포스팅 실행기 v2
# 사용법: bash run_ggultongmon.sh [--no-delay]
# Blog ID/URL은 blogs.json에서 자동 로드 (하드코딩 제거)
# ================================================================
set -e

BLOG_KEY="ggultongmon"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/var/log/ggultongmon_cron.log"
POSTS_DIR="$BASE_DIR/posts-ggultongmon"
KST=$(date '+%Y-%m-%d %H:%M:%S KST')

# 중복 실행 방지 락 (flock 기반 — race condition 완전 차단)
LOCK_FILE="/tmp/ggultongmon_cron.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[$KST] [SKIP] 이미 실행 중 (flock) — 종료" | tee -a "$LOG_FILE"
    exit 0
fi
trap "flock -u 9; rm -f '$LOCK_FILE'" EXIT

# 일일 발행 횟수 제한 (Blogger API 할당량 보호)
MAX_DAILY=3
TODAY=$(date '+%Y-%m-%d')
# 오늘 날짜 기준 완료 횟수 (타임스탬프 포함 라인 유니크 처리 — tee 중복 방지)
TODAY_COUNT=$(grep "^\[$TODAY" "$LOG_FILE" 2>/dev/null | grep "===== 완료 \[blog:" | sort -u | wc -l)
if [ "$TODAY_COUNT" -ge "$MAX_DAILY" ]; then
    echo "[SKIP] 오늘 발행 ${TODAY_COUNT}회 달성 (최대 ${MAX_DAILY}회) — 종료"
    exit 0
fi

# 최소 발행 간격 체크 (3시간 = 10800초) — Google 크롤 예산 최적화
MIN_INTERVAL=10800
LAST_POST_LINE=$(grep "^\[$TODAY" "$LOG_FILE" 2>/dev/null | grep "===== 완료 \[blog:" | tail -1)
if [ -n "$LAST_POST_LINE" ]; then
    LAST_POST_TIME_STR=$(echo "$LAST_POST_LINE" | grep -oP '\d{2}:\d{2}:\d{2}' | head -1)
    if [ -n "$LAST_POST_TIME_STR" ]; then
        NOW_EPOCH=$(date +%s)
        LAST_EPOCH=$(date -d "${TODAY} ${LAST_POST_TIME_STR}" +%s 2>/dev/null || echo 0)
        DIFF=$(( NOW_EPOCH - LAST_EPOCH ))
        if [ "$DIFF" -lt "$MIN_INTERVAL" ]; then
            REMAIN=$(( (MIN_INTERVAL - DIFF) / 60 ))
            echo "[SKIP] 마지막 발행 후 ${DIFF}초 경과 — 최소 ${MIN_INTERVAL}초(3h) 필요, ${REMAIN}분 후 재시도"
            exit 0
        fi
    fi
fi

mkdir -p "$POSTS_DIR"
echo "[$KST] ===== 포스팅 시작 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"

# .env 로드 (JSON 값 포함 안전 처리)
if [ -f "$BASE_DIR/.env" ]; then
    set -a
    source "$BASE_DIR/.env"
    set +a
fi

# ggultongmon 전용 OAuth 키 오버라이드
export BLOGGER_CLIENT_ID="$GGULTONGMON_CLIENT_ID"
export BLOGGER_CLIENT_SECRET="$GGULTONGMON_CLIENT_SECRET"
export BLOGGER_REFRESH_TOKEN="$GGULTONGMON_REFRESH_TOKEN"

# blogs.json에서 Blog ID/URL 읽기 (하드코딩 제거)
TARGET_BLOG_ID=$(python3 -c "
import json
blogs = json.load(open('$BASE_DIR/blogs.json'))['blogs']
b = next(b for b in blogs if b['id'] == '$BLOG_KEY')
print(b['blog_id'])
")
TARGET_BLOG_URL=$(python3 -c "
import json
blogs = json.load(open('$BASE_DIR/blogs.json'))['blogs']
b = next(b for b in blogs if b['id'] == '$BLOG_KEY')
print(b['blog_url'])
")
POSTS_OUTPUT_DIR="$BASE_DIR/$(python3 -c "
import json
blogs = json.load(open('$BASE_DIR/blogs.json'))['blogs']
b = next(b for b in blogs if b['id'] == '$BLOG_KEY')
print(b['github']['posts_dir'])
")"

echo "[INFO] Blog ID: $TARGET_BLOG_ID" | tee -a "$LOG_FILE"
echo "[INFO] Blog URL: $TARGET_BLOG_URL" | tee -a "$LOG_FILE"

# 랜덤 딜레이 (크론 충돌 방지)
if [ "$1" != "--no-delay" ]; then
    DELAY=$((RANDOM % 300))
    echo "[$(date '+%H:%M:%S')] ${DELAY}초 대기..." | tee -a "$LOG_FILE"
    sleep "$DELAY"
fi

cd "$BASE_DIR"

# Step 1: 주제 발굴 + 상품 선정 (bestcategories API)
echo "[$(date '+%H:%M:%S')] Step 1: 주제 발굴 및 상품 선정" | tee -a "$LOG_FILE"
TOPIC_FILE=$(mktemp /tmp/ggultong_topic_XXXX.txt)
GITHUB_OUTPUT="$TOPIC_FILE" python3 scripts/find_topics_ggultongmon.py 2>&1 | tee -a "$LOG_FILE"

TOPIC=$(grep '^topic=' "$TOPIC_FILE" | cut -d= -f2-)
SEARCH_KW=$(grep '^search_keyword=' "$TOPIC_FILE" | cut -d= -f2-)
ANGLE=$(grep '^angle=' "$TOPIC_FILE" | cut -d= -f2-)
CATEGORY=$(grep '^category=' "$TOPIC_FILE" | cut -d= -f2-)
LABELS=$(grep '^labels=' "$TOPIC_FILE" | cut -d= -f2-)
META_DESC=$(grep '^meta_desc=' "$TOPIC_FILE" | cut -d= -f2-)
PRODUCTS_JSON=$(python3 -c "
import sys
for line in open('$TOPIC_FILE'):
    if line.startswith('products_json='):
        print(line[len('products_json='):].rstrip())
        break
")
rm -f "$TOPIC_FILE"

echo "[$(date '+%H:%M:%S')] 주제: $TOPIC" | tee -a "$LOG_FILE"

# 주제 비어있으면 조기 종료 (쿠팡 API 장애 등)
if [ -z "$TOPIC" ] || [ ${#TOPIC} -lt 5 ]; then
    echo "[$(date '+%H:%M:%S')] [SKIP] 주제 없음 (쿠팡 API 장애 가능성) — 이번 사이클 건너뜀" | tee -a "$LOG_FILE"
    exit 0
fi

# Step 2: GitHub Actions 트리거 (deeplink shortenUrl 발급 → 발행 일괄 처리)
# [노이반님 원칙] 제품 링크는 반드시 shortenUrl 사용
# → 이 서버에서 api-gateway.coupang.com 직접 접근 불가
# → Actions(외부망)에서 deeplink API → shortenUrl 확보 → 발행까지 일괄 처리
echo "[$(date '+%H:%M:%S')] Step 2: GitHub Actions 트리거 (deeplink + 발행)" | tee -a "$LOG_FILE"

GH_PAT="${GITHUB_PAT:-${GH_PAT:-}}"
if [ -z "$GH_PAT" ]; then
    echo "[$(date '+%H:%M:%S')] [ERROR] GH_PAT 없음 — Actions 트리거 불가" | tee -a "$LOG_FILE"
    exit 1
fi

# TOPIC/CATEGORY를 Actions inputs로 전달
_PAYLOAD=$(python3 -c "
import json, sys
topic    = '''${TOPIC}'''
category = '''${CATEGORY}'''
print(json.dumps({'ref': 'main', 'inputs': {'topic': topic, 'category': category, 'skip_delay': 'true'}}))
")

_TRG_STATUS=$(curl -s -o /tmp/gh_trigger_resp.json -w "%{http_code}" -X POST \
    -H "Authorization: token $GH_PAT" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/noivan0/aikeeper-blog/actions/workflows/ggultongmon-auto.yml/dispatches" \
    -d "$_PAYLOAD")

echo "[$(date '+%H:%M:%S')] Actions 트리거: HTTP $_TRG_STATUS" | tee -a "$LOG_FILE"
cat /tmp/gh_trigger_resp.json 2>/dev/null | head -3 | tee -a "$LOG_FILE"

if [ "$_TRG_STATUS" = "204" ]; then
    echo "[$KST] ===== Actions 트리거 성공 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"
    echo "[$(date '+%H:%M:%S')] Actions에서 deeplink shortenUrl 발급 → 발행 진행 예정" | tee -a "$LOG_FILE"
else
    echo "[$KST] [ERROR] Actions 트리거 실패 (HTTP $_TRG_STATUS) — 발행 중단" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$KST] ===== 완료 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"
