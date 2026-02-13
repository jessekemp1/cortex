#!/usr/bin/env python3
"""
Cortex Bridge API - RESTful endpoint for Moltbot and external integrations.

Exposes Cortex intelligence for:
- Intelligence queries
- Anomaly detection
- Recommendations
- Project status
- Pattern matching

Start with: uvicorn cortex.api.bridge_endpoint:app --host 127.0.0.1 --port 8765
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add cortex to path for imports
cortex_root = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_root.parent))

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError:
    print("ERROR: FastAPI not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

try:
    from cortex.bridge import CortexBridge
    from cortex.orchestration.anomaly_detector import OrchestrationAnomalyManager
except ImportError as e:
    print(f"ERROR: Could not import Cortex modules: {e}")
    sys.exit(1)


# ============================================================================
# Pydantic Models
# ============================================================================


class IntelligenceQuery(BaseModel):
    """Request model for intelligence queries."""

    request: str = Field(..., description="User request or query")
    project: str = Field(default="cortex", description="Project name")
    query_type: str = Field(
        default="spec", description="Query type: spec, impl, analysis, research"
    )
    use_cache: bool = Field(default=True, description="Use query cache")
    parallel: bool = Field(default=True, description="Query sources in parallel")


class RecommendationRequest(BaseModel):
    """Request model for recommendations."""

    project: Optional[str] = Field(default=None, description="Filter by project")
    limit: int = Field(default=5, description="Max recommendations to return")


class StatusResponse(BaseModel):
    """Response model for status check."""

    status: str
    version: str
    available_projects: List[str]
    anomaly_count: int


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Cortex Bridge API",
    description="RESTful API for Cortex intelligence and orchestration",
    version="1.0.0",
)

# CORS - Allow Moltbot, React frontend, and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:18789",  # Moltbot
        "http://localhost:18789",  # Moltbot
        "http://localhost:5173",  # React dev server (legacy)
        "http://127.0.0.1:5173",  # React dev server (legacy)
        "http://localhost:3001",  # Cortex Mission Control
        "http://127.0.0.1:3001",  # Cortex Mission Control
        "http://localhost:*",  # Other local services
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Cortex bridge (lazy load)
_bridge: Optional[CortexBridge] = None
_anomaly_manager: Optional[OrchestrationAnomalyManager] = None


def get_bridge() -> CortexBridge:
    """Get or create Cortex bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = CortexBridge()
    return _bridge


