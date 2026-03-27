"""Edge case and error path tests for core modules.

Tests boundary conditions, empty inputs, invalid data, and error
recovery across supervisor, guardian, and intelligence modules.
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Supervisor edge cases ────────────────────────────────────────────────────


class TestSupervisorEdgeCases:
    """Edge cases for the supervisor tick loop."""

    def test_tick_with_corrupt_state_file(self, tmp_path):
        """Supervisor should start fresh if state file is corrupt."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        state_file = tmp_path / "state.json"
        state_file.write_text("{invalid json!!")

        config = SupervisorConfig(
            state_file=state_file,
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)
        # Should not crash — falls back to empty state
        result = supervisor.run_once()
        assert result.errors == []
        assert result.shell_tasks_started == 0

    def test_tick_with_empty_state_file(self, tmp_path):
        """Supervisor handles empty state file gracefully."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        state_file = tmp_path / "state.json"
        state_file.write_text("")

        config = SupervisorConfig(
            state_file=state_file,
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)
        result = supervisor.run_once()
        assert result.errors == []

    def test_tick_count_increments(self, tmp_path):
        """Each tick increments the counter."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            state_file=tmp_path / "state.json",
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)
        supervisor.run_once()
        supervisor.run_once()
        supervisor.run_once()
        assert supervisor._tick_count == 3

    def test_queue_summary_with_no_tasks(self):
        """Queue summary works when queue is empty."""
        from supervisor.core import CortexSupervisor

        supervisor = CortexSupervisor()
        summary = supervisor.get_queue_summary()
        assert summary["total_tasks"] >= 0
        assert summary["running"] >= 0
        assert summary["ready"] >= 0


# ── Guardian edge cases ──────────────────────────────────────────────────────


class TestGuardianEdgeCases:
    """Edge cases for file claims and snapshots."""

    def test_claim_nonexistent_path(self, tmp_path):
        """Claiming a path that doesn't exist should still work (advisory)."""
        from guardian.claims import FileClaimManager

        mgr = FileClaimManager(state_file=tmp_path / "claims.json")
        result = mgr.claim("/nonexistent/path.py", "agent_a", ttl=60)
        assert result.success is True

    def test_double_claim_same_agent(self, tmp_path):
        """Same agent can re-claim its own file."""
        from guardian.claims import FileClaimManager

        mgr = FileClaimManager(state_file=tmp_path / "claims.json")
        mgr.claim("/tmp/foo.py", "agent_a", ttl=60)
        result = mgr.claim("/tmp/foo.py", "agent_a", ttl=60)
        assert result.success is True
        assert result.agent_id == "agent_a"

    def test_claim_conflict_different_agent(self, tmp_path):
        """Different agent cannot claim an actively held file."""
        from guardian.claims import FileClaimManager

        mgr = FileClaimManager(state_file=tmp_path / "claims.json")
        mgr.claim("/tmp/foo.py", "agent_a", ttl=300)
        result = mgr.claim("/tmp/foo.py", "agent_b", ttl=300)
        assert result.success is False

    def test_snapshot_empty_file_list(self, tmp_path):
        """Snapshotting empty list creates an empty snapshot."""
        from guardian.snapshots import SnapshotRing

        ring = SnapshotRing(base_dir=tmp_path / "snaps")
        info = ring.snapshot([], reason="test")
        assert info.files == []
        assert info.file_hashes == {}

    def test_snapshot_missing_file(self, tmp_path):
        """Snapshotting a nonexistent file skips it silently."""
        from guardian.snapshots import SnapshotRing

        ring = SnapshotRing(base_dir=tmp_path / "snaps")
        info = ring.snapshot(["/nonexistent/file.py"], reason="test")
        assert info.files == []

    def test_recover_nonexistent_snapshot(self, tmp_path):
        """Recovery with bad snapshot ID returns failure."""
        from guardian.recovery import RecoveryEngine
        from guardian.snapshots import SnapshotRing

        ring = SnapshotRing(base_dir=tmp_path / "snaps")
        engine = RecoveryEngine(ring)
        result = engine.recover("/tmp/foo.py", "snap_nonexistent")
        assert result.success is False
        assert "not found" in result.message


