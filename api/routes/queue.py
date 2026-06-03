"""Queue routes — read, add, update priority, delete batch-queue tasks.

These endpoints inspect and mutate the persisted batch queue managed by
`cortex.batch.queue_manager.BatchQueueManager`. They share a single
dependency — `get_queue_manager()` — which lazily instantiates the
manager on first use.

Wired into the FastAPI app via:

    from api.routes.queue import router as queue_router
    app.include_router(queue_router)

Public route table (paths unchanged from the pre-split bridge):
    GET    /queue                     -> {tasks: [...], metadata: {...}}
    POST   /queue                     AddTaskRequest   -> {status, task}
    PATCH  /queue/{task_id}           UpdateTaskRequest -> {status, task}
    DELETE /queue/{task_id}                            -> {status, task_id}
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddTaskRequest(BaseModel):
    """Request model for adding a task to the queue."""

    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    priority: str = Field(
        default="NORMAL", description="Task priority: CRITICAL, HIGH, NORMAL, LOW"
    )
    estimated_tokens: int = Field(default=5000, description="Estimated token count")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Subtasks to execute")


class UpdateTaskRequest(BaseModel):
    """Request model for updating task priority."""

    priority: str = Field(..., description="New priority: CRITICAL, HIGH, NORMAL, LOW")


# ---------------------------------------------------------------------------
# Lazy queue manager
# ---------------------------------------------------------------------------

_queue_manager: Optional[Any] = None


def get_queue_manager():
    """Return a cached BatchQueueManager, lazily constructed on first use."""
    global _queue_manager
    if _queue_manager is None:
        try:
            from cortex.batch.queue_manager import BatchQueueManager

            _queue_manager = BatchQueueManager()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to initialize queue manager: {e}"
            )
    return _queue_manager


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["queue"])


@router.get("/queue")
async def get_queue():
    """Get pending tasks in the batch queue."""
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()
        return {
            "tasks": queue_data.get("priority_jobs", []),
            "metadata": queue_data.get("queue_metadata", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue")
async def add_task(task: AddTaskRequest):
    """Add a new task to the batch queue.

    Task will be submitted automatically when capacity allows.
    """
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        new_task = {
            "id": f"task_{int(time.time())}",
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "estimated_tokens": task.estimated_tokens,
            "tasks": task.tasks or [],
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        }

        queue_data.setdefault("priority_jobs", []).append(new_task)
        mgr.save_queue(queue_data)

        return {"status": "added", "task": new_task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/queue/{task_id}")
async def update_task_priority(task_id: str, update: UpdateTaskRequest):
    """Update the priority of a queued task."""
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        for task in queue_data.get("priority_jobs", []):
            if task.get("id") == task_id:
                task["priority"] = update.priority
                mgr.save_queue(queue_data)
                return {"status": "updated", "task": task}

        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/queue/{task_id}")
async def delete_task(task_id: str):
    """Remove a task from the queue."""
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        tasks = queue_data.get("priority_jobs", [])
        new_tasks = [t for t in tasks if t.get("id") != task_id]

        if len(new_tasks) == len(tasks):
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        queue_data["priority_jobs"] = new_tasks
        mgr.save_queue(queue_data)

        return {"status": "deleted", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
