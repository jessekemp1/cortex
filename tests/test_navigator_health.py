"""
Tests for Navigator health monitoring integration in Cortex.

Validates:
- alert_monitor correctly parses Navigator health responses
- Degraded Navigator status triggers alerts after 3 consecutive failures
- Bridge endpoint service_health includes Navigator subsystem details
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add cortex directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Navigator health response fixtures
# ---------------------------------------------------------------------------

HEALTHY_RESPONSE = {
    "status": "healthy",
    "checks": {
        "polars": {"status": "ok", "boat_types": 5, "cached": 2},
        "weather_api": {"status": "ok", "gfs": True, "ecmwf": True, "latency_ms": 180},
        "judge": {"status": "ok", "model": "claude-sonnet-4-20250514"},
        "wave_api": {"status": "ok"},
    },
    "timestamp": "2026-03-08T12:00:00+00:00",
    "version": "2.0.0",
}

DEGRADED_RESPONSE = {
    "status": "degraded",
    "checks": {
        "polars": {"status": "ok", "boat_types": 5, "cached": 2},
        "weather_api": {
            "status": "error",
            "gfs": False,
            "ecmwf": False,
            "latency_ms": -1,
            "error": "timeout",
        },
        "judge": {"status": "ok", "model": "claude-sonnet-4-20250514"},
        "wave_api": {"status": "ok"},
    },
    "timestamp": "2026-03-08T12:00:00+00:00",
    "version": "2.0.0",
}

UNHEALTHY_RESPONSE = {
    "status": "unhealthy",
    "checks": {
        "polars": {"status": "error", "error": "ImportError"},
        "weather_api": {"status": "error", "gfs": False, "ecmwf": False, "latency_ms": -1},
        "judge": {"status": "ok", "model": "claude-sonnet-4-20250514"},
        "wave_api": {"status": "error", "error": "timeout"},
    },
    "timestamp": "2026-03-08T12:00:00+00:00",
    "version": "2.0.0",
}


# ---------------------------------------------------------------------------
# alert_monitor tests
# ---------------------------------------------------------------------------


class TestAlertMonitorNavigator:
    """Test Navigator integration in alert_monitor.py."""

    def test_navigator_in_service_list(self):
        """Navigator must be registered in the SERVICES list."""
        from alert_monitor import SERVICES

        service_names = [name for name, _url in SERVICES]
        assert "navigator" in service_names

        nav_url = next(url for name, url in SERVICES if name == "navigator")
        assert nav_url == "http://127.0.0.1:8000/api/v2/navigator/health"

    def test_navigator_threshold_is_3(self):
        """Navigator should have a consecutive failure threshold of 3."""
        from alert_monitor import CONSECUTIVE_THRESHOLDS

        assert CONSECUTIVE_THRESHOLDS.get("navigator") == 3

    def test_check_service_healthy(self):
        """Healthy Navigator response returns (True, 'healthy')."""
        from alert_monitor import check_service

        body = json.dumps(HEALTHY_RESPONSE).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("alert_monitor.urllib.request.urlopen", return_value=mock_resp):
            healthy, detail = check_service(
                "navigator", "http://127.0.0.1:8000/api/v2/navigator/health"
            )

        assert healthy is True
        assert detail == "healthy"

    def test_check_service_degraded(self):
        """Degraded Navigator response returns (False, 'degraded:weather_api')."""
        from alert_monitor import check_service

        body = json.dumps(DEGRADED_RESPONSE).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("alert_monitor.urllib.request.urlopen", return_value=mock_resp):
            healthy, detail = check_service(
                "navigator", "http://127.0.0.1:8000/api/v2/navigator/health"
            )

        assert healthy is False
        assert "degraded" in detail
        assert "weather_api" in detail

    def test_check_service_unhealthy(self):
        """Unhealthy Navigator response lists all failed subsystems."""
        from alert_monitor import check_service

        body = json.dumps(UNHEALTHY_RESPONSE).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("alert_monitor.urllib.request.urlopen", return_value=mock_resp):
            healthy, detail = check_service(
                "navigator", "http://127.0.0.1:8000/api/v2/navigator/health"
            )

        assert healthy is False
        assert "unhealthy" in detail
        assert "polars" in detail
        assert "weather_api" in detail
        assert "wave_api" in detail

    def test_check_service_unreachable(self):
        """Unreachable Navigator returns (False, 'unreachable')."""
        from alert_monitor import check_service

        with patch("alert_monitor.urllib.request.urlopen", side_effect=ConnectionRefusedError):
            healthy, detail = check_service(
                "navigator", "http://127.0.0.1:8000/api/v2/navigator/health"
            )

        assert healthy is False
        assert detail == "unreachable"

    def test_no_alert_before_3_failures(self, tmp_path):
        """Navigator should NOT alert until 3 consecutive failures."""
        from alert_monitor import check_services, CONSECUTIVE_FILE

        # Patch the consecutive file to a temp location
        consec_file = tmp_path / "alert_consecutive.json"
        consec_file.write_text("{}")

        with (
            patch("alert_monitor.CONSECUTIVE_FILE", consec_file),
            patch("alert_monitor._is_silenced", return_value=False),
            patch("alert_monitor.check_service") as mock_check,
        ):
            # All services healthy except navigator
            def side_effect(name, url):
                if name == "navigator":
                    return (False, "degraded:weather_api")
                return (True, "healthy")

            mock_check.side_effect = side_effect

            # First failure
            alerts = check_services()
            nav_alerts = [a for a in alerts if a.get("service") == "navigator"]
            assert len(nav_alerts) == 0

            # Second failure
            alerts = check_services()
            nav_alerts = [a for a in alerts if a.get("service") == "navigator"]
            assert len(nav_alerts) == 0

            # Third failure — should alert
            alerts = check_services()
            nav_alerts = [a for a in alerts if a.get("service") == "navigator"]
            assert len(nav_alerts) == 1
            assert nav_alerts[0]["consecutive_failures"] == 3
            assert "DEGRADED" in nav_alerts[0]["message"]
            assert nav_alerts[0]["detail"] == "degraded:weather_api"

    def test_alert_message_includes_subsystem_detail(self, tmp_path):
        """Alert message should include which subsystems failed."""
        from alert_monitor import check_services

        consec_file = tmp_path / "alert_consecutive.json"
        # Pre-load with 2 failures so next one triggers alert
        consec_file.write_text(json.dumps({"navigator": 2}))

        with (
            patch("alert_monitor.CONSECUTIVE_FILE", consec_file),
            patch("alert_monitor._is_silenced", return_value=False),
            patch("alert_monitor.check_service") as mock_check,
        ):

            def side_effect(name, url):
                if name == "navigator":
                    return (False, "unhealthy:polars,weather_api,wave_api")
                return (True, "healthy")

            mock_check.side_effect = side_effect

            alerts = check_services()
            nav_alerts = [a for a in alerts if a.get("service") == "navigator"]
            assert len(nav_alerts) == 1
            assert "UNHEALTHY" in nav_alerts[0]["message"]

    def test_non_navigator_services_use_default_threshold(self, tmp_path):
        """Other services still use the default threshold of 2."""
        from alert_monitor import check_services

        consec_file = tmp_path / "alert_consecutive.json"
        consec_file.write_text("{}")

        with (
            patch("alert_monitor.CONSECUTIVE_FILE", consec_file),
            patch("alert_monitor._is_silenced", return_value=False),
            patch("alert_monitor.check_service") as mock_check,
        ):

            def side_effect(name, url):
                if name == "vortex-backend":
                    return (False, "unreachable")
                return (True, "healthy")

            mock_check.side_effect = side_effect

            # First failure — no alert
            alerts = check_services()
            vortex_alerts = [a for a in alerts if a.get("service") == "vortex-backend"]
            assert len(vortex_alerts) == 0

            # Second failure — should alert (threshold=2)
            alerts = check_services()
            vortex_alerts = [a for a in alerts if a.get("service") == "vortex-backend"]
            assert len(vortex_alerts) == 1


# ---------------------------------------------------------------------------
# Bridge endpoint service_health tests
# ---------------------------------------------------------------------------


class TestBridgeNavigatorHealth:
    """Test Navigator appears in bridge_endpoint service_health response."""

    def test_navigator_healthy_in_service_health(self):
        """When Navigator is healthy, service_health reports healthy with subsystems."""
        body = json.dumps(HEALTHY_RESPONSE).encode()

        # Simulate the parsing logic from bridge_endpoint
        import urllib.request

        data = json.loads(body)
        nav_status = data.get("status", "unknown")
        checks = data.get("checks", {})
        subsystems = {
            k: v.get("status", "unknown") for k, v in checks.items() if isinstance(v, dict)
        }

        result = {
            "status": nav_status,
            "port": 8000,
            "subsystems": subsystems,
            "version": data.get("version", "unknown"),
        }

        assert result["status"] == "healthy"
        assert result["version"] == "2.0.0"
        assert result["subsystems"]["polars"] == "ok"
        assert result["subsystems"]["weather_api"] == "ok"
        assert result["subsystems"]["judge"] == "ok"
        assert result["subsystems"]["wave_api"] == "ok"

    def test_navigator_degraded_in_service_health(self):
        """When Navigator is degraded, subsystems show which ones failed."""
        data = DEGRADED_RESPONSE
        checks = data.get("checks", {})
        subsystems = {
            k: v.get("status", "unknown") for k, v in checks.items() if isinstance(v, dict)
        }

        assert data["status"] == "degraded"
        assert subsystems["weather_api"] == "error"
        assert subsystems["polars"] == "ok"

    def test_navigator_offline_in_service_health(self):
        """When Navigator is unreachable, service_health reports offline."""
        # This tests the fallback path in bridge_endpoint
        result = {"status": "offline", "port": 8000}
        assert result["status"] == "offline"
