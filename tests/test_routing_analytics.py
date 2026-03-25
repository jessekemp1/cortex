"""Tests for routing analytics (Phase 2).

Tests:
  - Cost report generation from fixture data
  - Quality report with trends
  - Routing accuracy metrics
  - Empty/missing data handling
  - Savings calculation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cortex.supervisor.routing_analytics import RoutingAnalytics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_outcomes(tmp_path: Path, records: list[dict]) -> Path:
    outcomes_file = tmp_path / "model_outcomes.jsonl"
    lines = [json.dumps(r) for r in records]
    outcomes_file.write_text("\n".join(lines) + "\n")
    return outcomes_file


@pytest.fixture
def sample_outcomes(tmp_path: Path) -> Path:
    now = datetime.now(tz=timezone.utc).isoformat()
    records = [
        {
            "timestamp": now,
            "work_item_id": f"w{i}",
            "model_tier": "sonnet",
            "model_id": "deepseek/deepseek-chat",
            "task_type": "research",
            "success": True,
            "quality_score": 0.7,
            "tokens_used": 5000,
            "duration_seconds": 2.0,
            "provider": "deepseek",
            "cost_usd": 0.003,
        }
        for i in range(10)
    ] + [
        {
            "timestamp": now,
            "work_item_id": f"opus-{i}",
            "model_tier": "opus",
            "model_id": "claude-opus-4-6",
            "task_type": "architecture",
            "success": True,
            "quality_score": 0.9,
            "tokens_used": 8000,
            "duration_seconds": 5.0,
            "provider": "anthropic",
            "cost_usd": 0.48,
        }
        for i in range(5)
    ]
    return _make_outcomes(tmp_path, records)


@pytest.fixture
def analytics(sample_outcomes: Path) -> RoutingAnalytics:
    return RoutingAnalytics(outcomes_path=sample_outcomes)


# ---------------------------------------------------------------------------
# Tests: Cost report
# ---------------------------------------------------------------------------


class TestCostReport:
    def test_total_cost(self, analytics: RoutingAnalytics) -> None:
        report = analytics.cost_report(days=7)
        assert report["total_dispatches"] == 15
        assert report["total_cost_usd"] > 0

    def test_by_provider(self, analytics: RoutingAnalytics) -> None:
        report = analytics.cost_report(days=7)
        assert "deepseek" in report["by_provider"]
        assert "anthropic" in report["by_provider"]
        assert report["by_provider"]["deepseek"]["count"] == 10
        assert report["by_provider"]["anthropic"]["count"] == 5

    def test_savings_calculated(self, analytics: RoutingAnalytics) -> None:
        """Savings and baseline should be calculated."""
        report = analytics.cost_report(days=7)
        assert "savings_usd" in report
        assert "anthropic_only_baseline_usd" in report
        assert "savings_pct" in report
        assert isinstance(report["savings_usd"], float)

    def test_empty_data(self, tmp_path: Path) -> None:
        analytics = RoutingAnalytics(outcomes_path=tmp_path / "nonexistent.jsonl")
        report = analytics.cost_report(days=7)
        assert report["total_dispatches"] == 0
        assert report["total_cost_usd"] == 0


# ---------------------------------------------------------------------------
# Tests: Quality report
# ---------------------------------------------------------------------------


class TestQualityReport:
    def test_by_model(self, analytics: RoutingAnalytics) -> None:
        report = analytics.quality_report(days=7)
        assert "deepseek/deepseek-chat" in report["by_model"]
        assert "claude-opus-4-6" in report["by_model"]

    def test_avg_quality(self, analytics: RoutingAnalytics) -> None:
        report = analytics.quality_report(days=7)
        deepseek = report["by_model"]["deepseek/deepseek-chat"]
        assert deepseek["avg_quality"] == 0.7
        assert deepseek["count"] == 10

    def test_empty_data(self, tmp_path: Path) -> None:
        analytics = RoutingAnalytics(outcomes_path=tmp_path / "nonexistent.jsonl")
        report = analytics.quality_report(days=7)
        assert report["by_model"] == {}


# ---------------------------------------------------------------------------
# Tests: Routing accuracy
# ---------------------------------------------------------------------------


class TestRoutingAccuracy:
    def test_adequate_pct(self, analytics: RoutingAnalytics) -> None:
        report = analytics.routing_accuracy(days=7)
        # All sonnet dispatches have quality 0.7 >= 0.6, so should be 100%
        assert report["cheaper_model_adequate_pct"] == 100.0

    def test_total_dispatches(self, analytics: RoutingAnalytics) -> None:
        report = analytics.routing_accuracy(days=7)
        assert report["total_dispatches"] == 15

    def test_avg_by_tier(self, analytics: RoutingAnalytics) -> None:
        report = analytics.routing_accuracy(days=7)
        assert "sonnet" in report["avg_quality_by_tier"]
        assert "opus" in report["avg_quality_by_tier"]
        assert report["avg_quality_by_tier"]["opus"] == 0.9


# ---------------------------------------------------------------------------
# Tests: A/B Baseline comparison
# ---------------------------------------------------------------------------


class TestBaselineComparison:
    def test_insufficient_data(self, tmp_path: Path) -> None:
        analytics = RoutingAnalytics(outcomes_path=tmp_path / "nonexistent.jsonl")
        report = analytics.baseline_comparison(days=7)
        assert report["verdict"] == "insufficient_data"

    def test_too_few_baseline_records(self, tmp_path: Path) -> None:
        """Need at least 3 baseline + 3 optimized records."""
        now = datetime.now(tz=timezone.utc).isoformat()
        records = [
            {
                "timestamp": now,
                "work_item_id": "w0",
                "quality_score": 0.8,
                "success": True,
                "is_baseline": True,
            },
            {
                "timestamp": now,
                "work_item_id": "w1",
                "quality_score": 0.7,
                "success": True,
                "is_baseline": False,
            },
        ]
        path = _make_outcomes(tmp_path, records)
        analytics = RoutingAnalytics(outcomes_path=path)
        report = analytics.baseline_comparison(days=7)
        assert report["verdict"] == "insufficient_data"

    def test_acceptable_quality(self, tmp_path: Path) -> None:
        """Optimized quality within 10% of baseline → acceptable."""
        now = datetime.now(tz=timezone.utc).isoformat()
        records = [
            {
                "timestamp": now,
                "work_item_id": f"bl-{i}",
                "quality_score": 0.80,
                "success": True,
                "is_baseline": True,
            }
            for i in range(5)
        ] + [
            {
                "timestamp": now,
                "work_item_id": f"opt-{i}",
                "quality_score": 0.75,
                "success": True,
                "is_baseline": False,
            }
            for i in range(20)
        ]
        path = _make_outcomes(tmp_path, records)
        analytics = RoutingAnalytics(outcomes_path=path)
        report = analytics.baseline_comparison(days=7)
        assert report["verdict"] == "acceptable"
        assert report["quality_delta"] == -0.05  # -5% is within tolerance
        assert report["baseline"]["count"] == 5
        assert report["optimized"]["count"] == 20

    def test_degraded_quality(self, tmp_path: Path) -> None:
        """Optimized quality >10% worse than baseline → degraded."""
        now = datetime.now(tz=timezone.utc).isoformat()
        records = [
            {
                "timestamp": now,
                "work_item_id": f"bl-{i}",
                "quality_score": 0.90,
                "success": True,
                "is_baseline": True,
            }
            for i in range(5)
        ] + [
            {
                "timestamp": now,
                "work_item_id": f"opt-{i}",
                "quality_score": 0.60,
                "success": True,
                "is_baseline": False,
            }
            for i in range(20)
        ]
        path = _make_outcomes(tmp_path, records)
        analytics = RoutingAnalytics(outcomes_path=path)
        report = analytics.baseline_comparison(days=7)
        assert report["verdict"] == "degraded"
        assert report["quality_delta"] == -0.3  # 30% worse

    def test_success_rate_tracked(self, tmp_path: Path) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        records = (
            [
                {
                    "timestamp": now,
                    "work_item_id": f"bl-{i}",
                    "quality_score": 0.8,
                    "success": True,
                    "is_baseline": True,
                }
                for i in range(4)
            ]
            + [
                {
                    "timestamp": now,
                    "work_item_id": "bl-fail",
                    "quality_score": 0.3,
                    "success": False,
                    "is_baseline": True,
                },
            ]
            + [
                {
                    "timestamp": now,
                    "work_item_id": f"opt-{i}",
                    "quality_score": 0.75,
                    "success": True,
                    "is_baseline": False,
                }
                for i in range(5)
            ]
        )
        path = _make_outcomes(tmp_path, records)
        analytics = RoutingAnalytics(outcomes_path=path)
        report = analytics.baseline_comparison(days=7)
        assert report["baseline"]["success_rate"] == 0.8  # 4/5
        assert report["optimized"]["success_rate"] == 1.0  # 5/5
