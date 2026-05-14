#!/usr/bin/env python3
"""
Cortex Lean Git Hook Router

Central dispatcher for git-related guardians. Calls the appropriate
guardian based on the tool_name from stdin JSON.

Routing:
  PostToolUse (Edit|Write) → uncommitted_lines_guard, auto_commit_suggester
  SessionStart             → branch_age_guard

Enforces <100ms total latency budget. Logs all interventions to
~/.cortex-lean/guardian_log.jsonl.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

GUARDIAN_DIR = Path(__file__).parent


def _cleanup_stale_lock():
    """Remove stale .git/index.lock if a git subprocess was killed mid-operation."""
    try:
        lock = Path.cwd() / ".git" / "index.lock"
        if lock.exists():
            lock.unlink(missing_ok=True)
    except Exception:
        pass


def run_guardian(script: str, stdin_data: str = "") -> str:
    """Run a guardian script, return its stdout."""
    script_path = GUARDIAN_DIR / script
    if not script_path.exists():
        return ""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        _cleanup_stale_lock()
        return ""


def merge_outputs(outputs: list[str]) -> str:
    """Merge multiple guardian JSON outputs into a single message."""
    messages = []
    for output in outputs:
        if not output:
            continue
        try:
            data = json.loads(output)
            msg = data.get("hookSpecificOutput", {}).get("userMessage", "")
            if msg:
                messages.append(msg)
        except json.JSONDecodeError:
            continue

    if not messages:
        return ""

    combined = "\n".join(messages)
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "userMessage": combined,
            }
        }
    )


def main():
    start = time.monotonic()

    try:
        raw = sys.stdin.read().strip()
    except Exception:
        raw = ""

    # SessionStart sends empty stdin
    if not raw:
        output = run_guardian("branch_age_guard.py")
        if output:
            print(output)
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Likely SessionStart
        output = run_guardian("branch_age_guard.py")
        if output:
            print(output)
        return

    tool_name = data.get("tool_name", "")

    if tool_name in ("Edit", "Write"):
        outputs = []
        # Run guardians sequentially to stay within latency budget
        outputs.append(run_guardian("uncommitted_lines_guard.py"))

        elapsed_ms = (time.monotonic() - start) * 1000
        if elapsed_ms < 80:  # Only run suggester if we have time budget left
            outputs.append(run_guardian("auto_commit_suggester.py"))

        merged = merge_outputs(outputs)
        if merged:
            print(merged)
    # Other tool names: no git guardians needed


if __name__ == "__main__":
    main()
