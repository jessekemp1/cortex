#!/usr/bin/env python3
"""
Alert Monitor — surfaces critical failures and auto-restarts Tier 1 services.

Checks every invocation (called by LaunchAgent/systemd timer every 5 minutes):
  1. Service health: HTTP GET to all operational endpoints
  2. Auto-restart: Tier 1 services via launchctl (macOS) or systemctl (Linux)
  3. Scheduler failures: errors in ~/.cortex/metrics/scheduler_jobs.jsonl (last 5 min)
  4. Test regression: project test counts vs persisted baseline (>2% drop = alert)

Writes to ~/.cortex/alerts.jsonl (append-only, read by session_start_context.py).
Suppressed for 1h by: touch ~/.cortex/alert_silence_<service>
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The runtime binds CORTEX_RUNTIME_PORT (default 8000; see runtime/config.py
# RuntimeConfig.port) and serves its health check at /api/v1/runtime/health
# (runtime/api.py). Health-checking any other port (e.g. the bridge's 8765)
# would report the wrong process up/down and misdirect auto-restart.
CORTEX_RUNTIME_PORT = os.getenv("CORTEX_RUNTIME_PORT", "8000")

CORTEX_DIR = Path.home() / ".cortex"
ALERTS_LOG = CORTEX_DIR / "alerts.jsonl"
METRICS_DIR = CORTEX_DIR / "metrics"
SILENCE_DIR = CORTEX_DIR  # silence files: alert_silence_<service>
CONSECUTIVE_FILE = CORTEX_DIR / "alert_consecutive.json"
RESTART_LOG = CORTEX_DIR / "restart_history.jsonl"

# === Tier 1: Always-on operational services (99.99% target) ===
# === Tier 2: Supporting services ===
SERVICES = [
    ("cortex-runtime", f"http://127.0.0.1:{CORTEX_RUNTIME_PORT}/api/v1/runtime/health"),
    ("cortex-site", "http://127.0.0.1:3001/"),
    ("alpha-arena", "http://127.0.0.1:8502/_stcore/health"),
]


def _detect_platform() -> str:
    """Return 'macos' or 'linux' based on the current OS."""
    return "macos" if platform.system() == "Darwin" else "linux"


# Platform-specific restart configuration: service -> init-system label.
# Only list services that have a REAL installed unit — a label with no
# matching launchd plist / systemd unit makes _attempt_restart run a doomed
# kickstart that never succeeds, so the failure counter never resets. Restart
# is opt-in per service; unlisted services are monitored and alerted but not
# auto-restarted. (No com.cortex.runtime / com.cortex.site plist ships today,
# so cortex-runtime/cortex-site are intentionally absent — alert only.)
TIER1_RESTART_CONFIG: dict[str, dict[str, str]] = {
    "macos": {
        "alpha-arena": "com.alphaarena.dashboard",
    },
    "linux": {},
}

# Backwards compat: expose macOS labels as the old name for any external consumers
TIER1_LAUNCHD_LABELS = TIER1_RESTART_CONFIG["macos"]

# Consecutive failures before a service is alerted on. A per-service override
# map can be reintroduced here if a service needs a non-default threshold;
# until then check_services uses the constant directly.
CONSECUTIVE_THRESHOLD = 2

# Auto-restart after this many consecutive failures (Tier 1 only)
AUTO_RESTART_THRESHOLD = 3
# Max restarts per hour per service (prevent restart storms)
MAX_RESTARTS_PER_HOUR = 3

# Test regression threshold: alert if any project drops > 2%
TEST_REGRESSION_PCT = 0.02


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_silenced(service: str) -> bool:
    """Return True if a silence file exists and is <1h old."""
    silence_file = SILENCE_DIR / f"alert_silence_{service}"
    if not silence_file.exists():
        return False
    age = _now() - datetime.fromtimestamp(silence_file.stat().st_mtime, tz=timezone.utc)
    return age < timedelta(hours=1)


def _load_consecutive() -> dict:
    try:
        if CONSECUTIVE_FILE.exists():
            return json.loads(CONSECUTIVE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_consecutive(data: dict):
    try:
        tmp = Path(str(CONSECUTIVE_FILE) + ".tmp")
        tmp.write_text(json.dumps(data))
        tmp.rename(CONSECUTIVE_FILE)
    except Exception:
        pass


def _append_alert(alert: dict):
    """Append alert to alerts.jsonl (append-only)."""
    try:
        ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_LOG, "a") as f:
            f.write(json.dumps(alert) + "\n")
    except Exception:
        pass


def _log_restart(service: str, label: str, success: bool):
    """Log restart attempt to restart_history.jsonl."""
    try:
        RESTART_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": _now().isoformat(),
            "service": service,
            "label": label,
            "success": success,
        }
        with open(RESTART_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _recent_restart_count(service: str) -> int:
    """Count restarts for a service in the last hour."""
    if not RESTART_LOG.exists():
        return 0
    cutoff = (_now() - timedelta(hours=1)).isoformat()
    count = 0
    try:
        for line in RESTART_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("service") == service and entry.get("ts", "") >= cutoff:
                    count += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return count


def _attempt_restart(service: str) -> bool:
    """Attempt to restart a Tier 1 service via platform-appropriate init system.

    macOS: launchctl kickstart -k gui/<uid>/<label>
    Linux: systemctl --user restart <unit>
    """
    plat = _detect_platform()
    config = TIER1_RESTART_CONFIG.get(plat, {})
    label = config.get(service)
    if not label:
        return False

    # Rate limit: max N restarts per hour
    if _recent_restart_count(service) >= MAX_RESTARTS_PER_HOUR:
        print(
            f"RESTART SUPPRESSED: {service} hit {MAX_RESTARTS_PER_HOUR} restarts/hour limit",
            file=sys.stderr,
        )
        return False

    try:
        if plat == "macos":
            cmd = ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"]
        else:
            cmd = ["systemctl", "--user", "restart", label]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        success = result.returncode == 0
        _log_restart(service, label, success)
        if success:
            print(f"AUTO-RESTART: {service} ({label}) restarted via {plat}", file=sys.stderr)
        else:
            print(
                f"RESTART FAILED: {service} ({label}): {result.stderr.strip()}",
                file=sys.stderr,
            )
        return success
    except Exception as e:
        _log_restart(service, label, False)
        print(f"RESTART ERROR: {service}: {e}", file=sys.stderr)
        return False


def check_service(name: str, url: str) -> tuple[bool, str]:
    """Return (healthy, status_detail) for a service.

    A 200 alone is not sufficient: a health endpoint can answer 200 with a JSON
    body reporting a degraded/unhealthy subsystem. When the response is JSON
    carrying a ``status`` field, honour it so partial outages aren't masked as
    healthy. Non-JSON 200s (plain pages like /docs) stay healthy.
    """
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status != 200:
                return False, "http_error"
            body = resp.read(4096)
    except Exception:
        return False, "unreachable"

    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return True, "healthy"  # 200 with non-JSON body — treat as up
    if isinstance(payload, dict):
        status = str(payload.get("status", "healthy")).lower()
        if status in ("degraded", "unhealthy", "error", "down"):
            return False, status
    return True, "healthy"


def check_services() -> list[dict]:
    """Check all services, return list of alert dicts for down services."""
    consec = _load_consecutive()
    alerts = []
    now_ts = _now().isoformat()

    # Prune counters for services that are no longer monitored (e.g.
    # decommissioned ones like vortex-backend/navigator) so alert_consecutive
    # .json doesn't accumulate stale keys reported forever by downstream tools.
    monitored = {name for name, _ in SERVICES}
    for stale in [k for k in consec if k not in monitored]:
        del consec[stale]

    for name, url in SERVICES:
        if _is_silenced(name):
            continue
        healthy, detail = check_service(name, url)
        threshold = CONSECUTIVE_THRESHOLD

        if healthy:
            # Reset consecutive failure counter
            consec[name] = 0
        else:
            consec[name] = consec.get(name, 0) + 1

            # Auto-restart Tier 1 services after threshold
            plat_config = TIER1_RESTART_CONFIG.get(_detect_platform(), {})
            if consec[name] >= AUTO_RESTART_THRESHOLD and name in plat_config:
                restarted = _attempt_restart(name)
                if restarted:
                    # Reset counter — give it a chance to come back
                    consec[name] = 0

            if consec[name] >= threshold:
                message = f"{name} DOWN ({consec[name]} consecutive failures)"
                if detail and detail not in ("unreachable", "http_error"):
                    message = f"{name} {detail.upper()} ({consec[name]} consecutive failures)"
                alerts.append(
                    {
                        "ts": now_ts,
                        "type": "service_down",
                        "severity": "HIGH",
                        "service": name,
                        "url": url,
                        "consecutive_failures": consec[name],
                        "detail": detail,
                        "message": message,
                        "silence_cmd": f"touch ~/.cortex/alert_silence_{name}",
                    }
                )

    _save_consecutive(consec)
    return alerts


def check_scheduler_failures() -> list[dict]:
    """Check scheduler_jobs.jsonl for errors in the last 5 minutes."""
    log_file = METRICS_DIR / "scheduler_jobs.jsonl"
    if not log_file.exists():
        return []

    cutoff = _now() - timedelta(minutes=5)
    alerts = []

    try:
        for line in log_file.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Only look at error events
                if entry.get("event") not in ("error", "failure", "failed"):
                    continue
                ts_str = entry.get("ts", entry.get("timestamp", ""))
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue

                job = entry.get("job", entry.get("task", "unknown"))
                error = str(entry.get("error", entry.get("message", "")))[:200]

                if _is_silenced(f"scheduler_{job}"):
                    continue

                alerts.append(
                    {
                        "ts": ts_str,
                        "type": "scheduler_failure",
                        "severity": "MEDIUM",
                        "job": job,
                        "error": error,
                        "message": f"Scheduler job '{job}' failed: {error[:100]}",
                        "silence_cmd": f"touch ~/.cortex/alert_silence_scheduler_{job}",
                    }
                )
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        pass

    return alerts


def _load_test_baseline() -> dict:
    """Load persisted test baseline from ~/.cortex/metrics/test_baseline.json."""
    try:
        baseline_file = METRICS_DIR / "test_baseline.json"
        if baseline_file.exists():
            return json.loads(baseline_file.read_text())
    except Exception:
        pass
    return {}


def _save_test_baseline(data: dict):
    try:
        tests_file = METRICS_DIR / "tests.json"
        if not tests_file.exists():
            return
        current = json.loads(tests_file.read_text())
        # Only update baseline if all projects are passing
        all_passing = all(v.get("failed", 0) == 0 for v in current.values())
        if all_passing:
            baseline = {k: v.get("passed", 0) for k, v in current.items()}
            baseline_file = METRICS_DIR / "test_baseline.json"
            tmp = Path(str(baseline_file) + ".tmp")
            tmp.write_text(json.dumps(baseline))
            tmp.rename(baseline_file)
    except Exception:
        pass


def check_test_regression() -> list[dict]:
    """Check if any project's test count dropped vs baseline."""
    tests_file = METRICS_DIR / "tests.json"
    if not tests_file.exists():
        return []

    alerts = []
    try:
        current = json.loads(tests_file.read_text())
        baseline = _load_test_baseline()

        if not baseline:
            # First run: write baseline, no alerts
            _save_test_baseline(current)
            return []

        now_ts = _now().isoformat()
        for project, data in current.items():
            current_count = data.get("passed", 0)
            baseline_count = baseline.get(project, 0)
            if baseline_count == 0:
                continue

            drop = (baseline_count - current_count) / baseline_count
            if drop > TEST_REGRESSION_PCT and data.get("failed", 0) > 0:
                if _is_silenced(f"tests_{project}"):
                    continue
                alerts.append(
                    {
                        "ts": now_ts,
                        "type": "test_regression",
                        "severity": "MEDIUM",
                        "project": project,
                        "current": current_count,
                        "baseline": baseline_count,
                        "drop_pct": round(drop * 100, 1),
                        "message": f"REGRESSION: {project} tests {baseline_count}→{current_count} (-{drop * 100:.1f}%)",
                        "silence_cmd": f"touch ~/.cortex/alert_silence_tests_{project}",
                    }
                )
    except Exception:
        pass

    return alerts


