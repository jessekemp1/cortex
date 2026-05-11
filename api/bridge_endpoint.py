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

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add cortex to path for imports
cortex_root = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_root.parent))

try:
    from fastapi import Body, FastAPI, HTTPException, Query, Request
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


# IntelligenceQuery + ReasonQuery + the 4 intelligence routes extracted to
# api/routes/intelligence.py. RecommendationRequest was declared but unused
# in this file — removed during the extraction.

class BriefingExecutionRequest(BaseModel):
    """Request model for recording recommendation execution events."""

    execution_id: str = Field(..., description="Unique execution identifier")
    recommendation_id: str = Field(..., description="Recommendation identifier")
    recommendation_title: str = Field(..., description="Recommendation title")
    project: str = Field(..., description="Project name")
    mode: str = Field(..., description="Execution mode (queue/manual/etc)")
    status: str = Field(..., description="Execution status")
    source_version: Optional[str] = Field(default=None, description="Source version or channel")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional execution metadata"
    )


# Guardian request models + routes have been extracted to api/routes/guardian.py.
# (They were defined here historically; see CHANGELOG.md for the split.)


class StatusResponse(BaseModel):
    """Response model for status check."""

    status: str
    version: str
    available_projects: List[str]
    anomaly_count: int


# DecisionRecordRequest + /decisions/record extracted to api/routes/decisions.py.
# The router is mounted near the bottom of this file with the other extracted
# routers via app.include_router().


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Cortex Bridge API",
    description="RESTful API for Cortex intelligence and orchestration",
    version="1.0.0",
)

# Mount web chat gateway
try:
    from cortex.gateway.web_chat import router as chat_router

    app.include_router(chat_router)
except ImportError:
    pass  # gateway module not available

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


