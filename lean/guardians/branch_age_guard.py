#!/usr/bin/env python3
"""
Cortex Lean Guardian #4: Branch Age Monitor

SessionStart hook: checks branch age and commits ahead of main.
Runs once per session to surface branch health.

Thresholds:
  3 days / 5 commits  → suggest PR
  5 days / 10 commits → warn
  7 days / 25 commits → critical

Latency budget: <100ms (two git commands)
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

GUARDIAN_LOG = Path.home() / ".cortex-lean" / "guardian_log.jsonl"


def get_branch_info() -> tuple[str, float, int]:
    """Return (branch_name, age_days, commits_ahead_of_main)."""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()

        if branch in ("main", "master", ""):
            return branch, 0.0, 0

        # First commit on this branch (divergence from main)
        result = subprocess.run(
            ["git", "log", "--format=%aI", "--reverse", f"main..{branch}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return branch, 0.0, 0

        first_date = datetime.fromisoformat(lines[0])
        age_days = (
            datetime.now(timezone.utc) - first_date.astimezone(timezone.utc)
        ).total_seconds() / 86400
        commits_ahead = len(lines)

        return branch, age_days, commits_ahead
    except Exception:
        return "unknown", 0.0, 0


def log_event(branch: str, age_days: float, commits: int, level: str):
    try:
        GUARDIAN_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guardian": "branch_age",
            "branch": branch,
            "age_days": round(age_days, 1),
            "commits_ahead": commits,
            "level": level,
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        }
        with open(GUARDIAN_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main():
    branch, age_days, commits = get_branch_info()

    if branch in ("main", "master", ""):
        return  # Nothing to report on main

    level = "ok"
    message = None

    if age_days >= 7 or commits >= 25:
        level = "CRITICAL"
        message = f"Branch `{branch}` is {age_days:.0f}d old with {commits} commits — merge or create PR urgently"
    elif age_days >= 5 or commits >= 10:
        level = "ALERT"
        message = f"Branch `{branch}` is {age_days:.0f}d old with {commits} commits — consider creating a PR"
    elif age_days >= 3 or commits >= 5:
        level = "WARNING"
        message = (
            f"Branch `{branch}` is {age_days:.0f}d old with {commits} commits — good time for a PR"
        )

    log_event(branch, age_days, commits, level)

    if message:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "userMessage": f"[Git Guardian] {level}: {message}",
            }
        }
        print(json.dumps(output))


if __name__ == "__main__":
    main()
