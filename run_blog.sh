#!/bin/bash
# ============================================================
# run_blog.sh — aikeeper 멀티 블로그 포스팅 실행기
# 사용법: bash run_blog.sh <blog_id> [--no-delay]
#
# blog_id: blogs.json에 정의된 블로그 ID (기본값: aikeeper)
# --no-delay: 랜덤 딜레이 없이 즉시 실행 (테스트/수동용)
# ============================================================

set -e
cd /root/.openclaw/workspace/paperclip-company/projects/p004-blogger

# ── 인자 파싱 ──────────────────────────────────────────────
BLOG_ID="${1:-aikeeper}"
NO_DELAY=false
for arg in "$@"; do
    [ "$arg" = "--no-delay" ] && NO_DELAY=true
done

# ── .env 로드 (공통 API 키) ─────────────────────────────────
# .env 로드 (Python 기반 — JSON 멀티라인 값 포함 안전 처리)
BASE_DIR="$(pwd)"
eval "$(python3 -c "
import os, re, sys
for line in open('$BASE_DIR/.env'):
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    k, v = line.split('=', 1)
    k = k.strip()
    v = v.strip().strip(chr(39)).strip(chr(34))
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k) and chr(10) not in v:
        print(f'export {k}={repr(v)}')
" 2>/dev/null)"

LOG_FILE="/var/log/aikeeper_cron.log"
TIMESTAMP() { date '+%Y-%m-%d %H:%M:%S KST'; }

echo "[$(TIMESTAMP)] ===== 포스팅 시작 [blog: ${BLOG_ID}] =====" | tee -a "$LOG_FILE"

