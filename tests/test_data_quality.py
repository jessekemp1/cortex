#!/usr/bin/env python3
"""
Tests for Data Quality Framework

Tests all quality dimensions and integration with Cortex data types.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from feedback import FeedbackEntry, OutcomeEntry
from intelligence.memory.pattern_indexer import Pattern
from intelligence.quality.data_quality import DataQualityTracker, QualityDimensions
from intelligence.quality.dimensions import DimensionCheckers
from intelligence.quality.report import QualityReport, generate_markdown_report


class TestDimensionCheckers:
    """Test individual dimension checkers."""

    def test_completeness_all_fields_present(self):
        """Test completeness with all required fields present."""
        data = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }
        required = ["field1", "field2", "field3"]

        score = DimensionCheckers.check_completeness(data, required)
        assert score == 1.0

    def test_completeness_missing_fields(self):
        """Test completeness with missing fields."""
        data = {
            "field1": "value1",
            "field2": None,  # Missing
            "field3": "",  # Empty string
        }
        required = ["field1", "field2", "field3"]

        score = DimensionCheckers.check_completeness(data, required)
        assert score == pytest.approx(1.0 / 3.0)  # Only field1 is complete

    def test_completeness_with_lists_and_dicts(self):
        """Test completeness with complex types."""
        data = {
            "list_field": ["item1", "item2"],
            "dict_field": {"key": "value"},
            "empty_list": [],
            "empty_dict": {},
        }
        required = ["list_field", "dict_field", "empty_list", "empty_dict"]

        score = DimensionCheckers.check_completeness(data, required)
        assert score == pytest.approx(2.0 / 4.0)  # Only non-empty collections count

    def test_consistency_timestamp_order(self):
        """Test consistency with timestamp ordering."""
        data = {
            "created_at": "2026-01-01T10:00:00",
            "timestamp": "2026-01-01T11:00:00",  # Later than created
        }
        rules = [{"type": "timestamp_order", "fields": ["created_at", "timestamp"]}]

        score = DimensionCheckers.check_consistency(data, rules)
        assert score == 1.0

    def test_consistency_timestamp_order_violation(self):
        """Test consistency with invalid timestamp order."""
        data = {
            "created_at": "2026-01-01T11:00:00",
            "timestamp": "2026-01-01T10:00:00",  # Earlier than created (invalid)
        }
        rules = [{"type": "timestamp_order", "fields": ["created_at", "timestamp"]}]

        score = DimensionCheckers.check_consistency(data, rules)
        assert score == 0.0

    def test_consistency_value_range(self):
        """Test consistency with value range validation."""
        data = {"confidence": 0.75}
        rules = [{"type": "value_range", "field": "confidence", "min": 0.0, "max": 1.0}]

        score = DimensionCheckers.check_consistency(data, rules)
        assert score == 1.0

    def test_consistency_value_range_violation(self):
        """Test consistency with out-of-range value."""
        data = {"confidence": 1.5}  # Out of range
        rules = [{"type": "value_range", "field": "confidence", "min": 0.0, "max": 1.0}]

        score = DimensionCheckers.check_consistency(data, rules)
        assert score == 0.0

    def test_accuracy_basic_sanity_checks(self):
        """Test accuracy with basic sanity checks."""
        data = {
            "outcome": "success",
            "followed": True,
            "confidence": 0.8,
            "files_changed": ["file1.py", "file2.py"],
        }

        score = DimensionCheckers.check_accuracy(data)
        assert score == 1.0  # All sanity checks pass

    def test_accuracy_with_known_facts(self):
        """Test accuracy validation against known facts."""
        data = {
            "project": "cortex",
            "commit_hash": "abc123",
            "pattern_type": "fix",
        }
        known_facts = {
            "project": "cortex",
            "commit_hash": "abc123",
        }

        score = DimensionCheckers.check_accuracy(data, known_facts)
        assert score == 1.0

    def test_timeliness_recent_data(self):
        """Test timeliness with recent data."""
        now = datetime.now()
        data = {"timestamp": now.isoformat()}

        score = DimensionCheckers.check_timeliness(data, max_age_days=30)
        assert score >= 0.95  # Very recent should score high

    def test_timeliness_old_data(self):
        """Test timeliness with old data."""
        old_date = datetime.now() - timedelta(days=100)
        data = {"timestamp": old_date.isoformat()}

        score = DimensionCheckers.check_timeliness(data, max_age_days=30)
        assert score < 0.3  # Old data should score low

    def test_timeliness_decay(self):
        """Test timeliness score decay over time."""
        now = datetime.now()

        # Recent
        data_recent = {"timestamp": (now - timedelta(days=5)).isoformat()}
        score_recent = DimensionCheckers.check_timeliness(data_recent, max_age_days=30)

        # Medium age
        data_medium = {"timestamp": (now - timedelta(days=20)).isoformat()}
        score_medium = DimensionCheckers.check_timeliness(data_medium, max_age_days=30)

        # Old
        data_old = {"timestamp": (now - timedelta(days=50)).isoformat()}
        score_old = DimensionCheckers.check_timeliness(data_old, max_age_days=30)

        # Verify decay
        assert score_recent > score_medium > score_old

    def test_uniqueness_unique_data(self):
        """Test uniqueness with unique data."""
        existing_hashes = set()
        data = {"id": "unique_id_1", "title": "Unique Title"}

        score = DimensionCheckers.check_uniqueness(data, existing_hashes, ["id", "title"])
        assert score == 1.0
        assert len(existing_hashes) == 1

    def test_uniqueness_duplicate_data(self):
        """Test uniqueness with duplicate data."""
        existing_hashes = set()
        data1 = {"id": "id_1", "title": "Title"}
        data2 = {"id": "id_1", "title": "Title"}  # Duplicate

        # First entry is unique
        score1 = DimensionCheckers.check_uniqueness(data1, existing_hashes, ["id", "title"])
        assert score1 == 1.0

        # Second entry is duplicate
        score2 = DimensionCheckers.check_uniqueness(data2, existing_hashes, ["id", "title"])
        assert score2 == 0.0

    def test_validity_with_schema(self):
        """Test validity with schema validation."""
        data = {
            "title": "Test Title",
            "confidence": 0.8,
            "followed": True,
        }
        schema = {
            "title": {"type": "str"},
            "confidence": {"type": "float", "min": 0.0, "max": 1.0},
            "followed": {"type": "bool"},
        }

        score = DimensionCheckers.check_validity(data, schema)
        assert score == 1.0

    def test_validity_type_mismatch(self):
        """Test validity with type mismatches."""
        data = {
            "title": 123,  # Should be string
            "confidence": "high",  # Should be float
        }
        schema = {
            "title": {"type": "str"},
            "confidence": {"type": "float"},
        }

        score = DimensionCheckers.check_validity(data, schema)
        assert score == 0.0


class TestDataQualityTracker:
    """Test DataQualityTracker integration."""

    def test_assess_pattern(self):
        """Test quality assessment of a pattern."""
        pattern = Pattern(
            id="test:abc123",
            project="test_project",
            commit_hash="abc123",
            commit_date=datetime.now(),
            title="Fix bug in parser",
            description="Fixed null pointer exception",
            files_changed=["parser.py", "tests/test_parser.py"],
            keywords={"fix", "bug", "parser"},
            pattern_type="fix",
        )

        tracker = DataQualityTracker()
        quality = tracker.assess_pattern(pattern)

        # Verify dimensions
        assert quality.completeness == 1.0  # All required fields present
        assert quality.consistency >= 0.0  # Valid range
        assert quality.accuracy >= 0.0  # Valid range
        assert quality.timeliness >= 0.9  # Recent data
        assert quality.uniqueness == 1.0  # First occurrence
        assert quality.validity == 1.0  # Valid schema

        # Verify overall score
        overall = quality.overall_score()
        assert 0.0 <= overall <= 1.0

    def test_assess_outcome(self):
        """Test quality assessment of an outcome entry."""
        outcome = OutcomeEntry(
            timestamp=datetime.now().isoformat(),
            recommendation_id="rec_001",
            recommendation_title="Implement feature X",
            recommendation_type="feature",
            priority="A",
            confidence=0.85,
            followed=True,
            outcome="success",
            notes="Completed successfully",
            context={"project": "cortex"},
        )

        tracker = DataQualityTracker()
        quality = tracker.assess_outcome(outcome)

        # Verify dimensions
        assert quality.completeness == 1.0  # All required fields
        assert quality.consistency == 1.0  # Confidence in valid range
        assert quality.timeliness >= 0.9  # Recent
        assert quality.uniqueness == 1.0  # First occurrence
        assert quality.validity == 1.0  # Valid schema

    def test_assess_feedback(self):
        """Test quality assessment of a feedback entry."""
        feedback = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            action_id="act_001",
            action_title="Run tests",
            useful=True,
            notes="Tests passed",
            actual_outcome="success",
        )

        tracker = DataQualityTracker()
        quality = tracker.assess_feedback(feedback)

        # Verify dimensions exist
        assert quality.completeness >= 0.0
        assert quality.consistency >= 0.0
        assert quality.accuracy >= 0.0
        assert quality.timeliness >= 0.0
        assert quality.uniqueness >= 0.0
        assert quality.validity >= 0.0

    def test_assess_recommendation(self):
        """Test quality assessment of a recommendation."""
        recommendation = {
            "title": "Add unit tests",
            "rationale": "Improve code coverage",
            "priority": "B",
            "confidence": 0.75,
            "timestamp": datetime.now().isoformat(),
        }

        tracker = DataQualityTracker()
        quality = tracker.assess_recommendation(recommendation)

        # Verify completeness
        assert quality.completeness == 1.0  # All required fields


class TestQualityDimensions:
    """Test QualityDimensions dataclass."""

    def test_overall_score_default_weights(self):
        """Test overall score with default weights."""
        quality = QualityDimensions(
            completeness=1.0,
            consistency=1.0,
            accuracy=1.0,
            timeliness=1.0,
            uniqueness=1.0,
            validity=1.0,
        )

        score = quality.overall_score()
        assert score == 1.0

    def test_overall_score_custom_weights(self):
        """Test overall score with custom weights."""
        quality = QualityDimensions(
            completeness=1.0,
            consistency=0.5,
            accuracy=0.5,
            timeliness=0.5,
            uniqueness=0.5,
            validity=0.5,
        )

        # Custom weights favoring completeness
        weights = {
            "completeness": 0.5,
            "consistency": 0.1,
            "accuracy": 0.1,
            "timeliness": 0.1,
            "uniqueness": 0.1,
            "validity": 0.1,
        }

        score = quality.overall_score(weights)
        assert score == pytest.approx(0.75)  # 0.5*1.0 + 0.5*0.5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        quality = QualityDimensions(
            completeness=0.9,
            consistency=0.8,
            accuracy=0.85,
            timeliness=0.7,
            uniqueness=1.0,
            validity=0.95,
        )

        result = quality.to_dict()

        assert "completeness" in result
        assert "consistency" in result
        assert "accuracy" in result
        assert "timeliness" in result
        assert "uniqueness" in result
        assert "validity" in result
        assert "overall" in result


class TestQualityReport:
    """Test quality report generation."""

    def test_quality_report_creation(self):
        """Test creating a quality report."""
        avg_dims = QualityDimensions(
            completeness=0.9,
            consistency=0.85,
            accuracy=0.88,
            timeliness=0.75,
            uniqueness=0.95,
            validity=0.92,
        )

        report = QualityReport(
            timestamp=datetime.now().isoformat(),
            total_items_assessed=100,
            average_dimensions=avg_dims,
            dimension_details={
                "outcomes": {
                    "count": 100,
                    "avg_quality": 0.875,
                }
            },
        )

        assert report.total_items_assessed == 100
        assert 0.8 <= report.overall_quality() <= 0.9

    def test_markdown_report_generation(self):
        """Test markdown report generation."""
        avg_dims = QualityDimensions(
            completeness=0.85,
            consistency=0.80,
            accuracy=0.90,
            timeliness=0.70,
            uniqueness=0.95,
            validity=0.88,
        )

        report = QualityReport(
            timestamp=datetime.now().isoformat(),
            total_items_assessed=50,
            average_dimensions=avg_dims,
            dimension_details={
                "outcomes": {
                    "count": 50,
                    "avg_quality": 0.85,
                }
            },
        )

        markdown = generate_markdown_report(report)

        # Verify report structure
        assert "# Cortex Data Quality Report" in markdown
        assert "Quality Dimensions" in markdown
        assert "Completeness" in markdown
        assert "Recommendations" in markdown
        assert "50" in markdown  # Total items

    def test_markdown_report_with_trends(self):
        """Test markdown report with trend data."""
        avg_dims = QualityDimensions(
            completeness=0.9,
            consistency=0.85,
            accuracy=0.88,
            timeliness=0.75,
            uniqueness=0.95,
            validity=0.92,
        )

        report = QualityReport(
            timestamp=datetime.now().isoformat(),
            total_items_assessed=100,
            average_dimensions=avg_dims,
            dimension_details={},
            trends={
                "completeness": [0.85, 0.87, 0.90],
                "accuracy": [0.80, 0.84, 0.88],
            },
        )

        markdown = generate_markdown_report(report)

        # Verify trends section
        assert "Trends" in markdown
        assert "↑" in markdown or "→" in markdown  # Trend arrows


class TestIntegrationWithRealData:
    """Integration tests with real Cortex data."""

    def test_quality_report_with_real_outcomes(self, tmp_path):
        """Test quality report generation with real outcome data."""
        # This would require real data from ~/.cortex/outcomes.jsonl
        # For now, we'll test the structure

        tracker = DataQualityTracker()
        report = tracker.get_quality_report()

        assert isinstance(report, QualityReport)
        assert report.total_items_assessed >= 0
        assert 0.0 <= report.overall_quality() <= 1.0

    def test_track_quality_history(self):
        """Test quality history tracking."""
        tracker = DataQualityTracker()

        quality1 = QualityDimensions(
            completeness=0.8,
            consistency=0.85,
            accuracy=0.9,
            timeliness=0.75,
            uniqueness=0.95,
            validity=0.88,
        )

        tracker.track_quality("outcome", quality1)

        assert len(tracker.quality_history) == 1
        assert tracker.quality_history[0]["item_type"] == "outcome"
        assert "timestamp" in tracker.quality_history[0]
