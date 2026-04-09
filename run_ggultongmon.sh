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
MAX_DAILY=5
TODAY=$(date '+%Y-%m-%d')
# 오늘 날짜 기준 완료 횟수 (타임스탬프 있는 완료 라인으로 카운트, tee 중복 감안해 /2)
TODAY_COUNT_RAW=$(grep "\[$TODAY" "$LOG_FILE" 2>/dev/null | grep "===== 완료 \[blog:" | wc -l)
TODAY_COUNT=$(( TODAY_COUNT_RAW / 2 ))
if [ "$TODAY_COUNT" -ge "$MAX_DAILY" ]; then
    echo "[SKIP] 오늘 발행 ${TODAY_COUNT}회 달성 (최대 ${MAX_DAILY}회) — 종료"
    exit 0
fi

mkdir -p "$POSTS_DIR"
echo "[$KST] ===== 포스팅 시작 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"

# .env 로드 (JSON 값 포함 안전 처리)
if [ -f "$BASE_DIR/.env" ]; then
    set -a
    source "$BASE_DIR/.env"
    set +a
fi

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
PRODUCTS_JSON=$(grep '^products_json=' "$TOPIC_FILE" | cut -d= -f2-)
rm -f "$TOPIC_FILE"

echo "[$(date '+%H:%M:%S')] 주제: $TOPIC" | tee -a "$LOG_FILE"

# 주제 비어있으면 조기 종료 (쿠팡 API 장애 등)
if [ -z "$TOPIC" ] || [ ${#TOPIC} -lt 5 ]; then
    echo "[$(date '+%H:%M:%S')] [SKIP] 주제 없음 (쿠팡 API 장애 가능성) — 이번 사이클 건너뜀" | tee -a "$LOG_FILE"
    exit 0
fi

# Step 2: 포스트 생성 및 발행
echo "[$(date '+%H:%M:%S')] Step 2: 포스트 생성 및 발행" | tee -a "$LOG_FILE"

export TOPIC SEARCH_KW ANGLE CATEGORY LABELS META_DESC PRODUCTS_JSON
export TARGET_BLOG_ID TARGET_BLOG_URL POSTS_OUTPUT_DIR
export BLOG_TYPE="COUPANG"
export BLOG_NAME="꿀통 몬스터"
export COUPANG_SUB_ID="ggultongmon"

set -o pipefail
python3 scripts/post_to_blogger_ggultongmon.py 2>&1 | tee -a "$LOG_FILE"
_EXIT=$?
set +o pipefail

if [ $_EXIT -ne 0 ]; then
    echo "[$KST] [ERROR] 포스트 생성/발행 실패 (exit $_EXIT) — 이번 사이클 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$KST] ===== 완료 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"
