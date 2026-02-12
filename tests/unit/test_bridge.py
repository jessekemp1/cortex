"""Unit tests for Cortex Bridge API.

Tests the CortexBridge class which provides a unified interface for AI agents
to interact with the Cortex system.
"""

import json
import tempfile
from pathlib import Path


class TestCortexBridgeInitialization:
    """Test CortexBridge initialization and component availability."""

    def test_bridge_initializes_with_default_root(self):
        """Bridge should initialize with default root directory."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        assert bridge.root_dir == Path("/Users/jesse.kemp/Dev")

    def test_bridge_initializes_with_custom_root(self):
        """Bridge should accept custom root directory."""
        from cortex.bridge import CortexBridge

        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = CortexBridge(root_dir=tmpdir)
            assert bridge.root_dir == Path(tmpdir)

    def test_bridge_tracks_v2_availability(self):
        """Bridge should track V2 Prime component availability."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        # v2_available should be a boolean
        assert isinstance(bridge.v2_available, bool)

    def test_get_v2_status_returns_component_info(self):
        """get_v2_status should return status of all V2 components."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        status = bridge.get_v2_status()

        assert "v2_available" in status
        assert "absorber" in status
        assert "synthesis" in status
        assert "broker" in status
        assert "iap" in status


class TestCortexBridgeContextMethods:
    """Test context retrieval methods."""

    def test_get_context_returns_list(self):
        """get_context should return a list of context items."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_context("test query", limit=3)

        assert isinstance(result, list)

    def test_get_context_handles_missing_intel(self):
        """get_context should handle missing ContextIntelligence gracefully.

        With AI Engineering improvements, get_context now has multiple sources:
        TieredMemory, HybridRetriever, and ContextIntelligence. Disabling just
        ContextIntelligence should still return results from other sources.
        """
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.context_intel = None  # Simulate missing component

        result = bridge.get_context("test query")

        # Should return a list (may have results from HybridRetriever or TieredMemory)
        assert isinstance(result, list)
        # If HybridRetriever/TieredMemory are available, we get results; otherwise empty or error
        # The key is it handles gracefully without raising exceptions

    def test_get_portfolio_context_returns_dict(self):
        """get_portfolio_context should return project context as dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_portfolio_context("cortex")

        assert isinstance(result, dict)

    def test_get_portfolio_context_handles_missing_portfolio(self):
        """get_portfolio_context should handle missing PortfolioMemory."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.portfolio = None

        result = bridge.get_portfolio_context("test_project")

        assert "error" in result


class TestCortexBridgeRecommendations:
    """Test recommendation injection methods."""

    def test_inject_recommendation_creates_file(self):
        """inject_recommendation should create external_recommendations.json."""
        from cortex.bridge import CortexBridge

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cortex subdirectory
            cortex_dir = Path(tmpdir) / "cortex"
            cortex_dir.mkdir()

            bridge = CortexBridge(root_dir=tmpdir)

            result = bridge.inject_recommendation(
                title="Test Recommendation",
                rationale="Test rationale",
                priority="high",
            )

            assert result is True

            # Check file was created
            rec_file = cortex_dir / "external_recommendations.json"
            assert rec_file.exists()

            # Verify content
            data = json.loads(rec_file.read_text())
            assert isinstance(data, list)
            assert len(data) >= 1
            assert data[-1]["title"] == "Test Recommendation"
            assert data[-1]["priority"] == "high"

    def test_inject_recommendation_appends_to_existing(self):
        """inject_recommendation should append to existing recommendations."""
        from cortex.bridge import CortexBridge

        with tempfile.TemporaryDirectory() as tmpdir:
            cortex_dir = Path(tmpdir) / "cortex"
            cortex_dir.mkdir()

            # Create existing recommendations file
            rec_file = cortex_dir / "external_recommendations.json"
            existing = [{"title": "Existing", "id": "existing_1"}]
            rec_file.write_text(json.dumps(existing))

            bridge = CortexBridge(root_dir=tmpdir)

            result = bridge.inject_recommendation(
                title="New Recommendation",
                rationale="New rationale",
            )

            assert result is True

            data = json.loads(rec_file.read_text())
            assert len(data) == 2
            assert data[0]["title"] == "Existing"
            assert data[1]["title"] == "New Recommendation"


class TestCortexBridgePatterns:
    """Test pattern and lesson retrieval methods."""

    def test_get_patterns_returns_list(self):
        """get_patterns should return list of patterns."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_patterns()

        assert isinstance(result, list)

    def test_get_patterns_handles_missing_portfolio(self):
        """get_patterns should handle missing portfolio gracefully."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.portfolio = None

        result = bridge.get_patterns()

        assert isinstance(result, list)
        assert "error" in result[0]

    def test_get_lessons_returns_list(self):
        """get_lessons should return list of lessons."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_lessons()

        assert isinstance(result, list)

    def test_get_portfolio_stats_returns_dict(self):
        """get_portfolio_stats should return statistics dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_portfolio_stats()

        assert isinstance(result, dict)


class TestCortexBridgeHealthMethods:
    """Test health monitoring methods."""

    def test_get_project_health_returns_dict(self):
        """get_project_health should return health info as dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_project_health("cortex")

        assert isinstance(result, dict)

    def test_get_portfolio_health_summary_returns_dict(self):
        """get_portfolio_health_summary should return summary dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_portfolio_health_summary()

        assert isinstance(result, dict)


class TestCortexBridgeGraphMethods:
    """Test V2 Prime graph methods."""

    def test_query_graph_returns_list(self):
        """query_graph should return list of nodes."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.query_graph("goal")

        assert isinstance(result, list)

    def test_query_graph_handles_missing_synthesis(self):
        """query_graph should handle missing synthesis core."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.synthesis = None

        result = bridge.query_graph("goal")

        assert isinstance(result, list)
        assert "error" in result[0]

    def test_get_graph_stats_returns_dict(self):
        """get_graph_stats should return statistics dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_graph_stats()

        assert isinstance(result, dict)


class TestCortexBridgeInterventions:
    """Test intervention methods."""

    def test_get_pending_interventions_returns_list(self):
        """get_pending_interventions should return list."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.get_pending_interventions()

        assert isinstance(result, list)

    def test_acknowledge_intervention_returns_dict(self):
        """acknowledge_intervention should return result dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.acknowledge_intervention("test_id")

        assert isinstance(result, dict)

    def test_suppress_intervention_returns_dict(self):
        """suppress_intervention should return result dict."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        result = bridge.suppress_intervention("test_id", hours=24)

        assert isinstance(result, dict)


class TestCortexBridgeTriggerAction:
    """Test action triggering methods."""

    def test_trigger_action_handles_missing_orchestrator(self):
        """trigger_action should handle missing orchestrator gracefully."""
        from cortex.bridge import CortexBridge

        bridge = CortexBridge()
        bridge.orchestrator = None

        result = bridge.trigger_action("test_agent", {"key": "value"})

        assert result["success"] is False
        assert "error" in result
