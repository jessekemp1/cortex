"""
Cortex MCP handlers — endpoint logic callable without HTTP.

Phase 5 of the slim-down: each function here implements a former bridge
endpoint's read path as a stdlib-only call site. The HTTP route in
api/bridge_endpoint.py delegates to the function here; the MCP tool in
mcp_server.py also calls it directly, bypassing the HTTP round-trip.

Pattern:
  - Pure stdlib imports at module top (no FastAPI, no heavy ML libs).
  - Each handler accepts plain Python kwargs (no Query() shims).
  - Each handler returns a plain dict matching the endpoint contract.
  - Exceptions propagate; callers decide whether to raise HTTPException
    (route) or wrap in an error envelope (MCP tool).

When the eventual sibling-repo split lands, this module moves with the
core bundle; the bridge_endpoint.py shim is the only thing that knows
about HTTP.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Filesystem locations (kept in sync with api/bridge_endpoint.py) ───

import os

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
TASKBOARD_DIR = Path.home() / ".cortex" / "taskboard"
TASKBOARD_FILE = TASKBOARD_DIR / "tasks.json"
PLANS_DIR = Path.home() / ".cortex" / "plans"
DECISIONS_FILE = Path.home() / ".cortex" / "decisions.jsonl"
CONDUCTOR_HISTORY_FILE = Path.home() / ".cortex" / "conductor" / "prompt_history.jsonl"

WORKSPACE = Path.home() / "Dev"
NEXT_SESSION_FILES = {
    "cortex": WORKSPACE / "cortex" / ".next_session.md",
    "vortex": WORKSPACE / "Vortex" / "backend" / ".next_session.md",
    "alpha_arena": WORKSPACE / "alpha_arena" / ".next_session.md",
}

# Subset of CONDUCTOR_PROJECTS needed for compose. Full list lives in
# api/bridge_endpoint.py — keep these two in sync if either changes.
CONDUCTOR_PROJECTS = [
    {"id": "vortex-backend", "name": "Vortex Backend", "path": "Vortex/backend"},
    {"id": "vortex-frontend", "name": "Vortex Frontend", "path": "Vortex/frontend"},
    {"id": "cortex", "name": "Cortex", "path": "cortex"},
    {"id": "alpha_arena", "name": "Alpha Arena", "path": "alpha_arena"},
    {"id": "pupil", "name": "Pupil", "path": "pupil"},
]


# ─── /projects ─────────────────────────────────────────────────────────


def compute_projects(workspace: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Scan the workspace for known project directories.

    Mirrors api/bridge_endpoint.py:list_projects but as a plain function.
    """
    if workspace is None:
        workspace = Path.home() / "Dev"

    project_defs = [
        ("Vortex/backend", "Vortex Backend", "Vortex/backend/tests"),
        ("Vortex/frontend", "Vortex Frontend", "Vortex/frontend/src"),
        ("cortex", "Cortex", "cortex/tests"),
        ("alpha_arena", "Alpha Arena", "alpha_arena/tests"),
        ("pupil", "Pupil", "pupil/tests"),
    ]

    projects: List[Dict[str, Any]] = []
    for dir_name, display_name, _test_dir in project_defs:
        project_path = workspace / dir_name
        if not project_path.exists():
            continue

        last_activity = datetime.now().isoformat()
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", "--", dir_name],
                cwd=str(workspace),
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
                "name": display_name,
                "path": dir_name,
                "status": "healthy",
                "last_activity": last_activity,
            }
        )
    return projects


# ─── /sessions ─────────────────────────────────────────────────────────


def scan_sessions(active_only: bool = False, limit: int = 20) -> Dict[str, Any]:
    """Scan Claude Code session JSONL files for real-time visibility.

    State derivation:
      - ACTIVE  : last event < 60s
      - WAITING : last event type == 'user' and age < 60s
      - IDLE    : last event age 60s-300s
      - STALE   : last event age > 300s
    """
    sessions: List[Dict[str, Any]] = []
    now = time.time()

    if not CLAUDE_PROJECTS_DIR.exists():
        return {"sessions": [], "total": 0, "active_count": 0}

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        project_name = re.sub(r"^-Users-[^-]+-", "", project_dir.name).replace("-", "/")

        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                mtime = jsonl_file.stat().st_mtime
                age_seconds = now - mtime
                content = jsonl_file.read_bytes()
                lines = content.strip().split(b"\n")
                if not lines:
                    continue

                last_event: Dict[str, Any] = {}
                first_event: Dict[str, Any] = {}
                event_count = len(lines)

                try:
                    last_event = json.loads(lines[-1])
                except (ValueError, json.JSONDecodeError):
                    pass
                try:
                    first_event = json.loads(lines[0])
                except (ValueError, json.JSONDecodeError):
                    pass

                last_type = last_event.get("type", "")
                if age_seconds < 60:
                    status = "WAITING" if last_type == "user" else "ACTIVE"
                elif age_seconds < 300:
                    status = "IDLE"
                else:
                    status = "STALE"

                if active_only and status == "STALE":
                    continue

                sessions.append(
                    {
                        "id": jsonl_file.stem,
                        "project": project_name,
                        "status": status,
                        "git_branch": last_event.get("gitBranch", ""),
                        "last_event_type": last_type,
                        "last_event_age_seconds": round(age_seconds, 1),
                        "started_at": first_event.get("timestamp", ""),
                        "last_activity": last_event.get("timestamp", ""),
                        "event_count": event_count,
                        "model": last_event.get("model", ""),
                        "cwd": last_event.get("cwd", ""),
                    }
                )
            except Exception:
                continue

    sessions.sort(key=lambda s: s.get("last_event_age_seconds", 999999))
    sessions = sessions[:limit]
    active_count = sum(1 for s in sessions if s["status"] in ("ACTIVE", "WAITING"))
    return {"sessions": sessions, "total": len(sessions), "active_count": active_count}


