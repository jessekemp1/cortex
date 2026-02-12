#!/usr/bin/env python3
"""
Synthetic Data Engine API — FastAPI endpoints for enterprise access.

Provides async generation, status tracking, output download,
client outcome ingestion, and quality trend reporting.

Start with:
    uvicorn cortex.synthetic.api:app --host 127.0.0.1 --port 8766

Routes:
    POST /api/v1/synthetic/generate          — Async generation with flywheel
    GET  /api/v1/synthetic/status/{id}       — Track generation progress
    GET  /api/v1/synthetic/download/{id}     — Retrieve completed output
    POST /api/v1/synthetic/feedback/{id}     — Client outcome ingestion
    GET  /api/v1/synthetic/quality/report    — Quality trends across generations
"""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")

from synthetic.flywheel import Flywheel
from synthetic.generator import SyntheticGenerator
from synthetic.knowledge_base import CanadianFinServKB
from synthetic.schemas import GenerationRequest

# ============================================================================
# Pydantic Models
# ============================================================================


class GenerateRequest(BaseModel):
    """Request body for synthetic data generation."""

    data_type: str = Field("profiles", description="'profiles' or 'transactions'")
    count: int = Field(100, ge=1, le=10000, description="Number of records")
    segment: Optional[str] = Field(None, description="Target segment filter")
    province: Optional[str] = Field(None, description="Target province filter")
    include_risk_flags: bool = Field(False, description="Include AML risk flags")
    risk_profile: str = Field("normal", description="'normal', 'high', or 'adversarial'")
    skip_heavy_layers: bool = Field(False, description="Skip L5-L7 for fast validation")


class FeedbackRequest(BaseModel):
    """Client outcome feedback for a generation run."""

    outcome: str = Field(..., description="'positive', 'negative', or 'neutral'")
    detail: Optional[str] = Field(None, description="Freeform feedback text")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Custom metric dict")


class GenerationStatus(BaseModel):
    """Status of a generation run."""

    flywheel_id: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: str
    completed_at: Optional[str] = None
    data_type: str
    count: int
    flywheel_score: Optional[float] = None
    layers_passed: Optional[int] = None
    layers_executed: Optional[int] = None
    error: Optional[str] = None


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Cortex Synthetic Data Engine",
    description="Canadian FinServ synthetic data generation with 7-layer quality flywheel",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for generation runs (production would use a database)
_generation_store: Dict[str, Dict[str, Any]] = {}
_feedback_store: Dict[str, List[Dict[str, Any]]] = {}
_quality_history: List[Dict[str, Any]] = []

# Shared instances
_kb = CanadianFinServKB()
_generator = SyntheticGenerator(kb=_kb)
_flywheel = Flywheel(kb=_kb)

# Output directory
_output_dir = Path.home() / ".cortex" / "synthetic" / "api_output"
_output_dir.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Routes
# ============================================================================


@app.post("/api/v1/synthetic/generate", response_model=GenerationStatus)
async def generate_synthetic(request: GenerateRequest):
    """
    Generate synthetic data with flywheel quality validation.

    Returns immediately with a flywheel_id for status tracking.
    Generation runs synchronously for simplicity (async in production).
    """
    flywheel_id = f"FW-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now().isoformat()

    # Store initial status
    _generation_store[flywheel_id] = {
        "status": "running",
        "created_at": created_at,
        "data_type": request.data_type,
        "count": request.count,
    }

    try:
        gen_request = GenerationRequest(
            data_type=request.data_type,
            count=request.count,
            segment=request.segment,
            province=request.province,
            include_risk_flags=request.include_risk_flags,
            risk_profile=request.risk_profile,
        )

        # Generate data (use internal methods to get actual records)
        profiles = None
        transactions = None
        if gen_request.data_type == "profiles":
            profiles, _ = _generator._generate_profiles(gen_request)
        elif gen_request.data_type == "transactions":
            transactions, _ = _generator._generate_transactions(gen_request)

        # Run flywheel validation
        report = _flywheel.run_cycle(
            profiles=profiles,
            transactions=transactions,
            request=gen_request,
            flywheel_id=flywheel_id,
            skip_heavy_layers=request.skip_heavy_layers,
        )

        # Save output to disk
        output_path = _output_dir / f"{flywheel_id}.json"
        records_data = []
        if profiles:
            records_data = [p.to_dict() for p in profiles]
        elif transactions:
            records_data = [t.to_dict() for t in transactions]
        output_data = {
            "flywheel_id": flywheel_id,
            "data_type": request.data_type,
            "count": len(records_data),
            "records": records_data,
            "flywheel_report": report.to_dict(),
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, default=str)

        # Update store
        completed_at = datetime.now().isoformat()
        _generation_store[flywheel_id].update(
            {
                "status": "completed",
                "completed_at": completed_at,
                "flywheel_score": round(report.overall_score, 4),
                "layers_passed": report.layers_passed,
                "layers_executed": report.layers_executed,
                "output_path": str(output_path),
            }
        )

        # Track quality history
        _quality_history.append(
            {
                "flywheel_id": flywheel_id,
                "timestamp": completed_at,
                "overall_score": round(report.overall_score, 4),
                "layers_passed": report.layers_passed,
                "layers_executed": report.layers_executed,
                "data_type": request.data_type,
                "count": request.count,
            }
        )

        return GenerationStatus(
            flywheel_id=flywheel_id,
            status="completed",
            created_at=created_at,
            completed_at=completed_at,
            data_type=request.data_type,
            count=request.count,
            flywheel_score=round(report.overall_score, 4),
            layers_passed=report.layers_passed,
            layers_executed=report.layers_executed,
        )

    except Exception as e:
        _generation_store[flywheel_id].update(
            {
                "status": "failed",
                "error": str(e),
            }
        )
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@app.get("/api/v1/synthetic/status/{flywheel_id}", response_model=GenerationStatus)
async def get_status(flywheel_id: str):
    """Get the status of a generation run."""
    if flywheel_id not in _generation_store:
        raise HTTPException(status_code=404, detail=f"Generation {flywheel_id} not found")

    store = _generation_store[flywheel_id]
    return GenerationStatus(
        flywheel_id=flywheel_id,
        status=store["status"],
        created_at=store["created_at"],
        completed_at=store.get("completed_at"),
        data_type=store["data_type"],
        count=store["count"],
        flywheel_score=store.get("flywheel_score"),
        layers_passed=store.get("layers_passed"),
        layers_executed=store.get("layers_executed"),
        error=store.get("error"),
    )


