#!/usr/bin/env python3
"""
Cortex Telegram Gateway — lightweight bot that wraps the Bridge API at :8765.

Provides mobile access to Cortex intelligence, briefings, recommendations,
and anomaly alerts via Telegram with full ASCII/monospace rendering.

Setup:
  1. Message @BotFather on Telegram → /newbot → get token
  2. Set CORTEX_TELEGRAM_TOKEN in ~/.cortex/.env or environment
  3. Run: python -m cortex.gateway.telegram_bot

Commands:
  /start      — Welcome + available commands
  /briefing   — Morning briefing (portfolio + recommendations + anomalies)
  /status     — Project health summary
  /next       — Next recommended action
  /projects   — All active projects
  /ask <q>    — Query Cortex intelligence
  /emos       — EMOS calibration status
  /anomalies  — Active anomalies
  (any text)  — Treated as /ask
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from textwrap import dedent

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("cortex.gateway.telegram")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BRIDGE_URL = os.getenv("CORTEX_BRIDGE_URL", "http://127.0.0.1:8765")
MAX_MSG_LEN = 4096  # Telegram limit


def _get_token() -> str:
    """Load bot token from env or ~/.cortex/.env file."""
    token = os.getenv("CORTEX_TELEGRAM_TOKEN")
    if token:
        return token

    env_file = Path.home() / ".cortex" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("CORTEX_TELEGRAM_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")

    print("ERROR: Set CORTEX_TELEGRAM_TOKEN in environment or ~/.cortex/.env")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Bridge API client (no dependencies beyond stdlib)
# ---------------------------------------------------------------------------


def _bridge_get(path: str) -> dict:
    """GET request to Bridge API."""
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}{path}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"Bridge unavailable: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _bridge_post(path: str, body: dict) -> dict:
    """POST request to Bridge API."""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{BRIDGE_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"Bridge unavailable: {e}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _mono(text: str) -> str:
    """Wrap text in <pre> for Telegram monospace rendering."""
    # Escape HTML entities inside pre blocks
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<pre>{text}</pre>"


def _split_message(text: str) -> list[str]:
    """Split long messages at pre-block boundaries to stay under 4096 chars."""
    if len(text) <= MAX_MSG_LEN:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_MSG_LEN - 50:  # buffer for tags
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


async def _send(update: Update, text: str, mono: bool = True) -> None:
    """Send a message, splitting if needed. Monospace by default."""
    if mono:
        text = _mono(text)
    for chunk in _split_message(text):
        await update.message.reply_text(
            chunk,
            parse_mode=ParseMode.HTML,
        )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    welcome = dedent("""\
        ╔═══════════════════════════════════╗
        ║   CORTEX INTELLIGENCE GATEWAY     ║
        ╠═══════════════════════════════════╣
        ║                                   ║
        ║  /briefing  Morning briefing      ║
        ║  /status    Project health        ║
        ║  /next      Next action           ║
        ║  /projects  All projects          ║
        ║  /ask <q>   Query intelligence    ║
        ║  /emos      EMOS calibration      ║
        ║  /anomalies Active anomalies      ║
        ║                                   ║
        ║  Or just type any question.       ║
        ║                                   ║
        ╚═══════════════════════════════════╝""")
    await _send(update, welcome)


async def cmd_briefing(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Assemble morning briefing from multiple Bridge endpoints."""
    await update.message.reply_text("⏳ Assembling briefing...")

    health = _bridge_get("/service-health")
    recs = _bridge_get("/intelligence/recommendations")
    anomalies = _bridge_get("/anomalies")
    projects = _bridge_get("/projects")

    lines = ["╔═══════════════════════════════════╗"]
    lines.append("║       CORTEX MORNING BRIEFING     ║")
    lines.append("╠═══════════════════════════════════╣")

    # Health summary
    if "error" not in health:
        bridge_ok = health.get("bridge", {}).get("status", "unknown")
        lines.append(f"║  Bridge:  {bridge_ok:<24}║")
        vortex = health.get("vortex", {})
        if vortex:
            v_status = vortex.get("status", "unknown")
            lines.append(f"║  Vortex:  {v_status:<24}║")
    else:
        lines.append(f"║  ⚠ Bridge: {health['error'][:22]:<22}║")

    lines.append("╠═══════════════════════════════════╣")

    # Projects
    if "error" not in projects:
        proj_list = projects if isinstance(projects, list) else projects.get("projects", [])
        for p in proj_list[:6]:
            name = p.get("name", "?")[:14]
            tests = p.get("test_count", "?")
            health_str = p.get("health", "?")
            lines.append(f"║  {name:<14} {str(tests):>5} tests  {str(health_str)[:4]:>4} ║")

    lines.append("╠═══════════════════════════════════╣")

    # Recommendations
    lines.append("║  RECOMMENDED ACTIONS              ║")
    lines.append("║  ─────────────────────────────    ║")
    if "error" not in recs:
        rec_items = (
            recs if isinstance(recs, list) else recs.get("recommendations", recs.get("items", []))
        )
        if isinstance(rec_items, list):
            for i, r in enumerate(rec_items[:3], 1):
                title = r.get("title", r.get("action", "?"))[:30]
                lines.append(f"║  {i}. {title:<30}║")
        elif isinstance(recs, dict) and "next_action" in recs:
            action = recs["next_action"]
            if isinstance(action, dict):
                lines.append(f"║  → {action.get('action', '?')[:30]:<30}║")

    lines.append("╠═══════════════════════════════════╣")

    # Anomalies
    if "error" not in anomalies:
        anom_list = anomalies if isinstance(anomalies, list) else anomalies.get("anomalies", [])
        if anom_list:
            lines.append(f"║  ⚠ {len(anom_list)} anomalies detected         ║")
            for a in anom_list[:2]:
                desc = a.get("description", a.get("message", "?"))[:30]
                lines.append(f"║    {desc:<30}║")
        else:
            lines.append("║  ✅ No anomalies                  ║")
    else:
        lines.append("║  ? Anomaly check unavailable     ║")

    lines.append("╚═══════════════════════════════════╝")

    await _send(update, "\n".join(lines))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = _bridge_get("/service-health")
    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    lines = ["SERVICE HEALTH", "─" * 35]
    for key, val in data.items():
        if isinstance(val, dict):
            status = val.get("status", "unknown")
            lines.append(f"  {key:<16} {status}")
        else:
            lines.append(f"  {key:<16} {val}")

    await _send(update, "\n".join(lines))


