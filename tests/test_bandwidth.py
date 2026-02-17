"""
Tests for Human-AI Bandwidth Research Module

Tests:
- Session handoff capture and storage
- Bandwidth meter metrics
- Prediction tracker and calibration
- Dashboard rendering
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestSessionHandoff:
    """Tests for session handoff capture."""

    def test_session_handoff_creation(self):
        """Test creating a SessionHandoff with all fields."""
        from intelligence.bandwidth.handoff_capture import (
            Decision,
            SessionHandoff,
            WorkstreamType,
        )

        handoff = SessionHandoff(
            timestamp=datetime.now(),
            session_id="test_session_123",
            project="VortexV2",
            workstream=WorkstreamType.BUILDING,
            active_task="Debug wind_speed forecast",
            task_status="in_progress",
            blockers=["Missing GRIB data"],
            decisions_made=[
                Decision(decision="Use ECMWF over GFS", rationale="Lower MAE", confidence=0.85)
            ],
            open_questions=["How to handle missing timestamps?"],
            files_modified=["app/core/forecast.py"],
            next_action="Run validation suite",
            confidence=0.8,
        )

        assert handoff.project == "VortexV2"
        assert handoff.workstream == WorkstreamType.BUILDING
        assert len(handoff.blockers) == 1
        assert len(handoff.decisions_made) == 1
        assert handoff.decisions_made[0].confidence == 0.85

    def test_session_handoff_to_dict(self):
        """Test serialization to dictionary."""
        from intelligence.bandwidth.handoff_capture import (
            SessionHandoff,
            WorkstreamType,
        )

        handoff = SessionHandoff(
            timestamp=datetime.now(),
            session_id="test_123",
            project="Cortex",
            workstream=WorkstreamType.TESTING,
            active_task="Run integration tests",
            task_status="completed",
        )

        data = handoff.to_dict()

        assert data["project"] == "Cortex"
        assert data["workstream"] == "testing"
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)  # ISO format

    def test_session_handoff_from_dict(self):
        """Test deserialization from dictionary."""
        from intelligence.bandwidth.handoff_capture import (
            SessionHandoff,
            WorkstreamType,
        )

        data = {
            "timestamp": "2026-01-16T10:30:00",
            "session_id": "test_456",
            "project": "Alpha Arena",
            "workstream": "planning",
            "active_task": "Design momentum strategy",
            "task_status": "in_progress",
            "blockers": [],
            "decisions_made": [],
            "open_questions": [],
            "files_modified": [],
            "files_created": [],
            "tests_status": None,
            "next_action": "",
            "suggested_prompt": "",
            "confidence": 0.7,
            "duration_minutes": 0.0,
            "model_used": "",
            "tool": "claude-code",
        }

        handoff = SessionHandoff.from_dict(data)

        assert handoff.project == "Alpha Arena"
        assert handoff.workstream == WorkstreamType.PLANNING
        assert isinstance(handoff.timestamp, datetime)

    def test_handoff_storage(self):
        """Test handoff storage with temp directory."""
        from intelligence.bandwidth.handoff_capture import (
            HandoffStorage,
            SessionHandoff,
            WorkstreamType,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = HandoffStorage(storage_dir=Path(tmpdir))

            # Save a handoff
            handoff = SessionHandoff(
                timestamp=datetime.now(),
                session_id="storage_test",
                project="TestProject",
                workstream=WorkstreamType.BUILDING,
                active_task="Test task",
                task_status="in_progress",
            )

            storage.save(handoff)

            # Load it back
            loaded = storage.load_recent(limit=1)

            assert len(loaded) == 1
            assert loaded[0].project == "TestProject"
            assert loaded[0].session_id == "storage_test"


class TestBandwidthMeter:
    """Tests for bandwidth measurement."""

    def test_bandwidth_metrics_creation(self):
        """Test creating BandwidthMetrics."""
        from intelligence.bandwidth.meter import BandwidthMetrics

        metrics = BandwidthMetrics(
            timestamp=datetime.now(),
            session_id="metrics_test",
            project="Cortex",
            tokens_in=1500,
            tokens_out=800,
            tokens_useful=600,
            corrections=2,
            iterations=5,
            time_to_productive_seconds=180.0,
            files_modified=3,
        )

        # Check computed properties
        assert metrics.signal_ratio == 600 / 800  # 0.75
        assert metrics.correction_rate == 2 / 5  # 0.4

    def test_bandwidth_metrics_edge_cases(self):
        """Test edge cases (zero values)."""
        from intelligence.bandwidth.meter import BandwidthMetrics

        metrics = BandwidthMetrics(
            timestamp=datetime.now(),
            session_id="edge_test",
            project="Test",
            tokens_out=0,  # No output
            iterations=0,  # No iterations
        )

        # Should not raise division errors
        assert metrics.signal_ratio == 0.0
        assert metrics.correction_rate == 0.0

    def test_bandwidth_meter_storage(self):
        """Test meter storage and aggregation."""
        from intelligence.bandwidth.meter import BandwidthMeter, BandwidthMetrics

        with tempfile.TemporaryDirectory() as tmpdir:
            meter = BandwidthMeter(storage_dir=Path(tmpdir))

            # Record some metrics
            for i in range(3):
                metrics = BandwidthMetrics(
                    timestamp=datetime.now(),
                    session_id=f"session_{i}",
                    project="TestProject",
                    tokens_in=1000,
                    tokens_out=500,
                    tokens_useful=400,
                    corrections=1,
                    iterations=3,
                    files_modified=2,
                )
                meter.record(metrics)

            # Get aggregate stats
            stats = meter.get_aggregate_stats(days=7)

            assert stats["sessions"] == 3
            assert stats["avg_signal_ratio"] == pytest.approx(0.8, rel=0.01)
            assert stats["total_files_modified"] == 6


class TestPredictionTracker:
    """Tests for prediction tracking and calibration."""

    def test_record_prediction(self):
        """Test recording a prediction."""
        from intelligence.bandwidth.predictions import PredictionTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PredictionTracker(storage_dir=Path(tmpdir))

            prediction = tracker.record_prediction(
                prediction_id="pred_001",
                confidence=0.85,
                domain="code",
                description="This implementation will pass tests",
            )

            assert prediction.prediction_id == "pred_001"
            assert prediction.confidence == 0.85
            assert prediction.domain == "code"
            assert prediction.outcome is None  # Not yet recorded

    def test_record_outcome(self):
        """Test recording an outcome for a prediction."""
        from intelligence.bandwidth.predictions import PredictionTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PredictionTracker(storage_dir=Path(tmpdir))

            # Record prediction
            tracker.record_prediction(
                prediction_id="pred_002",
                confidence=0.7,
                domain="architecture",
                description="This design will scale",
            )

            # Record outcome
            updated = tracker.record_outcome("pred_002", was_correct=True)

            assert updated is not None
            assert updated.outcome is True
            assert updated.outcome_timestamp is not None

    def test_calibration_updates(self):
        """Test that calibration curves update correctly."""
        from intelligence.bandwidth.predictions import PredictionTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = PredictionTracker(storage_dir=Path(tmpdir))

            # Record multiple predictions with outcomes
            for i in range(5):
                tracker.record_prediction(
                    prediction_id=f"calibration_pred_{i}",
                    confidence=0.8,
                    domain="testing",
                )
                # 4 successes, 1 failure
                tracker.record_outcome(f"calibration_pred_{i}", was_correct=(i < 4))

            # Check calibration
            calibrations = tracker.get_calibration(domain="testing")

            assert "testing" in calibrations
            cal = calibrations["testing"]
            assert cal.successes == 4
            assert cal.failures == 1
            assert cal.total == 5

    def test_bayesian_calibration(self):
        """Test Bayesian confidence calculation."""
        from intelligence.bandwidth.predictions import DomainCalibration

        # With prior Beta(2,2), 4 successes, 1 failure:
        # Posterior = Beta(6, 3)
        # Mean = 6 / 9 = 0.667
        cal = DomainCalibration(
            domain="code",
            successes=4,
            failures=1,
            total=5,
        )

        # Expected: posterior_mean * certainty + 0.5 * (1-certainty)
        # certainty = 5/10 = 0.5
        # calibrated = (6/9) * 0.5 + 0.5 * 0.5 = 0.333 + 0.25 = 0.583
        assert cal.calibrated_confidence == pytest.approx(0.583, rel=0.05)
        assert cal.certainty == 0.5


class TestDashboard:
    """Tests for dashboard rendering."""

    def test_render_dashboard_empty(self):
        """Test dashboard renders without data."""
        from intelligence.bandwidth.dashboard import render_dashboard

        with tempfile.TemporaryDirectory():
            # Override storage directory (dashboard uses default)
            # This test just ensures no crashes with empty data
            output = render_dashboard(days=7)

            assert "BANDWIDTH METRICS" in output
            assert "SESSION STATS" in output

    def test_get_dashboard_data(self):
        """Test dashboard data structure."""
        from intelligence.bandwidth.dashboard import get_dashboard_data

        data = get_dashboard_data(days=7)

        assert "generated_at" in data
        assert "session_stats" in data
        assert "calibration" in data
        assert "trends" in data
        assert "recent_handoffs" in data


class TestBandwidthExperiments:
    """Tests for batch experiment runner."""

    def test_experiment_task_definition(self):
        """Test experiment tasks are properly defined."""
        from batch.bandwidth_experiments import BandwidthExperimentRunner

        runner = BandwidthExperimentRunner()
        tasks = runner._define_experiment_tasks()

        # Should have 5 experiments
        assert len(tasks) == 5

        # Check wave distribution
        wave_1_tasks = [t for t in tasks if t.wave_id == "wave_1"]
        wave_2_tasks = [t for t in tasks if t.wave_id == "wave_2"]
        wave_3_tasks = [t for t in tasks if t.wave_id == "wave_3"]

        assert len(wave_1_tasks) == 2  # context_compression, trust_calibration
        assert len(wave_2_tasks) == 2  # handoff_protocol, idea_augmentation
        assert len(wave_3_tasks) == 1  # synthesis_report

    def test_dry_run_experiments(self):
        """Test dry run doesn't submit tasks."""
        from batch.bandwidth_experiments import BandwidthExperimentRunner

        runner = BandwidthExperimentRunner()
        result = runner.submit_all_experiments(dry_run=True)

        # Dry run returns empty dict (doesn't submit)
        assert result == {}


