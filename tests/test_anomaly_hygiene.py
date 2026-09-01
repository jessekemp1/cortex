"""cortex_anomalies hides test/activation fixtures by default.

Two of five anomalies served here were an `activation_test` learning insight and
a "Test V2 Prime Integration" record from a January activation run. Permanent
fixtures on a live surface make it read as stale noise every time it is opened.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import mcp_server

_FIXTURE_PLUS_REAL = {
    "count": 4,
    "anomalies": [
        {"type": "context_switching_risk", "severity": "CRITICAL", "title": "11 active projects"},
        {"type": "learning_insight", "severity": "info", "title": "Learning insight: activation_test"},
        {"type": "recommendation_available", "severity": "medium", "title": "Recommendation: Test V2 Prime Integration"},
        {"type": "batch_inefficiency", "severity": "WARNING", "title": "Batch queue at 0%"},
    ],
}


def _call(**kwargs):
    with patch.object(mcp_server, "_bridge_get", return_value=dict(_FIXTURE_PLUS_REAL)):
        return json.loads(mcp_server.cortex_anomalies(**kwargs))


def test_fixtures_filtered_by_default():
    out = _call()
    titles = [a["title"] for a in out["anomalies"]]
    assert not any("activation_test" in t or "Test V2 Prime" in t for t in titles)
    # The two real anomalies survive.
    assert any("11 active projects" in t for t in titles)
    assert any("Batch queue" in t for t in titles)


def test_count_reflects_filtered_set():
    out = _call()
    assert out["count"] == 2
    assert out["fixtures_filtered"] == 2


def test_include_fixtures_returns_everything():
    out = _call(include_fixtures=True)
    assert out["count"] == 4
    assert "fixtures_filtered" not in out


def test_real_critical_anomaly_is_never_dropped():
    out = _call()
    assert any(a["severity"] == "CRITICAL" for a in out["anomalies"])


def test_fixture_matcher_is_case_insensitive():
    assert mcp_server._is_fixture_anomaly({"type": "X", "title": "ACTIVATION_TEST run"})
    assert mcp_server._is_fixture_anomaly({"type": "learning_insight", "title": "activation_test"})
    assert not mcp_server._is_fixture_anomaly({"type": "batch", "title": "Batch queue at 0%"})
