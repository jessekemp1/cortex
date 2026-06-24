"""RecoveryEngine — restore files from snapshots with integrity verification."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from guardian.snapshots import SnapshotRing


@dataclass
class RecoverResult:
    success: bool
    file_path: str
    snapshot_id: str
    bytes_restored: int = 0
    pre_recovery_hash: str = ""
    post_recovery_hash: str = ""
    pre_recovery_snapshot_id: str = ""
    message: str = ""


class RecoveryEngine:
    """Restores files from snapshots in the SnapshotRing.

    Recovery flow:
    1. Verify snapshot exists and contains the requested file
    2. Snapshot the file's CURRENT state (pre-recovery evidence)
    3. Read the snapshot content
    4. Write content to disk (atomic write-replace)
    5. Verify written content matches expected hash
    6. Return result with both hashes for audit
    """

    def __init__(self, snapshot_ring: SnapshotRing):
        self.ring = snapshot_ring

    def recover(self, file_path: str, snapshot_id: str) -> RecoverResult:
        """Restore a file from a snapshot."""
        # 1. Verify snapshot exists and contains the file
        info = self.ring.get_snapshot(snapshot_id)
        if info is None:
            return RecoverResult(
                success=False,
                file_path=file_path,
                snapshot_id=snapshot_id,
                message=f"Snapshot {snapshot_id} not found",
            )

        if file_path not in info.file_hashes:
            return RecoverResult(
                success=False,
                file_path=file_path,
                snapshot_id=snapshot_id,
                message=f"File not in snapshot {snapshot_id}",
            )

        # 2. Snapshot current state (pre-recovery evidence)
        pre_snap = self.ring.snapshot([file_path], reason="pre_recovery")
        pre_recovery_hash = ""
        if Path(file_path).exists():
            pre_recovery_hash = self._hash_file(file_path)

        # 3. Read snapshot content
        content = self.ring.get_file_content(snapshot_id, file_path)
        if content is None:
            return RecoverResult(
                success=False,
                file_path=file_path,
                snapshot_id=snapshot_id,
                pre_recovery_hash=pre_recovery_hash,
                pre_recovery_snapshot_id=pre_snap.snapshot_id,
                message="Snapshot content blob missing (possible corruption)",
            )

        # 4. Write content to disk
        self._atomic_write(file_path, content)

        # 5. Verify
        post_hash = self._hash_file(file_path)
        expected_hash = info.file_hashes[file_path]

        if post_hash != expected_hash:
            return RecoverResult(
                success=False,
                file_path=file_path,
                snapshot_id=snapshot_id,
                bytes_restored=len(content),
                pre_recovery_hash=pre_recovery_hash,
                post_recovery_hash=post_hash,
                pre_recovery_snapshot_id=pre_snap.snapshot_id,
                message=f"Post-write verification failed: {post_hash} != {expected_hash}",
            )

        return RecoverResult(
            success=True,
            file_path=file_path,
            snapshot_id=snapshot_id,
            bytes_restored=len(content),
            pre_recovery_hash=pre_recovery_hash,
            post_recovery_hash=post_hash,
            pre_recovery_snapshot_id=pre_snap.snapshot_id,
            message="Recovered successfully",
        )

    def verify_integrity(self, file_path: str, expected_hash: str) -> bool:
        """Check if a file matches an expected hash."""
        return self._hash_file(file_path) == expected_hash

    @staticmethod
    def _hash_file(file_path: str) -> str:
        p = Path(file_path)
        if not p.exists():
            return ""
        return hashlib.sha256(p.read_bytes()).hexdigest()

    @staticmethod
    def _atomic_write(file_path: str, content: bytes) -> None:
        """Write via tmp + os.replace for atomicity."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".guardian_tmp")
        tmp.write_bytes(content)
        os.replace(str(tmp), str(p))
