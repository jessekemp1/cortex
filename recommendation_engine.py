"""
Recommendation Engine - Layer 4 Integration

Complete recommendation system integrating all 4 layers:
- Layer 1: Project Analysis
- Layer 2: Pattern Memory
- Layer 3: Warning System & Metrics
- Layer 4: Smart Recommendations

This is the top-level API for the Cortex Intelligence Stack.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Layer 3: Warning System
from intelligence.monitoring.metric_tracker import MetricTracker
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.monitoring.alert_generator import AlertGenerator

# Layer 4: Smart Recommendations
from intelligence.recommendations.file_selector import FileSelector
from intelligence.recommendations.smart_generator import SmartRecommendationGenerator
from intelligence.recommendations.alert_adapter import adapt_alerts

# Layer 5: Planning
from intelligence.planning import Planner, PlanExecutor, Plan, PlanPriority


@dataclass
class Task:
    """Represents a task (placeholder for now)."""
    id: str
    title: str
    status: str
    metadata: Dict[str, Any] = None


@dataclass
class Goal:
    """Represents a project goal (placeholder for now)."""
    id: str
    name: str
    target_value: float
    current_value: float
    metric_type: str


@dataclass
class Recommendation:
    """Recommendation from the engine."""
    type: str
    title: str
    description: str
    priority: int
    confidence: float
    files: List[str] = None
    steps: List[str] = None
    metadata: Dict[str, Any] = None


class RecommendationEngine:
    """
    Top-level recommendation engine integrating all intelligence layers.

    This class provides the main API for generating smart, context-aware
    recommendations based on project health, goals, patterns, and metrics.
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        enable_learning: bool = True,
        enable_patterns: bool = True
    ):
        """
        Initialize the recommendation engine.

        Args:
            project_path: Path to project (defaults to current directory)
            enable_learning: Enable Layer 3 learning system
            enable_patterns: Enable Layer 2 pattern memory
        """
        self.project_path = project_path or Path.cwd()

        # Layer 3: Warning System components
        self.metric_tracker = MetricTracker()
        self.trend_analyzer = TrendAnalyzer(self.metric_tracker)
        self.alert_generator = AlertGenerator(self.trend_analyzer)

        # Layer 4: Smart Recommendations components
        self.file_selector = FileSelector(self.project_path)
        self.smart_generator = SmartRecommendationGenerator(
            file_selector=self.file_selector
        )

        # Layer 5: Planning
        self.planner = Planner()
        self.plan_executor = PlanExecutor()

        # Layer 2: Pattern Memory
        self.pattern_memory = None
        if enable_patterns:
            try:
                from intelligence.memory import PatternMemory
                self.pattern_memory = PatternMemory(root_dir=self.project_path.parent)
            except ImportError:
                pass

        # Layer 1: Project Analysis
        self.project_profiler = None
        if enable_learning:  # Using enable_learning flag for profiler
            try:
                from intelligence.analysis import ProjectProfiler
                self.project_profiler = ProjectProfiler(self.project_path)
            except ImportError:
                pass

    def generate_recommendations(
        self,
        tasks: List[Task] = None,
        goals: List[Goal] = None,
        context: Dict[str, Any] = None,
        limit: int = 10
    ) -> List[Recommendation]:
        """
        Generate prioritized recommendations using smart intelligence.

        Args:
            tasks: Current task list
            goals: Active goals
            context: Current work context (files, recent actions, etc.)
            limit: Maximum recommendations to return

        Returns:
            Sorted list of intelligent recommendations
        """
        tasks = tasks or []
        goals = goals or []
        context = context or {}

        recommendations = []

        # Get current project name
        project_name = self.project_path.name

        # Enrich context with alerts from Layer 3
        alerts = self.alert_generator.generate_alerts(project_name, days=7)
        if alerts:
            # Adapt alerts to Layer 4 format
            adapted_alerts = adapt_alerts(alerts)
            context["alerts"] = [
                {
                    "id": a.id,
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message
                }
                for a in adapted_alerts
            ]

        # 1. Alert-driven recommendations (from Layer 3)
        if alerts:
            alert_recs = self.smart_generator.generate_alert_recommendations(
                alerts=adapted_alerts,
                context=context
            )
            recommendations.extend(alert_recs)

        # 2. Blocker resolution
        if tasks:
            blocker_recs = self.smart_generator.generate_blocker_recommendations(
                tasks=[{"id": t.id, "title": t.title, "status": t.status} for t in tasks],
                context=context
            )
            recommendations.extend(blocker_recs)

        # 3. Goal progress
        if goals:
            goal_recs = self.smart_generator.generate_goal_recommendations(
                goals=[{
                    "id": g.id,
                    "name": g.name,
                    "target_value": g.target_value,
                    "current_value": g.current_value,
                    "metric_type": g.metric_type
                } for g in goals],
                tasks=[{"id": t.id, "title": t.title} for t in tasks],
                context=context
            )
            recommendations.extend(goal_recs)

        # 4. Health recommendations
        health_recs = self.smart_generator.generate_health_recommendations(
            tasks=[{"id": t.id, "title": t.title} for t in tasks],
            context=context
        )
        recommendations.extend(health_recs)

        # 5. Momentum recommendations
        momentum_recs = self.smart_generator.generate_momentum_recommendations(
            tasks=[{"id": t.id, "title": t.title} for t in tasks],
            context=context
        )
        recommendations.extend(momentum_recs)

        # Apply learning adjustments (Layer 3)
        if self.learning_system:
            recommendations = self._apply_learning_adjustments(recommendations)

        # Enrich with patterns (Layer 2)
        if self.pattern_memory:
            recommendations = self._enrich_with_patterns(recommendations)

        # Enrich with Layer 4 intelligence (files, steps, patterns)
        recommendations = self.smart_generator.enrich_with_intelligence(
            recommendations=recommendations,
            context=context
        )

        # Sort by priority score
        recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)

        return recommendations[:limit]

    def get_active_alerts(self, project: Optional[str] = None, days: int = 7):
        """
        Get active alerts for a project.

        Args:
            project: Project name (defaults to current directory name)
            days: Number of days to analyze

        Returns:
            List of active alerts
        """
        project_name = project or self.project_path.name
        return self.alert_generator.generate_alerts(project_name, days=days)

    def get_project_health(self, project: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive project health metrics.

        Args:
            project: Project name (defaults to current directory name)
            days: Number of days to analyze

        Returns:
            Dictionary with health metrics and trends
        """
        project_name = project or self.project_path.name

        # Get all trends
        coverage_trend = self.trend_analyzer.analyze_coverage_trend(project_name, days)
        violations_trend = self.trend_analyzer.analyze_violation_trend(project_name, days)
        activity_trend = self.trend_analyzer.analyze_activity_trend(project_name, days)

        # Get alerts
        alerts = self.alert_generator.generate_alerts(project_name, days)

        return {
            "project": project_name,
            "coverage": {
                "current": coverage_trend.end_value if coverage_trend else 0,
                "trend": coverage_trend.direction.value if coverage_trend else "unknown",
                "delta": coverage_trend.delta if coverage_trend else 0,
            },
            "violations": {
                "current": int(violations_trend.end_value) if violations_trend else 0,
                "trend": violations_trend.direction.value if violations_trend else "unknown",
                "delta": int(violations_trend.delta) if violations_trend else 0,
            },
            "activity": {
                "commits": int(activity_trend.end_value) if activity_trend else 0,
                "trend": activity_trend.direction.value if activity_trend else "unknown",
            },
            "alerts": {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.severity.value == "critical"),
                "warning": sum(1 for a in alerts if a.severity.value == "warning"),
            }
        }

    def _apply_learning_adjustments(self, recommendations):
        """Apply learning-based adjustments to recommendation priorities using project profiling."""
        if not self.project_profiler:
            return recommendations

        try:
            # Get project profile
            profile = self.project_profiler.profile_project()

            # Boost recommendations related to low coverage
            if profile.test_coverage.is_low:
                for rec in recommendations:
                    if hasattr(rec, 'type') and rec.type == 'coverage':
                        if hasattr(rec, 'priority_score'):
                            rec.priority_score *= 1.5

            # Boost recommendations for critical files
            critical_file_paths = {cf.path for cf in profile.critical_files}
            for rec in recommendations:
                if hasattr(rec, 'files') and rec.files:
                    if any(f in critical_file_paths for f in rec.files):
                        if hasattr(rec, 'priority_score'):
                            rec.priority_score *= 1.3

        except Exception:
            # Silently fall back if profiler fails
            pass

        return recommendations

    def _enrich_with_patterns(self, recommendations):
        """Enrich recommendations with pattern-based insights from similar work."""
        if not self.pattern_memory:
            return recommendations

        try:
            project_name = self.project_path.name

            for rec in recommendations:
                # Find similar work for this recommendation
                similar_work = self.pattern_memory.find_similar_solutions(
                    task=rec.title,
                    current_project=project_name,
                    pattern_type=rec.type if hasattr(rec, 'type') else None,
                    limit=2
                )

                if similar_work:
                    # Add similar work as metadata
                    if not hasattr(rec, 'metadata') or rec.metadata is None:
                        rec.metadata = {}

                    rec.metadata['similar_work'] = [
                        {
                            'project': sw.project,
                            'title': sw.title,
                            'files': sw.files_changed[:3],
                            'commit': sw.commit_hash[:8]
                        }
                        for sw in similar_work
                    ]

                    # Boost priority if we have similar successful work
                    if hasattr(rec, 'priority_score'):
                        rec.priority_score *= 1.2

        except Exception:
            # Silently fall back if pattern memory fails
            pass

        return recommendations

    def _priority_score(self, recommendation) -> float:
        """
        Calculate priority score for a recommendation.

        Args:
            recommendation: Recommendation object

        Returns:
            Priority score (higher = more important)
        """
        # Base score from recommendation priority
        score = getattr(recommendation, 'priority_score', 0.5)

        # Boost based on recommendation type
        type_boost = {
            'blocker': 2.0,
            'alert': 1.8,
            'goal': 1.5,
            'health': 1.2,
            'momentum': 1.0,
        }
        rec_type = getattr(recommendation, 'type', 'unknown')
        score *= type_boost.get(rec_type, 1.0)

        # Boost based on confidence
        confidence = getattr(recommendation, 'confidence', 0.5)
        if hasattr(confidence, 'value'):
            # Handle Confidence enum
            confidence_map = {'high': 0.9, 'medium': 0.7, 'low': 0.5}
            confidence = confidence_map.get(confidence.value, 0.5)
        score *= (0.5 + confidence)

        return score

    # ===== Layer 5: Planning Methods =====

    def create_plan(
        self,
        recommendations: List[Recommendation] = None,
        title: str = None,
        description: str = None,
        priority: PlanPriority = PlanPriority.MEDIUM,
        auto_generate: bool = False
    ) -> Plan:
        """
        Create an execution plan from recommendations.

        Args:
            recommendations: List of recommendations (auto-generated if None and auto_generate=True)
            title: Plan title (auto-generated if None)
            description: Plan description (auto-generated if None)
            priority: Plan priority
            auto_generate: Auto-generate recommendations if None provided

        Returns:
            Plan object
        """
        if recommendations is None and auto_generate:
            # Auto-generate recommendations
            recommendations = self.generate_recommendations(limit=5)

        if not recommendations:
            raise ValueError("No recommendations provided and auto_generate=False")

        # Create plan using planner
        plan = self.planner.create_plan_from_recommendations(
            recommendations=recommendations,
            title=title,
            description=description,
            priority=priority
        )

        # Save the plan
        self.plan_executor.save_plan(plan)

        return plan

    def start_plan(self, plan: Plan):
        """
        Start executing a plan.

        Args:
            plan: Plan to start
        """
        self.plan_executor.start_plan(plan)

    def get_active_plan(self) -> Optional[Plan]:
        """
        Get the currently active plan.

        Returns:
            Active plan or None
        """
        return self.plan_executor.active_plan

    def get_next_step(self):
        """
        Get the next step to execute in the active plan.

        Returns:
            Next PlanStep or None
        """
        return self.plan_executor.get_next_step()

    def complete_step(self, step_id: str, notes: str = ""):
        """
        Mark a step as completed in the active plan.

        Args:
            step_id: Step identifier
            notes: Optional completion notes
        """
        self.plan_executor.complete_step(step_id, notes)

    def get_plan_progress(self) -> Dict[str, Any]:
        """
        Get progress of the active plan.

        Returns:
            Progress dictionary
        """
        return self.plan_executor.get_progress()

    # ===== Layer 1: Project Analysis Methods =====

    def get_project_profile(self):
        """
        Get project profile with tech stack, coverage, and critical files.

        Returns:
            ProjectProfile object or None if profiler not available
        """
        if not self.project_profiler:
            return None

        try:
            return self.project_profiler.profile_project()
        except Exception:
            return None

    def get_tech_stack(self) -> Optional[Dict[str, Any]]:
        """
        Get project tech stack information.

        Returns:
            Dictionary with languages, frameworks, databases, tools
        """
        profile = self.get_project_profile()
        if not profile:
            return None

        return {
            'languages': list(profile.tech_stack.languages),
            'frameworks': list(profile.tech_stack.frameworks),
            'databases': list(profile.tech_stack.databases),
            'tools': list(profile.tech_stack.tools),
            'version_info': profile.tech_stack.version_info
        }

    def get_test_coverage_info(self) -> Optional[Dict[str, Any]]:
        """
        Get test coverage information.

        Returns:
            Dictionary with coverage metrics
        """
        profile = self.get_project_profile()
        if not profile:
            return None

        cov = profile.test_coverage
        return {
            'test_files': cov.test_files,
            'source_files': cov.source_files,
            'coverage_percent': cov.coverage_percent,
            'estimated_coverage': cov.estimated_coverage,
            'is_low': cov.is_low,
            'has_coverage_report': cov.has_coverage_report
        }

    # ===== Layer 2: Pattern Memory Methods =====

    def find_similar_work(self, task: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar work from other projects.

        Args:
            task: Description of current task
            limit: Maximum results

        Returns:
            List of similar work with projects, titles, files
        """
        if not self.pattern_memory:
            return []

        try:
            project_name = self.project_path.name
            similar = self.pattern_memory.find_similar_solutions(
                task=task,
                current_project=project_name,
                limit=limit
            )

            return [
                {
                    'project': sw.project,
                    'title': sw.title,
                    'description': sw.description,
                    'pattern_type': sw.pattern_type,
                    'files_changed': sw.files_changed,
                    'relevance_score': sw.relevance_score,
                    'commit_hash': sw.commit_hash
                }
                for sw in similar
            ]
        except Exception:
            return []

    def get_relevant_patterns(self, context: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get relevant patterns for current context.

        Args:
            context: Current context (file, error, etc.)
            limit: Maximum results

        Returns:
            List of relevant patterns
        """
        if not self.pattern_memory:
            return []

        try:
            patterns = self.pattern_memory.get_relevant_patterns(
                context=context,
                limit=limit
            )

            return [
                {
                    'project': p.project,
                    'title': p.title,
                    'description': p.description,
                    'pattern_type': p.pattern_type,
                    'files_changed': p.files_changed,
                    'relevance_score': p.relevance_score
                }
                for p in patterns
            ]
        except Exception:
            return []
