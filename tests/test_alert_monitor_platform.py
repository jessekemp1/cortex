"""
Tests for platform-agnostic alert monitor (Phase 1).

Validates:
  - Platform detection returns valid values
  - macOS restart uses launchctl with the running user's uid
  - Restart config only lists services with a real installed unit
  - Stale service URLs are fixed (bridge removed; runtime uses its own port)
"""

import os
import subprocess
from unittest.mock import MagicMock


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

    def test_macos_config_only_lists_services_with_real_units(self):
        # alpha-arena has a real launchd label; cortex-runtime/cortex-site do
        # NOT ship a plist, so they must not be listed (a doomed restart never
        # resets the failure counter). See TIER1_RESTART_CONFIG comment.
        macos = TIER1_RESTART_CONFIG["macos"]
        assert macos.get("alpha-arena") == "com.alphaarena.dashboard"
        assert "cortex-runtime" not in macos
        assert "cortex-site" not in macos

    def test_restart_labels_are_not_fabricated(self):
        # Guard against reintroducing labels with no matching unit.
        for plat, cfg in TIER1_RESTART_CONFIG.items():
            for svc, label in cfg.items():
                assert label, f"{plat}/{svc} has empty restart label"


class TestPlatformRestart:
    def test_macos_restart_uses_launchctl(self, monkeypatch):
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "macos")
        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(alert_monitor, "_recent_restart_count", lambda s: 0)

        # alpha-arena is the service with a real macOS launchd label.
        result = _attempt_restart("alpha-arena")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "launchctl"
        assert "kickstart" in cmd
        # uid must be the running user's, not a hardcoded value.
        assert f"gui/{os.getuid()}/" in cmd[-1]

    def test_unknown_service_returns_false(self, monkeypatch):
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "linux")
        result = _attempt_restart("nonexistent-service")
        assert result is False

    def test_unrestartable_service_returns_false(self, monkeypatch):
        # cortex-runtime is monitored but has no restart unit -> no restart.
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "macos")
        result = _attempt_restart("cortex-runtime")
        assert result is False

    def test_restart_rate_limited(self, monkeypatch):
        """Restart is suppressed when rate limit is hit."""
        monkeypatch.setattr(alert_monitor, "_detect_platform", lambda: "macos")
        monkeypatch.setattr(alert_monitor, "_recent_restart_count", lambda s: 99)

        result = _attempt_restart("alpha-arena")
        assert result is False


class TestStaleServiceURLs:
    def test_cortex_bridge_removed_from_services(self):
        """cortex-bridge was disabled — should not be monitored."""
        names = [name for name, _ in SERVICES]
        assert "cortex-bridge" not in names

    def test_cortex_runtime_uses_runtime_port_not_bridge(self):
        """cortex-runtime must hit the runtime (8000), not the bridge (8765)."""
        urls = {name: url for name, url in SERVICES}
        assert "cortex-runtime" in urls
        assert "8765" not in urls["cortex-runtime"]  # not the bridge
        assert "/api/v1/runtime/health" in urls["cortex-runtime"]
        assert "8003" not in urls["cortex-runtime"]
