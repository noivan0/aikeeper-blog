#!/bin/bash
# aikeeper 블로그 자동 포스팅 — 서버 직접 실행 (GitHub Actions schedule 대체)
# cron: */run_cron.sh >> /var/log/aikeeper_cron.log 2>&1

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# .env 로드
export $(grep -v '^#' .env | xargs)

# GITHUB_OUTPUT 임시 파일 (Step 1용)
GH_OUTPUT_TOPIC=/tmp/aikeeper_gh_topic_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_TOPIC"
touch "$GITHUB_OUTPUT"

LOG_FILE="/var/log/aikeeper_cron.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== aikeeper 포스팅 시작 =====" | tee -a "$LOG_FILE"

# 딜레이 제거 (병렬 즉시 실행)
DELAY=0
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 딜레이 없음 (병렬 실행 모드)" | tee -a "$LOG_FILE"

# Step 1: 주제 발굴
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 1: 주제 발굴" | tee -a "$LOG_FILE"
python3 scripts/ci_find_topic.py "" "" 2>&1 | tee -a "$LOG_FILE"

# ci_find_topic.py는 소문자 키(topic=, keywords=, angle=)로 출력함
TOPIC=$(grep '^topic=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
KEYWORDS=$(grep '^keywords=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
ANGLE=$(grep '^angle=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)

rm -f "$GH_OUTPUT_TOPIC"

if [ -z "$TOPIC" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제 발굴 실패 — 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 주제: $TOPIC" | tee -a "$LOG_FILE"

# Step 2: 포스트 생성 (별도 출력 파일 사용)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 2: 포스트 생성" | tee -a "$LOG_FILE"
GH_OUTPUT_GEN=/tmp/aikeeper_gh_gen_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_GEN"
touch "$GITHUB_OUTPUT"
python3 scripts/ci_generate.py "$TOPIC" "$KEYWORDS" "$ANGLE" 2>&1 | tee -a "$LOG_FILE"

POST_FILE=$(grep '^file=' "$GH_OUTPUT_GEN" | cut -d= -f2- | head -1)
rm -f "$GH_OUTPUT_GEN"

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    # 오늘 날짜 파일 중 아직 발행 안 된 파일 탐지 (published: true 없는 것)
    for f in $(ls posts/$(date '+%Y-%m-%d')*.md 2>/dev/null | sort); do
        if ! grep -q "^published: true" "$f" 2>/dev/null; then
            POST_FILE="$f"
            break
        fi
    done
fi

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 발행할 새 포스트 없음 (모두 발행 완료 또는 파일 없음) — 종료" | tee -a "$LOG_FILE"
    exit 0
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

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== 완료 =====" | tee -a "$LOG_FILE"
