"""Session routes — Claude Code session visibility + continuity helpers.

Three endpoints that surface session-level signal for the dashboard:
  - `/sessions`             scans `~/.claude/projects/*/*.jsonl` for live state
  - `/session/resume-context` proxies briefing.detect_resume_context()
  - `/session/delta`        proxies session_delta.get_session_delta_report()

The three are grouped here because they all answer "what's happening in
my Claude sessions right now?", even though the latter two are thin
wrappers around helpers defined elsewhere in the codebase.

Wired into the FastAPI app via:

    from api.routes.sessions import router as sessions_router
    app.include_router(sessions_router)
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def get_sessions(
    active_only: bool = Query(False, description="Only return active/waiting sessions"),
    limit: int = Query(20, description="Max sessions to return"),
) -> Dict[str, Any]:
    """Scan Claude Code session JSONL files for real-time session visibility.

    Derives session state from last event age:
      - ACTIVE: last event < 60s (Claude or tool running)
      - WAITING: last event type is 'user' and age < 60s
      - IDLE: last event age 60s-300s
      - STALE: last event age > 300s
    """
    try:
        sessions = []
        now = time.time()

        if not CLAUDE_PROJECTS_DIR.exists():
            return {"sessions": [], "total": 0, "active_count": 0}

        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            # Strip Claude project path prefix (format: -Users-<username>-<path>)
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
                    event_count = len(lines)
                    first_event: Dict[str, Any] = {}

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

                    if active_only and status in ("STALE",):
                        continue

                    session_id = jsonl_file.stem
                    sessions.append(
                        {
                            "id": session_id,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/resume-context")
async def get_resume_context() -> Dict[str, Any]:
    """Return uncommitted work context for the dashboard ResumeCard."""
    try:
        from briefing import detect_resume_context

        ctx = detect_resume_context()
        return {"resume": ctx}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/delta")
async def get_session_delta() -> Dict[str, Any]:
    """Return session-to-session delta and projections."""
    try:
        from session_delta import get_session_delta_report

        report = get_session_delta_report()
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
