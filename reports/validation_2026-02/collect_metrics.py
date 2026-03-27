#!/usr/bin/env python3
"""
Cortex Validation Metrics Collector
Captures daily snapshots during 7-day validation period (Jan 31 - Feb 7)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).parent
METRICS_FILE = REPORT_DIR / "metrics_snapshots.json"


def run_command(cmd):
    """Run shell command and return output."""
    import shlex
    try:
        result = subprocess.run(shlex.split(cmd), shell=False, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def collect_snapshot():
    """Collect current metrics snapshot."""
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "day_of_validation": calculate_validation_day(),
    }

    # Batch Queue Status
    snapshot["batch_queue"] = {
        "queued": count_queued_jobs(),
        "running": count_running_jobs(),
        "completed_today": count_completed_jobs(),
    }

    # Supervisor Status
    supervisor_status = run_command("ps aux | grep cortex | grep supervisor | grep -v grep | wc -l")
    snapshot["supervisor"] = {
        "running": int(supervisor_status) > 0,
        "pid": get_supervisor_pid(),
    }

    # Dashboard Status
    dashboard_status = run_command("lsof -i :8502 | grep LISTEN | wc -l")
    snapshot["dashboard"] = {
        "running": int(dashboard_status) > 0,
        "port": 8502,
        "uptime_hours": get_uptime_hours(8502),
    }

    # Port Usage
    ports_in_use = run_command("lsof -i -P -n | grep LISTEN | wc -l")
    snapshot["infrastructure"] = {
        "ports_in_use": int(ports_in_use) if ports_in_use.isdigit() else 0,
        "services": count_services(),
    }

    # Active Projects (from Launch Control)
    try:
        with open(Path.home() / "Dev/cortex/launcher/launcher_data.json") as f:
            launcher_data = json.load(f)
            running_projects = sum(
                1
                for p in launcher_data["projects"]
                if p.get("status") == "running"
                or (p.get("services") and any(s.get("status") == "running" for s in p["services"]))
            )
            snapshot["projects"] = {
                "total": len(launcher_data["projects"]),
                "running": running_projects,
            }
    except Exception as e:
        snapshot["projects"] = {"error": str(e)}

    return snapshot


def calculate_validation_day():
    """Calculate which day of validation (1-7) we're on."""
    start_date = datetime(2026, 1, 31)
    today = datetime.now()
    delta = (today - start_date).days + 1
    return max(1, min(delta, 7))


def count_queued_jobs():
    """Count jobs in batch queue."""
    try:
        # Check queue file
        queue_file = Path.home() / ".cortex/batches/remediation_queue.json"
        if queue_file.exists():
            with open(queue_file) as f:
                data = json.load(f)
                return len(data.get("priority_jobs", []))
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return 0


def count_running_jobs():
    """Count currently running batch jobs."""
    # This would query Anthropic API for active batches
    # Placeholder for now
    return 0


def count_completed_jobs():
    """Count jobs completed today."""
    # This would check completion log
    return 0


def get_supervisor_pid():
    """Get supervisor process PID."""
    output = run_command("ps aux | grep 'cortex supervisor' | grep -v grep | awk '{print $2}'")
    return int(output) if output.isdigit() else None


def get_uptime_hours(port):
    """Estimate uptime for service on given port."""
    # Simple heuristic based on process start time
    # Could be improved with actual uptime tracking
    return None


def count_services():
    """Count active Cortex services."""
    services = [
        ("Cortex Orchestration", 8502),
        ("Cortex Bridge API", 8765),
        ("Cortex Command Center", 5174),
        ("Launch Control", 3333),
    ]

    running = 0
    for name, port in services:
        check = run_command(f"lsof -i :{port} | grep LISTEN | wc -l")
        if check and int(check) > 0:
            running += 1

    return running


def save_snapshot(snapshot):
    """Save snapshot to metrics file."""
    # Load existing snapshots
    if METRICS_FILE.exists():
        with open(METRICS_FILE) as f:
            data = json.load(f)
    else:
        data = {"snapshots": []}

    # Append new snapshot
    data["snapshots"].append(snapshot)

    # Save back
    with open(METRICS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Snapshot saved: {snapshot['date']} (Day {snapshot['day_of_validation']}/7)")


def generate_summary():
    """Generate summary from all snapshots."""
    if not METRICS_FILE.exists():
        print("No snapshots yet")
        return

    with open(METRICS_FILE) as f:
        data = json.load(f)

    snapshots = data.get("snapshots", [])
    if not snapshots:
        print("No snapshots yet")
        return

    print(f"\n📊 Validation Metrics Summary ({len(snapshots)} snapshots)\n")

    # Batch Queue
    print("Batch Queue:")
    for s in snapshots:
        bq = s.get("batch_queue", {})
        print(f"  {s['date']}: {bq.get('queued', 0)} queued, {bq.get('running', 0)} running")

    # Services
    print("\nServices:")
    latest = snapshots[-1]
    print(
        f"  Dashboard: {'✅ Running' if latest.get('dashboard', {}).get('running') else '❌ Stopped'}"
    )
    print(
        f"  Supervisor: {'✅ Running' if latest.get('supervisor', {}).get('running') else '❌ Stopped'}"
    )
    print(f"  Active Services: {latest.get('infrastructure', {}).get('services', 0)}/4")

    # Projects
    print("\nProjects:")
    proj = latest.get("projects", {})
    print(f"  Total: {proj.get('total', 0)}")
    print(f"  Running: {proj.get('running', 0)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        generate_summary()
    else:
        snapshot = collect_snapshot()
        save_snapshot(snapshot)
        print("\nSnapshot details:")
        print(json.dumps(snapshot, indent=2))
