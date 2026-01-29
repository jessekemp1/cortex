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
    query_type: str = Field(default="spec", description="Query type: spec, impl, analysis, research")
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

# CORS - Allow Moltbot and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:18789", "http://localhost:18789", "http://localhost:*"],
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
            raise HTTPException(status_code=500, detail=f"Failed to initialize anomaly manager: {e}")
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
        bridge = get_bridge()
        anomaly_mgr = get_anomaly_manager()

        # Get active anomalies
        anomalies = anomaly_mgr.detect_all_anomalies()

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
    limit: int = Query(5, description="Max recommendations")
) -> Dict[str, Any]:
    """
    Get Cortex recommendations based on current context.
    """
    try:
        bridge = get_bridge()
        recommendations = bridge.get_recommendations()

        # Filter by project if specified
        if project and "recommendations" in recommendations:
            filtered = [r for r in recommendations["recommendations"] if r.get("project") == project]
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
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, WARNING, INFO"),
    anomaly_type: Optional[str] = Query(None, description="Filter by type")
) -> Dict[str, Any]:
    """
    Get current orchestration anomalies.

    Returns list of detected anomalies with severity, type, and recommendations.
    """
    try:
        anomaly_mgr = get_anomaly_manager()
        anomalies = anomaly_mgr.detect_all_anomalies()

        # Filter by severity
        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]

        # Filter by type
        if anomaly_type:
            anomalies = [a for a in anomalies if a.anomaly_type == anomaly_type]

        return {
            "count": len(anomalies),
            "anomalies": [
                {
                    "id": a.anomaly_id,
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "title": a.title,
                    "description": a.description,
                    "recommendation": a.recommendation,
                    "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                }
                for a in anomalies
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Context Graph Endpoints
# ============================================================================

@app.get("/graph/query")
async def query_graph(
    node_type: str = Query(..., description="Node type to query"),
    filters: Optional[str] = Query(None, description="JSON filters")
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

        return {
            "node_type": node_type,
            "count": len(nodes),
            "nodes": nodes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/projects")
async def list_projects() -> Dict[str, List[str]]:
    """List available projects."""
    return {
        "projects": ["cortex", "vortex", "alpha_arena", "kempion"]
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("🧠 Starting Cortex Bridge API on http://127.0.0.1:8765")
    print("📚 API docs: http://127.0.0.1:8765/docs")
    print("🦞 Ready for Moltbot integration!")
    uvicorn.run(app, host="127.0.0.1", port=8765)
