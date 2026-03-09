#!/usr/bin/env python3
"""
Cortex Heartbeat — Proactive check-in daemon (OpenClaw-inspired).

Runs every 30 minutes via launchd. Aggregates system state and sends a
Slack message ONLY when action is needed. Silent otherwise (like
OpenClaw's HEARTBEAT_OK pattern).

State sources:
  1. Service health (from alert_monitor's alerts.jsonl)
  2. GOALS.md pending items
  3. Batch job status (~/.cortex/batch/)
  4. Supervisor last tick result
  5. Test regression alerts

Usage:
  python3 cortex/heartbeat.py              # Run once
  python3 cortex/heartbeat.py --force      # Force send even if no action needed
  python3 cortex/heartbeat.py --dry-run    # Print message without sending

Slack channel configured via CORTEX_HEARTBEAT_CHANNEL env var or
~/.cortex/heartbeat_config.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CORTEX_DIR = Path.home() / ".cortex"
ALERTS_LOG = CORTEX_DIR / "alerts.jsonl"
BATCH_DIR = CORTEX_DIR / "batch"
HEARTBEAT_STATE = CORTEX_DIR / "heartbeat_state.json"
HEARTBEAT_CONFIG = CORTEX_DIR / "heartbeat_config.json"
GOALS_PATH = Path(__file__).resolve().parent.parent / "GOALS.md"
SUPERVISOR_LOG = CORTEX_DIR / "orchestration" / "runs"

# Minimum interval between heartbeat messages (avoid spam)
MIN_INTERVAL_MINUTES = 25


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_config() -> dict:
    """Load heartbeat config (Slack channel, etc.)."""
    defaults = {
        "slack_channel": os.environ.get("CORTEX_HEARTBEAT_CHANNEL", ""),
        "slack_token": os.environ.get("SLACK_BOT_TOKEN", ""),
        "min_severity": "MEDIUM",
        "silent_ok": True,
    }
    try:
        if HEARTBEAT_CONFIG.exists():
            cfg = json.loads(HEARTBEAT_CONFIG.read_text())
            defaults.update(cfg)
    except Exception:
        pass
    return defaults


def _should_run() -> bool:
    """Rate limit: don't send more often than MIN_INTERVAL_MINUTES."""
    try:
        if HEARTBEAT_STATE.exists():
            state = json.loads(HEARTBEAT_STATE.read_text())
            last_run = datetime.fromisoformat(state.get("last_run", "2000-01-01T00:00:00+00:00"))
            if _now() - last_run < timedelta(minutes=MIN_INTERVAL_MINUTES):
                return False
    except Exception:
        pass
    return True


def _save_state(sent: bool, summary: str):
    """Record heartbeat execution state."""
    try:
        HEARTBEAT_STATE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_STATE.write_text(
            json.dumps(
                {
                    "last_run": _now().isoformat(),
                    "sent": sent,
                    "summary": summary[:200],
                }
            )
        )
    except Exception:
        pass


# ── State Collectors ─────────────────────────────────────────────────


def _check_alerts() -> list[dict]:
    """Check for recent HIGH/CRITICAL alerts (last 30 min)."""
    alerts = []
    cutoff = _now() - timedelta(minutes=30)
    try:
        if not ALERTS_LOG.exists():
            return []
        for line in ALERTS_LOG.read_text().strip().splitlines()[-50:]:
            entry = json.loads(line)
            ts = datetime.fromisoformat(entry.get("ts", "2000-01-01"))
            if ts > cutoff and entry.get("severity") in ("HIGH", "CRITICAL"):
                alerts.append(entry)
    except Exception:
        pass
    return alerts


def _check_goals() -> dict:
    """Count unchecked items in GOALS.md."""
    result = {"total": 0, "high_priority": 0, "immediate": []}
    try:
        if not GOALS_PATH.exists():
            return result
        text = GOALS_PATH.read_text()
        in_high = False
        in_immediate = False
        for line in text.splitlines():
            lower = line.lower().strip()
            if "high priority" in lower or "immediate" in lower:
                in_high = True
                in_immediate = "immediate" in lower
            elif lower.startswith("##"):
                in_high = False
                in_immediate = False
            if line.strip().startswith("- [ ]"):
                result["total"] += 1
                if in_high:
                    result["high_priority"] += 1
                if in_immediate:
                    result["immediate"].append(line.strip()[6:].strip()[:80])
    except Exception:
        pass
    return result


