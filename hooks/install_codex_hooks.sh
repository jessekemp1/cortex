#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/hooks/codex_interaction_capture.py"

cat <<EOF
Codex Hook Setup
================

Hook command:
python "$HOOK"

Send JSON payload via stdin:
{
  "event": "prompt|tool_complete|stop|session_end",
  "session_id": "optional",
  "cwd": "/path",
  "prompt": "...",
  "tool_name": "...",
  "tool_input": {},
  "tool_response": {},
  "reason": "exit"
}

Queue target: ~/.cortex/interaction_queue.jsonl
EOF
