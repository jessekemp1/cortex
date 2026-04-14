"""
Tests for Phases 1-2: V2 Signal Bus enrichment and signal recording in query_intelligence.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_bridge_with_signal_bus(signal_bus, base_result=None):
    """Build a minimal IntelligenceMixin-style object for testing query_intelligence."""
    from cortex.bridge_intelligence import IntelligenceMixin

    if base_result is None:
        base_result = {"answer": "hello", "lessons_count": 0}

    mock_unified = MagicMock()
    mock_result = MagicMock()
    mock_result.to_dict.return_value = base_result
    mock_unified.query.return_value = mock_result

    class FakeBridge(IntelligenceMixin):
        def __init__(self):
            self.signal_bus = signal_bus
            self.hybrid_retriever = None
            self.tiered_memory = None
            self.context_optimizer = None
            self.unified_intel = mock_unified
            self.config = None
            self.defensive = None

    return FakeBridge()


# ---------------------------------------------------------------------------
# test_v2_context_added_to_result
# ---------------------------------------------------------------------------


def test_v2_context_added_to_result():
    """signal_bus.query returns dict → result has v2_context with correct structure."""
    bus = MagicMock()
    bus.query.return_value = {
        "graph_nodes": ["node-a"],
        "recent_signals": ["sig-1"],
        "trust": 0.9,
    }
    bus.get_cross_project_patterns.return_value = ["pattern-x"]

    bridge = _make_bridge_with_signal_bus(bus, base_result={"answer": "hello", "lessons_count": 0})
    result = bridge.query_intelligence("test query", "cortex")

    assert "v2_context" in result, "v2_context key must be present when signal_bus is set"
    assert result["v2_context"]["graph_nodes"] == ["node-a"]
    assert result["v2_context"]["recent_signals"] == ["sig-1"]
    assert result["v2_context"]["cross_project_patterns"] == ["pattern-x"]


# ---------------------------------------------------------------------------
# test_v2_enrichment_failure_returns_v1_result
# ---------------------------------------------------------------------------


def test_v2_enrichment_failure_returns_v1_result():
    """signal_bus.query raises → result has no error key and V1 fields intact."""
    bus = MagicMock()
    bus.query.side_effect = RuntimeError("bus exploded")

    bridge = _make_bridge_with_signal_bus(bus, base_result={"answer": "hello", "lessons_count": 1})
    result = bridge.query_intelligence("test query", "cortex")

    assert "error" not in result, "query failure must not surface error key"
    assert result.get("answer") == "hello", "V1 fields must survive V2 failure"
    assert "v2_context" not in result, "v2_context must not appear on failure"


# ---------------------------------------------------------------------------
# test_signal_absorbed_on_query
# ---------------------------------------------------------------------------


def test_signal_absorbed_on_query():
    """signal_bus.absorb is called once per query_intelligence invocation."""
    bus = MagicMock()
    bus.query.return_value = {"graph_nodes": [], "recent_signals": [], "trust": 0.5}
    bus.get_cross_project_patterns.return_value = []

    bridge = _make_bridge_with_signal_bus(bus, base_result={"answer": "hi", "lessons_count": 0})
    bridge.query_intelligence("some request", "vortex")

    bus.absorb.assert_called_once()


# ---------------------------------------------------------------------------
# test_signal_absorb_failure_doesnt_break_query
# ---------------------------------------------------------------------------


def test_signal_absorb_failure_doesnt_break_query():
    """signal_bus.absorb raises → query result is still valid."""
    bus = MagicMock()
    bus.query.return_value = {"graph_nodes": [], "recent_signals": [], "trust": 0.5}
    bus.get_cross_project_patterns.return_value = []
    bus.absorb.side_effect = RuntimeError("absorb failed")

    bridge = _make_bridge_with_signal_bus(
        bus, base_result={"answer": "still here", "lessons_count": 0}
    )
    result = bridge.query_intelligence("query", "cortex")

    assert result.get("answer") == "still here", "Result must be valid even when absorb raises"
    assert "error" not in result
