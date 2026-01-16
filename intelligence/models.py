"""Data models for Cortex Intelligence System."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IntelligenceQueryType(Enum):
    """Types of intelligence queries."""

    spec = "spec"
    architecture = "architecture"
    implementation = "implementation"
    research = "research"


@dataclass
class SimilarWork:
    """Represents similar work found via semantic search."""

    id: str
    title: str
    type: str
    similarity_score: float
    project: str
    summary: str
    key_patterns: List[str]
    lessons_learned: List[str]
    reference_path: str
    confidence_score: float = 0.0  # Confidence in this result (0.0-1.0)
    relevance_score: float = 0.0  # Overall relevance score for ranking


@dataclass
class Pattern:
    """Cross-project pattern."""

    name: str
    description: str
    projects: List[str]
    reference: str
    confidence_score: float = 0.0  # Confidence in pattern applicability
    relevance_score: float = 0.0  # Relevance score for ranking


@dataclass
class Lesson:
    """Lesson learned from portfolio."""

    id: str
    project: str
    category: str
    lesson: str
    context: str
    frequency: int
    first_seen: str
    last_seen: str


@dataclass
class Warning:
    """Warning about repeated mistakes."""

    type: str
    severity: str
    message: str
    occurrences: int
    prevention: str
    past_examples: List[str]


@dataclass
class Recommendation:
    """Strategic recommendation."""

    type: str
    priority: str
    title: str
    description: str
    rationale: str
    related_patterns: List[str]
    confidence_score: float = 0.0  # Confidence in recommendation
    relevance_score: float = 0.0  # Relevance score for ranking


@dataclass
class ProjectContext:
    """Project-specific context."""

    name: str
    description: str
    tech_stack: List[str]
    status: str
    patterns_used: List[str]
    related_projects: List[str]
    lessons_count: int
    last_updated: str
    health_data: Optional[Dict[str, Any]] = None


@dataclass
class SessionContext:
    """Current session context."""

    project: str
    working_directory: str
    recent_work: List[Dict[str, Any]]
    active_goals: List[str]
    current_focus: str
    last_updated: str


@dataclass
class ContextPrediction:
    """Predicted relevant context."""

    type: str
    relevance_score: float
    content: str
    source: str


@dataclass
class IntelligenceResult:
    """Complete result from unified intelligence query."""

    query_timestamp: str
    query_type: IntelligenceQueryType
    project: str
    similar_work: List[SimilarWork]
    applicable_patterns: List[Pattern]
    lessons: List[Lesson]
    warnings: List[Warning]
    recommendations: List[Recommendation]
    project_context: Optional[ProjectContext]
    session_context: Optional[SessionContext]
    context_predictions: List[ContextPrediction] = field(default_factory=list)
    reasoning: Optional[str] = None
    query_time_ms: float = 0.0
    sources_queried: List[str] = field(default_factory=list)
    overall_confidence: float = 0.0  # Overall confidence in results (0.0-1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        from dataclasses import asdict

        result = asdict(self)
        result["query_type"] = self.query_type.value
        return result