# ── 블로그 설정 로드 (blogs.json) ───────────────────────────
BLOG_CONFIG=$(python3 -c "
import json, sys
data = json.load(open('blogs.json'))
blogs = {b['id']: b for b in data['blogs']}
if '${BLOG_ID}' not in blogs:
    print('ERROR: blog_id not found', file=sys.stderr)
    sys.exit(1)
b = blogs['${BLOG_ID}']
if not b.get('enabled', True):
    print('DISABLED', file=sys.stderr)
    sys.exit(2)
print(json.dumps(b))
" 2>&1)

EXIT_CODE=$?
if [ $EXIT_CODE -eq 2 ]; then
    echo "[$(TIMESTAMP)] 블로그 비활성화 상태 — 종료" | tee -a "$LOG_FILE"
    exit 0
elif [ $EXIT_CODE -ne 0 ]; then
    echo "[$(TIMESTAMP)] blogs.json 로드 실패: $BLOG_CONFIG" | tee -a "$LOG_FILE"
    exit 1
fi

# 블로그별 환경변수 주입
# blogs.json의 env 섹션 키:값 → 환경변수명:환경변수명 매핑
# (현재는 .env 파일의 동일 키 사용, 향후 블로그별 독립 키 지원)
# 블로그 메타 환경변수 — Python으로 env 파일에 쓰고 source (JSON 값 eval 오류 방지)
_BLOG_ENV_TMP=$(mktemp)
python3 - <<PYEOF > "$_BLOG_ENV_TMP"
import json, os, shlex
b = json.loads('''$BLOG_CONFIG''')
env_map = b.get('env', {})
for env_key, src_key in env_map.items():
    val = os.environ.get(src_key, os.environ.get(env_key, ''))
    if val and '\n' not in val:
        print(f'export {env_key}={shlex.quote(val)}')
meta = {
    'TARGET_BLOG_ID': b['blog_id'],
    'TARGET_BLOG_URL': b['blog_url'],
    'TARGET_BLOG_NAME': b['name'],
    'ADSENSE_PUB': b.get('adsense_pub',''),
    'ADSENSE_IN_ARTICLE_SLOT': b.get('adsense_in_article_slot',''),
    'ADSENSE_DISPLAY_SLOT': b.get('adsense_display_slot',''),
    'NAVER_SITE_VERIFICATION': b.get('naver_site_verification',''),
    'BLOG_TYPE': b.get('topic_domain','AI'),
}
gh = b.get('github', {})
meta['GITHUB_REPO']   = gh.get('repo','')
meta['GITHUB_BRANCH'] = gh.get('branch','main')
meta['POSTS_DIR']     = gh.get('posts_dir','posts')
for k, v in meta.items():
    if '\n' not in str(v):
        print(f'export {k}={shlex.quote(str(v))}')
PYEOF
# shellcheck source=/dev/null
source "$_BLOG_ENV_TMP"
rm -f "$_BLOG_ENV_TMP"

echo "[$(TIMESTAMP)] 블로그: $TARGET_BLOG_NAME ($TARGET_BLOG_URL)" | tee -a "$LOG_FILE"

# ── 랜덤 딜레이 ─────────────────────────────────────────────
if [ "$NO_DELAY" = false ]; then
    DELAY=$((RANDOM % 1800))
    echo "[$(TIMESTAMP)] 랜덤 딜레이: ${DELAY}초" | tee -a "$LOG_FILE"
    sleep "$DELAY"
fi

# ── Step 1: 주제 발굴 ───────────────────────────────────────
echo "[$(TIMESTAMP)] Step 1: 주제 발굴" | tee -a "$LOG_FILE"
GH_OUTPUT_TOPIC=/tmp/aikeeper_gh_topic_${BLOG_ID}_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_TOPIC"
touch "$GITHUB_OUTPUT"

# 블로그별 전용 주제 발굴 스크립트 선택
if [ "$BLOG_ID" = "allsweep" ]; then
    FIND_TOPIC_SCRIPT="scripts/ci_find_topic_allsweep.py"
else
    FIND_TOPIC_SCRIPT="scripts/ci_find_topic.py"
fi
python3 "$FIND_TOPIC_SCRIPT" "" "" 2>&1 | tee -a "$LOG_FILE"

TOPIC=$(grep '^topic=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
KEYWORDS=$(grep '^keywords=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
ANGLE=$(grep '^angle=' "$GH_OUTPUT_TOPIC" | cut -d= -f2- | head -1)
rm -f "$GH_OUTPUT_TOPIC"

if [ -z "$TOPIC" ]; then
    echo "[$(TIMESTAMP)] 주제 발굴 실패 — 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(TIMESTAMP)] 주제: $TOPIC" | tee -a "$LOG_FILE"

# ── Step 2: 포스트 생성 ─────────────────────────────────────
echo "[$(TIMESTAMP)] Step 2: 포스트 생성" | tee -a "$LOG_FILE"
GH_OUTPUT_GEN=/tmp/aikeeper_gh_gen_${BLOG_ID}_$$.txt
export GITHUB_OUTPUT="$GH_OUTPUT_GEN"
touch "$GITHUB_OUTPUT"

python3 scripts/ci_generate.py "$TOPIC" "$KEYWORDS" "$ANGLE" 2>&1 | tee -a "$LOG_FILE"

POST_FILE=$(grep '^file=' "$GH_OUTPUT_GEN" | cut -d= -f2- | head -1)
rm -f "$GH_OUTPUT_GEN"

[ -z "$POST_FILE" ] && POST_FILE=$(ls ${POSTS_DIR}/$(date '+%Y-%m-%d')*.md 2>/dev/null | tail -1)

if [ -z "$POST_FILE" ] || [ ! -f "$POST_FILE" ]; then
    echo "[$(TIMESTAMP)] 포스트 파일 없음 — 종료" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(TIMESTAMP)] 파일: $POST_FILE" | tee -a "$LOG_FILE"

# ── Step 3: 이미지 추가 ─────────────────────────────────────
echo "[$(TIMESTAMP)] Step 3: 이미지 추가" | tee -a "$LOG_FILE"
python3 scripts/add_images.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 4: Blogger 발행 ────────────────────────────────────
echo "[$(TIMESTAMP)] Step 4: Blogger 발행 → $TARGET_BLOG_NAME" | tee -a "$LOG_FILE"
python3 scripts/post_to_blogger.py "$POST_FILE" 2>&1 | tee -a "$LOG_FILE"

# ── Step 5: git commit & push ───────────────────────────────
if [ -n "$GITHUB_REPO" ]; then
    echo "[$(TIMESTAMP)] Step 5: git push → $GITHUB_REPO" | tee -a "$LOG_FILE"
    git config user.name "aikeeper-cron"
    git config user.email "aikeeper@noreply"
    git add ${POSTS_DIR}/
    git diff --staged --quiet || git commit -m "auto[$BLOG_ID]: AI 포스트 $(date '+%Y-%m-%d %H:%M KST')"
    # PAT를 git URL에 직접 노출하지 않도록 insteadOf 설정 사용 (ps aux 노출 방지)
    git config url."https://${GITHUB_PAT}@github.com/".insteadOf "https://github.com/"
    git pull --rebase https://github.com/${GITHUB_REPO}.git ${GITHUB_BRANCH} 2>&1 | tee -a "$LOG_FILE" || true
    git push https://github.com/${GITHUB_REPO}.git ${GITHUB_BRANCH} 2>&1 | tee -a "$LOG_FILE" || true
    # 사용 후 insteadOf 설정 제거 (로컬 설정 오염 방지)
    git config --unset url."https://${GITHUB_PAT}@github.com/".insteadOf 2>/dev/null || true
fi

echo "[$(TIMESTAMP)] ===== 완료 [blog: ${BLOG_ID}] =====" | tee -a "$LOG_FILE"
