"""FileClaimManager — advisory file claims with TTL-based expiry."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class FileClaim:
    file_path: str
    agent_id: str
    claimed_at: float  # time.time()
    ttl: int  # seconds
    project: str = ""

    @property
    def expires_at(self) -> float:
        return self.claimed_at + self.ttl

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.expires_at - time.time())


@dataclass
class ClaimResult:
    success: bool
    file_path: str
    agent_id: str
    conflict: Optional[FileClaim] = None
    message: str = ""


@dataclass
class ReleaseResult:
    released: bool
    file_path: str
    agent_id: str
    message: str = ""


class FileClaimManager:
    """Advisory file claims with TTL-based expiry.

    Thread-safe via atomic file write-replace. No in-memory locking needed
    because the bridge is single-process and FastAPI async handlers on CPython
    do not truly run in parallel.

    Claims are advisory: the Guardian logs violations when agents edit
    without claiming, but does not block the edit.
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._claims: Dict[str, FileClaim] = {}
        self._load()

    def claim(
        self, file_path: str, agent_id: str, ttl: int = 300, project: str = ""
    ) -> ClaimResult:
        """Attempt to claim a file for exclusive editing."""
        self.reap_expired()

        existing = self._claims.get(file_path)

        # Case 1: unclaimed
        if existing is None:
            new_claim = FileClaim(
                file_path=file_path,
                agent_id=agent_id,
                claimed_at=time.time(),
                ttl=ttl,
                project=project,
            )
            self._claims[file_path] = new_claim
            self._save()
            return ClaimResult(
                success=True,
                file_path=file_path,
                agent_id=agent_id,
                message="Claimed successfully",
            )

        # Case 2: same agent — extend TTL (idempotent)
        if existing.agent_id == agent_id:
            existing.claimed_at = time.time()
            existing.ttl = ttl
            self._save()
            return ClaimResult(
                success=True,
                file_path=file_path,
                agent_id=agent_id,
                message="Claim extended",
            )

        # Case 3: different agent, check if expired
        if existing.is_expired:
            new_claim = FileClaim(
                file_path=file_path,
                agent_id=agent_id,
                claimed_at=time.time(),
                ttl=ttl,
                project=project,
            )
            self._claims[file_path] = new_claim
            self._save()
            return ClaimResult(
                success=True,
                file_path=file_path,
                agent_id=agent_id,
                message=f"Claimed (expired claim from {existing.agent_id} reaped)",
            )

        # Case 4: different agent, still active — conflict
        return ClaimResult(
            success=False,
            file_path=file_path,
            agent_id=agent_id,
            conflict=existing,
            message=f"File claimed by {existing.agent_id} ({existing.remaining_seconds:.0f}s remaining)",
        )

    def release(self, file_path: str, agent_id: str) -> ReleaseResult:
        """Release a claimed file."""
        existing = self._claims.get(file_path)

        if existing is None or existing.agent_id != agent_id:
            return ReleaseResult(
                released=False,
                file_path=file_path,
                agent_id=agent_id,
                message="File was not claimed by this agent",
            )

        del self._claims[file_path]
        self._save()
        return ReleaseResult(
            released=True,
            file_path=file_path,
            agent_id=agent_id,
            message="Released successfully",
        )

    def release_all(self, agent_id: str) -> int:
        """Release all claims held by an agent. Returns count released."""
        to_remove = [fp for fp, c in self._claims.items() if c.agent_id == agent_id]
        for fp in to_remove:
            del self._claims[fp]
        if to_remove:
            self._save()
        return len(to_remove)

    def get_claim(self, file_path: str) -> Optional[FileClaim]:
        """Get the current claim on a file, if any."""
        claim = self._claims.get(file_path)
        if claim and claim.is_expired:
            return None
        return claim

    def get_all_claims(self) -> Dict[str, FileClaim]:
        """Get all active (non-expired) claims."""
        return {fp: c for fp, c in self._claims.items() if not c.is_expired}

    def reap_expired(self) -> int:
        """Remove expired claims. Returns count reaped."""
        expired = [fp for fp, c in self._claims.items() if c.is_expired]
        for fp in expired:
            del self._claims[fp]
        if expired:
            self._save()
        return len(expired)

    def is_claimed_by_other(self, file_path: str, agent_id: str) -> bool:
        """Check if a file is claimed by a different agent."""
        claim = self.get_claim(file_path)
        return claim is not None and claim.agent_id != agent_id

    def _load(self) -> None:
        """Load claims from disk."""
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text())
            for fp, cdata in data.items():
                self._claims[fp] = FileClaim(**cdata)
        except (json.JSONDecodeError, TypeError, KeyError):
            self._claims = {}

    def _save(self) -> None:
        """Atomic write-replace: write to tmp, then os.replace."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        data = {fp: asdict(c) for fp, c in self._claims.items()}
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.state_file))
