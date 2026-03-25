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


def _portfolio_json() -> dict:
    """Run portfolio_status.py --json for ground-truth project data."""
    import subprocess

    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/python3", "scripts/portfolio_status.py", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/Users/jesse.kemp/Dev",
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}
    return {"error": "portfolio_status.py failed"}


def _build_briefing(bridge) -> str:
    portfolio = _portfolio_json()
    health = _api_get("/service-health")
    recs = _api_get("/intelligence/recommendations")

    lines = []
    lines.append("╔═══════════════════════════════════════════════════════╗")
    lines.append("║              CORTEX MORNING BRIEFING                  ║")
    lines.append("╠═══════════════════════════════════════════════════════╣")
    lines.append("║  PROJECT          TESTS    UNCOMMIT    LAST COMMIT   ║")
    lines.append("║  ─────────────────────────────────────────────────── ║")

    if "error" not in portfolio:
        for p in portfolio.get("projects", []):
            name = p.get("name", "?")[:16]
            tests = p.get("tests", "—")[:7]
            uncommit = p.get("uncommitted", "?")[:10]
            last = p.get("last_commit", "?")[:13]
            lines.append(f"║  {name:<16} {tests:>7}  {uncommit:<10}  {last:<13}║")

        gate = portfolio.get("gate", {})
        if gate:
            verdict = gate.get("verdict", "?")
            commit = str(gate.get("commit", "?"))[:8]
            icon = "✅" if verdict == "SHIP" else "❌"
            lines.append("║                                                       ║")
            lines.append(f"║  Release Gate: {icon} {verdict} ({commit})                       ║")
    else:
        lines.append(f"║  ⚠ Portfolio: {portfolio['error'][:38]:<38}║")

    # Services
    lines.append("╠═══════════════════════════════════════════════════════╣")
    if "error" not in health:
        services = health.get("services", health)
        svc_parts = []
        for svc_name, info in services.items():
            if isinstance(info, dict):
                st = info.get("status", "?")
                icon = "✅" if st == "healthy" else "❌" if st == "offline" else "⚠"
                short = svc_name.replace("vortex_", "v-").replace("_", "")[:10]
                svc_parts.append(f"{icon}{short}")
        if svc_parts:
            lines.append(f"║  {' '.join(svc_parts[:6]):<53}║")

    # Recommendations
    lines.append("╠═══════════════════════════════════════════════════════╣")
    lines.append("║  RECOMMENDED ACTIONS                                  ║")
    lines.append("║  ─────────────────────────────────────────────────── ║")
    if "error" not in recs:
        items = (
            recs if isinstance(recs, list) else recs.get("recommendations", recs.get("items", []))
        )
        if isinstance(items, list):
            for i, r in enumerate(items[:5], 1):
                title = r.get("title", r.get("action", "?"))[:48]
                lines.append(f"║  {i}. {title:<50}║")

    # Goals
    goals = portfolio.get("goals", []) if "error" not in portfolio else []
    if goals:
        lines.append("╠═══════════════════════════════════════════════════════╣")
        lines.append("║  ACTIVE GOALS                                        ║")
        for g in goals[:5]:
            title = g.get("title", "?")[:50]
            lines.append(f"║  • {title:<50}║")

    lines.append("╚═══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _build_status(bridge) -> str:
    portfolio = _portfolio_json()
    health = _api_get("/service-health")

    lines = ["SERVICE HEALTH", "─" * 55]

    if "error" not in health:
        services = health.get("services", health)
        for svc_name, info in services.items():
            if isinstance(info, dict):
                status = info.get("status", "?")
                port = info.get("port", "")
                port_str = f":{port}" if port else ""
                lines.append(f"  {svc_name:<20} {status:<12} {port_str}")
            else:
                lines.append(f"  {svc_name:<20} {info}")

    if "error" not in portfolio:
        lines.append("")
        lines.append("PROJECT STATUS")
        lines.append("─" * 55)
        lines.append(f"  {'Name':<16} {'Tests':>7}  {'Uncommit':<10}  {'Last Commit'}")
        lines.append("─" * 55)
        for p in portfolio.get("projects", []):
            name = p.get("name", "?")[:15]
            tests = p.get("tests", "—")[:7]
            uncommit = p.get("uncommitted", "?")[:10]
            last = p.get("last_commit", "?")[:15]
            lines.append(f"  {name:<16} {tests:>7}  {uncommit:<10}  {last}")

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
    portfolio = _portfolio_json()
    if "error" in portfolio:
        return f"⚠ {portfolio['error']}"

    lines = [
        "PROJECTS",
        "─" * 55,
        f"  {'Name':<16} {'Tests':>7}  {'Uncommit':<10}  {'Last Commit'}",
        "─" * 55,
    ]
    for p in portfolio.get("projects", []):
        name = p.get("name", "?")[:15]
        tests = p.get("tests", "—")[:7]
        uncommit = p.get("uncommitted", "?")[:10]
        last = p.get("last_commit", "?")[:15]
        flag = "⚠" if p.get("has_changes") else " "
        lines.append(f"  {flag}{name:<15} {tests:>7}  {uncommit:<10}  {last}")
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


PROJECT_KEYWORDS = {
    "vortex": [
        "vortex",
        "grib",
        "forecast",
        "ensemble",
        "emos",
        "hrrr",
        "gfs",
        "ecmwf",
        "weather",
        "wind",
        "wave",
        "buoy",
        "ndbc",
        "competition",
        "navigator",
        "frontend",
        "backend",
        "nowcast",
        "observation",
        "validation",
    ],
    "alpha_arena": [
        "arena",
        "trading",
        "trade",
        "kelly",
        "strategy",
        "backtest",
        "signal",
        "portfolio",
        "etf",
        "position",
        "ensemble engine",
    ],
    "cortex": [
        "cortex",
        "bridge",
        "cra",
        "orchestrat",
        "learning loop",
        "batch",
        "memory",
        "retriev",
        "mcp",
        "dispatch",
        "intelligence",
    ],
    "pupil": ["pupil", "simulation", "recession", "nowcast", "leading indicator"],
}


def _detect_project(query: str) -> str:
    """Detect which project a query is about from keywords."""
    q = query.lower()
    scores = {}
    for project, keywords in PROJECT_KEYWORDS.items():
        scores[project] = sum(1 for kw in keywords if kw in q)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "cortex"


def _build_intelligence(bridge, query: str) -> str:
    q_lower = query.lower()

    # Only intercept DIRECT data commands — not reasoning questions
    # These are short, imperative, clearly asking for a data lookup
    direct_data_patterns = [
        # "how many tests" / "test count" — but NOT "is testing complete"
        (["how many test", "test count", "number of test"], _answer_project_health),
        # "what services are running" / "is X up"
        (["what service", "which service", "is .* running", "what port"], _answer_service_status),
        # "list goals" / "what goals" — but NOT "is X goal on track"
        (["list goal", "what are my goal", "show goal", "active goal"], _answer_goals),
    ]

    for patterns, handler in direct_data_patterns:
        if any(p in q_lower for p in patterns):
            if handler == _answer_project_health:
                return handler(query, _detect_project(query))
            return handler(query)

    # Everything else → LLM reasoning with gathered context
    return _answer_with_reasoning(query)


def _answer_project_health(query: str, project: str) -> str:
    portfolio = _portfolio_json()
    if "error" in portfolio:
        return f"⚠ Portfolio data unavailable: {portfolio['error']}"

    lines = ["PROJECT HEALTH", "─" * 55]

    # Find matching project(s)
    q_lower = query.lower()
    matched = []
    for p in portfolio.get("projects", []):
        name = p.get("name", "").lower()
        if project.replace("_", "-") in name or project.replace("_", " ") in name:
            matched.append(p)
        elif any(kw in name for kw in q_lower.split() if len(kw) > 3):
            matched.append(p)

    if not matched:
        matched = portfolio.get("projects", [])

    for p in matched:
        name = p.get("name", "?")
        tests = p.get("tests", "—")
        uncommit = p.get("uncommitted", "clean")
        last = p.get("last_commit", "?")
        has_changes = p.get("has_changes", False)

        lines.append(f"  {name}")
        lines.append(f"    Tests:       {tests}")
        lines.append(f"    Uncommitted: {'⚠ ' + uncommit if has_changes else '✅ clean'}")
        lines.append(f"    Last commit: {last}")
        lines.append("")

    gate = portfolio.get("gate", {})
    if gate:
        verdict = gate.get("verdict", "?")
        icon = "✅" if verdict == "SHIP" else "❌"
        lines.append(f"  Release Gate: {icon} {verdict}")

    return "\n".join(lines)


def _answer_service_status(query: str) -> str:
    health = _api_get("/service-health")
    if "error" in health:
        return f"⚠ {health['error']}"

    lines = ["SERVICES", "─" * 55]
    services = health.get("services", health)
    for name, info in services.items():
        if isinstance(info, dict):
            status = info.get("status", "?")
            port = info.get("port", "")
            icon = "✅" if status == "healthy" else "❌" if status == "offline" else "⚠"
            p = f":{port}" if port else ""
            lines.append(f"  {icon} {name:<20} {status:<12} {p}")
    return "\n".join(lines)


def _answer_goals(query: str) -> str:
    portfolio = _portfolio_json()
    if "error" in portfolio:
        return f"⚠ {portfolio['error']}"

    goals = portfolio.get("goals", [])
    if not goals:
        return "No active goals found"

    lines = ["ACTIVE GOALS", "─" * 55]
    for g in goals:
        title = g.get("title", "?")
        status = g.get("status", "?")
        icon = "✅" if status == "COMPLETE" else "🔄" if status == "ACTIVE" else "⏸"
        lines.append(f"  {icon} {title}")
        if g.get("priority"):
            lines.append(f"     Priority: {g['priority']}")
    return "\n".join(lines)


def _answer_with_reasoning(query: str) -> str:
    """Send question to /intelligence/reason endpoint (LLM-powered)."""
    import urllib.request as _req

    try:
        data = json.dumps({"question": query}).encode()
        req = _req.Request(
            "http://127.0.0.1:8765/intelligence/reason",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with _req.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        answer = result.get("answer", "No answer generated.")
        project = result.get("project", "?")
        sources = result.get("sources_used", 0)
        model = result.get("model", "?")
        tokens = result.get("tokens", 0)

        lines = [
            f"CORTEX ({project})",
            "─" * 55,
            answer,
            "",
            f"[{model} | {sources} sources | {tokens} tokens]",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Reasoning error: {e}"


def _answer_intelligence(bridge, query: str, project: str) -> str:
    """Fall back to Cortex pattern retrieval."""
    try:
        result = bridge.query_intelligence(
            request=query,
            project=project,
            query_type="spec",
        )

        lines = [f"CORTEX INTELLIGENCE (project: {project})", "─" * 55]

        reasoning = result.get("reasoning", result.get("response", result.get("result", "")))
        if isinstance(reasoning, str) and reasoning:
            # Filter out the generic "no results" boilerplate
            useful_lines = [
                line
                for line in reasoning.split("\n")
                if not any(
                    skip in line.lower()
                    for skip in [
                        "no similar work found",
                        "no applicable patterns",
                        "no specific recommendations",
                        "consider refining",
                        "pattern library needs",
                        "query may be too broad",
                    ]
                )
            ]
            if useful_lines:
                lines.extend(useful_lines[:30])

        # Context predictions are often the most useful part
        predictions = result.get("context_predictions", [])
        if isinstance(predictions, list) and predictions:
            lines.append("")
            lines.append("RELEVANT CONTEXT")
            lines.append("─" * 55)
            for pred in predictions[:5]:
                if isinstance(pred, dict):
                    source = pred.get("source", "?")
                    rel = pred.get("relevance", "?")
                    content = pred.get("content", pred.get("description", ""))
                    lines.append(f"  [{rel}%] {source}")
                    if content:
                        # Show first 200 chars of content
                        snippet = str(content)[:200].replace("\n", " ")
                        lines.append(f"    {snippet}")
                    lines.append("")

        patterns = result.get("related_patterns", result.get("patterns", []))
        if patterns and isinstance(patterns, list):
            lines.append("RELATED PATTERNS")
            lines.append("─" * 55)
            for p in patterns[:5]:
                if isinstance(p, dict):
                    lines.append(f"  • {p.get('title', p.get('description', '?'))[:70]}")

        confidence = result.get("confidence")
        if confidence:
            lines.append(f"\n[Confidence: {confidence}]")

        # If we got almost nothing useful, say so honestly
        if len(lines) <= 3:
            lines.append("No relevant data found in Cortex knowledge base.")
            lines.append("Try: /status, /projects, /briefing for direct data.")

        return "\n".join(lines)
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
