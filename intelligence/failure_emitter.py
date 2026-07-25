"""
Failure Emitter — closes the audit-flagged learning-loop gap.

The 2026-04-19 Cortex audit observed: outcomes.jsonl shows 1320 success / 3
partial / 0 failed across 1323 entries. A logger that cannot emit failure is
not a learning signal. Every downstream claim (routing accuracy, confidence
calibration, anti-pattern surfacing) rests on a feedback signal that is
demonstrably broken.

This module scans the operational artifacts that already record failures and
turns them into structured `failed` entries on the outcome stream:

  1. Pytest's `.pytest_cache/v/cache/lastfailed` (test failures)
  2. `~/.cortex/restart_history.jsonl` (alert_monitor service restarts)
  3. `~/.cortex/metrics/scheduler_jobs.jsonl` (scheduler errors, last 5 min)
  4. `~/.cortex/alerts.jsonl` (alert_monitor critical alerts)

It is idempotent — each failure source carries a stable id and the emitter
deduplicates against an emitted-set file so it can run on a cron without
double-counting. Run it from a LaunchAgent or `cron` every 5 min.

Run standalone:  python -m intelligence.failure_emitter
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

CORTEX_DIR = Path(os.environ.get("CORTEX_HOME", str(Path.home() / ".cortex")))
EMITTED_LEDGER = CORTEX_DIR / "failure_emitter_ledger.jsonl"
DEFAULT_SCHEDULER_LOG = CORTEX_DIR / "metrics" / "scheduler_jobs.jsonl"
DEFAULT_RESTART_LOG = CORTEX_DIR / "restart_history.jsonl"
DEFAULT_ALERTS_LOG = CORTEX_DIR / "alerts.jsonl"
DEFAULT_PYTEST_CACHE = Path(".pytest_cache") / "v" / "cache" / "lastfailed"
DEFAULT_ORCHESTRATION_DB = CORTEX_DIR / "orchestration.db"
# Anomaly types that represent genuine execution/planning failures worth
# feeding the learning loop. Excludes context_switching_risk, which is a
# workload-shape heuristic already captured (and collapsed) via alerts.
_FAILURE_ANOMALY_TYPES = ("stuck_tasks", "batch_inefficiency", "planning_gap")


@dataclass(frozen=True)
class FailureSignal:
    """A normalized failure observed in an operational artifact."""

    source: str  # "pytest" | "restart" | "scheduler" | "alert"
    signal_id: str  # stable id for dedup (test nodeid, alert key, etc.)
    title: str
    detail: str
    observed_at: str  # ISO timestamp of the underlying event

    def recommendation_id(self) -> str:
        return f"failure:{self.source}:{self.signal_id}"


def collect_pytest_failures(cache_path: Path = DEFAULT_PYTEST_CACHE) -> List[FailureSignal]:
    """Read pytest's lastfailed cache and return one signal per failing nodeid."""
    if not cache_path.exists():
        return []
    try:
        data = json.loads(cache_path.read_text())
    except json.JSONDecodeError as exc:
        logger.warning("pytest lastfailed unreadable: %s", exc)
        return []
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc).isoformat()
    out: List[FailureSignal] = []
    for nodeid in data.keys():
        out.append(
            FailureSignal(
                source="pytest",
                signal_id=nodeid,
                title=f"pytest failure: {nodeid}",
                detail="pytest lastfailed cache",
                observed_at=mtime,
            )
        )
    return out


def collect_restart_failures(
    log_path: Path = DEFAULT_RESTART_LOG, lookback_minutes: int = 60
) -> List[FailureSignal]:
    """One signal per service restart in the last `lookback_minutes`.

    A restart is a confessed failure: the service died and alert_monitor
    auto-restarted it. The audit found 99.77% success rate while
    restart_history was actively being written — that's the gap.
    """
    if not log_path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    out: List[FailureSignal] = []
    for line in _read_jsonl(log_path):
        ts_raw = line.get("timestamp") or line.get("ts")
        if not _within_window(ts_raw, cutoff):
            continue
        service = line.get("service", "unknown")
        out.append(
            FailureSignal(
                source="restart",
                signal_id=f"{service}:{ts_raw}",
                title=f"service restart: {service}",
                detail=line.get("reason", "no reason recorded"),
                observed_at=ts_raw or "",
            )
        )
    return out


