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

    @classmethod
    def from_dict(cls, data: Dict) -> "Edge":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            type=EdgeType(data["type"]),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
        )


class ContextGraph:
    """
    Hierarchical context graph for V2 Prime.

    Nodes: Goals, Projects, Files, Patterns, Errors
    Edges: Relates To, Blocks, Implements, Caused By
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".claude" / "graph"
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

    def _save(self) -> None:
        """Save graph to storage."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)

            with open(self.storage_path / "nodes.json", "w") as f:
                json.dump([n.to_dict() for n in self.nodes.values()], f, indent=2)

            with open(self.storage_path / "edges.json", "w") as f:
                json.dump([e.to_dict() for e in self.edges], f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save graph: {e}")

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
