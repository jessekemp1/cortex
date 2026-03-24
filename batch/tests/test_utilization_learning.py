#!/usr/bin/env python3
"""Tests for UtilizationLearningEngine — the closed-loop learning system."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from batch.utilization_learning import (
    LearnedPolicy,
    PacingPolicy,
    UtilizationLearningEngine,
)


@pytest.fixture
def engine(tmp_path):
    """Create a learning engine with temp database."""
    return UtilizationLearningEngine(db_path=tmp_path / "test_learning.db")


class TestObservations:
    """OBSERVE phase: recording decisions and outcomes."""

    def test_observe_routing_decision(self, engine):
        engine.observe_routing_decision(
            request_type="code_review",
            route_chosen="batch",
            tokens_estimated=25000,
            utilization_pct=45.0,
            route_accepted=True,
        )
        # Should not raise; data persisted in SQLite
        with sqlite3.connect(engine.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM routing_observations").fetchone()[0]
        assert count == 1

    def test_observe_suggestion_outcome(self, engine):
        engine.observe_suggestion_outcome(
            task_type="security_audit",
            accepted=True,
            tokens_estimated=30000,
            utilization_pct=40.0,
            days_remaining=10,
        )
        with sqlite3.connect(engine.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM suggestion_observations").fetchone()[0]
        assert count == 1

    def test_observe_daily_pacing(self, engine):
        engine.observe_daily_pacing(
            target_tokens=150000,
            actual_tokens=130000,
            utilization_start=50.0,
            utilization_end=55.0,
            batch_tokens=30000,
            interactive_tokens=100000,
        )
        with sqlite3.connect(engine.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM daily_pacing").fetchone()[0]
        assert count == 1

    def test_multiple_observations_accumulate(self, engine):
        for i in range(10):
            engine.observe_routing_decision(
                request_type="code_review",
                route_chosen="batch",
                tokens_estimated=25000,
                utilization_pct=45.0 + i,
                route_accepted=(i % 3 != 0),  # 70% acceptance
            )
        with sqlite3.connect(engine.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM routing_observations").fetchone()[0]
        assert count == 10


class TestLearning:
    """LEARN phase: analyzing patterns and generating policies."""

    def _seed_routing_data(self, engine, request_type, route, accepted_count, rejected_count):
        """Helper to seed routing observations."""
        for _ in range(accepted_count):
            engine.observe_routing_decision(
                request_type=request_type,
                route_chosen=route,
                tokens_estimated=25000,
                utilization_pct=50.0,
                route_accepted=True,
                outcome="success",
            )
        for _ in range(rejected_count):
            engine.observe_routing_decision(
                request_type=request_type,
                route_chosen=route,
                tokens_estimated=25000,
                utilization_pct=50.0,
                route_accepted=False,
                outcome="success",
            )

    def test_learn_batch_preference(self, engine):
        """When user consistently accepts batch, learn to suggest it."""
        self._seed_routing_data(engine, "code_review", "batch", accepted_count=8, rejected_count=2)
        policies = engine.learn()

        routing_policies = [p for p in policies if p.policy_type == "routing"]
        assert len(routing_policies) > 0

        batch_pref = [p for p in routing_policies if "prefer_batch" in p.key]
        assert len(batch_pref) == 1
        assert batch_pref[0].value["route"] == "suggest_batch"
        assert batch_pref[0].confidence > 0.6

    def test_learn_interactive_preference(self, engine):
        """When user consistently rejects batch, learn to keep interactive."""
        self._seed_routing_data(engine, "debugging", "batch", accepted_count=1, rejected_count=7)
        policies = engine.learn()

        interactive_pref = [p for p in policies if "prefer_interactive" in p.key]
        assert len(interactive_pref) == 1
        assert interactive_pref[0].value["route"] == "interactive"

    def test_learn_suggestion_acceptance(self, engine):
        """Learn which suggestion types users accept most."""
        for _ in range(8):
            engine.observe_suggestion_outcome(
                task_type="security_audit", accepted=True,
                tokens_estimated=30000, utilization_pct=40.0, days_remaining=10,
            )
        for _ in range(3):
            engine.observe_suggestion_outcome(
                task_type="security_audit", accepted=False,
                tokens_estimated=30000, utilization_pct=40.0, days_remaining=10,
            )

        policies = engine.learn()
        suggestion_policies = [p for p in policies if p.policy_type == "suggestion_priority"]
        assert len(suggestion_policies) > 0

        # Security audit acceptance rate should be ~73%
        sec_policy = suggestion_policies[0]
        assert sec_policy.value["accept_rate"] > 0.7

    def test_learn_pacing_strategy(self, engine):
        """Learn daily pacing from historical data."""
        now = datetime.now()
        for days_ago in range(10, 0, -1):
            date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            day_of_week = (now - timedelta(days=days_ago)).weekday()
            is_weekend = day_of_week >= 5
            tokens = 50000 if is_weekend else 150000

            with sqlite3.connect(engine.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO daily_pacing
                    (date, target_tokens, actual_tokens, utilization_at_start,
                     utilization_at_end, batch_tokens, interactive_tokens,
                     suggestions_shown, suggestions_accepted)
                    VALUES (?, 150000, ?, 50.0, 55.0, ?, ?, 3, 1)
                """,
                    (date, tokens, int(tokens * 0.3), int(tokens * 0.7)),
                )
                conn.commit()

        policies = engine.learn()
        pacing = [p for p in policies if p.policy_type == "pacing"]
        assert len(pacing) == 1
        assert pacing[0].value["target_daily_tokens"] > 0
        assert pacing[0].value["weekday_multiplier"] > pacing[0].value["weekend_multiplier"]

    def test_learn_with_insufficient_data(self, engine):
        """With too few observations, no observation-based routing policies generated."""
        engine.observe_routing_decision(
            request_type="code_review",
            route_chosen="batch",
            tokens_estimated=25000,
            utilization_pct=50.0,
        )
        policies = engine.learn()
        # No preference-based routing policies (prefer_batch/prefer_interactive)
        # from just 1 observation — waste-based policies may still appear
        preference_policies = [
            p for p in policies
            if p.policy_type == "routing" and ("prefer_batch" in p.key or "prefer_interactive" in p.key)
        ]
        assert len(preference_policies) == 0

    def test_policies_are_persisted(self, engine):
        """Learned policies survive across engine instances."""
        self._seed_routing_data(engine, "code_review", "batch", accepted_count=8, rejected_count=2)
        engine.learn()

        # Create new engine instance pointing to same DB
        engine2 = UtilizationLearningEngine(db_path=engine.db_path)
        policies = engine2.get_active_policies()
        assert len(policies) > 0


