#!/usr/bin/env python3
"""Tests for the CostTracker module.

Covers: recording, daily spend aggregation, budget enforcement,
monthly summaries, and savings calculations vs Anthropic baseline.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cortex.conductor.cost_tracker import (
    DEFAULT_BASELINE,
    CostTracker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> CostTracker:
    """Create a CostTracker backed by a temp directory."""
    return CostTracker(state_dir=tmp_path, daily_budget=20.0)


@pytest.fixture
def populated_tracker(tracker: CostTracker) -> CostTracker:
    """Tracker pre-loaded with a handful of representative entries."""
    tracker.record(
        provider="groq",
        model="llama-3.1-8b-instant",
        input_tokens=500,
        output_tokens=100,
        cost_usd=0.000033,
        use_case="classification",
        latency_ms=45.2,
    )
    tracker.record(
        provider="xai",
        model="grok-3-fast",
        input_tokens=2000,
        output_tokens=500,
        cost_usd=0.000650,
        use_case="research",
        latency_ms=320.5,
    )
    tracker.record(
        provider="groq",
        model="llama-3.1-8b-instant",
        input_tokens=300,
        output_tokens=50,
        cost_usd=0.000019,
        use_case="quick_qa",
        latency_ms=30.1,
    )
    tracker.record(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        input_tokens=1000,
        output_tokens=800,
        cost_usd=0.015000,
        use_case="architecture",
        latency_ms=2500.0,
    )
    return tracker


# ---------------------------------------------------------------------------
# record() tests
# ---------------------------------------------------------------------------


class TestRecord:
    """Tests for CostTracker.record()."""

    def test_record_creates_file(self, tracker: CostTracker) -> None:
        """record() should create the costs JSONL file on first call."""
        assert not tracker.costs_file.exists()

        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.00001,
        )

        assert tracker.costs_file.exists()

    def test_record_appends_valid_jsonl(self, tracker: CostTracker) -> None:
        """Each record() call should append exactly one JSON line."""
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.00001,
            use_case="classification",
            latency_ms=42.0,
        )
        tracker.record(
            provider="xai",
            model="grok-3-fast",
            input_tokens=200,
            output_tokens=100,
            cost_usd=0.00009,
            use_case="research",
            latency_ms=150.0,
        )

        lines = tracker.costs_file.read_text().strip().split("\n")
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["provider"] == "groq"
        assert entry1["model"] == "llama-3.1-8b-instant"
        assert entry1["input_tokens"] == 100
        assert entry1["output_tokens"] == 50
        assert entry1["cost_usd"] == 0.00001
        assert entry1["use_case"] == "classification"
        assert entry1["latency_ms"] == 42.0
        assert "timestamp" in entry1

        entry2 = json.loads(lines[1])
        assert entry2["provider"] == "xai"

    def test_record_returns_entry(self, tracker: CostTracker) -> None:
        """record() should return the entry dict for confirmation."""
        result = tracker.record(
            provider="groq",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            use_case="test",
            latency_ms=10.0,
        )

        assert result["provider"] == "groq"
        assert result["model"] == "test-model"
        assert result["cost_usd"] == 0.001
        assert "timestamp" in result

    def test_record_timestamp_is_utc_iso(self, tracker: CostTracker) -> None:
        """Timestamps should be UTC ISO 8601 format ending with Z."""
        entry = tracker.record(
            provider="groq",
            model="m",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
        )

        ts = entry["timestamp"]
        assert ts.endswith("Z")
        # Should be parseable
        parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        assert parsed is not None

    def test_record_defaults_use_case_and_latency(self, tracker: CostTracker) -> None:
        """use_case and latency_ms should default to empty/zero."""
        entry = tracker.record(
            provider="groq",
            model="m",
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
        )

        assert entry["use_case"] == ""
        assert entry["latency_ms"] == 0.0


# ---------------------------------------------------------------------------
# get_daily_spend() tests
# ---------------------------------------------------------------------------


class TestGetDailySpend:
    """Tests for CostTracker.get_daily_spend()."""

    def test_empty_file_returns_zero_total(self, tracker: CostTracker) -> None:
        """No cost file should return just {"total": 0.0}."""
        spend = tracker.get_daily_spend()
        assert spend["total"] == 0.0

    def test_sums_by_provider(self, populated_tracker: CostTracker) -> None:
        """Spend should be summed per provider with a correct total."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        spend = populated_tracker.get_daily_spend(date=today)

        # groq: 0.000033 + 0.000019 = 0.000052
        assert abs(spend["groq"] - 0.000052) < 1e-9
        # xai: 0.000650
        assert abs(spend["xai"] - 0.000650) < 1e-9
        # anthropic: 0.015000
        assert abs(spend["anthropic"] - 0.015000) < 1e-9
        # total: 0.015702
        assert abs(spend["total"] - 0.015702) < 1e-9

    def test_filters_by_date(self, tracker: CostTracker) -> None:
        """Only entries matching the requested date should be summed."""
        # Write entries with explicit timestamps for two different days
        entry_today = {
            "timestamp": "2026-02-17T10:00:00Z",
            "provider": "groq",
            "model": "m",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 1.00,
            "use_case": "",
            "latency_ms": 0.0,
        }
        entry_yesterday = {
            "timestamp": "2026-02-16T10:00:00Z",
            "provider": "xai",
            "model": "m",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 2.00,
            "use_case": "",
            "latency_ms": 0.0,
        }

        with open(tracker.costs_file, "w") as f:
            f.write(json.dumps(entry_today) + "\n")
            f.write(json.dumps(entry_yesterday) + "\n")

        spend_17 = tracker.get_daily_spend(date="2026-02-17")
        assert spend_17["total"] == 1.00
        assert spend_17.get("groq", 0) == 1.00
        assert "xai" not in spend_17

        spend_16 = tracker.get_daily_spend(date="2026-02-16")
        assert spend_16["total"] == 2.00
        assert spend_16.get("xai", 0) == 2.00