# Integration test
class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_workflow(self):
        """Test complete workflow: capture -> measure -> predict -> outcome."""
        from intelligence.bandwidth.handoff_capture import WorkstreamType
        from intelligence.bandwidth.meter import BandwidthMeter
        from intelligence.bandwidth.predictions import PredictionTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_dir = Path(tmpdir)

            # 1. Capture handoff
            from intelligence.bandwidth.handoff_capture import HandoffStorage

            handoff_storage = HandoffStorage(storage_dir=storage_dir)
            from intelligence.bandwidth.handoff_capture import SessionHandoff

            handoff = SessionHandoff(
                timestamp=datetime.now(),
                session_id="integration_test",
                project="TestProject",
                workstream=WorkstreamType.BUILDING,
                active_task="Integration test",
                task_status="completed",
            )
            handoff_storage.save(handoff)

            # 2. Record metrics
            meter = BandwidthMeter(storage_dir=storage_dir)
            from intelligence.bandwidth.meter import BandwidthMetrics

            metrics = BandwidthMetrics(
                timestamp=datetime.now(),
                session_id="integration_test",
                project="TestProject",
                tokens_in=1000,
                tokens_out=500,
                tokens_useful=450,
                corrections=1,
                iterations=4,
                files_modified=2,
            )
            meter.record(metrics)

            # 3. Record prediction and outcome
            tracker = PredictionTracker(storage_dir=storage_dir)
            tracker.record_prediction(
                prediction_id="integration_pred",
                confidence=0.9,
                domain="code",
                description="Integration test prediction",
            )
            tracker.record_outcome("integration_pred", was_correct=True)

            # 4. Verify all data is stored
            loaded_handoffs = handoff_storage.load_recent(limit=10)
            loaded_metrics = meter.load_metrics(days=7)
            calibrations = tracker.get_calibration(domain="code")

            assert len(loaded_handoffs) == 1
            assert len(loaded_metrics) == 1
            assert calibrations["code"].successes == 1
