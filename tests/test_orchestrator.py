#!/usr/bin/env python3
"""
Tests for CortexOrchestrator
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add cortex directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import CortexOrchestrator, StrategistResponse


def _mock_find_repos(self):
    """Return empty list to avoid scanning full monorepo."""
    return []


def _mock_analyze(self, repo_path):
    """Return a minimal ProjectActivity to avoid git subprocess calls."""
    from ai_intelligence import ProjectActivity

    return ProjectActivity(
        name=repo_path.name if hasattr(repo_path, "name") else "mock",
        path=repo_path,
        status="active",
        commits_7d=1,
        commits_30d=5,
        files_changed_7d=2,
        uncommitted_changes=0,
    )


@pytest.fixture(autouse=True)
def _patch_slow_operations():
    """Patch ProjectScanner and other slow operations to avoid monorepo scans.

    Mocks: ProjectScanner (filesystem scan), ProcessMonitor (system calls ~1s),
    PatternMemory (index loading ~2.3s) which together cause 3-4s per test.
    """
    from unittest.mock import MagicMock

    mock_pm = MagicMock()
    mock_pm.alert_generator.generate_alerts.return_value = []

    with (
        patch("ai_intelligence.ProjectScanner.find_git_repos", _mock_find_repos),
        patch("ai_intelligence.ProjectScanner.find_projects", _mock_find_repos),
        patch("ai_intelligence.ProjectScanner.analyze_project", _mock_analyze),
        patch("recommendation_engine.ProcessMonitor", return_value=mock_pm),
        patch(
            "recommendation_engine.RecommendationEngine._enrich_with_patterns",
            lambda self, recs: recs,
        ),
    ):
        yield


def test_orchestrator_initialization():
    """Test orchestrator can be initialized with expected defaults."""
    orchestrator = CortexOrchestrator()
    assert orchestrator.root_dir == Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
    # Verify core attributes exist and have sane values
    response = orchestrator.get_next_action(limit=0)
    assert response.current_state["total_projects"] >= 0
    assert response.current_state["active_projects"] >= 0


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
    # If recommendations exist, they should be filtered (if related_projects available)
    if response.next_action:
        related = getattr(response.next_action, "related_projects", None)
        if related:
            assert any("vortexv2" in proj.lower() for proj in related)
        # If no related_projects, just verify we got a recommendation
        assert hasattr(response.next_action, "title")


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

    # Check values are sane, not just types
    assert state["active_projects"] >= 0
    assert state["total_projects"] >= 0
    assert state["total_projects"] >= state["active_projects"]
    assert isinstance(state["blockers"], list)
    assert state["goals_pending"] >= 0
    assert state["goals_in_progress"] >= 0


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
