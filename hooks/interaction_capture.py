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
import subprocess
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
HOOK_STATUS_FILE = Path.home() / ".cortex" / "interaction_hook_status.json"
HOOK_ERROR_LOG = Path.home() / ".cortex" / "interaction_hook_errors.log"
LAST_PROJECT_FILE = Path.home() / ".cortex" / "metrics" / "last_project.txt"


def _write_hook_status(**kwargs) -> None:
    """Best-effort write of hook health state."""
    try:
        HOOK_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        status = {"timestamp": datetime.now().isoformat()}
        status.update(kwargs)
        with open(HOOK_STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception:
        pass


def _append_hook_error(message: str) -> None:
    """Best-effort append of hook errors."""
    try:
        HOOK_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOK_ERROR_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} {message}\n")
    except Exception:
        pass


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
    _write_hook_status(last_queue_write="success", event_type=interaction.get("type"))


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

    # Detect project switch for cost tracking
    try:
        _check_project_switch(cwd)
    except Exception:
        pass  # Never block on switch tracking

    # Detect and track slash commands
    command_info = None
    try:
        command_info = track_command_if_present(prompt, session_id, cwd)
    except Exception:
        pass  # Never block on command tracking

    from intelligence.bandwidth.event_adapter import normalize_claude_event

    event = normalize_claude_event("prompt", hook_input)
    event["session_id"] = session_id or event.get("session_id")
    event["cwd"] = cwd or event.get("cwd")
    event["prompt"] = prompt
    event["command"] = command_info.get("command") if command_info else None
    queue_interaction(event)

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

    from intelligence.bandwidth.event_adapter import normalize_claude_event

    event = normalize_claude_event("tool_complete", hook_input)
    event["cwd"] = hook_input.get("cwd", os.getcwd())
    event["tool_input"] = sanitize_tool_input(hook_input.get("tool_input", {}))
    event["success"] = success
    event["response_summary"] = summarize_response(tool_response)
    queue_interaction(event)


def capture_stop(hook_input: dict) -> None:
    """
    Capture response completion.

    This signals that Claude has finished responding, allowing us to
    correlate prompts with responses.
    """
    from intelligence.bandwidth.event_adapter import normalize_claude_event

    event = normalize_claude_event("stop", hook_input)
    event["cwd"] = hook_input.get("cwd", os.getcwd())
    queue_interaction(event)


def capture_session_end(hook_input: dict) -> None:
    """
    Capture session end and trigger learning.

    Input from Claude Code:
    {
        "session_id": "abc123",
        "hook_event_name": "SessionEnd",
        "transcript_path": "/path/to/session.jsonl",
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

    from intelligence.bandwidth.event_adapter import normalize_claude_event

    event = normalize_claude_event("session_end", hook_input)
    event["session_id"] = session_id or event.get("session_id")
    event["cwd"] = hook_input.get("cwd", os.getcwd())
    queue_interaction(event)

    # Ingest the full conversation transcript into digests
    try:
        transcript_path = hook_input.get("transcript_path")
        if transcript_path:
            trigger_conversation_ingestion(transcript_path)
    except Exception as e:
        logger.warning(f"Failed to trigger conversation ingestion: {e}")

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
                project = "vortex-backend"
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


def _detect_project(cwd: str) -> str | None:
    """Derive project name from working directory."""
    cwd_lower = cwd.lower()
    if "vortex" in cwd_lower:
        return "vortex"
    if "alpha_arena" in cwd_lower:
        return "alpha_arena"
    if "cortex" in cwd_lower:
        return "cortex"
    if "pupil" in cwd_lower:
        return "pupil"
    if "dj-copilot" in cwd_lower or "dj_copilot" in cwd_lower:
        return "dj-copilot"
    if "kempion" in cwd_lower:
        return "kempion"
    return None


def _estimate_baseline_tokens() -> int:
    """Estimate raw token cost without Cortex filtering (chars // 4)."""
    total_chars = 0
    for name in ("CLAUDE.md", "GOALS.md"):
        p = CORTEX_DIR.parent / name
        if p.exists():
            total_chars += len(p.read_text())
    memory_path = (
        Path.home() / ".claude" / "projects" / "-Users-jesse-kemp-Dev" / "memory" / "MEMORY.md"
    )
    if memory_path.exists():
        total_chars += len(memory_path.read_text())
    return total_chars // 4


def _check_project_switch(cwd: str) -> None:
    """Detect project switch and record cost if one occurred."""
    try:
        project = _detect_project(cwd)
        if not project:
            return

        LAST_PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)

        last_project = None
        if LAST_PROJECT_FILE.exists():
            last_project = LAST_PROJECT_FILE.read_text().strip()

        LAST_PROJECT_FILE.write_text(project)

        if last_project and last_project != project:
            from hooks.switch_tracker import SwitchTracker

            # "with cortex" = session cache size (CLAUDE.md filtered)
            claude_md = CORTEX_DIR.parent / "CLAUDE.md"
            preamble_tokens = len(claude_md.read_text()) // 4 if claude_md.exists() else 0

            # "without cortex" = raw sum of all context files
            context_tokens = _estimate_baseline_tokens()

            tracker = SwitchTracker()
            tracker.record_switch(last_project, project, preamble_tokens, context_tokens)
    except Exception:
        pass  # Never break interaction capture


