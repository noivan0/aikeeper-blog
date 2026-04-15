#!/bin/bash
# ================================================================
# 네이버 prosweep 홈판 크로스포스팅 래퍼
# .env에서 NAVER_ID/PW 로드 (크론탭 하드코딩 제거용)
# cron: 30 23 * * * cd /path && bash run_naver_cron.sh >> /tmp/naver_cron.log 2>&1
# ================================================================
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/naver_cron.log"
KST=$(date '+%Y-%m-%d %H:%M:%S KST')

# 중복 실행 방지
LOCK_FILE="/tmp/naver_homefeed_cron.lock"
if [ -f "$LOCK_FILE" ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
    if [ "$AGE" -lt 1800 ]; then
        echo "[$KST] [SKIP] 이미 실행 중 (lock ${AGE}s) — 종료"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
touch "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

# .env 로드 (NAVER_ID, NAVER_PW 등)
if [ -f "$BASE_DIR/.env" ]; then
    set -a
    source "$BASE_DIR/.env"
    set +a
fi

if [ -z "$NAVER_ID" ] || [ -z "$NAVER_PW" ]; then
    echo "[$KST] [ERROR] NAVER_ID/NAVER_PW 없음 (.env 확인 필요)" | tee -a "$LOG_FILE"
    exit 1
fi

cd "$BASE_DIR"
DISPLAY=:99 python3 scripts/naver_homefeed_runner.py 2>&1 | tee -a "$LOG_FILE"
