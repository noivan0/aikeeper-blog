#!/bin/bash
# allsweep.xyz 블로그 자동 포스팅 — 서버 직접 실행 (GitHub Actions schedule 대체)
# cron: 26 */1 * * * cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger && bash run_allsweep_cron.sh >> /var/log/allsweep_cron.log 2>&1

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# .env 로드
export $(grep -v '^#' .env | xargs)

# allsweep 전용 환경변수 오버라이드
export TARGET_BLOG_ID="8772490249452917821"
export TARGET_BLOG_URL="https://www.allsweep.xyz"
export TARGET_BLOG_NAME="모든정보 쓸어담기"
export BLOG_TYPE="NEWS"
export POSTS_DIR="posts-allsweep"

# GITHUB_OUTPUT 임시 파일 (Step 1용)
GH_OUTPUT_TOPIC=/tmp/allsweep_gh_topic_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_TOPIC"
touch "$GITHUB_OUTPUT"

LOG_FILE="/var/log/allsweep_cron.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== allsweep 포스팅 시작 =====" | tee -a "$LOG_FILE"

# 랜덤 딜레이 (0~5분) — aikeeper와 26분 엇갈리므로 짧게
DELAY=$((RANDOM % 300))
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 랜덤 딜레이: ${DELAY}초" | tee -a "$LOG_FILE"
sleep "$DELAY"

# Step 1: 주제 발굴 (allsweep 전용)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 1: 주제 발굴 (allsweep)" | tee -a "$LOG_FILE"
python3 scripts/ci_find_topic_allsweep.py "" "" 2>&1 | tee -a "$LOG_FILE"

TOPIC=$(grep '^topic=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
KEYWORDS=$(grep '^keywords=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
ANGLE=$(grep '^angle=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
CATEGORY=$(grep '^category=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)

rm -f "$GH_OUTPUT_TOPIC"

if [ -z "$TOPIC" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제 발굴 실패 — 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제: $TOPIC" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 카테고리: $CATEGORY" | tee -a "$LOG_FILE"

# Step 2: 포스트 생성 (allsweep 환경변수 전달)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 2: 포스트 생성" | tee -a "$LOG_FILE"
GH_OUTPUT_GEN=/tmp/allsweep_gh_gen_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_GEN"
export TOPIC KEYWORDS ANGLE CATEGORY
touch "$GITHUB_OUTPUT"
python3 scripts/ci_generate.py "$TOPIC" "$KEYWORDS" "$ANGLE" 2>&1 | tee -a "$LOG_FILE"

POST_FILE=$(grep '^file=' "$GH_OUTPUT_GEN" | cut -d= -f2- | head -1)
rm -f "$GH_OUTPUT_GEN"

# posts-allsweep 에서 오늘 날짜 파일 탐지
if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    POST_FILE=$(ls posts-allsweep/$(date '+%Y-%m-%d')*.md 2>/dev/null | tail -1)
fi
# posts/ 에서도 fallback
if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    POST_FILE=$(ls posts/$(date '+%Y-%m-%d')*.md 2>/dev/null | tail -1)
fi

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 포스트 파일 없음 — 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 파일: $POST_FILE" | tee -a "$LOG_FILE"

# Step 3: 이미지 추가
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 3: 이미지 추가" | tee -a "$LOG_FILE"
python3 scripts/add_images.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE" || true

# Step 4: Blogger 발행 (allsweep 블로그 ID/타입)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 4: Blogger 발행 (allsweep)" | tee -a "$LOG_FILE"
TARGET_BLOG_ID="$TARGET_BLOG_ID" \
TARGET_BLOG_URL="$TARGET_BLOG_URL" \
TARGET_BLOG_NAME="$TARGET_BLOG_NAME" \
BLOG_TYPE="$BLOG_TYPE" \
python3 scripts/post_to_blogger.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE"

# Step 5: git commit & push (aikeeper-blog 저장소는 공통으로 사용)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 5: git push" | tee -a "$LOG_FILE"
git config user.name "allsweep-cron"
git config user.email "allsweep@noreply"
git add posts-allsweep/ posts/ 2>/dev/null || git add posts/ 2>/dev/null || true
git diff --staged --quiet || git commit -m "auto: allsweep 포스트 $(date '+%Y-%m-%d %H:%M KST')"
git push https://${GITHUB_PAT}@github.com/noivan0/aikeeper-blog.git main 2>&1 | tee -a "$LOG_FILE" || true

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== allsweep 완료 =====" | tee -a "$LOG_FILE"
