#!/usr/bin/env python3
"""
Data Quality Tracker - Main quality assessment system

Provides quality tracking across all Cortex data types:
- Patterns
- Feedback entries
- Outcome entries
- Recommendations
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add cortex to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Delay feedback imports to avoid circular dependency
# from feedback import FeedbackEntry, OutcomeEntry
from intelligence.memory.pattern_indexer import Pattern
from intelligence.quality.dimensions import DimensionCheckers


@dataclass
class QualityDimensions:
    """Six quality dimensions for data assessment."""

    completeness: float  # Required fields present (0.0-1.0)
    consistency: float  # No contradictions (0.0-1.0)
    accuracy: float  # Factually correct (0.0-1.0)
    timeliness: float  # Data freshness (0.0-1.0)
    uniqueness: float  # No duplicates (0.0-1.0)
    validity: float  # Format/schema valid (0.0-1.0)

    def overall_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate weighted overall quality score.

        Args:
            weights: Optional custom weights for dimensions
                    Default: completeness=0.2, consistency=0.2, accuracy=0.25,
                            timeliness=0.15, uniqueness=0.1, validity=0.1

        Returns:
            Weighted average score 0.0-1.0
        """
        if weights is None:
            weights = {
                "completeness": 0.2,
                "consistency": 0.2,
                "accuracy": 0.25,
                "timeliness": 0.15,
                "uniqueness": 0.1,
                "validity": 0.1,
            }

        score = 0.0
        for dimension in [
            "completeness",
            "consistency",
            "accuracy",
            "timeliness",
            "uniqueness",
            "validity",
        ]:
            score += getattr(self, dimension) * weights.get(dimension, 0.0)

        return score

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "completeness": self.completeness,
            "consistency": self.consistency,
            "accuracy": self.accuracy,
            "timeliness": self.timeliness,
            "uniqueness": self.uniqueness,
            "validity": self.validity,
            "overall": self.overall_score(),
        }


