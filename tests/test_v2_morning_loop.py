"""Tests for V2 Morning Loop — overnight lessons + V2ReasoningLayer + get_interventions."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch



class TestGetOvernightV2Lessons:
    """Tests for morning_processor.get_overnight_v2_lessons()."""

    def test_empty_graph(self):
        """Returns empty list when graph has no LESSON nodes."""
        mock_graph = MagicMock()
        mock_graph.get_nodes_by_type.return_value = []

        with (
            patch("cortex.engines.synthesis.ContextGraph", return_value=mock_graph),
            patch("cortex.engines.synthesis.NodeType", create=True),
        ):
            from cortex.batch.morning_processor import get_overnight_v2_lessons

            result = get_overnight_v2_lessons()
            assert result == []

    def test_with_recent_nodes(self):
        """Returns lessons created within last 24h."""
        recent_node = SimpleNamespace(
            name="hrrr_lambert_gotcha",
            data={"description": "Must use _find_nearest_lambert for HRRR"},
            type="LESSON",
            updated_at=datetime.now() - timedelta(hours=2),
            created_at=datetime.now() - timedelta(hours=2),
        )
        old_node = SimpleNamespace(
            name="old_lesson",
            data={"description": "stale"},
            type="LESSON",
            updated_at=datetime.now() - timedelta(hours=48),
            created_at=datetime.now() - timedelta(hours=48),
        )

        mock_graph = MagicMock()
        mock_graph.get_nodes_by_type.return_value = [recent_node, old_node]

        with patch("cortex.engines.synthesis.ContextGraph", return_value=mock_graph):
            from cortex.batch.morning_processor import get_overnight_v2_lessons

            result = get_overnight_v2_lessons()
            assert len(result) == 1
            assert result[0]["name"] == "hrrr_lambert_gotcha"

    def test_import_failure_returns_empty(self):
        """Returns empty list if ContextGraph import fails."""
        with patch.dict("sys.modules", {"cortex.engines.synthesis": None}):
            import cortex.batch.morning_processor as mp

            # Force re-execution — the function does a lazy import
            result = mp.get_overnight_v2_lessons()
            assert result == []


class TestV2ReasoningLayer:
    """Tests for intelligence.v2_reasoning.V2ReasoningLayer."""

    def test_empty_graph(self):
        """Returns empty list when synthesis returns no nodes."""
        from cortex.intelligence.v2_reasoning import V2ReasoningLayer

        mock_synthesis = MagicMock()
        mock_synthesis.query.return_value = {"nodes": []}

        layer = V2ReasoningLayer(mock_synthesis)
        result = layer.evaluate(context="test", project="cortex")
        assert result == []

    def test_with_lessons(self):
        """Returns interventions for high-confidence LESSON nodes."""
        from cortex.intelligence.v2_reasoning import V2ReasoningLayer

        mock_synthesis = MagicMock()
        mock_synthesis.query.return_value = {
            "nodes": [
                {"type": "LESSON", "name": "hrrr_gotcha", "confidence": 0.9},
                {"type": "PATTERN", "name": "low_conf", "confidence": 0.3},  # Below threshold
                {"type": "LESSON", "name": "ensemble_field_select", "confidence": 0.8},
            ]
        }

        layer = V2ReasoningLayer(mock_synthesis)
        result = layer.evaluate(context="HRRR issues", project="vortex")

        assert len(result) == 2
        assert result[0]["lesson"] == "hrrr_gotcha"
        assert result[0]["source"] == "v2_reasoning"
        assert result[0]["project"] == "vortex"
        assert result[1]["lesson"] == "ensemble_field_select"

    def test_synthesis_error_returns_empty(self):
        """Exception in synthesis.query returns empty list."""
        from cortex.intelligence.v2_reasoning import V2ReasoningLayer

        mock_synthesis = MagicMock()
        mock_synthesis.query.side_effect = RuntimeError("graph corrupt")

        layer = V2ReasoningLayer(mock_synthesis)
        result = layer.evaluate(context="test", project="cortex")
        assert result == []


class TestGetInterventions:
    """Tests for bridge_intelligence get_interventions method."""

    def test_no_engines_returns_empty(self):
        """Returns empty list when synthesis/broker not available."""
        # Create a minimal mock of the intelligence mixin
        mock_self = MagicMock()
        mock_self.synthesis = None
        mock_self.broker = None

        from cortex.bridge_intelligence import IntelligenceMixin

        result = IntelligenceMixin.get_interventions(mock_self, project="cortex")
        assert result == []
