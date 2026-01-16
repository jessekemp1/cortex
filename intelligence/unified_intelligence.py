"""Unified Intelligence - Aggregate all intelligence sources."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _get_priority_string(priority) -> str:
    """Convert priority to string, handling both enum and string types."""
    if hasattr(priority, "value"):
        return priority.value
    elif isinstance(priority, str):
        return priority
    return str(priority)


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
        self._metrics_tracker = None
        self._dependency_mapper = None
        self._recommendations_engine = None

        # Performance optimization: query cache
        self._query_cache: Dict[str, Tuple[IntelligenceResult, float]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes

    def query(
        self,
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
        use_cache: bool = True,
        parallel: bool = True,
    ) -> IntelligenceResult:
        """
        Query all intelligence sources and aggregate results.

        Args:
            user_request: Natural language request (e.g., "enhance golden spec")
            project: Project name (e.g., "cortex")
            query_type: Type of query (spec, architecture, implementation, research)
            use_cache: Whether to use query result cache (default: True)
            parallel: Whether to query sources in parallel (default: True)

        Returns:
            IntelligenceResult with aggregated data from all sources
        """
        # Check cache first
        cache_key = f"{user_request}:{project}:{query_type.value}"
        if use_cache and cache_key in self._query_cache:
            cached_result, cache_time = self._query_cache[cache_key]
            if time.time() - cache_time < self._cache_ttl_seconds:
                return cached_result
            else:
                # Expired cache entry
                del self._query_cache[cache_key]

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

        # Query sources in parallel or sequentially
        if parallel:
            # Parallel query execution
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self._query_spec_kb, user_request, project): "spec_kb",
                    executor.submit(self._query_session_manager): "session_mgr",
                    executor.submit(self._query_portfolio, project, query_type): "portfolio",
                    executor.submit(
                        self._query_context_intel, user_request, project
                    ): "context_intel",
                }

                for future in as_completed(futures):
                    source_name = futures[future]
                    try:
                        result = future.result()
                        if source_name == "spec_kb":
                            similar_work, source = result
                            if source:
                                sources_queried.append(source)
                        elif source_name == "session_mgr":
                            session_context, source = result
                            if source:
                                sources_queried.append(source)
                        elif source_name == "portfolio":
                            applicable_patterns, lessons, project_context, source = result
                            if source:
                                sources_queried.append(source)
                        elif source_name == "context_intel":
                            context_predictions, source = result
                            if source:
                                sources_queried.append(source)
                    except Exception:
                        # Continue with other sources if one fails
                        pass
        else:
            # Sequential query execution (original behavior)
            similar_work, source = self._query_spec_kb(user_request, project)
            if source:
                sources_queried.append(source)

            session_context, source = self._query_session_manager()
            if source:
                sources_queried.append(source)

            applicable_patterns, lessons, project_context, source = self._query_portfolio(
                project, query_type
            )
            if source:
                sources_queried.append(source)

            context_predictions, source = self._query_context_intel(user_request, project)
            if source:
                sources_queried.append(source)

        # 5. Generate warnings and recommendations
        warnings = self._generate_warnings(project, lessons, project_context)
        recommendations = self._generate_recommendations(
            query_type, applicable_patterns, similar_work, project_context
        )

        # 6. Calculate confidence scores for all results
        similar_work = self._calculate_confidence_scores(
            similar_work, user_request, project, query_type
        )
        applicable_patterns = self._calculate_pattern_confidence(
            applicable_patterns, user_request, project, query_type
        )
        recommendations = self._calculate_recommendation_confidence(
            recommendations, user_request, project, query_type
        )

        # 7. Rank results by relevance (with recency and pattern success rate)
        similar_work = self._rank_similar_work(similar_work, user_request, project, query_type)
        applicable_patterns = self._rank_patterns(
            applicable_patterns, user_request, project, query_type
        )
        recommendations = self._rank_recommendations(recommendations, query_type)

        # 8. Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(
            similar_work, applicable_patterns, recommendations, context_predictions
        )

        query_time_ms = (time.time() - start_time) * 1000

        # 9. Generate enhanced reasoning
        reasoning = self._generate_enhanced_reasoning(
            query_type,
            user_request,
            project,
            similar_work,
            applicable_patterns,
            recommendations,
            context_predictions,
            overall_confidence,
            sources_queried,
        )

        result = IntelligenceResult(
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
            reasoning=reasoning,
            query_time_ms=query_time_ms,
            sources_queried=sources_queried,
            overall_confidence=overall_confidence,
        )

        # Cache result
        if use_cache:
            self._query_cache[cache_key] = (result, time.time())

        return result

    def _query_spec_kb(self, request: str, project: str) -> Tuple[List[SimilarWork], Optional[str]]:
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

            # Get project context (includes health data by default)
            ctx_data = portfolio.get_project_context(project, include_health=True)
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
            predictions = intel.predict_context(current_project=project, keywords=keywords, limit=3)

            # Convert to models.ContextPrediction
            result = [
                ContextPrediction(
                    type=p.context_type,
                    relevance_score=p.confidence,
                    content=p.description,
                    source=p.title,
                )
                for p in predictions
            ]
            return result, "context_intelligence"
        except Exception:
            return [], None

    def _generate_warnings(
        self,
        project: str,
        lessons: List[Lesson],
        project_context: Optional[ProjectContext] = None,
    ) -> List[Warning]:
        """Generate warnings based on lessons learned and health data."""
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
                warnings.append(
                    Warning(
                        type=category,
                        severity="medium" if count < 5 else "high",
                        message=f"Repeated issue: {category} ({count} occurrences)",
                        occurrences=count,
                        prevention=(
                            category_lesson_list[0].context if category_lesson_list else ""
                        ),
                        past_examples=[l.lesson for l in category_lesson_list[:3]],
                    )
                )

        # Add health-based warnings if available
        if project_context:
            health_data = getattr(project_context, "health_data", None)
            if health_data:
                health_score = health_data.get("score", 0)
                assessment = health_data.get("assessment", "unknown")
                uncommitted = health_data.get("uncommitted_files", 0)

                # Warning for low health score
                if health_score < 50:
                    warnings.append(
                        Warning(
                            type="health",
                            severity="high",
                            message=f"Project health critically low: {health_score}/100 ({assessment})",
                            occurrences=1,
                            prevention="Review recent commits, clean up uncommitted work, increase activity",
                            past_examples=[],
                        )
                    )
                elif health_score < 70:
                    warnings.append(
                        Warning(
                            type="health",
                            severity="medium",
                            message=f"Project health declining: {health_score}/100 ({assessment})",
                            occurrences=1,
                            prevention="Monitor project activity and commit patterns",
                            past_examples=[],
                        )
                    )

                # Warning for high uncommitted changes
                if uncommitted > 20:
                    warnings.append(
                        Warning(
                            type="uncommitted_work",
                            severity="medium",
                            message=f"High uncommitted changes: {uncommitted} files",
                            occurrences=1,
                            prevention="Commit or clean up uncommitted work to improve project health",
                            past_examples=[],
                        )
                    )

        return warnings

    def _generate_recommendations(
        self,
        query_type: IntelligenceQueryType,
        patterns: List[Pattern],
        similar_work: List[SimilarWork],
        project_context: Optional[ProjectContext] = None,
    ) -> List[Recommendation]:
        """Generate strategic recommendations."""
        recommendations = []

        # Recommend patterns based on query type
        if query_type == IntelligenceQueryType.implementation:
            for pattern in patterns[:3]:  # Top 3 patterns
                recommendations.append(
                    Recommendation(
                        type="pattern",
                        priority="high",
                        title=f"Apply {pattern.name} pattern",
                        description=pattern.description,
                        rationale=f"Used in {len(pattern.projects)} projects: {', '.join(pattern.projects)}",
                        related_patterns=[pattern.name],
                    )
                )

        # Recommend similar work for review
        if similar_work:
            top_similar = similar_work[0]
            recommendations.append(
                Recommendation(
                    type="reference",
                    priority="medium",
                    title=f"Review similar work: {top_similar.title}",
                    description=top_similar.summary,
                    rationale=f"High similarity score: {top_similar.similarity_score:.2f}",
                    related_patterns=top_similar.key_patterns,
                )
            )

        # Add health-based recommendations
        if project_context:
            health_data = getattr(project_context, "health_data", None)
            if health_data:
                health_score = health_data.get("score", 0)
                uncommitted = health_data.get("uncommitted_files", 0)
                commits_7d = health_data.get("commits_7d", 0)

                # Recommendation for low activity
                if commits_7d < 3:
                    recommendations.append(
                        Recommendation(
                            type="health",
                            priority="medium",
                            title="Increase project activity",
                            description=f"Only {commits_7d} commits in last 7 days",
                            rationale="Low commit activity negatively impacts project health score",
                            related_patterns=[],
                        )
                    )

                # Recommendation for uncommitted work
                if uncommitted > 10:
                    recommendations.append(
                        Recommendation(
                            type="health",
                            priority="high" if uncommitted > 20 else "medium",
                            title="Review uncommitted work",
                            description=f"{uncommitted} uncommitted files detected",
                            rationale="High uncommitted changes reduce project maintainability and health score",
                            related_patterns=[],
                        )
                    )

                # Recommendation for declining health
                if health_score < 60:
                    recommendations.append(
                        Recommendation(
                            type="health",
                            priority="high",
                            title="Improve project health",
                            description=f"Current health score: {health_score}/100",
                            rationale="Low health score indicates potential maintainability issues",
                            related_patterns=[],
                        )
                    )

        return recommendations

    def _generate_reasoning(self, query_type: IntelligenceQueryType, sources: List[str]) -> str:
        """Generate reasoning about the intelligence query."""
        return (
            f"Queried {len(sources)} intelligence sources for {query_type.value} request: "
            f"{', '.join(sources)}"
        )

    def _calculate_confidence_scores(
        self,
        similar_work: List[SimilarWork],
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
    ) -> List[SimilarWork]:
        """Calculate confidence scores for similar work results."""
        request_lower = user_request.lower()
        request_words = set(request_lower.split())

        for work in similar_work:
            # Base confidence from similarity score (clamp to [0.0, 1.0])
            base_confidence = max(0.0, min(1.0, work.similarity_score))

            # Boost if project matches
            project_boost = 0.1 if work.project.lower() == project.lower() else 0.0

            # Boost if key patterns match request
            pattern_boost = 0.0
            for pattern in work.key_patterns:
                if any(word in pattern.lower() for word in request_words):
                    pattern_boost += 0.05
            pattern_boost = min(pattern_boost, 0.15)

            # Boost if summary contains request keywords
            summary_words = set(work.summary.lower().split())
            keyword_overlap = len(request_words & summary_words) / max(len(request_words), 1)
            keyword_boost = min(keyword_overlap * 0.1, 0.1)

            # Calculate final confidence (clamp to [0.0, 1.0])
            confidence = max(
                0.0,
                min(base_confidence + project_boost + pattern_boost + keyword_boost, 1.0),
            )
            work.confidence_score = confidence

        return similar_work

    def _calculate_pattern_confidence(
        self,
        patterns: List[Pattern],
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
    ) -> List[Pattern]:
        """Calculate confidence scores for pattern applicability."""
        request_lower = user_request.lower()
        request_words = set(request_lower.split())

        for pattern in patterns:
            # Base confidence from cross-project usage
            usage_count = len(pattern.projects)
            base_confidence = min(usage_count / 5.0, 0.7)  # Cap at 0.7 for usage alone

            # Boost if pattern name matches request
            pattern_lower = pattern.name.lower()
            name_match = sum(1 for word in request_words if word in pattern_lower)
            name_boost = min(name_match * 0.1, 0.2)

            # Boost if description matches request
            desc_words = set(pattern.description.lower().split())
            desc_overlap = len(request_words & desc_words) / max(len(request_words), 1)
            desc_boost = min(desc_overlap * 0.1, 0.1)

            # Boost if pattern used in current project
            project_boost = 0.1 if project.lower() in [p.lower() for p in pattern.projects] else 0.0

            # Calculate final confidence (clamp to [0.0, 1.0])
            confidence = max(
                0.0, min(base_confidence + name_boost + desc_boost + project_boost, 1.0)
            )
            pattern.confidence_score = confidence

        return patterns

    def _calculate_recommendation_confidence(
        self,
        recommendations: List[Recommendation],
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
    ) -> List[Recommendation]:
        """Calculate confidence scores for recommendations."""
        request_lower = user_request.lower()

        for rec in recommendations:
            # Base confidence from priority
            priority_map = {"high": 0.8, "medium": 0.6, "low": 0.4}
            base_confidence = priority_map.get(_get_priority_string(rec.priority).lower(), 0.5)

            # Boost if title matches request
            title_lower = rec.title.lower()
            title_match = sum(1 for word in request_lower.split() if word in title_lower)
            title_boost = min(title_match * 0.05, 0.1)

            # Boost if description matches request
            desc_lower = rec.description.lower()
            desc_match = sum(1 for word in request_lower.split() if word in desc_lower)
            desc_boost = min(desc_match * 0.05, 0.1)

            # Type-specific boosts
            type_boost = 0.0
            if rec.type == "pattern" and query_type == IntelligenceQueryType.implementation:
                type_boost = 0.1
            elif rec.type == "reference" and query_type == IntelligenceQueryType.spec:
                type_boost = 0.1

            # Calculate final confidence (clamp to [0.0, 1.0])
            confidence = max(0.0, min(base_confidence + title_boost + desc_boost + type_boost, 1.0))
            rec.confidence_score = confidence

        return recommendations

    def _rank_similar_work(
        self,
        similar_work: List[SimilarWork],
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
    ) -> List[SimilarWork]:
        """Rank similar work by relevance score with recency weighting."""
        request_lower = user_request.lower()
        request_words = set(request_lower.split())

        # Get current time for recency calculation
        now = datetime.now()

        for work in similar_work:
            # Relevance factors (updated weights)
            similarity_weight = 0.35
            confidence_weight = 0.25
            project_match_weight = 0.15
            keyword_match_weight = 0.10
            recency_weight = 0.15

            # Calculate components
            similarity_component = work.similarity_score * similarity_weight
            confidence_component = work.confidence_score * confidence_weight

            # Project match
            project_match = 1.0 if work.project.lower() == project.lower() else 0.0
            project_component = project_match * project_match_weight

            # Keyword match in summary
            summary_words = set(work.summary.lower().split())
            keyword_overlap = len(request_words & summary_words) / max(len(request_words), 1)
            keyword_component = keyword_overlap * keyword_match_weight

            # Recency component (if reference_path contains timestamp or we can infer from context)
            # For now, use a default recency score based on project activity
            # In future, could parse timestamps from reference_path or metadata
            recency_score = self._calculate_recency_score(work, now)
            recency_component = recency_score * recency_weight

            # Calculate relevance score
            relevance = (
                similarity_component
                + confidence_component
                + project_component
                + keyword_component
                + recency_component
            )
            work.relevance_score = relevance

        # Sort by relevance (descending)
        return sorted(similar_work, key=lambda w: w.relevance_score, reverse=True)

    def _rank_patterns(
        self,
        patterns: List[Pattern],
        user_request: str,
        project: str,
        query_type: IntelligenceQueryType,
    ) -> List[Pattern]:
        """Rank patterns by relevance score with pattern success rate weighting."""
        request_lower = user_request.lower()
        request_words = set(request_lower.split())

        for pattern in patterns:
            # Relevance factors (updated weights)
            confidence_weight = 0.30
            usage_weight = 0.25
            name_match_weight = 0.15
            project_match_weight = 0.10
            success_rate_weight = 0.20

            # Calculate components
            confidence_component = pattern.confidence_score * confidence_weight

            # Usage count (normalized)
            usage_count = len(pattern.projects)
            usage_component = min(usage_count / 5.0, 1.0) * usage_weight

            # Name match
            pattern_lower = pattern.name.lower()
            name_match = sum(1 for word in request_words if word in pattern_lower)
            name_component = min(name_match / max(len(request_words), 1), 1.0) * name_match_weight

            # Project match
            project_match = 1.0 if project.lower() in [p.lower() for p in pattern.projects] else 0.0
            project_component = project_match * project_match_weight

            # Pattern success rate (from metrics tracker or portfolio)
            success_rate = self._get_pattern_success_rate(pattern.name)
            success_rate_component = success_rate * success_rate_weight

            # Calculate relevance score
            relevance = (
                confidence_component
                + usage_component
                + name_component
                + project_component
                + success_rate_component
            )
            pattern.relevance_score = relevance

        # Sort by relevance (descending)
        return sorted(patterns, key=lambda p: p.relevance_score, reverse=True)

    def _rank_recommendations(
        self, recommendations: List[Recommendation], query_type: IntelligenceQueryType
    ) -> List[Recommendation]:
        """Rank recommendations by relevance score."""
        priority_map = {"high": 1.0, "medium": 0.6, "low": 0.3}

        for rec in recommendations:
            # Relevance factors
            confidence_weight = 0.5
            priority_weight = 0.3
            type_match_weight = 0.2

            # Calculate components
            confidence_component = rec.confidence_score * confidence_weight

            # Priority component
            priority_score = priority_map.get(_get_priority_string(rec.priority).lower(), 0.5)
            priority_component = priority_score * priority_weight

            # Type match with query type
            type_match = 0.0
            if rec.type == "pattern" and query_type == IntelligenceQueryType.implementation:
                type_match = 1.0
            elif rec.type == "reference" and query_type == IntelligenceQueryType.spec:
                type_match = 1.0
            elif rec.type == "health" and query_type == IntelligenceQueryType.architecture:
                type_match = 0.8
            type_component = type_match * type_match_weight

            # Calculate relevance score
            relevance = confidence_component + priority_component + type_component
            rec.relevance_score = relevance

        # Sort by relevance (descending)
        return sorted(recommendations, key=lambda r: r.relevance_score, reverse=True)

    def _calculate_overall_confidence(
        self,
        similar_work: List[SimilarWork],
        patterns: List[Pattern],
        recommendations: List[Recommendation],
        context_predictions: List[ContextPrediction],
    ) -> float:
        """Calculate overall confidence in query results."""
        if not any([similar_work, patterns, recommendations, context_predictions]):
            return 0.0

        # Weighted average of component confidences
        weights = []
        confidences = []

        # Similar work confidence (weighted by count)
        if similar_work:
            avg_similar_confidence = sum(w.confidence_score for w in similar_work) / len(
                similar_work
            )
            weights.append(0.3)
            confidences.append(avg_similar_confidence)

        # Pattern confidence
        if patterns:
            avg_pattern_confidence = sum(p.confidence_score for p in patterns) / len(patterns)
            weights.append(0.25)
            confidences.append(avg_pattern_confidence)

        # Recommendation confidence
        if recommendations:
            avg_rec_confidence = sum(r.confidence_score for r in recommendations) / len(
                recommendations
            )
            weights.append(0.25)
            confidences.append(avg_rec_confidence)

        # Context prediction confidence
        if context_predictions:
            avg_context_confidence = sum(p.relevance_score for p in context_predictions) / len(
                context_predictions
            )
            weights.append(0.2)
            confidences.append(avg_context_confidence)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        normalized_weights = [w / total_weight for w in weights]

        # Calculate weighted average
        overall = sum(w * c for w, c in zip(normalized_weights, confidences))
        return min(overall, 1.0)

    def _generate_enhanced_reasoning(
        self,
        query_type: IntelligenceQueryType,
        user_request: str,
        project: str,
        similar_work: List[SimilarWork],
        patterns: List[Pattern],
        recommendations: List[Recommendation],
        context_predictions: List[ContextPrediction],
        overall_confidence: float,
        sources_queried: List[str],
    ) -> str:
        """Generate detailed reasoning for query results with explanations."""
        reasoning_parts = []

        # Introduction
        reasoning_parts.append(
            f"Query: '{user_request}' for project '{project}' ({query_type.value})"
        )
        reasoning_parts.append(
            f"Queried {len(sources_queried)} sources: {', '.join(sources_queried)}"
        )
        reasoning_parts.append(f"Overall confidence: {overall_confidence:.0%}")

        # Top similar work with detailed explanation
        if similar_work:
            top_work = similar_work[0]
            reasoning_parts.append(
                f"\nTop similar work: '{top_work.title}' "
                f"(similarity: {top_work.similarity_score:.0%}, "
                f"confidence: {top_work.confidence_score:.0%}, "
                f"relevance: {top_work.relevance_score:.0%})"
            )
            reasoning_parts.append(
                f"  Why relevant: This work matches your query with {top_work.similarity_score:.0%} "
                f"semantic similarity. "
            )
            if top_work.project.lower() == project.lower():
                reasoning_parts.append(
                    "  Project match: This work is from the same project, increasing relevance."
                )
            if top_work.key_patterns:
                reasoning_parts.append(
                    f"  Key patterns: {', '.join(top_work.key_patterns[:3])} - "
                    f"these patterns may be applicable to your current task."
                )
            if top_work.summary:
                reasoning_parts.append(f"  Summary: {top_work.summary[:200]}...")
        else:
            reasoning_parts.append(
                "\nNo similar work found: Consider refining your query or checking if "
                "relevant specifications exist in the knowledge base."
            )

        # Top patterns with success rate explanation
        if patterns:
            top_pattern = patterns[0]
            success_rate = self._get_pattern_success_rate(top_pattern.name)
            reasoning_parts.append(
                f"\nTop pattern: '{top_pattern.name}' "
                f"(used in {len(top_pattern.projects)} projects, "
                f"confidence: {top_pattern.confidence_score:.0%}, "
                f"relevance: {top_pattern.relevance_score:.0%})"
            )
            reasoning_parts.append(
                f"  Why applicable: This pattern has been used in {len(top_pattern.projects)} projects, "
                f"indicating cross-project applicability."
            )
            if success_rate > 0.7:
                reasoning_parts.append(
                    f"  Success rate: {success_rate:.0%} - this pattern has a high success rate "
                    f"across projects."
                )
            elif success_rate < 0.5:
                reasoning_parts.append(
                    f"  Success rate: {success_rate:.0%} - consider reviewing pattern effectiveness "
                    f"before applying."
                )
            if top_pattern.description:
                reasoning_parts.append(f"  Description: {top_pattern.description[:200]}...")
        else:
            reasoning_parts.append(
                "\nNo applicable patterns found: This may be a novel task or the pattern library "
                "needs expansion."
            )

        # Top recommendations with detailed rationale
        if recommendations:
            top_rec = recommendations[0]
            reasoning_parts.append(
                f"\nTop recommendation: '{top_rec.title}' "
                f"(priority: {top_rec.priority}, "
                f"confidence: {top_rec.confidence_score:.0%}, "
                f"relevance: {top_rec.relevance_score:.0%})"
            )
            reasoning_parts.append(f"  Rationale: {top_rec.rationale}")
            reasoning_parts.append(
                f"  Why this matters: This recommendation is prioritized as '{top_rec.priority}' "
                f"because it aligns with your query type ({query_type.value}) and has strong "
                f"confidence ({top_rec.confidence_score:.0%})."
            )
            if top_rec.related_patterns:
                reasoning_parts.append(
                    f"  Related patterns: {', '.join(top_rec.related_patterns[:3])} - "
                    f"consider these patterns when implementing."
                )
        else:
            reasoning_parts.append(
                "\nNo specific recommendations: The query may be too broad or no clear action "
                "items were identified."
            )

        # Context predictions
        if context_predictions:
            reasoning_parts.append(
                f"\nFound {len(context_predictions)} relevant context predictions:"
            )
            for i, pred in enumerate(context_predictions[:3], 1):
                reasoning_parts.append(
                    f"  {i}. {pred.type} from {pred.source} "
                    f"(relevance: {pred.relevance_score:.0%})"
                )
                if pred.content:
                    reasoning_parts.append(f"     {pred.content[:150]}...")

        # Confidence rationale with actionable guidance
        reasoning_parts.append("\n--- Confidence Analysis ---")
        if overall_confidence >= 0.8:
            reasoning_parts.append(
                "High confidence: Multiple strong signals from different sources. "
                "The results are highly relevant and actionable."
            )
        elif overall_confidence >= 0.6:
            reasoning_parts.append(
                "Moderate confidence: Some relevant results found. "
                "Consider reviewing the top results and refining your query if needed."
            )
        else:
            reasoning_parts.append(
                "Lower confidence: Limited relevant results found. "
                "Consider: (1) refining your query with more specific terms, "
                "(2) checking if relevant specifications or patterns exist, "
                "(3) expanding the knowledge base with relevant content."
            )

        # Source quality assessment
        if len(sources_queried) >= 3:
            reasoning_parts.append(
                f"\nSource coverage: {len(sources_queried)} sources queried - comprehensive coverage."
            )
        elif len(sources_queried) == 2:
            reasoning_parts.append(
                f"\nSource coverage: {len(sources_queried)} sources queried - moderate coverage."
            )
        else:
            reasoning_parts.append(
                f"\nSource coverage: {len(sources_queried)} source(s) queried - limited coverage. "
                "Some intelligence sources may be unavailable."
            )

        return "\n".join(reasoning_parts)

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

    def _get_metrics_tracker(self):
        """Lazy initialize MetricsTracker."""
        if self._metrics_tracker is None:
            try:
                from cortex.metrics_tracker import MetricsTracker

                self._metrics_tracker = MetricsTracker()
            except (ImportError, Exception):
                pass
        return self._metrics_tracker

    def _get_dependency_mapper(self):
        """Lazy initialize DependencyMapper."""
        if self._dependency_mapper is None:
            try:
                from cortex.agents.data_agent.analyzers.dependency_mapper import (
                    DependencyMapper,
                )

                self._dependency_mapper = DependencyMapper()
            except (ImportError, Exception):
                pass
        return self._dependency_mapper

    def _get_recommendations_engine(self):
        """Lazy initialize RecommendationEngine."""
        if self._recommendations_engine is None:
            try:
                from cortex.recommendations import RecommendationEngine

                self._recommendations_engine = RecommendationEngine(self.root_dir)
            except (ImportError, Exception):
                pass
        return self._recommendations_engine

    def get_dependency_context(self, project: str) -> Optional[Dict[str, Any]]:
        """
        Get dependency analysis context for a project.

        Args:
            project: Project name

        Returns:
            Dict with dependency health, external deps count, circular deps
        """
        mapper = self._get_dependency_mapper()
        if not mapper:
            return None

        # Map project name to path
        project_paths = {
            "cortex": self.root_dir / "cortex",
            "VortexV2": self.root_dir / "Vortex" / "VortexV2",
            "alpha_arena": self.root_dir / "alpha_arena",
            "DJ-CoPilot": self.root_dir / "DJ-CoPilot",
        }

        path = project_paths.get(project)
        if not path or not path.exists():
            return None

        try:
            health = mapper.get_health_score(path)
            return {
                "health_score": health.get("total_score", 0),
                "external_deps": len(health.get("external_deps", [])),
                "has_circular": health.get("circular_dependencies", {}).get("has_cycles", False),
                "concerns": health.get("concerns", []),
            }
        except Exception:
            return None

    def get_smart_recommendations(self) -> Dict[str, Any]:
        """
        Get smart recommendations from the RecommendationEngine.

        Returns:
            Full recommendations report
        """
        engine = self._get_recommendations_engine()
        if not engine:
            return {"error": "RecommendationEngine not available"}

        try:
            return engine.get_full_report()
        except Exception as e:
            return {"error": str(e)}

    def _calculate_recency_score(self, work: SimilarWork, now: datetime) -> float:
        """
        Calculate recency score for similar work.

        Args:
            work: SimilarWork object
            now: Current datetime

        Returns:
            Recency score (0.0-1.0), where 1.0 is most recent
        """
        # Try to extract timestamp from reference_path or use default
        # For now, use a heuristic based on project activity
        # In future, could parse timestamps from file metadata or git history

        # Default: assume moderate recency if we can't determine
        # This could be enhanced by checking file modification times
        # or git commit dates for the reference_path
        return 0.7  # Default moderate recency

    def _get_pattern_success_rate(self, pattern_name: str) -> float:
        """
        Get pattern success rate from metrics tracker or portfolio.

        Args:
            pattern_name: Name of the pattern

        Returns:
            Success rate (0.0-1.0), default 0.5 if unknown
        """
        # Try metrics tracker first
        metrics = self._get_metrics_tracker()
        if metrics:
            try:
                validation = metrics.validate_pattern_success_rate(pattern_name)
                success_rate = validation.get("success_rate", 0.0)
                if success_rate > 0:
                    return min(success_rate, 1.0)
            except Exception:
                pass

        # Fallback: check portfolio for pattern metadata
        portfolio = self._get_portfolio()
        if portfolio:
            try:
                patterns = portfolio.get_cross_project_patterns()
                for pattern_data in patterns:
                    if pattern_data.get("pattern", "").lower() == pattern_name.lower():
                        # Extract success rate from pattern metadata if available
                        success_rate_str = pattern_data.get("success_rate", "")
                        if isinstance(success_rate_str, str) and "%" in success_rate_str:
                            try:
                                rate = float(success_rate_str.replace("%", "")) / 100.0
                                return min(rate, 1.0)
                            except (ValueError, AttributeError):
                                pass
            except Exception:
                pass

        # Default: moderate success rate if unknown
        return 0.5

    # Dataclass conversion helpers

    def _dict_to_pattern(self, data: Dict[str, Any]) -> Pattern:
        """Convert dict to Pattern dataclass."""
        # PortfolioMemory returns: {pattern, used_in, count}
        projects = [p["project"] for p in data.get("used_in", [])]
        return Pattern(
            name=data.get("pattern", ""),
            description=f"Used in {data.get('count', 0)} projects",
            projects=projects,
            reference="",
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
            last_seen=datetime.now().isoformat(),
        )

    def _dict_to_project_context(self, data: Dict[str, Any]) -> ProjectContext:
        """Convert dict to ProjectContext dataclass."""
        # PortfolioMemory returns: {project, path, priority, activity_7d, tech_stack, patterns, common_issues, related_projects, health}
        if "error" in data:
            # Project not found
            return None

        # Extract pattern names from pattern context objects
        patterns_list = data.get("patterns", [])
        pattern_names = [p.get("pattern", "") for p in patterns_list] if patterns_list else []

        # Extract health data if available
        health_data = data.get("health", None)

        return ProjectContext(
            name=data.get("project", ""),
            description=f"Location: {data.get('path', '')}",
            tech_stack=data.get("tech_stack", []),
            status="active" if data.get("activity_7d", 0) > 0 else "inactive",
            patterns_used=pattern_names,
            related_projects=data.get("related_projects", []),
            lessons_count=len(data.get("common_issues", [])),
            last_updated=datetime.now().isoformat(),
            health_data=health_data,
        )
