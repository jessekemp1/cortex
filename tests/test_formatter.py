#!/usr/bin/env python3
"""
Tests for CortexFormatter
"""

import pytest
import json
from pathlib import Path
import sys

# Add converx directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from formatter import CortexFormatter
from orchestrator import StrategistResponse, SystemHealth


def test_format_response_text():
    """Test text formatting."""
    # Create minimal response
    response = StrategistResponse(
        current_state={
            "active_projects": 1,
            "total_projects": 3,
            "priority_a_goals": 2,
            "goals_pending": 1,
            "goals_in_progress": 0,
            "blockers": []
        },
        next_action=None,
        alternative_actions=[],
        context_predictions=[],
        system_health=SystemHealth(
            project_scanner=True,
            goal_parser=True,
            recommendation_engine=True,
            context_intelligence=True
        )
    )

    formatter = CortexFormatter()
    output = formatter.format_response(response, json_output=False)

    assert isinstance(output, str)
    assert "CORTEX" in output
    assert "CURRENT STATE" in output


def test_format_response_json():
    """Test JSON formatting."""
    response = StrategistResponse(
        current_state={
            "active_projects": 1,
            "total_projects": 3,
            "priority_a_goals": 2,
            "goals_pending": 1,
            "goals_in_progress": 0,
            "blockers": []
        },
        next_action=None,
        alternative_actions=[],
        context_predictions=[],
        system_health=SystemHealth(
            project_scanner=True,
            goal_parser=True,
            recommendation_engine=True,
            context_intelligence=True
        )
    )

    formatter = CortexFormatter()
    output = formatter.format_response(response, json_output=True)

    # Should be valid JSON
    data = json.loads(output)
    assert "current_state" in data
    assert "next_action" in data
    assert "alternative_actions" in data
    assert "context_predictions" in data


def test_format_recommendation():
    """Test recommendation formatting."""
    # Create a mock recommendation
    try:
        from recommendation_engine import Recommendation
    except ImportError:
        pytest.skip("recommendation_engine not available")

    rec = Recommendation(
        id="test_1",
        type="next_action",
        priority="high",
        title="Test Action",
        description="Test description",
        rationale="Test rationale",
        estimated_effort="1 hour",
        estimated_impact="high",
        confidence=0.9,
        related_projects=["test-project"],
        related_goals=["test-goal"]
    )

    formatter = CortexFormatter()
    output = formatter._format_recommendation(rec, detailed=True)

    assert isinstance(output, str)
    assert "Test Action" in output
    assert "high" in output.lower() or "HIGH" in output


def test_format_empty_state():
    """Test formatting with empty state."""
    response = StrategistResponse(
        current_state={
            "active_projects": 0,
            "total_projects": 0,
            "priority_a_goals": 0,
            "goals_pending": 0,
            "goals_in_progress": 0,
            "blockers": []
        },
        next_action=None,
        alternative_actions=[],
        context_predictions=[],
        system_health=SystemHealth(
            project_scanner=False,
            goal_parser=False,
            recommendation_engine=False,
            context_intelligence=False
        )
    )

    formatter = CortexFormatter()
    output = formatter.format_response(response, json_output=False)

    assert isinstance(output, str)
    # Should still produce valid output
    assert "CORTEX" in output

