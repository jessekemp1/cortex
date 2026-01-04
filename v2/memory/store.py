"""Typed memory store with intent-aware retrieval."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .types import (
    TypedMemory,
    Pattern,
    Incident,
    Skill,
    Decision,
    memory_from_dict,
)
from .decay import TemporalDecay


class TypedMemoryStore:
    """Store for typed memories with smart retrieval.

    Features:
    - Separate storage for each memory type
    - Intent detection from queries
    - Type-appropriate retrieval
    """

    # Query intent patterns
    HOW_TO_PATTERNS = [
        r"^how (do i|to|can i|should i)",
        r"^steps (to|for)",
        r"^guide (to|for)",
        r"^tutorial",
        r"^walkthrough",
    ]

    WHY_PATTERNS = [
        r"^why (did|do|does|is|are|was|were)",
        r"^what caused",
        r"^reason for",
        r"^explain why",
    ]

    WHAT_HAPPENED_PATTERNS = [
        r"^what (happened|went wrong|broke)",
        r"^incident",
        r"^outage",
        r"^failure",
        r"^bug",
        r"^error",
    ]

    SOLUTION_PATTERNS = [
        r"^(best|good) (way|approach|practice)",
        r"^pattern for",
        r"^how (is|are) .* (done|implemented)",
        r"^example of",
    ]

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize store.

        Args:
            data_dir: Directory to store memories. Defaults to ~/.claude/v2/
        """
        if data_dir is None:
            data_dir = Path.home() / ".claude" / "v2"

        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir

        # Separate files for each type
        self.patterns_file = data_dir / "patterns.json"
        self.incidents_file = data_dir / "incidents.json"
        self.skills_file = data_dir / "skills.json"
        self.decisions_file = data_dir / "decisions.json"

        # Load all memories
        self.patterns: List[Pattern] = self._load_memories(self.patterns_file, Pattern)
        self.incidents: List[Incident] = self._load_memories(self.incidents_file, Incident)
        self.skills: List[Skill] = self._load_memories(self.skills_file, Skill)
        self.decisions: List[Decision] = self._load_memories(self.decisions_file, Decision)

    def _load_memories(self, path: Path, mem_type: Type[TypedMemory]) -> List[TypedMemory]:
        """Load memories from a file."""
        if not path.exists():
            return []

        try:
            with open(path) as f:
                data = json.load(f)
                return [memory_from_dict(m) for m in data.get("memories", [])]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_memories(self, path: Path, memories: List[TypedMemory]):
        """Save memories to a file."""
        with open(path, "w") as f:
            json.dump({
                "version": "2.0",
                "type": memories[0].__class__.__name__.lower() if memories else "unknown",
                "count": len(memories),
                "memories": [m.to_dict() for m in memories]
            }, f, indent=2)

    # === CRUD Operations ===

    def add(self, memory: TypedMemory) -> TypedMemory:
        """Add a memory to the appropriate store."""
        if isinstance(memory, Pattern):
            self.patterns.append(memory)
            self._save_memories(self.patterns_file, self.patterns)
        elif isinstance(memory, Incident):
            self.incidents.append(memory)
            self._save_memories(self.incidents_file, self.incidents)
        elif isinstance(memory, Skill):
            self.skills.append(memory)
            self._save_memories(self.skills_file, self.skills)
        elif isinstance(memory, Decision):
            self.decisions.append(memory)
            self._save_memories(self.decisions_file, self.decisions)

        return memory

    def get(self, memory_id: str) -> Optional[TypedMemory]:
        """Get a memory by ID."""
        all_memories = self.patterns + self.incidents + self.skills + self.decisions
        for memory in all_memories:
            if memory.id == memory_id:
                return memory
        return None

    def update(self, memory_id: str, updates: Dict[str, Any]) -> Optional[TypedMemory]:
        """Update a memory."""
        memory = self.get(memory_id)
        if not memory:
            return None

        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)

        # Save to appropriate file
        if isinstance(memory, Pattern):
            self._save_memories(self.patterns_file, self.patterns)
        elif isinstance(memory, Incident):
            self._save_memories(self.incidents_file, self.incidents)
        elif isinstance(memory, Skill):
            self._save_memories(self.skills_file, self.skills)
        elif isinstance(memory, Decision):
            self._save_memories(self.decisions_file, self.decisions)

        return memory

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        # Try each list
        for lst, path in [
            (self.patterns, self.patterns_file),
            (self.incidents, self.incidents_file),
            (self.skills, self.skills_file),
            (self.decisions, self.decisions_file),
        ]:
            for i, memory in enumerate(lst):
                if memory.id == memory_id:
                    lst.pop(i)
                    self._save_memories(path, lst)
                    return True

        return False

    # === Smart Query ===

    def query(
        self,
        query: str,
        types: Optional[List[str]] = None,
        projects: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
        apply_decay: bool = True
    ) -> List[TypedMemory]:
        """Smart query with intent detection.

        Args:
            query: Natural language query
            types: Filter by memory types (pattern, incident, skill, decision)
            projects: Filter by projects
            tags: Filter by tags
            min_confidence: Minimum confidence threshold
            limit: Maximum results
            apply_decay: Apply temporal decay to scoring (default True)

        Returns:
            Matching memories sorted by relevance
        """
        # Detect intent from query to determine types if not specified
        if types is None:
            types = self._detect_intent(query)

        # Get memories of appropriate types
        candidates = []
        for mem_type in types:
            if mem_type == "pattern":
                candidates.extend(self.patterns)
            elif mem_type == "incident":
                candidates.extend(self.incidents)
            elif mem_type == "skill":
                candidates.extend(self.skills)
            elif mem_type == "decision":
                candidates.extend(self.decisions)

        # Filter by projects
        if projects:
            candidates = [
                m for m in candidates
                if any(p in m.projects for p in projects)
            ]

        # Filter by tags
        if tags:
            candidates = [
                m for m in candidates
                if any(t in m.tags for t in tags)
            ]

        # Filter by confidence
        candidates = [m for m in candidates if m.confidence >= min_confidence]

        # Apply temporal decay to set effective_confidence
        if apply_decay:
            decay = TemporalDecay()
            decay.apply_decay(candidates, sort_by_relevance=False)

        # Score and rank
        scored = []
        for memory in candidates:
            score = self._score_match(query, memory, use_decay=apply_decay)
            if score > 0:
                scored.append((score, memory))

        # Sort by score descending
        scored.sort(key=lambda x: (-x[0], -x[1].use_count))

        # Return top results
        results = [memory for _, memory in scored[:limit]]

        # Mark as used
        for memory in results:
            memory.mark_used()

        return results

    def _detect_intent(self, query: str) -> List[str]:
        """Detect query intent to determine memory types.

        Returns:
            List of memory types to search
        """
        query_lower = query.lower().strip()

        # Check how-to patterns → skills, patterns
        for pattern in self.HOW_TO_PATTERNS:
            if re.search(pattern, query_lower):
                return ["skill", "pattern"]

        # Check why patterns → decisions, incidents
        for pattern in self.WHY_PATTERNS:
            if re.search(pattern, query_lower):
                return ["decision", "incident"]

        # Check what happened patterns → incidents
        for pattern in self.WHAT_HAPPENED_PATTERNS:
            if re.search(pattern, query_lower):
                return ["incident"]

        # Check solution patterns → patterns
        for pattern in self.SOLUTION_PATTERNS:
            if re.search(pattern, query_lower):
                return ["pattern"]

        # Default: search all types
        return ["pattern", "skill", "decision", "incident"]

    def _score_match(self, query: str, memory: TypedMemory, use_decay: bool = True) -> float:
        """Score how well a memory matches a query.

        Simple scoring based on term matching.
        TODO: Replace with semantic scoring when embeddings available.

        Args:
            query: Search query
            memory: Memory to score
            use_decay: If True, use effective_confidence (with decay applied)
        """
        query_terms = set(query.lower().split())
        memory_terms = set(memory.title.lower().split()) | set(memory.content.lower().split())

        if not query_terms:
            return 0.0

        # Term overlap
        overlap = query_terms & memory_terms
        term_score = len(overlap) / len(query_terms)

        # Boost for exact phrase match in title
        if query.lower() in memory.title.lower():
            term_score += 0.5

        # Use effective_confidence if decay is applied, otherwise raw confidence
        if use_decay:
            confidence = memory.effective_confidence
        else:
            confidence = memory.confidence

        # Boost for usage (already factored into decay, but still useful for tie-breaking)
        usage_score = min(1.0, memory.use_count / 10)

        # Weighted combination
        # When decay is applied, effective_confidence already includes recency/usage
        return (term_score * 0.7) + (confidence * 0.2) + (usage_score * 0.1)

    # === Convenience Methods ===

    def find_pattern(self, problem: str, project: Optional[str] = None) -> Optional[Pattern]:
        """Find a pattern that solves a problem."""
        results = self.query(
            query=problem,
            types=["pattern"],
            projects=[project] if project else None,
            limit=1
        )
        return results[0] if results else None

    def find_skill(self, task: str, project: Optional[str] = None) -> Optional[Skill]:
        """Find a skill for performing a task."""
        results = self.query(
            query=f"how to {task}",
            types=["skill"],
            projects=[project] if project else None,
            limit=1
        )
        return results[0] if results else None

    def find_incident(self, symptom: str, project: Optional[str] = None) -> Optional[Incident]:
        """Find a past incident matching symptoms."""
        results = self.query(
            query=symptom,
            types=["incident"],
            projects=[project] if project else None,
            limit=1
        )
        return results[0] if results else None

    def find_decision(self, topic: str, project: Optional[str] = None) -> Optional[Decision]:
        """Find a past decision on a topic."""
        results = self.query(
            query=f"why {topic}",
            types=["decision"],
            projects=[project] if project else None,
            limit=1
        )
        return results[0] if results else None

    # === Statistics ===

    def stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        all_memories = self.patterns + self.incidents + self.skills + self.decisions

        return {
            "total": len(all_memories),
            "patterns": len(self.patterns),
            "incidents": len(self.incidents),
            "skills": len(self.skills),
            "decisions": len(self.decisions),
            "by_project": self._count_by_project(all_memories),
            "avg_confidence": sum(m.confidence for m in all_memories) / len(all_memories) if all_memories else 0,
            "total_uses": sum(m.use_count for m in all_memories),
        }

    def _count_by_project(self, memories: List[TypedMemory]) -> Dict[str, int]:
        """Count memories by project."""
        counts = {}
        for memory in memories:
            for project in memory.projects:
                counts[project] = counts.get(project, 0) + 1
        return counts