class DataQualityTracker:
    """Track data quality metrics across Cortex."""

    def __init__(self):
        """Initialize quality tracker."""
        self.checkers = DimensionCheckers()
        self.existing_hashes: Set[str] = set()  # For uniqueness checking

        # Quality history for trend tracking
        self.quality_history: List[Dict[str, Any]] = []

    def assess_pattern(self, pattern: Pattern) -> QualityDimensions:
        """
        Assess quality of a pattern.

        Args:
            pattern: Pattern object to assess

        Returns:
            QualityDimensions with scores for each dimension
        """
        # Convert pattern to dict for checking
        data = pattern.to_dict()

        # Required fields for patterns
        required_fields = [
            "id",
            "project",
            "commit_hash",
            "title",
            "description",
            "files_changed",
        ]

        # Check completeness
        completeness = self.checkers.check_completeness(data, required_fields)

        # Check consistency
        consistency_rules = [
            {
                "type": "value_range",
                "field": "commit_date",
                "min": "2020-01-01",
                "max": "2030-12-31",
            }
        ]
        consistency = self.checkers.check_consistency(data, consistency_rules)

        # Check accuracy (basic sanity checks)
        accuracy = self.checkers.check_accuracy(data)

        # Check timeliness (patterns older than 6 months decay)
        timeliness = self.checkers.check_timeliness(
            data, timestamp_field="commit_date", max_age_days=180
        )

        # Check uniqueness (by pattern id)
        uniqueness = self.checkers.check_uniqueness(data, self.existing_hashes, ["id"])

        # Check validity
        pattern_schema = {
            "id": {"type": "str"},
            "project": {"type": "str"},
            "commit_hash": {"type": "str"},
            "title": {"type": "str"},
            "description": {"type": "str"},
            "files_changed": {"type": "list"},
            "keywords": {"type": "list"},
        }
        validity = self.checkers.check_validity(data, pattern_schema)

        return QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

    def assess_feedback(self, entry: "FeedbackEntry") -> QualityDimensions:
        """
        Assess quality of a feedback entry.

        Args:
            entry: FeedbackEntry object to assess

        Returns:
            QualityDimensions with scores for each dimension
        """
        # Convert to dict
        from dataclasses import asdict

        data = asdict(entry)

        # Required fields
        required_fields = ["timestamp", "action_title", "useful"]

        # Check completeness
        completeness = self.checkers.check_completeness(data, required_fields)

        # Check consistency
        consistency = self.checkers.check_consistency(data)

        # Check accuracy
        accuracy = self.checkers.check_accuracy(data)

        # Check timeliness (feedback older than 30 days decays)
        timeliness = self.checkers.check_timeliness(
            data, timestamp_field="timestamp", max_age_days=30
        )

        # Check uniqueness
        uniqueness = self.checkers.check_uniqueness(
            data, self.existing_hashes, ["timestamp", "action_title"]
        )

        # Check validity
        feedback_schema = {
            "timestamp": {"type": "str"},
            "action_title": {"type": "str"},
            "useful": {"type": "bool"},
        }
        validity = self.checkers.check_validity(data, feedback_schema)

        return QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

    def assess_outcome(self, outcome: "OutcomeEntry") -> QualityDimensions:
        """
        Assess quality of an outcome entry.

        Args:
            outcome: OutcomeEntry object to assess

        Returns:
            QualityDimensions with scores for each dimension
        """
        # Convert to dict
        from dataclasses import asdict

        data = asdict(outcome)

        # Required fields
        required_fields = [
            "timestamp",
            "recommendation_id",
            "recommendation_title",
            "recommendation_type",
            "priority",
            "confidence",
            "followed",
            "outcome",
        ]

        # Check completeness
        completeness = self.checkers.check_completeness(data, required_fields)

        # Check consistency
        consistency_rules = [{"type": "value_range", "field": "confidence", "min": 0.0, "max": 1.0}]
        consistency = self.checkers.check_consistency(data, consistency_rules)

        # Check accuracy
        known_facts = {}
        if data.get("outcome") == "success":
            known_facts["followed"] = True  # Can't succeed without following
        accuracy = self.checkers.check_accuracy(data, known_facts)

        # Check timeliness
        timeliness = self.checkers.check_timeliness(
            data, timestamp_field="timestamp", max_age_days=30
        )

        # Check uniqueness
        uniqueness = self.checkers.check_uniqueness(
            data, self.existing_hashes, ["recommendation_id", "timestamp"]
        )

        # Check validity
        outcome_schema = {
            "timestamp": {"type": "str"},
            "recommendation_id": {"type": "str"},
            "recommendation_title": {"type": "str"},
            "recommendation_type": {"type": "str"},
            "priority": {"type": "str"},
            "confidence": {"type": "float", "min": 0.0, "max": 1.0},
            "followed": {"type": "bool"},
            "outcome": {"type": "str"},
        }
        validity = self.checkers.check_validity(data, outcome_schema)

        return QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

    def assess_recommendation(self, recommendation: Dict[str, Any]) -> QualityDimensions:
        """
        Assess quality of a recommendation.

        Args:
            recommendation: Recommendation dictionary to assess

        Returns:
            QualityDimensions with scores for each dimension
        """
        # Required fields
        required_fields = ["title", "rationale", "priority", "confidence"]

        # Check completeness
        completeness = self.checkers.check_completeness(recommendation, required_fields)

        # Check consistency
        consistency = self.checkers.check_consistency(recommendation)

        # Check accuracy (basic sanity)
        accuracy = self.checkers.check_accuracy(recommendation)

        # Check timeliness
        timeliness = self.checkers.check_timeliness(
            recommendation, timestamp_field="timestamp", max_age_days=7
        )

        # Check uniqueness
        uniqueness = self.checkers.check_uniqueness(
            recommendation, self.existing_hashes, ["title", "rationale"]
        )

        # Check validity
        rec_schema = {
            "title": {"type": "str"},
            "rationale": {"type": "str"},
            "priority": {"type": "str"},
            "confidence": {"type": "float", "min": 0.0, "max": 1.0},
        }
        validity = self.checkers.check_validity(recommendation, rec_schema)

        return QualityDimensions(
            completeness=completeness,
            consistency=consistency,
            accuracy=accuracy,
            timeliness=timeliness,
            uniqueness=uniqueness,
            validity=validity,
        )

    def get_quality_report(self) -> "QualityReport":
        """
        Generate comprehensive quality report.

        Returns:
            QualityReport with aggregate statistics
        """
        # Load all data and assess quality
        from feedback import FeedbackLogger
        from intelligence.quality.report import QualityReport

        logger = FeedbackLogger()

        # Assess outcomes
        outcomes = logger.load_outcomes()
        outcome_qualities = [self.assess_outcome(o) for o in outcomes]

        # Calculate aggregates
        if outcome_qualities:
            avg_completeness = sum(q.completeness for q in outcome_qualities) / len(
                outcome_qualities
            )
            avg_consistency = sum(q.consistency for q in outcome_qualities) / len(outcome_qualities)
            avg_accuracy = sum(q.accuracy for q in outcome_qualities) / len(outcome_qualities)
            avg_timeliness = sum(q.timeliness for q in outcome_qualities) / len(outcome_qualities)
            avg_uniqueness = sum(q.uniqueness for q in outcome_qualities) / len(outcome_qualities)
            avg_validity = sum(q.validity for q in outcome_qualities) / len(outcome_qualities)
        else:
            avg_completeness = 1.0
            avg_consistency = 1.0
            avg_accuracy = 1.0
            avg_timeliness = 1.0
            avg_uniqueness = 1.0
            avg_validity = 1.0

        avg_dimensions = QualityDimensions(
            completeness=avg_completeness,
            consistency=avg_consistency,
            accuracy=avg_accuracy,
            timeliness=avg_timeliness,
            uniqueness=avg_uniqueness,
            validity=avg_validity,
        )

        return QualityReport(
            timestamp=datetime.now().isoformat(),
            total_items_assessed=len(outcome_qualities),
            average_dimensions=avg_dimensions,
            dimension_details={
                "outcomes": {
                    "count": len(outcome_qualities),
                    "avg_quality": avg_dimensions.overall_score(),
                }
            },
        )

    def track_quality(self, item_type: str, quality: QualityDimensions):
        """
        Track quality measurement for trend analysis.

        Args:
            item_type: Type of item assessed (pattern, feedback, outcome, recommendation)
            quality: Quality dimensions measured
        """
        self.quality_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "item_type": item_type,
                "quality": quality.to_dict(),
            }
        )
