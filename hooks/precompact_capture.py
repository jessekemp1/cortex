#!/usr/bin/env python3
"""
PreCompact hook — ensure a structured handoff exists before Claude Code compacts.

Why
---
Claude Code's native `/compact` summarizes the conversation into prose,
dropping the structured nuance (verified gates, file:line references,
open questions) that downstream sessions need. Today the user
defensively chooses `/clear` instead, which loses even more. This hook
runs before compaction and guarantees `.workflow/current/handoff.yaml`
is current — so agents can use `/compact` without losing the structured
handoff that `cortex/runtime/handoff.py` owns.

Behavior
--------
1. If `handoff.yaml` already exists and is fresh (agent wrote it recently),
   do nothing — the agent has already captured state.
2. If `handoff.yaml` is missing or stale, write a minimal fallback from
   git state (branch, last commit, diff status) so compaction doesn't
   leave downstream sessions with nothing.
3. Never block compaction. All failures are logged and swallowed — the
   hook exits 0 even on error, because blocking /compact is a worse
   outcome than a missing handoff.

Input (via stdin, per Claude Code hook contract)
-------------------------------------------------
{
  "session_id":      "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "hook_event_name": "PreCompact",
  "trigger":         "manual" | "auto",
  "custom_instructions": "..."   # present only on manual /compact
}

Usage in Claude Code settings.json
-----------------------------------
{
  "hooks": {
    "PreCompact": [{
      "hooks": [{
        "type": "command",
        "command": "python /path/to/cortex/hooks/precompact_capture.py",
        "timeout": 5
      }]
    }]
  }
}
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make cortex package importable when invoked as a standalone script.
CORTEX_DIR = Path(__file__).resolve().parent.parent
if str(CORTEX_DIR) not in sys.path:
    sys.path.insert(0, str(CORTEX_DIR))
if str(CORTEX_DIR.parent) not in sys.path:
    sys.path.insert(0, str(CORTEX_DIR.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [precompact] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# A handoff written within this window is considered fresh — the agent has
# already captured state and the hook should not overwrite it.
_FRESH_HANDOFF_WINDOW = timedelta(minutes=10)


def _git(args: list[str], cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(cwd),
        )
        return out.stdout.strip()
    except Exception:
        return ""


def _handoff_is_fresh(handoff_path: Path) -> bool:
    """Return True if handoff.yaml exists and was written within the fresh window."""
    if not handoff_path.exists():
        return False
    try:
        import yaml

        with open(handoff_path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return False
        written_at = data.get("_written_at")
        if not written_at:
            return False
        ts = datetime.fromisoformat(written_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        return age < _FRESH_HANDOFF_WINDOW
    except Exception as exc:
        log.debug("handoff freshness check failed: %s", exc)
        return False


def _write_fallback_handoff(cwd: Path, workflow_dir: Path, trigger: str) -> bool:
    """Write a minimal git-state handoff so compact doesn't lose everything.

    Returns True if something was written.
    """
    try:
        from cortex.runtime.handoff import HandoffFields, write_handoff
    except ImportError:
        try:
            from runtime.handoff import HandoffFields, write_handoff  # type: ignore[no-redef]
        except ImportError as exc:
            log.warning("cannot import runtime.handoff: %s", exc)
            return False

    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "unknown"
    last_commit = _git(["log", "--oneline", "-1"], cwd) or "(no commits)"
    status_lines = _git(["status", "--short"], cwd).splitlines()
    modified_files = [line[3:] for line in status_lines if line][:10]

    done: list[str] = []
    if last_commit and last_commit != "(no commits)":
        done.append(f"last commit: {last_commit}")

    open_questions: list[str] = []
    if modified_files:
        open_questions.append(
            f"uncommitted changes in {len(modified_files)} file(s): "
            f"{', '.join(modified_files[:5])}"
            + (" …" if len(modified_files) > 5 else "")
        )

    fields = HandoffFields(
        done=done,
        verified=[],
        open_questions=open_questions,
        next_action=(
            "Resume from the last commit. Hook-generated fallback — "
            "no agent-authored handoff was present at compact time."
        ),
        gate_command="git status --short",
        confidence=0.2,  # low: this is a machine-generated fallback
    )

    try:
        path = write_handoff(fields, workflow_dir=workflow_dir)
        log.info(
            "wrote fallback handoff to %s (branch=%s, trigger=%s)",
            path,
            branch,
            trigger,
        )
        return True
    except Exception as exc:
        log.warning("fallback handoff write failed: %s", exc)
        return False


def run(hook_input: dict) -> int:
    """Main hook entry. Returns exit code (always 0 — never block compact)."""
    session_id = hook_input.get("session_id", "?")[:8]
    trigger = hook_input.get("trigger", "unknown")
    cwd = Path(hook_input.get("cwd") or os.getcwd())

    # Prefer an explicit override if the harness sets one; else cwd-relative.
    env_dir = os.environ.get("CORTEX_WORKFLOW_DIR")
    workflow_dir = Path(env_dir) if env_dir else cwd / ".workflow" / "current"

    handoff_path = workflow_dir / "handoff.yaml"

    if _handoff_is_fresh(handoff_path):
        log.info(
            "handoff is fresh at %s — skipping fallback (session=%s, trigger=%s)",
            handoff_path,
            session_id,
            trigger,
        )
        return 0

    log.info(
        "handoff missing or stale at %s — writing fallback (session=%s, trigger=%s)",
        handoff_path,
        session_id,
        trigger,
    )
    _write_fallback_handoff(cwd, workflow_dir, trigger)
    return 0


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            log.warning("no stdin payload — exiting")
            return 0
        hook_input = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("malformed stdin JSON: %s", exc)
        return 0
    except Exception as exc:
        log.warning("stdin read failed: %s", exc)
        return 0

    try:
        return run(hook_input)
    except Exception as exc:
        # Blanket catch — never block /compact.
        log.warning("hook run failed: %s", exc)
        return 0


if __name__ == "__main__":
    sys.exit(main())
