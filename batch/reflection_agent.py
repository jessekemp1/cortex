#!/usr/bin/env python3
"""
Reflection Agent — Pattern Consolidation Batch Job

Reads ~/.cortex/outcomes.jsonl + ~/.cortex/signal_bus.db, finds repeated
patterns (>= 3 occurrences), synthesises lessons via Haiku, and writes
NodeType.LESSON nodes into the ContextGraph.

Run: python -m cortex.batch.reflection_agent [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

# Ensure repo root on path when run directly
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
_cortex_root = str(Path(__file__).resolve().parent.parent)
for _p in (_repo_root, _cortex_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CORTEX_HOME = Path.home() / ".cortex"
OUTCOMES_FILE = CORTEX_HOME / "outcomes.jsonl"
SIGNAL_BUS_DB = CORTEX_HOME / "signal_bus.db"
REFLECTION_MODEL = "claude-haiku-4-5"
PATTERN_THRESHOLD = 3
MAX_CLUSTERS = 10


class ReflectionResult(TypedDict):
    date: str
    outcomes_read: int
    signals_read: int
    patterns_found: int
    lessons_added: int
    model: str
    dry_run: bool


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_recent_outcomes(days: int = 7, path: Path = OUTCOMES_FILE) -> List[Dict[str, Any]]:
    """Return outcome records from the last `days` days."""
    if not path.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    results: List[Dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts_str = record.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        # Normalize TZ — record timestamps may be aware
                        # (ISO with +00:00) or naive; cutoff may be either.
                        # Compare by stripping tzinfo so a stray TZ-aware
                        # record doesn't raise TypeError.
                        if ts.tzinfo is not None:
                            ts = ts.replace(tzinfo=None)
                        cutoff_naive = (
                            cutoff.replace(tzinfo=None) if cutoff.tzinfo else cutoff
                        )
                        if ts < cutoff_naive:
                            continue
                    except ValueError:
                        pass  # keep records with unparseable timestamps
                results.append(record)
            except json.JSONDecodeError:
                continue
    return results


def load_signal_bus_events(days: int = 7, db_path: Path = SIGNAL_BUS_DB) -> List[Dict[str, Any]]:
    """Return signal bus events from the last `days` days."""
    if not db_path.exists():
        return []

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    results: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM bus_events WHERE timestamp >= ? ORDER BY timestamp DESC",
            (cutoff,),
        )
        for row in cur.fetchall():
            results.append(dict(row))
        conn.close()
    except Exception:
        pass  # DB may not have table yet — non-fatal
    return results


# ---------------------------------------------------------------------------
# Pattern detection (pure Python, no LLM)
# ---------------------------------------------------------------------------


def find_repeated_patterns(
    outcomes: List[Dict[str, Any]],
    signals: List[Dict[str, Any]],
    threshold: int = PATTERN_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Group outcomes by domain+outcome. Return clusters with >= threshold occurrences.
    """
    clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for rec in outcomes:
        domain = rec.get("domain", "unknown")
        outcome = rec.get("outcome", "unknown")
        key = f"{domain}:{outcome}"
        clusters[key].append(rec)

    patterns = []
    for key, records in clusters.items():
        if len(records) >= threshold:
            domain, outcome = key.split(":", 1)
            patterns.append(
                {
                    "key": key,
                    "domain": domain,
                    "outcome": outcome,
                    "count": len(records),
                    "sample_titles": [r.get("recommendation_title", "") for r in records[:3]],
                    "avg_confidence": (
                        sum(r.get("confidence", 0.5) for r in records) / len(records)
                    ),
                }
            )

    # Sort by count descending, cap at MAX_CLUSTERS
    patterns.sort(key=lambda p: p["count"], reverse=True)
    return patterns[:MAX_CLUSTERS]


# ---------------------------------------------------------------------------
# Lesson synthesis via Haiku
# ---------------------------------------------------------------------------


