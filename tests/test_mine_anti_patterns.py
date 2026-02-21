"""Tests for anti-pattern mining script.

mine_anti_patterns.py is an optional user-installed script, not bundled with Cortex.
Point CORTEX_ANTI_PATTERNS_SCRIPT to your copy to enable these tests.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Locate the script via env var or skip the entire module
_script_path = os.environ.get("CORTEX_ANTI_PATTERNS_SCRIPT")
if _script_path:
    sys.path.insert(0, str(Path(_script_path).parent))
    try:
        from mine_anti_patterns import (
            analyze_failed_outcomes,
            analyze_rule_violations,
            correlate_violations_with_outcomes,
            extract_anti_patterns,
            format_anti_pattern_entry,
            load_jsonl,
        )
    except ImportError:
        pytest.skip("mine_anti_patterns.py not importable — set CORTEX_ANTI_PATTERNS_SCRIPT", allow_module_level=True)
else:
    pytest.skip("CORTEX_ANTI_PATTERNS_SCRIPT not set — skipping anti-pattern mining tests", allow_module_level=True)


class TestLoadJsonl:
    """Tests for load_jsonl function."""

    def test_load_empty_file(self, tmp_path):
        """Test loading empty file returns empty list."""
        f = tmp_path / "empty.jsonl"
        f.touch()
        result = load_jsonl(f, 30)
        assert result == []

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading nonexistent file returns empty list."""
        f = tmp_path / "nonexistent.jsonl"
        result = load_jsonl(f, 30)
        assert result == []

    def test_load_filters_by_date(self, tmp_path):
        """Test that entries outside date range are filtered."""
        f = tmp_path / "test.jsonl"
        now = datetime.now()
        old = now - timedelta(days=60)
        recent = now - timedelta(days=5)

        entries = [
            {"timestamp": old.isoformat(), "value": "old"},
            {"timestamp": recent.isoformat(), "value": "recent"},
        ]
        f.write_text("\n".join(json.dumps(e) for e in entries))

        result = load_jsonl(f, 30)
        assert len(result) == 1
        assert result[0]["value"] == "recent"


class TestAnalyzeFailedOutcomes:
    """Tests for analyze_failed_outcomes function."""

    def test_empty_outcomes(self):
        """Test with no outcomes."""
        result = analyze_failed_outcomes([])
        assert result["total"] == 0
        assert result["failed"] == 0

    def test_counts_outcomes_correctly(self):
        """Test outcome counting."""
        outcomes = [
            {"outcome": "success", "recommendation_type": "blocker"},
            {"outcome": "success", "recommendation_type": "blocker"},
            {"outcome": "failed", "recommendation_type": "optimization"},
            {"outcome": "partial", "recommendation_type": "goal"},
        ]
        result = analyze_failed_outcomes(outcomes)
        assert result["total"] == 4
        assert result["success"] == 2
        assert result["failed"] == 1
        assert result["partial"] == 1

    def test_tracks_high_confidence_failures(self):
        """Test high confidence failure detection."""
        outcomes = [
            {"outcome": "failed", "confidence": 0.9, "recommendation_type": "test"},
            {"outcome": "failed", "confidence": 0.3, "recommendation_type": "test"},
        ]
        result = analyze_failed_outcomes(outcomes)
        assert len(result["high_confidence_failures"]) == 1
        assert result["high_confidence_failures"][0]["confidence"] == 0.9


class TestAnalyzeRuleViolations:
    """Tests for analyze_rule_violations function."""

    def test_empty_events(self):
        """Test with no events."""
        result = analyze_rule_violations([])
        assert result["total_events"] == 0
        assert result["violations"] == 0

    def test_counts_violations_by_rule(self):
        """Test violation counting by rule."""
        events = [
            {"event_type": "violation", "rule_name": "read_before_edit"},
            {"event_type": "violation", "rule_name": "read_before_edit"},
            {"event_type": "violation", "rule_name": "file_references"},
            {"event_type": "warning", "rule_name": "read_before_edit"},
        ]
        result = analyze_rule_violations(events)
        assert result["violations"] == 3
        assert result["warnings"] == 1
        assert result["by_rule"]["read_before_edit"] == 2
        assert result["by_rule"]["file_references"] == 1


class TestExtractAntiPatterns:
    """Tests for extract_anti_patterns function."""

    def test_extracts_high_failure_rate_patterns(self):
        """Test extraction of high failure rate patterns."""
        outcome_analysis = {
            "type_stats": {
                "optimization": {"success": 1, "partial": 0, "failed": 3},
            },
            "high_confidence_failures": [],
        }
        rule_analysis = {"by_rule": {}}

        patterns = extract_anti_patterns(outcome_analysis, rule_analysis, [])
        assert len(patterns) >= 1
        assert any("optimization" in p["name"].lower() for p in patterns)

    def test_extracts_recurring_violations(self):
        """Test extraction of recurring rule violations."""
        outcome_analysis = {
            "type_stats": {},
            "high_confidence_failures": [],
        }
        rule_analysis = {
            "by_rule": {"read_before_edit": 5},
        }

        patterns = extract_anti_patterns(outcome_analysis, rule_analysis, [])
        assert len(patterns) >= 1
        assert any("read" in p["name"].lower() for p in patterns)

    def test_no_patterns_for_low_counts(self):
        """Test no patterns extracted for low violation counts."""
        outcome_analysis = {
            "type_stats": {
                "optimization": {"success": 10, "partial": 0, "failed": 1},
            },
            "high_confidence_failures": [],
        }
        rule_analysis = {
            "by_rule": {"read_before_edit": 1},
        }

        patterns = extract_anti_patterns(outcome_analysis, rule_analysis, [])
        # Should not extract patterns for low counts
        assert not any("read" in p["name"].lower() for p in patterns)


class TestFormatAntiPatternEntry:
    """Tests for format_anti_pattern_entry function."""

    def test_formats_correctly(self):
        """Test markdown formatting."""
        pattern = {
            "name": "Test Pattern",
            "date": "2025-01-15",
            "pattern": "Do not do X",
            "consequence": "Bad things happen",
            "prevention": "Do Y instead",
        }
        result = format_anti_pattern_entry(pattern)
        assert "### Test Pattern" in result
        assert "2025-01-15" in result
        assert "Do not do X" in result
        assert "Bad things happen" in result
        assert "Do Y instead" in result


class TestCorrelateViolationsWithOutcomes:
    """Tests for correlate_violations_with_outcomes function."""

    def test_empty_inputs(self):
        """Test with empty inputs."""
        result = correlate_violations_with_outcomes([], [])
        assert result == []

    def test_finds_correlations_on_same_day(self):
        """Test finding correlations on the same day."""
        date = "2025-01-15"
        rule_events = [
            {
                "event_type": "violation",
                "rule_name": "test",
                "timestamp": f"{date}T10:00:00",
            },
        ]
        outcomes = [
            {
                "outcome": "failed",
                "recommendation_title": "Task",
                "timestamp": f"{date}T12:00:00",
            },
        ]
        result = correlate_violations_with_outcomes(rule_events, outcomes)
        assert len(result) == 1
        assert result[0]["date"] == date