# ─── /taskboard ────────────────────────────────────────────────────────


def load_taskboard() -> Dict[str, Any]:
    """Read the taskboard file, creating the default if missing."""
    if not TASKBOARD_FILE.exists():
        TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
        default = {"version": "1.0", "tasks": []}
        TASKBOARD_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(TASKBOARD_FILE.read_text())


def save_taskboard(data: Dict[str, Any]) -> None:
    """Write the taskboard file."""
    TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
    TASKBOARD_FILE.write_text(json.dumps(data, indent=2))


def query_taskboard(
    status: Optional[str] = None,
    project: Optional[str] = None,
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    """Return all tasks, optionally filtered."""
    data = load_taskboard()
    tasks = data.get("tasks", [])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if project:
        tasks = [t for t in tasks if t.get("project", "").lower() == project.lower()]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]
    return {"tasks": tasks, "total": len(tasks)}


# ─── /plans/progress ───────────────────────────────────────────────────


def plans_progress() -> Dict[str, Any]:
    """Summarize all active plans in ~/.cortex/plans/."""
    if not PLANS_DIR.exists():
        return {"plans": [], "total": 0}

    summaries: List[Dict[str, Any]] = []
    for plan_path in sorted(PLANS_DIR.glob("*.json")):
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


# ─── /decisions/record-freeform ───────────────────────────────────────


def record_freeform_decision(
    decision: str,
    context: str = "",
    alternatives: str = "",
    rationale: str = "",
    project: str = "",
    confidence: float = 0.0,
    tags: str = "",
) -> Dict[str, Any]:
    """Append a free-form decision to ~/.cortex/decisions.jsonl."""
    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    decision_id = f"dec_{int(time.time())}_{abs(hash(decision)) % 100000:05d}"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    entry = {
        "kind": "freeform",
        "decision_id": decision_id,
        "decision": decision,
        "context": context,
        "alternatives": alternatives,
        "rationale": rationale,
        "project": project,
        "confidence": confidence,
        "tags": tag_list,
        "timestamp": datetime.now().isoformat(),
    }
    with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {
        "recorded": True,
        "decision_id": decision_id,
        "timestamp": entry["timestamp"],
    }


# ─── /plans/create ─────────────────────────────────────────────────────


def create_plan(project: str, title: Optional[str] = None) -> Dict[str, Any]:
    """Parse goals for `project` and write a plan JSON to ~/.cortex/plans/."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

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
        "created_at": datetime.utcnow().isoformat() + "+00:00",
        "source": str(parser.action_plan_path),
        "item_count": len(items),
        "items": items,
    }
    plan_path = PLANS_DIR / f"{project}_{ts}.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return {"plan_id": plan_id, "path": str(plan_path), "item_count": len(items)}


# ─── /conductor/compose ───────────────────────────────────────────────


_INTENT_LEVEL_FRAMES = {
    "advisory": "Research and recommend only. Do not modify any files.",
    "collaborative": "Propose changes and wait for my approval before executing.",
    "autonomous": "Execute end-to-end. Test, fix, and report results when done.",
    "supervisory": "Orchestrate sub-agents for parallel execution. Report aggregate results.",
}


def compose_conductor_prompt(
    intent: str,
    project_id: str,
    intent_level: str = "collaborative",
    include_context: bool = True,
) -> Dict[str, Any]:
    """Compose an optimized prompt with intent framing + project context.

    Mirrors the api/bridge_endpoint.py:/conductor/compose body. Writes each
    composed prompt to ~/.cortex/conductor/prompt_history.jsonl.
    """
    sections: List[str] = []
    frame = _INTENT_LEVEL_FRAMES.get(intent_level, _INTENT_LEVEL_FRAMES["collaborative"])
    proj_info = next((p for p in CONDUCTOR_PROJECTS if p["id"] == project_id), None)

    sections.append(f"**Intent Level**: {intent_level.upper()} — {frame}")
    if proj_info:
        sections.append(f"**Project**: {proj_info['name']} (`{proj_info['path']}`)")
    sections.append(f"\n## Task\n{intent}")

    if include_context and proj_info:
        try:
            r = subprocess.run(
                ["git", "log", "-5", "--format=%h %s", "--", proj_info["path"]],
                cwd=str(WORKSPACE),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                sections.append(f"\n## Recent Commits\n```\n{r.stdout.strip()}\n```")
        except Exception:
            pass

        ns_file = NEXT_SESSION_FILES.get(project_id)
        if ns_file and ns_file.exists():
            try:
                content = ns_file.read_text(encoding="utf-8")[:1000]
                sections.append(f"\n## Previous Session Context\n{content}")
            except Exception:
                pass

    composed = "\n".join(sections)
    token_estimate = len(composed.split()) * 2

    # Persist to history (non-fatal on error).
    try:
        CONDUCTOR_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "+00:00",
            "intent": intent,
            "project_id": project_id,
            "intent_level": intent_level,
            "prompt": composed,
            "token_estimate": token_estimate,
        }
        with open(CONDUCTOR_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return {
        "prompt": composed,
        "project": project_id,
        "intent_level": intent_level,
        "token_estimate": token_estimate,
    }
