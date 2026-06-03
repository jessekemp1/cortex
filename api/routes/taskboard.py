"""Taskboard routes — spec-driven task management with AI decomposition.

These endpoints implement the persistent task board backed by
`~/.cortex/taskboard/tasks.json`. They share the file I/O helpers
(`_load_taskboard` / `_save_taskboard`), three Pydantic request models,
and the `/taskboard/decompose` route additionally calls into the
CortexBridge for AI-assisted task breakdown.

Wired into the FastAPI app via:

    from api.routes.taskboard import router as taskboard_router
    app.include_router(taskboard_router)

Public route table (paths unchanged from the pre-split bridge):
    GET    /taskboard               ?status=, ?project=, ?priority= -> filtered tasks
    POST   /taskboard               TaskBoardCreateRequest         -> created task
    PATCH  /taskboard/{task_id}     TaskBoardUpdateRequest         -> updated task
    DELETE /taskboard/{task_id}                                    -> deletion ack
    POST   /taskboard/decompose     DecomposeRequest               -> parent + subtasks
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

TASKBOARD_DIR = Path.home() / ".cortex" / "taskboard"
TASKBOARD_FILE = TASKBOARD_DIR / "tasks.json"


def _load_taskboard() -> Dict[str, Any]:
    """Load task board from disk, seeding an empty file on first read."""
    if not TASKBOARD_FILE.exists():
        TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
        default: Dict[str, Any] = {"version": "1.0", "tasks": []}
        TASKBOARD_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(TASKBOARD_FILE.read_text())


def _save_taskboard(data: Dict[str, Any]) -> None:
    """Save task board to disk."""
    TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
    TASKBOARD_FILE.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TaskBoardCreateRequest(BaseModel):
    """Request to create a task."""

    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    status: str = Field(default="backlog", description="Status: backlog, ready, in_progress, done")
    priority: str = Field(default="MEDIUM", description="Priority: HIGH, MEDIUM, LOW")
    project: str = Field(default="", description="Project name")
    tags: List[str] = Field(default_factory=list, description="Tags")
    parent_id: Optional[str] = Field(default=None, description="Parent task ID")


class TaskBoardUpdateRequest(BaseModel):
    """Request to update a task."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    project: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class DecomposeRequest(BaseModel):
    """Request to decompose a spec into tasks."""

    description: str = Field(..., description="Spec or feature description")
    project: str = Field(default="", description="Project name")
    context: str = Field(default="", description="Additional context")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(tags=["taskboard"])


