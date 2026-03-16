"""
Cortex Web Chat — self-hosted chat UI served from the Bridge API at :8765/chat.

Features:
  - JetBrains Mono for perfect ASCII box-drawing
  - Dark terminal theme
  - WebSocket for real-time communication
  - PWA-installable on mobile
  - No external dependencies (all inline)

Mount on the Bridge API:
  from cortex.gateway.web_chat import router as chat_router
  app.include_router(chat_router)
"""

import asyncio
import json
import logging
import traceback

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

log = logging.getLogger("cortex.gateway.web_chat")

router = APIRouter(tags=["chat"])

# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with Cortex intelligence."""
    await websocket.accept()
    log.info("Web chat client connected")

    # Lazy import to avoid circular deps
    try:
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
    except Exception as e:
        await websocket.send_json({"type": "error", "content": f"Bridge init failed: {e}"})
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "query")
            query = data.get("content", "").strip()

            if not query:
                await websocket.send_json({"type": "error", "content": "Empty query"})
                continue

            # Route to appropriate bridge method
            # All bridge calls run in a thread to avoid blocking the event loop
            try:
                if msg_type == "briefing" or query.startswith("/briefing"):
                    result = await asyncio.to_thread(_build_briefing, bridge)
                    await websocket.send_json({"type": "briefing", "content": result})

                elif msg_type == "status" or query.startswith("/status"):
                    result = await asyncio.to_thread(_build_status, bridge)
                    await websocket.send_json({"type": "status", "content": result})

                elif msg_type == "next" or query.startswith("/next"):
                    result = await asyncio.to_thread(_build_next, bridge)
                    await websocket.send_json({"type": "next", "content": result})

                elif msg_type == "projects" or query.startswith("/projects"):
                    result = await asyncio.to_thread(_build_projects, bridge)
                    await websocket.send_json({"type": "projects", "content": result})

                elif msg_type == "anomalies" or query.startswith("/anomalies"):
                    result = await asyncio.to_thread(_build_anomalies, bridge)
                    await websocket.send_json({"type": "anomalies", "content": result})

                else:
                    # Default: intelligence query
                    clean_query = (
                        query.removeprefix("/ask").strip() if query.startswith("/ask") else query
                    )
                    await websocket.send_json({"type": "thinking", "content": "Querying Cortex..."})
                    result = await asyncio.to_thread(_build_intelligence, bridge, clean_query)
                    await websocket.send_json({"type": "intelligence", "content": result})

            except Exception as e:
                log.error("Query error: %s", traceback.format_exc())
                await websocket.send_json({"type": "error", "content": f"Error: {e}"})

    except WebSocketDisconnect:
        log.info("Web chat client disconnected")


# ---------------------------------------------------------------------------
# Bridge query builders (return formatted strings for monospace display)
# ---------------------------------------------------------------------------


