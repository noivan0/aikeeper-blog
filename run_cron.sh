#!/bin/bash
# aikeeper 블로그 자동 포스팅 — 서버 직접 실행 (GitHub Actions schedule 대체)
# cron: */run_cron.sh >> /var/log/aikeeper_cron.log 2>&1

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# 중복 실행 방지 락 (GitHub Actions와 충돌 방지)
LOCK_FILE="/tmp/aikeeper_cron.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if kill -0 "$PID" 2>/dev/null; then
        echo "[SKIP] 이미 실행 중 (PID $PID) — 종료"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

# 일일 발행 횟수 제한 (Blogger API 할당량 보호 — 3개 블로그 균등 분배)
MAX_DAILY=3
TODAY=$(date '+%Y-%m-%d')
# 오늘 날짜 기준 실제 발행 성공 횟수 (blog: aikeeper 완료 패턴만, tee 중복 감안해 /2)
TODAY_COUNT_RAW=$(grep "\[$TODAY" /var/log/aikeeper_cron.log 2>/dev/null | grep "===== 완료 \[blog: aikeeper\] =====" | wc -l)
TODAY_COUNT=$(( TODAY_COUNT_RAW / 2 ))
if [ "$TODAY_COUNT" -ge "$MAX_DAILY" ]; then
    echo "[SKIP] 오늘 발행 ${TODAY_COUNT}회 달성 (최대 ${MAX_DAILY}회) — 종료"
    exit 0
fi

# .env 로드 (JSON 값 포함 안전 처리 — xargs 방식은 JSON 다중줄 값에서 오류 발생)
set +e
while IFS= read -r line; do
    [[ -z "$line" || "$line" == "#"* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && export "$key=$val"
done < .env
set -e

# aikeeper 전용 OAuth 키 오버라이드
export BLOGGER_CLIENT_ID="$AIKEEPER_CLIENT_ID"
export BLOGGER_CLIENT_SECRET="$AIKEEPER_CLIENT_SECRET"
export BLOGGER_REFRESH_TOKEN="$AIKEEPER_REFRESH_TOKEN"

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
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 4: Blogger 발행 → AI키퍼" | tee -a "$LOG_FILE"
TARGET_BLOG_ID="3598676904202320050" \
TARGET_BLOG_URL="https://aikeeper.allsweep.xyz" \
TARGET_BLOG_NAME="AI키퍼" \
BLOG_TYPE="AI" \
python3 scripts/post_to_blogger.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE"
_BLOG_EXIT=${PIPESTATUS[0]}

if [ "$_BLOG_EXIT" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== 완료 [blog: aikeeper] =====" | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== aikeeper 발행 실패 (exit $_BLOG_EXIT) =====" | tee -a "$LOG_FILE"
    exit 1
fi
