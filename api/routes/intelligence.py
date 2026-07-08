"""Intelligence routes — pattern retrieval + LLM reasoning + recommendations.

Four endpoints that surface Cortex's intelligence stack:

  POST /intelligence/query           pattern retrieval (no LLM call)
  POST /intelligence/reason          context-gathered LLM answer
  GET  /intelligence/recommendations ranked project recommendations
  GET  /recommendations              alias for /intelligence/recommendations

All four delegate to the CortexBridge singleton obtained via the lazy
`get_bridge()` helper exported from `api.bridge_endpoint`. `/intelligence/reason`
also calls the Anthropic API directly with a context block built from
portfolio status, service health, recent git activity, and Cortex pattern
retrieval.

Wired into the FastAPI app via:

    from api.routes.intelligence import router as intelligence_router
    app.include_router(intelligence_router)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class IntelligenceQuery(BaseModel):
    """Request model for intelligence queries."""

    request: str = Field(..., description="User request or query")
    project: Optional[str] = Field(
        default=None, description="Project; auto-detected if omitted"
    )
    query_type: str = Field(
        default="spec", description="Query type: spec, impl, analysis, research"
    )
    use_cache: bool = Field(default=True, description="Use query cache")
    parallel: bool = Field(default=True, description="Query sources in parallel")


class ReasonQuery(BaseModel):
    """Request model for reasoning queries (LLM-powered answers)."""

    question: str = Field(..., description="User's question in natural language")
    project: Optional[str] = Field(
        default=None, description="Project context (auto-detected if empty)"
    )


# ---------------------------------------------------------------------------
# Project routing — derived from discovery, not a hardcoded author portfolio.
# Single source of truth lives in mcp_handlers (the MCP server runs the same
# resolution in-process); imported back here so route and tool can never drift.
# ---------------------------------------------------------------------------

from mcp_handlers import _project_dirs, _workspace_root
from mcp_handlers import auto_detect_project as _auto_detect_project


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["intelligence"])


@router.post("/intelligence/query")
async def query_intelligence(query: IntelligenceQuery) -> Dict[str, Any]:
    """Query Cortex unified intelligence (pattern retrieval, no LLM call)."""
    from api.bridge_endpoint import get_bridge

    try:
        bridge = get_bridge()
        # Resolve project when omitted: prefer the bridge's git-aware detector
        # (derived from CORTEX_ROOT_DIR), then keyword auto-detect over the
        # user's discovered projects. Never default to a literal "cortex".
        project = query.project
        if not project:
            try:
                project = bridge._detect_current_project()
            except Exception:
                project = None
            if not project:
                project = _auto_detect_project(query.request)
        result = bridge.query_intelligence(
            request=query.request,
            project=project,
            query_type=query.query_type,
            use_cache=query.use_cache,
            parallel=query.parallel,
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/reason")
async def reason_query(query: ReasonQuery) -> Dict[str, Any]:
    """Answer a question using gathered context + Claude API.

    Unlike /intelligence/query (pattern retrieval), this endpoint reasons about
    the question: gathers context from portfolio status, service health, recent
    git activity, pattern retrieval, and GOALS.md, then sends the bundle to
    Claude Haiku for synthesis. Returns the model's answer + token usage on
    success; falls back to the raw context block on any failure so the caller
    always gets something.
    """
    from api.bridge_endpoint import get_bridge

    question = query.question
    project = query.project or _auto_detect_project(question)

    workspace = _workspace_root()
    context_parts: List[str] = []

    # 1. Portfolio status (real data)
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/python3", "scripts/portfolio_status.py", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(workspace),
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
            context_parts.append(
                f"SERVICE HEALTH:\n{json.dumps(health, indent=2, default=str)}"
            )
    except Exception:
        pass

    # 3. Recent git activity for the detected project
    try:
        proj_dir = _project_dirs().get(project, "")
        if proj_dir:
            git_result = subprocess.run(
                ["git", "log", "--oneline", "-15", "--", proj_dir],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(workspace),
            )
            if git_result.returncode == 0 and git_result.stdout.strip():
                context_parts.append(
                    f"RECENT COMMITS ({project}):\n{git_result.stdout.strip()}"
                )

            diff_result = subprocess.run(
                ["git", "diff", "--stat", "--", proj_dir],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(workspace),
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                context_parts.append(
                    f"UNCOMMITTED CHANGES ({project}):\n{diff_result.stdout.strip()}"
                )
    except Exception:
        pass

    # 4. Cortex pattern retrieval (lightweight)
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

    # 5. GOALS.md immediate-actions section
    try:
        goals_path = workspace / "GOALS.md"
        if goals_path.exists():
            goals_text = goals_path.read_text()
            if "## Immediate Actions" in goals_text:
                actions_section = goals_text.split("## Immediate Actions")[1].split("##")[0]
                context_parts.append(
                    f"GOALS - IMMEDIATE ACTIONS:\n{actions_section[:1500]}"
                )
    except Exception:
        pass

    context_block = (
        "\n\n---\n\n".join(context_parts) if context_parts else "No context gathered."
    )

    # Call Claude API (haiku for speed + cost efficiency)
    try:
        import anthropic

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
            "answer": (
                f"LLM call failed: {e}\n\nFallback context:\n{context_block[:2000]}"
            ),
            "project": project,
            "sources_used": len(context_parts),
            "model": "fallback",
            "tokens": 0,
        }


@router.get("/intelligence/recommendations")
async def get_recommendations(
    project: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(5, description="Max recommendations"),
) -> Dict[str, Any]:
    """Get Cortex recommendations based on current context.

    Normalizes report-style recommendation payloads (next_action,
    priority_projects, risk_alerts) into a flat list when the bridge returns
    that shape; otherwise returns the bridge's recommendations directly.
    """
    from api.bridge_endpoint import get_bridge

    from mcp_handlers import normalize_recommendations

    try:
        bridge = get_bridge()
        recommendations = bridge.get_recommendations()
        return normalize_recommendations(recommendations, project=project, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_recommendations_alias(
    project: Optional[str] = Query(None, description="Filter by project"),
    limit: int = Query(5, description="Max recommendations"),
) -> Dict[str, Any]:
    """Alias for /intelligence/recommendations."""
    return await get_recommendations(project=project, limit=limit)
