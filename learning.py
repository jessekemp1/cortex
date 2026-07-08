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

from batch import BatchConfig, BatchFallback, LearningBatcher, LearningContext
from feedback import FeedbackLogger

# Import quality tracking
try:
    from intelligence.quality.data_quality import DataQualityTracker
except ImportError:
    DataQualityTracker = None  # Optional dependency

# Import AI evaluation
try:
    from intelligence.evaluation.quality_judge import QualityJudge
except ImportError:
    QualityJudge = None  # Optional dependency


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
    # Human/auto split: auto-confirmed outcomes (implicit approval, failure
    # emitters) are throughput, not validated quality. The headline quality
    # number is human_success_rate.
    human_confirmed: int = 0
    auto_confirmed: int = 0
    human_success_rate: float = 0.0


class LearningSystem:
    """Analyzes outcomes and provides learning insights."""

    def __init__(self, outcomes_file: Optional[Path] = None):
        """Initialize learning system."""
        if outcomes_file is None:
            outcomes_file = Path.home() / ".cortex" / "outcomes.jsonl"
        self.outcomes_file = outcomes_file
        self.feedback_logger = FeedbackLogger()

        # Initialize quality tracker
        self.quality_tracker = DataQualityTracker() if DataQualityTracker else None

        # Initialize AI quality judge
        self.quality_judge = QualityJudge() if QualityJudge else None

    def calculate_recommendation_accuracy(self, domain: Optional[str] = None) -> float:
        """
        Calculate recommendation accuracy: % of followed recommendations that succeeded.

        Quality-weighted: High-quality outcomes contribute more to the accuracy calculation.

        Args:
            domain: Filter to specific domain ("aidev"/"databricks"), or None for all.

        Returns:
            Success rate (0.0-1.0), or 0.0 if no data
        """
        outcomes = self.feedback_logger.load_outcomes()
        if domain:
            outcomes = [o for o in outcomes if getattr(o, "domain", None) == domain]

        if not outcomes:
            return 0.0

        # Filter to followed recommendations only
        followed = [o for o in outcomes if o.followed]

        if not followed:
            return 0.0

        # Count successes with quality weighting if available
        if self.quality_tracker:
            weighted_success = 0.0
            total_weight = 0.0

            for outcome in followed:
                # Assess quality
                quality = self.quality_tracker.assess_outcome(outcome)
                weight = quality.overall_score()

                # Calculate success value
                if outcome.outcome == "success":
                    success_value = 1.0
                elif outcome.outcome == "partial":
                    success_value = 0.5
                else:
                    success_value = 0.0

                weighted_success += success_value * weight
                total_weight += weight

            return weighted_success / total_weight if total_weight > 0 else 0.0
        else:
            # Fallback to unweighted calculation
            success_count = sum(
                1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0
                for o in followed
            )
            return success_count / len(followed)

    def get_outcome_patterns(self, domain: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Analyze which types of recommendations work best.

        Args:
            domain: Filter to specific domain ("aidev"/"databricks"), or None for all.

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
        if domain:
            outcomes = [o for o in outcomes if getattr(o, "domain", None) == domain]

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
                    (1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0)
                    for o in followed
                )
                success_rate = success_count / len(followed)
            else:
                success_rate = 0.0

            patterns[rec_type] = {
                "total": len(type_outcomes),
                "followed": len(followed),
                "success_rate": success_rate,
                "avg_confidence": sum(o.confidence for o in type_outcomes) / len(type_outcomes),
            }

        return patterns

    def get_confidence_calibration(self, domain: Optional[str] = None) -> Dict[str, float]:
        """
        Analyze confidence calibration: are high-confidence recommendations more successful?

        Args:
            domain: Filter to specific domain ("aidev"/"databricks"), or None for all.

        Returns:
            Dictionary mapping confidence bucket to success rate:
            {
                "high (0.8-1.0)": 0.85,
                "medium (0.5-0.8)": 0.65,
                "low (0.0-0.5)": 0.45
            }
        """
        outcomes = self.feedback_logger.load_outcomes()
        if domain:
            outcomes = [o for o in outcomes if getattr(o, "domain", None) == domain]

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
                    (1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0)
                    for o in bucket_outcomes
                )
                calibration[bucket] = success_count / len(bucket_outcomes)
            else:
                calibration[bucket] = 0.0

        return calibration

    def get_ai_confidence_calibration(self) -> Dict[str, Any]:
        """
        Get AI-evaluated confidence calibration.

        Compares AI quality scores with actual outcome success rates.
        This helps understand if high AI scores predict successful outcomes.

        Returns:
            Dictionary with AI score buckets and their correlation with outcomes:
            {
                "ai_scores": {
                    "high (0.8-1.0)": {"count": 10, "avg_outcome": 0.85},
                    "medium (0.5-0.8)": {"count": 15, "avg_outcome": 0.65},
                    "low (0.0-0.5)": {"count": 5, "avg_outcome": 0.40}
                },
                "correlation": 0.75,  # Correlation between AI score and outcome
                "insights": ["High AI scores correlate with 85% success rate"]
            }
        """
        if not self.quality_judge:
            return {
                "ai_scores": {},
                "correlation": 0.0,
                "insights": ["AI evaluation not available"],
            }

        # Load AI evaluations
        evaluations = self.quality_judge.load_evaluations(item_type="recommendation")

        # Load outcomes
        outcomes = self.feedback_logger.load_outcomes()

        if not evaluations or not outcomes:
            return {
                "ai_scores": {},
                "correlation": 0.0,
                "insights": ["Insufficient data for calibration"],
            }

        # Match evaluations to outcomes by recommendation_id
        eval_by_id = {}
        for eval_entry in evaluations:
            item_id = eval_entry.get("item_id")
            if item_id:
                eval_by_id[item_id] = eval_entry

        # Group by AI score bucket
        buckets = {
            "high (0.8-1.0)": [],
            "medium (0.5-0.8)": [],
            "low (0.0-0.5)": [],
        }

        matched_pairs = []  # (ai_score, outcome_score) for correlation

        for outcome in outcomes:
            if not outcome.followed:
                continue

            # Find matching evaluation
            eval_entry = eval_by_id.get(outcome.recommendation_id)
            if not eval_entry:
                continue

            ai_score = eval_entry.get("score", {}).get("overall", 0.0)

            # Categorize by AI score
            if ai_score >= 0.8:
                bucket = "high (0.8-1.0)"
            elif ai_score >= 0.5:
                bucket = "medium (0.5-0.8)"
            else:
                bucket = "low (0.0-0.5)"

            # Calculate outcome score
            if outcome.outcome == "success":
                outcome_score = 1.0
            elif outcome.outcome == "partial":
                outcome_score = 0.5
            else:
                outcome_score = 0.0

            buckets[bucket].append(outcome_score)
            matched_pairs.append((ai_score, outcome_score))

        # Calculate bucket statistics
        ai_scores = {}
        for bucket, outcomes_list in buckets.items():
            if outcomes_list:
                ai_scores[bucket] = {
                    "count": len(outcomes_list),
                    "avg_outcome": round(sum(outcomes_list) / len(outcomes_list), 3),
                }
            else:
                ai_scores[bucket] = {"count": 0, "avg_outcome": 0.0}

        # Calculate correlation (simple Pearson correlation)
        correlation = 0.0
        insights = []

        if len(matched_pairs) >= 3:
            # Calculate Pearson correlation
            import statistics

            ai_vals = [p[0] for p in matched_pairs]
            outcome_vals = [p[1] for p in matched_pairs]

            if len(set(ai_vals)) > 1 and len(set(outcome_vals)) > 1:
                # Calculate correlation
                ai_mean = statistics.mean(ai_vals)
                outcome_mean = statistics.mean(outcome_vals)

                numerator = sum(
                    (ai - ai_mean) * (out - outcome_mean) for ai, out in zip(ai_vals, outcome_vals)
                )
                ai_var = sum((ai - ai_mean) ** 2 for ai in ai_vals)
                outcome_var = sum((out - outcome_mean) ** 2 for out in outcome_vals)

                if ai_var > 0 and outcome_var > 0:
                    correlation = numerator / (ai_var * outcome_var) ** 0.5

        # Generate insights
        if correlation > 0.7:
            insights.append(
                f"Strong positive correlation ({correlation:.2f}): "
                "High AI scores reliably predict success"
            )
        elif correlation > 0.4:
            insights.append(
                f"Moderate correlation ({correlation:.2f}): "
                "AI scores somewhat predictive of outcomes"
            )
        else:
            insights.append(
                f"Weak correlation ({correlation:.2f}): AI scores may need recalibration"
            )

        # Add bucket-specific insights
        for bucket, stats in ai_scores.items():
            if stats["count"] >= 3:
                insights.append(
                    f"{bucket}: {stats['count']} recommendations, "
                    f"{stats['avg_outcome']:.0%} success rate"
                )

        return {
            "ai_scores": ai_scores,
            "correlation": round(correlation, 3),
            "insights": insights,
            "sample_size": len(matched_pairs),
        }

    @staticmethod
    def outcome_source(o) -> str:
        """Classify an outcome as human- or auto-confirmed.

        New records carry an explicit source field ("human"/"auto"), which is
        trusted. Older records predate it (the loader marks them "") and are
        classified by machine markers: git_/commit_/implicit_ id prefixes,
        implicit_/failure: type prefixes, or context.implicit.
        """
        src = getattr(o, "source", "")
        if src in ("human", "auto"):
            return src
        # Legacy record (no source on disk): classify by machine markers.
        # The real store is dominated by git-activity automation — 1,555 of
        # 1,660 records at the time of this change had git_/commit_ ids.
        rid = str(o.recommendation_id)
        if rid.startswith(("implicit_", "git_", "commit_")):
            return "auto"
        if str(o.recommendation_type).startswith(("implicit_", "failure:")):
            return "auto"
        if isinstance(o.context, dict) and o.context.get("implicit"):
            return "auto"
        return "human"

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

        human = [o for o in outcomes if self.outcome_source(o) == "human"]
        human_followed = [o for o in human if o.followed]
        human_success_rate = (
            sum(1 for o in human_followed if o.outcome == "success") / len(human_followed)
            if human_followed
            else 0.0
        )

        return LearningMetrics(
            total_outcomes=len(outcomes),
            followed_count=len(followed),
            success_rate=success_rate,
            partial_rate=partial_rate,
            failed_rate=failed_rate,
            recommendation_accuracy=self.calculate_recommendation_accuracy(),
            confidence_calibration=self.get_confidence_calibration(),
            outcome_patterns=self.get_outcome_patterns(),
            human_confirmed=len(human),
            auto_confirmed=len(outcomes) - len(human),
            human_success_rate=human_success_rate,
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
        Adjust recommendation confidence based on historical outcomes and calibrated weights.

        Args:
            recommendation_type: Type of recommendation
            base_confidence: Base confidence score (0.0-1.0)

        Returns:
            (adjusted_confidence, explanation)
        """
        # Convert Confidence enum to float if needed
        if hasattr(base_confidence, "value"):
            conf_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            base_confidence = conf_map.get(base_confidence.value.lower(), 0.7)
        elif not isinstance(base_confidence, (int, float)):
            base_confidence = 0.7

        # Import learning config for calibrated weights
        try:
            from learning_config import get_learning_config

            config = get_learning_config()
            type_weight = config.get_weight(recommendation_type)
        except ImportError:
            type_weight = 1.0

        patterns = self.get_outcome_patterns()

        if recommendation_type not in patterns:
            # Apply calibrated weight even without historical data
            adjusted = min(1.0, base_confidence * type_weight)
            return adjusted, f"Using calibrated weight ({type_weight:.1f}x)"

        type_metrics = patterns[recommendation_type]

        if type_metrics["followed"] < 3:
            adjusted = min(1.0, base_confidence * type_weight)
            return (
                adjusted,
                f"Limited data ({type_metrics['followed']} outcomes), using calibrated weight",
            )

        # Adjust based on historical success rate
        historical_success = type_metrics["success_rate"]

        # Blend: 50% base, 30% historical, 20% calibrated weight
        # As we gather more data, trust history more
        history_weight = min(0.3, type_metrics["followed"] / 20)  # Cap at 30%
        calibration_weight = 0.2 * (type_weight - 1.0)  # Boost or penalty from config

        adjusted = base_confidence * (1 - history_weight) + historical_success * history_weight
        adjusted = min(1.0, adjusted + calibration_weight)

        weight_note = f", weight {type_weight:.1f}x" if type_weight != 1.0 else ""
        explanation = f"Based on {type_metrics['followed']} outcomes ({historical_success:.0%} success rate{weight_note})"

        return adjusted, explanation

    def get_rule_outcome_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Correlate rule violations with session outcomes.

        Analyzes whether rule violations correlate with session failures,
        helping to identify which rules have the most impact on outcomes.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with rule-outcome correlations:
            {
                "rules": {
                    "read_before_edit": {
                        "violations": 5,
                        "sessions_with_violations": 3,
                        "avg_session_outcome": 0.6,  # 0=fail, 0.5=partial, 1=success
                        "correlation_score": -0.3,  # negative = violations hurt outcomes
                    },
                    ...
                },
                "insights": ["rule X has strong negative correlation with success", ...],
                "total_sessions": 10,
            }
        """
        import json
        from collections import defaultdict
        from datetime import datetime, timedelta

        rule_events_file = Path.home() / ".cortex" / "rule_events.jsonl"
        outcomes = self.feedback_logger.load_outcomes()

        # Load rule events
        rule_events = []
        if rule_events_file.exists():
            cutoff = datetime.now() - timedelta(days=days)
            with open(rule_events_file, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])
                        if event_time >= cutoff:
                            rule_events.append(event)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        if not rule_events or not outcomes:
            return {
                "rules": {},
                "insights": ["Insufficient data for rule-outcome correlation"],
                "total_sessions": 0,
                "total_rule_events": len(rule_events),
            }

        # Group rule events by session (approximate by day for simplicity)
        events_by_day = defaultdict(list)
        for event in rule_events:
            day = event["timestamp"][:10]  # YYYY-MM-DD
            events_by_day[day].append(event)

        # Group outcomes by day
        outcomes_by_day = {}
        for outcome in outcomes:
            if hasattr(outcome, "timestamp"):
                day = str(outcome.timestamp)[:10]
            else:
                continue
            if day not in outcomes_by_day:
                outcomes_by_day[day] = []
            outcomes_by_day[day].append(outcome)

        # Analyze correlations per rule
        rule_stats = defaultdict(
            lambda: {
                "violations": 0,
                "adherences": 0,
                "sessions_with_violations": set(),
                "session_outcomes": [],
            }
        )

        for day, day_events in events_by_day.items():
            day_outcomes = outcomes_by_day.get(day, [])

            # Calculate day's average outcome
            if day_outcomes:
                day_outcome_score = sum(
                    (1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0)
                    for o in day_outcomes
                ) / len(day_outcomes)
            else:
                day_outcome_score = 0.5  # neutral if no outcome data

            for event in day_events:
                rule = event["rule_name"]
                event_type = event["event_type"]

                if event_type == "violation":
                    rule_stats[rule]["violations"] += 1
                    rule_stats[rule]["sessions_with_violations"].add(day)
                    rule_stats[rule]["session_outcomes"].append(day_outcome_score)
                elif event_type == "adherence":
                    rule_stats[rule]["adherences"] += 1

        # Calculate correlation scores
        rules_analysis = {}
        insights = []

        for rule, stats in rule_stats.items():
            violations = stats["violations"]
            adherences = stats["adherences"]
            session_outcomes = stats["session_outcomes"]

            if session_outcomes:
                avg_outcome = sum(session_outcomes) / len(session_outcomes)
            else:
                avg_outcome = 0.5

            # Simple correlation: how much do violations correlate with lower outcomes?
            # Negative score = violations hurt outcomes
            # Compare to baseline (0.5 = neutral)
            correlation_score = avg_outcome - 0.5  # negative if outcomes are below average

            rules_analysis[rule] = {
                "violations": violations,
                "adherences": adherences,
                "sessions_with_violations": len(stats["sessions_with_violations"]),
                "avg_session_outcome": round(avg_outcome, 3),
                "correlation_score": round(correlation_score, 3),
            }

            # Generate insights for problematic rules
            if violations >= 3 and correlation_score < -0.1:
                insights.append(
                    f"Rule '{rule}' has {violations} violations with below-average outcomes "
                    f"(avg: {avg_outcome:.0%}). Consider stricter enforcement."
                )
            elif violations >= 5 and correlation_score > 0.1:
                insights.append(
                    f"Rule '{rule}' violations don't significantly impact outcomes. "
                    f"Consider relaxing this rule."
                )

        return {
            "rules": rules_analysis,
            "insights": (insights if insights else ["No significant patterns detected yet"]),
            "total_sessions": len(events_by_day),
            "total_rule_events": len(rule_events),
            "days_analyzed": days,
        }
