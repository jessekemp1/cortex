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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add cortex to path for imports
cortex_root = Path(__file__).parent.parent
sys.path.insert(0, str(cortex_root.parent))

try:
    from fastapi import FastAPI, HTTPException, Query, Request
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


class GuardianClaimRequest(BaseModel):
    """Request to claim a file for exclusive editing."""

    file: str = Field(..., description="Absolute path to file")
    agent_id: str = Field(..., description="Unique agent session identifier")
    ttl: int = Field(default=300, description="Claim TTL in seconds (max 1800)")


class GuardianReleaseRequest(BaseModel):
    """Request to release a claimed file."""

    file: str = Field(..., description="Absolute path to file")
    agent_id: str = Field(..., description="Agent session identifier")


class GuardianSnapshotRequest(BaseModel):
    """Request to create a manual snapshot."""

    files: List[str] = Field(
        default_factory=list, description="Files to snapshot (empty = all claimed)"
    )
    reason: str = Field(default="manual", description="Reason for snapshot")


class GuardianRecoverRequest(BaseModel):
    """Request to restore a file from a snapshot."""

    file: str = Field(..., description="Absolute path to file to restore")
    snapshot_id: str = Field(..., description="Snapshot ID to restore from")


class StatusResponse(BaseModel):
    """Response model for status check."""

    status: str
    version: str
    available_projects: List[str]
    anomaly_count: int


class DecisionRecordRequest(BaseModel):
    """Request to record a user decision from the Co-Navigator UI."""

    prediction_id: str = Field(..., description="ID of the prediction this decision responds to")
    scenario_chosen: str = Field(..., description="Scenario label (e.g., 'A', 'B', 'C')")
    scenario_name: str = Field(..., description="Scenario description")
    domain: str = Field(
        ...,
        description="Prediction domain: dev, architecture, product, qa, release, research",
    )
    override_reason: Optional[str] = Field(
        default=None, description="Reason if user overrode all scenarios"
    )


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


class ReasonQuery(BaseModel):
    """Request model for reasoning queries (LLM-powered answers)."""

    question: str = Field(..., description="User's question in natural language")
    project: Optional[str] = Field(
        default=None, description="Project context (auto-detected if empty)"
    )


