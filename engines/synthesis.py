"""
Engine B: The Synthesis Core

Converting raw signals into structured context via hierarchical graph.
This is the PROCESSING layer of Cortex V2 Prime.

Architecture: Hierarchical Context Graph
- Nodes: Goals, Projects, Files, Patterns, Errors, Dependencies
- Edges: relates_to, implements, blocks, causes, contains, used_in
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the context graph."""

    GOAL = "goal"
    PROJECT = "project"
    FILE = "file"
    PATTERN = "pattern"
    LESSON = "lesson"
    DECISION = "decision"
    ERROR = "error"
    DEPENDENCY = "dependency"
    WORK_ITEM = "work_item"


class EdgeType(Enum):
    """Types of edges (relationships) in the context graph."""

    RELATES_TO = "relates_to"
    IMPLEMENTS = "implements"
    BLOCKS = "blocks"
    CAUSES = "causes"
    CONTAINS = "contains"
    USED_IN = "used_in"
    OCCURS_IN = "occurs_in"
    DEPENDS_ON = "depends_on"


@dataclass
class Node:
    """Graph node representing a context entity."""

    id: str
    type: NodeType
    name: str
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Node":
        return cls(
            id=data["id"],
            type=NodeType(data["type"]),
            name=data["name"],
            data=data["data"],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        )


@dataclass
class Edge:
    """Graph edge representing a relationship."""

    source_id: str
    target_id: str
    type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type.value,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    # Legacy edge-type names (pre-2026-05 graph generation) mapped onto the
    # current EdgeType enum. Without this, EdgeType("same_project") raised
    # ValueError inside _load(), which silently dropped every stored edge and
    # let the next _save() overwrite edges.json with []. See from_dict.
    _LEGACY_TYPE_MAP = {
        "same_project": "relates_to",
        "keyword_overlap": "relates_to",
        "fixes": "implements",
    }

    @classmethod
    def from_dict(cls, data: Dict) -> "Edge":
        # Backward-compat field names: older edges stored source/target/data
        # instead of source_id/target_id/metadata.
        source_id = data.get("source_id") or data.get("source")
        target_id = data.get("target_id") or data.get("target")
        if not source_id or not target_id:
            raise KeyError("edge missing source_id/target_id (or legacy source/target)")

        type_str = data.get("type", "relates_to")
        try:
            edge_type = EdgeType(type_str)
        except ValueError:
            # Unknown/legacy type — map it rather than dropping the whole edge.
            edge_type = EdgeType(cls._LEGACY_TYPE_MAP.get(type_str, "relates_to"))

        metadata = data.get("metadata")
        if metadata is None:
            metadata = data.get("data", {})

        return cls(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            weight=data.get("weight", 1.0),
            metadata=metadata,
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
        )