# ---------------------------------------------------------------------------
# get_budget_remaining() tests
# ---------------------------------------------------------------------------


class TestGetBudgetRemaining:
    """Tests for CostTracker.get_budget_remaining()."""

    def test_full_budget_when_no_spend(self, tracker: CostTracker) -> None:
        """No spend should yield the full daily budget."""
        assert tracker.get_budget_remaining() == 20.0

    def test_budget_decreases_with_spend(self, populated_tracker: CostTracker) -> None:
        """Budget remaining should be daily_budget - today's total spend."""
        remaining = populated_tracker.get_budget_remaining()
        expected = 20.0 - 0.015702
        assert abs(remaining - expected) < 1e-5

    def test_budget_floor_at_zero(self, tracker: CostTracker) -> None:
        """Budget remaining should never go negative."""
        tracker.record(
            provider="anthropic",
            model="opus",
            input_tokens=1_000_000,
            output_tokens=500_000,
            cost_usd=25.00,
        )

        assert tracker.get_budget_remaining() == 0.0


# ---------------------------------------------------------------------------
# check_budget() tests
# ---------------------------------------------------------------------------


class TestCheckBudget:
    """Tests for CostTracker.check_budget()."""

    def test_check_budget_allows_within_limit(self, tracker: CostTracker) -> None:
        """A call that fits within budget should return True."""
        assert tracker.check_budget(estimated_cost=5.0) is True

    def test_check_budget_rejects_over_limit(self, tracker: CostTracker) -> None:
        """A call that exceeds remaining budget should return False."""
        assert tracker.check_budget(estimated_cost=25.0) is False

    def test_check_budget_exact_match(self, tracker: CostTracker) -> None:
        """An estimated cost exactly equal to remaining should return True."""
        assert tracker.check_budget(estimated_cost=20.0) is True

    def test_check_budget_after_spend(self, tracker: CostTracker) -> None:
        """Budget check should account for prior spend today."""
        tracker.record(
            provider="groq",
            model="m",
            input_tokens=1,
            output_tokens=1,
            cost_usd=18.0,
        )

        assert tracker.check_budget(estimated_cost=1.0) is True
        assert tracker.check_budget(estimated_cost=3.0) is False


# ---------------------------------------------------------------------------
# get_savings_report() tests
# ---------------------------------------------------------------------------


