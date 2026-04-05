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

mkdir -p "$POSTS_DIR"
echo "[$KST] ===== 포스팅 시작 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"

# .env 로드
if [ -f "$BASE_DIR/.env" ]; then
    export $(grep -v '^#' "$BASE_DIR/.env" | xargs)
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

# Step 2: 포스트 생성 및 발행
echo "[$(date '+%H:%M:%S')] Step 2: 포스트 생성 및 발행" | tee -a "$LOG_FILE"

export TOPIC SEARCH_KW ANGLE CATEGORY LABELS META_DESC PRODUCTS_JSON
export TARGET_BLOG_ID TARGET_BLOG_URL POSTS_OUTPUT_DIR
export BLOG_TYPE="COUPANG"
export BLOG_NAME="꿀통 몬스터"
export COUPANG_SUB_ID="ggultongmon"

python3 scripts/post_to_blogger_ggultongmon.py 2>&1 | tee -a "$LOG_FILE"

echo "[$KST] ===== 완료 [blog: $BLOG_KEY] =====" | tee -a "$LOG_FILE"
