#!/usr/bin/env python3
"""Tests for the Synthetic Data Engine API endpoints."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi.testclient import TestClient
from synthetic.api import app


@pytest.fixture
def client():
    return TestClient(app)


class TestGenerate:
    """Test POST /api/v1/synthetic/generate."""

    def test_generate_profiles(self, client):
        resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 20,
                "skip_heavy_layers": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["flywheel_id"].startswith("FW-")
        assert data["count"] == 20
        assert data["flywheel_score"] is not None
        assert data["flywheel_score"] > 0

    def test_generate_transactions(self, client):
        resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "transactions",
                "count": 30,
                "include_risk_flags": True,
                "risk_profile": "high",
                "skip_heavy_layers": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    def test_generate_with_filters(self, client):
        resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 15,
                "segment": "mass_affluent",
                "province": "ON",
                "skip_heavy_layers": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    def test_generate_default_params(self, client):
        resp = client.post("/api/v1/synthetic/generate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_type"] == "profiles"
        assert data["count"] == 100


class TestStatus:
    """Test GET /api/v1/synthetic/status/{flywheel_id}."""

    def test_get_status_after_generate(self, client):
        # First generate
        gen_resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 10,
                "skip_heavy_layers": True,
            },
        )
        fw_id = gen_resp.json()["flywheel_id"]

        # Then check status
        status_resp = client.get(f"/api/v1/synthetic/status/{fw_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["flywheel_id"] == fw_id
        assert data["status"] == "completed"

    def test_status_not_found(self, client):
        resp = client.get("/api/v1/synthetic/status/NONEXISTENT-ID")
        assert resp.status_code == 404


class TestDownload:
    """Test GET /api/v1/synthetic/download/{flywheel_id}."""

    def test_download_completed(self, client):
        gen_resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 10,
                "skip_heavy_layers": True,
            },
        )
        fw_id = gen_resp.json()["flywheel_id"]

        dl_resp = client.get(f"/api/v1/synthetic/download/{fw_id}")
        assert dl_resp.status_code == 200
        data = dl_resp.json()
        assert "flywheel_id" in data
        assert "records" in data
        assert "flywheel_report" in data

    def test_download_not_found(self, client):
        resp = client.get("/api/v1/synthetic/download/NONEXISTENT-ID")
        assert resp.status_code == 404


class TestFeedback:
    """Test POST /api/v1/synthetic/feedback/{flywheel_id}."""

    def test_submit_feedback(self, client):
        gen_resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 10,
                "skip_heavy_layers": True,
            },
        )
        fw_id = gen_resp.json()["flywheel_id"]

        fb_resp = client.post(
            f"/api/v1/synthetic/feedback/{fw_id}",
            json={
                "outcome": "positive",
                "detail": "Data quality was excellent for our use case",
            },
        )
        assert fb_resp.status_code == 200
        data = fb_resp.json()
        assert data["status"] == "accepted"
        assert data["feedback_count"] == 1

    def test_submit_multiple_feedback(self, client):
        gen_resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 10,
                "skip_heavy_layers": True,
            },
        )
        fw_id = gen_resp.json()["flywheel_id"]

        for outcome in ["positive", "negative", "neutral"]:
            client.post(
                f"/api/v1/synthetic/feedback/{fw_id}",
                json={
                    "outcome": outcome,
                },
            )

        # Check count
        fb_resp = client.post(
            f"/api/v1/synthetic/feedback/{fw_id}",
            json={
                "outcome": "positive",
            },
        )
        assert fb_resp.json()["feedback_count"] == 4

    def test_feedback_not_found(self, client):
        resp = client.post(
            "/api/v1/synthetic/feedback/NONEXISTENT-ID",  # pragma: allowlist secret
            json={
                "outcome": "positive",
            },
        )
        assert resp.status_code == 404

    def test_feedback_with_metrics(self, client):
        gen_resp = client.post(
            "/api/v1/synthetic/generate",
            json={
                "data_type": "profiles",
                "count": 10,
                "skip_heavy_layers": True,
            },
        )
        fw_id = gen_resp.json()["flywheel_id"]

        fb_resp = client.post(
            f"/api/v1/synthetic/feedback/{fw_id}",
            json={
                "outcome": "positive",
                "detail": "Used for credit model training",
                "metrics": {"model_accuracy": 0.87, "false_positive_rate": 0.03},
            },
        )
        assert fb_resp.status_code == 200


class TestQualityReport:
    """Test GET /api/v1/synthetic/quality/report."""

    def test_quality_report_empty(self, client):
        # Note: may not be empty if other tests ran first in same process
        resp = client.get("/api/v1/synthetic/quality/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "generations" in data
        assert "trend" in data

    def test_quality_report_after_generations(self, client):
        # Generate a few runs
        for _ in range(3):
            client.post(
                "/api/v1/synthetic/generate",
                json={
                    "data_type": "profiles",
                    "count": 10,
                    "skip_heavy_layers": True,
                },
            )

        resp = client.get("/api/v1/synthetic/quality/report")
        data = resp.json()
        assert data["generations"] >= 3
        assert data["avg_score"] > 0
        assert "history" in data
        assert "feedback_summary" in data


class TestHealth:
    """Test GET /api/v1/synthetic/health."""

    def test_health_check(self, client):
        resp = client.get("/api/v1/synthetic/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.4.0"
        assert data["layers"] == 7