@app.get("/service-health")
async def service_health():
    """
    Check health of all ecosystem services.

    Returns status of bridge, Vortex backend, Navigator, and EMOS readiness.
    """
    import urllib.request

    services = {
        "bridge": {"status": "healthy", "port": 8765},
    }

    # Check Vortex Backend (:8000)
    try:
        req = urllib.request.Request("http://localhost:8000/api/v2/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            services["vortex_backend"] = {
                "status": "healthy" if data.get("status") == "healthy" else "degraded",
                "port": 8000,
                "scheduler_jobs": data.get("scheduler", {}).get("jobs_count", 0),
                "version": data.get("version", "unknown"),
            }
    except Exception:
        services["vortex_backend"] = {"status": "offline", "port": 8000}

    # Check Navigator (subsystem of Vortex Backend on :8000)
    try:
        req = urllib.request.Request("http://localhost:8000/api/v2/navigator/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            nav_status = data.get("status", "unknown")
            checks = data.get("checks", {})
            subsystems = {
                k: v.get("status", "unknown") for k, v in checks.items() if isinstance(v, dict)
            }
            services["navigator"] = {
                "status": nav_status,
                "port": 8000,
                "subsystems": subsystems,
                "version": data.get("version", "unknown"),
            }
    except Exception:
        services["navigator"] = {"status": "offline", "port": 8000}

    # Check Vortex Frontend (:5173 dev / :3000 prod)
    vortex_frontend_port = None
    for port in [5173, 3000]:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    services["vortex_frontend"] = {
                        "status": "healthy",
                        "port": port,
                        "label": "Vortex UI (React)",
                    }
                    vortex_frontend_port = port
                    break
        except Exception:
            continue
    if vortex_frontend_port is None:
        services["vortex_frontend"] = {
            "status": "offline",
            "port": 5173,
            "label": "Vortex UI (React)",
        }

    # Check Alpha Arena (:8502)
    try:
        req = urllib.request.Request("http://localhost:8502/healthz")
        with urllib.request.urlopen(req, timeout=2) as resp:
            services["alpha_arena"] = {
                "status": "healthy" if resp.status == 200 else "degraded",
                "port": 8502,
                "label": "Alpha Arena (Streamlit)",
            }
    except Exception:
        # Streamlit healthz may 200 but not JSON — just check connectivity
        try:
            req = urllib.request.Request("http://localhost:8502/")
            with urllib.request.urlopen(req, timeout=2) as resp:
                services["alpha_arena"] = {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "port": 8502,
                    "label": "Alpha Arena (Streamlit)",
                }
        except Exception:
            services["alpha_arena"] = {
                "status": "offline",
                "port": 8502,
                "label": "Alpha Arena (Streamlit)",
            }

    # Check Cortex Runtime API (:8003)
    try:
        req = urllib.request.Request("http://localhost:8003/api/v1/runtime/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            services["cortex_runtime"] = {
                "status": "healthy" if data.get("status") == "healthy" else "degraded",
                "port": 8003,
                "label": "Cortex Runtime API",
            }
    except Exception:
        services["cortex_runtime"] = {
            "status": "offline",
            "port": 8003,
            "label": "Cortex Runtime API",
        }

    # Check Mission Control site (:3001)
    try:
        req = urllib.request.Request("http://localhost:3001/")
        with urllib.request.urlopen(req, timeout=2) as resp:
            services["mission_control"] = {
                "status": "healthy" if resp.status == 200 else "degraded",
                "port": 3001,
            }
    except Exception:
        services["mission_control"] = {"status": "offline", "port": 3001}

    # Test metrics from ~/.cortex/metrics/tests.json
    tests_file = Path.home() / ".cortex" / "metrics" / "tests.json"
    if tests_file.exists():
        try:
            test_data = json.loads(tests_file.read_text())
            total_failed = sum(
                v.get("failed", 0) for v in test_data.values() if isinstance(v, dict)
            )
            services["tests"] = {
                "total_failures": total_failed,
                "projects": {
                    k: {"passed": v.get("passed", 0), "failed": v.get("failed", 0)}
                    for k, v in test_data.items()
                    if isinstance(v, dict)
                },
            }
        except Exception:
            pass

    # EMOS readiness from ~/.cortex/metrics/emos.json
    emos_file = Path.home() / ".cortex" / "metrics" / "emos.json"
    if emos_file.exists():
        try:
            emos_data = json.loads(emos_file.read_text())
            pairs = emos_data.get("pairs", {})
            threshold = 2000
            services["emos"] = {
                "pairs": pairs,
                "threshold": threshold,
                "ready_models": [m for m, c in pairs.items() if c >= threshold],
                "timestamp": emos_data.get("timestamp"),
            }
        except Exception:
            pass

    # Overall status
    statuses = [s.get("status") for s in services.values() if isinstance(s, dict) and "status" in s]
    overall = "healthy" if all(s == "healthy" for s in statuses) else "degraded"

    return {"overall": overall, "services": services}


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
        anomalies = await asyncio.to_thread(anomaly_mgr.detect_all, context=context)

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


# Intelligence routes (query, reason, recommendations, alias) extracted to
# api/routes/intelligence.py.
from api.routes.intelligence import router as _intelligence_router

app.include_router(_intelligence_router)






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
        anomalies = await asyncio.to_thread(anomaly_mgr.detect_all, context=context)

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

        serialized = [
            {
                "id": a.anomaly_id,
                "type": getattr(a.anomaly_type, "value", str(a.anomaly_type)),
                "severity": getattr(a.severity, "value", str(a.severity)),
                "title": a.title,
                "description": a.description,
                "recommendation": a.remediation,
                "detected_at": (
                    a.detected_at.isoformat()
                    if hasattr(a.detected_at, "isoformat")
                    else str(a.detected_at)
                    if a.detected_at
                    else None
                ),
                "source": "anomaly_manager",
            }
            for a in anomalies
        ]

        # Merge proactive ActionBroker interventions
        try:
            from engines.broker import ActionBroker

            broker = ActionBroker()
            for i in broker.get_pending():
                sev = getattr(i.severity, "value", str(i.severity))
                itype = getattr(i.type, "value", str(i.type))
                if severity and sev.upper() != severity.upper():
                    continue
                if anomaly_type and itype != anomaly_type:
                    continue
                serialized.append(
                    {
                        "id": i.id,
                        "type": itype,
                        "severity": sev,
                        "title": i.title,
                        "description": i.description,
                        "recommendation": (
                            i.suggested_action.title if i.suggested_action else None
                        ),
                        "detected_at": i.timestamp.isoformat() if i.timestamp else None,
                        "source": "action_broker",
                    }
                )
        except (ImportError, Exception):
            pass  # ActionBroker is optional

        return {"count": len(serialized), "anomalies": serialized}
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


# /batches routes extracted to api/routes/batch.py.
from api.routes.batch import router as _batch_router

app.include_router(_batch_router)


# /queue routes extracted to api/routes/queue.py.
from api.routes.queue import router as _queue_router

app.include_router(_queue_router)


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
    """List available projects with status, detected from filesystem."""
    import subprocess

    workspace = Path.home() / "Dev"
    projects = []

    # Project definitions: (dir_name, display_name, test_dir)
    project_defs = [
        ("Vortex/backend", "Vortex Backend", "Vortex/backend/tests"),
        ("Vortex/frontend", "Vortex Frontend", "Vortex/frontend/src"),
        ("cortex", "Cortex", "cortex/tests"),
        ("alpha_arena", "Alpha Arena", "alpha_arena/tests"),
        ("pupil", "Pupil", "pupil/tests"),
    ]

    for dir_name, display_name, test_dir in project_defs:
        project_path = workspace / dir_name
        if not project_path.exists():
            continue

        # Get last commit touching this directory
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


# ============================================================================
# V2 Intelligence Endpoints (lazy-import for fast startup)
# ============================================================================


@app.get("/v2/outcomes")
async def get_v2_outcomes(
    project: Optional[str] = Query(None, description="Filter by project"),
    days: int = Query(7, description="Look back N days"),
    limit: int = Query(50, description="Max outcomes to return"),
) -> Dict[str, Any]:
    """Get recent outcomes from JSONL storage."""
    try:
        outcomes_file = Path.home() / ".cortex" / "model_outcomes.jsonl"
        if not outcomes_file.exists():
            return {"outcomes": [], "total": 0}

        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        with open(outcomes_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry.get("timestamp", ""))
                if ts < cutoff:
                    continue
                if project and entry.get("project_name") != project:
                    continue
                entries.append(entry)
        return {"outcomes": entries[-limit:], "total": len(entries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/outcomes/stats")
async def get_v2_outcome_stats(
    project: Optional[str] = Query(None, description="Filter by project"),
    days: int = Query(30, description="Look back N days"),
) -> Dict[str, Any]:
    """Get outcome statistics for compound learning measurement."""
    try:
        outcomes_file = Path.home() / ".cortex" / "model_outcomes.jsonl"
        if not outcomes_file.exists():
            return {"by_model": {}, "total_outcomes": 0, "days": days}

        cutoff = datetime.now() - timedelta(days=days)
        entries = []
        with open(outcomes_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = datetime.fromisoformat(entry.get("timestamp", ""))
                if ts < cutoff:
                    continue
                if project and entry.get("project_name") != project:
                    continue
                entries.append(entry)

        by_model: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            m = e.get("model_used", "unknown")
            if m not in by_model:
                by_model[m] = {"total": 0, "success": 0, "failed": 0, "tokens": 0}
            by_model[m]["total"] += 1
            if e.get("outcome") == "success":
                by_model[m]["success"] += 1
            elif e.get("outcome") == "failed":
                by_model[m]["failed"] += 1
            by_model[m]["tokens"] += e.get("tokens_used", 0)
        for stats in by_model.values():
            if stats["total"]:
                stats["success_rate"] = round(stats["success"] / stats["total"], 3)

        return {"by_model": by_model, "total_outcomes": len(entries), "days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/graph/search")
async def search_v2_graph(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Max results"),
) -> Dict[str, Any]:
    """Search the V2 context graph (engines/synthesis.py ContextGraph) for patterns, projects, and outcomes."""
    try:
        from cortex.engines.synthesis import ContextGraph

        graph = ContextGraph()
        nodes = graph.query(query, limit=limit)
        return {
            "results": [
                {
                    "id": n.id,
                    "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                    "name": n.name,
                    "data": n.data,
                    "updated_at": (
                        n.updated_at.isoformat()
                        if hasattr(n.updated_at, "isoformat")
                        else str(n.updated_at)
                    ),
                }
                for n in nodes
            ],
            "total": len(nodes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/graph/stats")
async def get_v2_graph_stats() -> Dict[str, Any]:
    """Get V2 context graph statistics (node/edge counts by type)."""
    try:
        from cortex.engines.synthesis import ContextGraph

        graph = ContextGraph()
        return graph.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/compound-health")
async def get_compound_health() -> Dict[str, Any]:
    """Get compound loop health metrics — outcomes, graph, memory, context."""
    try:
        from cortex.measurement.compound_metrics import full_report

        return full_report()
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"measurement module not available: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Sessions — Claude Code session visibility
# ============================================================================

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
BRIEFING_EXECUTIONS_DIR = Path.home() / ".cortex" / "briefing"
BRIEFING_EXECUTIONS_FILE = BRIEFING_EXECUTIONS_DIR / "executions.jsonl"


def _append_briefing_execution(record: Dict[str, Any]) -> None:
    BRIEFING_EXECUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    with BRIEFING_EXECUTIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _read_briefing_executions(limit: int = 20) -> List[Dict[str, Any]]:
    if not BRIEFING_EXECUTIONS_FILE.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with BRIEFING_EXECUTIONS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)
    return rows[:limit]


@app.post("/briefing/executions")
async def record_briefing_execution(payload: BriefingExecutionRequest) -> Dict[str, Any]:
    """Record a briefing recommendation execution event."""
    try:
        recorded_at = datetime.now(tz=timezone.utc).isoformat()
        record = {
            "execution_id": payload.execution_id,
            "recommendation_id": payload.recommendation_id,
            "recommendation_title": payload.recommendation_title,
            "project": payload.project,
            "mode": payload.mode,
            "status": payload.status,
            "source_version": payload.source_version,
            "metadata": payload.metadata or {},
            "recorded_at": recorded_at,
        }
        _append_briefing_execution(record)
        return {"status": "recorded", "execution": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/briefing/executions")
async def list_briefing_executions(
    limit: int = Query(20, ge=1, le=200, description="Max executions to return"),
) -> Dict[str, Any]:
    """List recent briefing execution events, newest first."""
    try:
        executions = _read_briefing_executions(limit=limit)
        return {"executions": executions, "count": len(executions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# /sessions, /session/resume-context, /session/delta extracted to api/routes/sessions.py.
from api.routes.sessions import router as _sessions_router

app.include_router(_sessions_router)


# ============================================================================
# TaskBoard — Spec-driven task management
# ============================================================================

# Taskboard storage, models, and routes have been extracted to
# api/routes/taskboard.py and are wired in via app.include_router below.
from api.routes.taskboard import router as _taskboard_router

app.include_router(_taskboard_router)


# ============================================================================
# Guardian endpoints — extracted to api/routes/guardian.py
# ============================================================================
# The 6 guardian routes (claim, release, status, snapshot, snapshots, recover)
# now live in api/routes/guardian.py and are mounted below via
# app.include_router. Paths and response shapes are unchanged from pre-split.

from api.routes.guardian import router as _guardian_router

app.include_router(_guardian_router)

# ============================================================================
# Signal Bus Endpoint
# ============================================================================


def _get_api_key() -> Optional[str]:
    """Read configured API key from env or ~/.cortex/api_key."""
    key = os.environ.get("CORTEX_API_KEY")
    if key:
        return key
    key_file = Path.home() / ".cortex" / "api_key"
    if key_file.is_file():
        return key_file.read_text().strip() or None
    return None


def _verify_signal_auth(request: "Request") -> None:
    """Verify caller is authorised to inject signals.

    Policy:
      - If CORTEX_API_KEY (env or file) is set, require Bearer token match.
      - If no key configured, allow localhost-only (127.0.0.1 / ::1).
    Raises HTTPException(401) on failure.
    """
    api_key = _get_api_key()
    if api_key:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        if auth_header[7:] != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    else:
        # No key configured — restrict to localhost
        client_host = request.client.host if request.client else None
        if client_host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(
                status_code=401,
                detail="No API key configured; only localhost access allowed",
            )


class SignalAbsorbRequest(BaseModel):
    """Request model for absorbing a workspace signal via HTTP."""

    source: str = Field(..., description="Signal source: claude_code, iterm, git, manual, etc.")
    project: str = Field(..., description="Project name")
    workstream: str = Field(default="build", description="Work phase: build, plan, test, etc.")
    content_type: str = Field(..., description="Content type: idea, decision, code, insight, error")
    content: str = Field(..., description="Signal content")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence 0-1")
    context: Dict[str, Any] = Field(default_factory=dict, description="Extra context")


_signal_bus: Optional[Any] = None


def get_signal_bus():
    """Get or create the UniversalSignalBus instance."""
    global _signal_bus
    if _signal_bus is None:
        try:
            from cortex.engines.universal_signal_bus import UniversalSignalBus

            _signal_bus = UniversalSignalBus()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to initialize signal bus: {e}")
    return _signal_bus


@app.post("/signal/absorb")
async def absorb_signal(request: Request, payload: SignalAbsorbRequest) -> Dict[str, Any]:
    """
    Absorb a workspace signal from any tool into the Universal Signal Bus.

    Fan-out to WorkstreamOrchestrator, SynthesisCore, and bus event log.
    Returns immediately — never blocks the caller.

    Auth: Bearer token (CORTEX_API_KEY env / ~/.cortex/api_key) or localhost-only.

    Example:
        POST /signal/absorb
        Authorization: Bearer <key>
        {"source": "iterm", "project": "vortex", "content_type": "insight",
         "content": "HRRR wins wind_speed at all lead times today"}
    """
    _verify_signal_auth(request)
    try:
        from cortex.engines.workstream_orchestrator import (
            SignalSource,
            WorkspaceSignal,
            WorkstreamPhase,
        )

        # Map string values to enums with safe fallback
        try:
            source_enum = SignalSource(payload.source)
        except ValueError:
            source_enum = SignalSource.MANUAL

        try:
            phase_enum = WorkstreamPhase(payload.workstream)
        except ValueError:
            phase_enum = WorkstreamPhase.BUILD

        signal = WorkspaceSignal(
            source=source_enum,
            timestamp=datetime.now(),
            project=payload.project,
            workstream=phase_enum,
            content_type=payload.content_type,
            content=payload.content,
            context=payload.context,
            confidence=payload.confidence,
        )

        bus = get_signal_bus()
        bus.absorb(signal)

        return {
            "status": "absorbed",
            "signal_id": signal.signal_id,
            "project": payload.project,
            "source": payload.source,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signal/bus-stats")
async def get_bus_stats() -> Dict[str, Any]:
    """Get Universal Signal Bus event log statistics."""
    try:
        bus = get_signal_bus()
        return bus.get_bus_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Conductor — Human-AI Collaboration Cockpit
# ============================================================================

WORKSPACE = Path(os.environ.get("CORTEX_DEV_ROOT", str(Path.home() / "Dev")))
# Claude encodes project paths as a flattened directory under
# ~/.claude/projects/, e.g. /Users/foo/Dev → -Users-foo-Dev.
# Derive from WORKSPACE rather than hardcoding the maintainer's machine name.
MEMORY_FILE = (
    Path.home()
    / ".claude"
    / "projects"
    / f"-{str(WORKSPACE).replace('/', '-').lstrip('-')}"
    / "memory"
    / "MEMORY.md"
)
GOALS_FILE = WORKSPACE / "GOALS.md"
CLAUDE_MD_FILE = WORKSPACE / "CLAUDE.md"
NEXT_SESSION_FILES = {
    "cortex": WORKSPACE / "cortex" / ".next_session.md",
    "vortex": WORKSPACE / "Vortex" / "backend" / ".next_session.md",
    "alpha_arena": WORKSPACE / "alpha_arena" / ".next_session.md",
}


# Conductor routes (startup, compose, templates, history) extracted to
# api/routes/conductor.py. The router below registers all 4 paths plus their
# request models (ConductorStartupRequest, PromptComposeRequest) and the
# CONDUCTOR_PROJECTS / PROMPT_TEMPLATES constants that ship with it.
from api.routes.conductor import router as _conductor_router

app.include_router(_conductor_router)


# Meta-layer compounding risk routes extracted to api/routes/meta.py.
from api.routes.meta import router as _meta_router

app.include_router(_meta_router)




# ============================================================================
# Co-Navigator Endpoints
# ============================================================================

_docs_tree_cache: Dict[str, Any] = {"data": None, "timestamp": 0}
_predictions_cache: Dict[str, Any] = {"data": None, "timestamp": 0}
# _heatmap_cache moved to api/routes/activity.py with its consumer.

DOCS_INDEX = Path.home() / "Dev" / "DOCS_INDEX.md"
OUTCOMES_FILE = Path.home() / ".cortex" / "outcomes.jsonl"
DECISIONS_FILE = Path.home() / ".cortex" / "decisions.jsonl"


@app.get("/docs/tree")
async def get_docs_tree() -> Dict[str, Any]:
    """Parse ~/Dev/DOCS_INDEX.md into a JSON tree of project documentation."""
    import re

    now = time.time()
    if _docs_tree_cache["data"] and (now - _docs_tree_cache["timestamp"]) < 300:
        result = _docs_tree_cache["data"].copy()
        result["cached"] = True
        return result

    try:
        if not DOCS_INDEX.exists():
            raise HTTPException(status_code=404, detail="DOCS_INDEX.md not found")

        content = DOCS_INDEX.read_text(encoding="utf-8")
        projects: List[Dict[str, Any]] = []
        current_project: Optional[Dict[str, Any]] = None
        total_docs = 0

        for line in content.split("\n"):
            # Match project headers (### or ##)
            header_match = re.match(r"^#{2,3}\s+(.+)$", line.strip())
            if header_match:
                if current_project:
                    projects.append(current_project)
                current_project = {"name": header_match.group(1).strip(), "docs": []}
                continue

            # Match table rows: | Doc | Location | Purpose |
            if current_project and line.strip().startswith("|") and "---" not in line:
                cols = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cols) >= 2 and cols[0] and not cols[0].lower().startswith("doc"):
                    doc_entry: Dict[str, Any] = {
                        "title": cols[0],
                        "path": cols[1] if len(cols) > 1 else "",
                    }
                    if len(cols) > 2:
                        doc_entry["location"] = cols[2]
                    current_project["docs"].append(doc_entry)
                    total_docs += 1

        if current_project:
            projects.append(current_project)

        result = {
            "projects": projects,
            "total_docs": total_docs,
            "cached": False,
        }
        _docs_tree_cache["data"] = result
        _docs_tree_cache["timestamp"] = now
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse docs tree: {e}")


@app.get("/docs/content")
async def get_docs_content(
    path: str = Query(..., description="File path relative to ~/Dev/"),
) -> Dict[str, Any]:
    """Read a markdown file and return content + metadata."""
    try:
        base = Path.home() / "Dev"
        resolved = (base / path).resolve()

        # Security: ensure resolved path is under ~/Dev/
        if not str(resolved).startswith(str(base.resolve())):
            raise HTTPException(status_code=403, detail="Path escapes workspace boundary")

        if not resolved.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        if not resolved.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        stat = resolved.stat()
        size = stat.st_size

        # Limit content to 100KB
        if size > 100 * 1024:
            content = resolved.read_text(encoding="utf-8")[: 100 * 1024]
        else:
            content = resolved.read_text(encoding="utf-8")

        return {
            "path": str(resolved.relative_to(base)),
            "content": content,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size": size,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


def _check_health(name: str, url: str) -> Dict[str, Any]:
    """Check HTTP health of a service."""
    try:
        req = urllib.request.Request(url, method="GET")
        start = time.time()
        with urllib.request.urlopen(req, timeout=2) as resp:
            return {
                "name": name,
                "url": url,
                "status": resp.status,
                "latency_ms": round((time.time() - start) * 1000),
                "healthy": True,
            }
    except Exception:
        return {
            "name": name,
            "url": url,
            "status": 0,
            "latency_ms": 0,
            "healthy": False,
        }


@app.get("/services/status")
async def get_services_status() -> Dict[str, Any]:
    """Aggregate service status from launchctl, crontab, and HTTP health checks."""
    try:
        # LaunchD services
        launchd_entries: List[Dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n")[1:]:  # skip header
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        label = parts[2]
                        if any(
                            label.startswith(prefix)
                            for prefix in (
                                "com.cortex.",
                                "com.vortex.",
                                "com.alphaarena.",
                            )
                        ):
                            launchd_entries.append(
                                {
                                    "label": label,
                                    "pid": parts[0] if parts[0] != "-" else None,
                                    "exit_code": parts[1] if parts[1] != "-" else None,
                                    "running": parts[0] != "-",
                                }
                            )
        except Exception:
            pass

        # Crontab entries
        cron_entries: List[Dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(None, 5)
                        if len(parts) >= 6:
                            schedule = " ".join(parts[:5])
                            command = parts[5]
                            # Derive project from command path
                            project = "unknown"
                            if "/Dev/" in command:
                                seg = command.split("/Dev/")[1].split("/")[0]
                                project = seg
                            cron_entries.append(
                                {
                                    "schedule": schedule,
                                    "command": command,
                                    "project": project,
                                }
                            )
                        else:
                            cron_entries.append(
                                {
                                    "schedule": line,
                                    "command": line,
                                    "project": "unknown",
                                }
                            )
        except Exception:
            pass

        # HTTP health checks
        health_checks = [
            _check_health("vortex-backend", "http://127.0.0.1:8000/api/v2/health"),
            # Bridge marks itself as healthy (can't self-check without deadlock)
            {
                "name": "cortex-bridge",
                "url": "http://127.0.0.1:8765/health",
                "status": 200,
                "latency_ms": 0,
                "healthy": True,
            },
            _check_health("cortex-site", "http://127.0.0.1:3001/"),
        ]

        return {
            "launchd": launchd_entries,
            "cron": cron_entries,
            "health": health_checks,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {e}")


@app.get("/predictions/current")
async def get_predictions_current() -> Dict[str, Any]:
    """Aggregate predictions from existing data sources."""
    now = time.time()
    if _predictions_cache["data"] and (now - _predictions_cache["timestamp"]) < 60:
        return _predictions_cache["data"]

    try:
        predictions: List[Dict[str, Any]] = []

        # --- Read outcomes for pattern analysis ---
        recent_outcomes: List[Dict[str, Any]] = []
        if OUTCOMES_FILE.exists():
            try:
                lines = OUTCOMES_FILE.read_text(encoding="utf-8").strip().split("\n")
                for line in lines[-100:]:
                    try:
                        recent_outcomes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass

        # --- Read GOALS.md for active priorities ---
        goals_content = ""
        goals_file = WORKSPACE / "GOALS.md"
        if goals_file.exists():
            try:
                goals_content = goals_file.read_text(encoding="utf-8")[:5000]
            except Exception:
                pass

        # --- Git status for uncommitted files ---
        uncommitted_files: List[str] = []
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=str(WORKSPACE),
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        uncommitted_files.append(line.strip())
        except Exception:
            pass

        # --- Recent git activity for hot files ---
        hot_files: Dict[str, int] = {}
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--stat",
                    "--since=7 days ago",
                    "--format=|COMMIT|%H",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=str(WORKSPACE),
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if (
                        "|" in line
                        and ("+" in line or "-" in line)
                        and not line.startswith("|COMMIT|")
                    ):
                        file_part = line.split("|")[0].strip()
                        if file_part:
                            hot_files[file_part] = hot_files.get(file_part, 0) + 1
        except Exception:
            pass

        # --- Check batch queue ---
        batch_dir = Path.home() / ".cortex" / "batch"
        batch_count = 0
        if batch_dir.exists():
            batch_count = len(list(batch_dir.glob("*.json")))

        # --- Generate predictions ---

        # 1. QA prediction: uncommitted files + outcome patterns
        if uncommitted_files:
            failed_files = set()
            for outcome in recent_outcomes:
                if outcome.get("success") is False:
                    for f in outcome.get("files", []):
                        failed_files.add(f)

            at_risk = [f for f in uncommitted_files if any(ff in f for ff in failed_files)]
            confidence = 0.72 if at_risk else 0.55
            pred_text = f"{len(uncommitted_files)} uncommitted files detected" + (
                f", {len(at_risk)} overlap with past failures" if at_risk else ""
            )
            pred_id = f"pred_{hashlib.md5(f'qa_{pred_text}'.encode()).hexdigest()[:12]}"
            predictions.append(
                {
                    "id": pred_id,
                    "domain": "qa",
                    "prediction": pred_text,
                    "confidence": confidence,
                    "evidence": [
                        f"{len(uncommitted_files)} uncommitted changes",
                        f"{len(recent_outcomes)} recent outcomes analyzed",
                    ]
                    + ([f"{len(at_risk)} files overlap with prior failures"] if at_risk else []),
                    "scenarios": [
                        {
                            "name": "A: Safe",
                            "description": "Run full test suite before committing",
                            "risk": "low",
                            "effort": "20m",
                        },
                        {
                            "name": "B: Fast",
                            "description": "Commit with targeted tests only",
                            "risk": "medium",
                            "effort": "5m",
                        },
                        {
                            "name": "C: Thorough",
                            "description": "Run tests + review each changed file manually",
                            "risk": "low",
                            "effort": "45m",
                        },
                    ],
                }
            )

        # 2. Release prediction: batch queue + EMOS status
        pred_text = f"Batch queue: {batch_count} pending jobs"
        pred_id = f"pred_{hashlib.md5(f'release_{batch_count}'.encode()).hexdigest()[:12]}"
        predictions.append(
            {
                "id": pred_id,
                "domain": "release",
                "prediction": pred_text,
                "confidence": 0.65 if batch_count == 0 else 0.50,
                "evidence": [
                    f"{batch_count} batch jobs pending",
                    "Check EMOS calibration status before release",
                ],
                "scenarios": [
                    {
                        "name": "A: Safe",
                        "description": "Wait for batch queue to drain, then release",
                        "risk": "low",
                        "effort": "30m",
                    },
                    {
                        "name": "B: Fast",
                        "description": "Release now, batch jobs run post-deploy",
                        "risk": "medium",
                        "effort": "5m",
                    },
                    {
                        "name": "C: Thorough",
                        "description": "Drain queue, run validation suite, then release",
                        "risk": "low",
                        "effort": "60m",
                    },
                ],
            }
        )

        # 3. Architecture prediction: GOALS.md active items
        if goals_content:
            active_lines = [
                l.strip()
                for l in goals_content.split("\n")
                if l.strip().startswith("- [") and "[ ]" in l
            ]
            pred_text = f"{len(active_lines)} active goals in GOALS.md"
            pred_id = f"pred_{hashlib.md5(f'arch_{len(active_lines)}'.encode()).hexdigest()[:12]}"
            predictions.append(
                {
                    "id": pred_id,
                    "domain": "architecture",
                    "prediction": pred_text,
                    "confidence": 0.60,
                    "evidence": [
                        f"{len(active_lines)} unchecked goals",
                        "Cross-reference with project health metrics",
                    ],
                    "scenarios": [
                        {
                            "name": "A: Safe",
                            "description": "Prioritize top 3 goals, defer the rest",
                            "risk": "low",
                            "effort": "15m",
                        },
                        {
                            "name": "B: Fast",
                            "description": "Pick highest-impact goal and execute",
                            "risk": "medium",
                            "effort": "0m",
                        },
                        {
                            "name": "C: Thorough",
                            "description": "Review all goals against current capacity",
                            "risk": "low",
                            "effort": "45m",
                        },
                    ],
                }
            )

        # 4. Dev prediction: hot files from git activity
        if hot_files:
            sorted_hot = sorted(hot_files.items(), key=lambda x: x[1], reverse=True)[:5]
            hottest = sorted_hot[0] if sorted_hot else ("unknown", 0)
            pred_text = f"Hot file: {hottest[0]} ({hottest[1]} changes in 7d)"
            pred_id = f"pred_{hashlib.md5(f'dev_{hottest[0]}'.encode()).hexdigest()[:12]}"
            predictions.append(
                {
                    "id": pred_id,
                    "domain": "dev",
                    "prediction": pred_text,
                    "confidence": 0.70,
                    "evidence": [
                        f"{len(hot_files)} files changed in last 7 days",
                        f"Top: {', '.join(f[0] for f in sorted_hot[:3])}",
                    ],
                    "scenarios": [
                        {
                            "name": "A: Safe",
                            "description": "Add tests for hot files before next change",
                            "risk": "low",
                            "effort": "30m",
                        },
                        {
                            "name": "B: Fast",
                            "description": "Continue development, test later",
                            "risk": "medium",
                            "effort": "0m",
                        },
                        {
                            "name": "C: Thorough",
                            "description": "Refactor hot files to reduce churn",
                            "risk": "low",
                            "effort": "60m",
                        },
                    ],
                }
            )

        result = {
            "predictions": predictions,
            "generated_at": datetime.now().isoformat(),
        }
        _predictions_cache["data"] = result
        _predictions_cache["timestamp"] = now
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate predictions: {e}")


# /decisions/record extracted to api/routes/decisions.py.
from api.routes.decisions import router as _decisions_router

app.include_router(_decisions_router)


# /activity/heatmap route + its _heatmap_cache extracted to api/routes/activity.py.
from api.routes.activity import router as _activity_router


@app.post("/decisions/journal")
async def journal_decision(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Record an architectural/engineering decision from MCP tools."""
    try:
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        decision_id = f"dec_{int(time.time())}"
        entry = {
            "decision_id": decision_id,
            "decision": payload.get("decision", ""),
            "context": payload.get("context", ""),
            "alternatives": payload.get("alternatives", ""),
            "rationale": payload.get("rationale", ""),
            "timestamp": datetime.now().isoformat(),
            "source": "mcp",
        }
        with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return {"recorded": True, "decision_id": decision_id, "timestamp": entry["timestamp"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to journal decision: {e}")

app.include_router(_activity_router)


# ============================================================================
# Temporal Memory Retrieval
# ============================================================================


@app.get("/memory/temporal")
async def get_temporal_memory(
    since: Optional[str] = Query(
        None, description="Start: '3d', 'yesterday', '2026-04-01', 'last tuesday'"
    ),
    until: Optional[str] = Query(None, description="End: ISO date or None (defaults to now)"),
    text: Optional[str] = Query(None, description="Substring filter"),
    sources: Optional[str] = Query(
        None, description="Comma-separated: interaction,reflection,alert,digest"
    ),
    limit: int = Query(50, ge=1, le=500),
):
    """Query Cortex memory stores by time window."""
    try:
        from memory.temporal import TemporalQuery

        tq = TemporalQuery()
        src_list = [s.strip() for s in sources.split(",")] if sources else None
        summary = tq.summarise(since=since, until=until, text=text)
        if src_list:
            summary["entries"] = [e for e in summary["entries"] if e.get("_source") in src_list]
        summary["entries"] = summary["entries"][:limit]
        summary["total"] = len(summary["entries"])
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/providers/status")
async def get_providers_status():
    """Probe all inference providers — Anthropic API + local (Ollama, MLX)."""
    try:
        from supervisor.local_provider import probe_all_local

        local = probe_all_local()
        anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return {
            "anthropic": {"available": anthropic_ok, "backend": "anthropic"},
            "local": local,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/goals/stale-items")
async def get_stale_items():
    """Return GOALS.md items older than threshold days."""
    try:
        from briefing import detect_stale_items

        items = detect_stale_items()
        return {"stale_items": items, "threshold_days": 7}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("Starting Cortex Bridge API on http://127.0.0.1:8765")
    print("API docs: http://127.0.0.1:8765/docs")
    uvicorn.run(app, host="127.0.0.1", port=8765)
