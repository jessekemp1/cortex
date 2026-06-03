"""Meta-layer routes — compounding risk assessment (Examined Engineer).

Three endpoints that surface 6-month risk trajectories at three granularities:
project, portfolio, and individual file. All three delegate to a single
class (`cortex.intelligence.analysis.compounding_risk.CompoundingRiskAssessor`)
imported lazily inside each handler so the router module loads quickly.

Wired into the FastAPI app via:

    from api.routes.meta import router as meta_router
    app.include_router(meta_router)

Public route table (paths unchanged from the pre-split bridge):
    GET /meta/compounding              ?project=NAME    -> risk for one project
    GET /meta/compounding/portfolio                     -> sorted multi-project view
    GET /meta/compounding/file         ?path=PATH       -> risk for one file
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query


router = APIRouter(tags=["meta"])


@router.get("/meta/compounding")
async def meta_compounding_project(
    project: str = Query(..., description="Project name, e.g. 'vortex-backend'"),
) -> Dict[str, Any]:
    """Compounding risk assessment for a project.

    Returns 6-month trajectory, rate (low/medium/high/critical), and the
    boring risk nobody is tracking.
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


@router.get("/meta/compounding/portfolio")
async def meta_compounding_portfolio() -> Dict[str, Any]:
    """Compounding risk assessment for all known projects, sorted by severity.

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
                {"project": r.target, "risk": r.boring_risk}
                for r in risks_sorted
                if r.boring_risk
            ],
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Portfolio compounding assessment failed: {e}"
        )


@router.get("/meta/compounding/file")
async def meta_compounding_file(
    path: str = Query(..., description="File path relative to repo root"),
) -> Dict[str, Any]:
    """Compounding risk assessment for a specific file.

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