class TestAct:
    """ACT phase: providing policies to decision-makers."""

    def _seed_and_learn(self, engine):
        """Seed data and generate policies."""
        for _ in range(8):
            engine.observe_routing_decision(
                request_type="code_review", route_chosen="batch",
                tokens_estimated=25000, utilization_pct=50.0, route_accepted=True,
            )
        for _ in range(2):
            engine.observe_routing_decision(
                request_type="code_review", route_chosen="batch",
                tokens_estimated=25000, utilization_pct=50.0, route_accepted=False,
            )
        engine.learn()

    def test_get_routing_adjustment(self, engine):
        self._seed_and_learn(engine)
        adj = engine.get_routing_adjustment("code_review")
        assert adj is not None
        assert adj["preferred_route"] == "suggest_batch"
        assert adj["confidence"] > 0.5

    def test_get_routing_adjustment_unknown_type(self, engine):
        self._seed_and_learn(engine)
        adj = engine.get_routing_adjustment("unknown_type")
        # May return None or the batch aggressiveness policy
        # Either is acceptable — no crash
        assert adj is None or isinstance(adj, dict)

    def test_get_suggestion_ranking(self, engine):
        for _ in range(8):
            engine.observe_suggestion_outcome(
                task_type="security_audit", accepted=True,
                tokens_estimated=30000, utilization_pct=40.0, days_remaining=10,
            )
        for _ in range(6):
            engine.observe_suggestion_outcome(
                task_type="documentation", accepted=False,
                tokens_estimated=15000, utilization_pct=40.0, days_remaining=10,
            )
        engine.learn()

        ranking = engine.get_suggestion_ranking(["security_audit", "documentation", "unknown"])
        assert ranking[0][0] == "security_audit"  # Highest acceptance
        assert ranking[0][1] > ranking[1][1]  # Higher score

    def test_get_pacing_target(self, engine):
        now = datetime.now()
        for days_ago in range(7, 0, -1):
            date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            with sqlite3.connect(engine.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO daily_pacing
                    (date, target_tokens, actual_tokens, utilization_at_start,
                     utilization_at_end, batch_tokens, interactive_tokens,
                     suggestions_shown, suggestions_accepted)
                    VALUES (?, 150000, 140000, 50.0, 55.0, 35000, 105000, 3, 1)
                """,
                    (date,),
                )
                conn.commit()

        engine.learn()
        pacing = engine.get_pacing_target()
        assert pacing is not None
        assert isinstance(pacing, PacingPolicy)
        assert pacing.target_daily_tokens > 0
        assert pacing.batch_ratio > 0

    def test_get_active_policies_filters_by_type(self, engine):
        self._seed_and_learn(engine)
        routing = engine.get_active_policies("routing")
        assert all(p.policy_type == "routing" for p in routing)

    def test_get_model_adjustment_simple_task(self, engine):
        """If no waste data, should return None."""
        adj = engine.get_model_adjustment("explore", "simple")
        assert adj is None


class TestPolicyExpiry:
    def test_expired_policies_not_returned(self, engine):
        """Policies past their TTL should not be returned."""
        # Manually insert an expired policy
        expired = datetime.now() - timedelta(days=1)
        with sqlite3.connect(engine.db_path) as conn:
            conn.execute(
                """
                INSERT INTO learned_policies
                (policy_type, key, value, confidence, evidence_count,
                 reasoning, created_at, expires_at)
                VALUES ('routing', 'test_expired', '{}', 0.8, 10,
                        'test', ?, ?)
            """,
                (expired.isoformat(), expired.isoformat()),
            )
            conn.commit()

        policies = engine.get_active_policies()
        assert not any(p.key == "test_expired" for p in policies)


class TestReport:
    def test_empty_report(self, engine):
        report = engine.format_learning_report()
        assert "No learned policies" in report

    def test_report_with_policies(self, engine):
        for _ in range(8):
            engine.observe_routing_decision(
                request_type="code_review", route_chosen="batch",
                tokens_estimated=25000, utilization_pct=50.0, route_accepted=True,
            )
        engine.learn()

        report = engine.format_learning_report()
        assert "Active Policies" in report
        assert "Routing Preferences" in report
        assert "code_review" in report
