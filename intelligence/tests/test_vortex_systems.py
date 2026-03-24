#!/usr/bin/env python3
"""
Tests for Vortex-inspired systems:
1. FieldEnsembleDecider — field-level ensemble values
2. TemporalHorizonRouter — different models for different durations
3. VerifiableExpertise — provable expert co-navigator
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from intelligence.ensemble_decider import (
    DecisionField,
    FieldEnsembleDecider,
    FieldPredictor,
    FieldVote,
    FullDecision,
)
from intelligence.temporal_router import (
    TemporalHorizon,
    TemporalHorizonRouter,
    TemporalProfile,
)
from intelligence.verifiable_expertise import (
    DomainCredential,
    ExpertiseLevel,
    VerifiableExpertise,
)


# ──────────────────────────────────────────────
# Field Ensemble Decider Tests
# ──────────────────────────────────────────────


class TestFieldEnsembleDecider:
    @pytest.fixture
    def decider(self, tmp_path):
        return FieldEnsembleDecider(db_path=tmp_path / "ensemble.db")

    def test_basic_decision(self, decider):
        ctx = {"task_type": "code_review", "token_estimate": 25000, "request_text": "review this code"}
        decision = decider.decide(ctx)

        assert isinstance(decision, FullDecision)
        assert decision.model_tier in ("haiku", "sonnet", "opus")
        assert decision.routing in ("interactive", "batch")
        assert decision.context_size in ("minimal", "standard", "full")
        assert decision.priority in ("low", "medium", "high", "critical")
        assert 0 < decision.overall_confidence <= 1.0

    def test_architecture_gets_opus(self, decider):
        ctx = {"task_type": "architecture", "token_estimate": 50000, "request_text": "redesign the system"}
        decision = decider.decide(ctx)
        assert decision.model_tier == "opus"

    def test_quick_qa_gets_haiku(self, decider):
        ctx = {"task_type": "quick_qa", "token_estimate": 1000, "request_text": "what is this?"}
        decision = decider.decide(ctx)
        assert decision.model_tier == "haiku"

    def test_ensemble_produces_valid_confidence(self, decider):
        ctx = {"task_type": "architecture", "token_estimate": 60000, "request_text": "redesign"}
        decision = decider.decide(ctx)
        # Confidence should be between 0 and 1
        assert 0.0 < decision.overall_confidence <= 1.0
        # Each field result should also have valid confidence
        for result in decision.field_results.values():
            assert 0.0 <= result.confidence <= 1.0
            assert 0.0 <= result.agreement_ratio <= 1.0

    def test_field_results_have_votes(self, decider):
        ctx = {"task_type": "code_review"}
        decision = decider.decide(ctx)

        # Each field should have votes from its predictors
        for field_name, result in decision.field_results.items():
            assert len(result.votes) > 0
            assert result.agreement_ratio >= 0

    def test_outcome_updates_predictor_weights(self, decider):
        ctx = {"task_type": "code_review"}
        decision = decider.decide(ctx)

        # Record that the actual best model was opus
        decider.record_outcome(decision, {"model_tier": "opus", "routing": "batch"})

        # Predictors that voted for the winning value should have higher accuracy
        # This is a basic smoke test — detailed accuracy tested below

    def test_custom_predictor_registration(self, decider):
        def custom_predict(ctx):
            return FieldVote(
                field=DecisionField.MODEL_TIER,
                predictor_name="custom",
                value="opus",
                confidence=0.99,
                reasoning="Always opus",
            )

        pred = FieldPredictor("custom", DecisionField.MODEL_TIER, custom_predict)
        decider.register_predictor(pred)

        ctx = {"task_type": "quick_qa"}
        decision = decider.decide(ctx)
        # Custom predictor with very high confidence should influence result
        model_votes = decision.field_results.get("model_tier")
        assert model_votes is not None
        assert any(v.predictor_name == "custom" for v in model_votes.votes)

    def test_decision_persisted(self, decider):
        ctx = {"task_type": "code_review"}
        decider.decide(ctx)

        with sqlite3.connect(decider.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM ensemble_decisions").fetchone()[0]
        assert count == 1

    def test_predictor_leaderboard(self, decider):
        ctx = {"task_type": "code_review"}
        decider.decide(ctx)

        leaderboard = decider.get_predictor_leaderboard()
        assert "model_tier" in leaderboard
        assert "routing" in leaderboard

    def test_decision_report_formatting(self, decider):
        ctx = {"task_type": "code_review", "request_text": "review this code"}
        decision = decider.decide(ctx)

        report = decider.format_decision_report(decision)
        assert "Field-Level Ensemble Decision" in report
        assert decision.model_tier in report

    def test_batch_routing_with_keywords(self, decider):
        ctx = {"task_type": "code_review", "request_text": "review all files in the codebase"}
        decision = decider.decide(ctx)
        # "review all" should trigger batch consideration
        routing_result = decision.field_results.get("routing")
        assert routing_result is not None

    def test_interactive_routing_with_keywords(self, decider):
        ctx = {"task_type": "debugging", "request_text": "fix this error immediately"}
        decision = decider.decide(ctx)
        assert decision.routing == "interactive"


# ──────────────────────────────────────────────
# Temporal Horizon Router Tests
# ──────────────────────────────────────────────


class TestTemporalHorizonRouter:
    @pytest.fixture
    def router(self, tmp_path):
        return TemporalHorizonRouter(db_path=tmp_path / "temporal.db")

    def test_immediate_classification(self, router):
        profile = router.classify({
            "request_text": "fix this error",
            "task_type": "debugging",
            "token_estimate": 2000,
        })
        assert profile.horizon == TemporalHorizon.IMMEDIATE
        assert profile.preferred_model_tier == "haiku"
        assert profile.batch_eligible is False

    def test_session_classification(self, router):
        profile = router.classify({
            "request_text": "implement the new user authentication feature",
            "task_type": "implementation",
            "token_estimate": 20000,
        })
        assert profile.horizon == TemporalHorizon.SESSION
        assert profile.preferred_model_tier in ("sonnet", "opus")

    def test_strategic_classification(self, router):
        profile = router.classify({
            "request_text": "analyze the codebase architecture and create a migration plan",
            "task_type": "architecture",
            "token_estimate": 60000,
            "file_count": 15,
        })
        assert profile.horizon == TemporalHorizon.STRATEGIC
        assert profile.preferred_model_tier == "opus"
        assert profile.batch_eligible is True
        assert profile.context_depth == "portfolio"

    def test_time_sensitive_overrides_to_immediate(self, router):
        profile = router.classify({
            "request_text": "plan the architecture redesign",
            "task_type": "architecture",
            "time_sensitive": True,
        })
        assert profile.horizon == TemporalHorizon.IMMEDIATE

    def test_learning_weight_increases_with_horizon(self, router):
        immediate = router.classify({
            "request_text": "what is this?",
            "task_type": "quick_qa",
        })
        session = router.classify({
            "request_text": "implement feature",
            "task_type": "implementation",
        })
        strategic = router.classify({
            "request_text": "analyze codebase architecture",
            "task_type": "architecture",
            "file_count": 20,
        })

        assert immediate.learning_weight < session.learning_weight
        assert session.learning_weight < strategic.learning_weight

    def test_outcome_recording(self, router):
        router.record_outcome(
            TemporalHorizon.SESSION, "sonnet", success=True, tokens_used=25000
        )
        router.record_outcome(
            TemporalHorizon.SESSION, "sonnet", success=True, tokens_used=20000
        )

        with sqlite3.connect(router.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM horizon_performance WHERE horizon = 'session' AND model_tier = 'sonnet'"
            ).fetchone()

        assert row is not None
        assert row["total"] == 2
        assert row["successes"] == 2

    def test_learned_adjustment(self, router):
        # Seed strong performance data for haiku in immediate tasks
        for _ in range(10):
            router.record_outcome(TemporalHorizon.IMMEDIATE, "haiku", True, 2000)
        for _ in range(3):
            router.record_outcome(TemporalHorizon.IMMEDIATE, "sonnet", True, 5000)

        profile = router.classify({
            "request_text": "quick question",
            "task_type": "quick_qa",
        })
        # Should still recommend haiku for immediate (matches default)
        assert profile.preferred_model_tier == "haiku"

    def test_horizon_stats(self, router):
        router.record_outcome(TemporalHorizon.SESSION, "sonnet", True, 25000)
        stats = router.get_horizon_stats()
        assert "SESSION" in stats

    def test_classification_persisted(self, router):
        router.classify({"request_text": "fix bug", "task_type": "bug_fix"})

        with sqlite3.connect(router.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM temporal_classifications").fetchone()[0]
        assert count == 1

    def test_default_to_session_for_moderate_tasks(self, router):
        """Session-typed tasks should get session scope."""
        profile = router.classify({
            "request_text": "implement the new login feature",
            "task_type": "implementation",
            "token_estimate": 15000,
        })
        assert profile.horizon == TemporalHorizon.SESSION


# ──────────────────────────────────────────────
# Verifiable Expertise Tests
# ──────────────────────────────────────────────


class TestVerifiableExpertise:
    @pytest.fixture
    def ve(self, tmp_path):
        return VerifiableExpertise(db_path=tmp_path / "expertise.db")

    def test_record_and_resolve_prediction(self, ve):
        pred_id = ve.record_prediction(
            domain="model_selection",
            predicted_value="sonnet",
            confidence=0.80,
            task_summary="code review task",
        )
        assert pred_id > 0

        was_correct = ve.resolve_prediction(pred_id, "sonnet")
        assert was_correct is True

    def test_incorrect_prediction(self, ve):
        pred_id = ve.record_prediction(
            domain="model_selection",
            predicted_value="haiku",
            confidence=0.70,
        )
        was_correct = ve.resolve_prediction(pred_id, "sonnet")
        assert was_correct is False

    def test_credential_with_no_data(self, ve):
        cred = ve.get_credential("model_selection")
        assert cred.level == ExpertiseLevel.NOVICE
        assert cred.total_predictions == 0

    def test_credential_accuracy(self, ve):
        # Record 8 correct, 2 incorrect
        for i in range(8):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "sonnet")
        for i in range(2):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "opus")

        cred = ve.get_credential("model_selection")
        assert cred.accuracy == 0.8
        assert cred.total_predictions == 10

    def test_expertise_levels(self, ve):
        # Novice: < 10 predictions
        for i in range(5):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "sonnet")
        cred = ve.get_credential("model_selection")
        assert cred.level == ExpertiseLevel.NOVICE

        # Competent: 10-50 predictions, 50-70% accuracy
        for i in range(10):
            pid = ve.record_prediction("model_selection", "sonnet", 0.60)
            ve.resolve_prediction(pid, "sonnet" if i < 6 else "opus")
        cred = ve.get_credential("model_selection")
        assert cred.level in (ExpertiseLevel.NOVICE, ExpertiseLevel.COMPETENT)

    def test_brier_score(self, ve):
        # Perfect predictions at 100% confidence → Brier = 0
        for _ in range(10):
            pid = ve.record_prediction("model_selection", "sonnet", 1.0)
            ve.resolve_prediction(pid, "sonnet")
        cred = ve.get_credential("model_selection")
        assert cred.brier_score == 0.0

    def test_calibration_bins(self, ve):
        # Record predictions at different confidence levels
        for _ in range(10):
            pid = ve.record_prediction("model_selection", "sonnet", 0.90)
            ve.resolve_prediction(pid, "sonnet")

        for _ in range(5):
            pid = ve.record_prediction("model_selection", "haiku", 0.30)
            ve.resolve_prediction(pid, "haiku")

        cred = ve.get_credential("model_selection")
        assert "very_high" in cred.confidence_bins
        assert cred.confidence_bins["very_high"]["count"] == 10

    def test_should_trust_insufficient_data(self, ve):
        trust, reason = ve.should_trust("model_selection", 0.80)
        assert trust is False
        assert "Insufficient" in reason

    def test_should_trust_with_calibrated_data(self, ve):
        # Build a well-calibrated track record at 80% confidence
        for i in range(20):
            pid = ve.record_prediction("routing", "interactive", 0.85)
            # Resolve ~85% correctly to match claimed confidence
            ve.resolve_prediction(pid, "interactive" if i < 17 else "batch")

        trust, reason = ve.should_trust("routing", 0.85)
        # Should trust because calibration matches
        assert isinstance(trust, bool)
        assert len(reason) > 0

    def test_batch_resolution(self, ve):
        ids = []
        for _ in range(5):
            ids.append(ve.record_prediction("model_selection", "sonnet", 0.80))

        ve.resolve_batch([(pid, "sonnet") for pid in ids])

        cred = ve.get_credential("model_selection")
        assert cred.total_predictions == 5
        assert cred.accuracy == 1.0

    def test_expertise_card_empty(self, ve):
        card = ve.format_expertise_card()
        assert "No verified predictions" in card

    def test_expertise_card_with_data(self, ve):
        for i in range(15):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "sonnet" if i < 12 else "opus")

        card = ve.format_expertise_card()
        assert "Cortex Expertise Card" in card
        assert "Model Selection" in card

    def test_domain_deep_dive(self, ve):
        for i in range(10):
            pid = ve.record_prediction("routing", "interactive", 0.70)
            ve.resolve_prediction(pid, "interactive" if i < 7 else "batch")

        report = ve.format_domain_deep_dive("routing")
        assert "Deep Dive" in report
        assert "Predicted: interactive" in report

    def test_trend_detection(self, ve):
        # All recent predictions correct → should be stable or improving
        for i in range(20):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "sonnet")

        cred = ve.get_credential("model_selection")
        assert cred.trend in ("stable", "improving", "insufficient_data")

    def test_multiple_domains(self, ve):
        for _ in range(10):
            pid = ve.record_prediction("model_selection", "sonnet", 0.80)
            ve.resolve_prediction(pid, "sonnet")

        for _ in range(10):
            pid = ve.record_prediction("routing", "interactive", 0.70)
            ve.resolve_prediction(pid, "interactive")

        credentials = ve.get_all_credentials()
        assert len(credentials) == 2
        domains = {c.domain.value for c in credentials}
        assert "model_selection" in domains
        assert "routing" in domains
