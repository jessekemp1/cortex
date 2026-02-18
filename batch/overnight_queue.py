#!/usr/bin/env python3
"""
Overnight Queue — Fills the batch queue with recurring 24/7 jobs.

Run nightly (e.g., midnight) to enqueue jobs that keep the system healthy:
- Cross-project test validation
- EMOS pair count monitoring
- Winfield accuracy tracking
- Cortex self-diagnostics (outcome counts, memory stats, graph growth)

Usage:
    python -m cortex.batch.overnight_queue          # Queue all jobs
    python -m cortex.batch.overnight_queue --dry-run # Preview without queueing
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Need both repo root (for cortex.* imports) and cortex/ (for intelligence.* imports)
_repo_root = str(Path(__file__).parent.parent.parent)
_cortex_root = str(Path(__file__).parent.parent)
sys.path.insert(0, _repo_root)
sys.path.insert(0, _cortex_root)

from cortex.batch.orchestrator import BatchOrchestrator, LocalJob

WORKSPACE = Path.home() / "Dev"


def test_validation_jobs() -> List[LocalJob]:
    """Cross-project test suites — catch regressions overnight.

    Each job runs pytest then persists results to ~/.cortex/metrics/tests.json
    via cortex.metrics.snapshot so session_start can display live counts.
    """
    # (display_name, project_key, test_dir)
    suites = [
        ("Vortex Backend", "vortex_backend", "Vortex/backend/tests"),
        ("Winfield", "winfield", "Vortex/Winfield/tests"),
        ("Alpha Arena", "alpha_arena", "alpha_arena/tests"),
        ("Cortex", "cortex", "cortex/tests"),
        ("Pupil", "pupil", "pupil/tests"),
    ]
    snapshot = "python3 -m cortex.metrics.snapshot"
    jobs = []
    for name, key, test_dir in suites:
        if (WORKSPACE / test_dir).exists():
            # Run pytest, capture summary line, persist via snapshot
            cmd = (
                f"output=$(pytest {test_dir}/ -q --tb=no 2>&1); rc=$?; "
                f"summary=$(echo \"$output\" | grep -E '\\d+ passed|no tests ran' | tail -1); "
                f'echo "$output"; '
                f'{snapshot} tests {key} $rc "$summary"'
            )
            jobs.append(
                LocalJob(
                    description=f"Nightly test: {name}",
                    command=cmd,
                    task_type="test",
                    working_dir=WORKSPACE,
                    priority="high",
                    timeout_seconds=300,
                    metadata={"project": name, "recurring": True},
                )
            )
    return jobs


def emos_monitoring_job() -> LocalJob:
    """Check EMOS pair counts — persists to ~/.cortex/metrics/emos.json."""
    return LocalJob(
        description="EMOS pair count check (HRRR/GFS/ECMWF)",
        command="python3 -m cortex.metrics.snapshot emos",
        task_type="monitoring",
        working_dir=WORKSPACE,
        priority="normal",
        timeout_seconds=30,
        metadata={"project": "Vortex Backend", "recurring": True},
    )


def cortex_diagnostics_job() -> LocalJob:
    """Cortex self-diagnostics — outcome counts, memory stats, graph growth."""
    return LocalJob(
        description="Cortex compound loop diagnostics",
        command=(
            'python3 -c "'
            "import json;"
            "from pathlib import Path;"
            "outcomes_file = Path.home() / '.claude' / 'v2' / 'outcomes.json';"
            "o = json.loads(outcomes_file.read_text()) if outcomes_file.exists() else {};"
            "print(f'Outcomes: {len(o.get(\"outcomes\", []))}');"
            "import sqlite3;"
            "graph_db = Path.home() / '.claude' / 'v2' / 'graph.db';"
            "if graph_db.exists():"
            "    conn = sqlite3.connect(str(graph_db));"
            "    nodes = conn.execute('SELECT COUNT(*) FROM nodes').fetchone()[0];"
            "    edges = conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0];"
            "    conn.close();"
            "    print(f'Graph: {nodes} nodes, {edges} edges');"
            "wm_db = Path.home() / '.cortex' / 'working_memory.db';"
            "if wm_db.exists():"
            "    conn = sqlite3.connect(str(wm_db));"
            "    try: items = conn.execute('SELECT COUNT(*) FROM working_memory').fetchone()[0];"
            "    except: items = 0;"
            "    conn.close();"
            "    print(f'Working memory: {items} items')\""
        ),
        task_type="monitoring",
        working_dir=WORKSPACE,
        priority="normal",
        timeout_seconds=15,
        metadata={"project": "Cortex", "recurring": True},
    )


def winfield_accuracy_job() -> LocalJob:
    """Winfield accuracy snapshot — capture current blend performance."""
    return LocalJob(
        description="Winfield accuracy snapshot",
        command="python3 -c \"import requests; r = requests.get('http://localhost:8002/health', timeout=3); print(r.json())\" 2>/dev/null || echo 'Winfield not running'",
        task_type="monitoring",
        working_dir=WORKSPACE,
        priority="low",
        timeout_seconds=10,
        metadata={"project": "Winfield", "recurring": True},
    )


def build_overnight_queue() -> List[LocalJob]:
    """Build the full overnight job queue."""
    jobs = []
    jobs.extend(test_validation_jobs())
    jobs.append(emos_monitoring_job())
    jobs.append(cortex_diagnostics_job())
    jobs.append(winfield_accuracy_job())
    return jobs


def main():
    parser = argparse.ArgumentParser(description="Fill overnight batch queue")
    parser.add_argument("--dry-run", action="store_true", help="Preview without queueing")
    args = parser.parse_args()

    jobs = build_overnight_queue()

    if args.dry_run:
        print(f"Would queue {len(jobs)} jobs:")
        for j in jobs:
            print(f"  [{j.priority}] {j.description}")
        return

    orchestrator = BatchOrchestrator()
    submitted = []
    for job in jobs:
        try:
            job_id = orchestrator.submit_job(job)
            submitted.append(job_id)
            print(f"  Queued: {job.description} -> {job_id}")
        except Exception as e:
            print(f"  FAILED: {job.description} -> {e}")

    print(f"\n{len(submitted)}/{len(jobs)} jobs queued at {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
