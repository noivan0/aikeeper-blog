#!/usr/bin/env python3
"""allsweep용 CI 주제 발굴 래퍼 — GITHUB_OUTPUT에 안전하게 출력"""
import os, sys, subprocess

GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "/tmp/gh_output.txt")

manual_topic    = sys.argv[1] if len(sys.argv) > 1 else ""
manual_keywords = sys.argv[2] if len(sys.argv) > 2 else ""
target_category = sys.argv[3] if len(sys.argv) > 3 else ""

def write_output(key, value):
    safe = str(value).replace('\r', '').replace('\n', ' ')
    with open(GITHUB_OUTPUT, "a", encoding="utf-8") as f:
        f.write(f"{key}={safe}\n")

if manual_topic.strip():
    write_output("topic", manual_topic.strip())
    write_output("keywords", manual_keywords.strip())
    write_output("angle", "")
    write_output("category", target_category or "사회")
    print(f"수동 주제: {manual_topic[:60]}")
    sys.exit(0)

# find_topics_allsweep.py 실행 (stdout 캡처)
# GITHUB_OUTPUT 환경변수를 자식 프로세스에 전달하지 않음
# → 자식이 GITHUB_OUTPUT에 직접 쓰면 빈 값이 먼저 기록되어 head -1에서 빈 topic이 선택되는 버그 방지
child_env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
r = subprocess.run(
    [sys.executable, "scripts/find_topics_allsweep.py", "", "", target_category],
    capture_output=True, text=True, timeout=240,
    env=child_env,
)
output = r.stdout + r.stderr
print(output)

topic    = ""
keywords = ""
angle    = ""
category = ""
for line in output.splitlines():
    if line.startswith("topic:"):
        topic = line[6:].strip()
    elif line.startswith("keywords:"):
        keywords = line[9:].strip()
    elif line.startswith("angle:"):
        angle = line[6:].strip()
    elif line.startswith("category:"):
        category = line[9:].strip()

if not topic:
    print("❌ 주제 추출 실패 — fallback 사용", file=sys.stderr)
    topic    = "오늘의 주요 뉴스 총정리"
    keywords = "뉴스,한국,오늘"
    angle    = "총정리"
    category = "사회"

write_output("topic", topic)
write_output("keywords", keywords)
write_output("angle", angle)
write_output("category", category)
print(f"선정 주제: {topic[:60]}")
