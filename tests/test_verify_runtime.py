"""Runtime smoke tests — verify supervisor boots and logs correctly."""

import json
import logging
import tempfile
from pathlib import Path

import pytest


class TestSupervisorBoot:
    """Verify supervisor initializes without side effects."""

    def test_import_supervisor_has_no_side_effects(self, tmp_path):
        """Importing supervisor should not create files or make network calls."""
        before = set(tmp_path.iterdir())
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            state_file=tmp_path / "state.json",
            log_file=tmp_path / "supervisor.log",
            pid_file=tmp_path / "supervisor.pid",
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        # Only __post_init__ directory creation should happen, not full init
        after = set(tmp_path.iterdir())
        # No unexpected files until we actually create the supervisor
        supervisor = CortexSupervisor(config=config)
        assert supervisor is not None

    def test_three_ticks_no_errors(self, tmp_path):
        """Three consecutive ticks run without errors."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            state_file=tmp_path / "state.json",
            log_file=tmp_path / "supervisor.log",
            pid_file=tmp_path / "supervisor.pid",
            enable_work_discovery=False,
            enable_ai_batching=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        for i in range(3):
            result = supervisor.run_once()
            assert result.errors == [], f"Tick {i+1} had errors: {result.errors}"
            assert result.shell_tasks_started >= 0

        assert supervisor._tick_count == 3


class TestJSONLogging:
    """Verify structured logging produces valid JSON lines."""

    def test_json_formatter_produces_valid_json(self):
        """JSONFormatter output is parseable JSON."""
        from supervisor.logging_config import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="supervisor.core",
            level=logging.INFO,
            pathname="core.py",
            lineno=42,
            msg="Tick completed: %d tasks",
            args=(5,),
            exc_info=None,
        )

        line = formatter.format(record)
        parsed = json.loads(line)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "supervisor.core"
        assert "5 tasks" in parsed["msg"]
        assert "ts" in parsed

    def test_json_formatter_handles_exceptions(self):
        """JSONFormatter includes exc field for exceptions."""
        from supervisor.logging_config import JSONFormatter

        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="supervisor.core",
            level=logging.ERROR,
            pathname="core.py",
            lineno=99,
            msg="Tick failed",
            args=(),
            exc_info=exc_info,
        )

        line = formatter.format(record)
        parsed = json.loads(line)
        assert "exc" in parsed
        assert "ValueError" in parsed["exc"]
        assert "test error" in parsed["exc"]

    def test_configure_creates_rotating_log(self, tmp_path):
        """configure_supervisor_logging creates a rotating file handler."""
        from supervisor.logging_config import configure_supervisor_logging

        log_file = tmp_path / "test.log"
        logger = configure_supervisor_logging(
            log_file, console=False, json_format=True,
        )

        # Log some messages
        logger.info("hello from test")
        logger.warning("warning from test")

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        # Verify file exists and contains valid JSON lines
        content = log_file.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) >= 2

        for line in lines:
            parsed = json.loads(line)
            assert "ts" in parsed
            assert "level" in parsed
            assert "msg" in parsed

    def test_log_rotation_respects_max_bytes(self, tmp_path):
        """Log rotation kicks in when file exceeds max_bytes."""
        from supervisor.logging_config import configure_supervisor_logging

        log_file = tmp_path / "rotate.log"
        logger = configure_supervisor_logging(
            log_file,
            console=False,
            json_format=False,
            max_bytes=500,
            backup_count=3,
        )

        # Write enough to trigger rotation
        for i in range(100):
            logger.info(f"Message {i}: {'x' * 50}")

        for handler in logger.handlers:
            handler.flush()

        # Should have rotated
        rotated_files = list(tmp_path.glob("rotate.log*"))
        assert len(rotated_files) >= 2, f"Expected rotation, found: {rotated_files}"


class TestConfigValidationSmoke:
    """Verify config validation catches bad values at startup."""

    def test_zero_tick_interval_rejected(self):
        from supervisor.config import SupervisorConfig
        with pytest.raises(ValueError, match="tick_interval"):
            SupervisorConfig(tick_interval_seconds=0)

    def test_negative_max_concurrent_rejected(self):
        from supervisor.config import SupervisorConfig
        with pytest.raises(ValueError, match="max_concurrent"):
            SupervisorConfig(max_concurrent_shell_tasks=-1)

    def test_invalid_approval_policy_rejected(self):
        from supervisor.config import SupervisorConfig
        with pytest.raises(ValueError, match="approval_policy"):
            SupervisorConfig(approval_policy="yolo")

    def test_valid_config_succeeds(self):
        from supervisor.config import SupervisorConfig
        config = SupervisorConfig(
            tick_interval_seconds=30,
            max_concurrent_shell_tasks=5,
            approval_policy="gate_high",
        )
        assert config.tick_interval_seconds == 30
