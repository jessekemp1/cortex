#!/usr/bin/env python3
"""
Tests for CortexOrchestrator
"""

import pytest
from pathlib import Path
import sys

# Add converx directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import CortexOrchestrator, StrategistResponse


def test_orchestrator_initialization():
    """Test orchestrator can be initialized."""
    orchestrator = CortexOrchestrator()
    assert orchestrator is not None
    assert orchestrator.root_dir == Path("/Users/jesse.kemp/Dev")


def test_orchestrator_custom_root():
    """Test orchestrator with custom root directory."""
    custom_root = Path("/tmp")
    orchestrator = CortexOrchestrator(root_dir=custom_root)
    assert orchestrator.root_dir == custom_root


def test_get_next_action_basic():
    """Test get_next_action returns StrategistResponse."""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=1)

    assert isinstance(response, StrategistResponse)
    assert "active_projects" in response.current_state
    assert "total_projects" in response.current_state


def test_get_next_action_with_project_filter():
    """Test project filtering."""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(project_filter="vortexv2", limit=1)

    assert isinstance(response, StrategistResponse)
    # If recommendations exist, they should be filtered
    if response.next_action:
        assert any("vortexv2" in proj.lower() for proj in response.next_action.related_projects)


def test_get_next_action_with_context():
    """Test context predictions."""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(include_context=True, limit=1)

    assert isinstance(response, StrategistResponse)
    # Context predictions may or may not be available
    assert isinstance(response.context_predictions, list)


def test_current_state_structure():
    """Test current state has expected structure."""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=0)

    state = response.current_state

    # Check required fields
    assert "active_projects" in state
    assert "recent_projects" in state
    assert "dormant_projects" in state
    assert "total_projects" in state
    assert "priority_a_goals" in state
    assert "priority_b_goals" in state
    assert "goals_pending" in state
    assert "goals_in_progress" in state
    assert "blockers" in state

    # Check types
    assert isinstance(state["active_projects"], int)
    assert isinstance(state["total_projects"], int)
    assert isinstance(state["blockers"], list)


def test_graceful_degradation():
    """Test orchestrator handles missing tools gracefully."""
    # This test verifies that missing tools don't crash the orchestrator
    orchestrator = CortexOrchestrator()
    
    # Should not raise exception even if tools are missing
    try:
        response = orchestrator.get_next_action(limit=0)
        assert isinstance(response, StrategistResponse)
    except Exception as e:
        pytest.fail(f"Orchestrator should handle missing tools gracefully: {e}")

