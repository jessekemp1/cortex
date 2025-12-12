"""Tests for Cortex-local-orchestrator integration"""

import sys
from pathlib import Path

import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.local_orchestrator import (
    LOCAL_ORCHESTRATOR_AVAILABLE,
    CortexLocalOrchestratorIntegration,
    RecommendationToAgentAdapter,
)


def test_adapter_import():
    """Test that adapter can be imported"""
    assert RecommendationToAgentAdapter is not None
    assert CortexLocalOrchestratorIntegration is not None


def test_integration_initialization():
    """Test integration can be initialized"""
    if not LOCAL_ORCHESTRATOR_AVAILABLE:
        pytest.skip("local-orchestrator not available")

    integration = CortexLocalOrchestratorIntegration()
    # Should not raise exception
    assert integration is not None


def test_integration_availability_check():
    """Test availability check"""
    integration = CortexLocalOrchestratorIntegration()
    # Should return boolean
    assert isinstance(integration.is_available(), bool)
