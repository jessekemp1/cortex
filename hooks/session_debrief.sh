#!/bin/bash
# Cortex session debrief — called by Claude Code Stop hook.
# Reminds the agent to record decisions/outcomes before the session ends.

CORTEX_APP="https://cortex-dbx-dev-7474657396431162.aws.databricksapps.com"

# Only remind if deployed app is reachable
health=$(curl -sf --max-time 2 "$CORTEX_APP/health" 2>/dev/null)
[ -z "$health" ] && exit 0

echo "── Cortex Debrief ──"
echo "Before ending: did you make any architectural decisions or complete tasks this session?"
echo "If so, call mcp__cortex-dbx__record_decision to capture them."
echo "────────────────────"