_SELF_ROTATE_PATTERNS: tuple[str, ...] = (
    "/compact",
    "/clear",
    "fresh session",
    "new session",
    "start a new session",
    "context at ",
    "context is tight",
    "context tight",
    "checkpointing before",
    "checkpoint progress before",
    "recommend /compact",
    "recommend /clear",
)


def get_contextual_hint(hook_input: dict) -> str:
    """
    Inject a rollover-policy corrective when the user's prompt echoes a
    self-rotation pattern (typically because the agent just recommended one).

    Emits a single-line <cortex-hint> that the assistant sees via the
    UserPromptSubmit hook stdout. CLAUDE.md covers the steady-state policy;
    this hook is the runtime corrective for sessions that started before
    CLAUDE.md was installed or that drifted despite it.
    """
    prompt = (hook_input.get("prompt") or "").lower()
    if not prompt:
        return ""

    if not any(pat in prompt for pat in _SELF_ROTATE_PATTERNS):
        return ""

    return (
        "Rollover policy reminder (CLAUDE.md §1): do not recommend /compact, "
        "/clear, or 'fresh session'. Do not estimate context-%. If context is "
        "tight, write up to six YAML fields to .workflow/current/handoff.yaml "
        "and finish the atomic unit. Delegate via Task() instead of asking "
        "the user to open a new session."
    )


def trigger_conversation_ingestion(transcript_path: str) -> None:
    """
    Trigger async conversation ingestion for the completed session.

    Runs in a detached subprocess so the hook returns immediately.
    """
    cmd = (
        f"from engines.conversation_ingestor import ingest_conversation; "
        f"ingest_conversation({transcript_path!r})"
    )
    try:
        env = os.environ.copy()
        parent = str(CORTEX_DIR.parent)
        env["PYTHONPATH"] = (
            f"{CORTEX_DIR}{os.pathsep}{parent}{os.pathsep}{env.get('PYTHONPATH', '')}"
        )
        subprocess.Popen(
            [sys.executable, "-c", cmd],
            cwd=str(CORTEX_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
        )
        _write_hook_status(last_ingest="spawned", transcript=transcript_path)
    except Exception as e:
        _append_hook_error(f"trigger_conversation_ingestion error={e}")


def trigger_learning_pipeline() -> None:
    """
    Trigger the learning pipeline to process queued interactions.

    This runs asynchronously and doesn't block the hook.
    """
    cmd = (
        "from engines.interaction_learner import process_interaction_queue; "
        "result = process_interaction_queue(); "
        "print(result.get('status','unknown'))"
    )

    try:
        env = os.environ.copy()
        # Parent dir needed so `from cortex.state_paths` resolves
        parent = str(CORTEX_DIR.parent)
        env["PYTHONPATH"] = (
            f"{CORTEX_DIR}{os.pathsep}{parent}{os.pathsep}{env.get('PYTHONPATH', '')}"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", cmd],
            cwd=str(CORTEX_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
        )
        _write_hook_status(last_trigger_pid=proc.pid, last_trigger="spawned")
    except Exception as e:
        _append_hook_error(f"trigger_learning_pipeline error={e}")
        _write_hook_status(last_trigger="failed", last_error=str(e))


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
            _append_hook_error(f"handler={command} error={e}")
            _write_hook_status(last_handler=command, last_error=str(e))
            sys.exit(0)  # Don't block on errors
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
