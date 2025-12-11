#!/usr/bin/env python3
"""
Tests for System Health (Golden Spec: Dependency Transparency)
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import SystemHealth, ConverxOrchestrator


def test_system_health_all_active():
    """Test system health when all integrations are active."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=True,
        recommendation_engine=True,
        context_intelligence=True
    )
    
    assert health.all_active == True
    assert health.active_count == 4


def test_system_health_partial():
    """Test system health with partial integrations."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=False,
        recommendation_engine=True,
        context_intelligence=False
    )
    
    assert health.all_active == False
    assert health.active_count == 2


def test_system_health_to_dict():
    """Test system health to_dict conversion."""
    health = SystemHealth(
        project_scanner=True,
        goal_parser=True,
        recommendation_engine=False,
        context_intelligence=False
    )
    
    health_dict = health.to_dict()
    
    assert health_dict["project_scanner"] == True
    assert health_dict["goal_parser"] == True
    assert health_dict["recommendation_engine"] == False
    assert health_dict["context_intelligence"] == False
    assert health_dict["all_active"] == False
    assert health_dict["active_count"] == 2
    assert health_dict["total_integrations"] == 4


def test_orchestrator_includes_health():
    """Test orchestrator includes system health in response."""
    orchestrator = ConverxOrchestrator()
    response = orchestrator.get_next_action(limit=0)
    
    assert hasattr(response, "system_health")
    assert isinstance(response.system_health, SystemHealth)
    assert response.system_health.active_count >= 0
    assert response.system_health.active_count <= 4

