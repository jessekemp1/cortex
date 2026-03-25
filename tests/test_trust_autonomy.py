"""Tests for Trust Autonomy Bridge and Session Metrics.

Tests the two novel components from Exponential Collaboration research:
1. TrustAutonomyBridge — trust level evaluation → autonomy policy
2. SessionMetrics — session productivity tracking and trend analysis
"""

import json
import tempfile
from pathlib import Path

import pytest

from engines.workstream_orchestrator import (
    AutonomyPolicy,
    TrustAutonomyBridge,
    TrustLevel,
)
from intelligence.session_metrics import SessionMetrics, SessionRecord, Trend


# ═══════════════════════════════════════════════════════════
# Trust Autonomy Bridge
# ═══════════════════════════════════════════════════════════


class TestTrustLevel:
    """Test trust level evaluation — the core logic."""

    def setup_method(self):
        self.bridge = TrustAutonomyBridge()

    def test_no_outcomes_returns_verify_all(self):
        assert self.bridge.evaluate_level(0, 1.0) == TrustLevel.VERIFY_ALL

    def test_few_outcomes_returns_verify_all(self):
        assert self.bridge.evaluate_level(5, 0.0) == TrustLevel.VERIFY_ALL

    def test_10_outcomes_low_error_returns_spot_check(self):
        assert self.bridge.evaluate_level(10, 0.10) == TrustLevel.SPOT_CHECK

    def test_10_outcomes_high_error_returns_verify_all(self):
        assert self.bridge.evaluate_level(10, 0.20) == TrustLevel.VERIFY_ALL

    def test_25_outcomes_low_error_returns_trust_verify(self):
        assert self.bridge.evaluate_level(25, 0.08) == TrustLevel.TRUST_VERIFY

    def test_50_outcomes_low_error_returns_autonomous(self):
        assert self.bridge.evaluate_level(50, 0.04) == TrustLevel.AUTONOMOUS

    def test_100_outcomes_very_low_error_returns_full_autonomy(self):
        assert self.bridge.evaluate_level(100, 0.02) == TrustLevel.FULL_AUTONOMY

    def test_100_outcomes_moderate_error_caps_at_autonomous(self):
        # 100 outcomes but 4% error — not good enough for full autonomy
        assert self.bridge.evaluate_level(100, 0.04) == TrustLevel.AUTONOMOUS

    def test_highest_qualifying_level_wins(self):
        # 200 outcomes, 1% error — should get FULL_AUTONOMY (highest qualifying)
        assert self.bridge.evaluate_level(200, 0.01) == TrustLevel.FULL_AUTONOMY

    def test_boundary_exact_threshold(self):
        # Exactly at threshold boundary
        assert self.bridge.evaluate_level(10, 0.15) == TrustLevel.SPOT_CHECK
        assert self.bridge.evaluate_level(25, 0.10) == TrustLevel.TRUST_VERIFY
        assert self.bridge.evaluate_level(50, 0.05) == TrustLevel.AUTONOMOUS
        assert self.bridge.evaluate_level(100, 0.03) == TrustLevel.FULL_AUTONOMY


class TestAutonomyPolicy:
    """Test that policies correctly map trust levels to behaviors."""

    def test_verify_all_requires_review(self):
        policy = AutonomyPolicy.for_level(TrustLevel.VERIFY_ALL, 0.5)
        assert policy.review_required is True
        assert policy.max_blast_radius == "file"
        assert "[L0:50%]" == policy.confidence_display

    def test_autonomous_no_review(self):
        policy = AutonomyPolicy.for_level(TrustLevel.AUTONOMOUS, 0.95)
        assert policy.review_required is False
        assert policy.max_blast_radius == "project"
        assert "[L3:95%]" == policy.confidence_display

    def test_full_autonomy_deploy_radius(self):
        policy = AutonomyPolicy.for_level(TrustLevel.FULL_AUTONOMY, 0.98)
        assert policy.review_required is False
        assert policy.max_blast_radius == "deploy"

    def test_all_levels_produce_valid_policies(self):
        for level in TrustLevel:
            policy = AutonomyPolicy.for_level(level, 0.75)
            assert policy.level == level
            assert isinstance(policy.delegation_hint, str)
            assert len(policy.delegation_hint) > 0


class TestTrustAutonomyBridgeIntegration:
    """Test the bridge reads from LearningSystem (or gracefully degrades)."""

    def test_get_autonomy_policy_no_learning_system(self, monkeypatch):
        """Without outcome history, should return VERIFY_ALL."""
        # Patch LearningSystem.get_outcome_patterns to simulate no history
        from unittest.mock import MagicMock

        mock_ls = MagicMock()
        mock_ls.return_value.get_outcome_patterns.return_value = {}
        monkeypatch.setattr(
            "engines.workstream_orchestrator.LearningSystem", mock_ls, raising=False
        )
        # Also patch the cortex.learning import path
        import sys

        mock_module = MagicMock()
        mock_module.LearningSystem = mock_ls
        monkeypatch.setitem(sys.modules, "cortex.learning", mock_module)

        bridge = TrustAutonomyBridge()
        policy = bridge.get_autonomy_policy("nonexistent_domain")
        assert policy.level == TrustLevel.VERIFY_ALL
        assert policy.review_required is True

    def test_get_all_policies_empty(self):
        """With no data, should return empty dict."""
        bridge = TrustAutonomyBridge()
        policies = bridge.get_all_policies()
        assert isinstance(policies, dict)