def _check_batches() -> dict:
    """Check for completed/failed batch jobs."""
    result = {"pending": 0, "completed": 0, "failed": 0}
    try:
        if not BATCH_DIR.exists():
            return result
        for f in BATCH_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                status = data.get("status", "unknown")
                if status == "completed":
                    result["completed"] += 1
                elif status == "failed":
                    result["failed"] += 1
                elif status in ("pending", "queued", "running"):
                    result["pending"] += 1
            except Exception:
                continue
    except Exception:
        pass
    return result


def _check_services() -> list[str]:
    """Quick service health check (subset of alert_monitor)."""
    down = []
    services = [
        ("vortex-backend", "http://127.0.0.1:8000/api/v2/health"),
        ("cortex-bridge", "http://127.0.0.1:8765/health"),
    ]
    for name, url in services:
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            down.append(name)
    return down


def _check_supervisor() -> dict | None:
    """Read last supervisor run summary."""
    try:
        if not SUPERVISOR_LOG.exists():
            return None
        runs = sorted(SUPERVISOR_LOG.glob("*.json"))
        if not runs:
            return None
        return json.loads(runs[-1].read_text())
    except Exception:
        return None


# ── Message Formatting ───────────────────────────────────────────────


def _build_message(
    alerts: list[dict],
    goals: dict,
    batches: dict,
    services_down: list[str],
    supervisor: dict | None,
) -> str | None:
    """Build Slack message. Returns None if no action needed."""
    sections = []
    needs_action = False

    # Service health
    if services_down:
        needs_action = True
        sections.append(f":red_circle: *Services Down*: {', '.join(services_down)}")

    # Recent alerts
    if alerts:
        needs_action = True
        alert_lines = [
            f"  • [{a['severity']}] {a.get('service', '?')}: {a.get('message', '')[:60]}"
            for a in alerts[:3]
        ]
        sections.append(":warning: *Recent Alerts*\n" + "\n".join(alert_lines))

    # Batch status
    if batches["failed"] > 0:
        needs_action = True
        sections.append(
            f":x: *Batch Jobs*: {batches['failed']} failed, {batches['completed']} completed, {batches['pending']} pending"
        )
    elif batches["completed"] > 0:
        sections.append(
            f":white_check_mark: *Batch Jobs*: {batches['completed']} completed, {batches['pending']} pending"
        )

    # Goals
    if goals["immediate"]:
        needs_action = True
        items = "\n".join(f"  • {i}" for i in goals["immediate"][:3])
        sections.append(f":dart: *Immediate Actions* ({goals['total']} total)\n{items}")

    # Supervisor
    if supervisor:
        errors = supervisor.get("errors", [])
        if errors:
            needs_action = True
            sections.append(f":gear: *Supervisor*: {len(errors)} errors in last run")

    if not sections:
        return None

    header = ":brain: *Cortex Heartbeat*" + (
        " — :rotating_light: Action Needed" if needs_action else ""
    )
    ts = _now().strftime("%H:%M UTC")
    footer = f"_Checked at {ts}_"

    return header + "\n\n" + "\n\n".join(sections) + "\n\n" + footer


def _send_slack(message: str, config: dict) -> bool:
    """Send message via Slack API."""
    token = config.get("slack_token", "")
    channel = config.get("slack_channel", "")

    if not token or not channel:
        # Fall back to desktop notification
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message[:200]}" with title "Cortex Heartbeat"',
                ],
                timeout=5,
                capture_output=True,
            )
        except Exception:
            pass
        return False

    try:
        payload = json.dumps(
            {
                "channel": channel,
                "text": message,
                "mrkdwn": True,
            }
        ).encode()

        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception:
        return False


# ── Main ─────────────────────────────────────────────────────────────


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    config = _load_config()

    if not force and not _should_run():
        sys.exit(0)

    # Collect state
    alerts = _check_alerts()
    goals = _check_goals()
    batches = _check_batches()
    services_down = _check_services()
    supervisor = _check_supervisor()

    # Build message
    message = _build_message(alerts, goals, batches, services_down, supervisor)

    if message is None and config.get("silent_ok", True) and not force:
        _save_state(sent=False, summary="HEARTBEAT_OK")
        sys.exit(0)

    if message is None:
        message = ":brain: *Cortex Heartbeat* — All clear :white_check_mark:\n_No action needed._"

    if dry_run:
        print(message)
        _save_state(sent=False, summary="dry-run")
        sys.exit(0)

    sent = _send_slack(message, config)
    _save_state(sent=sent, summary=message[:200])

    if not sent and message:
        # Fallback: print to stdout for launchd log capture
        print(message, file=sys.stderr)


if __name__ == "__main__":
    main()
