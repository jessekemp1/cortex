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
    """Test that adapter can be imported and has expected interface."""
    assert callable(RecommendationToAgentAdapter)
    assert callable(CortexLocalOrchestratorIntegration)
    assert callable(getattr(CortexLocalOrchestratorIntegration, "is_available", None))


def test_integration_initialization():
    """Test integration can be initialized and reports availability."""
    if not LOCAL_ORCHESTRATOR_AVAILABLE:
        pytest.skip("local-orchestrator not available")

    integration = CortexLocalOrchestratorIntegration()
    assert integration.is_available() is True


def test_integration_availability_check():
    """Test availability reflects LOCAL_ORCHESTRATOR_AVAILABLE flag."""
    integration = CortexLocalOrchestratorIntegration()
    available = integration.is_available()
    assert isinstance(available, bool)
    assert available == LOCAL_ORCHESTRATOR_AVAILABLE