@app.post("/intelligence/reason")
async def reason_query(query: ReasonQuery) -> Dict[str, Any]:
    """
    Answer a question using gathered context + Claude API.

    Unlike /intelligence/query (pattern retrieval), this endpoint actually
    reasons about the question by gathering relevant context and sending
    it to an LLM for synthesis.
    """
    import subprocess

    question = query.question
    project = query.project

    # Auto-detect project from keywords if not specified
    if not project:
        q_lower = question.lower()
        project_kw = {
            "vortex": [
                "vortex",
                "grib",
                "forecast",
                "ensemble",
                "emos",
                "weather",
                "wind",
                "wave",
                "buoy",
                "frontend",
                "backend",
                "hrrr",
                "gfs",
                "ecmwf",
            ],
            "alpha_arena": ["arena", "trading", "trade", "kelly", "strategy", "etf"],
            "cortex": ["cortex", "bridge", "cra", "orchestrat", "memory", "mcp", "gateway"],
            "pupil": ["pupil", "simulation", "recession"],
        }
        scores = {p: sum(1 for kw in kws if kw in q_lower) for p, kws in project_kw.items()}
        project = max(scores, key=lambda k: scores[k])
        if scores[project] == 0:
            project = "cortex"

    # Gather context from multiple sources
    context_parts = []

    # 1. Portfolio status (real data)
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/python3", "scripts/portfolio_status.py", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/Users/jesse.kemp/Dev",
        )
        if result.returncode == 0:
            portfolio = json.loads(result.stdout)
            context_parts.append(f"PORTFOLIO STATUS:\n{json.dumps(portfolio, indent=2)}")
    except Exception:
        pass

    # 2. Service health
    try:
        bridge = get_bridge()
        health = bridge.get_portfolio_health_summary()
        if health:
            context_parts.append(f"SERVICE HEALTH:\n{json.dumps(health, indent=2, default=str)}")
    except Exception:
        pass

    # 3. Recent git activity for the detected project
    try:
        project_dirs = {
            "vortex": "Vortex/",
            "alpha_arena": "alpha_arena/",
            "cortex": "cortex/",
            "pupil": "pupil/",
        }
        proj_dir = project_dirs.get(project, "")
        if proj_dir:
            git_result = subprocess.run(
                ["git", "log", "--oneline", "-15", "--", proj_dir],
                capture_output=True,
                text=True,
                timeout=5,
                cwd="/Users/jesse.kemp/Dev",
            )
            if git_result.returncode == 0 and git_result.stdout.strip():
                context_parts.append(f"RECENT COMMITS ({project}):\n{git_result.stdout.strip()}")

            diff_result = subprocess.run(
                ["git", "diff", "--stat", "--", proj_dir],
                capture_output=True,
                text=True,
                timeout=5,
                cwd="/Users/jesse.kemp/Dev",
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                context_parts.append(
                    f"UNCOMMITTED CHANGES ({project}):\n{diff_result.stdout.strip()}"
                )
    except Exception:
        pass

    # 4. Cortex pattern retrieval (lightweight, for additional context)
    try:
        bridge = get_bridge()
        intel = bridge.query_intelligence(
            request=question,
            project=project,
            query_type="spec",
        )
        predictions = intel.get("context_predictions", [])
        if predictions:
            pred_text = "\n".join(
                f"- [{p.get('source', '?')}] {str(p.get('content', ''))[:200]}"
                for p in predictions[:3]
                if isinstance(p, dict)
            )
            if pred_text.strip():
                context_parts.append(f"CORTEX KNOWLEDGE:\n{pred_text}")
    except Exception:
        pass

    # 5. GOALS.md summary
    try:
        goals_path = Path("/Users/jesse.kemp/Dev/GOALS.md")
        if goals_path.exists():
            goals_text = goals_path.read_text()
            # Extract immediate actions section
            if "## Immediate Actions" in goals_text:
                actions_section = goals_text.split("## Immediate Actions")[1].split("##")[0]
                context_parts.append(f"GOALS - IMMEDIATE ACTIONS:\n{actions_section[:1500]}")
    except Exception:
        pass

    context_block = "\n\n---\n\n".join(context_parts) if context_parts else "No context gathered."

    # Call Claude API (haiku for speed + cost efficiency)
    try:
        import anthropic

        # Load API key from env or ~/.cortex/.env
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            env_file = Path.home() / ".cortex" / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.strip().startswith("export ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("'\"")
                        break
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = (
            "You are Cortex Intelligence, answering questions about a software portfolio. "
            "You have access to real-time project data provided below. "
            "Answer concisely and accurately based on the data. "
            "Use monospace-friendly formatting (no markdown headers, use dashes and indentation). "
            "If the data doesn't contain enough information to answer fully, say so honestly. "
            "Keep answers under 300 words."
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"CONTEXT:\n{context_block}\n\n---\n\nQUESTION: {question}",
                }
            ],
        )

        answer = message.content[0].text if message.content else "No response generated."
        tokens_used = message.usage.input_tokens + message.usage.output_tokens

        return {
            "answer": answer,
            "project": project,
            "sources_used": len(context_parts),
            "model": "claude-haiku-4-5",
            "tokens": tokens_used,
        }

    except Exception as e:
        return {
            "answer": f"LLM call failed: {e}\n\nFallback context:\n{context_block[:2000]}",
            "project": project,
            "sources_used": len(context_parts),
            "model": "fallback",
            "tokens": 0,
        }


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
        else:
            # Backward-compatible normalization for report-style recommendation payloads.
            normalized: List[Dict[str, Any]] = []

            next_action = recommendations.get("next_action")
            if isinstance(next_action, dict) and next_action.get("action"):
                normalized.append(
                    {
                        "project": next_action.get("project", project or "cortex"),
                        "priority": next_action.get("priority", "MEDIUM"),
                        "title": next_action.get("action"),
                        "type": next_action.get("type", "next_action"),
                    }
                )

            for item in recommendations.get("priority_projects", []) or []:
                if isinstance(item, dict):
                    normalized.append(
                        {
                            "project": item.get("project", project or "cortex"),
                            "priority": item.get("priority", "MEDIUM"),
                            "title": item.get("reason", "Priority project requires attention"),
                            "type": "priority_project",
                        }
                    )

            for alert in recommendations.get("risk_alerts", []) or []:
                if isinstance(alert, dict):
                    normalized.append(
                        {
                            "project": alert.get("project", project or "cortex"),
                            "priority": alert.get("severity", "MEDIUM"),
                            "title": alert.get("message", "Risk alert detected"),
                            "type": "risk_alert",
                        }
                    )

            recommendations["recommendations"] = normalized[:limit]

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
    """Get recent outcomes from OutcomeDetector (v2 compound learning)."""
    try:
        from cortex.v2.learning.outcomes import OutcomeDetector

        detector = OutcomeDetector()
        outcomes = detector.get_recent_outcomes(project=project, days=days)
        return {
            "outcomes": [o.to_dict() for o in outcomes[:limit]],
            "total": len(outcomes),
        }
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"v2 module not available: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/outcomes/stats")
async def get_v2_outcome_stats(
    project: Optional[str] = Query(None, description="Filter by project"),
    days: int = Query(30, description="Look back N days"),
) -> Dict[str, Any]:
    """Get outcome statistics for compound learning measurement."""
    try:
        from cortex.v2.learning.outcomes import OutcomeDetector

        detector = OutcomeDetector()
        return detector.get_outcome_stats(project=project, days=days)
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"v2 module not available: {e}")
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

            # Strip Claude project path prefix (format: -Users-<username>-<path>)
            import re

            project_name = re.sub(r"^-Users-[^-]+-", "", project_dir.name).replace("-", "/")

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
# Guardian Endpoints
# ============================================================================


