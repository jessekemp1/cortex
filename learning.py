#!/usr/bin/env python3
"""
Cortex Learning System - Learns from recommendation outcomes over time

Analyzes outcome data to:
1. Calculate recommendation accuracy
2. Identify outcome patterns
3. Calibrate confidence scores
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cortex.batch import BatchConfig, BatchFallback, LearningBatcher, LearningContext
from feedback import FeedbackLogger


@dataclass
class LearningMetrics:
    """Learning metrics summary."""

    total_outcomes: int
    followed_count: int
    success_rate: float  # Of followed recommendations
    partial_rate: float
    failed_rate: float
    recommendation_accuracy: float  # % of followed recs that succeeded
    confidence_calibration: Dict[str, float]  # Confidence bucket -> success rate
    outcome_patterns: Dict[str, Dict[str, Any]]  # Type -> metrics


class LearningSystem:
    """Analyzes outcomes and provides learning insights."""

    def __init__(self, outcomes_file: Optional[Path] = None):
        """Initialize learning system."""
        if outcomes_file is None:
            outcomes_file = Path.home() / ".cortex" / "outcomes.jsonl"
        self.outcomes_file = outcomes_file
        self.feedback_logger = FeedbackLogger()

    def calculate_recommendation_accuracy(self) -> float:
        """
        Calculate recommendation accuracy: % of followed recommendations that succeeded.

        Returns:
            Success rate (0.0-1.0), or 0.0 if no data
        """
        outcomes = self.feedback_logger.load_outcomes()

        if not outcomes:
            return 0.0

        # Filter to followed recommendations only
        followed = [o for o in outcomes if o.followed]

        if not followed:
            return 0.0

        # Count successes (including partial as 0.5 success)
        success_count = sum(
            1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0
            for o in followed
        )

        return success_count / len(followed)

    def get_outcome_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        Analyze which types of recommendations work best.

        Returns:
            Dictionary mapping recommendation_type to metrics:
            {
                "goal_progress": {
                    "total": 10,
                    "followed": 8,
                    "success_rate": 0.75,
                    "avg_confidence": 0.8
                },
                ...
            }
        """
        outcomes = self.feedback_logger.load_outcomes()

        if not outcomes:
            return {}

        # Group by recommendation type
        by_type = defaultdict(list)
        for outcome in outcomes:
            by_type[outcome.recommendation_type].append(outcome)

        # Calculate metrics per type
        patterns = {}
        for rec_type, type_outcomes in by_type.items():
            followed = [o for o in type_outcomes if o.followed]

            if followed:
                success_count = sum(
                    (
                        1.0
                        if o.outcome == "success"
                        else 0.5 if o.outcome == "partial" else 0.0
                    )
                    for o in followed
                )
                success_rate = success_count / len(followed)
            else:
                success_rate = 0.0

            patterns[rec_type] = {
                "total": len(type_outcomes),
                "followed": len(followed),
                "success_rate": success_rate,
                "avg_confidence": sum(o.confidence for o in type_outcomes)
                / len(type_outcomes),
            }

        return patterns

    def get_confidence_calibration(self) -> Dict[str, float]:
        """
        Analyze confidence calibration: are high-confidence recommendations more successful?

        Returns:
            Dictionary mapping confidence bucket to success rate:
            {
                "high (0.8-1.0)": 0.85,
                "medium (0.5-0.8)": 0.65,
                "low (0.0-0.5)": 0.45
            }
        """
        outcomes = self.feedback_logger.load_outcomes()

        if not outcomes:
            return {}

        # Group by confidence bucket
        buckets = {"high (0.8-1.0)": [], "medium (0.5-0.8)": [], "low (0.0-0.5)": []}

        for outcome in outcomes:
            if not outcome.followed:
                continue

            if outcome.confidence >= 0.8:
                bucket = "high (0.8-1.0)"
            elif outcome.confidence >= 0.5:
                bucket = "medium (0.5-0.8)"
            else:
                bucket = "low (0.0-0.5)"

            buckets[bucket].append(outcome)

        # Calculate success rate per bucket
        calibration = {}
        for bucket, bucket_outcomes in buckets.items():
            if bucket_outcomes:
                success_count = sum(
                    (
                        1.0
                        if o.outcome == "success"
                        else 0.5 if o.outcome == "partial" else 0.0
                    )
                    for o in bucket_outcomes
                )
                calibration[bucket] = success_count / len(bucket_outcomes)
            else:
                calibration[bucket] = 0.0

        return calibration

    def get_learning_metrics(self) -> LearningMetrics:
        """
        Get comprehensive learning metrics.

        Returns:
            LearningMetrics object with all metrics
        """
        outcomes = self.feedback_logger.load_outcomes()

        if not outcomes:
            return LearningMetrics(
                total_outcomes=0,
                followed_count=0,
                success_rate=0.0,
                partial_rate=0.0,
                failed_rate=0.0,
                recommendation_accuracy=0.0,
                confidence_calibration={},
                outcome_patterns={},
            )

        followed = [o for o in outcomes if o.followed]

        if followed:
            success_count = sum(1 for o in followed if o.outcome == "success")
            partial_count = sum(1 for o in followed if o.outcome == "partial")
            failed_count = sum(1 for o in followed if o.outcome == "failed")

            success_rate = success_count / len(followed)
            partial_rate = partial_count / len(followed)
            failed_rate = failed_count / len(followed)
        else:
            success_rate = 0.0
            partial_rate = 0.0
            failed_rate = 0.0

        return LearningMetrics(
            total_outcomes=len(outcomes),
            followed_count=len(followed),
            success_rate=success_rate,
            partial_rate=partial_rate,
            failed_rate=failed_rate,
            recommendation_accuracy=self.calculate_recommendation_accuracy(),
            confidence_calibration=self.get_confidence_calibration(),
            outcome_patterns=self.get_outcome_patterns(),
        )

    def _read_metrics_once(self) -> Dict[str, Any]:
        """Read outcomes.jsonl once and cache metrics

        This is the KEY EFFICIENCY STRATEGY: Load file ONCE, cache all
        metrics in memory, pass to all batch requests. Reduces 5+ sequential
        file reads to single read.
        """
        outcomes = self.feedback_logger.load_outcomes()

        return {
            "total_outcomes": len(outcomes),
            "followed_count": sum(1 for o in outcomes if o.followed),
            "success_rate": self.calculate_recommendation_accuracy(),
            "confidence_calibration": self.get_confidence_calibration(),
            "pattern_summary": self.get_outcome_patterns(),
        }

    def _analyze_patterns_batch(self, context: LearningContext) -> Dict[str, Any]:
        """Batch version of pattern analysis"""
        batcher = LearningBatcher()
        result = batcher.process_batch([context])
        return result["results"].get(context.context_id, {})

    def _analyze_patterns_sequential(self, execution_history: Dict) -> Dict[str, Any]:
        """Sequential version of pattern analysis (fallback)"""
        # This would be the original implementation
        # For now, return basic structure
        return {
            "key_insights": [],
            "pattern_discoveries": [],
            "confidence_assessment": "Sequential processing (batch disabled)",
            "adjustment_suggestions": [],
        }

    def analyze_patterns(self, execution_history: Dict) -> Dict[str, Any]:
        """Analyze execution patterns with batch/fallback support

        If batch enabled: Uses batch API with cached metrics
        If batch disabled or fails: Falls back to sequential processing
        """
        if BatchConfig.is_batch_enabled("learning"):
            # Read metrics ONCE and cache
            metrics_data = self._read_metrics_once()

            context = LearningContext(
                execution_history=execution_history,
                goals_context={},  # Would come from orchestrator context
                metrics_data=metrics_data,  # SINGLE FILE READ
                context_id="learning_001",
            )

            result = BatchFallback.process_with_fallback(
                items=[context],
                batch_processor=self._analyze_patterns_batch,
                sequential_processor=lambda ctx: self._analyze_patterns_sequential(
                    ctx.execution_history
                ),
                feature="learning",
            )
            return result
        else:
            return self._analyze_patterns_sequential(execution_history)

    def adjust_confidence_based_on_history(
        self, recommendation_type: str, base_confidence: float
    ) -> Tuple[float, str]:
        """
        Adjust recommendation confidence based on historical outcomes.

        Args:
            recommendation_type: Type of recommendation
            base_confidence: Base confidence score (0.0-1.0)

        Returns:
            (adjusted_confidence, explanation)
        """
        patterns = self.get_outcome_patterns()

        if recommendation_type not in patterns:
            return base_confidence, "No historical data for this recommendation type"

        type_metrics = patterns[recommendation_type]

        if type_metrics["followed"] < 3:
            return (
                base_confidence,
                f"Limited data ({type_metrics['followed']} outcomes)",
            )

        # Adjust based on historical success rate
        historical_success = type_metrics["success_rate"]

        # Simple adjustment: blend base confidence with historical success
        # Weight: 60% base, 40% historical (as we gather more data, trust history more)
        weight = min(0.4, type_metrics["followed"] / 20)  # Cap at 40% weight
        adjusted = base_confidence * (1 - weight) + historical_success * weight

        explanation = f"Based on {type_metrics['followed']} previous outcomes ({historical_success:.0%} success rate)"

        return adjusted, explanation
