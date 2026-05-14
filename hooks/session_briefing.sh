#!/bin/bash
# Cortex session briefing — called by Claude Code SessionStart hook.
# Hits the deployed cortex-dbx Databricks App via MCP Streamable HTTP
# to run intelligence_query and outputs a compact briefing to stdout.

CORTEX_APP="https://cortex-dbx-dev-7474657396431162.aws.databricksapps.com"
MCP_ENDPOINT="$CORTEX_APP/mcp/"
TIMEOUT=4

# Get Databricks auth token for the app's workspace
TOKEN=$(databricks auth token --profile fe-vm-cortex-dbx-dev 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
if [ -z "$TOKEN" ]; then
  TOKEN=$(databricks auth token 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
fi
if [ -z "$TOKEN" ]; then
  exit 0
fi
AUTH_HEADER="Authorization: Bearer $TOKEN"

# Helper: extract JSON from SSE "data: " lines, ignore "event:" lines
sse_to_json() { grep '^data: ' | head -1 | sed 's/^data: //'; }

# Step 1: Initialize MCP session
init_raw=$(curl -s --max-time $TIMEOUT \
  -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "$AUTH_HEADER" \
  -D /tmp/cortex_mcp_headers \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"cortex-hook","version":"1.0.0"}}}' 2>/dev/null)

if [ -z "$init_raw" ]; then
  rm -f /tmp/cortex_mcp_headers
  exit 0
fi

SESSION_ID=$(grep -i 'mcp-session-id' /tmp/cortex_mcp_headers 2>/dev/null | tr -d '\r' | awk '{print $2}')
rm -f /tmp/cortex_mcp_headers

# Step 2: Call intelligence_query tool
SESSION_HEADER=""
[ -n "$SESSION_ID" ] && SESSION_HEADER="-H Mcp-Session-Id:${SESSION_ID}"

raw_result=$(curl -s --max-time $TIMEOUT \
  -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "$AUTH_HEADER" \
  ${SESSION_HEADER} \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"intelligence_query","arguments":{"text":"session start: recent decisions, pending actions, anomalies","k":5,"anomaly_window_days":7}}}' 2>/dev/null)

# Extract JSON payload from SSE envelope
result=$(echo "$raw_result" | sse_to_json)
[ -z "$result" ] && result="$raw_result"

if [ -z "$result" ]; then
  exit 0
fi

# Parse the MCP tool result and format briefing
briefing=$(echo "$result" | python3 -c "
import sys, json
try:
    raw = sys.stdin.read().strip()
    d = json.loads(raw)
    # Navigate MCP response: result.content[0].text
    content = d.get('result', d)
    if isinstance(content, dict) and 'content' in content:
        for c in content['content']:
            if c.get('type') == 'text':
                inner = json.loads(c['text']) if c['text'].startswith('{') else {'summary': c['text']}
                break
        else:
            inner = content
    else:
        inner = content

    # Print decisions
    decisions = inner.get('decisions', [])
    if decisions:
        for dec in decisions[:3]:
            proj = dec.get('project', '?')
            summary = dec.get('decision', dec.get('context', ''))[:80]
            print(f'Decision [{proj}]: {summary}')

    # Print anomalies
    anomalies = inner.get('anomalies', [])
    for a in anomalies[:2]:
        z = a.get('z_score', '?')
        zfmt = f'{z:.1f}' if isinstance(z, (int, float)) else str(z)
        print(f\"Anomaly: {a.get('metric_name', '?')} z={zfmt} [{a.get('project', '?')}]\")

    # Print recommendations
    recs = inner.get('recommendations', [])
    for r in recs[:2]:
        print(f\"Next: {r.get('action', r.get('recommendation', '?'))} [{r.get('priority', '?')}]\")

    # Fallback: if none of the structured fields matched, print raw summary
    if not decisions and not anomalies and not recs:
        summary = inner.get('summary', inner.get('text', ''))
        if summary:
            print(summary[:200])
except Exception:
    pass
" 2>/dev/null)

if [ -n "$briefing" ]; then
  echo "── Cortex Briefing ──"
  echo "$briefing"
  echo "─────────────────────"
fi
