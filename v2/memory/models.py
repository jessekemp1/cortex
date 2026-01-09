"""Data models for V2 memory system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid


class MemoryType(Enum):
    """Types of memories stored in the system."""
    PATTERN = "pattern"      # Reusable solutions
    INCIDENT = "incident"    # What went wrong
    SKILL = "skill"          # Step-by-step procedures
    DECISION = "decision"    # Why we chose X over Y
    FACT = "fact"            # General knowledge
    PROJECT = "project"      # Project metadata
    OUTCOME = "outcome"      # Detected outcomes
    GOAL = "goal"            # Tracked goals/objectives


class RelationType(Enum):
    """Types of relationships between nodes."""
    USES = "uses"                    # project uses pattern
    SIMILAR_TO = "similar_to"        # pattern similar to pattern
    VALIDATES = "validates"          # outcome validates pattern
    CAUSED_BY = "caused_by"          # incident caused by pattern
    EXTRACTED_FROM = "extracted_from"  # skill extracted from outcome
    DEPENDS_ON = "depends_on"        # project depends on project
    SUPERSEDES = "supersedes"        # pattern supersedes older pattern
    RELATED_TO = "related_to"        # generic relationship


@dataclass
class Node:
    """A node in the memory graph."""
    id: str
    type: MemoryType
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, type: MemoryType, name: str, data: Dict[str, Any] = None) -> "Node":
        """Create a new node with generated ID."""
        return cls(
            id=f"{type.value}_{uuid.uuid4().hex[:8]}",
            type=type,
            name=name,
            data=data or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Node":
        """Create from dictionary."""
        return cls(
            id=d["id"],
            type=MemoryType(d["type"]),
            name=d["name"],
            data=d.get("data", {}),
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
        )


@dataclass
class Edge:
    """An edge (relationship) in the memory graph."""
    id: str
    from_id: str
    to_id: str
    relation: RelationType
    weight: float = 1.0
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(
        cls,
        from_id: str,
        to_id: str,
        relation: RelationType,
        weight: float = 1.0,
        data: Dict[str, Any] = None
    ) -> "Edge":
        """Create a new edge with generated ID."""
        return cls(
            id=f"edge_{uuid.uuid4().hex[:8]}",
            from_id=from_id,
            to_id=to_id,
            relation=relation,
            weight=weight,
            data=data or {}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "relation": self.relation.value,
            "weight": self.weight,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Edge":
        """Create from dictionary."""
        return cls(
            id=d["id"],
            from_id=d["from_id"],
            to_id=d["to_id"],
            relation=RelationType(d["relation"]),
            weight=d.get("weight", 1.0),
            data=d.get("data", {}),
            created_at=datetime.fromisoformat(d["created_at"]),
        )


@dataclass
class GraphQueryResult:
    """Result from a graph query."""
    node: Node
    path: List[Edge] = field(default_factory=list)
    distance: int = 0
    relevance: float = 1.0
