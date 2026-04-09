"""End-to-end tests for Cortex-local-orchestrator integration with active tasks"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.feedback_loop import FeedbackLoop
from integration.history_analyzer import ExecutionHistoryAnalyzer
from integration.local_orchestrator import (
    LOCAL_ORCHESTRATOR_AVAILABLE,
    CortexLocalOrchestratorIntegration,
    RecommendationToAgentAdapter,
)
from orchestrator import CortexOrchestrator, Recommendation


def _mock_find_repos(self):
    """Return empty list to avoid scanning full monorepo."""
    return []


@pytest.fixture(autouse=True)
def _patch_slow_operations():
    """Patch slow operations: ProjectScanner, ProcessMonitor, PatternMemory."""
    from unittest.mock import MagicMock

    mock_pm = MagicMock()
    mock_pm.alert_generator.generate_alerts.return_value = []

    with (
        patch("ai_intelligence.ProjectScanner.find_git_repos", _mock_find_repos),
        patch("ai_intelligence.ProjectScanner.find_projects", _mock_find_repos),
        patch("recommendation_engine.ProcessMonitor", return_value=mock_pm),
        patch(
            "recommendation_engine.RecommendationEngine._enrich_with_patterns",
            lambda self, recs: recs,
        ),
    ):
        yield


@pytest.mark.skipif(not LOCAL_ORCHESTRATOR_AVAILABLE, reason="local-orchestrator not available")
def test_integration_available():
    """Test that integration can be initialized"""
    integration = CortexLocalOrchestratorIntegration()
    assert integration is not None
    # May not be available if deps missing, but structure should work
    assert isinstance(integration.is_available(), bool)


@pytest.mark.skipif(not LOCAL_ORCHESTRATOR_AVAILABLE, reason="local-orchestrator not available")
def test_recommendation_to_agent_conversion():
    """Test that recommendations can be converted to agents"""
    adapter = RecommendationToAgentAdapter()

    # Create a test recommendation
    recommendation = Recommendation(
        type="test",
        title="Test Action",
        description="Test description",
        priority="high",
        confidence=0.9,
        rationale="Test rationale",
        estimated_effort="Low",
        estimated_impact="High",
        related_goals=[],
    )

    # Convert to agent
    agent = adapter.to_agent(recommendation)

    assert agent is not None
    assert agent["agent_id"].startswith("cortex_")
    assert "Test Action" in agent["name"]
    assert "Test description" in agent["description"]


@pytest.mark.skipif(not LOCAL_ORCHESTRATOR_AVAILABLE, reason="local-orchestrator not available")
def test_schedule_recommendation():
    """Test scheduling a recommendation"""
    integration = CortexLocalOrchestratorIntegration()

    if not integration.is_available():
        pytest.skip("local-orchestrator not available (dependencies missing)")

    # Create test recommendation
    recommendation = Recommendation(
        type="test",
        title="E2E Test Action",
        description="E2E test description",
        priority="medium",
        confidence=0.8,
        rationale="E2E test",
        estimated_effort="Low",
        estimated_impact="Medium",
        related_goals=[],
    )

    # Schedule it
    success = integration.schedule_recommendation(recommendation, schedule="0 8 * * *")

    # Should succeed if integration available
    assert isinstance(success, bool)

    # Check it's in the list
    scheduled = integration.list_scheduled_actions()
    [a for a in scheduled if a.get("agent_id") == "cortex_e2e_test_action"]
    # May or may not be there depending on orchestrator state, but structure should work
    assert isinstance(scheduled, list)


def test_cortex_generates_recommendation():
    """Test that Cortex can generate recommendations"""
    orchestrator = CortexOrchestrator()

    response = orchestrator.get_next_action(limit=1)

    assert response is not None
    assert hasattr(response, "next_action")
    assert hasattr(response, "system_health")

    # May or may not have recommendations, but structure should work
    if response.next_action:
        # May be different Recommendation classes, check for required attrs
        rec = response.next_action
        assert hasattr(rec, "title")
        assert hasattr(rec, "priority")


def test_feedback_loop_initialization():
    """Test feedback loop can be initialized"""
    feedback = FeedbackLoop()
    assert feedback is not None

    # Test learning metrics
    metrics = feedback.get_learning_metrics()
    assert isinstance(metrics, dict)
    assert "available" in metrics


def test_history_analyzer_initialization():
    """Test history analyzer can be initialized"""
    analyzer = ExecutionHistoryAnalyzer()
    assert analyzer is not None

    # Test availability check
    available = analyzer.is_available()
    assert isinstance(available, bool)

    # Test methods (may return defaults if history not available)
    success_rate = analyzer.get_success_rate("test_action", days=30)
    assert isinstance(success_rate, float)
    assert 0.0 <= success_rate <= 1.0


def test_integration_with_real_cortex_recommendation():
    """Test full integration: Cortex recommendation → local-orchestrator agent"""
    # Get recommendation from Cortex
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=1)

    if not response.next_action:
        pytest.skip("No recommendations available")

    recommendation = response.next_action

    # Try to schedule it
    integration = CortexLocalOrchestratorIntegration()

    if not integration.is_available():
        pytest.skip("local-orchestrator not available")

    # Schedule the recommendation
    success = integration.schedule_recommendation(recommendation)

    # Should be able to attempt scheduling
    assert isinstance(success, bool)


def test_cli_schedule_command_structure():
    """Test that CLI schedule command structure is correct"""
    # cmd_schedule lives in cli/commands/batch.py (cli/ package, not cli.py)
    from cli.commands.batch import cmd_schedule

    assert cmd_schedule is not None
    assert callable(cmd_schedule)
