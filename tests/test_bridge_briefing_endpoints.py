"""Tests for the 3 new briefing endpoints added to bridge_endpoint.py."""

from unittest.mock import patch
from fastapi.testclient import TestClient

from api.bridge_endpoint import app

client = TestClient(app)


def test_resume_context_endpoint_returns_json():
    """GET /session/resume-context returns a JSON object with a 'resume' key."""
    fake_ctx = {
        "directory": "/Users/jesse.kemp/Dev",
        "files": [{"path": "cortex/api/bridge_endpoint.py", "insertions": 30, "deletions": 2}],
        "summary": "Uncommitted changes in cortex/api",
    }
    with patch("briefing.detect_resume_context", return_value=fake_ctx):
        resp = client.get("/session/resume-context")
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert data["resume"]["directory"] == "/Users/jesse.kemp/Dev"


def test_stale_items_endpoint_returns_json():
    """GET /goals/stale-items returns a JSON object with 'stale_items' and 'threshold_days'."""
    fake_items = [
        {"text": "Wire RTOFS into brief", "age_days": 12},
        {"text": "Register Météo-France key", "age_days": 8},
    ]
    with patch("briefing.detect_stale_items", return_value=fake_items):
        resp = client.get("/goals/stale-items")
    assert resp.status_code == 200
    data = resp.json()
    assert "stale_items" in data
    assert "threshold_days" in data
    assert data["threshold_days"] == 7
    assert len(data["stale_items"]) == 2


def test_session_delta_endpoint_returns_json():
    """GET /session/delta returns a JSON object with a 'report' key."""
    fake_report = "Delta: +3 outcomes, -1 batch failures since last session."
    with patch("session_delta.get_session_delta_report", return_value=fake_report):
        resp = client.get("/session/delta")
    assert resp.status_code == 200
    data = resp.json()
    assert "report" in data
    assert data["report"] == fake_report


def test_resume_context_when_clean():
    """When detect_resume_context returns None, resume key is None (clean workspace)."""
    with patch("briefing.detect_resume_context", return_value=None):
        resp = client.get("/session/resume-context")
    assert resp.status_code == 200
    data = resp.json()
    assert "resume" in data
    assert data["resume"] is None


def test_stale_items_empty():
    """When detect_stale_items returns [], stale_items list is empty."""
    with patch("briefing.detect_stale_items", return_value=[]):
        resp = client.get("/goals/stale-items")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale_items"] == []
    assert data["threshold_days"] == 7
