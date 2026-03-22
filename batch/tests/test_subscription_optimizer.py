#!/usr/bin/env python3
"""Tests for SubscriptionOptimizer."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from batch.subscription_optimizer import (
    CapacityFillSuggestion,
    SubscriptionOptimizer,
    SubscriptionTier,
    TokenWasteReport,
    UtilizationStatus,
    check_utilization,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_utilization.db"


@pytest.fixture
def optimizer(tmp_db):
    """Create an optimizer with temp database."""
    return SubscriptionOptimizer(db_path=tmp_db)


@pytest.fixture
def configured_optimizer(optimizer):
    """Create an optimizer with a subscription already configured."""
    optimizer.configure_subscription(
        provider="anthropic",
        tier="pro",
        monthly_token_allowance=5_000_000,
        monthly_cost_usd=20.0,
        billing_reset_day=1,
    )
    return optimizer


class TestSubscriptionConfiguration:
    def test_configure_subscription(self, optimizer):
        sub = optimizer.configure_subscription(
            provider="anthropic",
            tier="pro",
            monthly_token_allowance=5_000_000,
            monthly_cost_usd=20.0,
            billing_reset_day=1,
        )
        assert sub.provider == "anthropic"
        assert sub.tier == "pro"
        assert sub.monthly_token_allowance == 5_000_000
        assert sub.monthly_cost_usd == 20.0

    def test_update_subscription(self, optimizer):
        optimizer.configure_subscription(
            provider="anthropic",
            tier="pro",
            monthly_token_allowance=5_000_000,
            monthly_cost_usd=20.0,
            billing_reset_day=1,
        )
        # Update the same subscription
        sub = optimizer.configure_subscription(
            provider="anthropic",
            tier="pro",
            monthly_token_allowance=10_000_000,
            monthly_cost_usd=40.0,
            billing_reset_day=15,
        )
        assert sub.monthly_token_allowance == 10_000_000
        assert sub.monthly_cost_usd == 40.0

    def test_multiple_providers(self, optimizer):
        optimizer.configure_subscription(
            provider="anthropic", tier="pro",
            monthly_token_allowance=5_000_000, monthly_cost_usd=20.0,
            billing_reset_day=1,
        )
        optimizer.configure_subscription(
            provider="openai", tier="plus",
            monthly_token_allowance=3_000_000, monthly_cost_usd=20.0,
            billing_reset_day=15,
        )
        subs = optimizer.get_all_subscriptions()
        assert len(subs) == 2
        providers = {s.provider for s in subs}
        assert providers == {"anthropic", "openai"}

    def test_optional_fields(self, optimizer):
        sub = optimizer.configure_subscription(
            provider="anthropic",
            tier="team",
            monthly_token_allowance=20_000_000,
            monthly_cost_usd=100.0,
            billing_reset_day=1,
            rate_limit_rpm=60,
            rate_limit_tpm=100_000,
            batch_discount_pct=50.0,
        )
        assert sub.rate_limit_rpm == 60
        assert sub.rate_limit_tpm == 100_000
        assert sub.batch_discount_pct == 50.0


class TestUsageRecording:
    def test_record_usage(self, configured_optimizer):
        configured_optimizer.record_usage(
            provider="anthropic",
            tokens_input=1000,
            tokens_output=500,
            model_tier="sonnet",
        )
        # Should not raise and data should be recorded
        status = configured_optimizer.get_utilization_status("anthropic")
        assert status is not None
        assert status.tokens_used >= 1500

    def test_record_batch_usage(self, configured_optimizer):
        configured_optimizer.record_usage(
            provider="anthropic",
            tokens_input=5000,
            tokens_output=2000,
            is_batch=True,
            model_tier="haiku",
        )
        status = configured_optimizer.get_utilization_status("anthropic")
        assert status.tokens_used >= 7000

    def test_record_failed_request_creates_waste(self, configured_optimizer):
        configured_optimizer.record_usage(
            provider="anthropic",
            tokens_input=1000,
            tokens_output=0,
            failed=True,
        )
        report = configured_optimizer.get_waste_report("anthropic", days=1)
        assert report.failed_request_tokens >= 1000

    def test_multiple_recordings_accumulate(self, configured_optimizer):
        for _ in range(5):
            configured_optimizer.record_usage(
                provider="anthropic",
                tokens_input=1000,
                tokens_output=500,
            )
        status = configured_optimizer.get_utilization_status("anthropic")
        assert status.tokens_used >= 7500


class TestUtilizationStatus:
    def test_no_subscription_returns_none(self, optimizer):
        status = optimizer.get_utilization_status("nonexistent")
        assert status is None

    def test_zero_usage_is_underutilized(self, configured_optimizer):
        status = configured_optimizer.get_utilization_status("anthropic")
        assert status is not None
        assert status.utilization_pct == 0.0
        assert status.status_level == "underutilized"
        assert status.tokens_at_risk > 0

    def test_utilization_fields(self, configured_optimizer):
        configured_optimizer.record_usage(
            provider="anthropic", tokens_input=100_000, tokens_output=50_000
        )
        status = configured_optimizer.get_utilization_status("anthropic")

        assert status.provider == "anthropic"
        assert status.tier == "pro"
        assert status.tokens_used >= 150_000
        assert status.tokens_allowance == 5_000_000
        assert status.tokens_remaining <= 5_000_000
        assert status.days_remaining >= 0
        assert status.days_elapsed >= 1
        assert status.avg_daily_tokens > 0
        assert status.cost_per_1k_tokens_nominal > 0

    def test_billing_period_calculation(self, configured_optimizer):
        status = configured_optimizer.get_utilization_status("anthropic")
        assert status.billing_period_start is not None
        assert status.billing_period_end is not None
        assert status.days_elapsed + status.days_remaining > 0


class TestWasteReport:
    def test_empty_waste_report(self, configured_optimizer):
        report = configured_optimizer.get_waste_report("anthropic", days=7)
        assert isinstance(report, TokenWasteReport)
        assert report.period_days == 7
        assert len(report.suggestions) > 0  # Should always have at least one suggestion

    def test_waste_categories(self, configured_optimizer):
        configured_optimizer.record_waste(
            provider="anthropic",
            waste_type="redundant_context",
            tokens_wasted=5000,
            description="Repeated system prompt",
        )
        configured_optimizer.record_waste(
            provider="anthropic",
            waste_type="model_mismatch",
            tokens_wasted=3000,
            description="Used Opus for simple task",
        )
        report = configured_optimizer.get_waste_report("anthropic", days=1)
        assert report.redundant_context_tokens >= 5000
        assert report.model_mismatch_tokens >= 3000

    def test_idle_capacity_detection(self, configured_optimizer):
        # With 5M monthly allowance and no usage, there should be significant idle capacity
        report = configured_optimizer.get_waste_report("anthropic", days=30)
        assert report.idle_capacity_tokens > 0


class TestCapacityFillSuggestions:
    def test_no_suggestions_when_fully_utilized(self, optimizer):
        # No subscription = no suggestions
        suggestions = optimizer.suggest_capacity_fill("nonexistent")
        assert suggestions == []

    def test_suggestions_when_underutilized(self, configured_optimizer):
        # With 5M allowance and no usage, should get suggestions
        suggestions = configured_optimizer.suggest_capacity_fill("anthropic")
        assert len(suggestions) > 0
        assert all(isinstance(s, CapacityFillSuggestion) for s in suggestions)

    def test_suggestion_fields(self, configured_optimizer):
        suggestions = configured_optimizer.suggest_capacity_fill("anthropic", max_suggestions=1)
        if suggestions:
            sug = suggestions[0]
            assert sug.task_type
            assert sug.description
            assert sug.estimated_tokens > 0
            assert sug.priority in ("high", "medium", "low")
            assert sug.batch_eligible is True

    def test_max_suggestions_limit(self, configured_optimizer):
        suggestions = configured_optimizer.suggest_capacity_fill("anthropic", max_suggestions=2)
        assert len(suggestions) <= 2


class TestDashboards:
    def test_utilization_dashboard(self, configured_optimizer):
        dashboard = configured_optimizer.format_utilization_dashboard("anthropic")
        assert "ANTHROPIC" in dashboard
        assert "Subscription Utilization" in dashboard
        assert "Token Usage" in dashboard
        assert "Billing Period" in dashboard

    def test_utilization_dashboard_no_subscription(self, optimizer):
        dashboard = optimizer.format_utilization_dashboard("unknown")
        assert "No subscription configured" in dashboard

    def test_waste_dashboard(self, configured_optimizer):
        dashboard = configured_optimizer.format_waste_dashboard("anthropic", days=7)
        assert "Token Waste Analysis" in dashboard
        assert "Recommendations" in dashboard

    def test_underutilized_dashboard_shows_suggestions(self, configured_optimizer):
        dashboard = configured_optimizer.format_utilization_dashboard("anthropic")
        assert "UNDERUTILIZED" in dashboard
        assert "Suggested work" in dashboard


class TestConvenienceFunction:
    def test_check_utilization_no_subscription(self, tmp_db):
        optimizer = SubscriptionOptimizer(db_path=tmp_db)
        result = optimizer.get_utilization_status("anthropic")
        assert result is None
