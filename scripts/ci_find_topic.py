#!/usr/bin/env python3
"""CI용 주제 발굴 래퍼 — GITHUB_OUTPUT에 안전하게 출력"""
import os, sys

GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT", "/tmp/gh_output.txt")

manual_topic = sys.argv[1] if len(sys.argv) > 1 else ""
manual_keywords = sys.argv[2] if len(sys.argv) > 2 else ""

def write_output(key, value):
    # 멀티라인 값 처리 (EOF 구분자)
    safe = str(value).replace('\r', '').replace('\n', ' ')
    with open(GITHUB_OUTPUT, "a", encoding="utf-8") as f:
        f.write(f"{key}={safe}\n")

if manual_topic.strip():
    write_output("topic", manual_topic.strip())
    write_output("keywords", manual_keywords.strip())
    write_output("angle", "")
    print(f"수동 주제: {manual_topic[:60]}")
else:
    # find_topics.py 실행
    import subprocess, tempfile
    result = subprocess.run(
        [sys.executable, "scripts/find_topics.py"],
        capture_output=False,
        text=True,
        timeout=180,
    )
    # 출력에서 파싱은 find_topics.py가 stdout에 직접 씀
    # stdout 재캡처
    r2 = subprocess.run(
        [sys.executable, "scripts/find_topics.py"],
        capture_output=True, text=True, timeout=180,
    )
    output = r2.stdout + r2.stderr
    print(output)

    topic = ""
    keywords = ""
    angle = ""
    for line in output.splitlines():
        if line.startswith("TOPIC:"):
            topic = line[6:].strip()
        elif line.startswith("KEYWORDS:"):
            keywords = line[9:].strip()
        elif line.startswith("ANGLE:"):
            angle = line[6:].strip()

    write_output("topic", topic)
    write_output("keywords", keywords)
    write_output("angle", angle)
    print(f"선정 주제: {topic[:60]}")
