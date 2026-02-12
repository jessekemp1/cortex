"""Statistical Validator - Validate predictions, patterns, and recommendations."""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class StatisticalValidator:
    """Perform statistical validation on predictions, patterns, and recommendations."""

    def __init__(self):
        """Initialize statistical validator."""
        pass

    def calculate_confidence_interval(
        self, proportion: float, sample_size: int, confidence_level: float = 0.95
    ) -> tuple:
        """
        Calculate confidence interval for a proportion using Wilson score interval.

        Args:
            proportion: Sample proportion (0.0-1.0)
            sample_size: Sample size
            confidence_level: Confidence level (default: 0.95 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if sample_size == 0:
            return (0.0, 0.0)

        # Z-score for confidence level
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence_level, 1.96)

        # Wilson score interval
        n = sample_size
        p = proportion

        denominator = 1 + (z**2 / n)
        center = (p + (z**2 / (2 * n))) / denominator
        margin = (z / denominator) * math.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return (round(lower, 3), round(upper, 3))

    def validate_pattern_effectiveness(
        self,
        pattern_name: str,
        total_applications: int,
        successful_applications: int,
        success_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Validate pattern effectiveness statistically.

        Args:
            pattern_name: Name of the pattern
            total_applications: Total number of times pattern was applied
            successful_applications: Number of successful applications
            success_threshold: Minimum success rate to consider effective

        Returns:
            Dict with validation results
        """
        if total_applications == 0:
            return {
                "pattern": pattern_name,
                "is_effective": False,
                "success_rate": 0.0,
                "confidence_interval": (0.0, 0.0),
                "validation_status": "insufficient_data",
                "statistical_significance": False,
            }

        success_rate = successful_applications / total_applications
        confidence_interval = self.calculate_confidence_interval(success_rate, total_applications)

        # Check statistical significance (at least 3 applications for basic significance)
        is_significant = total_applications >= 3

        # Check if effective
        is_effective = success_rate >= success_threshold and is_significant

        # Calculate p-value approximation (simplified)
        # For small samples, use binomial test approximation
        p_value = self._approximate_p_value(
            successful_applications, total_applications, success_threshold
        )

        return {
            "pattern": pattern_name,
            "is_effective": is_effective,
            "success_rate": round(success_rate, 3),
            "confidence_interval": confidence_interval,
            "validation_status": "validated" if is_significant else "insufficient_data",
            "statistical_significance": is_significant,
            "p_value_approximation": round(p_value, 4),
            "total_applications": total_applications,
            "successful_applications": successful_applications,
        }

    def validate_recommendation_accuracy(
        self, total_recommendations: int, followed_count: int, successful_count: int
    ) -> Dict[str, Any]:
        """
        Validate recommendation accuracy statistically.

        Args:
            total_recommendations: Total recommendations made
            followed_count: Number of recommendations that were followed
            successful_count: Number of followed recommendations that were successful

        Returns:
            Dict with validation results
        """
        if followed_count == 0:
            return {
                "accuracy": 0.0,
                "confidence_interval": (0.0, 0.0),
                "validation_status": "insufficient_data",
                "follow_rate": 0.0,
            }

        accuracy = successful_count / followed_count
        follow_rate = followed_count / total_recommendations if total_recommendations > 0 else 0.0

        confidence_interval = self.calculate_confidence_interval(accuracy, followed_count)

        is_significant = followed_count >= 10

        return {
            "accuracy": round(accuracy, 3),
            "confidence_interval": confidence_interval,
            "validation_status": "validated" if is_significant else "insufficient_data",
            "follow_rate": round(follow_rate, 3),
            "total_recommendations": total_recommendations,
            "followed_count": followed_count,
            "successful_count": successful_count,
            "statistical_significance": is_significant,
        }

    def generate_calibration_curve(
        self, predictions: List[Dict[str, Any]], num_bins: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate calibration curve data for visualization.

        Args:
            predictions: List of prediction dicts with 'confidence' and 'outcome'
            num_bins: Number of bins for calibration curve (default: 10)

        Returns:
            List of bin statistics
        """
        if not predictions:
            return []

        bins = []
        bin_size = 1.0 / num_bins

        for i in range(num_bins):
            bin_lower = i * bin_size
            bin_upper = (i + 1) * bin_size

            # Handle last bin to include 1.0
            if i == num_bins - 1:
                bin_predictions = [
                    p for p in predictions if bin_lower <= p.get("confidence", 0.0) <= bin_upper
                ]
            else:
                bin_predictions = [
                    p for p in predictions if bin_lower <= p.get("confidence", 0.0) < bin_upper
                ]

            if bin_predictions:
                actual_positive = sum(
                    1
                    for p in bin_predictions
                    if p.get("outcome") == "success" or p.get("was_correct", False)
                )
                total = len(bin_predictions)
                actual_rate = actual_positive / total
                avg_confidence = sum(p.get("confidence", 0.0) for p in bin_predictions) / total

                bins.append(
                    {
                        "bin_range": f"{bin_lower:.2f}-{bin_upper:.2f}",
                        "count": total,
                        "avg_confidence": round(avg_confidence, 3),
                        "actual_rate": round(actual_rate, 3),
                        "calibration_error": round(abs(avg_confidence - actual_rate), 3),
                    }
                )

        return bins

    def _approximate_p_value(self, successes: int, trials: int, null_hypothesis: float) -> float:
        """
        Approximate p-value for binomial test.

        Args:
            successes: Number of successes
            trials: Number of trials
            null_hypothesis: Null hypothesis proportion

        Returns:
            Approximate p-value
        """
        if trials == 0:
            return 1.0

        observed_rate = successes / trials

        # Simplified p-value calculation using normal approximation
        # For more accuracy, would use exact binomial test
        if trials < 30:
            # For small samples, return conservative estimate
            return 0.5  # Cannot determine significance with small sample
        else:
            # Normal approximation
            se = math.sqrt(null_hypothesis * (1 - null_hypothesis) / trials)
            z = (observed_rate - null_hypothesis) / se if se > 0 else 0

            # Approximate p-value (two-tailed)
            # Simplified: use standard normal CDF approximation
            p_value = 2 * (1 - self._normal_cdf(abs(z)))
            return min(max(p_value, 0.0), 1.0)

    def _normal_cdf(self, z: float) -> float:
        """Approximate standard normal CDF."""
        # Abramowitz and Stegun approximation
        t = 1.0 / (1.0 + 0.2316419 * abs(z))
        d = 0.3989423 * math.exp(-z * z / 2)
        p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
        if z > 0:
            return 1 - p
        return p

    def calculate_brier_score(self, predictions: List[Dict[str, Any]]) -> float:
        """
        Calculate Brier score for predictions.

        Args:
            predictions: List of prediction dicts with 'confidence' and 'outcome'

        Returns:
            Brier score (lower is better, 0 = perfect)
        """
        if not predictions:
            return 1.0

        total_score = 0.0
        for p in predictions:
            confidence = p.get("confidence", 0.0)
            actual = 1.0 if (p.get("outcome") == "success" or p.get("was_correct", False)) else 0.0
            total_score += (confidence - actual) ** 2

        return round(total_score / len(predictions), 4)

    def generate_validation_summary(
        self,
        pattern_validations: List[Dict[str, Any]],
        recommendation_validation: Dict[str, Any],
        calibration_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation summary.

        Args:
            pattern_validations: List of pattern validation results
            recommendation_validation: Recommendation validation results
            calibration_stats: Calibration statistics

        Returns:
            Comprehensive validation summary
        """
        # Aggregate pattern statistics
        effective_patterns = sum(1 for p in pattern_validations if p.get("is_effective", False))
        total_patterns = len(pattern_validations)
        pattern_effectiveness_rate = (
            effective_patterns / total_patterns if total_patterns > 0 else 0.0
        )

        # Recommendation statistics
        rec_accuracy = recommendation_validation.get("accuracy", 0.0)
        rec_status = recommendation_validation.get("validation_status", "unknown")

        # Calibration statistics
        calibration_error = calibration_stats.get("calibration_error", 0.0)
        brier_score = calibration_stats.get("brier_score", 1.0)

        return {
            "timestamp": datetime.now().isoformat(),
            "pattern_validation": {
                "total_patterns": total_patterns,
                "effective_patterns": effective_patterns,
                "effectiveness_rate": round(pattern_effectiveness_rate, 3),
                "average_success_rate": round(
                    (
                        sum(p.get("success_rate", 0.0) for p in pattern_validations)
                        / total_patterns
                        if total_patterns > 0
                        else 0.0
                    ),
                    3,
                ),
            },
            "recommendation_validation": {
                "accuracy": rec_accuracy,
                "status": rec_status,
                "follow_rate": recommendation_validation.get("follow_rate", 0.0),
            },
            "calibration": {
                "calibration_error": calibration_error,
                "brier_score": brier_score,
                "status": (
                    "good"
                    if calibration_error < 0.15 and brier_score < 0.25
                    else "needs_improvement"
                ),
            },
            "overall_assessment": self._assess_overall_quality(
                pattern_effectiveness_rate, rec_accuracy, calibration_error
            ),
        }

    def _assess_overall_quality(
        self,
        pattern_effectiveness: float,
        recommendation_accuracy: float,
        calibration_error: float,
    ) -> str:
        """Assess overall system quality."""
        if (
            pattern_effectiveness >= 0.7
            and recommendation_accuracy >= 0.7
            and calibration_error < 0.15
        ):
            return "excellent"
        elif (
            pattern_effectiveness >= 0.5
            and recommendation_accuracy >= 0.5
            and calibration_error < 0.25
        ):
            return "good"
        else:
            return "needs_improvement"


if __name__ == "__main__":
    # Test the validator
    validator = StatisticalValidator()

    # Test confidence interval
    ci = validator.calculate_confidence_interval(0.8, 100)
    print(f"Confidence interval for 80% success rate (n=100): {ci}")

    # Test pattern validation
    pattern_result = validator.validate_pattern_effectiveness(
        "test_pattern", 20, 16, success_threshold=0.7
    )
    print(f"Pattern validation: {pattern_result}")
