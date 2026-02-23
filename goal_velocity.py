"""
Goal Velocity — read-side API for commit_tracer data.

Answers:
  - Which goals have had commits in the last N days?
  - Which goals are stalled (no commits in N days)?
  - What's the velocity (commits, files, lines) per goal?

Used by: /briefing, /portfolio-status (future), session_start_context.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


VELOCITY_LOG = Path.home() / ".cortex" / "metrics" / "goal_velocity.jsonl"


def _load_entries(days: int = 7) -> list[dict]:
    """Load goal velocity entries from the last N days."""
    if not VELOCITY_LOG.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    try:
        for line in VELOCITY_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e.get("ts", ""))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    entries.append(e)
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        pass
    return entries


def get_velocity(days: int = 7) -> dict[str, dict]:
    """
    Return velocity stats per goal for the last N days.

    Returns:
        {goal_title: {commits, files_changed, insertions, last_commit_ts}}
    """
    entries = _load_entries(days)
    stats: dict[str, dict] = {}

    for e in entries:
        goal = e.get("goal") or "unattributed"
        if goal not in stats:
            stats[goal] = {
                "commits": 0,
                "files_changed": 0,
                "insertions": 0,
                "last_commit": None,
                "goal_status": e.get("goal_status", "unknown"),
            }
        s = stats[goal]
        s["commits"] += 1
        s["files_changed"] += e.get("files_changed", 0)
        s["insertions"] += e.get("insertions", 0)
        ts = e.get("ts", "")
        if s["last_commit"] is None or ts > s["last_commit"]:
            s["last_commit"] = ts

    return stats


def get_stale_goals(all_goal_titles: list[str], days: int = 3) -> list[str]:
    """
    Return goal titles with no commits in the last N days.

    Requires the caller to pass the full list of active goal titles
    (from GOALS.md) so we can detect goals with zero entries.
    """
    velocity = get_velocity(days)
    active_goals_with_activity = set(velocity.keys()) - {"unattributed"}
    return [g for g in all_goal_titles if g not in active_goals_with_activity]


def format_velocity_summary(days: int = 7) -> str | None:
    """
    Format a brief velocity summary for /briefing output.

    Returns a multi-line string, or None if no data.
    """
    velocity = get_velocity(days)
    if not velocity:
        return None

    # Sort by commit count descending, put unattributed last
    ordered = sorted(
        [(k, v) for k, v in velocity.items() if k != "unattributed"],
        key=lambda x: x[1]["commits"],
        reverse=True,
    )
    unattr = velocity.get("unattributed")

    lines = [f"Goal Velocity (last {days}d):"]
    for goal, stats in ordered[:5]:
        c = stats["commits"]
        ins = stats["insertions"]
        status = stats.get("goal_status", "")
        status_tag = " [COMPLETE]" if status == "complete" else ""
        lines.append(f"  • {goal}{status_tag}: {c} commit{'s' if c != 1 else ''}, +{ins} lines")

    if unattr:
        c = unattr["commits"]
        lines.append(f"  • (unattributed): {c} commit{'s' if c != 1 else ''}")

    return "\n".join(lines)


if __name__ == "__main__":
    summary = format_velocity_summary(days=7)
    if summary:
        print(summary)
    else:
        print("No goal velocity data yet. Data accumulates from post-commit hook.")
        print(f"Log: {VELOCITY_LOG}")
