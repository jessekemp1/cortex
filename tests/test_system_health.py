#!/usr/bin/env python3
"""
Tests for System Health (Golden Spec: Dependency Transparency)
"""

import sys
from pathlib import Path

# Add cortex directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import CortexOrchestrator, SystemHealth


def test_system_health_all_active():
    """Test system health when all integrations are active."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=True,
        recommendation_engine=True,
        context_intelligence=True,
    )

    assert health.all_active
    assert health.active_count == 4


def test_system_health_partial():
    """Test system health with partial integrations."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=False,
        recommendation_engine=True,
        context_intelligence=False,
    )

    assert not health.all_active
    assert health.active_count == 2


def test_system_health_to_dict():
    """Test system health to_dict conversion."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=True,
        recommendation_engine=False,
        context_intelligence=False,
    )

    health_dict = health.to_dict()

    assert health_dict["project_scanner"]
    assert health_dict["goal_parser"]
    assert not health_dict["recommendation_engine"]
    assert not health_dict["context_intelligence"]
    assert not health_dict["all_active"]
    assert health_dict["active_count"] == 2
    assert health_dict["total_integrations"] == 4


def test_orchestrator_includes_health():
    """Test orchestrator includes system health in response."""
    from unittest.mock import MagicMock, patch

    def _mock_find_repos(self):
        return []

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
        orchestrator = CortexOrchestrator()
        response = orchestrator.get_next_action(limit=0)

    assert hasattr(response, "system_health")
    assert isinstance(response.system_health, SystemHealth)
    assert response.system_health.active_count >= 0
    assert response.system_health.active_count <= 4
