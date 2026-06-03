"""Guardian routes — file claim, release, snapshot, recover, status.

The Guardian subsystem manages exclusive file claims (with TTL), point-in-
time snapshots (ring-buffered), and recovery from those snapshots. These
routes are a coherent unit — they share request models, the same
`_get_guardian()` helper, and a single set of HTTP error semantics — so
they extract cleanly from the larger `bridge_endpoint.py` surface.

Wired into the FastAPI app via:

    from api.routes.guardian import router as guardian_router
    app.include_router(guardian_router)

Public route table (paths unchanged from the pre-split bridge):
    POST /guardian/claim         GuardianClaimRequest      -> claim status
    POST /guardian/release       GuardianReleaseRequest    -> release status
    GET  /guardian/status        (none)                    -> health/claim status
    POST /guardian/snapshot      GuardianSnapshotRequest   -> snapshot info
    GET  /guardian/snapshots     ?limit=N                  -> snapshot list
    POST /guardian/recover       GuardianRecoverRequest    -> recovery info
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models (formerly defined at module top of bridge_endpoint.py)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_guardian():
    """Return the lazily-initialized cortex.guardian.Guardian singleton."""
    from cortex.guardian import get_guardian

    return get_guardian()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(tags=["guardian"])


@router.post("/guardian/claim")
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


@router.post("/guardian/release")
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


@router.get("/guardian/status")
async def guardian_status() -> Dict[str, Any]:
    """Get Guardian health and claim status."""
    guardian = _get_guardian()
    return guardian.status()


@router.post("/guardian/snapshot")
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


@router.get("/guardian/snapshots")
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


@router.post("/guardian/recover")
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