def synthesise_lessons(
    patterns: List[Dict[str, Any]],
    anthropic_client=None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Call Haiku to synthesise a lesson for each pattern cluster."""
    if dry_run or not patterns:
        return [
            {
                "pattern_key": p["key"],
                "domain": p["domain"],
                "outcome": p["outcome"],
                "lesson": f"[dry-run] Pattern '{p['key']}' seen {p['count']} times.",
                "confidence": p["avg_confidence"],
                "dry_run": True,
            }
            for p in patterns
        ]

    if anthropic_client is None:
        try:
            import anthropic  # type: ignore

            anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        except ImportError:
            # Return stubs if anthropic not installed
            return [
                {
                    "pattern_key": p["key"],
                    "domain": p["domain"],
                    "outcome": p["outcome"],
                    "lesson": f"Pattern '{p['key']}' seen {p['count']} times.",
                    "confidence": p["avg_confidence"],
                    "error": "anthropic package not installed",
                }
                for p in patterns
            ]

    lessons = []
    for pattern in patterns:
        prompt = (
            f"Domain: {pattern['domain']}\n"
            f"Outcome: {pattern['outcome']}\n"
            f"Occurrences: {pattern['count']}\n"
            f"Example titles: {', '.join(pattern['sample_titles'])}\n\n"
            "Write ONE concise lesson (≤80 chars) learned from this repeated pattern. "
            "Output only the lesson text, no commentary."
        )
        lesson_text = f"Pattern '{pattern['key']}' repeated {pattern['count']} times."
        try:
            response = anthropic_client.messages.create(
                model=REFLECTION_MODEL,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            lesson_text = response.content[0].text.strip()
        except Exception:
            pass  # Keep fallback text

        lessons.append(
            {
                "pattern_key": pattern["key"],
                "domain": pattern["domain"],
                "outcome": pattern["outcome"],
                "lesson": lesson_text,
                "confidence": pattern["avg_confidence"],
                "dry_run": False,
            }
        )

    return lessons


# ---------------------------------------------------------------------------
# Write lessons to graph
# ---------------------------------------------------------------------------


def write_lessons_to_graph(
    lessons: List[Dict[str, Any]],
    storage_path: Optional[Path] = None,
) -> int:
    """Add NodeType.LESSON nodes to ContextGraph. Returns count added."""
    if not lessons:
        return 0

    if storage_path is None:
        storage_path = Path.home() / ".cortex" / "graph"

    try:
        from cortex.engines.synthesis import ContextGraph, Node, NodeType

        graph = ContextGraph(storage_path=storage_path)
        added = 0
        for lesson in lessons:
            node_id = f"lesson:{lesson['pattern_key']}:{date.today().isoformat()}"
            node = Node(
                id=node_id,
                type=NodeType.LESSON,
                name=lesson["lesson"][:80],
                data={
                    "pattern_key": lesson["pattern_key"],
                    "domain": lesson["domain"],
                    "outcome": lesson["outcome"],
                    "lesson": lesson["lesson"],
                    "confidence": lesson["confidence"],
                    "created_date": date.today().isoformat(),
                    "dry_run": lesson.get("dry_run", False),
                },
            )
            graph.add_node(node)
            added += 1

        graph._save()
        return added
    except Exception as e:
        print(f"  write_lessons_to_graph: failed — {e}", file=sys.stderr)
        return 0


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ReflectionAgent:
    def __init__(self, anthropic_client=None):
        self._client = anthropic_client

    def run(self, dry_run: bool = False) -> ReflectionResult:
        outcomes = load_recent_outcomes()
        signals = load_signal_bus_events()
        patterns = find_repeated_patterns(outcomes, signals)
        lessons = synthesise_lessons(patterns, anthropic_client=self._client, dry_run=dry_run)
        added = 0 if dry_run else write_lessons_to_graph(lessons)

        result: ReflectionResult = {
            "date": date.today().isoformat(),
            "outcomes_read": len(outcomes),
            "signals_read": len(signals),
            "patterns_found": len(patterns),
            "lessons_added": added,
            "model": REFLECTION_MODEL,
            "dry_run": dry_run,
        }
        return result


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex Reflection Agent")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls and graph writes")
    args = parser.parse_args()

    agent = ReflectionAgent()
    result = agent.run(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
