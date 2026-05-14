#!/usr/bin/env python3
"""
Session Delta — tracks session-to-session changes and projects completion dates.

Captures a snapshot of current system state (EMOS, batch, git, tests, bridge),
diffs it against the previous snapshot, and projects when milestones will be reached.

Usage:
    from session_delta import get_session_delta_report
    print(get_session_delta_report())
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SNAPSHOT_DIR = Path.home() / ".cortex" / "snapshots"
MONOREPO_ROOT = Path(__file__).resolve().parent.parent
GOALS_PATH = MONOREPO_ROOT / "GOALS.md"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SessionSnapshot:
    timestamp: str  # ISO format
    session_id: str  # random short id
    emos: dict  # {"ecmwf": 473, "gfs": 416, "hrrr": 2100, "ensemble": 44}
    batch: dict  # {"failed": 19012, "pending": 0, "completed": 847}
    goals_checksum: str  # SHA256 of GOALS.md immediate actions section
    uncommitted_files: list  # list of file paths from git status
    last_commit: str  # commit hash
    test_counts: dict  # {"cortex": 1359, "vortex": 2126, ...}
    bridge_status: str  # "healthy", "degraded", "down"


@dataclass
class SessionDelta:
    hours_since: float  # hours since last snapshot
    emos_delta: dict  # {"ecmwf": +31, ...}
    batch_delta: dict  # {"failed": +0, "completed": +12, ...}
    goals_changed: bool  # True if checksum differs
    new_commits: int  # commits since last snapshot's commit hash
    new_commit_messages: list  # oneline messages
    files_changed: bool  # True if uncommitted files list differs
    bridge_transition: Optional[str]  # "degraded→healthy" or None if same
    test_delta: dict  # {"cortex": +5, ...}


@dataclass
class Projection:
    metric: str  # "emos_ecmwf", "emos_gfs", etc.
    current: int
    target: int
    rate_per_day: float
    estimated_date: Optional[str]  # ISO date or None
    status: str  # "on_track", "stalled", "ready", "insufficient_data"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 5, cwd: Path = None) -> str:
    """Run a subprocess and return stripped stdout, empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd or MONOREPO_ROOT),
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _curl_json(url: str, timeout: int = 2) -> dict:
    """Fetch a URL with curl and parse JSON. Returns empty dict on any failure."""
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url],
            capture_output=True,
            text=True,
            timeout=timeout + 1,
        ).stdout.strip()
        if out:
            return json.loads(out)
    except Exception:
        pass
    return {}


def _goals_checksum() -> str:
    """Return SHA256 of the immediate-actions section of GOALS.md."""
    try:
        text = GOALS_PATH.read_text()
        section_lines = []
        in_section = False
        for line in text.splitlines():
            if any(h in line for h in ("### This Week", "## Immediate Actions")):
                in_section = True
            elif line.startswith("## ") and in_section:
                break
            if in_section:
                section_lines.append(line)
        content = "\n".join(section_lines)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except Exception:
        return ""


def _collect_emos() -> dict:
    """Try to get EMOS counts via direct health_probe call (Phase 5: no HTTP)."""
    try:
        import health_probe

        services = health_probe.compute_service_health()
    except Exception:
        return {}
    emos = services.get("emos", {}).get("pairs", {}) if isinstance(services.get("emos"), dict) else {}
    result = {}
    for model in ("ecmwf", "gfs", "hrrr", "ensemble"):
        val = emos.get(model)
        if val is not None:
            try:
                result[model] = int(val)
            except (TypeError, ValueError):
                pass
    return result


def _collect_batch() -> dict:
    """Try to read batch state from ~/.cortex/batch/."""
    batch_dir = Path.home() / ".cortex" / "batch"
    if not batch_dir.exists():
        return {}
    result: dict[str, int] = {}
    try:
        for f in batch_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                status = str(data.get("status", "unknown"))
                result[status] = result.get(status, 0) + 1
            except Exception:
                pass
    except Exception:
        return {}
    return result


def _collect_git_status() -> list[str]:
    """Return list of file paths from git status --short."""
    output = _run(["git", "status", "--short"])
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _collect_last_commit() -> str:
    return _run(["git", "log", "-1", "--format=%H"]) or ""


