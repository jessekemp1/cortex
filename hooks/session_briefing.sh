#!/bin/bash
# Cortex session briefing — called by Claude Code SessionStart hook.
#
# Surfaces recommendations + plan progress as compact stdout (lands in the
# session context), scoped to the current project when derivable from $PWD.
#
# Resilience contract (verified by the bridge-down drill):
#   - recommendations come from the bridge; if it's down, that section is
#     silently skipped (curl -sf, 2s cap) — never an error, never a hang.
#   - plan progress is read IN-PROCESS via mcp_handlers (stdlib-only, no
#     bridge needed) — the old /plan-progress endpoint no longer exists.
#   - always exits 0.

BRIDGE="${CORTEX_BRIDGE_URL:-http://127.0.0.1:8765}"
TIMEOUT=2
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Project scope: the basename of the current working directory (Claude Code
# runs SessionStart hooks from the workspace dir). Harmless if unknown to
# cortex — the recommendations route treats it as a filter.
PROJECT="$(basename "$PWD" 2>/dev/null)"

recs=$(curl -sf --max-time $TIMEOUT "$BRIDGE/recommendations?project=$PROJECT&limit=3" 2>/dev/null)
if [ -z "$recs" ]; then
  # Unscoped fallback — a project unknown to cortex shouldn't blank the briefing.
  recs=$(curl -sf --max-time $TIMEOUT "$BRIDGE/recommendations?limit=3" 2>/dev/null)
fi

plans=$(PYTHONPATH="$REPO_ROOT" python3 -c "
import json
try:
    import mcp_handlers
    print(json.dumps(mcp_handlers.plans_progress()))
except Exception:
    pass
" 2>/dev/null)

if [ -z "$recs" ] && [ -z "$plans" ]; then
  exit 0
fi

next=""
progress=""

if [ -n "$recs" ]; then
  next=$(echo "$recs" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for r in d.get('recommendations', [])[:3]:
        title = r.get('title') or r.get('action') or ''
        if title:
            print(f\"{r.get('type','rec')}: {title} [{r.get('priority','?')}]\")
    na = d.get('next_action', {})
    if isinstance(na, dict) and na.get('action'):
        print(f\"Next: {na['action']} [{na.get('priority','?')}]\")
    for r in d.get('risk_alerts', [])[:2]:
        print(f\"Risk: {r.get('message','')} [{r.get('severity','?')}]\")
except Exception: pass
" 2>/dev/null)
fi

if [ -n "$plans" ]; then
  progress=$(echo "$plans" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    plans = d if isinstance(d, list) else d.get('plans', [])
    for p in plans[:3]:
        name = p.get('title', p.get('name', '?'))
        by_status = p.get('by_status', {})
        done = by_status.get('done', p.get('completed', 0))
        total = p.get('item_count', p.get('total', 0))
        if total > 0:
            print(f\"Plan: {name} [{done}/{total}]\")
except Exception: pass
" 2>/dev/null)
fi

# Print the frame only when there's something to say.
if [ -z "$next" ] && [ -z "$progress" ]; then
  exit 0
fi

echo "── Cortex Briefing ──"
[ -n "$next" ] && echo "$next"
[ -n "$progress" ] && echo "$progress"
echo "─────────────────────"
exit 0
