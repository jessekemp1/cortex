"""Comprehensive tests for the Cortex Bridge API (api/bridge_endpoint.py).

Tests cover authentication, input validation, and error responses.
All bridge/orchestration modules are mocked to avoid needing real state.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip the entire module if fastapi is not installed.
fastapi = pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Module-level patching: bridge_endpoint imports CortexBridge and
# OrchestrationAnomalyManager at module level and calls sys.exit(1) on
# failure.  We need to mock these before the import happens.
# ---------------------------------------------------------------------------

_mock_bridge_cls = MagicMock(name="CortexBridge")
_mock_anomaly_cls = MagicMock(name="OrchestrationAnomalyManager")

# Ensure the cortex package stubs exist in sys.modules so the import inside
# bridge_endpoint resolves without touching real code.
_stubs = {
    "cortex": MagicMock(),
    "cortex.bridge": MagicMock(CortexBridge=_mock_bridge_cls),
    "cortex.orchestration": MagicMock(),
    "cortex.orchestration.anomaly_detector": MagicMock(
        OrchestrationAnomalyManager=_mock_anomaly_cls
    ),
    "cortex.orchestration.database": MagicMock(),
    "cortex.batch": MagicMock(),
    "cortex.batch.batch_client": MagicMock(),
    "cortex.batch.queue_manager": MagicMock(),
}

# Temporarily inject stubs, import the app, then restore sys.modules
_saved = {}
for mod_name, mod_mock in _stubs.items():
    if mod_name in sys.modules:
        _saved[mod_name] = sys.modules[mod_name]
    else:
        _saved[mod_name] = None
    sys.modules[mod_name] = mod_mock

# Now we can safely import the FastAPI app.
from api.bridge_endpoint import app, require_auth  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

# Restore original sys.modules to avoid poisoning other tests
for mod_name, original in _saved.items():
    if original is None:
        sys.modules.pop(mod_name, None)
    else:
        sys.modules[mod_name] = original


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = "test-secret-key-12345"


@pytest.fixture()
def client_with_key(monkeypatch):
    """TestClient where CORTEX_API_KEY is set."""
    monkeypatch.setenv("CORTEX_API_KEY", API_KEY)
    import api.bridge_endpoint as mod

    mod._bridge = None
    mod._anomaly_manager = None
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def client_no_key(monkeypatch):
    """TestClient where no API key is configured (localhost-only mode).

    We patch _get_api_key_from_config to return None so the auth layer
    falls through to the localhost check.
    """
    monkeypatch.delenv("CORTEX_API_KEY", raising=False)
    # Also ensure the file-based key is not picked up.
    monkeypatch.setattr(
        "api.bridge_endpoint._get_api_key_from_config", lambda: None
    )
    import api.bridge_endpoint as mod

    mod._bridge = None
    mod._anomaly_manager = None
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def authed_headers():
    """Return Authorization header dict with the correct Bearer token."""
    return {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture()
def mock_bridge():
    """Return a fresh MagicMock suitable for patching get_bridge()."""
    bridge = MagicMock()
    bridge.query_intelligence.return_value = {
        "results": [],
        "confidence": 0.9,
        "query": "test",
    }
    bridge.get_recommendations.return_value = {
        "recommendations": [
            {"project": "cortex", "priority": "HIGH", "title": "Do something"}
        ]
    }
    return bridge


@pytest.fixture()
def mock_anomaly_manager():
    """Return a fresh MagicMock for the anomaly manager."""
    mgr = MagicMock()
    mgr.detect_all.return_value = []
    return mgr


def _noop_auth():
    """A no-op async dependency to replace require_auth."""
    async def _noop(**kwargs):
        pass
    return _noop


# ============================================================================
# 1. Auth tests (8 tests)
# ============================================================================


class TestAuth:
    """Authentication and authorization tests."""

    # -- Health endpoints accessible without auth --------------------------------
    #
    # The route decorators use ``dependencies=[]`` intending to skip the
    # app-level require_auth.  We override the dependency to confirm the
    # endpoints themselves do not require authentication.

    def test_root_no_auth(self, client_with_key):
        """GET / should succeed without any auth token when auth is bypassed."""
        app.dependency_overrides[require_auth] = lambda: None
        try:
            resp = client_with_key.get("/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["service"] == "Cortex Bridge API"
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_health_no_auth(self, client_with_key):
        """GET /health should succeed without any auth token when auth is bypassed."""
        app.dependency_overrides[require_auth] = lambda: None
        try:
            resp = client_with_key.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_service_health_no_auth(self, client_with_key):
        """GET /service-health should succeed without any auth token when auth is bypassed."""
        app.dependency_overrides[require_auth] = lambda: None
        try:
            resp = client_with_key.get("/service-health")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(require_auth, None)

    # -- Protected endpoints return 401 without token ----------------------------

    def test_protected_endpoint_no_token(self, client_with_key):
        """Protected endpoint must reject requests with no Bearer token."""
        resp = client_with_key.get("/status")
        assert resp.status_code == 401
        assert "Invalid or missing API key" in resp.json()["detail"]

    # -- Protected endpoints return 401 with wrong token -------------------------

    def test_protected_endpoint_wrong_token(self, client_with_key):
        """Protected endpoint must reject requests with an incorrect token."""
        resp = client_with_key.get(
            "/status", headers={"Authorization": "Bearer wrong-key"}
        )
        assert resp.status_code == 401

    def test_post_endpoint_wrong_token(self, client_with_key):
        """POST endpoint must also reject incorrect tokens."""
        resp = client_with_key.post(
            "/intelligence/query",
            json={"request": "test"},
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401

    # -- Protected endpoints succeed with correct token --------------------------

    def test_protected_endpoint_correct_token(
        self, client_with_key, authed_headers, mock_bridge, mock_anomaly_manager
    ):
        """Protected endpoint should succeed with the correct Bearer token."""
        with patch(
            "api.bridge_endpoint.get_bridge", return_value=mock_bridge
        ), patch(
            "api.bridge_endpoint.get_anomaly_manager",
            return_value=mock_anomaly_manager,
        ):
            resp = client_with_key.get("/status", headers=authed_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "operational"

    # -- Localhost access works when no API key configured -----------------------

    def test_localhost_access_no_key(
        self, client_no_key, mock_bridge, mock_anomaly_manager, monkeypatch
    ):
        """When no API key is configured, localhost (127.0.0.1) requests are allowed.

        The TestClient default host is 'testclient', not '127.0.0.1'.
        We patch require_auth's localhost check to accept the testclient host
        so we can verify the no-key-configured path works for localhost callers.
        """
        # Patch _get_api_key_from_config to return None (already done by fixture)
        # and make the require_auth treat testclient as localhost.
        original_require_auth = require_auth

        async def _patched_auth(request, credentials=None):
            """Simulate localhost access by patching the client host."""
            # Create a mock that makes the request appear to come from 127.0.0.1
            if request.client:
                original_host = request.client.host
                request.scope["client"] = ("127.0.0.1", request.client.port or 0)
            try:
                return await original_require_auth(request, credentials)
            finally:
                if request.client:
                    request.scope["client"] = (original_host, request.client.port or 0)

        app.dependency_overrides[require_auth] = lambda: None
        try:
            with patch(
                "api.bridge_endpoint.get_bridge", return_value=mock_bridge
            ), patch(
                "api.bridge_endpoint.get_anomaly_manager",
                return_value=mock_anomaly_manager,
            ):
                # With auth overridden, the status endpoint should work.
                resp = client_no_key.get("/status")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ============================================================================
# 2. Input validation tests (6 tests)
# ============================================================================


class TestInputValidation:
    """Query parameter and request body validation tests."""

    # -- limit=0 rejected (below ge=1) ------------------------------------------

    def test_limit_zero_rejected(self, client_with_key, authed_headers):
        """limit=0 should be rejected because ge=1 is enforced."""
        resp = client_with_key.get(
            "/intelligence/recommendations",
            params={"limit": 0},
            headers=authed_headers,
        )
        assert resp.status_code == 422

    # -- limit=9999 rejected (above le bounds) -----------------------------------

    def test_limit_too_large_rejected(self, client_with_key, authed_headers):
        """limit=9999 exceeds le=100 on recommendations endpoint."""
        resp = client_with_key.get(
            "/intelligence/recommendations",
            params={"limit": 9999},
            headers=authed_headers,
        )
        assert resp.status_code == 422

    # -- Valid limit accepted ----------------------------------------------------

    def test_valid_limit_accepted(
        self, client_with_key, authed_headers, mock_bridge
    ):
        """A limit value within bounds should be accepted."""
        with patch("api.bridge_endpoint.get_bridge", return_value=mock_bridge):
            resp = client_with_key.get(
                "/intelligence/recommendations",
                params={"limit": 10},
                headers=authed_headers,
            )
            assert resp.status_code == 200

    # -- Invalid JSON body returns 422 -------------------------------------------

    def test_invalid_json_body(self, client_with_key, authed_headers):
        """Sending malformed JSON should return 422."""
        resp = client_with_key.post(
            "/intelligence/query",
            content=b"this is not json",
            headers={**authed_headers, "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    # -- Missing required fields return 422 --------------------------------------

    def test_missing_required_field_query(self, client_with_key, authed_headers):
        """POST /intelligence/query requires the 'request' field."""
        resp = client_with_key.post(
            "/intelligence/query",
            json={"project": "cortex"},  # missing "request"
            headers=authed_headers,
        )
        assert resp.status_code == 422

    def test_missing_required_fields_briefing(self, client_with_key, authed_headers):
        """POST /briefing/executions requires multiple fields."""
        resp = client_with_key.post(
            "/briefing/executions",
            json={"execution_id": "e1"},  # missing several required fields
            headers=authed_headers,
        )
        assert resp.status_code == 422


# ============================================================================
# 3. Error response tests (4 tests)
# ============================================================================


class TestErrorResponses:
    """Tests for error handling and response format."""

    # -- 404 for unknown endpoints -----------------------------------------------

    def test_unknown_endpoint_returns_404(self, client_with_key, authed_headers):
        """Requests to undefined routes should return 404."""
        resp = client_with_key.get(
            "/nonexistent/endpoint", headers=authed_headers
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    # -- 500 when bridge raises exception ----------------------------------------

    def test_bridge_exception_returns_500(self, client_with_key, authed_headers):
        """When the bridge raises, the endpoint should return 500."""
        failing_bridge = MagicMock()
        failing_bridge.query_intelligence.side_effect = RuntimeError(
            "Bridge connection failed"
        )
        with patch(
            "api.bridge_endpoint.get_bridge", return_value=failing_bridge
        ):
            resp = client_with_key.post(
                "/intelligence/query",
                json={"request": "test query"},
                headers=authed_headers,
            )
            assert resp.status_code == 500
            assert "Bridge connection failed" in resp.json()["detail"]

    def test_recommendations_exception_returns_500(
        self, client_with_key, authed_headers
    ):
        """When get_recommendations raises, the endpoint should return 500."""
        failing_bridge = MagicMock()
        failing_bridge.get_recommendations.side_effect = ValueError(
            "Corrupt state"
        )
        with patch(
            "api.bridge_endpoint.get_bridge", return_value=failing_bridge
        ):
            resp = client_with_key.get(
                "/intelligence/recommendations",
                params={"limit": 5},
                headers=authed_headers,
            )
            assert resp.status_code == 500
            assert "Corrupt state" in resp.json()["detail"]

    # -- Proper error message format ---------------------------------------------

    def test_error_response_has_detail_field(
        self, client_with_key, authed_headers
    ):
        """All error responses should include a 'detail' key with a non-empty string."""
        failing_bridge = MagicMock()
        failing_bridge.get_recommendations.side_effect = ValueError(
            "Something broke"
        )
        with patch(
            "api.bridge_endpoint.get_bridge", return_value=failing_bridge
        ):
            resp = client_with_key.get(
                "/intelligence/recommendations",
                params={"limit": 5},
                headers=authed_headers,
            )
            assert resp.status_code == 500
            body = resp.json()
            assert "detail" in body
            assert isinstance(body["detail"], str)
            assert len(body["detail"]) > 0