def _api_get(path: str) -> dict:
    """GET the Bridge REST API (same-process, via HTTP to avoid method mismatches)."""
    import urllib.request as _req

    try:
        url = f"http://127.0.0.1:8765{path}"
        with _req.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def _build_briefing(bridge) -> str:
    lines = []
    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║              CORTEX MORNING BRIEFING                  ║")
    lines.append("╠═══════════════════════════════════════════════════════╣")

    health = _api_get("/service-health")
    if "error" not in health:
        for key, val in health.items():
            if isinstance(val, dict):
                status = val.get("status", "?")
                lines.append(f"║  {str(key):<16} {str(status):<36}║")
    else:
        lines.append(f"║  ⚠ {str(health.get('error', '?'))[:50]:<50} ║")

    lines.append("╠═══════════════════════════════════════════════════════╣")

    projects = _api_get("/projects")
    if "error" not in projects:
        proj_list = projects if isinstance(projects, list) else projects.get("projects", [])
        for p in proj_list[:6]:
            if isinstance(p, dict):
                name = str(p.get("name", "?"))[:14]
                tests = str(p.get("test_count", "?"))
                health_v = str(p.get("health", "?"))[:6]
                lines.append(f"║  {name:<14} {tests:>6} tests  {health_v:>6}      ║")

    lines.append("╠═══════════════════════════════════════════════════════╣")
    lines.append("║  RECOMMENDED ACTIONS                                  ║")
    lines.append("║  ─────────────────────────────────────────────────── ║")

    recs = _api_get("/intelligence/recommendations")
    if "error" not in recs:
        items = (
            recs if isinstance(recs, list) else recs.get("recommendations", recs.get("items", []))
        )
        if isinstance(items, list):
            for i, r in enumerate(items[:5], 1):
                title = r.get("title", r.get("action", "?"))[:48]
                lines.append(f"║  {i}. {title:<50}║")
        if isinstance(recs, dict):
            next_act = recs.get("next_action")
            if isinstance(next_act, dict):
                lines.append(f"║  → {next_act.get('action', '?')[:50]:<50}║")

    lines.append("╚═══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _build_status(bridge) -> str:
    data = _api_get("/service-health")
    if "error" in data:
        return f"⚠ {data['error']}"

    lines = ["SERVICE HEALTH", "─" * 55]
    for key, val in data.items():
        if isinstance(val, dict):
            status = val.get("status", "unknown")
            lines.append(f"  {str(key):<20} {str(status)}")
        else:
            lines.append(f"  {str(key):<20} {val}")
    return "\n".join(lines)


def _build_next(bridge) -> str:
    recs = _api_get("/intelligence/recommendations")
    if "error" in recs:
        return f"⚠ {recs['error']}"

    if isinstance(recs, dict):
        action = recs.get("next_action", {})
        if isinstance(action, dict) and action:
            title = action.get("title", action.get("action", "No action"))
            reason = action.get("rationale", action.get("reason", ""))
            priority = action.get("priority", "?")
            project = action.get("project", "?")
            lines = [
                "NEXT ACTION",
                "─" * 55,
                f"  [{priority}] {title}",
                f"  Project: {project}",
            ]
            if reason:
                lines.append(f"  Why: {reason[:80]}")
            return "\n".join(lines)
        items = recs.get("recommendations", [])
        if items and isinstance(items, list):
            r = items[0]
            return f"NEXT: [{r.get('priority', '?')}] {r.get('title', r.get('action', '?'))}"
    return "No recommendations available"


def _build_projects(bridge) -> str:
    data = _api_get("/projects")
    if "error" in data:
        return f"⚠ {data['error']}"

    proj_list = data if isinstance(data, list) else data.get("projects", [])
    lines = [
        "PROJECTS",
        "─" * 55,
        f"  {'Name':<18} {'Tests':>7}  {'Health':>8}  {'Commits':>8}",
        "─" * 55,
    ]
    for p in proj_list:
        if isinstance(p, dict):
            name = str(p.get("name", "?"))[:17]
            tests = str(p.get("test_count", "?"))
            health = str(p.get("health", "?"))[:8]
            commits = str(p.get("commit_count", p.get("commits", "?")))
            lines.append(f"  {name:<18} {tests:>7}  {health:>8}  {commits:>8}")
    return "\n".join(lines)


def _build_anomalies(bridge) -> str:
    try:
        # Use bridge's HTTP endpoint via urllib to stay decoupled
        import urllib.request as _req

        url = "http://127.0.0.1:8765/anomalies"
        with _req.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        anomalies = data if isinstance(data, list) else data.get("anomalies", [])
        if not anomalies:
            return "✅ No active anomalies"

        lines = [f"⚠ {len(anomalies)} ANOMALIES", "─" * 55]
        for a in anomalies[:10]:
            severity = a.get("severity", "?")
            desc = a.get("description", a.get("message", "?"))[:50]
            lines.append(f"  [{severity}] {desc}")
            rec = a.get("recommendation", "")
            if rec:
                lines.append(f"    → {rec[:50]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Anomaly detection error: {e}"


def _build_intelligence(bridge, query: str) -> str:
    try:
        result = bridge.query_intelligence(
            request=query,
            project="cortex",
            query_type="spec",
        )

        lines = []
        reasoning = result.get("reasoning", result.get("response", result.get("result", "")))
        if reasoning:
            lines.append("CORTEX INTELLIGENCE")
            lines.append("─" * 55)
            if isinstance(reasoning, str):
                lines.append(reasoning[:4000])
            elif isinstance(reasoning, list):
                for item in reasoning[:8]:
                    if isinstance(item, dict):
                        lines.append(f"• {item.get('title', item.get('content', str(item)))[:80]}")
                    else:
                        lines.append(f"• {str(item)[:80]}")

        patterns = result.get("related_patterns", result.get("patterns", []))
        if patterns and isinstance(patterns, list):
            lines.append("")
            lines.append("RELATED PATTERNS")
            lines.append("─" * 55)
            for p in patterns[:5]:
                if isinstance(p, dict):
                    lines.append(f"  • {p.get('title', p.get('description', '?'))[:70]}")
                else:
                    lines.append(f"  • {str(p)[:70]}")

        confidence = result.get("confidence")
        if confidence:
            lines.append(f"\n[Confidence: {confidence}]")

        return "\n".join(lines) if lines else json.dumps(result, indent=2, default=str)[:4000]
    except Exception as e:
        return f"Intelligence query error: {e}"


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------


CHAT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0a0e14">
<title>Cortex Intelligence</title>
<link rel="manifest" href="/chat/manifest.json">
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg:        #0a0e14;
    --bg-msg:    #111820;
    --bg-user:   #1a2332;
    --bg-input:  #0d1117;
    --border:    #1e2a3a;
    --text:      #c5cdd8;
    --text-dim:  #5c6a7a;
    --accent:    #3b82f6;
    --accent-dim:#1d4ed8;
    --green:     #22c55e;
    --amber:     #f59e0b;
    --red:       #ef4444;
    --mono:      'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', monospace;
  }

  html, body {
    height: 100%; width: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
  }

  #app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 900px;
    margin: 0 auto;
  }

  /* ── Header ── */
  #header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  #header h1 {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--text);
  }
  #status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-dim);
  }
  #status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--red);
    transition: background 0.3s;
  }
  #status-dot.connected { background: var(--green); }
  #status-dot.connecting { background: var(--amber); animation: pulse 1s infinite; }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── Messages ── */
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    scroll-behavior: smooth;
  }

  .msg {
    max-width: 95%;
    padding: 10px 14px;
    border-radius: 8px;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.5;
  }
  .msg.user {
    align-self: flex-end;
    background: var(--bg-user);
    border: 1px solid var(--border);
    color: var(--accent);
  }
  .msg.cortex {
    align-self: flex-start;
    background: var(--bg-msg);
    border: 1px solid var(--border);
    color: var(--text);
  }
  .msg.system {
    align-self: center;
    color: var(--text-dim);
    font-size: 11px;
    padding: 4px 8px;
  }
  .msg.error {
    align-self: flex-start;
    background: #1a0a0a;
    border: 1px solid var(--red);
    color: var(--red);
  }

  .msg-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    margin-bottom: 4px;
    color: var(--text-dim);
  }
  .msg.user .msg-label { color: var(--accent-dim); }
  .msg.cortex .msg-label { color: var(--green); }

  /* ── Quick commands ── */
  #quick-cmds {
    display: flex;
    gap: 6px;
    padding: 8px 16px;
    border-top: 1px solid var(--border);
    overflow-x: auto;
    flex-shrink: 0;
  }
  .qcmd {
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-msg);
    color: var(--text-dim);
    font-family: var(--mono);
    font-size: 11px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s;
  }
  .qcmd:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--bg-user);
  }

  /* ── Input ── */
  #input-area {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  #input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-input);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s;
  }
  #input:focus { border-color: var(--accent); }
  #input::placeholder { color: var(--text-dim); }

  #send-btn {
    padding: 10px 20px;
    border: 1px solid var(--accent);
    border-radius: 6px;
    background: var(--accent-dim);
    color: white;
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  #send-btn:hover { background: var(--accent); }
  #send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

  /* ── Mobile ── */
  @media (max-width: 600px) {
    .msg { max-width: 100%; font-size: 12px; }
    #header h1 { font-size: 12px; }
    #input { font-size: 14px; } /* prevent iOS zoom */
  }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <h1>CORTEX INTELLIGENCE</h1>
    <div id="status">
      <div id="status-dot" class="connecting"></div>
      <span id="status-text">connecting...</span>
    </div>
  </div>

  <div id="messages">
    <div class="msg system">Connected to Cortex Bridge API</div>
  </div>

  <div id="quick-cmds">
    <button class="qcmd" data-cmd="/briefing">/briefing</button>
    <button class="qcmd" data-cmd="/status">/status</button>
    <button class="qcmd" data-cmd="/next">/next</button>
    <button class="qcmd" data-cmd="/projects">/projects</button>
    <button class="qcmd" data-cmd="/anomalies">/anomalies</button>
  </div>

  <div id="input-area">
    <input type="text" id="input" placeholder="Ask Cortex anything..." autocomplete="off" autofocus>
    <button id="send-btn">SEND</button>
  </div>
