"""Conductor routes — startup intelligence, prompt composition, templates, history.

These four endpoints power the Conductor UI's session-start workflow:
inspect projects, compose enriched prompts, browse templates, recall history.

Wired into the FastAPI app via:

    from api.routes.conductor import router as conductor_router
    app.include_router(conductor_router)

Public route table (paths unchanged from the pre-split bridge):
    GET  /conductor/startup    ?project_id=  -> project health + git + next_session + alerts
    POST /conductor/compose    PromptComposeRequest -> enriched prompt + token estimate
    GET  /conductor/templates                  -> list of prompt templates
    GET  /conductor/history    ?limit=N      -> recent compose history, newest-first

Dependencies on the rest of the bridge:
    - get_bridge(): obtains the CortexBridge singleton for recommendations.
    - WORKSPACE / NEXT_SESSION_FILES / MEMORY_FILE: path constants defined in
      bridge_endpoint. Imported lazily inside handlers to avoid module-import-
      time cycles.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Project registry — id, display name, icon, test command per project the
# Conductor knows about. Keep this in lockstep with the UI's expectations.
# ---------------------------------------------------------------------------

CONDUCTOR_PROJECTS: List[Dict[str, str]] = [
    {
        "id": "vortex-backend",
        "name": "Vortex Backend",
        "path": "Vortex/backend",
        "icon": "◎",
        "test_cmd": "pytest Vortex/backend/tests/ -v",
    },
    {
        "id": "vortex-frontend",
        "name": "Vortex Frontend",
        "path": "Vortex/frontend",
        "icon": "◧",
        "test_cmd": "cd Vortex/frontend && npm test",
    },
    {
        "id": "cortex",
        "name": "Cortex",
        "path": "cortex",
        "icon": "◉",
        "test_cmd": "pytest cortex/tests/ -v",
    },
    {
        "id": "alpha-arena",
        "name": "Alpha Arena",
        "path": "alpha_arena",
        "icon": "▲",
        "test_cmd": "pytest alpha_arena/tests/ -v",
    },
    {
        "id": "pupil",
        "name": "Pupil",
        "path": "pupil",
        "icon": "◑",
        "test_cmd": "pytest pupil/tests/ -v",
    },
]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ConductorStartupRequest(BaseModel):
    """Optional request for customized startup data."""

    project_id: Optional[str] = Field(default=None, description="Focus on specific project")


class PromptComposeRequest(BaseModel):
    """Request to compose an optimized prompt."""

    intent: str = Field(..., description="What the user wants to accomplish")
    project_id: str = Field(..., description="Target project ID")
    intent_level: str = Field(
        default="collaborative", description="advisory|collaborative|autonomous|supervisory"
    )
    include_context: bool = Field(default=True, description="Include project context in prompt")


# ---------------------------------------------------------------------------
# Prompt templates — surfaced via /conductor/templates
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES: List[Dict[str, str]] = [
    {
        "id": "investigate",
        "label": "Investigate",
        "icon": "🔍",
        "template": "Investigate: {intent}\n\nDo NOT modify any files. Research the codebase, identify root causes, and report findings with file:line references.",
        "intent_level": "advisory",
    },
    {
        "id": "fix",
        "label": "Fix Bug",
        "icon": "🔧",
        "template": "Fix: {intent}\n\nIdentify root cause, implement the fix, run tests, and verify green before reporting.",
        "intent_level": "autonomous",
    },
    {
        "id": "implement",
        "label": "Implement Feature",
        "icon": "⚡",
        "template": "Implement: {intent}\n\nPlan the implementation, propose changes for review, then execute after approval.",
        "intent_level": "collaborative",
    },
    {
        "id": "ship",
        "label": "Ship It",
        "icon": "🚀",
        "template": "Ship: {intent}\n\nImplement, test, validate, commit, and prepare for deployment. Full autonomous execution.",
        "intent_level": "autonomous",
    },
    {
        "id": "review",
        "label": "Code Review",
        "icon": "📋",
        "template": "Review: {intent}\n\nAnalyze the code for bugs, performance issues, security vulnerabilities, and style. Report findings only.",
        "intent_level": "advisory",
    },
    {
        "id": "orchestrate",
        "label": "Orchestrate",
        "icon": "🎯",
        "template": "Orchestrate: {intent}\n\nDecompose into parallel work streams. Use sub-agents for independent tasks. Report aggregate results.",
        "intent_level": "supervisory",
    },
]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["conductor"])


@router.get("/conductor/startup")
async def conductor_startup(
    project_id: Optional[str] = Query(None, description="Focus on specific project"),
) -> Dict[str, Any]:
    """Aggregated startup intelligence for the Conductor UI.

    Returns everything needed to start a productive session: project health,
    git status, .next_session.md content (if any), active alerts and
    recommendations, and a memory snapshot.
    """
    # Import lazily to avoid pulling in the full bridge module at router-load.
    from api.bridge_endpoint import (
        WORKSPACE,
        NEXT_SESSION_FILES,
        MEMORY_FILE,
        get_bridge,
    )

    result: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "projects": [],
        "git": {},
        "next_session": None,
        "alerts": [],
        "recommendations": [],
        "memory_snapshot": None,
    }

    # 1. Project health cards
    for proj in CONDUCTOR_PROJECTS:
        proj_path = WORKSPACE / proj["path"]
        if not proj_path.exists():
            continue

        last_commit = ""
        last_commit_msg = ""
        uncommitted = 0
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%h|%ar|%s", "--", proj["path"]],
                cwd=str(WORKSPACE),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split("|", 2)
                last_commit = parts[0] if len(parts) > 0 else ""
                last_commit_msg = parts[2] if len(parts) > 2 else ""
        except Exception:
            pass

        try:
            r = subprocess.run(
                ["git", "diff", "--name-only", "--", proj["path"]],
                cwd=str(WORKSPACE),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode == 0:
                uncommitted = len([l for l in r.stdout.strip().split("\n") if l.strip()])
        except Exception:
            pass

        result["projects"].append(
            {
                "id": proj["id"],
                "name": proj["name"],
                "icon": proj["icon"],
                "last_commit": last_commit,
                "last_commit_msg": last_commit_msg,
                "uncommitted_files": uncommitted,
                "test_cmd": proj["test_cmd"],
            }
        )

    # 2. Global git status
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=2,
        )
        branch = r.stdout.strip() if r.returncode == 0 else "unknown"

        r2 = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=3,
        )
        changed_files = (
            len([l for l in r2.stdout.strip().split("\n") if l.strip()])
            if r2.returncode == 0
            else 0
        )

        result["git"] = {"branch": branch, "changed_files": changed_files}
    except Exception:
        result["git"] = {"branch": "unknown", "changed_files": 0}

    # 3. .next_session.md content
    if project_id and project_id in NEXT_SESSION_FILES:
        ns_file = NEXT_SESSION_FILES[project_id]
        if ns_file.exists():
            try:
                result["next_session"] = {
                    "project": project_id,
                    "content": ns_file.read_text(encoding="utf-8")[:2000],
                }
            except Exception:
                pass
    else:
        for pid, ns_file in NEXT_SESSION_FILES.items():
            if ns_file.exists():
                try:
                    mtime = ns_file.stat().st_mtime
                    age_hours = (time.time() - mtime) / 3600
                    if age_hours < 48:
                        result["next_session"] = {
                            "project": pid,
                            "content": ns_file.read_text(encoding="utf-8")[:2000],
                            "age_hours": round(age_hours, 1),
                        }
                        break
                except Exception:
                    pass

    # 4. Memory snapshot (first 40 lines for quick overview)
    if MEMORY_FILE.exists():
        try:
            lines = MEMORY_FILE.read_text(encoding="utf-8").split("\n")
            result["memory_snapshot"] = "\n".join(lines[:40])
        except Exception:
            pass

    # 5. Active alerts (from Cortex)
    try:
        bridge = get_bridge()
        recs = bridge.get_recommendations()
        if recs and isinstance(recs, dict):
            for alert in recs.get("risk_alerts", [])[:5]:
                result["alerts"].append(
                    {
                        "severity": alert.get("severity", "INFO"),
                        "message": alert.get("message", ""),
                        "type": alert.get("type", ""),
                    }
                )
            if recs.get("next_action"):
                result["recommendations"].append(
                    {
                        "action": recs["next_action"].get("action", ""),
                        "priority": recs["next_action"].get("priority", "MEDIUM"),
                        "type": recs["next_action"].get("type", ""),
                    }
                )
    except Exception:
        pass

    return result


@router.post("/conductor/compose")
async def conductor_compose_prompt(req: PromptComposeRequest) -> Dict[str, Any]:
    """Compose an optimized prompt based on intent, project, and context.

    Enriches the user's natural-language intent with project-specific context,
    intent-level framing, relevant .next_session content, and persists the
    composed prompt to history for later recall.
    """
    from api.bridge_endpoint import WORKSPACE, NEXT_SESSION_FILES

    sections: List[str] = []

    level_frames = {
        "advisory": "Research and recommend only. Do not modify any files.",
        "collaborative": "Propose changes and wait for my approval before executing.",
        "autonomous": "Execute end-to-end. Test, fix, and report results when done.",
        "supervisory": "Orchestrate sub-agents for parallel execution. Report aggregate results.",
    }
    frame = level_frames.get(req.intent_level, level_frames["collaborative"])

    proj_info = next((p for p in CONDUCTOR_PROJECTS if p["id"] == req.project_id), None)

    sections.append(f"**Intent Level**: {req.intent_level.upper()} — {frame}")
    if proj_info:
        sections.append(f"**Project**: {proj_info['name']} (`{proj_info['path']}`)")

    sections.append(f"\n## Task\n{req.intent}")

    if req.include_context and proj_info:
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

        ns_file = NEXT_SESSION_FILES.get(req.project_id)
        if ns_file and ns_file.exists():
            try:
                content = ns_file.read_text(encoding="utf-8")[:1000]
                sections.append(f"\n## Previous Session Context\n{content}")
            except Exception:
                pass

    composed = "\n".join(sections)
    token_estimate = len(composed.split()) * 2  # rough estimate

    # Persist to prompt history (non-critical — never fail the request on this).
    try:
        history_dir = Path.home() / ".cortex" / "conductor"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "prompt_history.jsonl"
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "intent": req.intent,
            "project_id": req.project_id,
            "intent_level": req.intent_level,
            "prompt": composed,
            "token_estimate": token_estimate,
        }
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return {
        "prompt": composed,
        "project": req.project_id,
        "intent_level": req.intent_level,
        "token_estimate": token_estimate,
    }


@router.get("/conductor/templates")
async def conductor_templates() -> Dict[str, Any]:
    """Return available prompt templates for the Prompt Composer."""
    return {"templates": PROMPT_TEMPLATES}


@router.get("/conductor/history")
async def conductor_prompt_history(
    limit: int = Query(default=20, ge=1, le=200, description="Number of recent entries to return"),
) -> Dict[str, Any]:
    """Return recent prompt composition history, newest-first.

    Reads from ~/.cortex/conductor/prompt_history.jsonl.
    """
    history_file = Path.home() / ".cortex" / "conductor" / "prompt_history.jsonl"

    if not history_file.exists():
        return {"entries": [], "total": 0}

    entries: List[Dict[str, Any]] = []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read prompt history: {e}")

    entries.reverse()  # newest-first
    total = len(entries)
    entries = entries[:limit]

    return {"entries": entries, "total": total}
