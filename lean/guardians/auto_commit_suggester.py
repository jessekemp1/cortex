#!/usr/bin/env python3
"""
Cortex Lean Guardian #5: Auto-Commit Suggester

PostToolUse hook (after Edit/Write): when uncommitted lines exceed 500
AND last commit was >30 minutes ago, suggests committing with heuristic
grouping by top-level project directory.

Throttled to at most once per 5 minutes to avoid spamming.
NEVER auto-executes — surfaces suggestion only.

Key difference from V1: fast heuristic grouping (split by top-level dir),
no intelligence queries.

State: ~/.cortex-lean/last_commit_suggestion.txt (timestamp of last suggestion)
Log:   ~/.cortex-lean/guardian_log.jsonl
"""

import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".cortex-lean"
LAST_SUGGESTION = STATE_DIR / "last_commit_suggestion.txt"
GUARDIAN_LOG = STATE_DIR / "guardian_log.jsonl"

MIN_LINES = 500
MIN_MINUTES_SINCE_COMMIT = 30
THROTTLE_SECONDS = 300  # 5 minutes


def is_throttled() -> bool:
    """Check if we suggested too recently."""
    try:
        if LAST_SUGGESTION.exists():
            last_ts = float(LAST_SUGGESTION.read_text().strip())
            return (time.time() - last_ts) < THROTTLE_SECONDS
    except Exception:
        pass
    return False


def mark_suggested():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_SUGGESTION.write_text(str(time.time()))


def minutes_since_last_commit() -> float:
    """Minutes since the most recent commit."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip():
            commit_ts = int(result.stdout.strip())
            return (time.time() - commit_ts) / 60
    except Exception:
        pass
    return 999  # If we can't tell, assume it's been a while


def count_uncommitted_lines() -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat"],
            capture_output=True,
            text=True,
            timeout=5,
        )
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


def get_commit_groups() -> dict[str, list[str]]:
    """Group changed files by top-level project directory."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
        groups = defaultdict(list)
        for f in files:
            parts = Path(f).parts
            # Use first directory as project key, or "root" for top-level files
            project = parts[0] if len(parts) > 1 else "root"
            groups[project].append(f)
        return dict(groups)
    except Exception:
        return {}


def suggest_message(project: str, files: list[str]) -> str:
    """Generate a simple conventional commit message from project and files."""
    # Detect change type from file paths
    has_tests = any("test" in f.lower() for f in files)
    has_docs = any(f.endswith(".md") for f in files)
    has_data = any(f.endswith((".json", ".csv", ".jsonl")) for f in files)

    if has_tests and not has_docs:
        prefix = "test"
    elif has_docs and len(files) == sum(1 for f in files if f.endswith(".md")):
        prefix = "docs"
    elif has_data and len(files) == sum(
        1 for f in files if f.endswith((".json", ".csv", ".jsonl"))
    ):
        prefix = "data"
    else:
        prefix = "feat"

    scope = project.lower().replace("vortex", "vortex").replace("cortex", "cortex")
    return f"{prefix}({scope}): Update {len(files)} file{'s' if len(files) != 1 else ''}"


def log_event(lines: int, groups: int):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guardian": "auto_commit_suggester",
            "source": "lean",
            "uncommitted_lines": lines,
            "groups_suggested": groups,
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        }
        with open(GUARDIAN_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main():
    if is_throttled():
        return

    lines = count_uncommitted_lines()
    if lines < MIN_LINES:
        return

    mins = minutes_since_last_commit()
    if mins < MIN_MINUTES_SINCE_COMMIT:
        return

    groups = get_commit_groups()
    if not groups:
        return

    mark_suggested()
    log_event(lines, len(groups))

    # Build suggestion message
    parts = [
        f"[Lean] {len(groups)} commit group{'s' if len(groups) != 1 else ''} detected ({lines} lines, {mins:.0f}min since last commit):"
    ]
    for project, files in sorted(groups.items()):
        msg = suggest_message(project, files)
        parts.append(f'  {len(files)} files in {project}/ → "{msg}"')
    parts.append("Run /commit to review and commit these changes.")

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "userMessage": "\n".join(parts),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
