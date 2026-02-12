#!/usr/bin/env python3
"""
Tests for Rule Tracking Integration

Tests the rule adherence tracking system:
1. CortexBridge.log_rule_event()
2. CortexBridge.get_rule_correlations()
3. LearningSystem.get_rule_outcome_patterns()
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLogRuleEvent:
    """Tests for CortexBridge.log_rule_event()"""

    def test_log_rule_event_creates_file(self, tmp_path):
        """Test that log_rule_event creates the events file."""
        from bridge import CortexBridge

        # Patch the home directory to use temp path
        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            result = bridge.log_rule_event(
                rule_name="read_before_edit",
                event_type="violation",
                context={"file": "test.py", "project": "test_project"},
            )

            assert result["success"] is True
            assert "event_id" in result
            assert result["rule_name"] == "read_before_edit"
            assert result["event_type"] == "violation"

            # Check file was created
            events_file = tmp_path / ".cortex" / "rule_events.jsonl"
            assert events_file.exists()

            # Check content
            with open(events_file) as f:
                event = json.loads(f.readline())
                assert event["rule_name"] == "read_before_edit"
                assert event["event_type"] == "violation"
                assert event["context"]["file"] == "test.py"

    def test_log_rule_event_appends(self, tmp_path):
        """Test that multiple events are appended to the file."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            # Log multiple events
            bridge.log_rule_event("read_before_edit", "violation")
            bridge.log_rule_event("file_references", "warning")
            bridge.log_rule_event("read_before_edit", "adherence")

            # Check all events are in file
            events_file = tmp_path / ".cortex" / "rule_events.jsonl"
            with open(events_file) as f:
                lines = f.readlines()
                assert len(lines) == 3

    def test_log_rule_event_with_empty_context(self, tmp_path):
        """Test logging event without context."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            result = bridge.log_rule_event(
                rule_name="unnecessary_questions",
                event_type="warning",
            )

            assert result["success"] is True


class TestGetRuleCorrelations:
    """Tests for CortexBridge.get_rule_correlations()"""

    def test_get_rule_correlations_empty(self, tmp_path):
        """Test correlations when no events exist."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            result = bridge.get_rule_correlations()

            assert result["success"] is True
            assert result["total_events"] == 0
            assert result["correlations"] == {}

    def test_get_rule_correlations_with_events(self, tmp_path):
        """Test correlations with logged events."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            # Log some events
            bridge.log_rule_event("read_before_edit", "violation")
            bridge.log_rule_event("read_before_edit", "violation")
            bridge.log_rule_event("read_before_edit", "adherence")
            bridge.log_rule_event("file_references", "warning")

            result = bridge.get_rule_correlations()

            assert result["success"] is True
            assert result["total_events"] == 4
            assert "read_before_edit" in result["correlations"]
            assert "file_references" in result["correlations"]

            # Check read_before_edit stats
            rbe = result["correlations"]["read_before_edit"]
            assert rbe["violations"] == 2
            assert rbe["adherences"] == 1
            assert rbe["adherence_rate"] == pytest.approx(0.333, rel=0.01)

    def test_get_rule_correlations_filter_by_rule(self, tmp_path):
        """Test filtering correlations by rule name."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            bridge.log_rule_event("read_before_edit", "violation")
            bridge.log_rule_event("file_references", "warning")

            result = bridge.get_rule_correlations(rule_name="read_before_edit")

            assert result["success"] is True
            assert result["total_events"] == 1  # Only read_before_edit events


class TestGetRuleOutcomePatterns:
    """Tests for LearningSystem.get_rule_outcome_patterns()"""

    def test_get_rule_outcome_patterns_no_data(self, tmp_path):
        """Test patterns when no data exists."""
        from learning import LearningSystem

        with patch.object(Path, "home", return_value=tmp_path):
            # Create empty outcomes file
            outcomes_file = tmp_path / ".cortex" / "outcomes.jsonl"
            outcomes_file.parent.mkdir(parents=True, exist_ok=True)
            outcomes_file.touch()

            # Mock feedback logger
            learning = LearningSystem(outcomes_file=outcomes_file)
            learning.feedback_logger = MagicMock()
            learning.feedback_logger.load_outcomes.return_value = []

            result = learning.get_rule_outcome_patterns()

            assert "rules" in result
            assert "insights" in result
            assert result["total_rule_events"] == 0

    def test_get_rule_outcome_patterns_with_data(self, tmp_path):
        """Test patterns with rule events and outcomes."""
        from learning import LearningSystem

        with patch.object(Path, "home", return_value=tmp_path):
            # Create rule events
            events_file = tmp_path / ".cortex" / "rule_events.jsonl"
            events_file.parent.mkdir(parents=True, exist_ok=True)

            today = datetime.now().strftime("%Y-%m-%d")
            events = [
                {
                    "timestamp": f"{today}T10:00:00",
                    "rule_name": "read_before_edit",
                    "event_type": "violation",
                },
                {
                    "timestamp": f"{today}T11:00:00",
                    "rule_name": "read_before_edit",
                    "event_type": "adherence",
                },
            ]

            with open(events_file, "w") as f:
                for event in events:
                    f.write(json.dumps(event) + "\n")

            # Create outcomes file
            outcomes_file = tmp_path / ".cortex" / "outcomes.jsonl"
            outcomes_file.touch()

            # Mock feedback logger with outcomes
            learning = LearningSystem(outcomes_file=outcomes_file)
            mock_outcome = MagicMock()
            mock_outcome.timestamp = f"{today}T12:00:00"
            mock_outcome.outcome = "success"
            mock_outcome.followed = True

            learning.feedback_logger = MagicMock()
            learning.feedback_logger.load_outcomes.return_value = [mock_outcome]

            result = learning.get_rule_outcome_patterns()

            assert result["total_rule_events"] == 2
            assert "read_before_edit" in result["rules"]


