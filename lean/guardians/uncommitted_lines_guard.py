#!/usr/bin/env python3
"""
Cortex Lean Guardian #3: Uncommitted Lines Detector

PostToolUse hook (after Edit/Write): counts uncommitted lines via
`git diff --stat` and warns when thresholds are exceeded.

Thresholds:
  500 lines  → warning
  1000 lines → alert
  2000 lines → critical

Latency budget: <50ms (single `git diff --stat | tail -1`)
State: none (stateless per-invocation)
Log:   ~/.cortex-lean/guardian_log.jsonl
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

GUARDIAN_LOG = Path.home() / ".cortex-lean" / "guardian_log.jsonl"

THRESHOLDS = [
    (2000, "CRITICAL", "Split changes into commits NOW — risk of losing work"),
    (1000, "ALERT", "Consider committing — uncommitted changes accumulating"),
    (500, "WARNING", "Uncommitted lines growing — good time to commit"),
]


def count_uncommitted_lines(repo_path: str = ".") -> int:
    """Count total inserted+deleted lines in uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Output: " 3 files changed, 45 insertions(+), 12 deletions(-)"
        text = result.stdout.strip()
        if not text:
            return 0
        total = 0
        for part in text.split(","):
            part = part.strip()
            if "insertion" in part or "deletion" in part:
                total += int(part.split()[0])
        return total
    except Exception:
        return 0


def log_event(lines: int, level: str):
    try:
        GUARDIAN_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guardian": "uncommitted_lines",
            "lines": lines,
            "level": level,
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        }
        with open(GUARDIAN_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main():
    lines = count_uncommitted_lines()

    for threshold, level, message in THRESHOLDS:
        if lines >= threshold:
            log_event(lines, level)
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "userMessage": (
                                f"[Git Guardian] {level}: {lines} uncommitted lines. {message}"
                            ),
                        }
                    }
                )
            )
            return

    # Below all thresholds — silent pass
    if lines > 0:
        log_event(lines, "ok")


if __name__ == "__main__":
    main()
