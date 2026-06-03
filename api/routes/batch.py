"""Batch routes — list, status, cancel for Anthropic batch jobs.

These endpoints wrap the Anthropic Batch API for inspection and lifecycle
control. They share a single dependency — `get_batch_client()` —
which lazily instantiates `cortex.batch.batch_api_client.BatchAPIClient`
on first use.

Wired into the FastAPI app via:

    from api.routes.batch import router as batch_router
    app.include_router(batch_router)

Public route table (paths unchanged from the pre-split bridge):
    GET  /batches                    ?limit=N            -> list of batches
    GET  /batches/{batch_id}                              -> status payload
    POST /batches/{batch_id}/cancel                       -> cancellation result
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query


# ---------------------------------------------------------------------------
# Lazy client (mirrors the pre-split global; reset on app reload)
# ---------------------------------------------------------------------------

_batch_client: Optional[Any] = None


def get_batch_client():
    """Return a cached BatchAPIClient, lazily constructed on first use."""
    global _batch_client
    if _batch_client is None:
        try:
            from cortex.batch.batch_api_client import BatchAPIClient

            _batch_client = BatchAPIClient()
        except Exception as e:  # ImportError, anthropic auth errors, etc.
            raise HTTPException(
                status_code=500, detail=f"Failed to initialize batch client: {e}"
            )
    return _batch_client


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["batches"])


@router.get("/batches")
async def list_batches(limit: int = Query(20, description="Max batches to return")):
    """List active and recent batch jobs. Returns batch status from Anthropic API."""
    try:
        client = get_batch_client()
        batches = client.list_batches(limit=limit)
        return {"batches": batches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batches/{batch_id}")
async def get_batch_status(batch_id: str):
    """Get detailed status for a specific batch: progress, request counts, completion."""
    try:
        client = get_batch_client()
        status = client.get_batch_status(batch_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Batch not found: {e}")


@router.post("/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """Cancel a running batch job. Returns updated status after cancellation."""
    try:
        client = get_batch_client()
        result = client.cancel_batch(batch_id)
        return {"status": "cancelled", "batch_id": batch_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