class TestGetSavingsReport:
    """Tests for CostTracker.get_savings_report()."""

    def test_empty_report(self, tracker: CostTracker) -> None:
        """No entries should produce zeroed savings report."""
        report = tracker.get_savings_report()

        assert report["actual_spend"] == 0.0
        assert report["anthropic_equivalent"] == 0.0
        assert report["savings_usd"] == 0.0
        assert report["savings_pct"] == 0.0
        assert report["total_calls"] == 0

    def test_savings_vs_anthropic(self, tracker: CostTracker) -> None:
        """Routing classification to Groq should show savings vs Haiku."""
        # Record a classification call on Groq
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=10_000,
            output_tokens=500,
            cost_usd=0.00054,  # Groq pricing
            use_case="classification",
        )

        report = tracker.get_savings_report()

        # Anthropic equivalent: haiku ($1/$5 per MTok)
        # = (10000 * 1.0 + 500 * 5.0) / 1_000_000
        # = (10000 + 2500) / 1_000_000
        # = 0.0125
        expected_anthro = (10_000 * 1.0 + 500 * 5.0) / 1_000_000
        assert abs(report["anthropic_equivalent"] - expected_anthro) < 1e-9
        assert abs(report["actual_spend"] - 0.00054) < 1e-9
        assert report["savings_usd"] > 0
        assert report["savings_pct"] > 0
        assert report["total_calls"] == 1

    def test_savings_by_use_case_breakdown(self, populated_tracker: CostTracker) -> None:
        """Each use case should appear in the by_use_case breakdown."""
        report = populated_tracker.get_savings_report()

        assert "classification" in report["by_use_case"]
        assert "research" in report["by_use_case"]
        assert "quick_qa" in report["by_use_case"]
        assert "architecture" in report["by_use_case"]

        # Each entry should have actual, anthropic_equivalent, calls, savings
        cls_stats = report["by_use_case"]["classification"]
        assert cls_stats["calls"] == 1
        assert "actual" in cls_stats
        assert "anthropic_equivalent" in cls_stats
        assert "savings_usd" in cls_stats
        assert "savings_pct" in cls_stats

    def test_savings_uses_correct_baseline_per_use_case(self, tracker: CostTracker) -> None:
        """security_audit should use opus pricing, quick_qa should use haiku."""
        tracker.record(
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=1_000,
            output_tokens=1_000,
            cost_usd=0.00042,
            use_case="security_audit",
        )
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=1_000,
            output_tokens=1_000,
            cost_usd=0.00013,
            use_case="quick_qa",
        )

        report = tracker.get_savings_report()

        # security_audit baseline = opus ($15/$75)
        sec_anthro = (1_000 * 15.0 + 1_000 * 75.0) / 1_000_000  # = 0.09
        assert (
            abs(report["by_use_case"]["security_audit"]["anthropic_equivalent"] - sec_anthro) < 1e-9
        )

        # quick_qa baseline = haiku ($1/$5)
        qa_anthro = (1_000 * 1.0 + 1_000 * 5.0) / 1_000_000  # = 0.006
        assert abs(report["by_use_case"]["quick_qa"]["anthropic_equivalent"] - qa_anthro) < 1e-9

    def test_unknown_use_case_uses_sonnet_baseline(self, tracker: CostTracker) -> None:
        """Unknown/untagged use cases should fall back to sonnet pricing."""
        tracker.record(
            provider="groq",
            model="llama-3.1-8b-instant",
            input_tokens=1_000,
            output_tokens=1_000,
            cost_usd=0.00013,
            use_case="some_future_use_case",
        )

        report = tracker.get_savings_report()
        uc = report["by_use_case"]["some_future_use_case"]

        # Default baseline = sonnet ($3/$15)
        expected = (1_000 * DEFAULT_BASELINE[0] + 1_000 * DEFAULT_BASELINE[1]) / 1_000_000
        assert abs(uc["anthropic_equivalent"] - expected) < 1e-9