def _get_guardian():
    """Lazy-import Guardian singleton to avoid startup cost."""
    from cortex.guardian import get_guardian

    return get_guardian()


@app.post("/guardian/claim")
async def guardian_claim(req: GuardianClaimRequest) -> Dict[str, Any]:
    """Claim a file for exclusive editing."""
    ttl = min(req.ttl, 1800)  # cap at 30 minutes
    guardian = _get_guardian()
    result = guardian.claim(req.file, req.agent_id, ttl=ttl)

    if result.success:
        snaps = guardian.list_snapshots(limit=1)
        snap_id = snaps[0].snapshot_id if snaps else ""
        project = guardian.router.resolve(req.file).name
        claim = guardian.claims.get_claim(req.file)
        return {
            "claimed": True,
            "file": req.file,
            "agent_id": req.agent_id,
            "expires_in": round(claim.remaining_seconds) if claim else ttl,
            "project": project,
            "snapshot_id": snap_id,
        }

    conflict = result.conflict
    return {
        "claimed": False,
        "file": req.file,
        "holder": conflict.agent_id if conflict else "unknown",
        "expires_in": round(conflict.remaining_seconds) if conflict else 0,
        "message": result.message,
    }


@app.post("/guardian/release")
async def guardian_release(req: GuardianReleaseRequest) -> Dict[str, Any]:
    """Release a claimed file."""
    guardian = _get_guardian()
    result = guardian.release(req.file, req.agent_id)
    return {
        "released": result.released,
        "file": req.file,
        "agent_id": req.agent_id,
        "message": result.message,
    }


@app.get("/guardian/status")
async def guardian_status() -> Dict[str, Any]:
    """Get Guardian health and claim status."""
    guardian = _get_guardian()
    return guardian.status()


