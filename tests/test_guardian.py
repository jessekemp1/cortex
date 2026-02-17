"""Tests for the Cortex Repo Guardian — claims, snapshots, recovery, routing."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from cortex.guardian.claims import FileClaimManager
from cortex.guardian.recovery import RecoveryEngine
from cortex.guardian.router import ProjectRouter
from cortex.guardian.snapshots import SnapshotRing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def claim_mgr(tmp_path: Path) -> FileClaimManager:
    return FileClaimManager(tmp_path / "claims.json")


@pytest.fixture
def snap_ring(tmp_path: Path) -> SnapshotRing:
    return SnapshotRing(tmp_path / "snapshots", max_size=5)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.py"
    f.write_text("print('hello')")
    return f


@pytest.fixture
def router() -> ProjectRouter:
    return ProjectRouter()


# ---------------------------------------------------------------------------
# Claim Tests
# ---------------------------------------------------------------------------


class TestClaims:
    def test_claim_unclaimed_file_succeeds(self, claim_mgr: FileClaimManager) -> None:
        result = claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=300)
        assert result.success is True
        assert result.file_path == "/tmp/foo.py"
        assert result.agent_id == "agent_a"
        assert result.conflict is None

    def test_claim_already_held_by_same_agent_extends_ttl(
        self, claim_mgr: FileClaimManager
    ) -> None:
        claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=100)
        result = claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=500)
        assert result.success is True
        assert result.message == "Claim extended"
        # Verify TTL was updated
        claim = claim_mgr.get_claim("/tmp/foo.py")
        assert claim is not None
        assert claim.ttl == 500

    def test_claim_held_by_other_agent_returns_conflict(self, claim_mgr: FileClaimManager) -> None:
        claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=300)
        result = claim_mgr.claim("/tmp/foo.py", "agent_b", ttl=300)
        assert result.success is False
        assert result.conflict is not None
        assert result.conflict.agent_id == "agent_a"
        assert "agent_a" in result.message

    def test_claim_expired_by_other_agent_succeeds(self, claim_mgr: FileClaimManager) -> None:
        claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=1)
        time.sleep(1.1)
        result = claim_mgr.claim("/tmp/foo.py", "agent_b", ttl=300)
        assert result.success is True
        assert result.agent_id == "agent_b"

    def test_release_claimed_file(self, claim_mgr: FileClaimManager) -> None:
        claim_mgr.claim("/tmp/foo.py", "agent_a", ttl=300)
        result = claim_mgr.release("/tmp/foo.py", "agent_a")
        assert result.released is True
        assert claim_mgr.get_claim("/tmp/foo.py") is None

    def test_release_unclaimed_file_is_noop(self, claim_mgr: FileClaimManager) -> None:
        result = claim_mgr.release("/tmp/foo.py", "agent_a")
        assert result.released is False
        assert "not claimed" in result.message


# ---------------------------------------------------------------------------
# TTL Reaping Tests
# ---------------------------------------------------------------------------


class TestTTLReaping:
    def test_reap_expired_removes_stale_claims(self, claim_mgr: FileClaimManager) -> None:
        claim_mgr.claim("/tmp/a.py", "agent_a", ttl=1)
        claim_mgr.claim("/tmp/b.py", "agent_a", ttl=1)
        claim_mgr.claim("/tmp/c.py", "agent_a", ttl=1)
        time.sleep(1.1)
        reaped = claim_mgr.reap_expired()
        assert reaped == 3
        assert len(claim_mgr.get_all_claims()) == 0

    def test_reap_preserves_active_claims(self, claim_mgr: FileClaimManager) -> None:
        claim_mgr.claim("/tmp/short.py", "agent_a", ttl=1)
        claim_mgr.claim("/tmp/long.py", "agent_b", ttl=300)
        time.sleep(1.1)
        reaped = claim_mgr.reap_expired()
        assert reaped == 1
        active = claim_mgr.get_all_claims()
        assert len(active) == 1
        assert "/tmp/long.py" in active


# ---------------------------------------------------------------------------
# Snapshot Tests
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_snapshot_creates_content_addressed_blob(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        info = snap_ring.snapshot([str(sample_file)], reason="test")
        assert len(info.files) == 1
        assert str(sample_file) in info.file_hashes
        # Verify the blob exists on disk
        h = info.file_hashes[str(sample_file)]
        blob = snap_ring.content_dir / f"{h}.dat"
        assert blob.exists()
        assert blob.read_bytes() == b"print('hello')"

    def test_snapshot_deduplicates_identical_content(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        snap_ring.snapshot([str(sample_file)], reason="first")
        snap_ring.snapshot([str(sample_file)], reason="second")
        # Only 1 content blob despite 2 snapshots
        blobs = list(snap_ring.content_dir.glob("*.dat"))
        assert len(blobs) == 1

    def test_snapshot_ring_evicts_oldest(self, snap_ring: SnapshotRing, sample_file: Path) -> None:
        # Ring max_size is 5. Create 8 snapshots.
        ids = []
        for i in range(8):
            sample_file.write_text(f"version_{i}")
            info = snap_ring.snapshot([str(sample_file)], reason=f"v{i}")
            ids.append(info.snapshot_id)
            time.sleep(0.01)  # ensure unique timestamps

        # Only 5 remain
        assert len(snap_ring._manifest) == 5
        # Oldest 3 should be gone
        for old_id in ids[:3]:
            assert snap_ring.get_snapshot(old_id) is None
        # Newest 5 should exist
        for new_id in ids[3:]:
            assert snap_ring.get_snapshot(new_id) is not None

    def test_snapshot_list_returns_newest_first(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        ids = []
        for i in range(3):
            sample_file.write_text(f"v{i}")
            info = snap_ring.snapshot([str(sample_file)], reason=f"v{i}")
            ids.append(info.snapshot_id)
            time.sleep(0.01)

        listing = snap_ring.list_snapshots()
        assert len(listing) == 3
        assert listing[0].snapshot_id == ids[2]  # newest first
        assert listing[2].snapshot_id == ids[0]  # oldest last


# ---------------------------------------------------------------------------
# Recovery Tests
# ---------------------------------------------------------------------------


class TestRecovery:
    def test_recover_restores_file_content(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        engine = RecoveryEngine(snap_ring)
        # Snapshot original content "A"
        sample_file.write_text("content_A")
        info = snap_ring.snapshot([str(sample_file)], reason="backup")
        # Overwrite with "B"
        sample_file.write_text("content_B")
        assert sample_file.read_text() == "content_B"
        # Recover from snapshot
        result = engine.recover(str(sample_file), info.snapshot_id)
        assert result.success is True
        assert sample_file.read_text() == "content_A"
        assert result.bytes_restored == len(b"content_A")

    def test_recover_creates_pre_recovery_snapshot(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        engine = RecoveryEngine(snap_ring)
        sample_file.write_text("original")
        info = snap_ring.snapshot([str(sample_file)], reason="backup")
        sample_file.write_text("modified")

        result = engine.recover(str(sample_file), info.snapshot_id)
        assert result.success is True
        assert result.pre_recovery_snapshot_id != ""
        # Verify the pre-recovery snapshot exists
        pre_snap = snap_ring.get_snapshot(result.pre_recovery_snapshot_id)
        assert pre_snap is not None
        assert pre_snap.reason == "pre_recovery"

    def test_recover_nonexistent_snapshot_fails(
        self, snap_ring: SnapshotRing, sample_file: Path
    ) -> None:
        engine = RecoveryEngine(snap_ring)
        result = engine.recover(str(sample_file), "snap_nonexistent")
        assert result.success is False
        assert "not found" in result.message


# ---------------------------------------------------------------------------
# ProjectRouter Tests
# ---------------------------------------------------------------------------


class TestProjectRouter:
    def test_router_resolves_vortex_backend(self, router: ProjectRouter) -> None:
        info = router.resolve("/Users/jesse.kemp/Dev/Vortex/backend/app/main.py")
        assert info.name == "vortex_backend"
        assert info.display_name == "Vortex Backend"

    def test_router_resolves_unknown_path(self, router: ProjectRouter) -> None:
        info = router.resolve("/Users/jesse.kemp/Dev/scripts/run_gate.sh")
        assert info.name == "repo_root"

    def test_router_returns_project_rules(self, router: ProjectRouter) -> None:
        rules = router.get_rules("/Users/jesse.kemp/Dev/Vortex/backend/app/main.py")
        assert any("GRIB" in r for r in rules)

    def test_router_resolves_cortex(self, router: ProjectRouter) -> None:
        info = router.resolve("/Users/jesse.kemp/Dev/cortex/guardian/claims.py")
        assert info.name == "cortex"

    def test_router_resolves_winfield(self, router: ProjectRouter) -> None:
        info = router.resolve("/Users/jesse.kemp/Dev/Vortex/Winfield/scripts/blend.py")
        assert info.name == "winfield"


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestGuardianIntegration:
    def test_guardian_claim_triggers_snapshot(self, tmp_path: Path) -> None:
        from cortex.guardian.process import GuardianProcess

        guardian = GuardianProcess(state_dir=tmp_path / "guardian")
        # Create a file to claim
        target = tmp_path / "target.py"
        target.write_text("def main(): pass")

        result = guardian.claim(str(target), "agent_a")
        assert result.success is True

        # Verify a snapshot was created
        snaps = guardian.list_snapshots()
        assert len(snaps) >= 1
        assert snaps[0].reason == "pre_claim"
        assert str(target) in snaps[0].files

    def test_guardian_full_lifecycle(self, tmp_path: Path) -> None:
        from cortex.guardian.process import GuardianProcess

        guardian = GuardianProcess(state_dir=tmp_path / "guardian")
        target = tmp_path / "target.py"
        target.write_text("original content")

        # Claim
        claim_result = guardian.claim(str(target), "agent_a")
        assert claim_result.success is True

        # Verify claimed
        status = guardian.status()
        assert status["active_claims"] == 1
        assert str(target) in status["claims"]

        # Release
        release_result = guardian.release(str(target), "agent_a")
        assert release_result.released is True

        # Verify released
        status = guardian.status()
        assert status["active_claims"] == 0

        # Snapshot exists from the claim
        assert status["snapshot_count"] >= 1
