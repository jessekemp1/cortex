"""SnapshotRing — circular buffer of file snapshots with content-addressed storage."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SnapshotInfo:
    snapshot_id: str  # "snap_<timestamp_ms>"
    created_at: str  # ISO format
    reason: str  # "pre_claim", "manual", "pre_recovery"
    files: List[str]  # absolute paths
    file_hashes: Dict[str, str] = field(default_factory=dict)  # path -> sha256


class SnapshotRing:
    """Circular buffer of file snapshots, triggered by events not timers.

    Storage layout:
        <base_dir>/
            manifest.json       # ordered list of snapshot metadata
            content/
                <sha256>.dat    # content-addressed file blobs
            meta/
                snap_<ts>.json  # per-snapshot metadata

    Content-addressed storage means identical file content across snapshots
    is stored only once on disk. When the ring exceeds max_size, the oldest
    snapshot is evicted and unreferenced blobs are garbage-collected.
    """

    DEFAULT_MAX_SIZE = 50

    def __init__(self, base_dir: Path, max_size: int = DEFAULT_MAX_SIZE):
        self.base_dir = base_dir
        self.content_dir = base_dir / "content"
        self.meta_dir = base_dir / "meta"
        self.manifest_file = base_dir / "manifest.json"
        self.max_size = max_size
        self._ensure_dirs()
        self._manifest: List[str] = self._load_manifest()

    def snapshot(self, files: List[str], reason: str) -> SnapshotInfo:
        """Create a snapshot of the specified files."""
        snap_id = f"snap_{int(time.time() * 1000)}"
        file_hashes: Dict[str, str] = {}
        snapshotted_files: List[str] = []

        for fpath in files:
            p = Path(fpath)
            if not p.exists() or not p.is_file():
                continue
            content = p.read_bytes()
            h = self._store_content(content)
            file_hashes[fpath] = h
            snapshotted_files.append(fpath)

        from datetime import datetime, timezone

        info = SnapshotInfo(
            snapshot_id=snap_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            files=snapshotted_files,
            file_hashes=file_hashes,
        )

        # Write per-snapshot metadata
        meta_file = self.meta_dir / f"{snap_id}.json"
        meta_file.write_text(json.dumps(asdict(info), indent=2))

        # Update manifest
        self._manifest.append(snap_id)
        self._save_manifest()

        # Evict if over capacity
        while len(self._manifest) > self.max_size:
            self.evict_oldest()

        return info

    def get_snapshot(self, snapshot_id: str) -> Optional[SnapshotInfo]:
        """Load a snapshot by ID."""
        meta_file = self.meta_dir / f"{snapshot_id}.json"
        if not meta_file.exists():
            return None
        try:
            data = json.loads(meta_file.read_text())
            return SnapshotInfo(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def list_snapshots(self, limit: int = 20) -> List[SnapshotInfo]:
        """List snapshots, newest first."""
        result: List[SnapshotInfo] = []
        for snap_id in reversed(self._manifest):
            info = self.get_snapshot(snap_id)
            if info:
                result.append(info)
            if len(result) >= limit:
                break
        return result

    def get_file_content(self, snapshot_id: str, file_path: str) -> Optional[bytes]:
        """Retrieve file content from a snapshot."""
        info = self.get_snapshot(snapshot_id)
        if info is None:
            return None
        h = info.file_hashes.get(file_path)
        if h is None:
            return None
        blob = self.content_dir / f"{h}.dat"
        if not blob.exists():
            return None
        return blob.read_bytes()

    def evict_oldest(self) -> None:
        """Remove the oldest snapshot and garbage-collect unreferenced blobs."""
        if not self._manifest:
            return
        oldest_id = self._manifest.pop(0)
        meta_file = self.meta_dir / f"{oldest_id}.json"
        if meta_file.exists():
            meta_file.unlink()
        self._save_manifest()
        self._gc_content()

    def _gc_content(self) -> int:
        """Remove content blobs not referenced by any snapshot. Returns count removed."""
        # Collect all referenced hashes
        referenced: set[str] = set()
        for snap_id in self._manifest:
            info = self.get_snapshot(snap_id)
            if info:
                referenced.update(info.file_hashes.values())

        # Remove unreferenced blobs
        removed = 0
        for blob in self.content_dir.iterdir():
            if blob.suffix == ".dat":
                h = blob.stem
                if h not in referenced:
                    blob.unlink()
                    removed += 1
        return removed

    @staticmethod
    def _hash_bytes(content: bytes) -> str:
        """SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def _store_content(self, content: bytes) -> str:
        """Store content-addressed blob. Returns hash."""
        h = self._hash_bytes(content)
        blob = self.content_dir / f"{h}.dat"
        if not blob.exists():
            blob.write_bytes(content)
        return h

    def _ensure_dirs(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(exist_ok=True)
        self.meta_dir.mkdir(exist_ok=True)

    def _load_manifest(self) -> List[str]:
        if not self.manifest_file.exists():
            return []
        try:
            return json.loads(self.manifest_file.read_text())
        except (json.JSONDecodeError, TypeError):
            return []

    def _save_manifest(self) -> None:
        tmp = self.manifest_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._manifest))
        os.replace(str(tmp), str(self.manifest_file))