@app.post("/guardian/snapshot")
async def guardian_snapshot(req: GuardianSnapshotRequest) -> Dict[str, Any]:
    """Create a manual snapshot of specified files."""
    guardian = _get_guardian()
    files = req.files
    if not files:
        active = guardian.claims.get_all_claims()
        files = list(active.keys())
    if not files:
        raise HTTPException(status_code=400, detail="No files specified and no active claims")

    info = guardian.snapshot(files, reason=req.reason)
    return {
        "snapshot_id": info.snapshot_id,
        "files_snapshotted": len(info.files),
        "reason": info.reason,
    }


@app.get("/guardian/snapshots")
async def guardian_list_snapshots(limit: int = Query(default=20)) -> Dict[str, Any]:
    """List available snapshots."""
    guardian = _get_guardian()
    snaps = guardian.list_snapshots(limit=limit)
    return {
        "snapshots": [
            {
                "snapshot_id": s.snapshot_id,
                "created_at": s.created_at,
                "reason": s.reason,
                "file_count": len(s.files),
                "files": s.files,
            }
            for s in snaps
        ],
        "total": len(guardian.snapshots._manifest),
        "ring_capacity": guardian.snapshots.max_size,
    }


@app.post("/guardian/recover")
async def guardian_recover(req: GuardianRecoverRequest) -> Dict[str, Any]:
    """Restore a file from a snapshot."""
    guardian = _get_guardian()
    result = guardian.recover(req.file, req.snapshot_id)

    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)

    return {
        "recovered": True,
        "file": result.file_path,
        "snapshot_id": result.snapshot_id,
        "bytes_restored": result.bytes_restored,
        "pre_recovery_snapshot": result.pre_recovery_snapshot_id,
    }


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

WORKSPACE = Path.home() / "Dev"
MEMORY_FILE = (
    Path.home() / ".claude" / "projects" / "-Users-jesse-kemp-Dev" / "memory" / "MEMORY.md"
)
GOALS_FILE = WORKSPACE / "GOALS.md"
CLAUDE_MD_FILE = WORKSPACE / "CLAUDE.md"
NEXT_SESSION_FILES = {
    "cortex": WORKSPACE / "cortex" / ".next_session.md",
    "vortex": WORKSPACE / "Vortex" / "backend" / ".next_session.md",
    "alpha_arena": WORKSPACE / "alpha_arena" / ".next_session.md",
}

