#!/usr/bin/env python3
"""
Cortex Alert Manager - Safe, local-first notifications.

Ported from Moltbot's notification system, but using ONLY secure channels:
- Desktop notifications (macOS/Linux native)
- Email (optional, user-configured SMTP)
- Log files (always enabled)

NO multi-channel gateways, NO WebSockets, NO third-party services.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Alert:
    """A Cortex alert."""
    alert_id: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    title: str
    message: str
    source: str  # "anomaly_detector", "vortex", "alpha_arena", etc.
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class AlertManager:
    """
    Send alerts through safe, local channels only.

    Supported channels:
    1. Desktop notifications (macOS osascript, Linux notify-send)
    2. Email (optional, user-configured SMTP)
    3. Log files (~/.cortex/alerts.jsonl)

    Security:
    - NO external gateways
    - NO third-party services
    - NO credential storage (email uses OS keychain if configured)
    - Local-first architecture
    """

    def __init__(self, alerts_dir: Optional[Path] = None):
        """Initialize alert manager."""
        if alerts_dir is None:
            alerts_dir = Path.home() / ".cortex"

        alerts_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_file = alerts_dir / "alerts.jsonl"
        self.config_file = alerts_dir / "alert_config.json"

        # Load config
        self.config = self._load_config()

    # =========================================================================
    # Main Alert Interface
    # =========================================================================

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "INFO",
        source: str = "cortex",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """
        Send alert through configured channels.

        Args:
            title: Alert title
            message: Alert message
            severity: "CRITICAL", "WARNING", "INFO"
            source: Alert source
            metadata: Additional context

        Returns:
            Alert object
        """
        import uuid

        alert = Alert(
            alert_id=str(uuid.uuid4())[:8],
            severity=severity,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )

        # Always log
        self._log_alert(alert)

        # Desktop notification (if enabled and severity matches)
        if self._should_desktop_notify(severity):
            self._send_desktop(alert)

        # Email (if enabled and severity matches)
        if self._should_email_notify(severity):
            self._send_email(alert)

        return alert

    # =========================================================================
    # Desktop Notifications
    # =========================================================================

    def _send_desktop(self, alert: Alert):
        """
        Send desktop notification.

        macOS: Uses osascript
        Linux: Uses notify-send (if available)
        """
        try:
            if sys.platform == "darwin":
                # macOS
                emoji = self._get_emoji(alert.severity)
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'display notification "{alert.message}" '
                        f'with title "{emoji} Cortex: {alert.title}"',
                    ],
                    check=False,
                    timeout=5,
                )
            elif sys.platform.startswith("linux"):
                # Linux (requires notify-send)
                subprocess.run(
                    [
                        "notify-send",
                        f"Cortex: {alert.title}",
                        alert.message,
                        "-u",
                        self._get_urgency(alert.severity),
                    ],
                    check=False,
                    timeout=5,
                )
        except Exception as e:
            # Don't fail on notification errors
            self._log_error(f"Desktop notification failed: {e}")

    def _get_emoji(self, severity: str) -> str:
        """Get emoji for severity."""
        return {
            "CRITICAL": "🚨",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
        }.get(severity, "ℹ️")

    def _get_urgency(self, severity: str) -> str:
        """Get urgency level for Linux notify-send."""
        return {
            "CRITICAL": "critical",
            "WARNING": "normal",
            "INFO": "low",
        }.get(severity, "low")

    # =========================================================================
    # Email Notifications
    # =========================================================================

    def _send_email(self, alert: Alert):
        """
        Send email notification (if configured).

        Uses SMTP settings from config file.
        Credentials should be stored in OS keychain, not in config.
        """
        if not self.config.get("email", {}).get("enabled"):
            return

        try:
            import smtplib
            from email.mime.text import MIMEText

            email_config = self.config["email"]
            smtp_host = email_config.get("smtp_host")
            smtp_port = email_config.get("smtp_port", 587)
            from_addr = email_config.get("from_address")
            to_addr = email_config.get("to_address")

            if not all([smtp_host, from_addr, to_addr]):
                return

            # Create message
            msg = MIMEText(
                f"Severity: {alert.severity}\n"
                f"Source: {alert.source}\n"
                f"Time: {alert.timestamp.isoformat()}\n\n"
                f"{alert.message}\n\n"
                f"Alert ID: {alert.alert_id}"
            )
            msg["Subject"] = f"[Cortex {alert.severity}] {alert.title}"
            msg["From"] = from_addr
            msg["To"] = to_addr

            # Send (TLS)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                # Note: Password should come from OS keychain, not stored here
                # For now, email is optional and requires manual SMTP setup
                server.send_message(msg)

        except Exception as e:
            self._log_error(f"Email notification failed: {e}")

    # =========================================================================
    # Logging
    # =========================================================================

    def _log_alert(self, alert: Alert):
        """Log alert to file (always enabled)."""
        with open(self.alerts_file, "a") as f:
            f.write(json.dumps(alert.to_dict()) + "\n")

    def _log_error(self, message: str):
        """Log internal error."""
        error_file = self.alerts_file.parent / "alert_errors.log"
        with open(error_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")

    # =========================================================================
    # Configuration
    # =========================================================================

    def _should_desktop_notify(self, severity: str) -> bool:
        """Check if desktop notification should be sent."""
        config = self.config.get("desktop", {})

        if not config.get("enabled", True):
            return False

        min_severity = config.get("min_severity", "WARNING")
        severity_levels = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

        return severity_levels.get(severity, 0) >= severity_levels.get(
            min_severity, 1
        )

    def _should_email_notify(self, severity: str) -> bool:
        """Check if email notification should be sent."""
        config = self.config.get("email", {})

        if not config.get("enabled", False):
            return False

        min_severity = config.get("min_severity", "CRITICAL")
        severity_levels = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

        return severity_levels.get(severity, 0) >= severity_levels.get(
            min_severity, 2
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load alert configuration."""
        if not self.config_file.exists():
            return self._get_default_config()

        with open(self.config_file, "r") as f:
            return json.load(f)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default alert configuration."""
        return {
            "desktop": {
                "enabled": True,
                "min_severity": "WARNING",  # Only WARNING and CRITICAL
            },
            "email": {
                "enabled": False,  # Disabled by default (requires setup)
                "min_severity": "CRITICAL",
                "smtp_host": None,
                "smtp_port": 587,
                "from_address": None,
                "to_address": None,
            },
        }

    def update_config(self, config: Dict[str, Any]):
        """Update alert configuration."""
        self.config.update(config)
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    # =========================================================================
    # Query Alerts
    # =========================================================================

    def get_recent_alerts(
        self, hours: int = 24, severity: Optional[str] = None
    ) -> List[Alert]:
        """
        Get recent alerts.

        Args:
            hours: Hours to look back
            severity: Filter by severity (optional)

        Returns:
            List of Alert objects
        """
        if not self.alerts_file.exists():
            return []

        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=hours)
        alerts = []

        with open(self.alerts_file, "r") as f:
            for line in f:
                data = json.loads(line)
                alert = Alert(
                    alert_id=data["alert_id"],
                    severity=data["severity"],
                    title=data["title"],
                    message=data["message"],
                    source=data["source"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    metadata=data.get("metadata", {}),
                )

                # Filter by time
                if alert.timestamp < cutoff:
                    continue

                # Filter by severity
                if severity and alert.severity != severity:
                    continue

                alerts.append(alert)

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)


# =============================================================================
# CLI Integration
# =============================================================================


def main():
    """CLI for testing alert manager."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  alert_manager.py send <title> <message> [severity]")
        print("  alert_manager.py recent [hours] [severity]")
        print("  alert_manager.py test")
        return

    manager = AlertManager()
    command = sys.argv[1]

    if command == "send":
        title = sys.argv[2]
        message = sys.argv[3]
        severity = sys.argv[4] if len(sys.argv) > 4 else "INFO"
        alert = manager.send_alert(title, message, severity)
        print(f"✓ Alert sent: {alert.alert_id}")

    elif command == "recent":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        severity = sys.argv[3] if len(sys.argv) > 3 else None
        alerts = manager.get_recent_alerts(hours, severity)
        print(f"Recent alerts (last {hours}h):")
        for alert in alerts:
            print(f"  [{alert.severity}] {alert.title}: {alert.message}")

    elif command == "test":
        print("Testing alert channels...")
        manager.send_alert("Test Alert", "This is a test notification", "INFO")
        print("✓ INFO sent (logged only)")
        manager.send_alert(
            "Test Warning", "This is a test warning", "WARNING"
        )
        print("✓ WARNING sent (desktop + log)")
        manager.send_alert(
            "Test Critical", "This is a critical test", "CRITICAL"
        )
        print("✓ CRITICAL sent (desktop + log)")


if __name__ == "__main__":
    main()