# ═══════════════════════════════════════════════════════════
# Session Metrics
# ═══════════════════════════════════════════════════════════


class TestSessionMetrics:
    """Test session productivity tracking."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.metrics = SessionMetrics(metrics_file=Path(self.tmp.name))

    def teardown_method(self):
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_basic_session_lifecycle(self):
        sid = self.metrics.session_start("vortex")
        assert sid is not None

        elapsed = self.metrics.mark_first_output()
        assert elapsed is not None
        assert elapsed >= 0

        self.metrics.record_correction()
        self.metrics.record_correction()
        self.metrics.record_context_question()

        record = self.metrics.session_end()
        assert record is not None
        assert record.project == "vortex"
        assert record.corrections == 2
        assert record.context_questions == 1
        assert record.time_to_first_output_minutes is not None

    def test_session_end_without_start_returns_none(self):
        assert self.metrics.session_end() is None

    def test_mark_first_output_only_records_first(self):
        self.metrics.session_start("cortex")
        t1 = self.metrics.mark_first_output()
        t2 = self.metrics.mark_first_output()
        # Second call should return same time (doesn't overwrite)
        assert t1 == t2
        self.metrics.session_end()

    def test_records_persist_to_disk(self):
        self.metrics.session_start("pupil")
        self.metrics.mark_first_output()
        self.metrics.session_end()

        # Read back
        records = self.metrics.load_records()
        assert len(records) == 1
        assert records[0].project == "pupil"

    def test_multiple_sessions_append(self):
        for project in ["vortex", "cortex", "pupil"]:
            self.metrics.session_start(project)
            self.metrics.mark_first_output()
            self.metrics.session_end()

        records = self.metrics.load_records()
        assert len(records) == 3


class TestSessionTrend:
    """Test trend analysis — the actual research measurement."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.metrics = SessionMetrics(metrics_file=Path(self.tmp.name))

    def teardown_method(self):
        Path(self.tmp.name).unlink(missing_ok=True)

    def _write_synthetic_records(self, scores: list):
        """Write synthetic session records with given productivity scores."""
        with open(self.tmp.name, "w") as f:
            for i, score in enumerate(scores):
                record = {
                    "session_id": f"s{i}",
                    "project": "test",
                    "started_at": f"2026-03-{i + 1:02d}T09:00:00",
                    "ended_at": f"2026-03-{i + 1:02d}T10:00:00",
                    "duration_minutes": 60.0,
                    "time_to_first_output_minutes": score,
                    "corrections": 0,
                    "context_questions": 0,
                }
                f.write(json.dumps(record) + "\n")

    def test_fewer_than_3_sessions_returns_none(self):
        self._write_synthetic_records([5.0, 4.0])
        assert self.metrics.get_trend() is None

    def test_improving_trend_detected(self):
        # Sessions getting faster: 10min → 2min
        self._write_synthetic_records([10, 9, 8, 7, 6, 5, 4, 3, 2])
        trend = self.metrics.get_trend()
        assert trend is not None
        assert trend.slope < 0  # Negative slope = improving
        assert trend.improving is True

    def test_degrading_trend_detected(self):
        # Sessions getting slower: 2min → 10min
        self._write_synthetic_records([2, 3, 4, 5, 6, 7, 8, 9, 10])
        trend = self.metrics.get_trend()
        assert trend is not None
        assert trend.slope > 0  # Positive slope = degrading
        assert trend.improving is False

    def test_flat_trend(self):
        # No change
        self._write_synthetic_records([5, 5, 5, 5, 5])
        trend = self.metrics.get_trend()
        assert trend is not None
        assert abs(trend.slope) < 0.01

    def test_corrections_increase_score(self):
        """Corrections should make the composite score worse."""
        with open(self.tmp.name, "w") as f:
            for i in range(5):
                record = {
                    "session_id": f"s{i}",
                    "project": "test",
                    "started_at": f"2026-03-{i + 1:02d}T09:00:00",
                    "ended_at": f"2026-03-{i + 1:02d}T10:00:00",
                    "duration_minutes": 60.0,
                    "time_to_first_output_minutes": 5.0,  # Same TTFO
                    "corrections": 5 - i,  # Decreasing corrections (improving)
                    "context_questions": 0,
                }
                f.write(json.dumps(record) + "\n")

        trend = self.metrics.get_trend()
        assert trend is not None
        assert trend.improving is True  # Fewer corrections = better

    def test_trend_respects_last_n(self):
        # 20 records, but only look at last 5
        self._write_synthetic_records(list(range(1, 21)))
        trend = self.metrics.get_trend(last_n=5)
        assert trend is not None
        assert trend.sessions_analyzed == 5
