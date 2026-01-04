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
from datetime import datetime

# Layer 3: Warning System
from intelligence.monitoring.metric_tracker import MetricTracker
from intelligence.monitoring.trend_analyzer import TrendAnalyzer
from intelligence.monitoring.alert_generator import AlertGenerator

# Layer 3.5: Process Monitor
try:
    from intelligence.process_monitor import ProcessMonitor
except ImportError:
    ProcessMonitor = None

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
    priority: str  # "high", "medium", "low"
    confidence: float
    id: str = None
    rationale: str = None
    estimated_effort: str = None
    estimated_impact: str = None
    related_projects: List[str] = None
    related_goals: List[str] = None
    prerequisites: List[str] = None
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

        # Layer 3.5: Process Monitor
        self.process_monitor = None
        if ProcessMonitor:
            try:
                self.process_monitor = ProcessMonitor()
            except Exception:
                pass

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

        # Priority Calculator for smart recommendations
        try:
            from cortex.agents.data_agent.analyzers.priority_calculator import PriorityCalculator
            self.priority_calculator = PriorityCalculator()
        except ImportError:
            self.priority_calculator = None

        # Portfolio Memory for cross-project intelligence
        try:
            from cortex.portfolio_memory import PortfolioMemory
            self.portfolio_memory = PortfolioMemory()
        except ImportError:
            self.portfolio_memory = None

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

        # Collect alerts from both Layer 3 sources
        all_alerts = []

        # Layer 3: Metric-based alerts
        metric_alerts = self.alert_generator.generate_alerts(project_name, days=7)
        if metric_alerts:
            all_alerts.extend(metric_alerts)

        # Layer 3.5: Process Monitor alerts
        if self.process_monitor:
            try:
                # Get alerts from process monitor (last 24 hours)
                process_alerts_data = self.process_monitor.alert_generator.generate_alerts(hours=24)
                if process_alerts_data:
                    all_alerts.extend(process_alerts_data)
            except Exception:
                pass  # Silently ignore if process monitor fails

        # Adapt all alerts to Layer 4 format
        if all_alerts:
            adapted_alerts = adapt_alerts(all_alerts)
            context["alerts"] = [
                {
                    "id": a.id,
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message
                }
                for a in adapted_alerts
            ]

            # 1. Alert-driven recommendations (from all Layer 3 sources)
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
        if hasattr(self, 'learning_system') and self.learning_system:
            recommendations = self._apply_learning_adjustments(recommendations)

        # Enrich with patterns (Layer 2)
        if self.pattern_memory:
            recommendations = self._enrich_with_patterns(recommendations)

        # Enrich with Layer 4 intelligence (files, steps, patterns)
        recommendations = self.smart_generator.enrich_with_intelligence(
            recommendations=recommendations,
            context=context
        )

        # Build context for priority calculation
        priority_context = self._build_priority_context(project_name, context)

        # Convert recommendations to dict format for priority calculation
        rec_dicts = [self._recommendation_to_dict(r) for r in recommendations]

        # Calculate priorities using PriorityCalculator
        if self.priority_calculator:
            rec_dicts = self.priority_calculator.rank_recommendations(rec_dicts, priority_context)
            # Update recommendations with calculated priorities
            for i, rec_dict in enumerate(rec_dicts):
                if i < len(recommendations):
                    recommendations[i].priority = int(rec_dict.get("calculated_priority", 0.5) * 100)
                    if not hasattr(recommendations[i], 'metadata') or recommendations[i].metadata is None:
                        recommendations[i].metadata = {}
                    recommendations[i].metadata["calculated_priority"] = rec_dict.get("calculated_priority", 0.5)
            # Re-sort recommendations by calculated priority
            recommendations.sort(key=lambda r: r.metadata.get("calculated_priority", 0.0) if r.metadata else 0.0, reverse=True)
        else:
            # Fallback to original priority scoring
            recommendations.sort(key=lambda r: self._priority_score(r), reverse=True)

        return recommendations[:limit]

    def get_active_alerts(self, project: Optional[str] = None, days: int = 7):
        """
        Get active alerts for a project from all sources.

        Args:
            project: Project name (defaults to current directory name)
            days: Number of days to analyze

        Returns:
            List of active alerts from Layer 3 and Process Monitor
        """
        project_name = project or self.project_path.name
        all_alerts = []

        # Layer 3: Metric-based alerts
        metric_alerts = self.alert_generator.generate_alerts(project_name, days=days)
        if metric_alerts:
            all_alerts.extend(metric_alerts)

        # Layer 3.5: Process Monitor alerts
        if self.process_monitor:
            try:
                hours = days * 24
                process_alerts = self.process_monitor.alert_generator.generate_alerts(hours=hours)
                if process_alerts:
                    all_alerts.extend(process_alerts)
            except Exception:
                pass

        return all_alerts

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
        """
        Enrich recommendations with pattern-based insights from similar work.
        
        Enhanced to use portfolio memory for cross-project pattern matching.
        Includes portfolio intelligence for better recommendations.
        """
        # Try portfolio memory first (more comprehensive)
        if self.portfolio_memory:
            try:
                project_name = self.project_path.name
                patterns = self.portfolio_memory.get_cross_project_patterns()
                
                # Get project context for better matching
                project_context = self.portfolio_memory.get_project_context(
                    project_name,
                    include_health=True
                )
                
                for rec in recommendations:
                    rec_type = getattr(rec, 'type', '')
                    rec_title = getattr(rec, 'title', '')
                    rec_description = getattr(rec, 'description', '')
                    
                    # Find matching patterns using multiple criteria
                    matching_patterns = []
                    for p in patterns:
                        pattern_text = p.get("pattern", "").lower()
                        # Match by type
                        if rec_type and rec_type.lower() in pattern_text:
                            matching_patterns.append(p)
                        # Match by title keywords
                        elif rec_title:
                            title_words = rec_title.lower().split()
                            if any(word in pattern_text for word in title_words if len(word) > 3):
                                matching_patterns.append(p)
                        # Match by description keywords
                        elif rec_description:
                            desc_words = rec_description.lower().split()
                            if any(word in pattern_text for word in desc_words if len(word) > 3):
                                matching_patterns.append(p)
                    
                    if matching_patterns:
                        # Use most successful pattern
                        best_pattern = max(
                            matching_patterns,
                            key=lambda p: p.get("success_rate", 0.0)
                        )
                        
                        # Enhance recommendation with pattern insights
                        if not hasattr(rec, 'metadata') or rec.metadata is None:
                            rec.metadata = {}
                        
                        rec.metadata["pattern"] = best_pattern.get("pattern", "")
                        rec.metadata["pattern_success_rate"] = best_pattern.get("success_rate", 0.0)
                        rec.metadata["pattern_project"] = best_pattern.get("project", "")
                        
                        # Add rationale if not present
                        if not hasattr(rec, 'rationale'):
                            rec.rationale = ""
                        if rec.metadata["pattern"]:
                            rec.rationale += f" Based on successful pattern from {rec.metadata['pattern_project']}: {rec.metadata['pattern']}"
                        
                        # Boost priority if pattern is highly successful
                        if rec.metadata["pattern_success_rate"] > 0.8:
                            if hasattr(rec, 'priority_score'):
                                rec.priority_score *= 1.3
                            rec.metadata["estimated_impact"] = "high"
                    
                    # Add cross-project insights if available
                    if project_context:
                        cross_project_insights = project_context.get("cross_project_insights", [])
                        if cross_project_insights and not hasattr(rec, 'metadata') or rec.metadata is None:
                            rec.metadata = {}
                        if cross_project_insights:
                            rec.metadata["cross_project_insights"] = cross_project_insights[:3]  # Top 3
                
                return recommendations
            except Exception as e:
                # Log error but continue with fallback
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Portfolio memory enrichment failed: {e}")
        
        # Fallback to pattern_memory if portfolio not available
        
        # Fallback to pattern_memory
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
        Calculate enhanced priority score for a recommendation.

        Args:
            recommendation: Recommendation object

        Returns:
            Priority score (higher = more important)

        Factors considered:
        - Base priority (urgency, importance)
        - Dependencies (blocking other work)
        - Pattern success rate (if pattern-based)
        - Portfolio intelligence (cross-project insights)
        - Project health impact
        """
        # Base score from recommendation priority
        score = getattr(recommendation, 'priority_score', 0.5)
        
        # Enhance with portfolio intelligence
        try:
            from cortex.portfolio_memory import PortfolioMemory
            portfolio = PortfolioMemory()
            
            # Get project context
            project_name = getattr(recommendation, 'project', None) or self.project_path.name
            project_context = portfolio.get_project_context(project_name, include_health=True)
            
            # Boost if project health is low
            if project_context and project_context.get("health_score", 100) < 50:
                score *= 1.3
            
            # Boost if recommendation addresses critical warnings
            warnings = portfolio.get_warnings(project=project_name, severity="critical")
            if warnings and hasattr(recommendation, 'type'):
                rec_type = getattr(recommendation, 'type', '')
                if any(w.get("metric") in rec_type for w in warnings):
                    score *= 1.5
            
        except Exception:
            pass  # Fallback if portfolio not available

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

    def _build_priority_context(
        self,
        project_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build context dictionary for priority calculation.
        
        Args:
            project_name: Name of the project
            context: Existing context dictionary
            
        Returns:
            Context dictionary with warnings, patterns, health score, etc.
        """
        priority_context = context.copy() if context else {}
        
        # Add warnings from portfolio memory
        if self.portfolio_memory:
            try:
                warnings = self.portfolio_memory.get_warnings(project=project_name)
                priority_context["warnings"] = warnings
            except Exception:
                priority_context["warnings"] = []
        
        # Add project health score
        if self.portfolio_memory:
            try:
                project_context = self.portfolio_memory.get_project_context(
                    project_name,
                    include_health=True
                )
                if project_context:
                    priority_context["health_score"] = project_context.get("health_score", 100)
                    priority_context["cross_project_insights"] = project_context.get(
                        "cross_project_insights", []
                    )
            except Exception:
                priority_context["health_score"] = 100
        
        # Add patterns from portfolio memory
        if self.portfolio_memory:
            try:
                patterns = self.portfolio_memory.get_cross_project_patterns()
                priority_context["patterns"] = patterns
            except Exception:
                priority_context["patterns"] = []
        
        return priority_context

    def _recommendation_to_dict(self, recommendation: Recommendation) -> Dict[str, Any]:
        """
        Convert Recommendation dataclass to dictionary for priority calculation.
        
        Args:
            recommendation: Recommendation object
            
        Returns:
            Dictionary representation of recommendation
        """
        rec_dict = {
            "type": getattr(recommendation, "type", "unknown"),
            "title": getattr(recommendation, "title", ""),
            "description": getattr(recommendation, "description", ""),
            "priority": getattr(recommendation, "priority", 50),
            "confidence": getattr(recommendation, "confidence", 0.5),
            "files": getattr(recommendation, "files", []),
            "steps": getattr(recommendation, "steps", []),
            "metadata": getattr(recommendation, "metadata", {}),
        }
        
        # Extract additional fields from metadata
        if rec_dict["metadata"]:
            rec_dict.update({
                "pattern": rec_dict["metadata"].get("pattern", ""),
                "estimated_impact": rec_dict["metadata"].get("estimated_impact", "medium"),
                "time_sensitive": rec_dict["metadata"].get("time_sensitive", False),
                "blocks_others": rec_dict["metadata"].get("blocks_others", False),
                "dependencies": rec_dict["metadata"].get("dependencies", []),
                "dependencies_met": rec_dict["metadata"].get("dependencies_met", False),
            })
        
        return rec_dict

    def get_scheduling_recommendations(
        self,
        tasks: List[Task] = None,
        recommendations: List[Recommendation] = None
    ) -> List[Dict[str, Any]]:
        """
        Get capacity-aware scheduling recommendations for tasks.

        Args:
            tasks: List of tasks to schedule
            recommendations: List of recommendations to schedule

        Returns:
            List of scheduling recommendations
        """
        if not self.process_monitor or not hasattr(self.process_monitor, 'scheduler'):
            return []

        scheduler = self.process_monitor.scheduler
        scheduling_recs = []

        # Schedule tasks
        if tasks:
            for task in tasks:
                # Detect task type from title
                task_type = scheduler.detect_task_type_from_description(task.title)

                # Determine priority from task status
                if task.status == "blocked":
                    priority = "high"
                elif task.status == "in_progress":
                    priority = "immediate"
                else:
                    priority = "normal"

                from intelligence.process_monitor import SchedulingPriority
                scheduled = scheduler.schedule_task(
                    task_id=task.id,
                    task_type=task_type,
                    priority=SchedulingPriority(priority),
                )

                scheduling_recs.append({
                    'task_id': task.id,
                    'task_title': task.title,
                    'task_type': task_type.value,
                    'can_run_now': scheduled.can_run_now,
                    'recommended_start': scheduled.recommended_start_time.isoformat(),
                    'reason': scheduled.scheduling_reason,
                    'capacity_available': scheduled.capacity_forecast.resource_availability if scheduled.capacity_forecast else 0,
                })

        # Schedule recommendations
        if recommendations:
            for rec in recommendations:
                # Detect task type from recommendation type and title
                task_type = scheduler.detect_task_type_from_description(
                    f"{rec.type} {rec.title}"
                )

                from intelligence.process_monitor import SchedulingPriority
                scheduled = scheduler.schedule_task(
                    task_id=rec.title,
                    task_type=task_type,
                    priority=SchedulingPriority("normal"),
                )

                scheduling_recs.append({
                    'recommendation_title': rec.title,
                    'recommendation_type': rec.type,
                    'task_type': task_type.value,
                    'can_run_now': scheduled.can_run_now,
                    'recommended_start': scheduled.recommended_start_time.isoformat(),
                    'reason': scheduled.scheduling_reason,
                    'capacity_available': scheduled.capacity_forecast.resource_availability if scheduled.capacity_forecast else 0,
                })

        return scheduling_recs

    def get_recommendation_dashboard(
        self,
        project: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get recommendation dashboard with prioritized recommendations and context.
        
        Args:
            project: Project name (defaults to current directory name)
            limit: Maximum recommendations to return
            
        Returns:
            Dashboard dictionary with recommendations, health, alerts, and patterns
        """
        project_name = project or self.project_path.name
        
        # Generate recommendations
        recommendations = self.generate_recommendations(limit=limit)
        
        # Get project health
        health = self.get_project_health(project=project_name)
        
        # Get active alerts
        alerts = self.get_active_alerts(project=project_name)
        
        # Get relevant patterns
        patterns = []
        if self.pattern_memory:
            try:
                patterns = self.get_relevant_patterns(
                    context=f"project: {project_name}",
                    limit=5
                )
            except Exception:
                pass
        
        # Convert recommendations to dict format
        rec_dicts = []
        for rec in recommendations:
            rec_dict = {
                "type": rec.type,
                "title": rec.title,
                "description": rec.description,
                "priority": rec.priority,
                "confidence": rec.confidence,
                "calculated_priority": rec.metadata.get("calculated_priority", 0.5) if rec.metadata else 0.5,
                "files": rec.files or [],
                "steps": rec.steps or [],
                "rationale": rec.metadata.get("rationale", "") if rec.metadata else "",
                "pattern": rec.metadata.get("pattern", "") if rec.metadata else "",
                "pattern_success_rate": rec.metadata.get("pattern_success_rate", 0.0) if rec.metadata else 0.0,
            }
            rec_dicts.append(rec_dict)
        
        return {
            "project": project_name,
            "timestamp": datetime.now().isoformat(),
            "health": health,
            "alerts": {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if getattr(a, "severity", None) and getattr(a.severity, "value", "") == "critical"),
                "warning": sum(1 for a in alerts if getattr(a, "severity", None) and getattr(a.severity, "value", "") == "warning"),
            },
            "recommendations": rec_dicts,
            "patterns": patterns[:5],
            "summary": {
                "total_recommendations": len(rec_dicts),
                "high_priority": sum(1 for r in rec_dicts if r.get("calculated_priority", 0) > 0.7),
                "pattern_based": sum(1 for r in rec_dicts if r.get("pattern", "")),
            }
        }
