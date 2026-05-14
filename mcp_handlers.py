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

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
TASKBOARD_DIR = Path.home() / ".cortex" / "taskboard"
TASKBOARD_FILE = TASKBOARD_DIR / "tasks.json"
PLANS_DIR = Path.home() / ".cortex" / "plans"


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
