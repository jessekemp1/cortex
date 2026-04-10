"""
Optional Telegram notification channel for Cortex alerts.

Requires:
- CORTEX_TELEGRAM_BOT_TOKEN env var
- CORTEX_TELEGRAM_CHAT_ID env var

These can be set in ~/.cortex/.env or cortex/.env
Does NOT add any dependencies — uses urllib (stdlib) to call Telegram API.
"""

import json
import os
import urllib.request
import urllib.error


def _get_config() -> tuple:
    """Get Telegram bot token and chat ID from environment."""
    token = os.environ.get("CORTEX_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("CORTEX_TELEGRAM_CHAT_ID")

    # Try loading from .env files if not in environment
    if not token or not chat_id:
        for env_path in [
            os.path.expanduser("~/.cortex/.env"),
            os.path.join(os.path.dirname(__file__), "..", ".env"),
        ]:
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key == "CORTEX_TELEGRAM_BOT_TOKEN" and not token:
                            token = val
                        elif key == "CORTEX_TELEGRAM_CHAT_ID" and not chat_id:
                            chat_id = val
            except FileNotFoundError:
                continue

    return token, chat_id


def is_configured() -> bool:
    """Check if Telegram notifications are configured."""
    token, chat_id = _get_config()
    return bool(token and chat_id)


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message via Telegram Bot API using stdlib only.

    Returns True if sent successfully, False otherwise.
    """
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def format_alert(severity: str, title: str, message: str, source: str = "") -> str:
    """Format an alert as an HTML Telegram message."""
    emoji = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(severity, "⚪")
    parts = [
        f"{emoji} <b>CORTEX {severity}</b>",
        f"<b>{title}</b>",
        message,
    ]
    if source:
        parts.append(f"<i>Source: {source}</i>")
    return "\n".join(parts)
