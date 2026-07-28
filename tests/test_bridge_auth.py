"""Tests for global Bridge API authentication middleware."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.bridge_endpoint import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_endpoints_skip_auth(client, monkeypatch):
    monkeypatch.setenv("CORTEX_API_KEY", "secret-key")
    for path in ("/", "/health", "/service-health"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_mutating_route_requires_bearer_when_key_configured(client, monkeypatch):
    monkeypatch.setenv("CORTEX_API_KEY", "secret-key")
    resp = client.post("/decisions/learning", json={"decision": "test"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing Bearer token"

    resp = client.post(
        "/decisions/learning",
        json={"decision": "test"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


def test_mutating_route_allows_localhost_without_key(client, monkeypatch, tmp_path):
    monkeypatch.delenv("CORTEX_API_KEY", raising=False)
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    resp = client.post("/decisions/learning", json={"decision": "local ok"})
    assert resp.status_code == 200, resp.text


def test_sensitive_get_requires_bearer_when_key_configured(client, monkeypatch):
    monkeypatch.setenv("CORTEX_API_KEY", "secret-key")
    resp = client.get("/signal/bus-stats")
    assert resp.status_code == 401

    resp = client.get("/signal/bus-stats", headers={"Authorization": "Bearer secret-key"})
    assert resp.status_code == 200


def test_verify_bridge_auth_rejects_remote_without_key(monkeypatch):
    from api.auth import verify_bridge_auth
    from fastapi import HTTPException, Request

    monkeypatch.delenv("CORTEX_API_KEY", raising=False)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/queue",
        "headers": [],
        "client": ("203.0.113.1", 12345),
        "server": ("127.0.0.1", 8765),
    }
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        verify_bridge_auth(request)
    assert exc.value.status_code == 401