def get_anomaly_manager() -> OrchestrationAnomalyManager:
    """Get or create anomaly manager instance."""
    global _anomaly_manager
    if _anomaly_manager is None:
        try:
            from cortex.orchestration.database import OrchestrationDatabase

            db = OrchestrationDatabase()
            _anomaly_manager = OrchestrationAnomalyManager(db)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to initialize anomaly manager: {e}"
            )
    return _anomaly_manager


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - API info."""
    return {
        "service": "Cortex Bridge API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cortex-bridge-api"}


@app.get("/status")
async def status():
    """Get comprehensive Cortex status."""
    try:
        get_bridge()
        anomaly_mgr = get_anomaly_manager()

        # Get active anomalies
        context = {
            "active_projects": ["cortex", "vortex", "alpha_arena"],
            "total_projects": 4,
            "goals_in_progress": 2,
            "goals_pending": 1,
        }
        anomalies = anomaly_mgr.detect_all(context=context)

        return {
            "status": "operational",
            "version": "1.0.0",
            "available_projects": ["cortex", "vortex", "alpha_arena", "kempion"],
            "anomaly_count": len(anomalies),
            "bridge_initialized": _bridge is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Intelligence Endpoints
# ============================================================================


@app.post("/intelligence/query")
async def query_intelligence(query: IntelligenceQuery) -> Dict[str, Any]:
    """
    Query Cortex unified intelligence.

    Returns ranked results, confidence scores, and detailed reasoning.
    """
    try:
        bridge = get_bridge()
        result = bridge.query_intelligence(
            request=query.request,
            project=query.project,
            query_type=query.query_type,
            use_cache=query.use_cache,
            parallel=query.parallel,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/intelligence/recommendations")
async def get_recommendations(
    project: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(5, description="Max recommendations"),
) -> Dict[str, Any]:
    """
    Get Cortex recommendations based on current context.
    """
    try:
        bridge = get_bridge()
        recommendations = bridge.get_recommendations()

        # Filter by project if specified
        if project and "recommendations" in recommendations:
            filtered = [
                r for r in recommendations["recommendations"] if r.get("project") == project
            ]
            recommendations["recommendations"] = filtered[:limit]
        elif "recommendations" in recommendations:
            recommendations["recommendations"] = recommendations["recommendations"][:limit]

        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================


@app.get("/anomalies")
async def get_anomalies(
    severity: Optional[str] = Query(
        None, description="Filter by severity: CRITICAL, WARNING, INFO"
    ),
    anomaly_type: Optional[str] = Query(None, description="Filter by type"),
) -> Dict[str, Any]:
    """
    Get current orchestration anomalies.

    Returns list of detected anomalies with severity, type, and recommendations.
    """
    try:
        anomaly_mgr = get_anomaly_manager()
        context = {
            "active_projects": ["cortex", "vortex", "alpha_arena"],
            "total_projects": 4,
            "goals_in_progress": 2,
            "goals_pending": 1,
        }
        anomalies = anomaly_mgr.detect_all(context=context)

        # Filter by severity
        if severity:
            anomalies = [
                a for a in anomalies if getattr(a.severity, "value", a.severity) == severity
            ]

        # Filter by type
        if anomaly_type:
            anomalies = [
                a
                for a in anomalies
                if getattr(a.anomaly_type, "value", a.anomaly_type) == anomaly_type
            ]

        return {
            "count": len(anomalies),
            "anomalies": [
                {
                    "id": a.anomaly_id,
                    "type": getattr(a.anomaly_type, "value", str(a.anomaly_type)),
                    "severity": getattr(a.severity, "value", str(a.severity)),
                    "title": a.title,
                    "description": a.description,
                    "recommendation": a.remediation,
                    "detected_at": a.detected_at.isoformat()
                    if hasattr(a.detected_at, "isoformat")
                    else str(a.detected_at)
                    if a.detected_at
                    else None,
                }
                for a in anomalies
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Context Graph Endpoints
# ============================================================================


@app.get("/graph/query")
async def query_graph(
    node_type: str = Query(..., description="Node type to query"),
    filters: Optional[str] = Query(None, description="JSON filters"),
) -> Dict[str, Any]:
    """
    Query Cortex context graph.

    Returns nodes matching the specified type and filters.
    """
    try:
        import json

        bridge = get_bridge()

        filter_dict = json.loads(filters) if filters else None
        nodes = bridge.query_graph(node_type=node_type, filters=filter_dict)

        return {"node_type": node_type, "count": len(nodes), "nodes": nodes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Management Endpoints
# ============================================================================

# Lazy-loaded batch client and queue manager
_batch_client: Optional[Any] = None
_queue_manager: Optional[Any] = None


def get_batch_client():
    """Get or create batch API client."""
    global _batch_client
    if _batch_client is None:
        try:
            from cortex.batch.batch_api_client import BatchAPIClient

            _batch_client = BatchAPIClient()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize batch client: {e}")
    return _batch_client


def get_queue_manager():
    """Get or create queue manager."""
    global _queue_manager
    if _queue_manager is None:
        try:
            from cortex.batch.queue_manager import BatchQueueManager

            _queue_manager = BatchQueueManager()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize queue manager: {e}")
    return _queue_manager


@app.get("/batches")
async def list_batches(limit: int = Query(20, description="Max batches to return")):
    """
    List active and recent batch jobs.

    Returns batch status from Anthropic API.
    """
    try:
        client = get_batch_client()
        batches = client.list_batches(limit=limit)
        return {"batches": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/batches/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Get detailed status for a specific batch.

    Returns progress, request counts, and completion status.
    """
    try:
        client = get_batch_client()
        status = client.get_batch_status(batch_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Batch not found: {e}")


@app.post("/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """
    Cancel a running batch job.

    Returns updated batch status after cancellation.
    """
    try:
        client = get_batch_client()
        result = client.cancel_batch(batch_id)
        return {"status": "cancelled", "batch_id": batch_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue")
async def get_queue():
    """
    Get pending tasks in the batch queue.

    Returns tasks waiting for submission.
    """
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()
        return {
            "tasks": queue_data.get("priority_jobs", []),
            "metadata": queue_data.get("queue_metadata", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AddTaskRequest(BaseModel):
    """Request model for adding a task to the queue."""

    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    priority: str = Field(
        default="NORMAL", description="Task priority: CRITICAL, HIGH, NORMAL, LOW"
    )
    estimated_tokens: int = Field(default=5000, description="Estimated token count")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="Subtasks to execute")


@app.post("/queue")
async def add_task(task: AddTaskRequest):
    """
    Add a new task to the batch queue.

    Task will be submitted automatically when capacity allows.
    """
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        # Create new task entry
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


class UpdateTaskRequest(BaseModel):
    """Request model for updating task priority."""

    priority: str = Field(..., description="New priority: CRITICAL, HIGH, NORMAL, LOW")


@app.patch("/queue/{task_id}")
async def update_task_priority(task_id: str, update: UpdateTaskRequest):
    """
    Update the priority of a queued task.
    """
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        # Find and update task
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


@app.delete("/queue/{task_id}")
async def delete_task(task_id: str):
    """
    Remove a task from the queue.
    """
    try:
        mgr = get_queue_manager()
        queue_data = mgr.load_queue()

        # Filter out the task
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


@app.get("/metrics")
async def get_metrics(days: int = Query(7, description="Days of history to include")):
    """
    Get usage metrics and cost savings.

    Returns batch API usage stats and savings vs interactive mode.
    """
    try:
        client = get_batch_client()

        # Get recent batches for metrics calculation
        batches = client.list_batches(limit=100)

        # Calculate metrics
        total_requests = sum(b.get("request_counts", {}).get("total", 0) for b in batches)
        succeeded = sum(b.get("request_counts", {}).get("succeeded", 0) for b in batches)
        errored = sum(b.get("request_counts", {}).get("errored", 0) for b in batches)

        # Estimate cost savings (batch API is 50% cheaper)
        # Rough estimate based on average request cost
        estimated_savings = total_requests * 0.005  # ~$0.005 saved per request

        return {
            "period_days": days,
            "total_requests": total_requests,
            "successful_requests": succeeded,
            "failed_requests": errored,
            "success_rate": (succeeded / total_requests * 100) if total_requests > 0 else 100.0,
            "estimated_savings_usd": round(estimated_savings, 2),
            "batch_count": len(batches),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Utility Endpoints
# ============================================================================


@app.get("/projects")
async def list_projects() -> List[Dict[str, Any]]:
    """List available projects with status."""
    return [
        {
            "name": "VortexV2",
            "status": "healthy",
            "health_score": 0.92,
            "last_activity": datetime.now().isoformat(),
            "key_metric": "MAE",
            "key_metric_value": "2.20 kt",
        },
        {
            "name": "VortexV3",
            "status": "healthy",
            "health_score": 0.95,
            "last_activity": datetime.now().isoformat(),
            "key_metric": "Tests",
            "key_metric_value": "50/50",
        },
        {
            "name": "Cortex",
            "status": "healthy",
            "health_score": 0.88,
            "last_activity": datetime.now().isoformat(),
            "key_metric": "Uptime",
            "key_metric_value": "99.9%",
        },
        {
            "name": "Winfield",
            "status": "healthy",
            "health_score": 0.85,
            "last_activity": datetime.now().isoformat(),
            "key_metric": "Tests",
            "key_metric_value": "161 pass",
        },
        {
            "name": "Alpha Arena",
            "status": "warning",
            "health_score": 0.60,
            "last_activity": datetime.now().isoformat(),
            "key_metric": "Phase",
            "key_metric_value": "Planning",
        },
    ]


@app.get("/recommendations")
async def get_recommendations_alias(
    project: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(5, description="Max recommendations"),
) -> Dict[str, Any]:
    """Alias for /intelligence/recommendations."""
    return await get_recommendations(project=project, limit=limit)


# ============================================================================
# Sessions — Claude Code session visibility
# ============================================================================

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@app.get("/sessions")
async def get_sessions(
    active_only: bool = Query(False, description="Only return active/waiting sessions"),
    limit: int = Query(20, description="Max sessions to return"),
) -> Dict[str, Any]:
    """
    Scan Claude Code session JSONL files for real-time session visibility.

    Derives session state from last event age:
    - ACTIVE: last event < 60s (Claude or tool running)
    - WAITING: last event type is 'user' and age < 60s
    - IDLE: last event age 60s-300s
    - STALE: last event age > 300s
    """
    import json as _json

    try:
        sessions = []
        now = time.time()

        if not CLAUDE_PROJECTS_DIR.exists():
            return {"sessions": [], "total": 0, "active_count": 0}

        # Scan all project directories for session JSONL files
        for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue

            project_name = project_dir.name.replace("-Users-jesse-kemp-", "").replace("-", "/")

            for jsonl_file in project_dir.glob("*.jsonl"):
                try:
                    mtime = jsonl_file.stat().st_mtime
                    age_seconds = now - mtime

                    # Read last few lines for state detection
                    content = jsonl_file.read_bytes()
                    lines = content.strip().split(b"\n")
                    if not lines:
                        continue

                    last_event = {}
                    event_count = len(lines)
                    first_event = {}

                    # Parse last line
                    try:
                        last_event = _json.loads(lines[-1])
                    except (ValueError, _json.JSONDecodeError):
                        pass

                    # Parse first line for start time
                    try:
                        first_event = _json.loads(lines[0])
                    except (ValueError, _json.JSONDecodeError):
                        pass

                    # Derive status
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

        # Sort by most recent activity
        sessions.sort(key=lambda s: s.get("last_event_age_seconds", 999999))
        sessions = sessions[:limit]

        active_count = sum(1 for s in sessions if s["status"] in ("ACTIVE", "WAITING"))
        return {"sessions": sessions, "total": len(sessions), "active_count": active_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TaskBoard — Spec-driven task management
# ============================================================================

TASKBOARD_DIR = Path.home() / ".cortex" / "taskboard"
TASKBOARD_FILE = TASKBOARD_DIR / "tasks.json"


def _load_taskboard() -> Dict[str, Any]:
    """Load task board from disk."""
    if not TASKBOARD_FILE.exists():
        TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
        default = {"version": "1.0", "tasks": []}
        TASKBOARD_FILE.write_text(__import__("json").dumps(default, indent=2))
        return default
    import json as _json

    return _json.loads(TASKBOARD_FILE.read_text())


def _save_taskboard(data: Dict[str, Any]) -> None:
    """Save task board to disk."""
    import json as _json

    TASKBOARD_DIR.mkdir(parents=True, exist_ok=True)
    TASKBOARD_FILE.write_text(_json.dumps(data, indent=2))


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


@app.get("/taskboard")
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


@app.post("/taskboard")
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


@app.patch("/taskboard/{task_id}")
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


@app.delete("/taskboard/{task_id}")
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


@app.post("/taskboard/decompose")
async def decompose_task(req: DecomposeRequest) -> Dict[str, Any]:
    """
    Decompose a feature description into subtasks using Cortex intelligence.

    Falls back to heuristic decomposition if intelligence engine unavailable.
    """
    try:
        # Try Cortex intelligence for smart decomposition
        bridge = get_bridge()
        result = bridge.query_intelligence(
            f"Decompose this into 3-5 actionable implementation tasks. "
            f"For each task, provide a title and priority (HIGH/MEDIUM/LOW).\n\n"
            f"Feature: {req.description}\n"
            f"Project: {req.project}\n"
            f"Context: {req.context}",
            project=req.project or "cortex",
        )

        # Parse AI response into structured tasks
        response_text = result.get("result", "") or result.get("response", "")

        # Create parent task
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

        # Create subtasks from AI response (simple line-based parsing)
        subtasks = []
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
                subtask = {
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
                subtasks.append(subtask)
                parent_task["subtasks"].append(sub_id)

                if len(subtasks) >= 7:
                    break

        return {
            "parent_task": parent_task,
            "subtasks": subtasks,
            "ai_response": response_text[:500],
        }
    except Exception as e:
        # Fallback: return the description as a single task
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


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("Starting Cortex Bridge API on http://127.0.0.1:8765")
    print("API docs: http://127.0.0.1:8765/docs")
    uvicorn.run(app, host="127.0.0.1", port=8765)
