#!/usr/bin/env python3
"""Memory-loop maintenance — keeps the compounding layer from silently rotting.

Runs three idempotent jobs that the 2026-07 memory-restoration work identified
as needing a periodic driver (nothing was scheduling them, so they decayed):

  1. failure emission  — fold operational failures (restarts, alerts, scheduler
     errors, pytest) into the outcome stream as weighted `failed` outcomes, so
     the learning loop has a real failure signal to calibrate against.
  2. edge regeneration — rebuild the knowledge-graph edges from current nodes
     when the edge set has collapsed (the schema-mismatch regression wiped
     1247 edges to 0 between April and June 2026).
  3. decision index    — recorded decisions are auto-loaded by HybridRetriever
     on construction, so a rebuilt retriever is enough; we just report the
     count here for the maintenance log.

Idempotent and safe to run on a short interval (LaunchAgent / cron). Each job
guards its own exceptions so one failing job never blocks the others. Writes a
JSON run-report to ~/.cortex/maintenance/ for auditability.

Run standalone:  python -m scripts.memory_maintenance
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make repo-root modules importable when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

CORTEX_DIR = Path(os.environ.get("CORTEX_HOME", str(Path.home() / ".cortex")))
REPORT_DIR = CORTEX_DIR / "maintenance"


def _emit_failures(lookback_minutes: int) -> dict:
    """Job 1: emit collapsed operational failures into the outcome stream."""
    try:
        from intelligence import failure_emitter

        result = failure_emitter.run_once(lookback_minutes=lookback_minutes)
        return {"job": "failure_emission", "ok": True, **result}
    except Exception as exc:  # never let one job kill the run
        return {"job": "failure_emission", "ok": False, "error": str(exc)}


def _regenerate_edges() -> dict:
    """Job 2: sync decisions into the graph, then rebuild edges if collapsed.

    First imports any new recorded decisions as DECISION nodes (idempotent),
    then regenerates edges when the edge set is empty (the failure mode) OR
    when new decision nodes were just added (so they get linked). A healthy
    graph with no new decisions is left untouched to avoid churn.
    """
    try:
        from engines.synthesis import ContextGraph

        graph = ContextGraph()
        before = len(graph.edges)
        # Keep the graph in sync with newly recorded decisions.
        new_decisions = graph.import_decisions(save=False)
        # Regenerate when edges collapsed, or to link freshly imported decisions.
        if (before == 0 or new_decisions > 0) and graph.nodes:
            total = graph.regenerate_edges(save=True)
            return {
                "job": "edge_regeneration",
                "ok": True,
                "regenerated": True,
                "new_decision_nodes": new_decisions,
                "edges_before": before,
                "edges_after": total,
                "nodes": len(graph.nodes),
            }
        return {
            "job": "edge_regeneration",
            "ok": True,
            "regenerated": False,
            "new_decision_nodes": new_decisions,
            "edges": before,
            "nodes": len(graph.nodes),
        }
    except Exception as exc:
        return {"job": "edge_regeneration", "ok": False, "error": str(exc)}


def _decision_index() -> dict:
    """Job 3: report how many recorded decisions are recall-indexable."""
    try:
        from intelligence.memory.hybrid_retriever import _load_decision_patterns

        return {
            "job": "decision_index",
            "ok": True,
            "decisions_indexable": len(_load_decision_patterns()),
        }
    except Exception as exc:
        return {"job": "decision_index", "ok": False, "error": str(exc)}


def run_once(lookback_minutes: int = 90) -> dict:
    """Run all maintenance jobs once and persist a report."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jobs": [
            _emit_failures(lookback_minutes),
            _regenerate_edges(),
            _decision_index(),
        ],
    }
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with (REPORT_DIR / "maintenance_history.jsonl").open("a") as f:
            f.write(json.dumps(report) + "\n")
    except OSError:
        pass  # reporting is best-effort
    return report


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Cortex memory-loop maintenance")
    p.add_argument("--lookback-minutes", type=int, default=90)
    args = p.parse_args()
    print(json.dumps(run_once(lookback_minutes=args.lookback_minutes), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
