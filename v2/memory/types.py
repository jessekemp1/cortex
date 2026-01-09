"""Typed memory definitions for V2.

Memory types:
- Pattern: Reusable solutions (Redis for caching, JWT for auth)
- Incident: What went wrong (production outage, data corruption)
- Skill: Step-by-step procedures (deploy to prod, setup dev env)
- Decision: Why we chose X over Y (chose Postgres over MySQL because...)
- Fact: General knowledge (API rate limit is 1000/min)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class TypedMemory:
    """Base class for all typed memories."""
    id: str
    title: str
    content: str
    projects: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    use_count: int = 0
    # Effective confidence after decay (set by TemporalDecay.apply_decay)
    effective_confidence: float = field(default=0.5, compare=False, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.__class__.__name__.lower(),
            "title": self.title,
            "content": self.content,
            "projects": self.projects,
            "tags": self.tags,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count,
        }

    def mark_used(self):
        """Mark this memory as used."""
        self.last_used = datetime.utcnow()
        self.use_count += 1


@dataclass
class Pattern(TypedMemory):
    """A reusable solution pattern.

    Example: "Use Redis for session caching in FastAPI"
    """
    problem: str = ""
    solution: str = ""
    context: str = ""  # When to use this pattern
    anti_patterns: List[str] = field(default_factory=list)  # When NOT to use
    outcome_ids: List[str] = field(default_factory=list)  # Linked outcomes

    @classmethod
    def create(
        cls,
        title: str,
        problem: str,
        solution: str,
        context: str = "",
        projects: List[str] = None,
        tags: List[str] = None
    ) -> "Pattern":
        """Create a new pattern."""
        return cls(
            id=f"pattern_{uuid.uuid4().hex[:8]}",
            title=title,
            content=f"Problem: {problem}\n\nSolution: {solution}",
            problem=problem,
            solution=solution,
            context=context,
            projects=projects or [],
            tags=tags or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "problem": self.problem,
            "solution": self.solution,
            "context": self.context,
            "anti_patterns": self.anti_patterns,
            "outcome_ids": self.outcome_ids,
        })
        return d


@dataclass
class Incident(TypedMemory):
    """A record of what went wrong.

    Example: "Production outage caused by Redis connection exhaustion"
    """
    what_happened: str = ""
    root_cause: str = ""
    resolution: str = ""
    prevention: str = ""  # How to prevent recurrence
    severity: str = "minor"  # critical, major, minor

    @classmethod
    def create(
        cls,
        title: str,
        what_happened: str,
        root_cause: str,
        resolution: str,
        severity: str = "minor",
        projects: List[str] = None
    ) -> "Incident":
        """Create a new incident."""
        return cls(
            id=f"incident_{uuid.uuid4().hex[:8]}",
            title=title,
            content=f"What happened: {what_happened}\n\nRoot cause: {root_cause}\n\nResolution: {resolution}",
            what_happened=what_happened,
            root_cause=root_cause,
            resolution=resolution,
            severity=severity,
            projects=projects or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "what_happened": self.what_happened,
            "root_cause": self.root_cause,
            "resolution": self.resolution,
            "prevention": self.prevention,
            "severity": self.severity,
        })
        return d


@dataclass
class Skill(TypedMemory):
    """A step-by-step procedure.

    Example: "How to deploy VortexV2 to production"
    """
    steps: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    estimated_time: str = ""  # "30 minutes", "2 hours"
    difficulty: str = "medium"  # easy, medium, hard

    @classmethod
    def create(
        cls,
        title: str,
        steps: List[str],
        prerequisites: List[str] = None,
        estimated_time: str = "",
        difficulty: str = "medium",
        projects: List[str] = None
    ) -> "Skill":
        """Create a new skill."""
        steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
        return cls(
            id=f"skill_{uuid.uuid4().hex[:8]}",
            title=title,
            content=f"Steps:\n{steps_text}",
            steps=steps,
            prerequisites=prerequisites or [],
            estimated_time=estimated_time,
            difficulty=difficulty,
            projects=projects or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "steps": self.steps,
            "prerequisites": self.prerequisites,
            "estimated_time": self.estimated_time,
            "difficulty": self.difficulty,
        })
        return d


@dataclass
class Decision(TypedMemory):
    """A record of why we chose X over Y.

    Example: "Chose PostgreSQL over MySQL for VortexV2 database"
    """
    question: str = ""  # The decision we faced
    chosen_option: str = ""
    alternatives: List[str] = field(default_factory=list)
    rationale: str = ""  # Why we chose this
    outcome: str = ""  # How it turned out (retrospective)

    @classmethod
    def create(
        cls,
        title: str,
        question: str,
        chosen_option: str,
        alternatives: List[str],
        rationale: str,
        projects: List[str] = None
    ) -> "Decision":
        """Create a new decision."""
        alt_text = ", ".join(alternatives) if alternatives else "none"
        return cls(
            id=f"decision_{uuid.uuid4().hex[:8]}",
            title=title,
            content=f"Question: {question}\n\nChose: {chosen_option}\n\nAlternatives: {alt_text}\n\nRationale: {rationale}",
            question=question,
            chosen_option=chosen_option,
            alternatives=alternatives,
            rationale=rationale,
            projects=projects or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "question": self.question,
            "chosen_option": self.chosen_option,
            "alternatives": self.alternatives,
            "rationale": self.rationale,
            "outcome": self.outcome,
        })
        return d


@dataclass
class Goal(TypedMemory):
    """A tracked goal or objective.

    Example: "Ship VortexV2 production API by end of week"
    """
    status: str = "active"  # active, completed, blocked, abandoned
    progress: int = 0  # 0-100 percent
    deadline: Optional[str] = None  # ISO date string
    success_criteria: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    parent_goal_id: Optional[str] = None  # For sub-goals
    outcome_ids: List[str] = field(default_factory=list)  # Linked outcomes

    @classmethod
    def create(
        cls,
        title: str,
        description: str = "",
        deadline: str = None,
        success_criteria: List[str] = None,
        projects: List[str] = None,
        progress: int = 0
    ) -> "Goal":
        """Create a new goal."""
        return cls(
            id=f"goal_{uuid.uuid4().hex[:8]}",
            title=title,
            content=description,
            deadline=deadline,
            success_criteria=success_criteria or [],
            projects=projects or [],
            progress=progress,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "status": self.status,
            "progress": self.progress,
            "deadline": self.deadline,
            "success_criteria": self.success_criteria,
            "blockers": self.blockers,
            "parent_goal_id": self.parent_goal_id,
            "outcome_ids": self.outcome_ids,
        })
        return d


# Type registry for deserialization
MEMORY_TYPES = {
    "pattern": Pattern,
    "incident": Incident,
    "skill": Skill,
    "decision": Decision,
    "goal": Goal,
}


def memory_from_dict(d: Dict[str, Any]) -> TypedMemory:
    """Create a typed memory from dictionary."""
    mem_type = d.get("type", "pattern")
    cls = MEMORY_TYPES.get(mem_type, Pattern)

    # Common fields
    common = {
        "id": d["id"],
        "title": d["title"],
        "content": d["content"],
        "projects": d.get("projects", []),
        "tags": d.get("tags", []),
        "confidence": d.get("confidence", 0.5),
        "created_at": datetime.fromisoformat(d["created_at"]),
        "last_used": datetime.fromisoformat(d["last_used"]),
        "use_count": d.get("use_count", 0),
    }

    # Type-specific fields
    if cls == Pattern:
        return Pattern(
            **common,
            problem=d.get("problem", ""),
            solution=d.get("solution", ""),
            context=d.get("context", ""),
            anti_patterns=d.get("anti_patterns", []),
            outcome_ids=d.get("outcome_ids", []),
        )
    elif cls == Incident:
        return Incident(
            **common,
            what_happened=d.get("what_happened", ""),
            root_cause=d.get("root_cause", ""),
            resolution=d.get("resolution", ""),
            prevention=d.get("prevention", ""),
            severity=d.get("severity", "minor"),
        )
    elif cls == Skill:
        return Skill(
            **common,
            steps=d.get("steps", []),
            prerequisites=d.get("prerequisites", []),
            estimated_time=d.get("estimated_time", ""),
            difficulty=d.get("difficulty", "medium"),
        )
    elif cls == Decision:
        return Decision(
            **common,
            question=d.get("question", ""),
            chosen_option=d.get("chosen_option", ""),
            alternatives=d.get("alternatives", []),
            rationale=d.get("rationale", ""),
            outcome=d.get("outcome", ""),
        )
    elif cls == Goal:
        return Goal(
            **common,
            status=d.get("status", "active"),
            progress=d.get("progress", 0),
            deadline=d.get("deadline"),
            success_criteria=d.get("success_criteria", []),
            blockers=d.get("blockers", []),
            parent_goal_id=d.get("parent_goal_id"),
            outcome_ids=d.get("outcome_ids", []),
        )

    return TypedMemory(**common)