class TestRuleAdherenceHook:
    """Tests for the rule adherence hook."""

    def test_hook_detects_blind_edit(self, tmp_path):
        """Test that hook detects edit without read."""
        # Import hook module
        hook_path = Path(__file__).parent.parent.parent / ".claude" / "hooks"
        sys.path.insert(0, str(hook_path))

        # Import after adding to path
        import rule_adherence_hook

        # Patch the module-level constants
        with (
            patch.object(rule_adherence_hook, "CORTEX_DATA", tmp_path / ".cortex"),
            patch.object(
                rule_adherence_hook, "RULE_EVENTS_FILE", tmp_path / ".cortex" / "rule_events.jsonl"
            ),
            patch.object(
                rule_adherence_hook,
                "SESSION_STATE_FILE",
                tmp_path / ".cortex" / "session_read_files.json",
            ),
        ):

            # Create cortex dir
            (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)

            # Simulate edit without read (no prior session state)
            warnings = rule_adherence_hook.process_tool_completion(
                tool_name="Edit",
                tool_input={"file_path": "/test/file.py"},
                tool_output="",
            )

            assert len(warnings) == 1
            assert "Edit without prior Read" in warnings[0]

    def test_hook_allows_edit_after_read(self, tmp_path):
        """Test that hook allows edit after read."""
        hook_path = Path(__file__).parent.parent.parent / ".claude" / "hooks"
        sys.path.insert(0, str(hook_path))

        # Import after adding to path
        import rule_adherence_hook

        # Patch the module-level constants
        with (
            patch.object(rule_adherence_hook, "CORTEX_DATA", tmp_path / ".cortex"),
            patch.object(
                rule_adherence_hook, "RULE_EVENTS_FILE", tmp_path / ".cortex" / "rule_events.jsonl"
            ),
            patch.object(
                rule_adherence_hook,
                "SESSION_STATE_FILE",
                tmp_path / ".cortex" / "session_read_files.json",
            ),
        ):

            (tmp_path / ".cortex").mkdir(parents=True, exist_ok=True)

            # First read the file (will save to session state file)
            rule_adherence_hook.process_tool_completion(
                tool_name="Read",
                tool_input={"file_path": "/test/file.py"},
                tool_output="file contents",
            )

            # Then edit should not warn (will load from session state file)
            warnings = rule_adherence_hook.process_tool_completion(
                tool_name="Edit",
                tool_input={"file_path": "/test/file.py"},
                tool_output="",
            )

            assert len(warnings) == 0


# Integration test
class TestRuleTrackingIntegration:
    """Integration tests for the full rule tracking flow."""

    def test_full_flow(self, tmp_path):
        """Test the full flow: log event -> get correlations."""
        from bridge import CortexBridge

        with patch.object(Path, "home", return_value=tmp_path):
            bridge = CortexBridge()

            # Log several events
            for _ in range(5):
                bridge.log_rule_event("read_before_edit", "violation", {"project": "test"})
            for _ in range(10):
                bridge.log_rule_event("read_before_edit", "adherence", {"project": "test"})
            for _ in range(3):
                bridge.log_rule_event("file_references", "warning", {"project": "test"})

            # Get correlations
            correlations = bridge.get_rule_correlations()

            assert correlations["success"]
            assert correlations["total_events"] == 18

            rbe = correlations["correlations"]["read_before_edit"]
            assert rbe["violations"] == 5
            assert rbe["adherences"] == 10
            # Adherence rate = 10 / (5 + 10) = 0.667
            assert rbe["adherence_rate"] == pytest.approx(0.667, rel=0.01)
