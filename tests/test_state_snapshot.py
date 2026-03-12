"""
Tests for crash-resilient state snapshots (Phase 3).

Validates:
  - State persisted by one supervisor instance is restored by another
  - Corrupt state file doesn't crash — falls back to empty
  - Missing state file is a clean start
  - Atomic write produces valid JSON
  - Tick persists state automatically
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.supervisor.config import SupervisorConfig
from cortex.supervisor.core import CortexSupervisor


@pytest.fixture
def supervisor_config(tmp_path):
    """Config with all paths pointing to tmp_path for test isolation."""
    return SupervisorConfig(
        state_file=tmp_path / "state.json",
        pid_file=tmp_path / "supervisor.pid",
        log_file=tmp_path / "logs" / "supervisor.log",
        overnight_queue_file=tmp_path / "overnight_queue.json",
        enable_work_discovery=False,
        enable_self_healing=False,
        enable_ai_batching=False,
    )


@pytest.fixture
def mock_supervisor(supervisor_config):
    """Create a supervisor with mocked heavy dependencies."""
    with (
        patch("cortex.supervisor.core.BatchTaskQueue"),
        patch("cortex.supervisor.core.BatchExecutor"),
        patch("cortex.supervisor.core.HealthMonitor"),
    ):
        sup = CortexSupervisor(config=supervisor_config)
        return sup


class TestStatePersistence:
    def test_state_survives_restart(self, supervisor_config):
        """State persisted by one supervisor instance is restored by another."""
        with (
            patch("cortex.supervisor.core.BatchTaskQueue"),
            patch("cortex.supervisor.core.BatchExecutor"),
            patch("cortex.supervisor.core.HealthMonitor"),
        ):
            sup1 = CortexSupervisor(config=supervisor_config)
            sup1._dispatched_ids = {"abc123", "def456"}
            sup1._dispatched_descriptions = {"test desc": 1000.0}
            sup1._pending_batch_ids = ["batch_789"]
            sup1._tick_count = 42
            sup1._save_state()

            # Simulate restart
            sup2 = CortexSupervisor(config=supervisor_config)
            assert "abc123" in sup2._dispatched_ids
            assert "def456" in sup2._dispatched_ids
            assert sup2._pending_batch_ids == ["batch_789"]
            assert sup2._tick_count == 42
            assert "test desc" in sup2._dispatched_descriptions

    def test_corrupt_state_file_doesnt_crash(self, supervisor_config):
        """Corrupt JSON falls back to clean state, no exception."""
        supervisor_config.state_file.write_text("NOT JSON {{{")
        with (
            patch("cortex.supervisor.core.BatchTaskQueue"),
            patch("cortex.supervisor.core.BatchExecutor"),
            patch("cortex.supervisor.core.HealthMonitor"),
        ):
            sup = CortexSupervisor(config=supervisor_config)
            assert sup._dispatched_ids == set()
            assert sup._tick_count == 0

    def test_missing_state_file_is_clean_start(self, supervisor_config):
        """No state file = fresh start with defaults."""
        assert not supervisor_config.state_file.exists()
        with (
            patch("cortex.supervisor.core.BatchTaskQueue"),
            patch("cortex.supervisor.core.BatchExecutor"),
            patch("cortex.supervisor.core.HealthMonitor"),
        ):
            sup = CortexSupervisor(config=supervisor_config)
            assert sup._tick_count == 0
            assert sup._dispatched_ids == set()

    def test_atomic_write_produces_valid_json(self, mock_supervisor):
        """State file should always be valid JSON (atomic rename)."""
        mock_supervisor._dispatched_ids = {"item1", "item2"}
        mock_supervisor._tick_count = 7
        mock_supervisor._save_state()

        state = json.loads(mock_supervisor.config.state_file.read_text())
        assert set(state["dispatched_ids"]) == {"item1", "item2"}
        assert state["tick_count"] == 7
        assert "saved_at" in state

    def test_no_tmp_file_left_after_save(self, mock_supervisor):
        """The .tmp file used for atomic write should be cleaned up."""
        mock_supervisor._save_state()
        tmp_file = Path(str(mock_supervisor.config.state_file) + ".tmp")
        assert not tmp_file.exists()


class TestTickPersistsState:
    def test_tick_saves_state(self, mock_supervisor):
        """Every tick should persist state to disk."""
        # Ensure shell_queue mock has the methods tick() calls
        mock_supervisor.shell_queue.get_running_tasks.return_value = []
        mock_supervisor.shell_queue.get_next_available_tasks.return_value = []
        mock_supervisor.shell_queue._get_tasks_by_state.return_value = []

        mock_supervisor.tick()
        assert mock_supervisor.config.state_file.exists()

        state = json.loads(mock_supervisor.config.state_file.read_text())
        assert state["tick_count"] == 1