def _collect_bridge_status() -> str:
    """Return 'healthy', 'degraded', or 'down' for the bridge.

    Phase 5: replaced HTTP probe with cheap import-spec check. If
    bridge.py is on PYTHONPATH the bridge is structurally available
    ("healthy"); else "down". Distinct ("degraded") states no longer
    apply now that there's no separate process to fail.
    """
    import importlib.util

    spec = importlib.util.find_spec("bridge")
    return "healthy" if spec is not None else "down"


# ---------------------------------------------------------------------------
# Part 1: Snapshot capture + persistence
# ---------------------------------------------------------------------------


def capture_snapshot(root_dir: Path = None, snapshot_dir: Path = None) -> SessionSnapshot:
    """
    Collect current system state and save to snapshot_dir.

    Never raises — every sub-collection is wrapped to return safe defaults.
    """
    snap_dir = snapshot_dir or SNAPSHOT_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()
    session_id = uuid.uuid4().hex[:8]

    emos = _collect_emos()
    batch = _collect_batch()
    goals_checksum = _goals_checksum()
    uncommitted_files = _collect_git_status()
    last_commit = _collect_last_commit()
    bridge_status = _collect_bridge_status()
    test_counts: dict = {}  # expensive to run; start empty, can be populated externally

    snapshot = SessionSnapshot(
        timestamp=ts,
        session_id=session_id,
        emos=emos,
        batch=batch,
        goals_checksum=goals_checksum,
        uncommitted_files=uncommitted_files,
        last_commit=last_commit,
        test_counts=test_counts,
        bridge_status=bridge_status,
    )

    # Persist
    filename = f"{ts.replace(':', '-').replace('+', 'Z')}_{session_id}.json"
    snap_path = snap_dir / filename
    snap_path.write_text(json.dumps(asdict(snapshot), indent=2))

    return snapshot


def _load_snapshot_from_file(path: Path) -> Optional[SessionSnapshot]:
    """Deserialize a snapshot JSON file. Returns None on any error."""
    try:
        data = json.loads(path.read_text())
        return SessionSnapshot(**data)
    except Exception:
        return None


def load_latest_snapshot(snapshot_dir: Path = None) -> Optional[SessionSnapshot]:
    """Find and return the most recent snapshot (by filename sort), or None."""
    snap_dir = snapshot_dir or SNAPSHOT_DIR
    if not snap_dir.exists():
        return None
    files = sorted(snap_dir.glob("*.json"), reverse=True)
    for f in files:
        snap = _load_snapshot_from_file(f)
        if snap is not None:
            return snap
    return None


def load_snapshot_history(days: int = 7, snapshot_dir: Path = None) -> list[SessionSnapshot]:
    """Return all snapshots from the last N days, sorted oldest-first."""
    snap_dir = snapshot_dir or SNAPSHOT_DIR
    if not snap_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snapshots = []
    for f in snap_dir.glob("*.json"):
        snap = _load_snapshot_from_file(f)
        if snap is None:
            continue
        try:
            ts = datetime.fromisoformat(snap.timestamp)
            if ts >= cutoff:
                snapshots.append(snap)
        except Exception:
            continue
    snapshots.sort(key=lambda s: s.timestamp)
    return snapshots


# ---------------------------------------------------------------------------
# Part 2: Delta computation
# ---------------------------------------------------------------------------


def _git_commits_between(old_hash: str, new_hash: str) -> tuple[int, list[str]]:
    """Return (count, [oneline messages]) for commits after old_hash up to new_hash."""
    if not old_hash or not new_hash or old_hash == new_hash:
        return 0, []
    try:
        out = _run(["git", "log", f"{old_hash}..{new_hash}", "--oneline"])
        if not out:
            return 0, []
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return len(lines), lines
    except Exception:
        return 0, []


