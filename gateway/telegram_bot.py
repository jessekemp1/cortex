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


def _portfolio_json() -> dict:
    """Run portfolio_status.py --json for ground-truth project data."""
    try:
        import subprocess

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
    """Assemble morning briefing from real portfolio data."""
    await update.message.reply_text("⏳ Assembling briefing...")

    portfolio = _portfolio_json()
    recs = _bridge_get("/intelligence/recommendations")

    lines = ["╔═══════════════════════════════════╗"]
    lines.append("║     CORTEX MORNING BRIEFING       ║")
    lines.append("╠═══════════════════════════════════╣")

    if "error" not in portfolio:
        for p in portfolio.get("projects", []):
            name = p.get("name", "?")[:14]
            tests = p.get("tests", "—")[:6]
            uncommit = p.get("uncommitted", "?")[:8]
            flag = "⚠" if p.get("has_changes") else " "
            lines.append(f"║ {flag}{name:<13} {tests:>6} {uncommit:>8} ║")

        gate = portfolio.get("gate", {})
        if gate:
            verdict = gate.get("verdict", "?")
            icon = "✅" if verdict == "SHIP" else "❌"
            lines.append(f"║  Gate: {icon} {verdict:<25}║")
    else:
        lines.append(f"║  ⚠ {portfolio['error'][:30]:<30}║")

    lines.append("╠═══════════════════════════════════╣")
    lines.append("║  ACTIONS                          ║")

    if "error" not in recs:
        items = (
            recs if isinstance(recs, list) else recs.get("recommendations", recs.get("items", []))
        )
        if isinstance(items, list):
            for i, r in enumerate(items[:3], 1):
                title = r.get("title", r.get("action", "?"))[:30]
                lines.append(f"║  {i}. {title:<30}║")

    goals = portfolio.get("goals", []) if "error" not in portfolio else []
    if goals:
        lines.append("╠═══════════════════════════════════╣")
        lines.append("║  GOALS                            ║")
        for g in goals[:3]:
            title = g.get("title", "?")[:30]
            lines.append(f"║  • {title:<30}║")

    lines.append("╚═══════════════════════════════════╝")
    await _send(update, "\n".join(lines))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    portfolio = _portfolio_json()
    health = _bridge_get("/service-health")

    lines = ["SERVICE HEALTH", "─" * 38]

    if "error" not in health:
        services = health.get("services", health)
        for key, val in services.items():
            if isinstance(val, dict):
                status = val.get("status", "?")
                port = val.get("port", "")
                p = f":{port}" if port else ""
                lines.append(f"  {key:<18} {status:<10} {p}")

    if "error" not in portfolio:
        lines.append("")
        lines.append("PROJECTS")
        lines.append("─" * 38)
        for p in portfolio.get("projects", []):
            name = p.get("name", "?")[:14]
            tests = p.get("tests", "—")[:6]
            uncommit = p.get("uncommitted", "?")[:8]
            last = p.get("last_commit", "?")[:10]
            lines.append(f"  {name:<14} {tests:>6} {uncommit:>8} {last}")

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
    portfolio = _portfolio_json()
    if "error" in portfolio:
        await _send(update, f"⚠ {portfolio['error']}")
        return

    lines = [
        "PROJECTS",
        "─" * 38,
        f"{'Name':<14} {'Tests':>6} {'Uncommit':>8} {'Last'}",
        "─" * 38,
    ]
    for p in portfolio.get("projects", []):
        name = p.get("name", "?")[:13]
        tests = p.get("tests", "—")[:6]
        uncommit = p.get("uncommitted", "?")[:8]
        last = p.get("last_commit", "?")[:10]
        flag = "⚠" if p.get("has_changes") else " "
        lines.append(f"{flag}{name:<13} {tests:>6} {uncommit:>8} {last}")

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
