"""ML-based confidence calibration using Bayesian updating.

The key insight: 3 successes / 1 failure = 75% success rate, but we're LESS
certain than 30 successes / 10 failures with the same 75% rate. This module
uses Beta-Binomial Bayesian updating to account for both rate AND certainty.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..memory.graph import GraphMemory
    from .outcomes import OutcomeDetector


@dataclass
class OutcomeStats:
    """Statistics about outcomes for a pattern."""

    successes: int = 0
    failures: int = 0
    partial: int = 0
    total: int = 0
    last_outcome: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Raw success rate (0-1)."""
        if self.total == 0:
            return 0.5  # Prior: assume 50%
        return self.successes / self.total

    @property
    def failure_rate(self) -> float:
        """Raw failure rate (0-1)."""
        if self.total == 0:
            return 0.5
        return self.failures / self.total


@dataclass
class CalibrationResult:
    """Result of confidence calibration."""

    pattern_id: str
    pattern_name: str
    old_confidence: float
    new_confidence: float
    delta: float
    outcome_stats: OutcomeStats
    certainty: float  # How confident we are in the confidence


class ConfidenceCalibrator:
    """Bayesian confidence calibration based on outcomes.

    Uses Beta-Binomial model:
    - Prior: Beta(α=2, β=2) = neutral 50% expectation
    - Posterior: Beta(α + successes, β + failures)
    - Confidence = posterior mean, adjusted for certainty

    Why Bayesian?
    - 3/1 (75%) with low certainty → ~63% confidence
    - 30/10 (75%) with high certainty → ~73% confidence
    - New patterns start at prior (50%)
    """

    # Prior parameters (Beta distribution)
    # α=2, β=2 gives ~50% mean with moderate uncertainty
    PRIOR_ALPHA = 2
    PRIOR_BETA = 2

    # Minimum outcomes to trust the calibrated confidence
    MIN_OUTCOMES_FOR_CERTAINTY = 10

    def __init__(
        self,
        graph: Optional["GraphMemory"] = None,
        outcomes: Optional["OutcomeDetector"] = None,
    ):
        """Initialize calibrator.

        Args:
            graph: GraphMemory for finding pattern-outcome links
            outcomes: OutcomeDetector for outcome data
        """
        self.graph = graph
        self.outcomes = outcomes

    def calculate_confidence(self, stats: OutcomeStats) -> tuple[float, float]:
        """Calculate calibrated confidence from outcome stats.

        Args:
            stats: Outcome statistics

        Returns:
            Tuple of (confidence, certainty)
        """
        # Bayesian posterior parameters
        alpha = self.PRIOR_ALPHA + stats.successes
        # Partial successes count as 0.5 failures
        beta = self.PRIOR_BETA + stats.failures + (stats.partial * 0.5)

        # Posterior mean
        posterior_mean = alpha / (alpha + beta)

        # Certainty: how much we trust the posterior
        # Ranges from 0 (no data) to 1 (sufficient data)
        certainty = min(1.0, stats.total / self.MIN_OUTCOMES_FOR_CERTAINTY)

        # Blend posterior with prior based on certainty
        # Low data → stays near prior (0.5)
        # High data → moves toward posterior
        confidence = (posterior_mean * certainty) + (0.5 * (1 - certainty))

        return round(confidence, 3), round(certainty, 2)

    def calculate_for_pattern(
        self, pattern_id: str, project: Optional[str] = None
    ) -> CalibrationResult:
        """Calculate calibrated confidence for a pattern.

        Args:
            pattern_id: Pattern graph node ID
            project: Optional project filter

        Returns:
            CalibrationResult with old/new confidence
        """
        if not self.graph:
            raise ValueError("GraphMemory required for pattern calibration")

        # Get pattern node
        pattern_node = self.graph.get_node(pattern_id)
        if not pattern_node:
            raise ValueError(f"Pattern not found: {pattern_id}")

        # Get current confidence
        old_confidence = pattern_node.data.get("confidence", 0.5)

        # Get outcome stats
        stats = self._get_outcome_stats_for_pattern(pattern_id, project)

        # Calculate new confidence
        new_confidence, certainty = self.calculate_confidence(stats)

        return CalibrationResult(
            pattern_id=pattern_id,
            pattern_name=pattern_node.name,
            old_confidence=old_confidence,
            new_confidence=new_confidence,
            delta=new_confidence - old_confidence,
            outcome_stats=stats,
            certainty=certainty,
        )

    def _get_outcome_stats_for_pattern(
        self, pattern_id: str, project: Optional[str] = None
    ) -> OutcomeStats:
        """Get outcome statistics for a pattern.

        Args:
            pattern_id: Pattern graph node ID
            project: Optional project filter

        Returns:
            OutcomeStats for the pattern
        """
        from ..memory.models import MemoryType, RelationType

        if not self.graph:
            return OutcomeStats()

        # Find edges where outcome VALIDATES pattern
        edges = self.graph.get_edges(to_id=pattern_id, relation=RelationType.VALIDATES)

        stats = OutcomeStats()

        for edge in edges:
            # Get the outcome node
            outcome_node = self.graph.get_node(edge.from_id)
            if not outcome_node or outcome_node.type != MemoryType.OUTCOME:
                continue

            outcome_data = outcome_node.data or {}

            # Filter by project if specified
            if project and outcome_data.get("project") != project:
                continue

            # Get outcome type
            outcome_type = outcome_data.get("outcome_type", "unknown")

            stats.total += 1

            if outcome_type == "success":
                stats.successes += 1
            elif outcome_type == "failure":
                stats.failures += 1
            elif outcome_type == "partial":
                stats.partial += 1

            # Track last outcome time
            timestamp_str = outcome_data.get("timestamp")
            if timestamp_str:
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                    if stats.last_outcome is None or ts > stats.last_outcome:
                        stats.last_outcome = ts
                except ValueError:
                    pass

        return stats

    def recalibrate_all(self, project: Optional[str] = None) -> Dict[str, CalibrationResult]:
        """Recalibrate confidence for all patterns.

        Args:
            project: Optional project filter

        Returns:
            Dict of pattern_id -> CalibrationResult
        """
        from ..memory.models import MemoryType

        if not self.graph:
            raise ValueError("GraphMemory required")

        patterns = self.graph.find_nodes(type=MemoryType.PATTERN)
        results = {}

        for pattern in patterns:
            try:
                result = self.calculate_for_pattern(pattern.id, project)

                # Only include if there was a meaningful change
                if abs(result.delta) > 0.01 or result.outcome_stats.total > 0:
                    results[pattern.id] = result

                    # Update pattern in graph if confidence changed significantly
                    if abs(result.delta) > 0.01:
                        pattern.data["confidence"] = result.new_confidence
                        self.graph.update_node(pattern.id, data=pattern.data)

            except Exception:
                continue

        return results

    def get_confidence_report(self, project: Optional[str] = None) -> Dict[str, Any]:
        """Generate a confidence report for all patterns.

        Args:
            project: Optional project filter

        Returns:
            Report with confidence distribution and recommendations
        """
        from ..memory.models import MemoryType

        if not self.graph:
            return {"error": "GraphMemory required"}

        patterns = self.graph.find_nodes(type=MemoryType.PATTERN)

        report = {
            "total_patterns": len(patterns),
            "high_confidence": 0,  # > 0.7
            "medium_confidence": 0,  # 0.4 - 0.7
            "low_confidence": 0,  # < 0.4
            "needs_data": 0,  # < MIN_OUTCOMES
            "patterns": [],
            "recommendations": [],
        }

        for pattern in patterns:
            stats = self._get_outcome_stats_for_pattern(pattern.id, project)
            confidence, certainty = self.calculate_confidence(stats)

            pattern_info = {
                "id": pattern.id,
                "name": pattern.name,
                "confidence": confidence,
                "certainty": certainty,
                "outcomes": stats.total,
                "success_rate": stats.success_rate,
            }
            report["patterns"].append(pattern_info)

            # Categorize
            if stats.total < self.MIN_OUTCOMES_FOR_CERTAINTY:
                report["needs_data"] += 1
                if stats.total == 0:
                    report["recommendations"].append(
                        f"Pattern '{pattern.name}' has no linked outcomes. "
                        "Link outcomes to improve confidence calibration."
                    )
            elif confidence > 0.7:
                report["high_confidence"] += 1
            elif confidence > 0.4:
                report["medium_confidence"] += 1
            else:
                report["low_confidence"] += 1
                report["recommendations"].append(
                    f"Pattern '{pattern.name}' has low confidence ({confidence:.0%}). "
                    "Consider reviewing or deprecating."
                )

        return report

    @staticmethod
    def calculate_from_counts(
        successes: int, failures: int, partial: int = 0
    ) -> tuple[float, float]:
        """Quick calculation from raw counts.

        Convenience method for testing or one-off calculations.

        Args:
            successes: Number of successes
            failures: Number of failures
            partial: Number of partial successes

        Returns:
            Tuple of (confidence, certainty)
        """
        stats = OutcomeStats(
            successes=successes,
            failures=failures,
            partial=partial,
            total=successes + failures + partial,
        )

        calibrator = ConfidenceCalibrator()
        return calibrator.calculate_confidence(stats)
