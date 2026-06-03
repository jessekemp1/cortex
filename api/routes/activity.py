"""Activity routes — codebase change-frequency visualization.

Single endpoint that aggregates git history over the last 30 days into a
heatmap-friendly payload: file → change count, plus hotspots (>5 changes)
and any files currently scheduled in the batch queue. Caches the result
in-process for 5 minutes since the underlying `git log` is moderately
expensive on large repos.

Wired into the FastAPI app via:

    from api.routes.activity import router as activity_router
    app.include_router(activity_router)

Public route table (paths unchanged from the pre-split bridge):
    GET /activity/heatmap   -> {files, hotspots, period_days, batch_targets}
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException


# Per-process cache for the moderately expensive git-log scan. 5-minute TTL.
_heatmap_cache: Dict[str, Any] = {"data": None, "timestamp": 0}


router = APIRouter(tags=["activity"])


@router.get("/activity/heatmap")
async def get_activity_heatmap() -> Dict[str, Any]:
    """Codebase activity visualization data — file change frequency over 30 days."""
    # Lazy import: WORKSPACE lives in bridge_endpoint and we don't want to
    # cycle on module load.
    from api.bridge_endpoint import WORKSPACE

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
                    parts = line.split("|")
                    current_date = parts[2].strip() if len(parts) >= 3 else ""
                    continue

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

        # Top 50 most-changed files, then hotspots (>5 changes), then
        # cross-reference with anything currently in the batch queue.
        sorted_files = sorted(
            file_changes.values(), key=lambda x: x["changes_30d"], reverse=True
        )[:50]
        hotspots = [f for f in sorted_files if f["changes_30d"] > 5]

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
        raise HTTPException(
            status_code=500, detail=f"Failed to generate activity heatmap: {e}"
        )
