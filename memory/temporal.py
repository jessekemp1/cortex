"""
Temporal Retrieval — query Cortex flat-file stores by time window.

Searches across:
  - ~/.cortex/interaction_queue.jsonl  (prompts, queued_at field)
  - ~/.cortex/reflections/*.json       (nightly reflections, date field)
  - ~/.cortex/alerts.jsonl             (system alerts)
  - ~/.cortex/conversation_digests.jsonl

Usage:
    from memory.temporal import TemporalQuery
    tq = TemporalQuery()
    results = tq.query(since="3d")          # last 3 days
    results = tq.query(since="2026-04-01")  # absolute date
    results = tq.query(since="2026-04-01", until="2026-04-07")
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CORTEX_HOME = Path.home() / ".cortex"

# Sources to query — (path, timestamp_field, type_label)
SOURCES: List[Tuple[Path, str, str]] = [
    (CORTEX_HOME / "interaction_queue.jsonl", "queued_at", "interaction"),
    (CORTEX_HOME / "alerts.jsonl", "timestamp", "alert"),
    (CORTEX_HOME / "conversation_digests.jsonl", "timestamp", "digest"),
]


# ---------------------------------------------------------------------------
# Time window parsing
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_relative(spec: str) -> datetime:
    """
    Parse relative window specs like '3d', '2h', '1w', 'yesterday', 'last tuesday'.

    Returns the start datetime (UTC).
    """
    spec = spec.strip().lower()

    # Named offsets
    if spec in ("today",):
        d = date.today()
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if spec in ("yesterday",):
        d = date.today() - timedelta(days=1)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    # "last <weekday>"
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, wd in enumerate(weekdays):
        if spec == f"last {wd}":
            today = date.today()
            days_back = (today.weekday() - i) % 7 or 7
            d = today - timedelta(days=days_back)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    # "Nd" / "Ndays" / "Nh" / "Nw"
    m = re.match(r"^(\d+)\s*(d|day|days|h|hour|hours|w|week|weeks)$", spec)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("h"):
            return _now() - timedelta(hours=n)
        if unit.startswith("w"):
            return _now() - timedelta(weeks=n)
        return _now() - timedelta(days=n)

    raise ValueError(f"Cannot parse time spec: {spec!r}")


def parse_window(
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Return (start, end) datetimes from user-facing specs.

    since:  "3d", "yesterday", "2026-04-01", "last tuesday"
    until:  "2026-04-07" or None (defaults to now)
    """
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    if since:
        # Try ISO date first
        try:
            d = date.fromisoformat(since)
            start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            start = _parse_relative(since)

    if until:
        try:
            d = date.fromisoformat(until)
            end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        except ValueError:
            end = _parse_relative(until)
    else:
        end = _now()

    return start, end


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# JSONL querying
# ---------------------------------------------------------------------------


def _query_jsonl(
    path: Path,
    ts_field: str,
    type_label: str,
    start: Optional[datetime],
    end: Optional[datetime],
    text_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return entries from a JSONL file within the time window."""
    results = []
    if not path.exists():
        return results

    text_lower = text_filter.lower() if text_filter else None

    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = entry.get(ts_field, "")
                dt = _parse_ts(ts_str)
                if dt is None:
                    continue
                if start and dt < start:
                    continue
                if end and dt > end:
                    continue

                # Optional text filter
                if text_lower:
                    entry_text = json.dumps(entry).lower()
                    if text_lower not in entry_text:
                        continue

                results.append({"_source": type_label, "_ts": dt.isoformat(), **entry})
    except OSError:
        pass

    return results


def _query_reflections(
    reflections_dir: Path,
    start: Optional[datetime],
    end: Optional[datetime],
    text_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return nightly reflection JSON files within the time window."""
    results = []
    if not reflections_dir.exists():
        return results

    text_lower = text_filter.lower() if text_filter else None

    for f in sorted(reflections_dir.glob("*.json"), reverse=True):
        try:
            d = date.fromisoformat(f.stem)
            dt = datetime(d.year, d.month, d.day, 0, 1, 0, tzinfo=timezone.utc)
        except ValueError:
            continue

        if start and dt < start:
            continue
        if end and dt > end:
            continue

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        if text_lower:
            if text_lower not in json.dumps(data).lower():
                continue

        results.append({"_source": "reflection", "_ts": dt.isoformat(), **data})

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TemporalQuery:
    """Query Cortex memory stores by time window."""

    def __init__(self, cortex_home: Path = CORTEX_HOME):
        self._home = cortex_home

    def query(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        text: Optional[str] = None,
        sources: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Return entries across all sources within the time window, sorted by recency.

        Args:
            since:   Start of window — "3d", "yesterday", "2026-04-01", "last tuesday"
            until:   End of window — ISO date or None (defaults to now)
            text:    Optional substring filter applied to full entry JSON
            sources: Restrict to subset — ["interaction", "reflection", "alert", "digest"]
            limit:   Max results to return
        """
        start, end = parse_window(since, until)
        all_sources = sources or ["interaction", "reflection", "alert", "digest"]
        results: List[Dict[str, Any]] = []

        source_map = {
            "interaction": (self._home / "interaction_queue.jsonl", "queued_at", "interaction"),
            "alert": (self._home / "alerts.jsonl", "timestamp", "alert"),
            "digest": (self._home / "conversation_digests.jsonl", "timestamp", "digest"),
        }

        for src_name in all_sources:
            if src_name == "reflection":
                results.extend(_query_reflections(self._home / "reflections", start, end, text))
            elif src_name in source_map:
                path, ts_field, label = source_map[src_name]
                results.extend(_query_jsonl(path, ts_field, label, start, end, text))

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda r: r.get("_ts", ""), reverse=True)
        return results[:limit]

    def summarise(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a summary dict suitable for CLI display."""
        results = self.query(since=since, until=until, text=text, limit=200)
        by_source: Dict[str, int] = {}
        for r in results:
            src = r.get("_source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1

        start, end = parse_window(since, until)
        return {
            "window_start": start.isoformat() if start else None,
            "window_end": end.isoformat() if end else None,
            "total": len(results),
            "by_source": by_source,
            "entries": results,
        }