# ---------------------------------------------------------------------------
# get_monthly_summary() tests
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    """Tests for CostTracker.get_monthly_summary()."""

    def test_empty_summary(self, tracker: CostTracker) -> None:
        """No entries should produce an empty but structured summary."""
        summary = tracker.get_monthly_summary()

        assert summary["total_calls"] == 0
        assert summary["total_spend"] == 0.0
        assert summary["by_provider"] == {}
        assert summary["by_use_case"] == {}
        assert summary["by_day"] == {}
        assert "current_month" in summary

    def test_monthly_aggregation(self, populated_tracker: CostTracker) -> None:
        """Summary should aggregate by provider, use_case, and day."""
        summary = populated_tracker.get_monthly_summary()

        assert summary["total_calls"] == 4
        assert summary["total_spend"] > 0

        # Should have all 3 providers
        assert "groq" in summary["by_provider"]
        assert "xai" in summary["by_provider"]
        assert "anthropic" in summary["by_provider"]

        # Should have all use cases
        assert "classification" in summary["by_use_case"]
        assert "research" in summary["by_use_case"]
        assert "quick_qa" in summary["by_use_case"]
        assert "architecture" in summary["by_use_case"]

        # Should have at least one day
        assert len(summary["by_day"]) >= 1

    def test_monthly_filters_to_current_month(self, tracker: CostTracker) -> None:
        """Only entries from the current month should be included."""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")

        # One entry this month
        this_month_entry = {
            "timestamp": f"{current_month}-15T10:00:00Z",
            "provider": "groq",
            "model": "m",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 1.00,
            "use_case": "test",
            "latency_ms": 0.0,
        }
        # One entry from a different month
        other_month_entry = {
            "timestamp": "2025-01-15T10:00:00Z",
            "provider": "xai",
            "model": "m",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 2.00,
            "use_case": "test",
            "latency_ms": 0.0,
        }

        with open(tracker.costs_file, "w") as f:
            f.write(json.dumps(this_month_entry) + "\n")
            f.write(json.dumps(other_month_entry) + "\n")

        summary = tracker.get_monthly_summary()

        assert summary["total_calls"] == 1
        assert summary["total_spend"] == 1.00
        assert "groq" in summary["by_provider"]
        assert "xai" not in summary["by_provider"]


# ---------------------------------------------------------------------------
# Edge cases & resilience
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and error resilience tests."""

    def test_corrupted_jsonl_line_is_skipped(self, tracker: CostTracker) -> None:
        """Malformed JSON lines should be silently skipped."""
        with open(tracker.costs_file, "w") as f:
            f.write('{"provider":"groq","cost_usd":1.0,"timestamp":"2026-02-17T10:00:00Z"}\n')
            f.write("NOT VALID JSON\n")
            f.write('{"provider":"xai","cost_usd":2.0,"timestamp":"2026-02-17T10:00:00Z"}\n')

        spend = tracker.get_daily_spend(date="2026-02-17")
        assert spend["total"] == 3.0

    def test_state_dir_is_created(self, tmp_path: Path) -> None:
        """CostTracker should create its state directory if it doesn't exist."""
        nested = tmp_path / "deep" / "nested" / "dir"
        tracker = CostTracker(state_dir=nested)
        assert nested.exists()
        assert tracker.state_dir == nested

    def test_custom_daily_budget(self, tmp_path: Path) -> None:
        """Custom daily budget should be respected."""
        tracker = CostTracker(state_dir=tmp_path, daily_budget=5.0)
        assert tracker.get_budget_remaining() == 5.0
        assert tracker.check_budget(4.99) is True
        assert tracker.check_budget(5.01) is False

    def test_zero_cost_entries(self, tracker: CostTracker) -> None:
        """Zero-cost entries should be recorded and counted."""
        tracker.record(
            provider="groq",
            model="m",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            use_case="test",
        )

        spend = tracker.get_daily_spend()
        assert spend["total"] == 0.0

        report = tracker.get_savings_report()
        assert report["total_calls"] == 1

    def test_multiple_records_same_provider(self, tracker: CostTracker) -> None:
        """Multiple entries for the same provider should be summed."""
        for _ in range(5):
            tracker.record(
                provider="groq",
                model="m",
                input_tokens=100,
                output_tokens=50,
                cost_usd=1.0,
            )

        spend = tracker.get_daily_spend()
        assert spend["groq"] == 5.0
        assert spend["total"] == 5.0
