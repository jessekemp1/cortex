"""
Canonical event adapter for cross-tool interaction capture.

Normalizes Claude Code and Codex hook payloads into a shared schema so the
learning pipeline can process both sources consistently.
"""

from datetime import datetime
from typing import Any, Dict, Optional


def _base_event(
    event_type: str,
    source: str,
    session_id: Optional[str],
    cwd: Optional[str],
) -> Dict[str, Any]:
    return {
        "type": event_type,
        "source": source,
        "session_id": session_id or "unknown",
        "cwd": cwd or "",
        "captured_at": datetime.now().isoformat(),
    }


def normalize_claude_event(command: str, hook_input: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Claude hook event into canonical schema."""
    if command == "prompt":
        event = _base_event(
            "prompt_received",
            "claude",
            hook_input.get("session_id"),
            hook_input.get("cwd"),
        )
        event["prompt"] = hook_input.get("prompt", "")
        event["transcript_path"] = hook_input.get("transcript_path")
        return event

    if command == "tool_complete":
        event = _base_event(
            "tool_completed",
            "claude",
            hook_input.get("session_id"),
            hook_input.get("cwd"),
        )
        event["tool_name"] = hook_input.get("tool_name")
        event["tool_input"] = hook_input.get("tool_input", {})
        event["tool_response"] = hook_input.get("tool_response", {})
        return event

    if command == "stop":
        return _base_event(
            "response_completed",
            "claude",
            hook_input.get("session_id"),
            hook_input.get("cwd"),
        )

    if command == "session_end":
        event = _base_event(
            "session_ended",
            "claude",
            hook_input.get("session_id"),
            hook_input.get("cwd"),
        )
        event["reason"] = hook_input.get("reason", "unknown")
        return event

    event = _base_event("unknown", "claude", hook_input.get("session_id"), hook_input.get("cwd"))
    event["raw_command"] = command
    event["raw"] = hook_input
    return event


def normalize_codex_event(event_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a Codex event into canonical schema.

    Expected top-level keys:
    - event: prompt|tool_complete|stop|session_end
    - session_id, cwd, prompt, tool_name, tool_input, tool_response, reason
    """
    event_name = str(event_input.get("event", "")).strip().lower()

    if event_name == "prompt":
        event = _base_event(
            "prompt_received",
            "codex",
            event_input.get("session_id"),
            event_input.get("cwd"),
        )
        event["prompt"] = event_input.get("prompt", "")
        return event

    if event_name == "tool_complete":
        event = _base_event(
            "tool_completed",
            "codex",
            event_input.get("session_id"),
            event_input.get("cwd"),
        )
        event["tool_name"] = event_input.get("tool_name")
        event["tool_input"] = event_input.get("tool_input", {})
        event["tool_response"] = event_input.get("tool_response", {})
        return event

    if event_name == "stop":
        return _base_event(
            "response_completed",
            "codex",
            event_input.get("session_id"),
            event_input.get("cwd"),
        )

    if event_name == "session_end":
        event = _base_event(
            "session_ended",
            "codex",
            event_input.get("session_id"),
            event_input.get("cwd"),
        )
        event["reason"] = event_input.get("reason", "unknown")
        return event

    event = _base_event("unknown", "codex", event_input.get("session_id"), event_input.get("cwd"))
    event["raw"] = event_input
    return event
