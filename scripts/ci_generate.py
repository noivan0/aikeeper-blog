#!/usr/bin/env python3
"""CI용 포스트 생성 래퍼 — GITHUB_OUTPUT에 파일 경로 출력"""
import os, sys, subprocess

GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "/tmp/gh_output.txt")

topic = sys.argv[1] if len(sys.argv) > 1 else "AI 최신 뉴스"
keywords = sys.argv[2] if len(sys.argv) > 2 else ""
angle = sys.argv[3] if len(sys.argv) > 3 else ""

r = subprocess.run(
    [sys.executable, "scripts/generate_post.py", topic, keywords, angle],
    capture_output=True, text=True, timeout=300,
)
print(r.stdout)
if r.stderr:
    print(r.stderr, file=sys.stderr)

# 파일 경로 추출
filepath = ""
for line in reversed(r.stdout.splitlines()):
    if line.startswith("posts/"):
        filepath = line.strip()
        break

if not filepath or not os.path.exists(filepath):
    print(f"❌ 파일 없음: [{filepath}]", file=sys.stderr)
    sys.exit(1)

with open(GITHUB_OUTPUT, "a", encoding="utf-8") as f:
    f.write(f"file={filepath}\n")

print(f"✅ 파일: {filepath}")