def compute_delta(current: SessionSnapshot, previous: SessionSnapshot) -> SessionDelta:
    """Diff two snapshots into a SessionDelta."""
    try:
        ts_current = datetime.fromisoformat(current.timestamp)
        ts_previous = datetime.fromisoformat(previous.timestamp)
        hours_since = (ts_current - ts_previous).total_seconds() / 3600
    except Exception:
        hours_since = 0.0

    # EMOS delta
    emos_delta: dict[str, Optional[int]] = {}
    all_emos_keys = set(current.emos) | set(previous.emos)
    for k in all_emos_keys:
        if k in current.emos and k in previous.emos:
            emos_delta[k] = current.emos[k] - previous.emos[k]
        else:
            emos_delta[k] = None  # no previous data

    # Batch delta
    batch_delta: dict[str, Optional[int]] = {}
    all_batch_keys = set(current.batch) | set(previous.batch)
    for k in all_batch_keys:
        if k in current.batch and k in previous.batch:
            batch_delta[k] = current.batch[k] - previous.batch[k]
        else:
            batch_delta[k] = None

    # Goals
    goals_changed = current.goals_checksum != previous.goals_checksum

    # Git commits
    new_commits, new_commit_messages = _git_commits_between(
        previous.last_commit, current.last_commit
    )

    # Files changed
    files_changed = sorted(current.uncommitted_files) != sorted(previous.uncommitted_files)

    # Bridge transition
    bridge_transition: Optional[str] = None
    if current.bridge_status != previous.bridge_status:
        bridge_transition = f"{previous.bridge_status}→{current.bridge_status}"

    # Test delta
    test_delta: dict[str, Optional[int]] = {}
    all_test_keys = set(current.test_counts) | set(previous.test_counts)
    for k in all_test_keys:
        if k in current.test_counts and k in previous.test_counts:
            test_delta[k] = current.test_counts[k] - previous.test_counts[k]
        else:
            test_delta[k] = None

    return SessionDelta(
        hours_since=hours_since,
        emos_delta=emos_delta,
        batch_delta=batch_delta,
        goals_changed=goals_changed,
        new_commits=new_commits,
        new_commit_messages=new_commit_messages,
        files_changed=files_changed,
        bridge_transition=bridge_transition,
        test_delta=test_delta,
    )


def _fmt_hours(h: float) -> str:
    if h < 1:
        return f"{int(h * 60)}m"
    if h < 24:
        return f"{h:.1f}h"
    return f"{h / 24:.1f}d"


