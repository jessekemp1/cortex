"""Tests for ML confidence calibration."""

import pytest

from cortex.v2.learning.calibration import (
    CalibrationResult,
    ConfidenceCalibrator,
    OutcomeStats,
)


@pytest.fixture
def calibrator():
    """Create a ConfidenceCalibrator instance."""
    return ConfidenceCalibrator()


class TestOutcomeStats:
    """Test OutcomeStats dataclass."""

    def test_success_rate_no_data(self):
        """No data should return 50% (prior)."""
        stats = OutcomeStats()
        assert stats.success_rate == 0.5

    def test_success_rate_with_data(self):
        """Should calculate correct success rate."""
        stats = OutcomeStats(successes=30, failures=10, total=40)
        assert stats.success_rate == 0.75

    def test_failure_rate(self):
        """Should calculate correct failure rate."""
        stats = OutcomeStats(successes=30, failures=10, total=40)
        assert stats.failure_rate == 0.25


class TestConfidenceCalibrator:
    """Test ConfidenceCalibrator class."""

    def test_new_pattern_gets_prior(self, calibrator):
        """Pattern with no outcomes should get prior (~50%)."""
        stats = OutcomeStats()
        confidence, certainty = calibrator.calculate_confidence(stats)

        assert confidence == 0.5  # Prior mean
        assert certainty == 0.0  # No data, no certainty

    def test_low_data_stays_near_prior(self, calibrator):
        """Few outcomes should stay close to prior."""
        # 3 successes, 1 failure = 75% raw rate
        stats = OutcomeStats(successes=3, failures=1, total=4)
        confidence, certainty = calibrator.calculate_confidence(stats)

        # Should be pulled toward prior (0.5)
        assert 0.54 <= confidence <= 0.70
        assert certainty < 0.5  # Low certainty

    def test_high_data_approaches_rate(self, calibrator):
        """Many outcomes should approach raw success rate."""
        # 30 successes, 10 failures = 75% raw rate
        stats = OutcomeStats(successes=30, failures=10, total=40)
        confidence, certainty = calibrator.calculate_confidence(stats)

        # Should be close to 75%
        assert 0.70 < confidence < 0.80
        assert certainty == 1.0  # High certainty (>= 10 outcomes)

    def test_certainty_difference(self, calibrator):
        """Same rate but different amounts of data should give different confidence."""
        # 3/1 = 75%
        low_data = OutcomeStats(successes=3, failures=1, total=4)
        low_conf, low_cert = calibrator.calculate_confidence(low_data)

        # 30/10 = 75%
        high_data = OutcomeStats(successes=30, failures=10, total=40)
        high_conf, high_cert = calibrator.calculate_confidence(high_data)

        # Same rate, but high data should be more confident
        assert high_conf > low_conf
        assert high_cert > low_cert

    def test_success_increases_confidence(self, calibrator):
        """More successes should increase confidence."""
        base = OutcomeStats(successes=5, failures=5, total=10)
        base_conf, _ = calibrator.calculate_confidence(base)

        more_success = OutcomeStats(successes=8, failures=2, total=10)
        high_conf, _ = calibrator.calculate_confidence(more_success)

        assert high_conf > base_conf

    def test_failure_decreases_confidence(self, calibrator):
        """More failures should decrease confidence."""
        base = OutcomeStats(successes=5, failures=5, total=10)
        base_conf, _ = calibrator.calculate_confidence(base)

        more_failure = OutcomeStats(successes=2, failures=8, total=10)
        low_conf, _ = calibrator.calculate_confidence(more_failure)

        assert low_conf < base_conf

    def test_partial_counts_as_half_failure(self, calibrator):
        """Partial successes should be weighted between success and failure."""
        # 10 successes, 0 failures
        all_success = OutcomeStats(successes=10, failures=0, total=10)
        success_conf, _ = calibrator.calculate_confidence(all_success)

        # 10 successes, 0 failures, 10 partial (= 5 effective failures)
        with_partial = OutcomeStats(successes=10, failures=0, partial=10, total=20)
        partial_conf, _ = calibrator.calculate_confidence(with_partial)

        # Partial should reduce confidence
        assert partial_conf < success_conf

    def test_calculate_from_counts_convenience(self):
        """Static method should work for quick calculations."""
        conf, cert = ConfidenceCalibrator.calculate_from_counts(successes=30, failures=10)

        assert 0.70 < conf < 0.80
        assert cert == 1.0

    def test_confidence_bounded(self, calibrator):
        """Confidence should always be between 0 and 1."""
        # All successes
        all_success = OutcomeStats(successes=100, failures=0, total=100)
        conf, _ = calibrator.calculate_confidence(all_success)
        assert 0 <= conf <= 1

        # All failures
        all_failure = OutcomeStats(successes=0, failures=100, total=100)
        conf, _ = calibrator.calculate_confidence(all_failure)
        assert 0 <= conf <= 1


class TestCalibrationResults:
    """Test calibration result calculations."""

    def test_calibration_result_delta(self):
        """CalibrationResult should calculate delta correctly."""
        result = CalibrationResult(
            pattern_id="test",
            pattern_name="Test Pattern",
            old_confidence=0.5,
            new_confidence=0.75,
            delta=0.25,
            outcome_stats=OutcomeStats(successes=10, failures=2, total=12),
            certainty=1.0,
        )

        assert result.delta == 0.25

    def test_real_world_scenarios(self):
        """Test real-world calibration scenarios."""
        calibrator = ConfidenceCalibrator()

        # Scenario 1: New pattern, never used
        conf, cert = calibrator.calculate_confidence(OutcomeStats())
        assert conf == 0.5
        assert cert == 0.0
        print(f"New pattern: {conf:.0%} confidence, {cert:.0%} certainty")

        # Scenario 2: Pattern used once, succeeded
        conf, cert = calibrator.calculate_confidence(OutcomeStats(successes=1, failures=0, total=1))
        assert 0.5 < conf < 0.6  # Slight boost, but low certainty
        print(f"1 success: {conf:.0%} confidence, {cert:.0%} certainty")

        # Scenario 3: Pattern used 5 times, all succeeded
        conf, cert = calibrator.calculate_confidence(OutcomeStats(successes=5, failures=0, total=5))
        assert conf > 0.6
        print(f"5 successes: {conf:.0%} confidence, {cert:.0%} certainty")

        # Scenario 4: Well-tested pattern, 90% success
        conf, cert = calibrator.calculate_confidence(
            OutcomeStats(successes=18, failures=2, total=20)
        )
        assert conf > 0.8
        assert cert == 1.0
        print(f"18/20 success: {conf:.0%} confidence, {cert:.0%} certainty")

        # Scenario 5: Problematic pattern, 30% success
        conf, cert = calibrator.calculate_confidence(
            OutcomeStats(successes=6, failures=14, total=20)
        )
        assert conf < 0.4
        assert cert == 1.0
        print(f"6/20 success: {conf:.0%} confidence, {cert:.0%} certainty")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
