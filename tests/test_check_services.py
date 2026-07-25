"""Tests for alert_monitor.check_service / check_services.

Restores coverage lost when tests/test_navigator_health.py was deleted during
the vortex/navigator decommission: the consecutive-failure counting, threshold
gating, alert emission, structured-health parsing, and stale-counter pruning of
the central alerting loop.
"""

import json
from unittest.mock import patch

from cortex import alert_monitor
from cortex.alert_monitor import check_service, check_services


class _FakeResp:
    def __init__(self, status=200, body=b""):
        self.status = status
        self._body = body

    def read(self, *_):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestCheckService:
    def test_plain_200_is_healthy(self):
        with patch("urllib.request.urlopen", return_value=_FakeResp(200, b"<html>ok</html>")):
            healthy, detail = check_service("svc", "http://x/docs")
        assert healthy is True
        assert detail == "healthy"

    def test_json_status_healthy(self):
        body = json.dumps({"status": "healthy"}).encode()
        with patch("urllib.request.urlopen", return_value=_FakeResp(200, body)):
            healthy, detail = check_service("svc", "http://x/health")
        assert healthy is True

    def test_json_degraded_is_not_healthy(self):
        # A 200 with a degraded body must NOT be masked as healthy.
        body = json.dumps({"status": "degraded"}).encode()
        with patch("urllib.request.urlopen", return_value=_FakeResp(200, body)):
            healthy, detail = check_service("svc", "http://x/health")
        assert healthy is False
        assert detail == "degraded"

    def test_json_unhealthy_is_not_healthy(self):
        body = json.dumps({"status": "unhealthy"}).encode()
        with patch("urllib.request.urlopen", return_value=_FakeResp(200, body)):
            healthy, detail = check_service("svc", "http://x/health")
        assert healthy is False
        assert detail == "unhealthy"

    def test_non_200_is_http_error(self):
        with patch("urllib.request.urlopen", return_value=_FakeResp(503, b"")):
            healthy, detail = check_service("svc", "http://x/health")
        assert healthy is False
        assert detail == "http_error"

    def test_exception_is_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            healthy, detail = check_service("svc", "http://x/health")
        assert healthy is False
        assert detail == "unreachable"


class TestCheckServices:
    def _isolate(self, tmp_path, consec=None):
        """Patch state files/services to a single always-down test service."""
        consec_file = tmp_path / "alert_consecutive.json"
        consec_file.write_text(json.dumps(consec or {}))
        return patch.multiple(
            "cortex.alert_monitor",
            CONSECUTIVE_FILE=consec_file,
            SILENCE_DIR=tmp_path,
            SERVICES=[("svc", "http://x/health")],
            TIER1_RESTART_CONFIG={"macos": {}, "linux": {}},
        )

    def test_no_alert_below_threshold(self, tmp_path):
        with self._isolate(tmp_path), patch(
            "cortex.alert_monitor.check_service", return_value=(False, "unreachable")
        ):
            alerts = check_services()  # 1st failure, threshold is 2
        assert [a for a in alerts if a["service"] == "svc"] == []

    def test_alert_at_threshold(self, tmp_path):
        with self._isolate(tmp_path, {"svc": 1}), patch(
            "cortex.alert_monitor.check_service", return_value=(False, "unreachable")
        ):
            alerts = check_services()  # 2nd consecutive failure hits threshold
        svc_alerts = [a for a in alerts if a["service"] == "svc"]
        assert len(svc_alerts) == 1
        assert svc_alerts[0]["consecutive_failures"] == 2

    def test_healthy_resets_counter(self, tmp_path):
        consec_file = tmp_path / "alert_consecutive.json"
        with self._isolate(tmp_path, {"svc": 5}) as _, patch(
            "cortex.alert_monitor.check_service", return_value=(True, "healthy")
        ):
            check_services()
            persisted = json.loads((tmp_path / "alert_consecutive.json").read_text())
        assert persisted["svc"] == 0

    def test_degraded_detail_in_message(self, tmp_path):
        with self._isolate(tmp_path, {"svc": 1}), patch(
            "cortex.alert_monitor.check_service", return_value=(False, "degraded")
        ):
            alerts = check_services()
        svc_alerts = [a for a in alerts if a["service"] == "svc"]
        assert len(svc_alerts) == 1
        assert "DEGRADED" in svc_alerts[0]["message"]

    def test_stale_counters_pruned(self, tmp_path):
        # A decommissioned service's counter must not persist forever.
        with self._isolate(tmp_path, {"svc": 0, "vortex-backend": 7}), patch(
            "cortex.alert_monitor.check_service", return_value=(True, "healthy")
        ):
            check_services()
            persisted = json.loads((tmp_path / "alert_consecutive.json").read_text())
        assert "vortex-backend" not in persisted
        assert "svc" in persisted