# Project definitions for conductor
CONDUCTOR_PROJECTS = [
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


@app.get("/conductor/startup")
async def conductor_startup(
    project_id: Optional[str] = Query(None, description="Focus on specific project"),
) -> Dict[str, Any]:
    """
    Aggregated startup intelligence for the Conductor UI.

    Returns everything needed to start a productive session:
    - Project health overview
    - Git status (branch, uncommitted files)
    - .next_session.md content (if exists)
    - Active alerts and recommendations
    - Recent session history
    """
    import subprocess

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

        # Get last commit info
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

        # Count uncommitted changes in this project
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

        result["git"] = {
            "branch": branch,
            "changed_files": changed_files,
        }
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
        # Check all next_session files
        for pid, ns_file in NEXT_SESSION_FILES.items():
            if ns_file.exists():
                try:
                    mtime = ns_file.stat().st_mtime
                    age_hours = (time.time() - mtime) / 3600
                    if age_hours < 48:  # Only show if < 48h old
                        result["next_session"] = {
                            "project": pid,
                            "content": ns_file.read_text(encoding="utf-8")[:2000],
                            "age_hours": round(age_hours, 1),
                        }
                        break
                except Exception:
                    pass

    # 4. Memory snapshot (first 30 lines for quick overview)
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


@app.post("/conductor/compose")
async def conductor_compose_prompt(req: PromptComposeRequest) -> Dict[str, Any]:
    """
    Compose an optimized prompt based on intent, project, and context.

    Enriches the user's natural-language intent with:
    - Project-specific context (recent commits, state)
    - Intent level framing
    - Relevant .next_session content
    - Anti-patterns and gotchas for the project
    """
    import subprocess

    sections: List[str] = []

    # Intent level framing
    level_frames = {
        "advisory": "Research and recommend only. Do not modify any files.",
        "collaborative": "Propose changes and wait for my approval before executing.",
        "autonomous": "Execute end-to-end. Test, fix, and report results when done.",
        "supervisory": "Orchestrate sub-agents for parallel execution. Report aggregate results.",
    }
    frame = level_frames.get(req.intent_level, level_frames["collaborative"])

    # Find project info
    proj_info = next((p for p in CONDUCTOR_PROJECTS if p["id"] == req.project_id), None)

    # Header
    sections.append(f"**Intent Level**: {req.intent_level.upper()} — {frame}")
    if proj_info:
        sections.append(f"**Project**: {proj_info['name']} (`{proj_info['path']}`)")

    # User intent
    sections.append(f"\n## Task\n{req.intent}")

    # Project context
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

        # .next_session content
        ns_file = NEXT_SESSION_FILES.get(req.project_id)
        if ns_file and ns_file.exists():
            try:
                content = ns_file.read_text(encoding="utf-8")[:1000]
                sections.append(f"\n## Previous Session Context\n{content}")
            except Exception:
                pass

    composed = "\n".join(sections)
    token_estimate = len(composed.split()) * 2  # rough estimate

    # Persist to prompt history
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
        pass  # Non-critical — don't fail compose if history write fails

    return {
        "prompt": composed,
        "project": req.project_id,
        "intent_level": req.intent_level,
        "token_estimate": token_estimate,
    }


PROMPT_TEMPLATES = [
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


@app.get("/conductor/templates")
async def conductor_templates() -> Dict[str, Any]:
    """Get available prompt templates for the Prompt Composer."""
    return {"templates": PROMPT_TEMPLATES}


# ============================================================================
# Meta Layer — Examined Engineer
# ============================================================================


@app.get("/meta/compounding")
async def meta_compounding_project(
    project: str = Query(..., description="Project name, e.g. 'vortex-backend'"),
) -> Dict[str, Any]:
    """
    Compounding risk assessment for a project.

    Returns 6-month trajectory, rate (low/medium/high/critical), and the
    boring risk nobody is tracking. Part of the Examined Engineer meta layer.
    """
    try:
        from cortex.intelligence.analysis.compounding_risk import CompoundingRiskAssessor

        assessor = CompoundingRiskAssessor()
        risk = assessor.assess_project(project)
        return {
            "meta_layer": "compounding_risk",
            "assessed_at": datetime.now(tz=timezone.utc).isoformat(),
            **risk.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compounding risk assessment failed: {e}")


@app.get("/meta/compounding/portfolio")
async def meta_compounding_portfolio() -> Dict[str, Any]:
    """
    Compounding risk assessment for all known projects, sorted by severity.

    Surfaces the highest-risk project and any boring risks not tracked elsewhere.
    """
    try:
        from cortex.intelligence.analysis.compounding_risk import CompoundingRiskAssessor

        assessor = CompoundingRiskAssessor()
        risks = assessor.assess_portfolio()
        rate_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risks_sorted = sorted(risks, key=lambda r: rate_order.get(r.rate, 0), reverse=True)
        return {
            "meta_layer": "compounding_risk_portfolio",
            "assessed_at": datetime.now(tz=timezone.utc).isoformat(),
            "highest_risk": risks_sorted[0].target if risks_sorted else None,
            "projects": [r.to_dict() for r in risks_sorted],
            "boring_risks": [
                {"project": r.target, "risk": r.boring_risk} for r in risks_sorted if r.boring_risk
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Portfolio compounding assessment failed: {e}")


@app.get("/meta/compounding/file")
async def meta_compounding_file(
    path: str = Query(..., description="File path relative to repo root"),
) -> Dict[str, Any]:
    """
    Compounding risk assessment for a specific file.

    Uses caller count, churn rate, and test coverage as signals.
    """
    try:
        from cortex.intelligence.analysis.compounding_risk import CompoundingRiskAssessor

        assessor = CompoundingRiskAssessor()
        risk = assessor.assess_file(path)
        return {
            "meta_layer": "compounding_risk_file",
            "assessed_at": datetime.now(tz=timezone.utc).isoformat(),
            **risk.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File compounding assessment failed: {e}")


@app.get("/conductor/history")
async def conductor_prompt_history(
    limit: int = Query(default=20, ge=1, le=200, description="Number of recent entries to return"),
) -> Dict[str, Any]:
    """
    Return recent prompt composition history, newest-first.

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

    # Newest-first
    entries.reverse()
    total = len(entries)
    entries = entries[:limit]

    return {"entries": entries, "total": total}


# ============================================================================
# Co-Navigator Endpoints
# ============================================================================

_docs_tree_cache: Dict[str, Any] = {"data": None, "timestamp": 0}
_predictions_cache: Dict[str, Any] = {"data": None, "timestamp": 0}
_heatmap_cache: Dict[str, Any] = {"data": None, "timestamp": 0}

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


@app.post("/decisions/record")
async def record_decision(req: DecisionRecordRequest) -> Dict[str, Any]:
    """Record a user decision from the Co-Navigator UI."""
    try:
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        decision_id = f"dec_{int(time.time())}_{req.prediction_id[:8]}"
        entry = {
            "decision_id": decision_id,
            "prediction_id": req.prediction_id,
            "scenario_chosen": req.scenario_chosen,
            "scenario_name": req.scenario_name,
            "domain": req.domain,
            "override_reason": req.override_reason,
            "timestamp": datetime.now().isoformat(),
        }
        with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return {
            "recorded": True,
            "decision_id": decision_id,
            "timestamp": entry["timestamp"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record decision: {e}")


@app.get("/activity/heatmap")
async def get_activity_heatmap() -> Dict[str, Any]:
    """Codebase activity visualization data - file change frequency over 30 days."""
    now = time.time()
    if _heatmap_cache["data"] and (now - _heatmap_cache["timestamp"]) < 300:
        return _heatmap_cache["data"]

    try:
        file_changes: Dict[str, Dict[str, Any]] = {}

        result = subprocess.run(
            [
                "git",
                "log",
                "--name-only",
                "--since=30 days ago",
                "--format=|COMMIT|%ai",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(WORKSPACE),
        )

        if result.returncode == 0:
            current_date = ""
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("|COMMIT|"):
                    current_date = line.split("|")[2].strip() if len(line.split("|")) >= 3 else ""
                    continue

                # Each non-empty, non-COMMIT line is a file path
                file_part = line
                if file_part:
                    if file_part not in file_changes:
                        project = file_part.split("/")[0] if "/" in file_part else "root"
                        file_changes[file_part] = {
                            "path": file_part,
                            "changes_30d": 0,
                            "last_changed": current_date,
                            "project": project,
                        }
                    file_changes[file_part]["changes_30d"] += 1
                    if current_date and (
                        not file_changes[file_part]["last_changed"]
                        or current_date > file_changes[file_part]["last_changed"]
                    ):
                        file_changes[file_part]["last_changed"] = current_date

        # Sort by change count, take top 50
        sorted_files = sorted(file_changes.values(), key=lambda x: x["changes_30d"], reverse=True)[
            :50
        ]

        # Hotspots = files with > 5 changes
        hotspots = [f for f in sorted_files if f["changes_30d"] > 5]

        # Cross-reference with batch targets
        batch_dir = Path.home() / ".cortex" / "batch"
        batch_targets: List[str] = []
        if batch_dir.exists():
            for bf in batch_dir.glob("*.json"):
                try:
                    data = json.loads(bf.read_text(encoding="utf-8"))
                    if "target" in data:
                        batch_targets.append(data["target"])
                except Exception:
                    continue

        result_data = {
            "files": sorted_files,
            "hotspots": hotspots,
            "period_days": 30,
            "batch_targets": batch_targets,
        }
        _heatmap_cache["data"] = result_data
        _heatmap_cache["timestamp"] = now
        return result_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate activity heatmap: {e}")


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


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("Starting Cortex Bridge API on http://127.0.0.1:8765")
    print("API docs: http://127.0.0.1:8765/docs")
    uvicorn.run(app, host="127.0.0.1", port=8765)
