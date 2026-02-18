"""Graph-based memory storage using SQLite."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from .models import Edge, GraphQueryResult, MemoryType, Node, RelationType


class GraphMemory:
    """Graph-based memory with SQLite backend.

    Provides relationship-aware storage for patterns, projects, outcomes.
    Enables queries like "patterns used by VortexV2" or "similar patterns".
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize graph memory.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.claude/v2/graph.db
        """
        if db_path is None:
            db_path = Path.home() / ".claude" / "v2" / "graph.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript(
                """
                -- Nodes table
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Edges table
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    from_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                    to_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                -- Indexes for fast queries
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
                CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
                CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

                -- Full-text search on node names
                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                    id, name, content='nodes', content_rowid='rowid'
                );

                -- Triggers to keep FTS in sync
                CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
                    INSERT INTO nodes_fts(id, name) VALUES (new.id, new.name);
                END;

                CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, id, name) VALUES('delete', old.id, old.name);
                END;

                CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, id, name) VALUES('delete', old.id, old.name);
                    INSERT INTO nodes_fts(id, name) VALUES (new.id, new.name);
                END;
            """
            )

    # === Node Operations ===

    def add_node(self, type: MemoryType, name: str, data: Dict[str, Any] = None) -> Node:
        """Add a node to the graph.

        Args:
            type: Type of memory (pattern, project, outcome, etc.)
            name: Human-readable name
            data: Additional structured data

        Returns:
            Created Node object
        """
        node = Node.create(type=type, name=name, data=data)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO nodes (id, type, name, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.type.value,
                    node.name,
                    json.dumps(node.data),
                    node.created_at.isoformat(),
                    node.updated_at.isoformat(),
                ),
            )

        return node

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()

            if row:
                return self._row_to_node(row)
        return None

    def update_node(self, node_id: str, data: Dict[str, Any]) -> Optional[Node]:
        """Update a node's data."""
        with self._connect() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                """
                UPDATE nodes SET data = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(data), now, node_id),
            )

        return self.get_node(node_id)

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        with self._connect() as conn:
            # Delete edges first
            conn.execute("DELETE FROM edges WHERE from_id = ? OR to_id = ?", (node_id, node_id))
            # Delete node
            result = conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            return result.rowcount > 0

    def find_nodes(
        self,
        type: Optional[MemoryType] = None,
        name_contains: Optional[str] = None,
        limit: int = 100,
    ) -> List[Node]:
        """Find nodes by type and/or name."""
        query = "SELECT * FROM nodes WHERE 1=1"
        params = []

        if type:
            query += " AND type = ?"
            params.append(type.value)

        if name_contains:
            # Case-sensitive contains to align with tests and avoid overmatching.
            query += " AND INSTR(name, ?) > 0"
            params.append(name_contains)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_node(row) for row in rows]

    def search_nodes(self, query: str, limit: int = 20) -> List[Node]:
        """Full-text search on node names."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT n.* FROM nodes n
                JOIN nodes_fts fts ON n.id = fts.id
                WHERE nodes_fts MATCH ?
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
            return [self._row_to_node(row) for row in rows]

    # === Edge Operations ===

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation: RelationType,
        weight: float = 1.0,
        data: Dict[str, Any] = None,
    ) -> Edge:
        """Add an edge (relationship) between nodes.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relation: Type of relationship
            weight: Relationship strength (0-1)
            data: Additional structured data

        Returns:
            Created Edge object
        """
        edge = Edge.create(
            from_id=from_id, to_id=to_id, relation=relation, weight=weight, data=data
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO edges (id, from_id, to_id, relation, weight, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.from_id,
                    edge.to_id,
                    edge.relation.value,
                    edge.weight,
                    json.dumps(edge.data),
                    edge.created_at.isoformat(),
                ),
            )

        return edge

    def get_edges(
        self,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation: Optional[RelationType] = None,
    ) -> List[Edge]:
        """Get edges matching criteria."""
        query = "SELECT * FROM edges WHERE 1=1"
        params = []

        if from_id:
            query += " AND from_id = ?"
            params.append(from_id)

        if to_id:
            query += " AND to_id = ?"
            params.append(to_id)

        if relation:
            query += " AND relation = ?"
            params.append(relation.value)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_edge(row) for row in rows]

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        with self._connect() as conn:
            result = conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
            return result.rowcount > 0

    # === Graph Traversal ===

    def get_related(
        self,
        node_id: str,
        relation: Optional[RelationType] = None,
        direction: str = "outgoing",
        depth: int = 1,
    ) -> List[GraphQueryResult]:
        """Get nodes related to a given node.

        Args:
            node_id: Starting node ID
            relation: Filter by relationship type
            direction: "outgoing", "incoming", or "both"
            depth: How many hops to traverse (1-3)

        Returns:
            List of related nodes with path information
        """
        results = []
        visited = {node_id}

        def traverse(current_id: str, current_depth: int, path: List[Edge]):
            if current_depth > depth:
                return

            edges = []
            if direction in ("outgoing", "both"):
                edges.extend(self.get_edges(from_id=current_id, relation=relation))
            if direction in ("incoming", "both"):
                edges.extend(self.get_edges(to_id=current_id, relation=relation))

            for edge in edges:
                next_id = edge.to_id if edge.from_id == current_id else edge.from_id

                if next_id not in visited:
                    visited.add(next_id)
                    node = self.get_node(next_id)
                    if node:
                        new_path = path + [edge]
                        results.append(
                            GraphQueryResult(
                                node=node,
                                path=new_path,
                                distance=len(new_path),
                                relevance=self._calculate_relevance(new_path),
                            )
                        )
                        traverse(next_id, current_depth + 1, new_path)

        traverse(node_id, 1, [])
        return sorted(results, key=lambda r: (-r.relevance, r.distance))

    def find_path(self, from_id: str, to_id: str, max_depth: int = 5) -> Optional[List[Edge]]:
        """Find shortest path between two nodes (BFS)."""
        if from_id == to_id:
            return []

        visited = {from_id}
        queue = [(from_id, [])]

        while queue:
            current_id, path = queue.pop(0)

            if len(path) >= max_depth:
                continue

            edges = self.get_edges(from_id=current_id)
            for edge in edges:
                if edge.to_id == to_id:
                    return path + [edge]

                if edge.to_id not in visited:
                    visited.add(edge.to_id)
                    queue.append((edge.to_id, path + [edge]))

        return None

    def get_patterns_for_project(self, project_id: str) -> List[Node]:
        """Get all patterns used by a project."""
        results = self.get_related(
            node_id=project_id,
            relation=RelationType.USES,
            direction="outgoing",
            depth=1,
        )
        return [r.node for r in results if r.node.type == MemoryType.PATTERN]

    def get_similar_patterns(self, pattern_id: str) -> List[Node]:
        """Get patterns similar to a given pattern."""
        results = self.get_related(
            node_id=pattern_id,
            relation=RelationType.SIMILAR_TO,
            direction="both",
            depth=1,
        )
        return [r.node for r in results if r.node.type == MemoryType.PATTERN]

    def get_pattern_outcomes(self, pattern_id: str) -> List[Node]:
        """Get outcomes that validate or invalidate a pattern."""
        results = self.get_related(
            node_id=pattern_id,
            relation=RelationType.VALIDATES,
            direction="incoming",
            depth=1,
        )
        return [r.node for r in results if r.node.type == MemoryType.OUTCOME]

    # === Statistics ===

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        with self._connect() as conn:
            node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

            nodes_by_type = {}
            for row in conn.execute("SELECT type, COUNT(*) as count FROM nodes GROUP BY type"):
                nodes_by_type[row["type"]] = row["count"]

            edges_by_relation = {}
            for row in conn.execute(
                "SELECT relation, COUNT(*) as count FROM edges GROUP BY relation"
            ):
                edges_by_relation[row["relation"]] = row["count"]

        return {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "nodes_by_type": nodes_by_type,
            "edges_by_relation": edges_by_relation,
        }

    # === Helpers ===

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        """Convert database row to Node."""
        return Node(
            id=row["id"],
            type=MemoryType(row["type"]),
            name=row["name"],
            data=json.loads(row["data"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        """Convert database row to Edge."""
        return Edge(
            id=row["id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            relation=RelationType(row["relation"]),
            weight=row["weight"],
            data=json.loads(row["data"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _calculate_relevance(self, path: List[Edge]) -> float:
        """Calculate relevance score based on path."""
        if not path:
            return 1.0

        # Relevance decreases with distance and is weighted by edge weights
        base_score = 1.0 / (len(path) + 1)
        weight_score = sum(e.weight for e in path) / len(path)
        return base_score * weight_score