# ── Consolidated store edge cases ────────────────────────────────────────────


class TestConsolidatedStoreEdgeCases:
    """Edge cases for the outcome store."""

    def test_load_empty_tables(self, tmp_path):
        """Loading from empty tables returns empty lists."""
        from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
        outcomes = store.load_recommendation_outcomes(days=30)
        assert outcomes == []

    def test_log_command_metric_zero_duration(self, tmp_path):
        """Zero-duration command metrics are valid."""
        from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
        store.log_command_metric(command="instant", duration_ms=0, success=True)
        metrics = store.load_command_metrics(days=1)
        assert len(metrics) == 1
        assert metrics[0]["duration_ms"] == 0

    def test_get_storage_info_on_fresh_db(self, tmp_path):
        """Storage info works on empty database."""
        from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

        store = ConsolidatedOutcomeStore(db_path=tmp_path / "test.db")
        info = store.get_storage_info()
        assert info["backend"] == "sqlite"
        assert info["schema_version"] == 2
        assert all(v == 0 for v in info["tables"].values())


# ── Quality evaluator edge cases ─────────────────────────────────────────────


class TestQualityEvaluatorEdgeCases:
    """Edge cases for the quality evaluator."""

    def test_empty_output(self):
        """Empty output gets low score."""
        from supervisor.quality_evaluator import QualityEvaluator

        evaluator = QualityEvaluator()
        result = MagicMock(success=True, output="")
        work_item = MagicMock()
        evaluation = evaluator.evaluate_heuristic(work_item, result)
        assert evaluation.overall_score == 0.2

    def test_none_output(self):
        """None output doesn't crash."""
        from supervisor.quality_evaluator import QualityEvaluator

        evaluator = QualityEvaluator()
        result = MagicMock(success=True, output=None)
        work_item = MagicMock()
        evaluation = evaluator.evaluate_heuristic(work_item, result)
        assert 0.0 <= evaluation.overall_score <= 1.0

    def test_missing_output_attr(self):
        """Result without output attribute doesn't crash."""
        from supervisor.quality_evaluator import QualityEvaluator

        evaluator = QualityEvaluator()
        result = MagicMock(spec=["success"])
        result.success = True
        work_item = MagicMock()
        evaluation = evaluator.evaluate_heuristic(work_item, result)
        assert 0.0 <= evaluation.overall_score <= 1.0


# ── Workflow runner edge cases ───────────────────────────────────────────────


class TestWorkflowConditionEdgeCases:
    """Edge cases for the safe condition evaluator."""

    def _eval(self, condition, steps):
        from workflows.runner import WorkflowRunner
        return WorkflowRunner._safe_eval_condition(condition, steps)

    def test_empty_condition(self):
        assert self._eval("", {}) is False

    def test_unknown_step(self):
        assert self._eval("steps.missing.success", {}) is False

    def test_valid_truthy_check(self):
        steps = {"build": {"success": True, "exit_code": 0}}
        assert self._eval("steps.build.success", steps) is True

    def test_valid_equality_check(self):
        steps = {"build": {"success": True, "exit_code": 0}}
        assert self._eval("steps.build.exit_code == 0", steps) is True

    def test_valid_inequality_check(self):
        steps = {"build": {"success": True, "exit_code": 1}}
        assert self._eval("steps.build.exit_code != 0", steps) is True

    def test_injection_attempt_rejected(self):
        """Malicious condition syntax is rejected."""
        assert self._eval("__import__('os').system('rm -rf /')", {}) is False

    def test_nested_attribute_rejected(self):
        """Deep attribute access beyond steps.<id>.<field> is rejected."""
        assert self._eval("steps.build.success.real", {}) is False
