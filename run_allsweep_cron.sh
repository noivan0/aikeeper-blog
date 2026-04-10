#!/bin/bash
# allsweep.xyz 블로그 자동 포스팅 — 서버 직접 실행 (GitHub Actions schedule 대체)
# cron: 26 */1 * * * cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger && bash run_allsweep_cron.sh >> /var/log/allsweep_cron.log 2>&1

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# 중복 실행 방지 락
LOCK_FILE="/tmp/allsweep_cron.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if kill -0 "$PID" 2>/dev/null; then
        echo "[SKIP] 이미 실행 중 (PID $PID) — 종료"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

# 일일 발행 횟수 제한 (Blogger API 할당량 보호)
MAX_DAILY=5
TODAY=$(date '+%Y-%m-%d')
# 오늘 날짜 기준 완료 횟수 (타임스탬프 있는 완료 라인으로 카운트, tee 중복 감안해 /2)
TODAY_COUNT_RAW=$(grep "\[$TODAY" /var/log/allsweep_cron.log 2>/dev/null | grep "===== allsweep 완료 =====" | wc -l)
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

# allsweep 전용 OAuth 키 오버라이드
export BLOGGER_CLIENT_ID="$ALLSWEEP_CLIENT_ID"
export BLOGGER_CLIENT_SECRET="$ALLSWEEP_CLIENT_SECRET"
export BLOGGER_REFRESH_TOKEN="$ALLSWEEP_REFRESH_TOKEN"

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

# 딜레이 제거 (병렬 즉시 실행)
DELAY=0
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] 딜레이 없음 (병렬 실행 모드)" | tee -a "$LOG_FILE"

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

# posts-allsweep 에서 오늘 날짜 중 아직 발행 안 된 파일 탐지
if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    for f in $(ls posts-allsweep/$(date '+%Y-%m-%d')*.md 2>/dev/null | sort); do
        if ! grep -q "^published: true" "$f" 2>/dev/null; then
            POST_FILE="$f"
            break
        fi
    done
fi
# posts/ 에서도 fallback (발행 안 된 것만)
if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
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

# Step 4: Blogger 발행 (allsweep 블로그 ID/타입)
echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] Step 4: Blogger 발행 (allsweep)" | tee -a "$LOG_FILE"
TARGET_BLOG_ID="$TARGET_BLOG_ID" \
TARGET_BLOG_URL="$TARGET_BLOG_URL" \
TARGET_BLOG_NAME="$TARGET_BLOG_NAME" \
BLOG_TYPE="$BLOG_TYPE" \
python3 scripts/post_to_blogger.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S KST')] ===== allsweep 완료 =====" | tee -a "$LOG_FILE"
