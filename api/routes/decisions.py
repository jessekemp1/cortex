"""Decisions routes — record user-decision events from the Co-Navigator UI.

A single endpoint that appends a structured decision event (which scenario
the user picked, whether they overrode, why) to a JSONL log. The log is used
downstream by the learning loop to calibrate scenario predictions against
real outcomes.

Wired into the FastAPI app via:

    from api.routes.decisions import router as decisions_router
    app.include_router(decisions_router)

Public route table:
    POST /decisions/record     DecisionRecordRequest    -> {recorded, decision_id, timestamp}  (Co-Navigator scenario picks)
    POST /decisions/learning   LearningDecisionRequest  -> {recorded, decision_id, timestamp}  (cortex_record_decision MCP tool)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


DECISIONS_FILE = Path.home() / ".cortex" / "decisions.jsonl"


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


router = APIRouter(tags=["decisions"])


@router.post("/decisions/record")
async def record_decision(req: DecisionRecordRequest) -> Dict[str, Any]:
    """Record a user decision from the Co-Navigator UI.

    Appends one JSON line to ~/.cortex/decisions.jsonl. Returns the synthesized
    decision_id and ISO timestamp so the UI can immediately reference the
    persisted record.
    """
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


class LearningDecisionRequest(BaseModel):
    """Request to record a learning-loop decision (architecture / library / tradeoff).

    This is the schema the `cortex_record_decision` MCP tool sends. Distinct from
    the Co-Navigator scenario `DecisionRecordRequest` above — different concern,
    different path. Only `decision` is required; the rest default to empty so the
    MCP tool can omit blank fields.
    """

    decision: str = Field(..., description="What was decided")
    context: str = Field(default="", description="Why this decision was needed")
    alternatives: str = Field(default="", description="Other options considered")
    rationale: str = Field(default="", description="Why this option was chosen over alternatives")
    project: str = Field(default="", description="Project this decision belongs to (optional)")


@router.post("/decisions/learning")
async def record_learning_decision(req: LearningDecisionRequest) -> Dict[str, Any]:
    """Record a learning-loop decision for the Cortex intelligence layer.

    Delegates to mcp_handlers.record_learning_decision — the same crash-proof
    writer the `cortex_record_decision` MCP tool calls in-process — so route
    and tool share one implementation (canonical schema: decision/context/
    alternatives/rationale/timestamp/source + decision_id, with spool
    fallback). Kept separate from the Co-Navigator `/decisions/record` route,
    which has an incompatible schema.
    """
    try:
        import mcp_handlers

        return mcp_handlers.record_learning_decision(
            decision=req.decision,
            context=req.context,
            alternatives=req.alternatives,
            rationale=req.rationale,
            project=req.project,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record learning decision: {e}")
