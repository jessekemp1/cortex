"""Cortex MCP handlers — endpoint logic callable without HTTP.

Each function here implements a former bridge endpoint's logic as a
stdlib-only call site. The HTTP route in api/ delegates to the function
here; the MCP tool in mcp_server.py also calls it directly, bypassing the
HTTP round-trip — so the memory loop keeps working when the bridge daemon
is down.

Pattern:
  - Pure stdlib imports at module top (no FastAPI, no heavy ML libs).
  - Each handler accepts plain Python kwargs (no Query() shims).
  - Each handler returns a plain dict matching the endpoint contract.
  - Exceptions propagate; callers decide whether to raise HTTPException
    (route) or wrap in an error envelope (MCP tool).

Crash-proof decision writes:
  record_learning_decision() appends directly to ~/.cortex/decisions.jsonl.
  If the primary append fails (permissions, transient FS error), the entry
  is spooled to ~/.cortex/spool/decision-<id>.json — one file per entry, so
  concurrent sessions never contend — and flushed opportunistically on the
  next successful record call or explicitly via `cortex doctor --fix`.

Paths resolve through state_paths.get_cortex_dir() at call time (honors
CORTEX_STATE_DIR), so tests can redirect the whole store to a tmp dir.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from state_paths import get_cortex_dir


# ─── Filesystem locations (call-time, CORTEX_STATE_DIR-aware) ──────────


def _decisions_file() -> Path:
    return get_cortex_dir() / "decisions.jsonl"


def _outcomes_file() -> Path:
    return get_cortex_dir() / "outcomes.jsonl"


def _plans_dir() -> Path:
    return get_cortex_dir() / "plans"


def _spool_dir() -> Path:
    return get_cortex_dir() / "spool"


# ─── Decision recording (crash-proof) ──────────────────────────────────


def _append_line(path: Path, entry: Dict[str, Any]) -> None:
    """Append one JSON line. Single-line O_APPEND writes are atomic in
    practice for the handful of local processes that share this file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def record_learning_decision(
    decision: str,
    context: str = "",
    alternatives: str = "",
    rationale: str = "",
    project: str = "",
    source: str = "mcp",
) -> Dict[str, Any]:
    """Record a learning-loop decision to ~/.cortex/decisions.jsonl.

    Canonical schema matches POST /decisions/learning (decision/context/
    alternatives/rationale/timestamp/source + decision_id). `project` is
    included only when non-empty (back-compat: older entries lack the key).

    Never loses a decision: on primary-append failure the entry lands in
    the spool instead and the response carries `"spooled": true`.
    """
    # Opportunistic flush of anything a previous failure left behind.
    try:
        flush_spool()
    except Exception:
        pass  # flushing must never block recording

    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    entry: Dict[str, Any] = {
        "decision_id": decision_id,
        "decision": decision,
        "context": context,
        "alternatives": alternatives,
        "rationale": rationale,
        "timestamp": datetime.now().isoformat(),
        "source": source,
    }
    if project:
        entry["project"] = project

    try:
        _append_line(_decisions_file(), entry)
        return {
            "recorded": True,
            "decision_id": decision_id,
            "timestamp": entry["timestamp"],
        }
    except Exception:
        spool_dir = _spool_dir()
        spool_dir.mkdir(parents=True, exist_ok=True)
        spool_path = spool_dir / f"decision-{decision_id}.json"
        spool_path.write_text(json.dumps(entry), encoding="utf-8")
        return {
            "recorded": True,
            "spooled": True,
            "decision_id": decision_id,
            "timestamp": entry["timestamp"],
        }


def spool_depth() -> int:
    """Number of decisions waiting in the spool."""
    spool = _spool_dir()
    if not spool.exists():
        return 0
    return sum(1 for _ in spool.glob("decision-*.json"))