def collect_scheduler_failures(
    log_path: Path = DEFAULT_SCHEDULER_LOG, lookback_minutes: int = 60
) -> List[FailureSignal]:
    """One signal per scheduler job error in the lookback window."""
    if not log_path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    out: List[FailureSignal] = []
    for line in _read_jsonl(log_path):
        if line.get("status") not in {"error", "failed"} and not line.get("error"):
            continue
        ts_raw = line.get("timestamp") or line.get("ts")
        if not _within_window(ts_raw, cutoff):
            continue
        job = line.get("job", line.get("name", "unknown"))
        out.append(
            FailureSignal(
                source="scheduler",
                signal_id=f"{job}:{ts_raw}",
                title=f"scheduler job error: {job}",
                detail=str(line.get("error", line.get("message", "")))[:500],
                observed_at=ts_raw or "",
            )
        )
    return out


def collect_alert_failures(
    log_path: Path = DEFAULT_ALERTS_LOG, lookback_minutes: int = 60
) -> List[FailureSignal]:
    """One signal per critical alert in the lookback window."""
    if not log_path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    out: List[FailureSignal] = []
    for line in _read_jsonl(log_path):
        severity = (line.get("severity") or line.get("level") or "").lower()
        if severity not in {"critical", "error", "high"}:
            continue
        ts_raw = line.get("timestamp") or line.get("ts")
        if not _within_window(ts_raw, cutoff):
            continue
        key = line.get("key") or line.get("service") or "unknown"
        out.append(
            FailureSignal(
                source="alert",
                signal_id=f"{key}:{ts_raw}",
                title=f"alert: {line.get('title', key)}",
                detail=str(line.get("message", ""))[:500],
                observed_at=ts_raw or "",
            )
        )
    return out


def _collapse_repeats(signals: List[FailureSignal]) -> List[FailureSignal]:
    """Collapse repeated failures of the same identity into one signal.

    The raw collectors key each occurrence by timestamp, so a service that
    restarts 50 times or an alert that fires 79 times produces 50/79 near-
    identical signals. Emitting those verbatim floods the outcome stream with
    volume, not signal — the exact failure the 2026-04-19 audit warned about
    ("the fix produced volume, not signal fidelity"). Mirroring the zombie-
    alert fix, we collapse by a stable identity (source + failure family,
    ignoring the timestamp) and keep the most recent occurrence, recording how
    many times it happened in the title/detail so calibration sees one weighted
    failure rather than N duplicates.
    """
    groups: dict[str, List[FailureSignal]] = {}
    order: List[str] = []
    for sig in signals:
        # pytest nodeids are already unique per test; keep them as-is. For the
        # timestamped sources (restart/alert/scheduler) the title captures the
        # failure identity (service name, alert text, job) without the varying
        # timestamp — so grouping by (source, title) folds repeats together.
        # We deliberately do NOT parse the timestamp out of signal_id: ISO
        # timestamps contain their own colons, which made naive splitting fail.
        if sig.source == "pytest":
            family = sig.recommendation_id()
        else:
            family = f"{sig.source}:{sig.title}"
        if family not in groups:
            groups[family] = []
            order.append(family)
        groups[family].append(sig)

    collapsed: List[FailureSignal] = []
    for family in order:
        members = groups[family]
        latest = max(members, key=lambda s: s.observed_at or "")
        count = len(members)
        if count == 1:
            collapsed.append(latest)
            continue
        collapsed.append(
            FailureSignal(
                source=latest.source,
                # Stable id across runs so the ledger dedups the collapsed
                # signal by identity, not by the latest timestamp.
                signal_id=family,
                title=f"{latest.title} (x{count} in window)",
                detail=f"{count} occurrences; latest: {latest.detail}"[:500],
                observed_at=latest.observed_at,
            )
        )
    return collapsed


def collect_anomaly_failures(
    db_path: Path = DEFAULT_ORCHESTRATION_DB, lookback_minutes: int = 60
) -> List[FailureSignal]:
    """One signal per orchestration anomaly (execution/planning failures).

    Reads the orchestration.db ``anomalies`` table for CRITICAL/WARNING rows of
    genuine failure types (stuck tasks, batch inefficiency, planning gaps).
    These are behavioural failures the log-based collectors never see — a task
    stuck in a phase or a batch running inefficiently is a real negative
    outcome. Downstream ``_collapse_repeats`` folds the many rows per type into
    a small number of weighted signals.
    """
    if not db_path.exists():
        return []
    import sqlite3

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    out: List[FailureSignal] = []
    placeholders = ",".join("?" for _ in _FAILURE_ANOMALY_TYPES)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                f"SELECT anomaly_id, anomaly_type, severity, detected_at, title, description "
                f"FROM anomalies WHERE anomaly_type IN ({placeholders}) "
                f"AND severity IN ('CRITICAL','WARNING')",
                _FAILURE_ANOMALY_TYPES,
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("cannot read anomalies from %s: %s", db_path, exc)
        return []

    for row in rows:
        ts_raw = row["detected_at"]
        if not _within_window(ts_raw, cutoff):
            continue
        out.append(
            FailureSignal(
                source="anomaly",
                signal_id=f"{row['anomaly_type']}:{row['anomaly_id']}",
                title=f"anomaly[{row['severity']}]: {row['title']}",
                detail=str(row["description"] or "")[:500],
                observed_at=ts_raw or "",
            )
        )
    return out


