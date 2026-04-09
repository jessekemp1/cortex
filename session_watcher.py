#!/usr/bin/env python3
"""
Cortex Session Watcher — Detects long-running Claude Code sessions and rotates them.

Called by heartbeat.py every 30 minutes. Checks if the active claude process has exceeded
age or request-count thresholds, then:
  1. Writes a handoff snapshot to .workflow/current/progress.md
  2. Sends a macOS notification + Slack message (if configured)
  3. SIGTERMs the claude process

The user restarts with `claude` — /start picks up the snapshot automatically.

Usage:
  python cortex/session_watcher.py            # check + rotate if needed
  python cortex/session_watcher.py --dry-run  # report without acting
  python cortex/session_watcher.py --status   # just print current state
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CORTEX_DIR = Path(__file__).resolve().parent
MONOREPO_ROOT = CORTEX_DIR.parent
INTERACTION_QUEUE = Path.home() / ".cortex" / "interaction_queue.jsonl"
SESSION_WATCHER_STATE = Path.home() / ".cortex" / "session_watcher_state.json"
HEARTBEAT_CONFIG = Path.home() / ".cortex" / "heartbeat_config.json"

# Thresholds (tune here or override via ~/.cortex/session_watcher_config.json)
SESSION_MAX_HOURS = 3
SESSION_MAX_REQUESTS = 80

# Minimum interval between rotations (prevent rapid repeat triggers)
MIN_ROTATION_INTERVAL_HOURS = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_thresholds() -> dict:
    """Load thresholds from config file if present."""
    cfg_path = Path.home() / ".cortex" / "session_watcher_config.json"
    defaults = {
        "max_hours": SESSION_MAX_HOURS,
        "max_requests": SESSION_MAX_REQUESTS,
        "min_rotation_interval_hours": MIN_ROTATION_INTERVAL_HOURS,
    }
    try:
        if cfg_path.exists():
            defaults.update(json.loads(cfg_path.read_text()))
    except Exception:
        pass
    return defaults


def find_claude_pid() -> int | None:
    """
    Find the main Claude Code process PID via ps.

    Looks for a process named 'claude' that isn't a Python hook script or grep.
    Returns the lowest-PID match (the parent process, not subprocesses).
    """
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        candidates = []
        for line in result.stdout.splitlines():
            # Match standalone 'claude' binary — exclude grep/python/node wrapper lines
            if not re.search(r"\bclaude\b", line):
                continue
            if any(skip in line for skip in ("grep", "python", "session_watcher", "heartbeat")):
                continue
            parts = line.split()
            if len(parts) > 1:
                try:
                    candidates.append(int(parts[1]))
                except ValueError:
                    continue
        return min(candidates) if candidates else None
    except Exception:
        return None


def get_process_age_hours(pid: int) -> float | None:
    """
    Get process uptime in hours using ps etime.

    etime format: [[DD-]HH:]MM:SS
    """
    try:
        result = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        etime = result.stdout.strip()
        if not etime:
            return None
        parts = [int(p) for p in etime.replace("-", ":").split(":")]
        if len(parts) == 2:  # MM:SS
            return parts[0] / 60
        elif len(parts) == 3:  # HH:MM:SS
            return parts[0] + parts[1] / 60
        elif len(parts) == 4:  # DD:HH:MM:SS
            return parts[0] * 24 + parts[1] + parts[2] / 60
    except Exception:
        pass
    return None


def count_recent_prompts(hours: float) -> int:
    """
    Count UserPromptSubmit events in ~/.cortex/interaction_queue.jsonl within the last N hours.

    The interaction_capture.py hook writes events with a 'queued_at' timestamp.
    """
    count = 0
    cutoff = _now() - timedelta(hours=hours)
    try:
        if not INTERACTION_QUEUE.exists():
            return 0
        lines = INTERACTION_QUEUE.read_text().strip().splitlines()
        for line in lines[-500:]:  # only scan recent tail
            try:
                entry = json.loads(line)
                if entry.get("type") not in ("prompt", "UserPromptSubmit"):
                    continue
                ts_str = entry.get("queued_at") or entry.get("timestamp", "")
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts > cutoff:
                    count += 1
            except Exception:
                continue
    except Exception:
        pass
    return count


def _was_recently_rotated(min_interval_hours: float) -> bool:
    """Prevent back-to-back rotations within the minimum interval."""
    try:
        if SESSION_WATCHER_STATE.exists():
            state = json.loads(SESSION_WATCHER_STATE.read_text())
            last = datetime.fromisoformat(state.get("last_rotation", "2000-01-01T00:00:00+00:00"))
            return _now() - last < timedelta(hours=min_interval_hours)
    except Exception:
        pass
    return False


def _notify(message: str) -> None:
    """macOS notification + stderr fallback."""
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "Cortex Session Watcher"',
            ],
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass
    print(f"[session_watcher] {message}", file=sys.stderr)


def _send_slack(message: str) -> None:
    """Send Slack message via heartbeat config (best-effort)."""
    try:
        if not HEARTBEAT_CONFIG.exists():
            return
        config = json.loads(HEARTBEAT_CONFIG.read_text())
        token = config.get("slack_token") or os.environ.get("SLACK_BOT_TOKEN", "")
        channel = config.get("slack_channel", "")
        if not token or not channel:
            return
        import urllib.request

        payload = json.dumps({"channel": channel, "text": message, "mrkdwn": True}).encode()
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def rotate_session(pid: int, reason: str) -> None:
    """
    Save snapshot → notify → SIGTERM the claude process.

    Does NOT restart claude — the user resumes with `claude` + /start.
    """
    # Snapshot first (before killing anything)
    try:
        sys.path.insert(0, str(CORTEX_DIR))
        from session_snapshot import write_progress_snapshot

        write_progress_snapshot(reason=reason)
    except Exception as e:
        print(f"[session_watcher] snapshot failed: {e}", file=sys.stderr)

    # Notify
    short_msg = f"Session rotated ({reason}). Run 'claude' to resume."
    slack_msg = (
        f":recycle: *Cortex Session Watcher* — Session rotated\n"
        f"  Reason: {reason}\n"
        f"  Run `claude` then `/start` to resume — snapshot saved to `.workflow/current/progress.md`"
    )
    _notify(short_msg)
    _send_slack(slack_msg)

    # Record rotation
    try:
        SESSION_WATCHER_STATE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_WATCHER_STATE.write_text(
            json.dumps(
                {
                    "last_rotation": _now().isoformat(),
                    "reason": reason,
                    "pid": pid,
                }
            )
        )
    except Exception:
        pass

    # Graceful kill
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # Process already gone


def check_and_rotate_if_needed(dry_run: bool = False) -> str:
    """
    Main entry point. Called by heartbeat.py every 30 minutes.

    Returns a status string suitable for logging.
    """
    cfg = _load_thresholds()
    max_hours = cfg["max_hours"]
    max_requests = cfg["max_requests"]
    min_interval = cfg["min_rotation_interval_hours"]

    pid = find_claude_pid()
    if not pid:
        return "no_claude_process"

    if _was_recently_rotated(min_interval):
        return f"skipped: rotated within last {min_interval}h"

    age_hours = get_process_age_hours(pid)
    prompt_count = count_recent_prompts(hours=max_hours)

    age_str = f"{age_hours:.1f}h" if age_hours is not None else "unknown"
    status_ok = f"ok (pid={pid}, age={age_str}, requests={prompt_count})"

    reasons = []
    if age_hours is not None and age_hours >= max_hours:
        reasons.append(f"age={age_str} >= {max_hours}h")
    if prompt_count >= max_requests:
        reasons.append(f"requests={prompt_count} >= {max_requests}")

    if not reasons:
        return status_ok

    reason_str = ", ".join(reasons)
    if dry_run:
        return f"would_rotate (pid={pid}): {reason_str}"

    rotate_session(pid, reason_str)
    return f"rotated (pid={pid}): {reason_str}"


def _print_status() -> None:
    """Print current session state without acting."""
    cfg = _load_thresholds()
    pid = find_claude_pid()
    if not pid:
        print("No claude process found.")
        return
    age = get_process_age_hours(pid)
    prompts = count_recent_prompts(hours=cfg["max_hours"])
    age_str = f"{age:.1f}h" if age else "unknown"
    print(f"Claude PID:    {pid}")
    print(f"Process age:   {age_str} (limit: {cfg['max_hours']}h)")
    print(f"Recent prompts:{prompts} (limit: {cfg['max_requests']} in last {cfg['max_hours']}h)")

    state_file = SESSION_WATCHER_STATE
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            print(
                f"Last rotation: {state.get('last_rotation', 'never')} ({state.get('reason', '?')})"
            )
        except Exception:
            pass


if __name__ == "__main__":
    if "--status" in sys.argv:
        _print_status()
    else:
        dry_run = "--dry-run" in sys.argv
        result = check_and_rotate_if_needed(dry_run=dry_run)
        print(result)
