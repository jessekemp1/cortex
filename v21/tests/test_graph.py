"""Tests for graph memory system."""

import tempfile
from pathlib import Path

import pytest
from cortex.v2.memory.graph import GraphMemory
from cortex.v2.memory.models import Edge, MemoryType, Node, RelationType


@pytest.fixture
def graph():
    """Create a temporary graph memory instance."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    g = GraphMemory(db_path=db_path)
    yield g

    # Cleanup
    db_path.unlink(missing_ok=True)


class TestGraphMemory:
    """Test GraphMemory class."""

    def test_add_node(self, graph):
        """Test adding a node."""
        node = graph.add_node(
            type=MemoryType.PATTERN,
            name="Redis Caching Pattern",
            data={"problem": "Slow API responses"},
        )

        assert node.id.startswith("pattern_")
        assert node.type == MemoryType.PATTERN
        assert node.name == "Redis Caching Pattern"
        assert node.data["problem"] == "Slow API responses"

    def test_get_node(self, graph):
        """Test retrieving a node."""
        node = graph.add_node(type=MemoryType.PROJECT, name="VortexV2")

        retrieved = graph.get_node(node.id)
        assert retrieved is not None
        assert retrieved.id == node.id
        assert retrieved.name == "VortexV2"

    def test_delete_node(self, graph):
        """Test deleting a node."""
        node = graph.add_node(type=MemoryType.PATTERN, name="Test")

        assert graph.delete_node(node.id)
        assert graph.get_node(node.id) is None

    def test_find_nodes(self, graph):
        """Test finding nodes by type and name."""
        graph.add_node(type=MemoryType.PATTERN, name="Pattern A")
        graph.add_node(type=MemoryType.PATTERN, name="Pattern B")
        graph.add_node(type=MemoryType.PROJECT, name="Project A")

        patterns = graph.find_nodes(type=MemoryType.PATTERN)
        assert len(patterns) == 2

        projects = graph.find_nodes(type=MemoryType.PROJECT)
        assert len(projects) == 1

        a_nodes = graph.find_nodes(name_contains="A")
        assert len(a_nodes) == 2

    def test_add_edge(self, graph):
        """Test adding an edge between nodes."""
        project = graph.add_node(type=MemoryType.PROJECT, name="VortexV2")
        pattern = graph.add_node(type=MemoryType.PATTERN, name="Redis Caching")

        edge = graph.add_edge(
            from_id=project.id, to_id=pattern.id, relation=RelationType.USES, weight=0.9
        )

        assert edge.id.startswith("edge_")
        assert edge.from_id == project.id
        assert edge.to_id == pattern.id
        assert edge.relation == RelationType.USES
        assert edge.weight == 0.9

    def test_get_edges(self, graph):
        """Test getting edges by criteria."""
        p1 = graph.add_node(type=MemoryType.PROJECT, name="P1")
        p2 = graph.add_node(type=MemoryType.PROJECT, name="P2")
        pattern = graph.add_node(type=MemoryType.PATTERN, name="Pattern")

        graph.add_edge(p1.id, pattern.id, RelationType.USES)
        graph.add_edge(p2.id, pattern.id, RelationType.USES)

        edges_from_p1 = graph.get_edges(from_id=p1.id)
        assert len(edges_from_p1) == 1

        edges_to_pattern = graph.get_edges(to_id=pattern.id)
        assert len(edges_to_pattern) == 2

        uses_edges = graph.get_edges(relation=RelationType.USES)
        assert len(uses_edges) == 2

    def test_get_related(self, graph):
        """Test getting related nodes."""
        project = graph.add_node(type=MemoryType.PROJECT, name="VortexV2")
        pattern1 = graph.add_node(type=MemoryType.PATTERN, name="Redis Caching")
        pattern2 = graph.add_node(type=MemoryType.PATTERN, name="JWT Auth")

        graph.add_edge(project.id, pattern1.id, RelationType.USES)
        graph.add_edge(project.id, pattern2.id, RelationType.USES)

        related = graph.get_related(project.id, direction="outgoing")
        assert len(related) == 2

    def test_get_patterns_for_project(self, graph):
        """Test getting patterns used by a project."""
        project = graph.add_node(type=MemoryType.PROJECT, name="VortexV2")
        pattern1 = graph.add_node(type=MemoryType.PATTERN, name="Redis Caching")
        pattern2 = graph.add_node(type=MemoryType.PATTERN, name="JWT Auth")
        other = graph.add_node(type=MemoryType.OUTCOME, name="Outcome")

        graph.add_edge(project.id, pattern1.id, RelationType.USES)
        graph.add_edge(project.id, pattern2.id, RelationType.USES)
        graph.add_edge(project.id, other.id, RelationType.USES)

        patterns = graph.get_patterns_for_project(project.id)
        assert len(patterns) == 2
        assert all(p.type == MemoryType.PATTERN for p in patterns)

    def test_get_similar_patterns(self, graph):
        """Test getting similar patterns."""
        p1 = graph.add_node(type=MemoryType.PATTERN, name="Redis Caching")
        p2 = graph.add_node(type=MemoryType.PATTERN, name="Memcached Caching")
        p3 = graph.add_node(type=MemoryType.PATTERN, name="Unrelated")

        graph.add_edge(p1.id, p2.id, RelationType.SIMILAR_TO)

        similar = graph.get_similar_patterns(p1.id)
        assert len(similar) == 1
        assert similar[0].name == "Memcached Caching"

    def test_find_path(self, graph):
        """Test finding path between nodes."""
        a = graph.add_node(type=MemoryType.PROJECT, name="A")
        b = graph.add_node(type=MemoryType.PATTERN, name="B")
        c = graph.add_node(type=MemoryType.OUTCOME, name="C")

        graph.add_edge(a.id, b.id, RelationType.USES)
        graph.add_edge(b.id, c.id, RelationType.VALIDATES)

        path = graph.find_path(a.id, c.id)
        assert path is not None
        assert len(path) == 2
        assert path[0].relation == RelationType.USES
        assert path[1].relation == RelationType.VALIDATES

    def test_stats(self, graph):
        """Test graph statistics."""
        graph.add_node(type=MemoryType.PROJECT, name="P1")
        graph.add_node(type=MemoryType.PATTERN, name="Pattern")

        p1 = graph.find_nodes(type=MemoryType.PROJECT)[0]
        pattern = graph.find_nodes(type=MemoryType.PATTERN)[0]
        graph.add_edge(p1.id, pattern.id, RelationType.USES)

        stats = graph.stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["nodes_by_type"]["project"] == 1
        assert stats["nodes_by_type"]["pattern"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
