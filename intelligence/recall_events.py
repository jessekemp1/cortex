"""Recall-event instrumentation — proof the memory loop is being *used*.

Every intelligence query (HTTP route or in-process MCP tool) appends one JSON
line to ``<cortex_state>/recall_events.jsonl`` recording what the query
surfaced:

    {"ts": ..., "session_id": ..., "n_predictions": int, "n_decisions_surfaced": int}

This is the raw signal behind the `cortex stats` "memory is being used"
headline. Two hard rules:

  * **Best-effort.** Logging a recall event must NEVER break the query it
    instruments — every public function here swallows its own exceptions.
  * **Real data only.** ``n_predictions`` / ``n_decisions_surfaced`` are counted
    from the actual query result. Nothing is invented; a query that surfaced
    nothing writes zeros.

Paths resolve through ``state_paths.get_cortex_dir()`` at call time (honors
``CORTEX_STATE_DIR`` / ``CORTEX_HOME``), so tests can redirect the whole store
to a tmp dir.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from state_paths import get_cortex_dir


def _recall_events_file() -> Path:
    return get_cortex_dir() / "recall_events.jsonl"


def _session_id() -> Optional[str]:
    """Best-guess current session id, or None.

    Cortex sets ``CORTEX_SESSION_ID`` from the session hook; fall back to
    ``CLAUDE_SESSION_ID`` if present. Never guesses a fake value — None is
    honest when we don't know.
    """
    sid = os.environ.get("CORTEX_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
    return sid or None


def count_surfaced(result: Dict[str, Any]) -> Dict[str, int]:
    """Count real items an intelligence result surfaced.

    Returns ``{"n_predictions", "n_decisions_surfaced"}``:

      * ``n_predictions`` — total retrieved items across the result's
        prediction-bearing lists (context_predictions + similar_work +
        applicable_patterns + related_patterns). These are the recalled
        memories the query put in front of the caller.
      * ``n_decisions_surfaced`` — how many of those are recorded *decisions*
        (indexed with id ``decision:<id>`` and/or type ``decision`` by
        pattern_indexer). This is the sharper "your past decisions came back
        to you" signal.

    Never raises — an unexpected shape yields zeros.
    """
    n_predictions = 0
    n_decisions = 0
    try:
        preds: List[Any] = result.get("context_predictions") or []
        similar: List[Any] = result.get("similar_work") or []
        patterns: List[Any] = result.get("applicable_patterns") or []
        related: List[Any] = result.get("related_patterns") or []

        n_predictions = len(preds) + len(similar) + len(patterns) + len(related)

        def _is_decision(item: Any) -> bool:
            if not isinstance(item, dict):
                return False
            if str(item.get("type", "")).lower() == "decision":
                return True
            for key in ("id", "source", "reference", "reference_path"):
                val = item.get(key)
                if isinstance(val, str) and "decision" in val.lower():
                    return True
            return False

        for group in (preds, similar, patterns, related):
            for item in group:
                if _is_decision(item):
                    n_decisions += 1
    except Exception:
        return {"n_predictions": 0, "n_decisions_surfaced": 0}

    return {"n_predictions": n_predictions, "n_decisions_surfaced": n_decisions}


def record_recall_event(
    result: Dict[str, Any],
    session_id: Optional[str] = None,
) -> None:
    """Append one recall event for an intelligence query result. Best-effort.

    ``result`` is the dict returned by ``bridge.query_intelligence``. A result
    carrying an ``error`` key is skipped (a failed query surfaced nothing, so
    logging it would overstate usage). Any exception is swallowed so this can
    be called on the hot path without a try/except at every call site.
    """
    try:
        if not isinstance(result, dict) or "error" in result:
            return
        counts = count_surfaced(result)
        entry = {
            "ts": datetime.now().isoformat(),
            "session_id": session_id if session_id is not None else _session_id(),
            "n_predictions": counts["n_predictions"],
            "n_decisions_surfaced": counts["n_decisions_surfaced"],
        }
        path = _recall_events_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        return  # instrumentation must never break the query


def read_recall_events(days: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read recall events, newest last. Optionally filter to the last ``days``.

    Small reader used by ``cortex stats``. Never raises — a missing or corrupt
    file yields ``[]`` (honest zero).
    """
    path = _recall_events_file()
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
    except OSError:
        return []

    if days is not None:
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        events = [e for e in events if str(e.get("ts", "")) >= cutoff]
    return events


def recall_summary(days: int = 7) -> Dict[str, int]:
    """Aggregate recall usage for the stats report.

    Returns totals computed from real events only:
      * ``total_recalls`` — number of instrumented queries (all time)
      * ``recalls_7d`` — instrumented queries in the window
      * ``decisions_resurfaced`` — sum of ``n_decisions_surfaced`` (all time)
      * ``predictions_surfaced`` — sum of ``n_predictions`` (all time)
    """
    all_events = read_recall_events()
    windowed = read_recall_events(days=days)
    return {
        "total_recalls": len(all_events),
        "recalls_7d": len(windowed),
        "decisions_resurfaced": sum(int(e.get("n_decisions_surfaced", 0) or 0) for e in all_events),
        "predictions_surfaced": sum(int(e.get("n_predictions", 0) or 0) for e in all_events),
    }
