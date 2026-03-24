"""Resend email service for Cortex.

Sends HTML-formatted emails via the Resend API.
Used for daily briefings, alerts, and notifications.

Configuration:
    Set RESEND_API_KEY in environment or ~/.cortex/secrets/resend_api_key
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Cortex <onboarding@resend.dev>"


@dataclass
class EmailResult:
    """Result of an email send attempt."""

    success: bool
    email_id: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class EmailMessage:
    """An email message to send."""

    to: list[str]
    subject: str
    html: str
    text: Optional[str] = None
    from_address: str = DEFAULT_FROM
    reply_to: Optional[str] = None
    tags: list[dict[str, str]] = field(default_factory=list)


def _get_api_key() -> Optional[str]:
    """Resolve Resend API key from environment or secrets file."""
    # 1. Environment variable
    key = os.environ.get("RESEND_API_KEY")
    if key:
        return key

    # 2. Secrets file
    secrets_file = Path.home() / ".cortex" / "secrets" / "resend_api_key"
    if secrets_file.exists():
        try:
            return secrets_file.read_text().strip()
        except OSError:
            pass

    return None


def send_email(message: EmailMessage, api_key: Optional[str] = None) -> EmailResult:
    """Send an email via Resend API.

    Uses urllib to avoid requiring the resend package as a dependency.
    """
    key = api_key or _get_api_key()
    if not key:
        return EmailResult(
            success=False,
            error="No Resend API key found. Set RESEND_API_KEY or create ~/.cortex/secrets/resend_api_key",
        )

    payload = {
        "from": message.from_address,
        "to": message.to,
        "subject": message.subject,
        "html": message.html,
    }
    if message.text:
        payload["text"] = message.text
    if message.reply_to:
        payload["reply_to"] = message.reply_to
    if message.tags:
        payload["tags"] = message.tags

    data = json.dumps(payload).encode("utf-8")

    req = Request(
        RESEND_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return EmailResult(
                success=True,
                email_id=body.get("id"),
                status_code=resp.status,
            )
    except HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        return EmailResult(
            success=False,
            error=f"HTTP {e.code}: {error_body}",
            status_code=e.code,
        )
    except URLError as e:
        return EmailResult(success=False, error=f"Network error: {e.reason}")
    except Exception as e:
        return EmailResult(success=False, error=str(e))


def send_briefing_email(
    to: str,
    subject: str,
    briefing_html: str,
    briefing_text: Optional[str] = None,
    api_key: Optional[str] = None,
) -> EmailResult:
    """Convenience function to send a briefing email."""
    message = EmailMessage(
        to=[to],
        subject=subject,
        html=briefing_html,
        text=briefing_text,
        tags=[{"name": "type", "value": "briefing"}],
    )
    return send_email(message, api_key=api_key)
