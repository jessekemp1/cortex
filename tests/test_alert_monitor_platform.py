"""
Tests for platform-agnostic alert monitor (Phase 1).

Validates:
  - Platform detection returns valid values
  - Linux restart uses systemctl
  - macOS restart uses launchctl
  - Stale service URLs are fixed (bridge removed, runtime port 8765)
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cortex import alert_monitor
from cortex.alert_monitor import (
    SERVICES,
    TIER1_RESTART_CONFIG,
    _attempt_restart,
    _detect_platform,
)


class TestPlatformDetection:
    def test_detect_platform_returns_valid(self):
        result = _detect_platform()
        assert result in ("macos", "linux")

    def test_detect_platform_darwin_returns_macos(self, monkeypatch):
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        assert _detect_platform() == "macos"

    def test_detect_platform_linux_returns_linux(self, monkeypatch):
        monkeypatch.setattr("platform.system", lambda: "Linux")
        assert _detect_platform() == "linux"


class TestRestartConfig:
    def test_restart_config_has_both_platforms(self):
        assert "macos" in TIER1_RESTART_CONFIG
        assert "linux" in TIER1_RESTART_CONFIG

    def test_macos_config_has_launchd_labels(self):
        macos = TIER1_RESTART_CONFIG["macos"]
        assert "vortex-backend" in macos
        assert macos["vortex-backend"] == "com.vortexv2.backend"

    def test_linux_config_has_systemd_units(self):
        linux = TIER1_RESTART_CONFIG["linux"]
        assert "vortex-backend" in linux
        assert linux["vortex-backend"] == "vortexv2-backend"

    def test_linux_config_has_cortex_runtime(self):
        linux = TIER1_RESTART_CONFIG["linux"]
        assert "cortex-runtime" in linux
        assert linux["cortex-runtime"] == "cortex-runtime"


class TestPlatformRestart:
    def test_linux_restart_uses_systemctl(self, monkeypatch):
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "linux")
        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(alert_monitor, "_recent_restart_count", lambda s: 0)

        result = _attempt_restart("vortex-backend")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "systemctl"
        assert "--user" in cmd
        assert "restart" in cmd
        assert "vortexv2-backend" in cmd

    def test_macos_restart_uses_launchctl(self, monkeypatch):
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "macos")
        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(alert_monitor, "_recent_restart_count", lambda s: 0)

        result = _attempt_restart("vortex-backend")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "launchctl"
        assert "kickstart" in cmd

    def test_unknown_service_returns_false(self, monkeypatch):
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "linux")
        result = _attempt_restart("nonexistent-service")
        assert result is False

    def test_restart_rate_limited(self, monkeypatch):
        """Restart is suppressed when rate limit is hit."""
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "linux")
        monkeypatch.setattr(alert_monitor, "_recent_restart_count", lambda s: 99)

        result = _attempt_restart("vortex-backend")
        assert result is False


class TestStaleServiceURLs:
    def test_cortex_bridge_removed_from_services(self):
        """cortex-bridge was disabled — should not be monitored."""
        names = [name for name, _ in SERVICES]
        assert "cortex-bridge" not in names

    def test_cortex_runtime_port_8765(self):
        """cortex-runtime should use port 8765, not stale 8003."""
        urls = {name: url for name, url in SERVICES}
        assert "cortex-runtime" in urls
        assert "8765" in urls["cortex-runtime"]
        assert "8003" not in urls["cortex-runtime"]