def collect_all(lookback_minutes: int = 60, collapse: bool = True) -> List[FailureSignal]:
    """Collect failure signals from every known source.

    With ``collapse=True`` (default) repeated failures of the same identity are
    folded into one weighted signal so the outcome stream captures failure
    *signal* rather than duplicate *volume*.
    """
    raw = (
        collect_pytest_failures()
        + collect_restart_failures(lookback_minutes=lookback_minutes)
        + collect_scheduler_failures(lookback_minutes=lookback_minutes)
        + collect_alert_failures(lookback_minutes=lookback_minutes)
        + collect_anomaly_failures(lookback_minutes=lookback_minutes)
    )
    return _collapse_repeats(raw) if collapse else raw


def emit(signals: Iterable[FailureSignal], ledger_path: Path = EMITTED_LEDGER) -> int:
    """Emit each new signal as a `failed` outcome and record it in the ledger.

    Returns the number of newly emitted signals (already-emitted ones skipped).
    """
    seen = _load_ledger(ledger_path)
    emitted = 0
    try:
        from feedback import FeedbackLogger  # type: ignore
    except ImportError:
        try:
            from cortex.feedback import FeedbackLogger  # type: ignore
        except ImportError as exc:
            logger.error("cannot import FeedbackLogger: %s", exc)
            return 0

    fl = FeedbackLogger()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a") as ledger:
        for sig in signals:
            rec_id = sig.recommendation_id()
            if rec_id in seen:
                continue
            try:
                fl.log_outcome(
                    recommendation_id=rec_id,
                    recommendation_title=sig.title,
                    recommendation_type=f"failure:{sig.source}",
                    priority="A",
                    confidence=1.0,
                    followed=True,
                    outcome="failed",
                    notes=sig.detail[:500],
                    context={
                        "source": sig.source,
                        "signal_id": sig.signal_id,
                        "observed_at": sig.observed_at,
                    },
                    source="auto",  # machine-derived failure signal
                )
            except Exception as exc:
                logger.warning("emit failed for %s: %s", rec_id, exc)
                continue
            ledger.write(
                json.dumps({"id": rec_id, "emitted_at": datetime.now(timezone.utc).isoformat()})
                + "\n"
            )
            emitted += 1
    return emitted


def run_once(lookback_minutes: int = 60) -> dict:
    """One-shot collection + emission. Designed to be called from cron."""
    signals = collect_all(lookback_minutes=lookback_minutes)
    new_count = emit(signals)
    return {
        "total_collected": len(signals),
        "newly_emitted": new_count,
        "by_source": _group_by_source(signals),
    }


# --- private helpers ---


def _read_jsonl(path: Path) -> Iterable[dict]:
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        logger.warning("cannot read %s: %s", path, exc)


def _within_window(ts_raw: Optional[str], cutoff: datetime) -> bool:
    if not ts_raw:
        return False
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def _load_ledger(path: Path) -> set:
    if not path.exists():
        return set()
    seen = set()
    for entry in _read_jsonl(path):
        rid = entry.get("id")
        if rid:
            seen.add(rid)
    return seen


def _group_by_source(signals: Iterable[FailureSignal]) -> dict:
    counts: dict = {}
    for s in signals:
        counts[s.source] = counts.get(s.source, 0) + 1
    return counts


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Emit failure outcomes from operational artifacts")
    p.add_argument("--lookback-minutes", type=int, default=60)
    p.add_argument("--dry-run", action="store_true", help="Collect without emitting")
    args = p.parse_args()

    if args.dry_run:
        sigs = collect_all(lookback_minutes=args.lookback_minutes)
        print(json.dumps({"collected": len(sigs), "by_source": _group_by_source(sigs)}, indent=2))
    else:
        result = run_once(lookback_minutes=args.lookback_minutes)
        print(json.dumps(result, indent=2))
