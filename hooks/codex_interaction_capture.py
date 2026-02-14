#!/usr/bin/env python3
"""
Codex interaction capture shim.

Accepts JSON from stdin, normalizes to Cortex canonical interaction events,
and appends to the shared interaction queue used by Claude hooks.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

CORTEX_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(CORTEX_DIR))

logger = logging.getLogger(__name__)
INTERACTION_QUEUE = Path.home() / ".cortex" / "interaction_queue.jsonl"
HOOK_STATUS_FILE = Path.home() / ".cortex" / "interaction_hook_status.json"
HOOK_ERROR_LOG = Path.home() / ".cortex" / "interaction_hook_errors.log"


def _write_status(**kwargs) -> None:
    try:
        HOOK_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": datetime.now().isoformat(), "source": "codex"}
        payload.update(kwargs)
        with open(HOOK_STATUS_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def _append_error(msg: str) -> None:
    try:
        HOOK_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOK_ERROR_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else {}
    except Exception as e:
        _append_error(f"codex hook parse error={e}")
        return {}


def _queue(event: dict) -> None:
    INTERACTION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    event["queued_at"] = datetime.now().isoformat()
    with open(INTERACTION_QUEUE, "a") as f:
        f.write(json.dumps(event) + "\n")


def main() -> int:
    try:
        from hooks.interaction_capture import trigger_learning_pipeline
        from intelligence.bandwidth.event_adapter import normalize_codex_event

        payload = _read_stdin_json()
        event = normalize_codex_event(payload)
        _queue(event)
        _write_status(last_queue_write="success", event_type=event.get("type"))

        if event.get("type") == "session_ended":
            trigger_learning_pipeline()
        return 0
    except Exception as e:
        _append_error(f"codex hook handler error={e}")
        _write_status(last_queue_write="failed", last_error=str(e))
        logger.error("codex interaction capture failed: %s", e)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
