"""
Worker API — exposes task queue to remote workers over HTTP.

Thin FastAPI app on top of existing SQLite BatchTaskQueue.
Auth via bearer token. Endpoints:
  GET  /tasks/next?capabilities=sonnet,haiku → claim next matching task
  POST /tasks/{id}/result                    → submit dispatch result
  POST /tasks/{id}/heartbeat                 → worker still alive
  GET  /workers                              → list connected workers
  GET  /health                               → API health + queue depth

Only starts when enable_distributed=True in SupervisorConfig.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class WorkerInfo:
    """Tracked state of a connected worker."""

    worker_id: str
    hostname: str
    capabilities: List[str]  # ["haiku", "sonnet", "gpu"]
    max_concurrent: int = 2
    providers: List[str] = field(default_factory=lambda: ["anthropic"])
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    status: str = "idle"  # "idle" | "busy" | "disconnected"
    active_task_id: Optional[str] = None


@dataclass
class ClaimedTask:
    """A task claimed by a worker for execution."""

    task_id: str
    work_item: Dict[str, Any]
    model_selection: Dict[str, Any]
    claimed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    worker_id: str = ""


class WorkerRegistry:
    """In-memory registry of connected workers and claimed tasks.

    Thread-safe via the GIL for simple dict operations.
    """

    def __init__(self, heartbeat_timeout_seconds: int = 90) -> None:
        self._workers: Dict[str, WorkerInfo] = {}
        self._claimed_tasks: Dict[str, ClaimedTask] = {}  # task_id → claim
        self._heartbeat_timeout = heartbeat_timeout_seconds

    def register_worker(self, info: WorkerInfo) -> None:
        """Register or update a worker."""
        self._workers[info.worker_id] = info
        log.info("Worker registered: %s (%s)", info.worker_id[:8], info.hostname)

    def heartbeat(self, worker_id: str) -> bool:
        """Update worker heartbeat. Returns False if worker unknown."""
        worker = self._workers.get(worker_id)
        if not worker:
            return False
        worker.last_heartbeat = datetime.now(tz=timezone.utc)
        return True

    def claim_task(
        self, task_id: str, worker_id: str, work_item: Dict, model_selection: Dict
    ) -> ClaimedTask:
        """Record that a worker has claimed a task."""
        claim = ClaimedTask(
            task_id=task_id,
            work_item=work_item,
            model_selection=model_selection,
            worker_id=worker_id,
        )
        self._claimed_tasks[task_id] = claim
        worker = self._workers.get(worker_id)
        if worker:
            worker.status = "busy"
            worker.active_task_id = task_id
        return claim

    def complete_task(self, task_id: str) -> Optional[ClaimedTask]:
        """Mark a task as completed. Returns the claim or None."""
        claim = self._claimed_tasks.pop(task_id, None)
        if claim:
            worker = self._workers.get(claim.worker_id)
            if worker:
                worker.status = "idle"
                worker.active_task_id = None
        return claim

    def get_stale_claims(self) -> List[ClaimedTask]:
        """Find tasks claimed by workers with stale heartbeats."""
        now = datetime.now(tz=timezone.utc)
        stale = []
        for task_id, claim in list(self._claimed_tasks.items()):
            worker = self._workers.get(claim.worker_id)
            if not worker:
                stale.append(claim)
                continue
            elapsed = (now - worker.last_heartbeat).total_seconds()
            if elapsed > self._heartbeat_timeout:
                stale.append(claim)
                worker.status = "disconnected"
        return stale

    def reclaim_stale_tasks(self) -> List[str]:
        """Remove stale claims so tasks can be re-dispatched."""
        stale = self.get_stale_claims()
        reclaimed = []
        for claim in stale:
            self._claimed_tasks.pop(claim.task_id, None)
            reclaimed.append(claim.task_id)
            log.warning(
                "Reclaimed stale task %s from worker %s",
                claim.task_id[:8],
                claim.worker_id[:8],
            )
        return reclaimed

    def list_workers(self) -> List[Dict[str, Any]]:
        """Return worker info dicts."""
        return [
            {
                "worker_id": w.worker_id,
                "hostname": w.hostname,
                "capabilities": w.capabilities,
                "status": w.status,
                "active_task_id": w.active_task_id,
                "last_heartbeat": w.last_heartbeat.isoformat(),
            }
            for w in self._workers.values()
        ]

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def active_task_count(self) -> int:
        return len(self._claimed_tasks)


def create_worker_api(
    worker_registry: WorkerRegistry,
    auth_token: str = "",
) -> Any:
    """Create a FastAPI app for the worker API.

    Returns the FastAPI app instance. Import is lazy to avoid
    requiring FastAPI when distributed mode is disabled.
    """
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
    except ImportError:
        raise RuntimeError(
            "FastAPI required for distributed mode. Install with: pip install fastapi uvicorn"
        )

    app = FastAPI(title="Cortex Worker API", version="1.0.0")

    def verify_token(authorization: str = Header(default="")) -> None:
        if auth_token and authorization != f"Bearer {auth_token}":
            raise HTTPException(status_code=401, detail="Invalid auth token")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "workers": worker_registry.worker_count,
            "active_tasks": worker_registry.active_task_count,
        }

    @app.get("/workers", dependencies=[Depends(verify_token)])
    def list_workers():
        return {"workers": worker_registry.list_workers()}

    @app.post("/workers/register", dependencies=[Depends(verify_token)])
    def register_worker(body: dict):
        info = WorkerInfo(
            worker_id=body.get("worker_id", str(uuid.uuid4())),
            hostname=body.get("hostname", "unknown"),
            capabilities=body.get("capabilities", []),
            max_concurrent=body.get("max_concurrent", 2),
            providers=body.get("providers", ["anthropic"]),
        )
        worker_registry.register_worker(info)
        return {"worker_id": info.worker_id, "status": "registered"}

    @app.post("/tasks/{task_id}/heartbeat", dependencies=[Depends(verify_token)])
    def task_heartbeat(task_id: str, body: dict):
        worker_id = body.get("worker_id", "")
        if not worker_registry.heartbeat(worker_id):
            raise HTTPException(status_code=404, detail="Worker not found")
        return {"status": "ok"}

    @app.post("/tasks/{task_id}/result", dependencies=[Depends(verify_token)])
    def submit_result(task_id: str, body: dict):
        claim = worker_registry.complete_task(task_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Task not claimed")
        return {"status": "completed", "task_id": task_id}

    return app
