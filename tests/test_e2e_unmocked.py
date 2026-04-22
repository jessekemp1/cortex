"""Unmocked end-to-end tests exercising real components.

These tests verify full pipelines without mocking, using temporary
directories to avoid side effects on real state.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestSupervisorTickToOutcome:
    """E2E: supervisor tick → task execution → state persistence."""

    def test_full_tick_cycle_persists_state(self, tmp_path):
        """Run a complete tick cycle and verify state is written to disk."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        state_file = tmp_path / "state.json"
        config = SupervisorConfig(
            state_file=state_file,
            log_file=tmp_path / "supervisor.log",
            pid_file=tmp_path / "supervisor.pid",
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        # Run 3 ticks
        for _ in range(3):
            result = supervisor.run_once()
            assert result.errors == []

        # State file should exist and contain valid JSON
        assert state_file.exists()
        import json
        state = json.loads(state_file.read_text())
        assert isinstance(state, dict)

        # Queue summary should reflect empty-but-healthy state
        summary = supervisor.get_queue_summary()
        assert summary["total_tasks"] >= 0
        assert summary["running"] == 0

    def test_tick_with_health_check(self, tmp_path):
        """Tick with health checking enabled finds no issues on empty queue."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            state_file=tmp_path / "state.json",
            log_file=tmp_path / "supervisor.log",
            pid_file=tmp_path / "supervisor.pid",
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=True,
            health_check_interval_seconds=1,
        )
        supervisor = CortexSupervisor(config=config)
        result = supervisor.run_once()

        assert result.errors == []
        assert result.tasks_healed == 0


class TestGuardianClaimSnapshotRecover:
    """E2E: guardian claim → snapshot → modify → recover."""

    def test_full_guardian_lifecycle(self, tmp_path):
        """Claim a file, snapshot it, modify it, and recover."""
        from guardian.claims import FileClaimManager
        from guardian.recovery import RecoveryEngine
        from guardian.snapshots import SnapshotRing

        # Setup
        claims_file = tmp_path / "claims.json"
        snap_dir = tmp_path / "snapshots"
        test_file = tmp_path / "target.py"
        test_file.write_text("original_content = True\n")

        mgr = FileClaimManager(state_file=claims_file)
        ring = SnapshotRing(base_dir=snap_dir)
        engine = RecoveryEngine(ring)

        # 1. Claim the file
        claim = mgr.claim(str(test_file), "agent_e2e", ttl=300)
        assert claim.success is True

        # 2. Snapshot it
        snap_info = ring.snapshot([str(test_file)], reason="e2e_test")
        assert str(test_file) in snap_info.files
        assert len(snap_info.file_hashes) == 1

        # 3. Modify the file
        test_file.write_text("modified_content = True\n")
        assert test_file.read_text() == "modified_content = True\n"

        # 4. Recover from snapshot
        result = engine.recover(str(test_file), snap_info.snapshot_id)
        assert result.success is True
        assert test_file.read_text() == "original_content = True\n"
        assert result.bytes_restored == len(b"original_content = True\n")

        # 5. Release the claim
        release = mgr.release(str(test_file), "agent_e2e")
        assert release.released is True


class TestConsolidatedStoreRoundtrip:
    """E2E: log outcomes → query → verify data integrity."""

    def test_outcome_roundtrip(self, tmp_path, monkeypatch):
        """Log outcomes and verify they round-trip through the store."""
        monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
        from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "e2e.db")

        # 1. Log command metrics
        store.log_command_metric(command="cortex next", duration_ms=150, success=True)
        store.log_command_metric(command="cortex next", duration_ms=200, success=True)
        store.log_command_metric(command="cortex status", duration_ms=50, success=False)

        # 2. Query back
        metrics = store.load_command_metrics(days=1)
        assert len(metrics) == 3
        commands = {m["command"] for m in metrics}
        assert "cortex next" in commands
        assert "cortex status" in commands
        durations = [m["duration_ms"] for m in metrics]
        assert 150 in durations
        assert 50 in durations

        # 3. Verify storage info reflects all data
        info = store.get_storage_info()
        assert info["backend"] == "sqlite"
        assert info["schema_version"] == 2
        assert info["tables"]["command_metrics"] == 3

    def test_feedback_roundtrip(self, tmp_path, monkeypatch):
        """Log feedback and verify it persists."""
        monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
        from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "e2e_fb.db")

        # Log feedback
        store.log_recommendation_outcome(
            recommendation_id="rec_001",
            recommendation_title="Fix auth bug",
            recommendation_type="action",
            priority="HIGH",
            confidence=0.9,
            followed=True,
            outcome="success",
        )
        store.log_recommendation_outcome(
            recommendation_id="rec_002",
            recommendation_title="Add tests",
            recommendation_type="action",
            priority="NORMAL",
            confidence=0.7,
            followed=False,
            outcome="skipped",
        )

        # Query back
        outcomes = store.load_recommendation_outcomes(days=1)
        assert len(outcomes) == 2
        titles = {o["recommendation_title"] for o in outcomes}
        assert "Fix auth bug" in titles
        assert "Add tests" in titles