class ContextGraph:
    """
    Hierarchical context graph for V2 Prime.

    Nodes: Goals, Projects, Files, Patterns, Errors
    Edges: Relates To, Blocks, Implements, Caused By
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".cortex" / "graph"
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._adjacency: Dict[str, Set[str]] = {}  # node_id -> connected node_ids
        self._reverse_adjacency: Dict[str, Set[str]] = {}  # node_id -> nodes pointing to it
        self._edges_by_source: Dict[str, List[Edge]] = {}
        self._edges_by_target: Dict[str, List[Edge]] = {}

        self._load()

    def _load(self) -> None:
        """Load graph from storage."""
        nodes_path = self.storage_path / "nodes.json"
        edges_path = self.storage_path / "edges.json"

        if nodes_path.exists():
            try:
                with open(nodes_path) as f:
                    data = json.load(f)
                    for node_data in data:
                        node = Node.from_dict(node_data)
                        self.nodes[node.id] = node
            except Exception as e:
                logger.error(f"Failed to load nodes: {e}")

        if edges_path.exists():
            try:
                with open(edges_path) as f:
                    data = json.load(f)
                    for edge_data in data:
                        edge = Edge.from_dict(edge_data)
                        self.edges.append(edge)
                        self._update_adjacency(edge)
            except Exception as e:
                logger.error(f"Failed to load edges: {e}")

        logger.info(f"Loaded graph: {len(self.nodes)} nodes, {len(self.edges)} edges")

    @staticmethod
    def _atomic_write_json(path: Path, payload) -> None:
        """Write JSON to ``path`` atomically (temp file + os.replace).

        A same-directory temp file is fully written and fsynced, then renamed
        over the target. os.replace is atomic on POSIX, so a concurrent reader
        (the bridge daemon vs the maintenance job) always sees either the old
        or the new complete file — never a torn/truncated one.
        """
        import os
        import tempfile

        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)  # atomic
        except Exception:
            # Never leave a stray temp file behind on failure.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _save(self) -> bool:
        """Save graph to storage atomically.

        Returns True on success, False if the write failed (e.g. disk full) so
        callers can react instead of silently proceeding on stale data.
        """
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            edges_path = self.storage_path / "edges.json"

            # SAFETY GUARD: never downgrade a non-empty edges.json to []. An
            # empty self.edges almost always means _load() failed to parse the
            # stored edges (e.g. a schema mismatch) rather than a graph that
            # genuinely has no edges. Overwriting here is exactly how 1247
            # edges were lost between April and June 2026. If the caller truly
            # wants to clear edges it can delete the file explicitly.
            skip_edges = False
            if not self.edges and edges_path.exists():
                try:
                    with open(edges_path) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, OSError):
                    existing = []
                if existing:
                    logger.warning(
                        "Refusing to overwrite %d persisted edges with an empty set "
                        "(likely a load failure, not an intentional clear).",
                        len(existing),
                    )
                    skip_edges = True

            self._atomic_write_json(
                self.storage_path / "nodes.json", [n.to_dict() for n in self.nodes.values()]
            )
            if not skip_edges:
                self._atomic_write_json(edges_path, [e.to_dict() for e in self.edges])
            return True

        except Exception as e:
            # Surface the failure in logs AND to the caller — a swallowed disk
            # error previously meant edges could be lost with no signal.
            logger.error(f"Failed to save graph: {e}")
            return False

    def _update_adjacency(self, edge: Edge) -> None:
        """Update adjacency indices."""
        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = set()
        if edge.target_id not in self._adjacency:
            self._adjacency[edge.target_id] = set()
        if edge.source_id not in self._reverse_adjacency:
            self._reverse_adjacency[edge.source_id] = set()
        if edge.target_id not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target_id] = set()

        self._adjacency[edge.source_id].add(edge.target_id)
        self._reverse_adjacency[edge.target_id].add(edge.source_id)

        # Index by source/target
        if edge.source_id not in self._edges_by_source:
            self._edges_by_source[edge.source_id] = []
        self._edges_by_source[edge.source_id].append(edge)

        if edge.target_id not in self._edges_by_target:
            self._edges_by_target[edge.target_id] = []
        self._edges_by_target[edge.target_id].append(edge)

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        self._save()

    def update_node(self, node_id: str, data: Dict[str, Any]) -> Optional[Node]:
        """Update a node's data."""
        if node_id in self.nodes:
            self.nodes[node_id].data.update(data)
            self.nodes[node_id].updated_at = datetime.now()
            self._save()
            return self.nodes[node_id]
        return None

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its edges."""
        if node_id not in self.nodes:
            return False

        del self.nodes[node_id]

        # Remove related edges
        self.edges = [e for e in self.edges if e.source_id != node_id and e.target_id != node_id]

        # Clean up adjacency
        if node_id in self._adjacency:
            del self._adjacency[node_id]
        if node_id in self._reverse_adjacency:
            del self._reverse_adjacency[node_id]

        for adj in self._adjacency.values():
            adj.discard(node_id)
        for adj in self._reverse_adjacency.values():
            adj.discard(node_id)

        self._save()
        return True

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)
        self._update_adjacency(edge)
        self._save()

    def remove_edge(
        self, source_id: str, target_id: str, edge_type: Optional[EdgeType] = None
    ) -> bool:
        """Remove an edge from the graph."""
        original_len = len(self.edges)

        if edge_type:
            self.edges = [
                e
                for e in self.edges
                if not (
                    e.source_id == source_id and e.target_id == target_id and e.type == edge_type
                )
            ]
        else:
            self.edges = [
                e for e in self.edges if not (e.source_id == source_id and e.target_id == target_id)
            ]

        if len(self.edges) < original_len:
            self._rebuild_adjacency()
            self._save()
            return True
        return False

    def _rebuild_adjacency(self) -> None:
        """Rebuild adjacency indices from edges."""
        self._adjacency.clear()
        self._reverse_adjacency.clear()
        self._edges_by_source.clear()
        self._edges_by_target.clear()

        for edge in self.edges:
            self._update_adjacency(edge)

    def regenerate_edges(self, per_node_cap: int = 6, save: bool = True) -> int:
        """Rebuild edges from current nodes when the edge set was lost.

        Bounded and deterministic (O(n * per_node_cap), not O(n^2)): links are
        derived from structured node metadata rather than pairwise keyword
        similarity, so there is no 2111^2 blow-up. Two relationship families:

          1. lesson -> pattern within the same project  (a lesson RELATES_TO
             the patterns of the project it was learned in), capped per lesson.
          2. nodes sharing an exact ``pattern_key``       (co-derived signals).
          3. decision -> lesson/pattern within the same project (a recorded
             decision RELATES_TO the memories of the project it was made in),
             so decisions participate in graph traversal / compounding.

        Idempotent: existing (source, target, type) triples are never
        duplicated, so it is safe to re-run from the maintenance loop.

        Returns the number of edges after regeneration.
        """

        def _bucket_key(node: Node, field: str) -> Optional[str]:
            val = (node.data or {}).get(field)
            return str(val) if val else None

        # Index nodes by project and by pattern_key (deterministic ordering).
        by_project_lessons: Dict[str, List[str]] = {}
        by_project_patterns: Dict[str, List[str]] = {}
        by_project_decisions: Dict[str, List[str]] = {}
        by_pattern_key: Dict[str, List[str]] = {}

        for nid in sorted(self.nodes):
            node = self.nodes[nid]
            proj = _bucket_key(node, "project")
            pkey = _bucket_key(node, "pattern_key")
            if node.type == NodeType.LESSON:
                if proj:
                    by_project_lessons.setdefault(proj, []).append(nid)
            elif node.type == NodeType.PATTERN:
                if proj:
                    by_project_patterns.setdefault(proj, []).append(nid)
            elif node.type == NodeType.DECISION:
                if proj:
                    by_project_decisions.setdefault(proj, []).append(nid)
            if pkey:
                by_pattern_key.setdefault(pkey, []).append(nid)

        # Dedup against whatever edges currently exist.
        existing = {(e.source_id, e.target_id, e.type.value) for e in self.edges}
        new_edges: List[Edge] = []

        def _add(src: str, dst: str, etype: EdgeType, reason: str) -> None:
            if src == dst:
                return
            key = (src, dst, etype.value)
            if key in existing:
                return
            existing.add(key)
            new_edges.append(
                Edge(
                    source_id=src,
                    target_id=dst,
                    type=etype,
                    weight=0.5,
                    metadata={"reason": reason, "regenerated": True},
                )
            )

        # 1. lesson -> pattern within the same project (capped per lesson).
        for proj, lessons in by_project_lessons.items():
            patterns = by_project_patterns.get(proj, [])
            if not patterns:
                continue
            for lid in lessons:
                for pid in patterns[:per_node_cap]:
                    _add(lid, pid, EdgeType.RELATES_TO, "same_project")

        # 2. exact pattern_key co-occurrence (bounded ring per bucket).
        for pkey, nids in by_pattern_key.items():
            if len(nids) < 2:
                continue
            for i, src in enumerate(nids):
                for dst in nids[i + 1 : i + 1 + per_node_cap]:
                    _add(src, dst, EdgeType.RELATES_TO, "shared_pattern_key")

        # 3. decision -> project lessons/patterns (capped per decision) so
        #    recorded decisions are reachable via graph traversal.
        for proj, decisions in by_project_decisions.items():
            neighbors = (
                by_project_lessons.get(proj, []) + by_project_patterns.get(proj, [])
            )[:per_node_cap]
            for did in decisions:
                for nid in neighbors:
                    _add(did, nid, EdgeType.RELATES_TO, "decision_project")

        self.edges.extend(new_edges)
        self._rebuild_adjacency()
        if save:
            self._save()
        logger.info(
            "regenerate_edges: added %d edges (total now %d)", len(new_edges), len(self.edges)
        )
        return len(self.edges)

    def import_decisions(self, decisions_path: Optional[Path] = None, save: bool = True) -> int:
        """Persist recorded decisions from decisions.jsonl as DECISION nodes.

        Decisions were previously loaded into the retriever at query time only
        (a runtime-only view of ``~/.cortex/decisions.jsonl``); they were never
        persisted into the graph, so they could not participate in edges /
        traversal and were effectively lost to the compounding layer. This
        makes the graph a durable second home for them.

        Idempotent: a decision whose node id already exists is skipped, so it
        is safe to re-run from the maintenance loop. Node ids use a
        ``decision:<decision_id>`` scheme matching the retriever's prefix.

        Returns the number of new decision nodes added.
        """
        path = decisions_path or (Path.home() / ".cortex" / "decisions.jsonl")
        if not path.exists():
            return 0

        added = 0
        try:
            lines = path.read_text().splitlines()
        except OSError as exc:
            logger.warning("cannot read decisions file %s: %s", path, exc)
            return 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            decision_text = d.get("decision")
            if not decision_text:
                continue
            decision_id = d.get("decision_id", "unknown")
            node_id = f"decision:{decision_id}"
            data = {
                "project": d.get("project", "unknown"),
                "decision": decision_text,
                "context": d.get("context", ""),
                "alternatives": d.get("alternatives", ""),
                "rationale": d.get("rationale", ""),
                "source": d.get("source", "unknown"),
            }
            existing = self.nodes.get(node_id)
            if existing is not None:
                # Idempotent, but not blind: refresh if the recorded decision's
                # content changed since it was imported (e.g. an edited
                # rationale), otherwise skip. New adds and content changes count.
                if existing.data == data:
                    continue
                existing.data = data
                existing.name = str(decision_text)[:120]
                existing.updated_at = datetime.now()
                added += 1
                continue
            created = d.get("timestamp")
            try:
                created_at = (
                    datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if created
                    else datetime.now()
                )
            except (ValueError, TypeError):
                created_at = datetime.now()
            self.nodes[node_id] = Node(
                id=node_id,
                type=NodeType.DECISION,
                name=str(decision_text)[:120],
                data=data,
                created_at=created_at,
                updated_at=created_at,
            )
            added += 1

        if added and save:
            self._save()
        logger.info("import_decisions: added %d decision nodes (total %d)", added, len(self.nodes))
        return added

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[Node]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.type == node_type]

    def get_related(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[Node]:
        """Get nodes related to a given node (outgoing edges)."""
        related_ids = self._adjacency.get(node_id, set())
        related_nodes = [self.nodes[nid] for nid in related_ids if nid in self.nodes]

        if edge_type:
            # Filter by edge type
            valid_targets = {
                e.target_id for e in self._edges_by_source.get(node_id, []) if e.type == edge_type
            }
            related_nodes = [n for n in related_nodes if n.id in valid_targets]

        return related_nodes

    def get_pointing_to(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[Node]:
        """Get nodes pointing to a given node (incoming edges)."""
        source_ids = self._reverse_adjacency.get(node_id, set())
        source_nodes = [self.nodes[nid] for nid in source_ids if nid in self.nodes]

        if edge_type:
            valid_sources = {
                e.source_id for e in self._edges_by_target.get(node_id, []) if e.type == edge_type
            }
            source_nodes = [n for n in source_nodes if n.id in valid_sources]

        return source_nodes

    def find_path(self, source_id: str, target_id: str, max_depth: int = 10) -> Optional[List[str]]:
        """Find shortest path between two nodes (BFS)."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return None

        visited = {source_id}
        queue = [(source_id, [source_id])]

        while queue and len(queue[0][1]) <= max_depth:
            current, path = queue.pop(0)

            if current == target_id:
                return path

            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_subgraph(self, center_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get subgraph around a node."""
        if center_id not in self.nodes:
            return {"nodes": [], "edges": []}

        visited = {center_id}
        to_visit = [(center_id, 0)]

        while to_visit:
            node_id, current_depth = to_visit.pop(0)

            if current_depth >= depth:
                continue

            neighbors = self._adjacency.get(node_id, set()) | self._reverse_adjacency.get(
                node_id, set()
            )
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    to_visit.append((neighbor, current_depth + 1))

        nodes = [self.nodes[nid].to_dict() for nid in visited if nid in self.nodes]
        edges = [
            e.to_dict() for e in self.edges if e.source_id in visited and e.target_id in visited
        ]

        return {"nodes": nodes, "edges": edges}

    def query(
        self,
        query_text: str,
        node_types: Optional[List[NodeType]] = None,
        limit: int = 10,
    ) -> List[Node]:
        """
        Simple text-based query over graph.

        TODO: Upgrade to semantic search with embeddings.
        """
        query_lower = query_text.lower()
        results = []

        for node in self.nodes.values():
            if node_types and node.type not in node_types:
                continue

            # Simple text matching on name and data
            score = 0
            if query_lower in node.name.lower():
                score += 2

            data_str = json.dumps(node.data).lower()
            if query_lower in data_str:
                score += 1

            if score > 0:
                results.append((score, node))

        # Sort by score descending
        results.sort(key=lambda x: -x[0])
        return [node for _, node in results[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.type.value] = type_counts.get(node.type.value, 0) + 1

        edge_type_counts = {}
        for edge in self.edges:
            edge_type_counts[edge.type.value] = edge_type_counts.get(edge.type.value, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": type_counts,
            "edges_by_type": edge_type_counts,
        }


class SynthesisCore:
    """
    Engine B: Converts signals to structured context.

    This is the processing layer of Cortex V2 Prime.
    """

    def __init__(self, graph: Optional[ContextGraph] = None):
        self.graph = graph or ContextGraph()
        self._signal_processors: Dict[str, callable] = {}

    def process_signal(self, signal) -> List[Node]:
        """
        Process a raw signal and update the context graph.

        Returns list of affected nodes.
        """
        from cortex.engines.absorber import SignalType

        affected_nodes = []

        if signal.type == SignalType.FILE_MODIFIED:
            node = self._process_file_signal(signal)
            if node:
                affected_nodes.append(node)

        elif signal.type == SignalType.GIT_COMMIT:
            nodes = self._process_git_signal(signal)
            affected_nodes.extend(nodes)

        elif signal.type in (SignalType.COMMAND_EXECUTED, SignalType.COMMAND_FAILED):
            node = self._process_command_signal(signal)
            if node:
                affected_nodes.append(node)

        # Mark signal as processed
        signal.processed = True

        return affected_nodes

    def _process_file_signal(self, signal) -> Optional[Node]:
        """Process file modification signal."""
        file_path = signal.payload.get("path")
        if not file_path:
            return None

        file_id = f"file:{file_path}"
        existing = self.graph.get_node(file_id)

        if existing:
            self.graph.update_node(
                file_id,
                {
                    "last_modified": signal.timestamp.isoformat(),
                    "modification_count": existing.data.get("modification_count", 0) + 1,
                },
            )
            return existing
        else:
            node = Node(
                id=file_id,
                type=NodeType.FILE,
                name=Path(file_path).name,
                data={
                    "path": file_path,
                    "project": signal.project,
                    "last_modified": signal.timestamp.isoformat(),
                    "modification_count": 1,
                },
            )
            self.graph.add_node(node)

            # Link to project if known
            if signal.project:
                project_id = f"project:{signal.project}"
                if self.graph.get_node(project_id):
                    self.graph.add_edge(
                        Edge(
                            source_id=project_id,
                            target_id=file_id,
                            type=EdgeType.CONTAINS,
                        )
                    )

            return node

    def _process_git_signal(self, signal) -> List[Node]:
        """Process git commit signal."""
        nodes = []

        commit_id = f"commit:{signal.payload.get('hash', 'unknown')}"

        node = Node(
            id=commit_id,
            type=NodeType.WORK_ITEM,
            name=signal.payload.get("message", "Unknown commit")[:50],
            data={
                "hash": signal.payload.get("hash"),
                "message": signal.payload.get("message"),
                "author": signal.payload.get("author"),
                "timestamp": signal.timestamp.isoformat(),
                "project": signal.project,
                "files_changed": signal.payload.get("files", []),
            },
        )
        self.graph.add_node(node)
        nodes.append(node)

        # Link to project
        if signal.project:
            project_id = f"project:{signal.project}"
            if self.graph.get_node(project_id):
                self.graph.add_edge(
                    Edge(
                        source_id=project_id,
                        target_id=commit_id,
                        type=EdgeType.CONTAINS,
                    )
                )

        return nodes

    def _process_command_signal(self, signal) -> Optional[Node]:
        """Process command execution signal."""
        from cortex.engines.absorber import SignalType

        command = signal.payload.get("command", "")
        if not command or len(command) < 3:
            return None

        # Only track interesting commands
        interesting_prefixes = ["git ", "python ", "pytest ", "npm ", "cargo ", "make "]
        if not any(command.startswith(p) for p in interesting_prefixes):
            return None

        import uuid

        node = Node(
            id=f"command:{uuid.uuid4().hex[:8]}",
            type=NodeType.WORK_ITEM,
            name=command[:50],
            data={
                "command": command,
                "success": signal.type == SignalType.COMMAND_EXECUTED,
                "timestamp": signal.timestamp.isoformat(),
                "project": signal.project,
            },
        )
        self.graph.add_node(node)
        return node

    def query(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Query the context graph.

        Returns relevant nodes and relationships.
        """
        # Get relevant nodes
        nodes = self.graph.query(query, limit=10)

        # Get edges between these nodes
        node_ids = {n.id for n in nodes}
        edges = [e for e in self.graph.edges if e.source_id in node_ids or e.target_id in node_ids]

        return {
            "query": query,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "count": len(nodes),
        }

    def get_context_for_goal(self, goal_id: str) -> Dict[str, Any]:
        """Get full context for a goal."""
        goal = self.graph.get_node(goal_id)
        if not goal:
            return {"error": f"Goal {goal_id} not found"}

        # Get related patterns, projects, files
        related = self.graph.get_related(goal_id)
        blockers = self.graph.get_related(goal_id, EdgeType.BLOCKS)
        implementing = self.graph.get_pointing_to(goal_id, EdgeType.IMPLEMENTS)

        return {
            "goal": goal.to_dict(),
            "related_nodes": [n.to_dict() for n in related],
            "blocking": [n.to_dict() for n in blockers],
            "implementing": [n.to_dict() for n in implementing],
        }

    def get_context_for_project(self, project_name: str) -> Dict[str, Any]:
        """Get full context for a project."""
        project_id = f"project:{project_name}"
        project = self.graph.get_node(project_id)

        if not project:
            return {"error": f"Project {project_name} not found"}

        # Get contained files, related patterns, lessons
        contained = self.graph.get_related(project_id, EdgeType.CONTAINS)
        patterns = [n for n in self.graph.get_related(project_id) if n.type == NodeType.PATTERN]
        lessons = [n for n in self.graph.get_related(project_id) if n.type == NodeType.LESSON]

        return {
            "project": project.to_dict(),
            "files": [n.to_dict() for n in contained if n.type == NodeType.FILE],
            "work_items": [n.to_dict() for n in contained if n.type == NodeType.WORK_ITEM],
            "patterns": [n.to_dict() for n in patterns],
            "lessons": [n.to_dict() for n in lessons],
        }

    def import_portfolio_data(self, portfolio_path: Path) -> Dict[str, int]:
        """
        Import existing portfolio data into graph.

        Converts V1 patterns, lessons, projects to V2 Prime nodes.
        """
        imported = {"patterns": 0, "lessons": 0, "projects": 0, "goals": 0}

        # Import patterns
        patterns_file = portfolio_path / "patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file) as f:
                    patterns = json.load(f)
                for pattern in patterns:
                    node = Node(
                        id=f"pattern:{pattern.get('name', 'unknown')}",
                        type=NodeType.PATTERN,
                        name=pattern.get("name", "Unknown Pattern"),
                        data=pattern,
                    )
                    self.graph.add_node(node)
                    imported["patterns"] += 1
            except Exception as e:
                logger.error(f"Failed to import patterns: {e}")

        # Import lessons
        lessons_file = portfolio_path / "lessons.json"
        if lessons_file.exists():
            try:
                with open(lessons_file) as f:
                    lessons = json.load(f)
                for lesson in lessons:
                    node = Node(
                        id=f"lesson:{lesson.get('title', 'unknown')}",
                        type=NodeType.LESSON,
                        name=lesson.get("title", "Unknown Lesson"),
                        data=lesson,
                    )
                    self.graph.add_node(node)
                    imported["lessons"] += 1
            except Exception as e:
                logger.error(f"Failed to import lessons: {e}")

        # Import projects
        projects_file = portfolio_path / "project_index.json"
        if projects_file.exists():
            try:
                with open(projects_file) as f:
                    data = json.load(f)

                # Handle nested "projects" key format
                if isinstance(data, dict) and "projects" in data:
                    projects = data["projects"]
                    if isinstance(projects, dict):
                        # Format: {"projects": {"key": {...}, ...}}
                        projects = list(projects.values())
                elif isinstance(data, dict):
                    # Format: {"key": {...}, ...}
                    projects = list(data.values())
                else:
                    projects = data

                for project in projects:
                    if isinstance(project, dict):
                        node = Node(
                            id=f"project:{project.get('name', 'unknown')}",
                            type=NodeType.PROJECT,
                            name=project.get("name", "Unknown Project"),
                            data=project,
                        )
                        self.graph.add_node(node)
                        imported["projects"] += 1
            except Exception as e:
                logger.error(f"Failed to import projects: {e}")

        # Import goals
        goals_file = portfolio_path / "goals.json"
        if goals_file.exists():
            try:
                with open(goals_file) as f:
                    goals = json.load(f)
                for goal in goals:
                    node = Node(
                        id=f"goal:{goal.get('id', 'unknown')}",
                        type=NodeType.GOAL,
                        name=goal.get("name", goal.get("title", "Unknown Goal")),
                        data=goal,
                    )
                    self.graph.add_node(node)
                    imported["goals"] += 1
            except Exception as e:
                logger.error(f"Failed to import goals: {e}")

        logger.info(f"Imported: {imported}")
        return imported
