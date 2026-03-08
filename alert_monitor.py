#!/usr/bin/env python3
"""
Alert Monitor — surfaces critical failures and auto-restarts Tier 1 services.

Checks every invocation (called by LaunchAgent every 5 minutes):
  1. Service health: HTTP GET to all operational endpoints
  2. Auto-restart: Tier 1 services get launchctl kickstart on failure
  3. Scheduler failures: errors in ~/.cortex/metrics/scheduler_jobs.jsonl (last 5 min)
  4. Test regression: project test counts vs persisted baseline (>2% drop = alert)

Writes to ~/.cortex/alerts.jsonl (append-only, read by session_start_context.py).
Suppressed for 1h by: touch ~/.cortex/alert_silence_<service>
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

CORTEX_DIR = Path.home() / ".cortex"
ALERTS_LOG = CORTEX_DIR / "alerts.jsonl"
METRICS_DIR = CORTEX_DIR / "metrics"
SILENCE_DIR = CORTEX_DIR  # silence files: alert_silence_<service>
CONSECUTIVE_FILE = CORTEX_DIR / "alert_consecutive.json"
RESTART_LOG = CORTEX_DIR / "restart_history.jsonl"

# === Tier 1: Always-on operational services (99.99% target) ===
# === Tier 2: Supporting services ===
SERVICES = [
    ("vortex-backend", "http://127.0.0.1:8000/api/v2/health"),
    ("cortex-runtime", "http://127.0.0.1:8003/docs"),
    ("cortex-bridge", "http://127.0.0.1:8765/health"),
    ("cortex-site", "http://127.0.0.1:3001/"),
    ("alpha-arena", "http://127.0.0.1:8502/_stcore/health"),
    ("navigator", "http://127.0.0.1:8000/api/v2/navigator/health"),
]

# Map service names to their launchd labels for auto-restart
TIER1_LAUNCHD_LABELS = {
    "vortex-backend": "com.vortexv2.backend",
    "cortex-runtime": "com.cortex.runtime",
    "cortex-bridge": "com.cortex.bridge",
    "cortex-site": "com.cortex.site",
    "alpha-arena": "com.alphaarena.dashboard",
}

# Per-service consecutive failure thresholds (default: 2)
CONSECUTIVE_THRESHOLD = 2
CONSECUTIVE_THRESHOLDS = {
    "navigator": 3,  # Navigator has external API deps (Open-Meteo) — allow more retries
}

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
    """Attempt to restart a Tier 1 service via launchctl kickstart."""
    label = TIER1_LAUNCHD_LABELS.get(service)
    if not label:
        return False

    # Rate limit: max N restarts per hour
    if _recent_restart_count(service) >= MAX_RESTARTS_PER_HOUR:
        print(
            f"⚠️  RESTART SUPPRESSED: {service} hit {MAX_RESTARTS_PER_HOUR} restarts/hour limit",
            file=sys.stderr,
        )
        return False

    try:
        # Force-restart via launchctl kickstart -k (kill + restart)
        result = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/502/{label}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        success = result.returncode == 0
        _log_restart(service, label, success)
        if success:
            print(f"🔄 AUTO-RESTART: {service} ({label}) restarted", file=sys.stderr)
        else:
            print(
                f"❌ RESTART FAILED: {service} ({label}): {result.stderr.strip()}",
                file=sys.stderr,
            )
        return success
    except Exception as e:
        _log_restart(service, label, False)
        print(f"❌ RESTART ERROR: {service}: {e}", file=sys.stderr)
        return False


def check_service(name: str, url: str) -> tuple[bool, str]:
    """Return (healthy, status_detail) for a service.

    For Navigator, parses the JSON response to detect degraded status
    (subsystem failures) even when the HTTP response is 200.
    """
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status != 200:
                return False, "http_error"
            # Navigator returns structured health with subsystem checks
            if name == "navigator":
                data = json.loads(resp.read())
                status = data.get("status", "unknown")
                if status == "healthy":
                    return True, "healthy"
                # "degraded" or "unhealthy" — report which subsystems failed
                failed = [
                    k
                    for k, v in data.get("checks", {}).items()
                    if isinstance(v, dict) and v.get("status") != "ok"
                ]
                return False, f"{status}:{','.join(failed)}" if failed else status
            return True, "healthy"
    except Exception:
        return False, "unreachable"


def check_services() -> list[dict]:
    """Check all services, return list of alert dicts for down services."""
    consec = _load_consecutive()
    alerts = []
    now_ts = _now().isoformat()

    for name, url in SERVICES:
        if _is_silenced(name):
            continue
        healthy, detail = check_service(name, url)
        threshold = CONSECUTIVE_THRESHOLDS.get(name, CONSECUTIVE_THRESHOLD)

        if healthy:
            # Reset consecutive failure counter
            consec[name] = 0
        else:
            consec[name] = consec.get(name, 0) + 1

            # Auto-restart Tier 1 services after threshold
            if consec[name] >= AUTO_RESTART_THRESHOLD and name in TIER1_LAUNCHD_LABELS:
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


def main():
    prune_old_alerts()

    all_alerts: list[dict] = []
    all_alerts.extend(check_services())
    all_alerts.extend(check_scheduler_failures())
    all_alerts.extend(check_test_regression())

    for alert in all_alerts:
        _append_alert(alert)
        severity = alert.get("severity", "INFO")
        icon = "🚨" if severity == "HIGH" else "⚠️"
        print(f"{icon} ALERT: {alert['message']}", file=sys.stderr)

    # Update test baseline when all passing
    _save_test_baseline({})

    return len(all_alerts)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