@app.get("/api/v1/synthetic/download/{flywheel_id}")
async def download_output(flywheel_id: str):
    """Download the generated output for a completed generation run."""
    if flywheel_id not in _generation_store:
        raise HTTPException(status_code=404, detail=f"Generation {flywheel_id} not found")

    store = _generation_store[flywheel_id]
    if store["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Generation {flywheel_id} is {store['status']}, not completed",
        )

    output_path = Path(store.get("output_path", ""))
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    with open(output_path) as f:
        return json.load(f)


@app.post("/api/v1/synthetic/feedback/{flywheel_id}")
async def submit_feedback(flywheel_id: str, request: FeedbackRequest):
    """
    Submit client outcome feedback for a generation run.

    Closes the external feedback loop — clients report whether the
    synthetic data was useful, and the flywheel incorporates this
    for future generation cycles.
    """
    if flywheel_id not in _generation_store:
        raise HTTPException(status_code=404, detail=f"Generation {flywheel_id} not found")

    feedback_entry = {
        "flywheel_id": flywheel_id,
        "timestamp": datetime.now().isoformat(),
        "outcome": request.outcome,
        "detail": request.detail,
        "metrics": request.metrics,
    }

    if flywheel_id not in _feedback_store:
        _feedback_store[flywheel_id] = []
    _feedback_store[flywheel_id].append(feedback_entry)

    # Log to persistent storage
    feedback_log = _output_dir / "feedback_log.jsonl"
    with open(feedback_log, "a") as f:
        f.write(json.dumps(feedback_entry) + "\n")

    return {
        "status": "accepted",
        "flywheel_id": flywheel_id,
        "feedback_count": len(_feedback_store[flywheel_id]),
    }


@app.get("/api/v1/synthetic/quality/report")
async def quality_report(last_n: int = 20):
    """
    Get quality trend report across recent generations.

    Returns per-generation scores and aggregate trend analysis.
    """
    recent = _quality_history[-last_n:]

    if not recent:
        return {
            "generations": 0,
            "trend": "no_data",
            "history": [],
        }

    scores = [h["overall_score"] for h in recent]
    avg_score = sum(scores) / len(scores)

    trend = "stable"
    if len(scores) >= 3:
        first_half = sum(scores[: len(scores) // 2]) / max(len(scores) // 2, 1)
        second_half = sum(scores[len(scores) // 2 :]) / max(len(scores) - len(scores) // 2, 1)
        if second_half > first_half + 0.01:
            trend = "improving"
        elif second_half < first_half - 0.01:
            trend = "declining"

    # Flywheel trend from the orchestrator
    flywheel_trend = _flywheel.get_trend()

    return {
        "generations": len(recent),
        "avg_score": round(avg_score, 4),
        "latest_score": round(scores[-1], 4) if scores else None,
        "trend": trend,
        "flywheel_trend": flywheel_trend,
        "history": recent,
        "feedback_summary": {
            "total_feedback": sum(len(v) for v in _feedback_store.values()),
            "positive": sum(
                1
                for entries in _feedback_store.values()
                for e in entries
                if e["outcome"] == "positive"
            ),
            "negative": sum(
                1
                for entries in _feedback_store.values()
                for e in entries
                if e["outcome"] == "negative"
            ),
        },
    }


@app.get("/api/v1/synthetic/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.4.0",
        "engine": "Cortex Synthetic Data Engine",
        "layers": 7,
        "total_generations": len(_generation_store),
        "total_feedback": sum(len(v) for v in _feedback_store.values()),
    }
