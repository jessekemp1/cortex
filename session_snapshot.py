#!/usr/bin/env python3
"""
Session Snapshot — writes a handoff block to .workflow/current/progress.md before session rotation.

Called by session_watcher.rotate_session(). Prepends a timestamped handoff section
so that /start can immediately orient the next session.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

MONOREPO_ROOT = Path(__file__).resolve().parent.parent
GOALS_PATH = MONOREPO_ROOT / "GOALS.md"
WORKFLOW_PROGRESS = MONOREPO_ROOT / ".workflow" / "current" / "progress.md"


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stripped stdout, empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, cwd=str(MONOREPO_ROOT)
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _pending_immediate_actions() -> list[str]:
    """
    Extract unchecked - [ ] items from the 'This Week' / 'Immediate Actions' section of GOALS.md.

    Returns at most 8 items (enough for a handoff, not the full backlog).
    """
    items = []
    try:
        text = GOALS_PATH.read_text()
        in_section = False
        for line in text.splitlines():
            stripped = line.strip()
            if any(h in line for h in ("### This Week", "## Immediate Actions")):
                in_section = True
            elif stripped.startswith("## ") and "Immediate" not in line and "This Week" not in line:
                in_section = False
            if in_section and stripped.startswith("- [ ]"):
                items.append(stripped[6:].strip()[:100])
    except Exception:
        pass
    return items[:8]


def _current_branch() -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"


def write_progress_snapshot(reason: str = "session_rotation") -> None:
    """
    Prepend a handoff block to .workflow/current/progress.md.

    Preserves all existing content after the new block — the file becomes
    a chronological log of rotation events.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    branch = _current_branch()
    git_status = _run(["git", "status", "--short"]) or "(clean)"
    git_log = _run(["git", "log", "--oneline", "-5"])
    pending = _pending_immediate_actions()

    pending_block = (
        "\n".join(f"  - {item}" for item in pending) if pending else "  (none — check GOALS.md)"
    )

    existing = ""
    if WORKFLOW_PROGRESS.exists():
        existing = WORKFLOW_PROGRESS.read_text()

    snapshot = f"""# Session Handoff — {ts}
**Rotation reason:** {reason}
**Branch:** {branch}

## Working Tree
```
{git_status}
```

## Last 5 Commits
```
{git_log}
```

## Pending This Week (from GOALS.md)
{pending_block}

## Resume Instructions
1. Run `claude` in the project directory
2. `/start` — picks up this snapshot and runs briefing + next
3. Check `.workflow/current/` for any in-progress plan/spec files

---

{existing}""".lstrip()

    WORKFLOW_PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW_PROGRESS.write_text(snapshot)
