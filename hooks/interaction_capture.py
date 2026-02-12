#!/usr/bin/env python3
"""
Cortex Interaction Capture Hooks for Claude Code

This module provides hook handlers that capture Claude Code interactions
and feed them into Cortex's learning system in real-time.

Hooks:
- UserPromptSubmit: Captures user prompts
- PostToolUse: Captures tool usage and outcomes
- Stop: Captures response completion
- SessionEnd: Triggers session summarization

Usage in Claude Code settings.json:
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "python /path/to/cortex/hooks/interaction_capture.py prompt"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python /path/to/cortex/hooks/interaction_capture.py tool_complete"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python /path/to/cortex/hooks/interaction_capture.py stop"
      }]
    }],
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "python /path/to/cortex/hooks/interaction_capture.py session_end"
      }]
    }]
  }
}
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add cortex to path
CORTEX_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(CORTEX_DIR))

# Configure minimal logging (hooks must be fast)
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)

# Storage path for async processing
INTERACTION_QUEUE = Path.home() / ".cortex" / "interaction_queue.jsonl"


def get_hook_input() -> dict:
    """Read hook input from stdin (Claude Code passes JSON)."""
    try:
        return json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse hook input: {e}")
        return {}


def queue_interaction(interaction: dict) -> None:
    """
    Queue interaction for async processing.

    This ensures hooks complete quickly (< 100ms) while still capturing data.
    The queue is processed by the Cortex daemon or next CLI invocation.
    """
    INTERACTION_QUEUE.parent.mkdir(parents=True, exist_ok=True)

    interaction["queued_at"] = datetime.now().isoformat()

    with open(INTERACTION_QUEUE, "a") as f:
        f.write(json.dumps(interaction) + "\n")


def capture_prompt(hook_input: dict) -> None:
    """
    Capture user prompt submission.

    Input from Claude Code:
    {
        "session_id": "abc123",
        "transcript_path": "/path/to/transcript.jsonl",
        "cwd": "/current/working/dir",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "the user's prompt text"
    }
    """
    prompt = hook_input.get("prompt", "")
    session_id = hook_input.get("session_id")
    cwd = hook_input.get("cwd", os.getcwd())

    # Detect and track slash commands
    command_info = None
    try:
        command_info = track_command_if_present(prompt, session_id, cwd)
    except Exception:
        pass  # Never block on command tracking

    queue_interaction(
        {
            "type": "prompt_received",
            "session_id": session_id,
            "cwd": cwd,
            "prompt": prompt,
            "transcript_path": hook_input.get("transcript_path"),
            "command": command_info.get("command") if command_info else None,
        }
    )

    # Output context enhancement based on patterns (optional)
    try:
        context = get_contextual_hint(hook_input)
        if context:
            print(f"<cortex-hint>{context}</cortex-hint>")
    except Exception:
        pass  # Never block on hint generation


def capture_tool_complete(hook_input: dict) -> None:
    """
    Capture tool execution completion.

    Input from Claude Code:
    {
        "session_id": "abc123",
        "tool_name": "Edit",
        "tool_input": {...},
        "tool_response": {...},
        "cwd": "/current/working/dir"
    }
    """
    tool_response = hook_input.get("tool_response", {})
    success = determine_tool_success(tool_response)

    queue_interaction(
        {
            "type": "tool_completed",
            "session_id": hook_input.get("session_id"),
            "cwd": hook_input.get("cwd", os.getcwd()),
            "tool_name": hook_input.get("tool_name"),
            "tool_input": sanitize_tool_input(hook_input.get("tool_input", {})),
            "success": success,
            "response_summary": summarize_response(tool_response),
        }
    )


def capture_stop(hook_input: dict) -> None:
    """
    Capture response completion.

    This signals that Claude has finished responding, allowing us to
    correlate prompts with responses.
    """
    queue_interaction(
        {
            "type": "response_completed",
            "session_id": hook_input.get("session_id"),
            "cwd": hook_input.get("cwd", os.getcwd()),
        }
    )


def capture_session_end(hook_input: dict) -> None:
    """
    Capture session end and trigger learning.

    Input from Claude Code:
    {
        "session_id": "abc123",
        "hook_event_name": "SessionEnd",
        "reason": "exit"
    }
    """
    session_id = hook_input.get("session_id")

    # Finalize command tracking for this session (extracts workflow patterns)
    try:
        from engines.command_tracker import get_tracker

        tracker = get_tracker()
        tracker._finalize_session()
    except Exception as e:
        logger.debug(f"Command session finalization failed: {e}")

    queue_interaction(
        {
            "type": "session_ended",
            "session_id": session_id,
            "cwd": hook_input.get("cwd", os.getcwd()),
            "reason": hook_input.get("reason", "unknown"),
        }
    )

    # Trigger async learning processing
    try:
        trigger_learning_pipeline()
    except Exception as e:
        logger.warning(f"Failed to trigger learning: {e}")


def determine_tool_success(response: dict) -> bool:
    """Determine if tool execution was successful."""
    if not response:
        return True  # Assume success if no response

    # Explicit success field
    if "success" in response:
        return bool(response["success"])

    # Error indicators
    error_indicators = ["error", "failed", "exception", "traceback"]
    response_str = json.dumps(response).lower()

    return not any(indicator in response_str for indicator in error_indicators)


def sanitize_tool_input(tool_input: dict) -> dict:
    """Remove sensitive data from tool input."""
    if not isinstance(tool_input, dict):
        return {}

    sensitive_keys = ["password", "secret", "token", "key", "credential", "auth"]
    sanitized = {}

    for key, value in tool_input.items():
        if any(s in key.lower() for s in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 500:
            sanitized[key] = value[:500] + "..."
        else:
            sanitized[key] = value

    return sanitized


def summarize_response(response: dict) -> dict:
    """Create a compact summary of tool response."""
    if not response:
        return {"empty": True}

    summary = {
        "has_error": "error" in str(response).lower(),
    }

    if isinstance(response, dict):
        if "success" in response:
            summary["success"] = response["success"]
        if "filePath" in response:
            summary["file_affected"] = True
        if "output" in response:
            summary["output_length"] = len(str(response["output"]))

    return summary


def track_command_if_present(prompt: str, session_id: str, cwd: str) -> dict:
    """
    Detect and track slash commands in user prompts.

    Returns command info dict if command detected, None otherwise.
    """
    try:
        from engines.command_tracker import get_tracker

        tracker = get_tracker()
        result = tracker.detect_command(prompt)

        if result:
            command_type, arguments = result

            # Derive project from cwd
            project = None
            cwd_path = Path(cwd)
            if "vortex" in cwd_path.as_posix().lower():
                project = "VortexV2"
            elif "alpha_arena" in cwd_path.as_posix().lower():
                project = "alpha_arena"
            elif "cortex" in cwd_path.as_posix().lower():
                project = "cortex"

            # Track the command execution
            tracker.track_command(
                command=command_type,
                session_id=session_id or "unknown",
                project=project,
                arguments=arguments,
            )

            return {
                "command": command_type.value,
                "arguments": arguments,
                "project": project,
            }

    except Exception as e:
        logger.debug(f"Command tracking failed: {e}")

    return None


def get_contextual_hint(hook_input: dict) -> str:
    """
    Generate a contextual hint based on detected patterns.

    This is optional and provides real-time guidance based on
    historical patterns without blocking the user.
    """
    try:
        from engines.claude_session_absorber import ClaudeSessionSource

        source = ClaudeSessionSource()
        stats = source.get_implicit_feedback_stats(days=7)

        # If correction rate is high, suggest being more careful
        if stats.get("correction_rate", 0) > 0.15:
            return (
                "Pattern: Higher than usual corrections detected. Consider verifying assumptions."
            )

        return ""
    except Exception:
        return ""


def trigger_learning_pipeline() -> None:
    """
    Trigger the learning pipeline to process queued interactions.

    This runs asynchronously and doesn't block the hook.
    """
    import subprocess

    # Fire-and-forget subprocess
    subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from cortex.learning import InteractionLearner; InteractionLearner().process_queue()",
        ],
        cwd=str(CORTEX_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main():
    """Main entry point for interaction capture hook."""
    if len(sys.argv) < 2:
        print(
            "Usage: interaction_capture.py <prompt|tool_complete|stop|session_end>",
            file=sys.stderr,
        )
        sys.exit(1)

    command = sys.argv[1]
    hook_input = get_hook_input()

    handlers = {
        "prompt": capture_prompt,
        "tool_complete": capture_tool_complete,
        "stop": capture_stop,
        "session_end": capture_session_end,
    }

    handler = handlers.get(command)
    if handler:
        try:
            handler(hook_input)
            sys.exit(0)  # Success
        except Exception as e:
            logger.error(f"Hook handler failed: {e}")
            sys.exit(0)  # Don't block on errors
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