def prune_old_alerts(days: int = 7):
    """Remove alerts older than N days (keep file bounded)."""
    if not ALERTS_LOG.exists():
        return
    try:
        cutoff = (_now() - timedelta(days=days)).isoformat()
        lines = ALERTS_LOG.read_text().splitlines()
        fresh = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts", "") >= cutoff:
                    fresh.append(line)
            except json.JSONDecodeError:
                continue
        ALERTS_LOG.write_text("\n".join(fresh) + "\n" if fresh else "")
    except Exception:
        pass


def get_recent_alerts(minutes: int = 60) -> list[dict]:
    """Read alerts from the last N minutes (for session_start_context.py)."""
    if not ALERTS_LOG.exists():
        return []
    cutoff = (_now() - timedelta(minutes=minutes)).isoformat()
    alerts = []
    try:
        for line in ALERTS_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts", "") >= cutoff:
                    alerts.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return alerts


def _run_threshold_checks() -> list[dict]:
    """Run threshold detector checks and convert events to alert dicts."""
    alerts = []
    try:
        from notifications.threshold_detector import run_all_checks

        events = run_all_checks()
        for event in events:
            alerts.append(
                {
                    "ts": _now().isoformat(),
                    "type": "threshold_crossed",
                    "severity": event.severity,
                    "metric": event.metric,
                    "previous": event.previous_value,
                    "current": event.current_value,
                    "direction": event.direction,
                    "message": event.message,
                }
            )
    except Exception:
        pass
    return alerts


def _send_telegram_alerts(alerts: list[dict]):
    """Send critical/high alerts via Telegram if configured."""
    try:
        from notifications.telegram_channel import is_configured, send_alert

        if not is_configured():
            return
        for alert in alerts:
            if alert.get("severity") in ("HIGH", "CRITICAL"):
                send_alert(
                    alert["message"],
                    severity=alert.get("severity", "WARNING"),
                    source="alert_monitor",
                )
    except Exception:
        pass


def main():
    prune_old_alerts()

    all_alerts: list[dict] = []
    all_alerts.extend(check_services())
    all_alerts.extend(check_scheduler_failures())
    all_alerts.extend(check_test_regression())
    all_alerts.extend(_run_threshold_checks())

    for alert in all_alerts:
        _append_alert(alert)
        severity = alert.get("severity", "INFO")
        icon = "🚨" if severity == "HIGH" else "⚠️"
        print(f"{icon} ALERT: {alert['message']}", file=sys.stderr)

    _send_telegram_alerts(all_alerts)

    # Update test baseline when all passing
    _save_test_baseline({})

    return len(all_alerts)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
