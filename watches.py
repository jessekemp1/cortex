"""Cortex Watch — scheduled verification tasks that bridge sessions.

A Watch is a script + pass/fail criteria that runs between sessions
(via the morning processor daemon) and surfaces results in the next
session's briefing.

Usage from a Claude session:
    from cortex.watches import create_watch
    create_watch(
        name="blend_revalidation",
        script="/path/to/script.sh",
        criteria={"blend_mae_lt": 4.0, "hrrr_warnings_eq": 0, "min_records": 50},
        run_after="07:00",
        context="Post-fix blend validation. HRRR lon bug fixed Feb 17.",
    )

The morning_processor picks up pending watches, runs them, evaluates
criteria, and writes results to briefing_cache.json.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WATCHES_DIR = Path.home() / ".cortex" / "watches"
PENDING_DIR = WATCHES_DIR / "pending"
COMPLETED_DIR = WATCHES_DIR / "completed"


def create_watch(
    name: str,
    script: str,
    criteria: dict[str, Any],
    run_after: str = "06:00",
    context: str = "",
    timeout_seconds: int = 120,
) -> Path:
    """Create a pending watch task.

    Args:
        name: Short identifier (used as filename).
        script: Absolute path to script to execute.
        criteria: Dict of metric_name -> expected_value. Supported operators:
            - "metric_lt": value  (metric < value = PASS)
            - "metric_gt": value  (metric > value = PASS)
            - "metric_eq": value  (metric == value = PASS)
            - "min_records": int  (output line count >= value = PASS)
        run_after: HH:MM time string. Daemon skips if current time < run_after.
        context: Human-readable explanation of why this watch exists.
        timeout_seconds: Max script runtime.

    Returns:
        Path to the created watch JSON file.
    """
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    watch = {
        "name": name,
        "script": script,
        "criteria": criteria,
        "run_after": run_after,
        "timeout_seconds": timeout_seconds,
        "context": context,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    path = PENDING_DIR / f"{name}.json"
    path.write_text(json.dumps(watch, indent=2))
    return path


def run_watch(watch_path: Path) -> dict[str, Any]:
    """Execute a watch task and evaluate its criteria.

    Returns a result dict with status, output, and per-criterion verdicts.
    """
    watch = json.loads(watch_path.read_text())

    # Check run_after time gate
    now = datetime.now()
    run_after = watch.get("run_after", "00:00")
    hour, minute = map(int, run_after.split(":"))
    if now.hour < hour or (now.hour == hour and now.minute < minute):
        return {"status": "skipped", "reason": f"Too early (before {run_after})"}

    script = watch["script"]
    timeout = watch.get("timeout_seconds", 120)

    # Execute the script
    try:
        result = subprocess.run(
            ["/bin/bash", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.home() / "Dev"),
        )
        output = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        output = ""
        stderr = f"Script timed out after {timeout}s"
        exit_code = -1
    except Exception as e:
        output = ""
        stderr = str(e)
        exit_code = -2

    # Evaluate criteria against output
    verdicts = _evaluate_criteria(watch.get("criteria", {}), output, exit_code)
    all_pass = all(v["pass"] for v in verdicts)

    completed = {
        **watch,
        "status": "pass" if all_pass else "fail",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "output": output[-2000:],  # Last 2KB
        "stderr": stderr[-500:] if stderr else "",
        "verdicts": verdicts,
    }

    # Move to completed
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    completed_path = COMPLETED_DIR / watch_path.name
    completed_path.write_text(json.dumps(completed, indent=2))
    watch_path.unlink()

    return completed


def _evaluate_criteria(
    criteria: dict[str, Any], output: str, exit_code: int
) -> list[dict[str, Any]]:
    """Evaluate pass/fail criteria against script output.

    Parses output for key=value patterns (e.g., "blend_mae=3.45")
    and compares against criteria thresholds.
    """
    verdicts = []

    # Parse metrics from output (look for key=value or key: value patterns)
    metrics = _parse_metrics(output)

    for criterion, expected in criteria.items():
        # Determine operator from suffix
        if criterion.endswith("_lt"):
            metric_name = criterion[:-3]
            actual = metrics.get(metric_name)
            passed = actual is not None and float(actual) < float(expected)
            op = "<"
        elif criterion.endswith("_gt"):
            metric_name = criterion[:-3]
            actual = metrics.get(metric_name)
            passed = actual is not None and float(actual) > float(expected)
            op = ">"
        elif criterion.endswith("_eq"):
            metric_name = criterion[:-3]
            actual = metrics.get(metric_name)
            passed = actual is not None and str(actual) == str(expected)
            op = "=="
        elif criterion == "min_records":
            actual = len([line for line in output.strip().split("\n") if line.strip()])
            passed = actual >= int(expected)
            metric_name = "output_lines"
            op = ">="
        elif criterion == "exit_code":
            actual = exit_code
            passed = exit_code == int(expected)
            metric_name = "exit_code"
            op = "=="
        else:
            # Unknown criterion — try exact match
            actual = metrics.get(criterion)
            passed = actual is not None and str(actual) == str(expected)
            metric_name = criterion
            op = "=="

        verdicts.append(
            {
                "criterion": criterion,
                "metric": metric_name,
                "expected": f"{op} {expected}",
                "actual": actual,
                "pass": passed,
            }
        )

    return verdicts


def _parse_metrics(output: str) -> dict[str, str]:
    """Extract key=value and key: value metrics from script output."""
    metrics: dict[str, str] = {}

    for line in output.split("\n"):
        line = line.strip()
        # Match: metric_name=value or metric_name: value
        for sep in ["=", ": "]:
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower().replace(" ", "_")
                    val = parts[1].strip()
                    # Clean common unit suffixes (use removesuffix, not
                    # rstrip which strips individual chars destructively)
                    for suffix in ["kts", "kt", "deg", "°", "%"]:
                        if val.endswith(suffix):
                            val = val[: -len(suffix)].strip()
                            break
                    metrics[key] = val

    return metrics


def list_pending() -> list[dict[str, Any]]:
    """List all pending watch tasks."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    watches = []
    for path in sorted(PENDING_DIR.glob("*.json")):
        try:
            watches.append(json.loads(path.read_text()))
        except Exception:
            continue
    return watches


def list_completed(hours: int = 24) -> list[dict[str, Any]]:
    """List recently completed watch tasks."""
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    watches = []
    for path in sorted(COMPLETED_DIR.glob("*.json")):
        try:
            if path.stat().st_mtime > cutoff:
                watches.append(json.loads(path.read_text()))
        except Exception:
            continue
    return watches


def format_results(watches: list[dict[str, Any]]) -> str:
    """Format watch results for briefing display."""
    if not watches:
        return "No watch results."

    lines = ["Watch Task Results:", ""]
    for w in watches:
        status_icon = "PASS" if w.get("status") == "pass" else "FAIL"
        lines.append(f"  [{status_icon}] {w['name']} — {w.get('context', '')[:60]}")
        for v in w.get("verdicts", []):
            check = "ok" if v["pass"] else "FAIL"
            lines.append(f"    {check}: {v['metric']} {v['expected']} (actual: {v['actual']})")
        lines.append("")

    return "\n".join(lines)
