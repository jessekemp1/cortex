#!/usr/bin/env python3
"""
Session Ingest Hook — Claude Code Stop/SessionEnd hook entry point.

Reads transcript path from the hook event (stdin JSON) and ingests
the full conversation into Cortex's learning store.

Hook config (add to ~/.claude/settings.json):
  "Stop": [{
    "hooks": [{
      "type": "command",
      "command": "python /home/user/cortex/hooks/session_ingest_hook.py",
      "timeout": 10
    }]
  }]
"""

import json
import logging
import os
import sys
from pathlib import Path

# Ensure cortex root is importable
_CORTEX_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CORTEX_DIR))

logger = logging.getLogger("cortex.hooks.session_ingest")


def main() -> None:
    """Read hook input from stdin and ingest the conversation."""
    # Configure minimal logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    # Try to find the transcript path
    transcript_path = hook_input.get("transcript_path", "")
    session_id = hook_input.get("session_id", "")

    # If no transcript_path in the hook input, try to find the most recent
    # session file matching this session
    if not transcript_path and session_id:
        projects_dir = Path.home() / ".claude" / "projects"
        if projects_dir.is_dir():
            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                candidate = project_dir / f"{session_id}.jsonl"
                if candidate.exists():
                    transcript_path = str(candidate)
                    break

    # If still no path, try to find most recently modified .jsonl
    if not transcript_path:
        projects_dir = Path.home() / ".claude" / "projects"
        if projects_dir.is_dir():
            latest = None
            latest_mtime = 0
            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                for f in project_dir.glob("*.jsonl"):
                    mtime = f.stat().st_mtime
                    if mtime > latest_mtime:
                        latest = f
                        latest_mtime = mtime
            if latest:
                transcript_path = str(latest)

    if not transcript_path:
        logger.debug("No transcript path found, skipping ingestion")
        return

    # Ingest
    try:
        from engines.conversation_ingestor import ConversationIngestor

        ingestor = ConversationIngestor()
        digest = ingestor.ingest_single(transcript_path)
        if digest:
            logger.info(
                f"Ingested {digest.session_id}: "
                f"{digest.user_prompt_count} prompts, "
                f"{digest.correction_count} corrections, "
                f"outcome={digest.outcome}"
            )
    except Exception as e:
        logger.warning(f"Ingestion failed: {e}")


if __name__ == "__main__":
    main()