def flush_spool() -> Dict[str, Any]:
    """Replay spooled decisions into decisions.jsonl.

    Dedup by decision_id (idempotent — a re-run after a partial flush skips
    entries that already landed). A spool file is deleted only after its
    line is durably appended (flush + fsync).
    """
    spool = _spool_dir()
    if not spool.exists():
        return {"flushed": 0, "skipped": 0, "remaining": 0}

    decisions_path = _decisions_file()
    existing_ids = set()
    if decisions_path.exists():
        for line in decisions_path.read_text(encoding="utf-8").splitlines():
            try:
                existing_ids.add(json.loads(line).get("decision_id"))
            except (json.JSONDecodeError, AttributeError):
                continue

    flushed = skipped = 0
    for spool_path in sorted(spool.glob("decision-*.json")):
        try:
            entry = json.loads(spool_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # unreadable spool entry: leave for inspection
        if entry.get("decision_id") in existing_ids:
            spool_path.unlink()  # already durable in decisions.jsonl
            skipped += 1
            continue
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        with open(decisions_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())
        existing_ids.add(entry.get("decision_id"))
        spool_path.unlink()
        flushed += 1

    return {"flushed": flushed, "skipped": skipped, "remaining": spool_depth()}


# ─── /projects ─────────────────────────────────────────────────────────


def compute_projects() -> List[Dict[str, Any]]:
    """List the user's projects (git repos under CORTEX_ROOT_DIR) with status.

    Mirrors GET /projects in api/bridge_endpoint.py: config.discover_projects
    + last-commit timestamp per repo.
    """
    import subprocess

    from config import discover_projects

    projects: List[Dict[str, Any]] = []
    for proj in discover_projects():
        project_path = Path(proj["path"])
        last_activity = datetime.now().isoformat()
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                last_activity = result.stdout.strip()
        except Exception:
            pass
        projects.append(
            {
                "name": proj["name"],
                "path": proj["rel"],
                "status": "healthy",
                "last_activity": last_activity,
            }
        )
    return projects


# ─── /plans/progress ───────────────────────────────────────────────────


def plans_progress() -> Dict[str, Any]:
    """Summarize all active plans in ~/.cortex/plans/."""
    plans_dir = _plans_dir()
    if not plans_dir.exists():
        return {"plans": [], "total": 0}

    summaries: List[Dict[str, Any]] = []
    for plan_path in sorted(plans_dir.glob("*.json")):
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items = plan.get("items", [])
        status_counts: Dict[str, int] = {}
        for item in items:
            s = item.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        summaries.append(
            {
                "plan_id": plan.get("plan_id"),
                "project": plan.get("project"),
                "title": plan.get("title"),
                "created_at": plan.get("created_at"),
                "item_count": len(items),
                "by_status": status_counts,
                "path": str(plan_path),
            }
        )
    return {"plans": summaries, "total": len(summaries)}


# ─── /plans/create ─────────────────────────────────────────────────────


def create_plan(project: str, title: Optional[str] = None) -> Dict[str, Any]:
    """Parse goals for `project` and write a plan JSON to ~/.cortex/plans/."""
    plans_dir = _plans_dir()
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import keeps mcp_handlers stdlib-only for the typical path; the
    # GoalParser dependency only loads when this handler is actually called.
    from goal_parser import GoalParser  # type: ignore

    goals_override = os.environ.get("CORTEX_GOALS_FILE")
    action_plan_path = Path(goals_override) if goals_override else None
    parser = GoalParser(action_plan_path=action_plan_path)
    all_goals = parser.parse()

    project_lower = project.lower()
    project_goals = [
        g for g in all_goals if not g.project or g.project.lower() == project_lower
    ]

    ts = int(time.time())
    plan_id = f"plan_{project}_{ts}"
    items = [
        {
            "id": g.id,
            "title": g.title,
            "priority": g.priority,
            "status": g.status,
            "actions": list(g.actions),
            "success_criteria": g.success_criteria,
            "blockers": list(g.blockers),
        }
        for g in project_goals
    ]
    plan = {
        "plan_id": plan_id,
        "project": project,
        "title": title or f"Plan for {project}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(parser.action_plan_path),
        "item_count": len(items),
        "items": items,
    }
    plan_path = plans_dir / f"{project}_{ts}.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return {"plan_id": plan_id, "path": str(plan_path), "item_count": len(items)}


# ─── /v2/outcomes ──────────────────────────────────────────────────────


def read_outcomes(project: str = "", limit: int = 20) -> Dict[str, Any]:
    """Read recorded outcomes from ~/.cortex/outcomes.jsonl.

    This is the real outcome store written by feedback.FeedbackLogger
    (OutcomeEntry schema: timestamp, recommendation_id, outcome, followed,
    confidence, context, ...). Filters by project (matched against the
    entry's `context.project`), returns the most recent `limit` entries
    newest-first.
    """
    outcomes_path = _outcomes_file()
    if not outcomes_path.exists():
        return {"outcomes": [], "total": 0}

    entries: List[Dict[str, Any]] = []
    for line in outcomes_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if project:
        proj_lower = project.lower()
        entries = [
            e
            for e in entries
            if isinstance(e.get("context"), dict)
            and str(e["context"].get("project", "")).lower() == proj_lower
        ]

    # Newest first by timestamp string (ISO-8601 sorts lexically).
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    total = len(entries)
    return {"outcomes": entries[: max(0, limit)], "total": total}
