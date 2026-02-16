#!/usr/bin/env python3
"""
Compound Loop Metrics — Measures whether the feedback loop is actually growing.

Reads from:
- ~/.claude/v2/outcomes.json     → outcomes recorded by OutcomeDetector
- ~/.claude/v2/graph.db          → knowledge graph nodes/edges
- ~/.cortex/working_memory.db    → promoted memory items
- ~/.cortex/session_summaries.jsonl → session history
- ~/.cortex/session_cache.json   → session start context richness

Usage:
    python -m cortex.measurement.compound_metrics          # Full report
    python -m cortex.measurement.compound_metrics --json   # Machine-readable
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


CLAUDE_V2_DIR = Path.home() / ".claude" / "v2"
CORTEX_DIR = Path.home() / ".cortex"


def outcomes_count(days: int = 30) -> Dict[str, Any]:
    """Count outcomes and breakdown by type/source."""
    outcomes_file = CLAUDE_V2_DIR / "outcomes.json"
    if not outcomes_file.exists():
        return {"total": 0, "by_type": {}, "by_source": {}, "recent_7d": 0}

    data = json.loads(outcomes_file.read_text())
    outcomes = data.get("outcomes", [])

    cutoff_30d = (datetime.now(tz=None) - timedelta(days=days)).isoformat()
    cutoff_7d = (datetime.now(tz=None) - timedelta(days=7)).isoformat()

    by_type: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    recent_7d = 0

    for o in outcomes:
        ts = o.get("timestamp", "")
        if ts >= cutoff_30d:
            otype = o.get("outcome_type", "unknown")
            by_type[otype] = by_type.get(otype, 0) + 1
            source = o.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1
        if ts >= cutoff_7d:
            recent_7d += 1

    return {
        "total": len(outcomes),
        "by_type": by_type,
        "by_source": by_source,
        "recent_7d": recent_7d,
    }


def graph_stats() -> Dict[str, Any]:
    """Get knowledge graph size and growth."""
    graph_db = CLAUDE_V2_DIR / "graph.db"
    if not graph_db.exists():
        return {"nodes": 0, "edges": 0, "nodes_by_type": {}}

    conn = sqlite3.connect(str(graph_db))
    try:
        nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        type_rows = conn.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type").fetchall()
        nodes_by_type = dict(type_rows)
        return {"nodes": nodes, "edges": edges, "nodes_by_type": nodes_by_type}
    except Exception:
        return {"nodes": 0, "edges": 0, "nodes_by_type": {}}
    finally:
        conn.close()


def working_memory_count() -> Dict[str, Any]:
    """Count items in working memory (promoted from short-term)."""
    wm_db = CORTEX_DIR / "working_memory.db"
    if not wm_db.exists():
        return {"items": 0, "source": "not_found"}

    conn = sqlite3.connect(str(wm_db))
    try:
        items = conn.execute("SELECT COUNT(*) FROM working_memory").fetchone()[0]
        return {"items": items, "source": str(wm_db)}
    except Exception:
        return {"items": 0, "source": "error"}
    finally:
        conn.close()


def session_history(days: int = 30) -> Dict[str, Any]:
    """Analyze session summaries for trend data."""
    summaries_file = CORTEX_DIR / "session_summaries.jsonl"
    if not summaries_file.exists():
        return {"total_sessions": 0, "recent_7d": 0, "avg_insights": 0}

    cutoff = (datetime.now(tz=None) - timedelta(days=days)).isoformat()
    cutoff_7d = (datetime.now(tz=None) - timedelta(days=7)).isoformat()

    total = 0
    recent_7d = 0
    total_insights = 0

    with open(summaries_file) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                ts = entry.get("timestamp", "")
                if ts >= cutoff:
                    total += 1
                    total_insights += entry.get("insights_captured", 0)
                if ts >= cutoff_7d:
                    recent_7d += 1
            except (json.JSONDecodeError, ValueError):
                continue

    return {
        "total_sessions": total,
        "recent_7d": recent_7d,
        "avg_insights": round(total_insights / max(total, 1), 1),
    }


def session_context_richness() -> Dict[str, Any]:
    """Measure how many fields are populated at session start."""
    cache_file = CORTEX_DIR / "session_cache.json"
    if not cache_file.exists():
        return {"fields_populated": 0, "total_fields": 8, "richness_pct": 0}

    try:
        data = json.loads(cache_file.read_text())
        ctx = data.get("context", {})
    except Exception:
        return {"fields_populated": 0, "total_fields": 8, "richness_pct": 0}

    expected_fields = [
        "project",
        "focus",
        "goals",
        "recent_work",
        "pr_status",
        "insights",
        "budget",
        "flywheel",
    ]

    populated = 0
    for field in expected_fields:
        val = ctx.get(field)
        if val and val != "Unknown" and val != {} and val != []:
            populated += 1

    return {
        "fields_populated": populated,
        "total_fields": len(expected_fields),
        "richness_pct": round(populated / len(expected_fields) * 100),
    }


def full_report() -> Dict[str, Any]:
    """Generate the complete compound loop health report."""
    return {
        "generated_at": datetime.now(tz=None).isoformat(),
        "outcomes": outcomes_count(),
        "graph": graph_stats(),
        "working_memory": working_memory_count(),
        "sessions": session_history(),
        "context_richness": session_context_richness(),
    }


def print_report(report: Dict[str, Any]) -> None:
    """Pretty-print the compound metrics report."""
    o = report["outcomes"]
    g = report["graph"]
    w = report["working_memory"]
    s = report["sessions"]
    c = report["context_richness"]

    print("=" * 55)
    print("  COMPOUND LOOP HEALTH REPORT")
    print(f"  Generated: {report['generated_at'][:19]}")
    print("=" * 55)
    print()
    print(f"  Outcomes     : {o['total']:>4} total  ({o['recent_7d']} last 7d)")
    print(f"  Graph        : {g['nodes']:>4} nodes, {g['edges']} edges")
    print(f"  Working Mem  : {w['items']:>4} items")
    print(f"  Sessions(30d): {s['total_sessions']:>4} ({s['avg_insights']} avg insights)")
    print(
        f"  Context      : {c['fields_populated']}/{c['total_fields']} fields ({c['richness_pct']}%)"
    )
    print()

    # Health assessment
    health_score = 0
    if o["total"] > 3:
        health_score += 1  # Beyond seed data
    if o["recent_7d"] > 0:
        health_score += 1  # Active recording
    if g["nodes"] > 44:
        health_score += 1  # Beyond seed graph
    if w["items"] > 6:
        health_score += 1  # Beyond test items
    if c["richness_pct"] >= 50:
        health_score += 1  # Decent context

    bar = "#" * health_score + "." * (5 - health_score)
    print(f"  Health: [{bar}] {health_score}/5")

    if health_score < 3:
        print("  Status: BOOTSTRAPPING — loop wired, accumulating data")
    elif health_score < 5:
        print("  Status: GROWING — compound effects starting")
    else:
        print("  Status: COMPOUNDING — full loop active")
    print()


def main():
    import sys

    report = full_report()

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
