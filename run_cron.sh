#!/bin/bash
# aikeeper 블로그 자동 포스팅 — 서버 직접 실행 (GitHub Actions schedule 대체)
# cron: */run_cron.sh >> /var/log/aikeeper_cron.log 2>&1

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# .env 로드
export $(grep -v '^#' .env | xargs)

# GITHUB_OUTPUT 임시 파일
export GITHUB_OUTPUT=/tmp/aikeeper_gh_output_$$.txt
touch "$GITHUB_OUTPUT"

LOG_FILE="/var/log/aikeeper_cron.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== aikeeper 포스팅 시작 =====" | tee -a "$LOG_FILE"

# 랜덤 딜레이 (0~30분) — 자연스러운 포스팅 패턴
DELAY=$((RANDOM % 1800))
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 랜덤 딜레이: ${DELAY}초" | tee -a "$LOG_FILE"
sleep "$DELAY"

# Step 1: 주제 발굴
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 1: 주제 발굴" | tee -a "$LOG_FILE"
python3 scripts/ci_find_topic.py "" "" 2>&1 | tee -a "$LOG_FILE"

TOPIC=$(grep '^TOPIC=' "$GITHUB_OUTPUT" | cut -d= -f2- | head -1)
KEYWORDS=$(grep '^KEYWORDS=' "$GITHUB_OUTPUT" | cut -d= -f2- | head -1)
ANGLE=$(grep '^ANGLE=' "$GITHUB_OUTPUT" | cut -d= -f2- | head -1)

if [ -z "$TOPIC" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제 발굴 실패 — 종료" | tee -a "$LOG_FILE"
    rm -f "$GITHUB_OUTPUT"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제: $TOPIC" | tee -a "$LOG_FILE"

# Step 2: 포스트 생성
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 2: 포스트 생성" | tee -a "$LOG_FILE"
export GITHUB_OUTPUT=/tmp/aikeeper_gh_output2_$$.txt
touch "$GITHUB_OUTPUT"
python3 scripts/ci_generate.py "$TOPIC" "$KEYWORDS" "$ANGLE" 2>&1 | tee -a "$LOG_FILE"

POST_FILE=$(grep '^file=' "$GITHUB_OUTPUT" | cut -d= -f2- | head -1)

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    # 오늘 날짜 파일 자동 탐지
    POST_FILE=$(ls posts/$(date '+%Y-%m-%d')*.md 2>/dev/null | tail -1)
fi

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 포스트 파일 없음 — 종료" | tee -a "$LOG_FILE"
    rm -f "$GITHUB_OUTPUT"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 파일: $POST_FILE" | tee -a "$LOG_FILE"

# Step 3: 이미지 추가
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 3: 이미지 추가" | tee -a "$LOG_FILE"
python3 scripts/add_images.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE" || true

# Step 4: Blogger 발행
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 4: Blogger 발행" | tee -a "$LOG_FILE"
python3 scripts/post_to_blogger.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE"

# Step 5: git commit & push
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 5: git push" | tee -a "$LOG_FILE"
git config user.name "aikeeper-cron"
git config user.email "aikeeper@noreply"
git add posts/
git diff --staged --quiet || git commit -m "auto: AI 포스트 $(date '+%Y-%m-%d %H:%M KST')"
git push https://${GITHUB_PAT}@github.com/noivan0/aikeeper-blog.git main 2>&1 | tee -a "$LOG_FILE" || true

rm -f "$GITHUB_OUTPUT"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== 완료 =====" | tee -a "$LOG_FILE"
