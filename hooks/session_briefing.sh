#!/bin/bash
# Cortex session briefing — called by Claude Code SessionStart hook.
# Hits the local bridge for recommendations + plan progress and
# outputs a compact briefing to stdout (appears in session context).

BRIDGE="http://127.0.0.1:8765"
TIMEOUT=3

recs=$(curl -sf --max-time $TIMEOUT "$BRIDGE/recommendations" 2>/dev/null)
plans=$(curl -sf --max-time $TIMEOUT "$BRIDGE/plan-progress" 2>/dev/null)

if [ -z "$recs" ] && [ -z "$plans" ]; then
  exit 0
fi

echo "── Cortex Briefing ──"

if [ -n "$recs" ]; then
  next=$(echo "$recs" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    na = d.get('next_action', {})
    if na.get('action'):
        print(f\"Next: {na['action']} [{na.get('priority','?')}]\")
    for r in d.get('risk_alerts', [])[:2]:
        print(f\"Risk: {r.get('message','')} [{r.get('severity','?')}]\")
except: pass
" 2>/dev/null)
  [ -n "$next" ] && echo "$next"
fi

if [ -n "$plans" ]; then
  progress=$(echo "$plans" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    plans = d if isinstance(d, list) else d.get('plans', [])
    for p in plans[:3]:
        name = p.get('title', p.get('name', '?'))
        done = p.get('completed', p.get('done', 0))
        total = p.get('total', p.get('tasks', 0))
        if total > 0:
            print(f\"Plan: {name} [{done}/{total}]\")
except: pass
" 2>/dev/null)
  [ -n "$progress" ] && echo "$progress"
fi

echo "─────────────────────"
