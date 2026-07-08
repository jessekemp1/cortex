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


# ─── Project routing (single source of truth; api/routes/intelligence.py
#     imports these back) ────────────────────────────────────────────────


def _workspace_root() -> Path:
    """Resolve the projects workspace root from CORTEX_ROOT_DIR.

    Aligns with config.workspace_root() (the single source of truth for the
    projects root). Falls back to ~/Dev only if config can't be imported.
    """
    try:
        from config import workspace_root

        return workspace_root()
    except Exception:
        return Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.home() / "Dev"))).expanduser()


def _project_dirs() -> Dict[str, str]:
    """Map discovered project name -> path (relative to the workspace root).

    Built at call time from config.discover_projects() so git context comes
    from the user's repos under CORTEX_ROOT_DIR, never a static author map.
    """
    try:
        from config import discover_projects

        return {p["name"]: p["rel"] for p in discover_projects(_workspace_root())}
    except Exception:
        return {}


def default_project() -> str:
    """The current project when none is specified: the workspace root's name."""
    root = _workspace_root()
    return root.name or "unknown"


def auto_detect_project(question: str) -> str:
    """Choose the most-likely discovered project from question keywords.

    Keywords default to the project's own name token (lowercased). Falls back
    to the current default project (workspace root name) when nothing matches.
    """
    q_lower = question.lower()
    project_names = list(_project_dirs().keys())
    if not project_names:
        return default_project()
    scores = {name: (1 if name.lower() in q_lower else 0) for name in project_names}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else default_project()


def normalize_recommendations(
    recommendations: Dict[str, Any],
    project: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Normalize report-style recommendation payloads into a flat list.

    Mirrors GET /intelligence/recommendations: when the bridge returns the
    report shape (next_action / priority_projects / risk_alerts), flatten it
    into `recommendations`; otherwise filter/trim the list the bridge sent.
    Mutates and returns the passed dict (parity with the route).
    """
    if project and "recommendations" in recommendations:
        filtered = [
            r for r in recommendations["recommendations"] if r.get("project") == project
        ]
        recommendations["recommendations"] = filtered[:limit]
    elif "recommendations" in recommendations:
        recommendations["recommendations"] = recommendations["recommendations"][:limit]
    else:
        normalized: List[Dict[str, Any]] = []
        # Fallback project when a report item omits one: the query filter if
        # given, else the discovered default project — never a literal "cortex".
        default_proj = project or default_project()

        next_action = recommendations.get("next_action")
        if isinstance(next_action, dict) and next_action.get("action"):
            normalized.append(
                {
                    "project": next_action.get("project", default_proj),
                    "priority": next_action.get("priority", "MEDIUM"),
                    "title": next_action.get("action"),
                    "type": next_action.get("type", "next_action"),
                }
            )

        for item in recommendations.get("priority_projects", []) or []:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "project": item.get("project", default_proj),
                        "priority": item.get("priority", "MEDIUM"),
                        "title": item.get("reason", "Priority project requires attention"),
                        "type": "priority_project",
                    }
                )

        for alert in recommendations.get("risk_alerts", []) or []:
            if isinstance(alert, dict):
                normalized.append(
                    {
                        "project": alert.get("project", default_proj),
                        "priority": alert.get("severity", "MEDIUM"),
                        "title": alert.get("message", "Risk alert detected"),
                        "type": "risk_alert",
                    }
                )

        recommendations["recommendations"] = normalized[:limit]

    return recommendations


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
