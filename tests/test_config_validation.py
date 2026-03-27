"""Tests for SupervisorConfig validation rules."""

import os
from unittest.mock import patch

import pytest

from supervisor.config import SupervisorConfig


# ---------------------------------------------------------------------------
# 1. Valid configs pass
# ---------------------------------------------------------------------------


class TestValidConfigs:
    """Verify that well-formed configurations are accepted."""

    def test_default_config_validates(self):
        """Default SupervisorConfig should pass all validation checks."""
        config = SupervisorConfig()
        assert config.tick_interval_seconds == 30
        assert config.max_concurrent_shell_tasks == 3
        assert config.approval_policy == "gate_high"

    def test_from_env_with_valid_vars(self):
        """from_env() should honour valid environment variables."""
        env = {
            "CORTEX_SUPERVISOR_TICK_INTERVAL": "10",
            "CORTEX_SUPERVISOR_HEALTH_INTERVAL": "120",
            "CORTEX_SUPERVISOR_DISCOVERY_INTERVAL": "600",
            "CORTEX_SUPERVISOR_MAX_CONCURRENT": "5",
            "CORTEX_SUPERVISOR_STALE_HOURS": "8",
        }
        with patch.dict(os.environ, env, clear=False):
            config = SupervisorConfig.from_env()

        assert config.tick_interval_seconds == 10
        assert config.health_check_interval_seconds == 120
        assert config.work_discovery_interval_seconds == 600
        assert config.max_concurrent_shell_tasks == 5
        assert config.stale_task_hours == 8


# ---------------------------------------------------------------------------
# 2. Invalid configs rejected
# ---------------------------------------------------------------------------


class TestInvalidConfigs:
    """Verify that out-of-range or invalid values are rejected."""

    def test_tick_interval_zero_rejected(self):
        with pytest.raises(ValueError, match="tick_interval_seconds"):
            SupervisorConfig(tick_interval_seconds=0)

    def test_tick_interval_too_large_rejected(self):
        with pytest.raises(ValueError, match="tick_interval_seconds"):
            SupervisorConfig(tick_interval_seconds=9999)

    def test_max_concurrent_zero_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_shell_tasks"):
            SupervisorConfig(max_concurrent_shell_tasks=0)

    def test_max_concurrent_too_large_rejected(self):
        with pytest.raises(ValueError, match="max_concurrent_shell_tasks"):
            SupervisorConfig(max_concurrent_shell_tasks=200)

    def test_stale_task_hours_zero_rejected(self):
        with pytest.raises(ValueError, match="stale_task_hours"):
            SupervisorConfig(stale_task_hours=0)

    def test_max_retries_zero_rejected(self):
        with pytest.raises(ValueError, match="max_retries"):
            SupervisorConfig(max_retries=0)

    def test_ab_baseline_ratio_above_one_rejected(self):
        with pytest.raises(ValueError, match="ab_baseline_ratio"):
            SupervisorConfig(ab_baseline_ratio=2.0)

    def test_approval_policy_invalid_rejected(self):
        with pytest.raises(ValueError, match="approval_policy"):
            SupervisorConfig(approval_policy="invalid")


# ---------------------------------------------------------------------------
# 3. from_env safety
# ---------------------------------------------------------------------------


class TestFromEnvSafety:
    """Verify that from_env() handles bad or missing env vars gracefully."""

    def test_non_numeric_env_var_falls_back_to_default(self):
        """A non-numeric value should be silently replaced by the default."""
        env = {"CORTEX_SUPERVISOR_TICK_INTERVAL": "not_a_number"}
        with patch.dict(os.environ, env, clear=False):
            config = SupervisorConfig.from_env()

        assert config.tick_interval_seconds == 30  # default

    def test_missing_env_var_uses_default(self):
        """When the env var is absent, the default value should be used."""
        # Remove the var if it happens to exist in the test environment
        env_removals = {
            "CORTEX_SUPERVISOR_TICK_INTERVAL": "",
            "CORTEX_SUPERVISOR_HEALTH_INTERVAL": "",
            "CORTEX_SUPERVISOR_DISCOVERY_INTERVAL": "",
            "CORTEX_SUPERVISOR_MAX_CONCURRENT": "",
            "CORTEX_SUPERVISOR_STALE_HOURS": "",
        }
        with patch.dict(os.environ, {}, clear=True):
            config = SupervisorConfig.from_env()

        assert config.tick_interval_seconds == 30
        assert config.health_check_interval_seconds == 60
        assert config.work_discovery_interval_seconds == 300
        assert config.max_concurrent_shell_tasks == 3
        assert config.stale_task_hours == 4