@router.get("/taskboard")
async def get_taskboard(
    status: Optional[str] = Query(None, description="Filter by status"),
    project: Optional[str] = Query(None, description="Filter by project"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
) -> Dict[str, Any]:
    """Get all tasks, optionally filtered."""
    try:
        data = _load_taskboard()
        tasks = data.get("tasks", [])

        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        if project:
            tasks = [t for t in tasks if t.get("project", "").lower() == project.lower()]
        if priority:
            tasks = [t for t in tasks if t.get("priority") == priority]

        return {"tasks": tasks, "total": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/taskboard")
async def create_task(task: TaskBoardCreateRequest) -> Dict[str, Any]:
    """Create a new task."""
    try:
        data = _load_taskboard()
        new_task = {
            "id": f"task_{int(time.time())}",
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "project": task.project,
            "tags": task.tags,
            "parent_id": task.parent_id,
            "subtasks": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "source": "manual",
            "notes": "",
        }
        data.setdefault("tasks", []).append(new_task)
        _save_taskboard(data)
        return {"status": "added", "task": new_task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/taskboard/{task_id}")
async def update_task(task_id: str, update: TaskBoardUpdateRequest) -> Dict[str, Any]:
    """Update a task."""
    try:
        data = _load_taskboard()

        for task in data.get("tasks", []):
            if task.get("id") == task_id:
                if update.title is not None:
                    task["title"] = update.title
                if update.description is not None:
                    task["description"] = update.description
                if update.status is not None:
                    old_status = task.get("status")
                    task["status"] = update.status
                    if update.status == "in_progress" and old_status != "in_progress":
                        task["started_at"] = datetime.now().isoformat()
                    if update.status == "done" and old_status != "done":
                        task["completed_at"] = datetime.now().isoformat()
                if update.priority is not None:
                    task["priority"] = update.priority
                if update.project is not None:
                    task["project"] = update.project
                if update.tags is not None:
                    task["tags"] = update.tags
                if update.notes is not None:
                    task["notes"] = update.notes
                task["updated_at"] = datetime.now().isoformat()

                _save_taskboard(data)
                return {"status": "updated", "task": task}

        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/taskboard/{task_id}")
async def delete_taskboard_task(task_id: str) -> Dict[str, Any]:
    """Delete a task."""
    try:
        data = _load_taskboard()
        tasks = data.get("tasks", [])
        new_tasks = [t for t in tasks if t.get("id") != task_id]

        if len(new_tasks) == len(tasks):
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        data["tasks"] = new_tasks
        _save_taskboard(data)
        return {"status": "deleted", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/taskboard/decompose")
async def decompose_task(req: DecomposeRequest) -> Dict[str, Any]:
    """Decompose a feature description into subtasks via Cortex intelligence.

    Falls back to a single-task heuristic if the intelligence engine is
    unavailable (e.g., the bridge isn't initialized or returns an error).
    """
    # Import lazily so the router module loads without the full bridge ready
    # (the bridge has heavy transitive imports — we don't want them at
    # router-module-load time).
    from api.bridge_endpoint import get_bridge

    try:
        bridge = get_bridge()
        result = bridge.query_intelligence(
            f"Decompose this into 3-5 actionable implementation tasks. "
            f"For each task, provide a title and priority (HIGH/MEDIUM/LOW).\n\n"
            f"Feature: {req.description}\n"
            f"Project: {req.project}\n"
            f"Context: {req.context}",
            project=req.project or "cortex",
        )

        response_text = result.get("result", "") or result.get("response", "")

        parent_id = f"task_{int(time.time())}"
        parent_task = {
            "id": parent_id,
            "title": req.description[:100],
            "description": req.description,
            "status": "backlog",
            "priority": "HIGH",
            "project": req.project,
            "tags": ["decomposed"],
            "parent_id": None,
            "subtasks": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "source": "decompose",
            "notes": "",
        }

        # Parse AI response into structured subtasks (line-based heuristic).
        subtasks: List[Dict[str, Any]] = []
        for i, line in enumerate(response_text.split("\n")):
            line = line.strip().lstrip("0123456789.-) ")
            if len(line) > 10 and not line.startswith("#"):
                sub_id = f"task_{int(time.time())}_{i}"
                priority = (
                    "HIGH"
                    if "high" in line.lower()
                    else "MEDIUM"
                    if "medium" in line.lower()
                    else "LOW"
                )
                subtasks.append(
                    {
                        "id": sub_id,
                        "title": line[:120],
                        "description": "",
                        "status": "backlog",
                        "priority": priority,
                        "project": req.project,
                        "tags": ["subtask"],
                        "parent_id": parent_id,
                        "subtasks": [],
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "started_at": None,
                        "completed_at": None,
                        "source": "decompose",
                        "notes": "",
                    }
                )

        return {
            "parent_task": parent_task,
            "subtasks": subtasks,
            "ai_response": response_text[:500],
        }
    except Exception as e:
        # Fallback: return the description as a single task with the error noted.
        parent_id = f"task_{int(time.time())}"
        return {
            "parent_task": {
                "id": parent_id,
                "title": req.description[:100],
                "description": req.description,
                "status": "backlog",
                "priority": "HIGH",
                "project": req.project,
                "tags": [],
                "parent_id": None,
                "subtasks": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "source": "decompose_fallback",
                "notes": f"Decomposition failed: {str(e)}",
            },
            "subtasks": [],
            "ai_response": "",
        }
