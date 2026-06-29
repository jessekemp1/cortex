#!/bin/bash
# Cortex session debrief — called by Claude Code Stop hook.
# Reminds the agent to record decisions/outcomes before the session ends.

BRIDGE="http://127.0.0.1:8765"

# Only remind if bridge is up and session had meaningful work
health=$(curl -sf --max-time 2 "$BRIDGE/health" 2>/dev/null)
[ -z "$health" ] && exit 0

echo "── Cortex Debrief ──"
echo "Before ending: did you make any architectural decisions or complete tasks this session?"
echo "If so, call cortex_record_decision to capture them."
echo "────────────────────"
