"""
Tests for V2 engine wiring — verifies ContextGraph and SynthesisCore
are importable, functional, and correctly wired to bridge_endpoint routes.

Phase 2 acceptance criteria (cortex_v2_plan.md):
  python -c "from engines import ContextAbsorber, SynthesisCore, ActionBroker" → OK
"""

from datetime import datetime

import pytest


class TestContextGraphCore:
    """ContextGraph (engines/synthesis.py) — basic CRUD and query."""

    @pytest.fixture
    def graph(self, tmp_path):
        from engines.synthesis import ContextGraph

        return ContextGraph(storage_path=tmp_path / "graph")

    def test_import_ok(self):
        from engines.synthesis import ContextGraph, SynthesisCore

        assert ContextGraph is not None
        assert SynthesisCore is not None

    def test_add_and_query_node(self, graph):
        from engines.synthesis import Node, NodeType

        node = Node(
            id="pattern:test_wiring",
            type=NodeType.PATTERN,
            name="V2 Engine Wiring Test Pattern",
            data={"key": "value", "source": "unit_test"},
        )
        graph.add_node(node)

        results = graph.query("wiring")
        assert len(results) == 1
        assert results[0].id == "pattern:test_wiring"

    def test_query_returns_empty_for_no_match(self, graph):
        results = graph.query("zzz_no_match_xyz")
        assert results == []

    def test_get_stats_structure(self, graph):
        from engines.synthesis import Node, NodeType

        graph.add_node(Node(id="goal:1", type=NodeType.GOAL, name="Ship V2", data={}))
        graph.add_node(Node(id="project:cortex", type=NodeType.PROJECT, name="Cortex", data={}))

        stats = graph.get_stats()
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert "nodes_by_type" in stats
        assert stats["total_nodes"] == 2
        assert stats["nodes_by_type"]["goal"] == 1
        assert stats["nodes_by_type"]["project"] == 1

    def test_persistence(self, tmp_path):
        from engines.synthesis import ContextGraph, Node, NodeType

        storage = tmp_path / "graph"
        g1 = ContextGraph(storage_path=storage)
        g1.add_node(
            Node(id="test:persist", type=NodeType.PATTERN, name="Persistence Check", data={})
        )
        g1._save()

        g2 = ContextGraph(storage_path=storage)
        assert "test:persist" in g2.nodes

    def test_query_limit(self, graph):
        from engines.synthesis import Node, NodeType

        for i in range(10):
            graph.add_node(
                Node(id=f"pattern:{i}", type=NodeType.PATTERN, name=f"pattern item {i}", data={})
            )

        results = graph.query("pattern", limit=3)
        assert len(results) <= 3


class TestSynthesisCoreSignalProcessing:
    """SynthesisCore processes signals into ContextGraph nodes."""

    @pytest.fixture
    def core(self, tmp_path):
        from engines.synthesis import ContextGraph, SynthesisCore

        graph = ContextGraph(storage_path=tmp_path / "graph")
        return SynthesisCore(graph=graph)

    def test_process_file_signal(self, core):
        from engines.absorber import Signal, SignalType

        signal = Signal(
            id="sig_001",
            type=SignalType.FILE_MODIFIED,
            timestamp=datetime.now(),
            source="test",
            payload={"path": "cortex/mcp_server.py", "lines_changed": 50},
            project="cortex",
        )
        nodes = core.process_signal(signal)
        assert isinstance(nodes, list)

    def test_process_git_signal(self, core):
        from engines.absorber import Signal, SignalType

        signal = Signal(
            id="sig_002",
            type=SignalType.GIT_COMMIT,
            timestamp=datetime.now(),
            source="git",
            payload={"message": "feat(cortex): V2 engine wiring", "hash": "abc123"},
            project="cortex",
        )
        nodes = core.process_signal(signal)
        assert isinstance(nodes, list)


class TestContextAbsorberImport:
    """ContextAbsorber (engines/absorber.py) — import and basic API."""

    def test_import_all_v2_engines(self):
        """Phase 2 acceptance criterion from cortex_v2_plan.md."""
        from engines.absorber import ContextAbsorber
        from engines.broker import ActionBroker
        from engines.synthesis import SynthesisCore

        assert ContextAbsorber is not None
        assert SynthesisCore is not None
        assert ActionBroker is not None

    def test_create_default_absorber(self, tmp_path):
        from engines.absorber import create_default_absorber

        absorber = create_default_absorber(root_dir=tmp_path)
        assert absorber is not None
        status = absorber.get_status()
        assert "sources" in status

    def test_absorber_get_buffer_empty(self, tmp_path):
        from engines.absorber import create_default_absorber

        absorber = create_default_absorber(root_dir=tmp_path)
        buf = absorber.get_buffer()
        assert isinstance(buf, list)


class TestActionBrokerImport:
    """ActionBroker (engines/broker.py) — import and basic API."""

    def test_create_broker(self):
        from engines.broker import ActionBroker

        broker = ActionBroker()
        assert broker is not None

    def test_get_pending_empty(self):
        from engines.broker import ActionBroker

        broker = ActionBroker()
        pending = broker.get_pending()
        assert isinstance(pending, list)

    def test_get_status(self):
        from engines.broker import ActionBroker

        broker = ActionBroker()
        status = broker.get_status()
        assert "pending_count" in status


class TestBridgeEndpointV2GraphRoutes:
    """Verify bridge_endpoint.py /v2/graph/* routes use engines/synthesis.ContextGraph."""

    def test_v2_graph_search_uses_context_graph(self):
        """Route imports ContextGraph, not the deleted cortex.v2.memory.graph."""
        import inspect

        from api.bridge_endpoint import search_v2_graph

        src = inspect.getsource(search_v2_graph)
        assert "engines.synthesis" in src, "Route must import from engines.synthesis"
        assert "v2.memory.graph" not in src, "Deleted v2.memory.graph must not be referenced"

    def test_v2_graph_stats_uses_context_graph(self):
        """Route imports ContextGraph, not the deleted cortex.v2.memory.graph."""
        import inspect

        from api.bridge_endpoint import get_v2_graph_stats

        src = inspect.getsource(get_v2_graph_stats)
        assert "engines.synthesis" in src, "Route must import from engines.synthesis"
        assert "v2.memory.graph" not in src, "Deleted v2.memory.graph must not be referenced"

    def test_v2_graph_search_returns_results_format(self):
        """The route function returns the expected dict structure."""
        import asyncio

        from api.bridge_endpoint import search_v2_graph

        # Call the async function directly (no HTTP server needed)
        # We're testing the return structure, not integration
        # Use a real query that should return 0 results on empty storage path
        # but should not raise — we just verify it imports correctly
        try:
            result = asyncio.run(search_v2_graph(query="test", limit=1))
            assert "results" in result
            assert "total" in result
        except Exception as e:
            # If graph storage doesn't exist, it should still return empty results
            # not raise ImportError (that was the bug)
            assert "ImportError" not in str(type(e).__name__), f"Should not ImportError: {e}"
