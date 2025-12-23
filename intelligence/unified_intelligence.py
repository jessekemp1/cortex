"""Unified Intelligence - Aggregate all intelligence sources."""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ContextPrediction,
    IntelligenceQueryType,
    IntelligenceResult,
    Lesson,
    Pattern,
    ProjectContext,
    Recommendation,
    SessionContext,
    SimilarWork,
    Warning,
)


class UnifiedIntelligence:
    """Unified intelligence aggregator for portfolio-wide insights."""

    def __init__(self, root_dir: Path):
        """
        Initialize with project root directory.

        Args:
            root_dir: Path to development root (e.g., /Users/jesse.kemp/Dev)
        """
        self.root_dir = Path(root_dir)

        # Lazy initialization of sub-systems
        self._spec_kb = None
        self._session_mgr = None
        self._portfolio = None
        self._context_intel = None

    def query(
        self,
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType
    ) -> IntelligenceResult:
        """
        Query all intelligence sources and aggregate results.

        Args:
            user_request: Natural language request (e.g., "enhance golden spec")
            project: Project name (e.g., "cortex")
            query_type: Type of query (spec, architecture, implementation, research)

        Returns:
            IntelligenceResult with aggregated data from all sources
        """
        start_time = time.time()
        sources_queried = []

        # Initialize result components with defaults
        similar_work: List[SimilarWork] = []
        applicable_patterns: List[Pattern] = []
        lessons: List[Lesson] = []
        warnings: List[Warning] = []
        recommendations: List[Recommendation] = []
        project_context: Optional[ProjectContext] = None
        session_context: Optional[SessionContext] = None
        context_predictions: List[ContextPrediction] = []

        # 1. Query SpecKnowledgeBase (semantic similarity)
        similar_work, source = self._query_spec_kb(user_request, project)
        if source:
            sources_queried.append(source)

        # 2. Query SessionManager (current session)
        session_context, source = self._query_session_manager()
        if source:
            sources_queried.append(source)

        # 3. Query PortfolioMemory (patterns + lessons)
        applicable_patterns, lessons, project_context, source = \
            self._query_portfolio(project, query_type)
        if source:
            sources_queried.append(source)

        # 4. Query ContextIntelligence (predictions)
        context_predictions, source = self._query_context_intel(user_request, project)
        if source:
            sources_queried.append(source)

        # 5. Generate warnings and recommendations
        warnings = self._generate_warnings(project, lessons)
        recommendations = self._generate_recommendations(
            query_type, applicable_patterns, similar_work
        )

        query_time_ms = (time.time() - start_time) * 1000

        return IntelligenceResult(
            query_timestamp=datetime.now().isoformat(),
            query_type=query_type,
            project=project,
            similar_work=similar_work,
            applicable_patterns=applicable_patterns,
            lessons=lessons,
            warnings=warnings,
            recommendations=recommendations,
            project_context=project_context,
            session_context=session_context,
            context_predictions=context_predictions,
            reasoning=self._generate_reasoning(query_type, sources_queried),
            query_time_ms=query_time_ms,
            sources_queried=sources_queried
        )

    def _query_spec_kb(
        self, request: str, project: str
    ) -> Tuple[List[SimilarWork], Optional[str]]:
        """Query SpecKnowledgeBase for similar work."""
        try:
            kb = self._get_spec_kb()
            if not kb:
                return [], None
            similar = kb.find_similar(request, k=5, project_filter=project)
            return similar, "spec_knowledge_base"
        except Exception:
            return [], None

    def _query_session_manager(self) -> Tuple[Optional[SessionContext], Optional[str]]:
        """Query SessionManager for current session."""
        try:
            mgr = self._get_session_manager()
            if not mgr:
                return None, None
            context = mgr.load_session_context()
            return context, "session_manager" if context else None
        except Exception:
            return None, None

    def _query_portfolio(
        self, project: str, query_type: IntelligenceQueryType
    ) -> Tuple[List[Pattern], List[Lesson], Optional[ProjectContext], Optional[str]]:
        """Query PortfolioMemory for patterns and lessons."""
        try:
            portfolio = self._get_portfolio()
            if not portfolio:
                return [], [], None, None

            # Get patterns
            patterns_data = portfolio.get_cross_project_patterns()
            patterns = [self._dict_to_pattern(p) for p in patterns_data]

            # Get lessons for this project
            lessons_data = portfolio.get_lessons_learned(project=project)
            lessons = [self._dict_to_lesson(l) for l in lessons_data]

            # Get project context
            ctx_data = portfolio.get_project_context(project)
            project_context = self._dict_to_project_context(ctx_data) if ctx_data else None

            return patterns, lessons, project_context, "portfolio_memory"
        except Exception:
            return [], [], None, None

    def _query_context_intel(
        self, request: str, project: str
    ) -> Tuple[List[ContextPrediction], Optional[str]]:
        """Query ContextIntelligence for predictions."""
        try:
            intel = self._get_context_intel()
            if not intel:
                return [], None

            # Extract keywords from request
            keywords = request.split()[:5]
            predictions = intel.predict_context(
                current_project=project,
                keywords=keywords,
                limit=3
            )

            # Convert to models.ContextPrediction
            result = [
                ContextPrediction(
                    type=p.context_type,
                    relevance_score=p.confidence,
                    content=p.description,
                    source=p.title
                )
                for p in predictions
            ]
            return result, "context_intelligence"
        except Exception:
            return [], None

    def _generate_warnings(
        self, project: str, lessons: List[Lesson]
    ) -> List[Warning]:
        """Generate warnings based on lessons learned."""
        warnings = []

        # Group lessons by category to find high-frequency issues
        category_counts: Dict[str, int] = {}
        category_lessons: Dict[str, List[Lesson]] = {}

        for lesson in lessons:
            cat = lesson.category
            category_counts[cat] = category_counts.get(cat, 0) + lesson.frequency
            if cat not in category_lessons:
                category_lessons[cat] = []
            category_lessons[cat].append(lesson)

        # Create warnings for high-frequency categories
        for category, count in category_counts.items():
            if count >= 3:  # Threshold for warning
                category_lesson_list = category_lessons[category]
                warnings.append(Warning(
                    type=category,
                    severity="medium" if count < 5 else "high",
                    message=f"Repeated issue: {category} ({count} occurrences)",
                    occurrences=count,
                    prevention=category_lesson_list[0].context if category_lesson_list else "",
                    past_examples=[l.lesson for l in category_lesson_list[:3]]
                ))

        return warnings

    def _generate_recommendations(
        self,
        query_type: IntelligenceQueryType,
        patterns: List[Pattern],
        similar_work: List[SimilarWork]
    ) -> List[Recommendation]:
        """Generate strategic recommendations."""
        recommendations = []

        # Recommend patterns based on query type
        if query_type == IntelligenceQueryType.implementation:
            for pattern in patterns[:3]:  # Top 3 patterns
                recommendations.append(Recommendation(
                    type="pattern",
                    priority="high",
                    title=f"Apply {pattern.name} pattern",
                    description=pattern.description,
                    rationale=f"Used in {len(pattern.projects)} projects: {', '.join(pattern.projects)}",
                    related_patterns=[pattern.name]
                ))

        # Recommend similar work for review
        if similar_work:
            top_similar = similar_work[0]
            recommendations.append(Recommendation(
                type="reference",
                priority="medium",
                title=f"Review similar work: {top_similar.title}",
                description=top_similar.summary,
                rationale=f"High similarity score: {top_similar.similarity_score:.2f}",
                related_patterns=top_similar.key_patterns
            ))

        return recommendations

    def _generate_reasoning(
        self, query_type: IntelligenceQueryType, sources: List[str]
    ) -> str:
        """Generate reasoning about the intelligence query."""
        return (
            f"Queried {len(sources)} intelligence sources for {query_type.value} request: "
            f"{', '.join(sources)}"
        )

    # Lazy initialization helpers

    def _get_spec_kb(self):
        """Lazy initialize SpecKnowledgeBase."""
        if self._spec_kb is None:
            try:
                from .spec_knowledge_base import SpecKnowledgeBase
                self._spec_kb = SpecKnowledgeBase()
            except (ImportError, Exception):
                pass
        return self._spec_kb

    def _get_session_manager(self):
        """Lazy initialize SessionManager."""
        if self._session_mgr is None:
            try:
                from .session_manager import SessionManager
                self._session_mgr = SessionManager(self.root_dir)
            except (ImportError, Exception):
                pass
        return self._session_mgr

    def _get_portfolio(self):
        """Lazy initialize PortfolioMemory."""
        if self._portfolio is None:
            try:
                from cortex.portfolio_memory import PortfolioMemory
                self._portfolio = PortfolioMemory()
            except (ImportError, Exception):
                pass
        return self._portfolio

    def _get_context_intel(self):
        """Lazy initialize ContextIntelligence."""
        if self._context_intel is None:
            try:
                from cortex.context_intelligence import ContextIntelligence
                self._context_intel = ContextIntelligence(self.root_dir)
            except (ImportError, Exception):
                pass
        return self._context_intel

    # Dataclass conversion helpers

    def _dict_to_pattern(self, data: Dict[str, Any]) -> Pattern:
        """Convert dict to Pattern dataclass."""
        # PortfolioMemory returns: {pattern, used_in, count}
        projects = [p["project"] for p in data.get("used_in", [])]
        return Pattern(
            name=data.get("pattern", ""),
            description=f"Used in {data.get('count', 0)} projects",
            projects=projects,
            reference=""
        )

    def _dict_to_lesson(self, data: Dict[str, Any]) -> Lesson:
        """Convert dict to Lesson dataclass."""
        # PortfolioMemory returns: {lesson, project, priority, source}
        lesson_text = data.get("lesson", "")
        return Lesson(
            id=f"{data.get('project', '')}_{data.get('source', '')}",
            project=data.get("project", ""),
            category=data.get("source", "common_issues"),
            lesson=lesson_text,
            context=f"Priority: {data.get('priority', 'tier3')}",
            frequency=1,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )

    def _dict_to_project_context(self, data: Dict[str, Any]) -> ProjectContext:
        """Convert dict to ProjectContext dataclass."""
        # PortfolioMemory returns: {project, path, priority, activity_7d, tech_stack, patterns, common_issues, related_projects}
        if "error" in data:
            # Project not found
            return None

        # Extract pattern names from pattern context objects
        patterns_list = data.get("patterns", [])
        pattern_names = [p.get("pattern", "") for p in patterns_list] if patterns_list else []

        return ProjectContext(
            name=data.get("project", ""),
            description=f"Location: {data.get('path', '')}",
            tech_stack=data.get("tech_stack", []),
            status="active" if data.get("activity_7d", 0) > 0 else "inactive",
            patterns_used=pattern_names,
            related_projects=data.get("related_projects", []),
            lessons_count=len(data.get("common_issues", [])),
            last_updated=datetime.now().isoformat()
        )