async def cmd_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = _bridge_get("/intelligence/recommendations")
    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    # Extract next action from various response shapes
    if isinstance(data, dict):
        action = data.get("next_action", data.get("recommendations", [{}]))
        if isinstance(action, list) and action:
            action = action[0]
        if isinstance(action, dict):
            title = action.get("title", action.get("action", "No action"))
            reason = action.get("rationale", action.get("reason", ""))
            priority = action.get("priority", "?")
            project = action.get("project", "?")

            lines = [
                "NEXT ACTION",
                "─" * 35,
                f"  [{priority}] {title}",
                f"  Project: {project}",
            ]
            if reason:
                lines.append(f"  Why: {reason[:60]}")
            await _send(update, "\n".join(lines))
            return

    await _send(update, json.dumps(data, indent=2)[:3000])


async def cmd_projects(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = _bridge_get("/projects")
    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    proj_list = data if isinstance(data, list) else data.get("projects", [])
    lines = [
        "PROJECTS",
        "─" * 40,
        f"{'Name':<16} {'Tests':>6}  {'Health':>6}",
        "─" * 40,
    ]
    for p in proj_list:
        name = p.get("name", "?")[:15]
        tests = str(p.get("test_count", "?"))
        health = str(p.get("health", "?"))[:6]
        lines.append(f"{name:<16} {tests:>6}  {health:>6}")

    await _send(update, "\n".join(lines))


async def cmd_ask(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(ctx.args) if ctx.args else ""
    if not query:
        await _send(update, "Usage: /ask <your question>")
        return
    await _do_ask(update, query)


async def cmd_emos(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = _bridge_get("/service-health")
    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    emos = data.get("emos", {})
    if not emos:
        await _send(update, "EMOS data not available in health response")
        return

    lines = ["EMOS CALIBRATION STATUS", "─" * 35]
    if isinstance(emos, dict):
        for model, info in emos.items():
            if isinstance(info, dict):
                pairs = info.get("pairs", info.get("count", "?"))
                status = info.get("status", "?")
                lines.append(f"  {model:<10} {str(pairs):>8} pairs  {status}")
            else:
                lines.append(f"  {model:<10} {info}")

    await _send(update, "\n".join(lines))


async def cmd_anomalies(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = _bridge_get("/anomalies")
    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    anom_list = data if isinstance(data, list) else data.get("anomalies", [])
    if not anom_list:
        await _send(update, "✅ No active anomalies")
        return

    lines = [f"⚠ {len(anom_list)} ANOMALIES", "─" * 40]
    for a in anom_list:
        severity = a.get("severity", "?")
        desc = a.get("description", a.get("message", "?"))
        lines.append(f"  [{severity}] {desc[:50]}")
        rec = a.get("recommendation", "")
        if rec:
            lines.append(f"    → {rec[:50]}")

    await _send(update, "\n".join(lines))


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Any non-command text is treated as an intelligence query."""
    await _do_ask(update, update.message.text)


async def _do_ask(update: Update, query: str) -> None:
    """Query Cortex intelligence and return formatted result."""
    await update.message.reply_text("🔍 Querying Cortex...")

    data = _bridge_post(
        "/intelligence/query",
        {
            "request": query,
            "project": "cortex",
            "query_type": "spec",
        },
    )

    if "error" in data:
        await _send(update, f"⚠ {data['error']}")
        return

    # Format response — adapt to whatever shape bridge returns
    lines = []

    reasoning = data.get("reasoning", data.get("response", data.get("result", "")))
    if reasoning:
        lines.append("CORTEX INTELLIGENCE")
        lines.append("─" * 40)
        # Truncate long responses for Telegram
        if isinstance(reasoning, str):
            lines.append(reasoning[:3000])
        elif isinstance(reasoning, list):
            for item in reasoning[:5]:
                if isinstance(item, dict):
                    lines.append(f"• {item.get('title', item.get('content', str(item)))[:80]}")
                else:
                    lines.append(f"• {str(item)[:80]}")

    patterns = data.get("related_patterns", data.get("patterns", []))
    if patterns and isinstance(patterns, list):
        lines.append("")
        lines.append("RELATED PATTERNS")
        lines.append("─" * 40)
        for p in patterns[:3]:
            if isinstance(p, dict):
                lines.append(f"  • {p.get('title', p.get('description', '?'))[:60]}")
            else:
                lines.append(f"  • {str(p)[:60]}")

    confidence = data.get("confidence")
    if confidence:
        lines.append(f"\n[Confidence: {confidence}]")

    await _send(update, "\n".join(lines) if lines else json.dumps(data, indent=2)[:3000])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    token = _get_token()

    log.info("Starting Cortex Telegram Gateway...")
    log.info("Bridge API: %s", BRIDGE_URL)

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("emos", cmd_emos))
    app.add_handler(CommandHandler("anomalies", cmd_anomalies))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Bot registered. Polling for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