def format_delta(delta: SessionDelta, use_color: bool = True) -> str:
    """Produce a human-readable delta report."""
    lines = []

    # Check if anything actually changed
    any_change = (
        any(v != 0 for v in delta.emos_delta.values() if v is not None)
        or any(v != 0 for v in delta.batch_delta.values() if v is not None)
        or delta.goals_changed
        or delta.new_commits > 0
        or delta.files_changed
        or delta.bridge_transition is not None
        or any(v != 0 for v in delta.test_delta.values() if v is not None)
    )

    ago = _fmt_hours(delta.hours_since)

    if not any_change:
        return f"No changes since last session ({ago} ago)."

    lines.append(f"Since last session ({ago} ago):")

    # EMOS
    if delta.emos_delta:
        emos_parts = []
        for model, diff in sorted(delta.emos_delta.items()):
            if diff is None:
                continue
            sign = "+" if diff >= 0 else ""
            emos_parts.append(f"{model.upper()} {sign}{diff}")
        if emos_parts:
            lines.append(f"  EMOS: {', '.join(emos_parts)}")

    # Batch
    if delta.batch_delta:
        batch_parts = []
        for status, diff in sorted(delta.batch_delta.items()):
            if diff is None or diff == 0:
                continue
            sign = "+" if diff >= 0 else ""
            batch_parts.append(f"{status} {sign}{diff}")
        if batch_parts:
            lines.append(f"  Batch: {', '.join(batch_parts)}")
        else:
            # check if anything in batch at all
            if delta.batch_delta:
                lines.append("  Batch: no change")

    # Commits
    if delta.new_commits > 0:
        msgs = delta.new_commit_messages[:3]
        msg_str = ", ".join(f'"{m}"' for m in msgs)
        lines.append(f"  New commits: {delta.new_commits} ({msg_str})")

    # Goals
    if delta.goals_changed:
        lines.append("  GOALS.md: changed")

    # Bridge
    if delta.bridge_transition:
        lines.append(f"  Bridge: {delta.bridge_transition}")

    # Tests
    if delta.test_delta:
        test_parts = []
        for proj, diff in sorted(delta.test_delta.items()):
            if diff is None or diff == 0:
                continue
            sign = "+" if diff >= 0 else ""
            test_parts.append(f"{proj} {sign}{diff}")
        if test_parts:
            lines.append(f"  Tests: {', '.join(test_parts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part 3: Trend projections
# ---------------------------------------------------------------------------


def project_metric(
    metric_name: str,
    current: int,
    target: int,
    history: list[tuple[str, int]],
) -> Projection:
    """
    Project when a metric will reach target, based on historical timestamps+values.

    history: list of (iso_timestamp, value) sorted oldest-first.
    """
    if current >= target:
        return Projection(
            metric=metric_name,
            current=current,
            target=target,
            rate_per_day=0.0,
            estimated_date=None,
            status="ready",
        )

    if len(history) < 2:
        return Projection(
            metric=metric_name,
            current=current,
            target=target,
            rate_per_day=0.0,
            estimated_date=None,
            status="insufficient_data",
        )

    # Compute rate from first to last point
    try:
        ts_first = datetime.fromisoformat(history[0][0])
        ts_last = datetime.fromisoformat(history[-1][0])
        val_first = history[0][1]
        val_last = history[-1][1]

        days_span = (ts_last - ts_first).total_seconds() / 86400
        if days_span <= 0:
            return Projection(
                metric=metric_name,
                current=current,
                target=target,
                rate_per_day=0.0,
                estimated_date=None,
                status="insufficient_data",
            )

        rate_per_day = (val_last - val_first) / days_span
    except Exception:
        return Projection(
            metric=metric_name,
            current=current,
            target=target,
            rate_per_day=0.0,
            estimated_date=None,
            status="insufficient_data",
        )

    if rate_per_day <= 0:
        return Projection(
            metric=metric_name,
            current=current,
            target=target,
            rate_per_day=rate_per_day,
            estimated_date=None,
            status="stalled",
        )

    days_remaining = (target - current) / rate_per_day
    estimated_date = (date.today() + timedelta(days=days_remaining)).isoformat()

    return Projection(
        metric=metric_name,
        current=current,
        target=target,
        rate_per_day=rate_per_day,
        estimated_date=estimated_date,
        status="on_track",
    )


def project_emos(history: list[SessionSnapshot], target: int = 2000) -> list[Projection]:
    """Compute EMOS projections for all models from snapshot history."""
    models = ["ecmwf", "gfs", "hrrr", "ensemble"]
    projections = []
    for model in models:
        time_series = []
        for snap in history:
            val = snap.emos.get(model)
            if val is not None:
                time_series.append((snap.timestamp, int(val)))

        current_val = time_series[-1][1] if time_series else 0
        proj = project_metric(f"emos_{model}", current_val, target, time_series)
        projections.append(proj)
    return projections


def format_projections(projections: list[Projection], use_color: bool = True) -> str:
    """Format EMOS projections as a compact multi-line string."""
    if not projections:
        return ""

    lines = ["EMOS Projections:"]
    for p in projections:
        model = p.metric.replace("emos_", "").upper()
        pct = int(p.current / p.target * 100) if p.target > 0 else 0

        if p.status == "ready":
            lines.append(f"  {model}: READY ({p.current:,} pairs)")
        elif p.status == "on_track":
            rate = f"+{p.rate_per_day:.0f}/day"
            lines.append(f"  {model}: {pct}% -> est. {p.estimated_date} ({rate})")
        elif p.status == "stalled":
            lines.append(f"  {model}: {pct}% STALLED ({p.current:,} pairs, no recent growth)")
        else:
            # insufficient_data
            lines.append(f"  {model}: {p.current:,} pairs (insufficient history to project)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def get_session_delta_report(
    root_dir: Path = None,
    snapshot_dir: Path = None,
    emos_target: int = 2000,
) -> str:
    """
    One-call function: capture snapshot, compute delta, compute projections, return report.

    Never raises — returns a graceful message on any failure.
    """
    try:
        snap_dir = snapshot_dir or SNAPSHOT_DIR

        # 1. Load previous snapshot (before we overwrite with current)
        previous = load_latest_snapshot(snapshot_dir=snap_dir)

        # 2. Capture current snapshot (saves it too)
        current = capture_snapshot(root_dir=root_dir, snapshot_dir=snap_dir)

        parts = []

        # 3. Compute delta if we have a previous
        if previous is not None:
            delta = compute_delta(current, previous)
            parts.append(format_delta(delta))

        # 4. Compute EMOS projections from history
        history = load_snapshot_history(days=7, snapshot_dir=snap_dir)
        if history:
            projections = project_emos(history, target=emos_target)
            proj_str = format_projections(projections)
            if proj_str:
                parts.append(proj_str)

        if not parts:
            return "First session — no previous snapshot to diff against."

        return "\n\n".join(parts)

    except Exception as e:
        return f"Session delta unavailable: {e}"
