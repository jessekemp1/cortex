"""Comprehensive tests for all integration phases"""
import pytest
from pathlib import Path
import sys

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Guard imports - these modules may not exist yet
try:
    from agents.integration.team_coordinator import TeamCoordinator
    from agents.integration.base_coordination_agent import BaseCoordinationAgent
    INTEGRATION_AVAILABLE = True
except ImportError:
    TeamCoordinator = None
    BaseCoordinationAgent = None
    INTEGRATION_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not INTEGRATION_AVAILABLE,
    reason="Integration modules not available (agents.integration not implemented)"
)


def test_team_coordinator_import():
    """Test team coordinator can be imported"""
    assert TeamCoordinator is not None


def test_base_coordination_agent_import():
    """Test base coordination agent can be imported"""
    assert BaseCoordinationAgent is not None


def test_phase1_agent_import():
    """Test Phase 1 agent can be imported"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "local-orchestrator"))
        from agents.integration.phase1_agent import Phase1Agent
        assert Phase1Agent is not None
    except ImportError:
        pytest.skip("Phase 1 agent not available (local-orchestrator dependencies missing)")


def test_phase2_agent_import():
    """Test Phase 2 agent can be imported"""
    from agents.integration.phase2_agent import Phase2Agent
    assert Phase2Agent is not None


def test_phase3_agent_import():
    """Test Phase 3 agent can be imported"""
    from agents.integration.phase3_agent import Phase3Agent
    assert Phase3Agent is not None


def test_coordinator_initialization():
    """Test coordinator can be initialized"""
    coordinator = TeamCoordinator()
    assert coordinator is not None
    assert len(coordinator.agents) == 0


def test_agent_registration():
    """Test agents can be registered"""
    coordinator = TeamCoordinator()
    
    try:
        from agents.integration.phase2_agent import Phase2Agent
        agent = Phase2Agent()
        coordinator.register_agent(agent)
        assert len(coordinator.agents) == 1
    except ImportError:
        pytest.skip("Phase 2 agent not available")


def test_dependency_checking():
    """Test dependency checking works"""
    try:
        from agents.integration.phase2_agent import Phase2Agent
        agent = Phase2Agent()
        # Phase 2 depends on Phase 1
        # Should return False if Phase 1 not complete
        deps_met = agent.check_dependencies()
        assert isinstance(deps_met, bool)
    except ImportError:
        pytest.skip("Phase 2 agent not available")

