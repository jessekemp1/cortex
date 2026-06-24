"""GuardianProcess — singleton orchestrator for file claims, snapshots, and recovery."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortex.guardian.claims import ClaimResult, FileClaimManager, ReleaseResult
from cortex.guardian.recovery import RecoverResult, RecoveryEngine
from cortex.guardian.router import ProjectRouter
from cortex.guardian.snapshots import SnapshotInfo, SnapshotRing


class GuardianProcess:
    """Singleton repo guardian managing file claims, snapshots, and recovery.

    Lifecycle:
    - Created lazily on first API call (not at bridge startup)
    - Loads state from disk (~/.cortex/guardian/)
    - Persists state on every mutation
    - Reaps expired claims on every query (no background thread)
    """

    STATE_DIR = Path.home() / ".cortex" / "guardian"

    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is not None:
            self.STATE_DIR = state_dir
        self.STATE_DIR.mkdir(parents=True, exist_ok=True)

        self.claims = FileClaimManager(self.STATE_DIR / "claims.json")
        self.snapshots = SnapshotRing(self.STATE_DIR / "snapshots", max_size=50)
        self.router = ProjectRouter()
        self.recovery = RecoveryEngine(self.snapshots)
        self.started_at = datetime.now(timezone.utc)
        self.log_file = self.STATE_DIR / "guardian.log"
        self.violations_file = self.STATE_DIR / "violations.jsonl"

    def claim(self, file_path: str, agent_id: str, ttl: int = 300) -> ClaimResult:
        """Claim a file for exclusive editing. Auto-snapshots on success."""
        project = self.router.resolve(file_path).name
        result = self.claims.claim(file_path, agent_id, ttl=ttl, project=project)

        if result.success:
            # Auto-snapshot the file before any edits
            snap = self.snapshots.snapshot([file_path], reason="pre_claim")
            self.log_event(
                "claim",
                {
                    "file": file_path,
                    "agent_id": agent_id,
                    "project": project,
                    "snapshot_id": snap.snapshot_id,
                },
            )
        else:
            self.log_event(
                "claim_conflict",
                {
                    "file": file_path,
                    "agent_id": agent_id,
                    "holder": result.conflict.agent_id if result.conflict else "unknown",
                },
            )

        return result

    def release(self, file_path: str, agent_id: str) -> ReleaseResult:
        """Release a claimed file."""
        result = self.claims.release(file_path, agent_id)
        if result.released:
            self.log_event(
                "release",
                {
                    "file": file_path,
                    "agent_id": agent_id,
                },
            )
        return result

    def status(self) -> Dict[str, Any]:
        """Get Guardian health and claim status."""
        self.claims.reap_expired()
        active = self.claims.get_all_claims()

        claims_info = {}
        for fp, c in active.items():
            claims_info[fp] = {
                "agent_id": c.agent_id,
                "remaining_seconds": round(c.remaining_seconds, 1),
                "project": c.project,
            }

        violations_today = 0
        if self.violations_file.exists():
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for line in self.violations_file.read_text().splitlines():
                if line.strip() and today in line:
                    violations_today += 1

        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()

        return {
            "status": "operational",
            "uptime_seconds": round(uptime, 1),
            "claims": claims_info,
            "active_claims": len(claims_info),
            "snapshot_count": len(self.snapshots._manifest),
            "ring_capacity": self.snapshots.max_size,
            "violations_today": violations_today,
        }

    def snapshot(self, files: List[str], reason: str = "manual") -> SnapshotInfo:
        """Create a manual snapshot."""
        info = self.snapshots.snapshot(files, reason=reason)
        self.log_event(
            "snapshot",
            {
                "snapshot_id": info.snapshot_id,
                "reason": reason,
                "files": info.files,
            },
        )
        return info

    def list_snapshots(self, limit: int = 20) -> List[SnapshotInfo]:
        """List available snapshots, newest first."""
        return self.snapshots.list_snapshots(limit=limit)

    def recover(self, file_path: str, snapshot_id: str) -> RecoverResult:
        """Restore a file from a snapshot."""
        result = self.recovery.recover(file_path, snapshot_id)
        self.log_event(
            "recover",
            {
                "file": file_path,
                "snapshot_id": snapshot_id,
                "success": result.success,
                "bytes_restored": result.bytes_restored,
            },
        )
        return result

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Append a structured log entry."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            **data,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_violation(self, file_path: str, agent_id: str, details: str) -> None:
        """Log an advisory violation (edit without claim)."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "file": file_path,
            "agent_id": agent_id,
            "details": details,
        }
        with open(self.violations_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