</div>

<script>
(function() {
  const msgBox  = document.getElementById('messages');
  const input   = document.getElementById('input');
  const sendBtn = document.getElementById('send-btn');
  const dot     = document.getElementById('status-dot');
  const stxt    = document.getElementById('status-text');

  let ws = null;
  let reconnectTimer = null;

  function setStatus(state) {
    dot.className = 'status-dot ' + state;
    stxt.textContent = state === 'connected' ? 'connected · :8765'
                     : state === 'connecting' ? 'connecting...'
                     : 'disconnected';
    sendBtn.disabled = state !== 'connected';
  }

  function addMsg(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;

    if (role !== 'system') {
      const label = document.createElement('div');
      label.className = 'msg-label';
      label.textContent = role === 'user' ? 'YOU' : 'CORTEX';
      div.appendChild(label);
    }

    const content = document.createElement('div');
    content.textContent = text;
    div.appendChild(content);

    msgBox.appendChild(div);
    msgBox.scrollTop = msgBox.scrollHeight;
    return div;
  }

  function connect() {
    setStatus('connecting');
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(proto + '//' + location.host + '/ws/chat');

    ws.onopen = () => {
      setStatus('connected');
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'thinking') {
          // Replace or update thinking indicator
          const existing = msgBox.querySelector('.msg.system.thinking');
          if (existing) existing.remove();
          const div = addMsg('system', data.content);
          div.classList.add('thinking');
        } else if (data.type === 'error') {
          addMsg('error', data.content);
        } else {
          // Remove thinking indicator
          const thinking = msgBox.querySelector('.msg.system.thinking');
          if (thinking) thinking.remove();
          addMsg('cortex', data.content);
        }
      } catch(err) {
        addMsg('cortex', e.data);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setStatus('disconnected');
    };
  }

  function send() {
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    addMsg('user', text);
    input.value = '';

    // Determine message type from slash commands
    let type = 'query';
    if (text.startsWith('/briefing')) type = 'briefing';
    else if (text.startsWith('/status')) type = 'status';
    else if (text.startsWith('/next')) type = 'next';
    else if (text.startsWith('/projects')) type = 'projects';
    else if (text.startsWith('/anomalies')) type = 'anomalies';

    ws.send(JSON.stringify({ type: type, content: text }));
  }

  // Event listeners
  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });

  // Quick command buttons
  document.querySelectorAll('.qcmd').forEach(btn => {
    btn.addEventListener('click', () => {
      input.value = btn.dataset.cmd;
      send();
    });
  });

  // Connect
  connect();
})();
</script>
</body>
</html>
"""

# PWA manifest for installability
MANIFEST_JSON = json.dumps(
    {
        "name": "Cortex Intelligence",
        "short_name": "Cortex",
        "start_url": "/chat",
        "display": "standalone",
        "background_color": "#0a0e14",
        "theme_color": "#0a0e14",
        "description": "Cortex Intelligence Gateway",
    },
    indent=2,
)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Serve the web chat UI."""
    return HTMLResponse(content=CHAT_HTML)


@router.get("/chat/manifest.json")
async def chat_manifest():
    """PWA manifest for installability."""
    return HTMLResponse(content=MANIFEST_JSON, media_type="application/json")
