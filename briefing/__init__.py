#!/usr/bin/env python3
"""
Briefing Generator - Daily briefing system for cross-project status

Synthesizes:
- Portfolio pulse (active projects, commits, blockers)
- Priority actions (top recommendations)
- Patterns noticed (activity trends)
- Waiting on (decisions needed)
"""

import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import existing tools
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    from ai_intelligence import ProjectActivity, ProjectScanner
except ImportError:
    ProjectScanner = None
    ProjectActivity = None

try:
    from goal_parser import Goal, GoalParser
except ImportError:
    GoalParser = None
    Goal = None

try:
    from recommendation_engine import Recommendation, RecommendationEngine
except ImportError:
    RecommendationEngine = None
    Recommendation = None

try:
    from intelligence.process_monitor import ProcessMonitor
except ImportError:
    ProcessMonitor = None

try:
    from integration.git_tracker import GitTracker, get_git_briefing
except ImportError:
    GitTracker = None
    get_git_briefing = None

try:
    from learning import LearningSystem
except ImportError:
    LearningSystem = None

try:
    from portfolio_memory import PortfolioMemory
except ImportError:
    PortfolioMemory = None

try:
    from intelligence.session_manager import SessionManager
except ImportError:
    SessionManager = None

try:
    from batch.usage_optimizer import UsageOptimizer
except ImportError:
    UsageOptimizer = None

try:
    from metrics_tracker import MetricsTracker
except ImportError:
    MetricsTracker = None

try:
    from intelligence.bandwidth.contracts import ContractMetricsStore
except ImportError:
    ContractMetricsStore = None

try:
    from intelligence.bandwidth.queue_slo import check_queue_slo
except ImportError:
    check_queue_slo = None


DEFAULT_BRIEFING_STYLE = {
    "separator_width": 64,
    "show_ascii_graphics": True,
    "show_infographics": True,
    "show_sparklines": True,
    "progress_bar": {
        "width": 10,
        "filled_char": "#",
        "empty_char": ".",
        "left_bracket": "[",
        "right_bracket": "]",
    },
    "sparkline_chars": "▁▂▃▄▅▆▇█",
}


# _load_briefing_style + _build_progress_bar + format_statusline migrated to
# briefing/formatters.py. Re-exported at the bottom of this file for
# import-site compatibility with existing callers.


# _sparkline + _compute_signal_quality + get_briefing_signal_quality
# migrated to briefing/signal_quality.py — re-exported at the bottom of
# this file for import-site compatibility with existing callers.


def get_briefing_style_path() -> Path:
    """Get path to persistent briefing style config."""
    return Path(__file__).parent / "config" / "briefing_style.json"


def get_briefing_style() -> Dict[str, Any]:
    """Get effective briefing style (defaults merged with file)."""
    return _load_briefing_style()


def validate_briefing_style(style: Optional[Dict[str, Any]] = None) -> List[str]:
    """Validate briefing style and return list of errors (empty if valid)."""
    data = style or _load_briefing_style()
    errors: List[str] = []

    if not isinstance(data.get("separator_width"), int) or data.get("separator_width", 0) < 20:
        errors.append("separator_width must be an integer >= 20")

    for key in ["show_ascii_graphics", "show_infographics", "show_sparklines"]:
        if not isinstance(data.get(key), bool):
            errors.append(f"{key} must be true/false")

    pb = data.get("progress_bar")
    if not isinstance(pb, dict):
        errors.append("progress_bar must be an object")
    else:
        if not isinstance(pb.get("width"), int) or pb.get("width", 0) < 1:
            errors.append("progress_bar.width must be an integer >= 1")
        for char_key in ["filled_char", "empty_char", "left_bracket", "right_bracket"]:
            val = pb.get(char_key)
            if not isinstance(val, str) or len(val) != 1:
                errors.append(f"progress_bar.{char_key} must be a single character")

    sparkline_chars = data.get("sparkline_chars")
    if not isinstance(sparkline_chars, str) or len(sparkline_chars) < 2:
        errors.append("sparkline_chars must be a string with at least 2 characters")

    return errors


@dataclass
class BriefingData:
    """Structured briefing data."""

    # Portfolio pulse
    active_projects: List[str]
    recent_commits_24h: int
    total_commits_7d: int
    blockers: List[Dict[str, str]]

    # Priority actions
    priority_actions: List[Dict[str, Any]]

    # Patterns noticed
    patterns: List[str]

    # Waiting on
    waiting_on: List[str]

    # Metadata
    generated_at: datetime

    # Optional fields
    resource_status: Optional[Dict[str, Any]] = None
    batch_queue_status: Optional[Dict[str, Any]] = None
    git_status: Optional[Dict[str, Any]] = None
    work_progress: Optional[Dict[str, Any]] = None  # Work absorber status
    project_snapshot: Optional[List[Dict[str, Any]]] = None  # Top active projects with metrics
    period: str = "24h"

    # Enhanced intelligence fields
    intelligence_metrics: Optional[Dict[str, Any]] = None  # Learning system metrics
    strategic_alignment: Optional[Dict[str, Any]] = None  # Goal velocity, drift
    temporal_context: Optional[Dict[str, Any]] = None  # Day patterns, session continuity
    cross_project_insights: Optional[Dict[str, Any]] = None  # Related work, patterns
    predictive_insights: Optional[Dict[str, Any]] = None  # Predicted focus, optimal sequence

    # Resource & Orchestration Intelligence (High-Value)
    resource_intelligence: Optional[Dict[str, Any]] = None  # AIO consumption, pacing
    orchestration_advisory: Optional[Dict[str, Any]] = (
        None  # Agent recommendations, batch vs interactive
    )
    velocity_metrics: Optional[Dict[str, Any]] = None  # ROI, time savings

    # Overnight batch insights (surfaced from completed AI analysis tasks)
    batch_insights: Optional[Dict[str, Any]] = None
    bandwidth_contract_metrics: Optional[Dict[str, Any]] = None
    queue_slo: Optional[Dict[str, Any]] = None


class BriefingGenerator:
    """Generate daily briefings from cross-project data."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.root_dir = root_dir

        # Initialize core tools
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = RecommendationEngine() if RecommendationEngine else None

        # Initialize enhanced intelligence tools
        self.learning_system = LearningSystem() if LearningSystem else None
        self.portfolio_memory = PortfolioMemory() if PortfolioMemory else None
        self.session_manager = SessionManager(root_dir) if SessionManager else None

        # Initialize resource & orchestration tools
        self.usage_optimizer = UsageOptimizer() if UsageOptimizer else None
        self.metrics_tracker = MetricsTracker() if MetricsTracker else None
        self.contract_metrics_store = ContractMetricsStore() if ContractMetricsStore else None

    def generate_daily_briefing(self) -> BriefingData:
        """
        Generate daily briefing with portfolio status and recommendations.

        Returns:
            BriefingData with all briefing sections
        """
        # 1. Get project activity
        project_activity = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                project_activity = [self.project_scanner.analyze_project(repo) for repo in repos]
            except Exception as e:
                print(f"Warning: Could not scan projects: {e}", file=sys.stderr)

        # 2. Get goals
        goals = []
        if self.goal_parser:
            try:
                goals = self.goal_parser.parse()
            except Exception as e:
                print(f"Warning: Could not parse goals: {e}", file=sys.stderr)

        # 3. Get recommendations
        recommendations = []
        if self.recommendation_engine:
            try:
                generate_fn = self.recommendation_engine.generate_recommendations
                params = set(inspect.signature(generate_fn).parameters)

                if "project_activity" in params:
                    recommendations = generate_fn(
                        project_activity=project_activity if project_activity else None,
                        limit=5,
                    )
                elif "goals" in params or "context" in params:
                    recommendations = generate_fn(
                        goals=goals if goals else None,
                        context=(
                            {"project_activity": project_activity} if project_activity else None
                        ),
                        limit=5,
                    )
                elif "tasks" in params:
                    recommendations = generate_fn(limit=5)
                else:
                    recommendations = generate_fn()
            except Exception as e:
                print(f"Warning: Could not generate recommendations: {e}", file=sys.stderr)

        # 4. Get Git/GitHub status
        git_status = None
        if GitTracker:
            try:
                tracker = GitTracker(str(self.root_dir))
                git_status = {
                    "summary": tracker.get_summary(),
                    "recommendations": tracker.get_recommendations(),
                    "formatted": tracker.format_for_briefing(),
                }
            except Exception as e:
                print(f"Warning: Could not get Git status: {e}", file=sys.stderr)

        # 5. Get resource status
        resource_status = None
        batch_queue_status = None
        if ProcessMonitor:
            try:
                monitor = ProcessMonitor()
                resource_status = monitor.get_status()

                # Get batch queue statistics and task details
                from intelligence.process_monitor import TaskState

                batch_queue_status = monitor.batch_queue.get_queue_stats()

                # Add detailed task lists
                batch_queue_status["running_tasks"] = monitor.batch_queue.get_running_tasks()
                batch_queue_status["scheduled_tasks"] = monitor.batch_queue.get_scheduled_tasks()[
                    :5
                ]  # Next 5
                batch_queue_status["pending_tasks"] = monitor.batch_queue.get_pending_tasks()[
                    :5
                ]  # First 5
                batch_queue_status["recent_completed"] = monitor.batch_queue.get_task_history(
                    limit=3, state=TaskState.COMPLETED
                )
                batch_queue_status["recent_failed"] = monitor.batch_queue.get_task_history(
                    limit=3, state=TaskState.FAILED
                )

                # Add V2a sprint batch status
                try:
                    sys.path.insert(0, str(Path(__file__).parent / "batch"))
                    from v2a_sprint_orchestrator import V2aSprintOrchestrator

                    orchestrator = V2aSprintOrchestrator()
                    batch_queue_status["v2a_sprint"] = orchestrator.get_overall_status()
                except Exception:
                    # V2a orchestrator not available or no V2a tasks
                    pass
            except Exception as e:
                # Sandbox-limited environments can block sysctl introspection.
                # Suppress this expected warning to keep briefing output clean.
                if "Operation not permitted" not in str(e):
                    print(f"Warning: Could not get resource status: {e}", file=sys.stderr)

        # 5b. Get overnight batch insights from completed tasks
        batch_insights = self._get_batch_insights()

        # 6. Get work absorber status
        work_progress = None
        try:
            from work_absorber import WorkAbsorber

            absorber = WorkAbsorber()

            # Get recent work summary
            recent_items = absorber.get_recent_work(days=1)
            all_items = absorber.get_recent_work(days=7)
            drift_summary = absorber.get_drift_summary()

            # Build work progress summary
            work_progress = {
                "items_24h": len(recent_items),
                "items_7d": len(all_items),
                "correlated_24h": sum(1 for i in recent_items if i.plan_step_id),
                "orphaned_24h": sum(1 for i in recent_items if not i.plan_step_id),
                "drifts_total": drift_summary.get("total", 0),
                "drifts_by_type": dict(drift_summary.get("by_type", {})),
                "recent_work": [
                    {"title": i.title, "project": i.project, "scope": i.scope}
                    for i in recent_items[:5]
                ],
            }
        except ImportError:
            pass  # Work absorber not available
        except Exception as e:
            print(f"Warning: Could not get work progress: {e}", file=sys.stderr)

        # 7. Get enhanced intelligence (new sections)
        intelligence_metrics = self._get_intelligence_metrics()
        strategic_alignment = self._get_strategic_alignment(goals, project_activity)
        temporal_context = self._get_temporal_context()
        cross_project_insights = self._get_cross_project_insights(project_activity)
        predictive_insights = self._get_predictive_insights(
            project_activity, goals, temporal_context
        )

        # 8. Get resource & orchestration intelligence (HIGH-VALUE)
        resource_intelligence = self._get_resource_intelligence()
        orchestration_advisory = self._get_orchestration_advisory(
            resource_intelligence, batch_queue_status, project_activity
        )
        velocity_metrics = self._get_velocity_metrics()
        bandwidth_contract_metrics = self._get_bandwidth_contract_metrics()
        queue_slo = self._get_queue_slo_metrics()

        # 9. Build briefing sections
        briefing = BriefingData(
            active_projects=self._get_active_projects(project_activity),
            recent_commits_24h=self._count_recent_commits(project_activity, hours=24),
            total_commits_7d=self._count_recent_commits(project_activity, days=7),
            blockers=self._get_blockers(project_activity, goals),
            priority_actions=self._get_priority_actions(recommendations, goals),
            patterns=self._detect_patterns(project_activity),
            waiting_on=self._get_waiting_on(goals, project_activity),
            resource_status=resource_status,
            batch_queue_status=batch_queue_status,
            git_status=git_status,
            work_progress=work_progress,
            project_snapshot=self._build_project_snapshot(project_activity),
            generated_at=datetime.now(),  # noqa: DTZ005
            # Enhanced intelligence fields
            intelligence_metrics=intelligence_metrics,
            strategic_alignment=strategic_alignment,
            temporal_context=temporal_context,
            cross_project_insights=cross_project_insights,
            predictive_insights=predictive_insights,
            # Resource & Orchestration Intelligence
            resource_intelligence=resource_intelligence,
            orchestration_advisory=orchestration_advisory,
            velocity_metrics=velocity_metrics,
            # Overnight batch insights
            batch_insights=batch_insights,
            bandwidth_contract_metrics=bandwidth_contract_metrics,
            queue_slo=queue_slo,
        )

        return briefing

    def _get_active_projects(self, projects: List[ProjectActivity]) -> List[str]:
        """Get list of active project names."""
        if not projects:
            return []

        # Active = has commits in last 7 days; dedupe by name and keep strongest signal.
        by_name: Dict[str, ProjectActivity] = {}
        for p in projects:
            if p.commits_7d <= 0:
                continue
            existing = by_name.get(p.name)
            if existing is None or p.commits_7d > existing.commits_7d:
                by_name[p.name] = p

        active = list(by_name.keys())
        active.sort(key=lambda name: by_name[name].commits_7d, reverse=True)
        return active

    def _build_project_snapshot(self, projects: List[ProjectActivity]) -> List[Dict[str, Any]]:
        """Build top-project snapshot table rows for briefing display."""
        if not projects:
            return []

        by_name: Dict[str, ProjectActivity] = {}
        for p in projects:
            existing = by_name.get(p.name)
            if existing is None or p.commits_7d > existing.commits_7d:
                by_name[p.name] = p

        top = sorted(by_name.values(), key=lambda p: p.commits_7d, reverse=True)[:6]
        max_commits = max((p.commits_7d for p in top), default=0)
        rows: List[Dict[str, Any]] = []
        for p in top:
            # Relative trend buckets produce more informative variation.
            if max_commits > 0 and p.commits_7d >= max_commits * 0.60:
                trend = "hot"
            elif max_commits > 0 and p.commits_7d >= max_commits * 0.25:
                trend = "active"
            elif p.commits_7d > 0:
                trend = "steady"
            else:
                trend = "idle"

            rows.append(
                {
                    "project": p.name,
                    "commits_7d": p.commits_7d,
                    "uncommitted": p.uncommitted_changes,
                    "status": p.status,
                    "trend": trend,
                }
            )
        return rows

    def _count_recent_commits(
        self,
        projects: List[ProjectActivity],
        hours: Optional[int] = None,
        days: Optional[int] = None,
    ) -> int:
        """Count commits in recent time period."""
        if not projects:
            return 0

        total = 0
        now = datetime.now()  # noqa: DTZ005

        for project in projects:
            if not project.last_commit_date:
                continue

            # Check if commit is within time window
            if hours:
                cutoff = now - timedelta(hours=hours)
                if project.last_commit_date >= cutoff:
                    # Count all commits in 7d as proxy for 24h
                    # (we don't have 24h granularity in ProjectActivity)
                    total += max(1, project.commits_7d // 7)
            elif days:
                total += project.commits_7d if days <= 7 else project.commits_30d

        return total

    def _get_blockers(
        self, projects: List[ProjectActivity], goals: List[Goal]
    ) -> List[Dict[str, str]]:
        """Get all current blockers from projects and goals."""
        blockers = []

        # Project blockers
        if projects:
            for project in projects:
                if project.blockers and project.status in ["active", "recent"]:
                    for blocker in project.blockers:
                        blockers.append(
                            {
                                "project": project.name,
                                "blocker": blocker,
                                "source": "project",
                            }
                        )

        # Goal blockers
        if goals:
            for goal in goals:
                if goal.status == "blocked" and goal.project:
                    blocker_text = f"{goal.title}"
                    if goal.blockers:
                        blocker_text = goal.blockers[0]
                    blockers.append(
                        {
                            "project": goal.project,
                            "blocker": blocker_text,
                            "source": "goal",
                        }
                    )

        return blockers

    def _get_priority_actions(
        self, recommendations: List[Recommendation], goals: List[Goal]
    ) -> List[Dict[str, Any]]:
        """Get top 5 priority actions from recommendations and goals with detailed info."""
        actions = []
        seen_titles = set()  # Track titles to avoid duplicates

        def normalize_title(title: str) -> str:
            """Normalize title for deduplication."""
            import re

            # Remove project prefix (e.g., "cortex: " or "vortex-backend: ")
            normalized = re.sub(r"^[^:]+:\s*", "", title.lower())
            # Remove parenthetical content (e.g., "(feat/branch-name)")
            normalized = re.sub(r"\([^)]*\)", "", normalized)
            # Remove punctuation
            normalized = re.sub(r"[^\w\s]", "", normalized)
            # Normalize common variations
            normalized = normalized.replace("complete", "finish")
            normalized = normalized.replace("pr 2", "pr2")
            # Remove extra whitespace
            normalized = " ".join(normalized.split())
            return normalized.strip()

        # Add recommendations first
        if recommendations:
            for rec in recommendations[:3]:
                title = rec.action_title if hasattr(rec, "action_title") else rec.title
                norm_title = normalize_title(title)

                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)

                # Handle priority as int, enum, or string
                priority = rec.priority
                if isinstance(priority, int):
                    priority_str = "HIGH" if priority > 70 else "MEDIUM" if priority > 40 else "LOW"
                elif hasattr(priority, "value"):
                    priority_str = priority.value.upper()
                else:
                    priority_str = str(priority).upper()

                related_projects = getattr(rec, "related_projects", None) or []
                rationale = getattr(rec, "rationale", None) or getattr(rec, "description", "")

                action = {
                    "title": title,
                    "priority": priority_str,
                    "project": related_projects[0] if related_projects else "General",
                    "rationale": rationale,
                    "source": "recommendation",
                    "steps": getattr(rec, "steps", []) or [],
                    "estimated_effort": getattr(rec, "estimated_effort", None),
                    "estimated_impact": getattr(rec, "estimated_impact", None),
                    "confidence": getattr(rec, "confidence", None),
                }
                actions.append(action)

        # Fill remaining with high-priority goals (avoiding duplicates)
        if goals:
            priority_goals = [
                g for g in goals if g.priority == "A" and g.status in ["pending", "in_progress"]
            ]

            for goal in priority_goals:
                if len(actions) >= 5:
                    break

                norm_title = normalize_title(goal.title)
                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)

                action = {
                    "title": goal.title,
                    "priority": "HIGH",
                    "project": goal.project or "General",
                    "rationale": goal.description[:150] if goal.description else "",
                    "source": "goal",
                    "steps": goal.actions[:3] if goal.actions else [],
                    "success_criteria": goal.success_criteria,
                    "estimated_effort": getattr(goal, "estimated_effort", None),
                    "completion_percentage": getattr(goal, "completion_percentage", 0),
                }
                actions.append(action)

        return actions[:5]

    def _detect_patterns(self, projects: List[ProjectActivity]) -> List[str]:
        """Detect activity patterns and trends."""
        patterns = []

        if not projects:
            return patterns

        # 1. Most productive project (dedupe by name to avoid double counting)
        by_name: Dict[str, ProjectActivity] = {}
        for p in projects:
            if p.commits_7d <= 0:
                continue
            existing = by_name.get(p.name)
            if existing is None or p.commits_7d > existing.commits_7d:
                by_name[p.name] = p
        active_projects = list(by_name.values())
        if active_projects:
            most_active = max(active_projects, key=lambda p: p.commits_7d)
            patterns.append(
                f"{most_active.name} momentum: {most_active.commits_7d} commits this week"
            )

        # 2. Multi-project activity
        if len(active_projects) >= 3:
            patterns.append(
                f"Multi-project sprint: {len(active_projects)} projects active this week"
            )

        # 3. Dormant projects awakening
        recently_awakened = [
            p for p in projects if p.commits_7d > 0 and p.commits_30d <= p.commits_7d + 1
        ]
        if recently_awakened:
            patterns.append(f"Renewed focus on {recently_awakened[0].name}")

        # 4. Consistency patterns (commits every day vs burst)
        steady_projects = [p for p in active_projects if p.commits_7d >= 5 and p.commits_7d <= 10]
        if steady_projects:
            patterns.append(f"Steady progress on {steady_projects[0].name} (daily commits)")

        # 5. Burst activity
        burst_projects = [p for p in active_projects if p.commits_7d >= 15]
        if burst_projects:
            patterns.append(
                f"Sprint on {burst_projects[0].name} ({burst_projects[0].commits_7d} commits)"
            )

        return patterns[:3]  # Top 3 patterns

    def _get_waiting_on(self, goals: List[Goal], projects: List[ProjectActivity]) -> List[str]:
        """Get list of things waiting on user decisions."""
        waiting = []

        # 1. Blocked goals
        if goals:
            blocked_goals = [g for g in goals if g.status == "blocked"]
            for goal in blocked_goals:
                if goal.blockers:
                    waiting.append(f"{goal.project or 'Project'}: {goal.blockers[0]}")
                else:
                    waiting.append(f"{goal.project or 'Project'}: {goal.title}")

        # 2. Missing .env files (API keys needed)
        if projects:
            for project in projects:
                if "Missing .env file" in project.blockers:
                    waiting.append(f"{project.name}: Environment configuration needed")

        # 3. Uncommitted changes (decisions to commit or not)
        if projects:
            uncommitted = [p for p in projects if p.uncommitted_changes > 5]
            for project in uncommitted[:2]:  # Top 2
                waiting.append(
                    f"{project.name}: {project.uncommitted_changes} uncommitted changes to review"
                )

        return waiting[:4]  # Top 4 items

    def _get_intelligence_metrics(self) -> Optional[Dict[str, Any]]:
        """Get learning system metrics for briefing intelligence."""
        if not self.learning_system:
            return None

        try:
            metrics = self.learning_system.get_learning_metrics()
            patterns = self.learning_system.get_outcome_patterns()

            # Find best and worst performing recommendation types
            best_type = None
            worst_type = None
            if patterns:
                sorted_patterns = sorted(
                    [(k, v) for k, v in patterns.items() if v.get("followed", 0) >= 3],
                    key=lambda x: x[1].get("success_rate", 0),
                    reverse=True,
                )
                if sorted_patterns:
                    best_type = {
                        "type": sorted_patterns[0][0],
                        "success_rate": sorted_patterns[0][1].get("success_rate", 0),
                        "count": sorted_patterns[0][1].get("followed", 0),
                    }
                if len(sorted_patterns) > 1:
                    worst_type = {
                        "type": sorted_patterns[-1][0],
                        "success_rate": sorted_patterns[-1][1].get("success_rate", 0),
                        "count": sorted_patterns[-1][1].get("followed", 0),
                    }

            return {
                "recommendation_accuracy": metrics.recommendation_accuracy,
                "total_outcomes": metrics.total_outcomes,
                "followed_count": metrics.followed_count,
                "success_rate": metrics.success_rate,
                "confidence_calibration": metrics.confidence_calibration,
                "best_performing_type": best_type,
                "worst_performing_type": worst_type,
                "has_sufficient_data": metrics.total_outcomes >= 10,
            }
        except Exception as e:
            print(f"Warning: Could not get intelligence metrics: {e}", file=sys.stderr)
            return None

    def _get_strategic_alignment(
        self, goals: List[Goal], project_activity: List[ProjectActivity]
    ) -> Optional[Dict[str, Any]]:
        """Analyze strategic alignment: goal velocity, drift detection."""
        if not goals:
            return None

        try:
            # Calculate goal completion velocity
            completed_goals = [g for g in goals if g.status == "completed"]
            in_progress_goals = [g for g in goals if g.status == "in_progress"]
            pending_goals = [g for g in goals if g.status == "pending"]
            blocked_goals = [g for g in goals if g.status == "blocked"]

            total_goals = len(goals)
            completion_rate = len(completed_goals) / total_goals if total_goals > 0 else 0

            # Analyze priority distribution
            high_priority = [g for g in goals if g.priority == "A"]
            high_priority_completed = [g for g in high_priority if g.status == "completed"]
            high_priority_blocked = [g for g in high_priority if g.status == "blocked"]

            # Detect strategic drift: high priority goals blocked or stalled
            drift_indicators = []
            if len(high_priority_blocked) > 0:
                drift_indicators.append(f"{len(high_priority_blocked)} high-priority goals blocked")
            if len(high_priority) > 0 and len(high_priority_completed) / len(high_priority) < 0.3:
                drift_indicators.append("Low completion rate on high-priority goals")

            # Project focus alignment: are commits happening on priority projects?
            priority_projects = set(g.project for g in high_priority if g.project)
            active_project_names = (
                set(p.name for p in project_activity if p.commits_7d > 0)
                if project_activity
                else set()
            )
            aligned_projects = priority_projects & active_project_names
            unaligned_active = active_project_names - priority_projects

            if unaligned_active and priority_projects:
                drift_indicators.append(
                    f"Activity on non-priority projects: {', '.join(list(unaligned_active)[:2])}"
                )

            # Goal velocity insight
            velocity_status = "healthy"
            if len(blocked_goals) > len(in_progress_goals):
                velocity_status = "blocked"
            elif len(pending_goals) > len(completed_goals) + len(in_progress_goals):
                velocity_status = "backlog_growing"

            return {
                "total_goals": total_goals,
                "completed": len(completed_goals),
                "in_progress": len(in_progress_goals),
                "pending": len(pending_goals),
                "blocked": len(blocked_goals),
                "completion_rate": completion_rate,
                "high_priority_total": len(high_priority),
                "high_priority_completed": len(high_priority_completed),
                "velocity_status": velocity_status,
                "drift_indicators": drift_indicators,
                "aligned_projects": list(aligned_projects),
                "has_strategic_drift": len(drift_indicators) > 0,
            }
        except Exception as e:
            print(f"Warning: Could not analyze strategic alignment: {e}", file=sys.stderr)
            return None

    def _get_temporal_context(self) -> Optional[Dict[str, Any]]:
        """Get temporal context: day patterns, session continuity."""
        try:
            now = datetime.now()  # noqa: DTZ005
            day_of_week = now.strftime("%A")
            hour = now.hour

            # Day-based patterns and suggestions
            day_patterns = {
                "Monday": {
                    "pattern": "week_start",
                    "suggestion": "Good day for planning and high-priority tasks",
                    "energy": "fresh_start",
                },
                "Tuesday": {
                    "pattern": "deep_work",
                    "suggestion": "Peak productivity day - tackle complex problems",
                    "energy": "high",
                },
                "Wednesday": {
                    "pattern": "mid_week",
                    "suggestion": "Continue momentum on in-progress work",
                    "energy": "sustained",
                },
                "Thursday": {
                    "pattern": "delivery_prep",
                    "suggestion": "Focus on completing tasks before week end",
                    "energy": "focused",
                },
                "Friday": {
                    "pattern": "week_close",
                    "suggestion": "Wrap up, commit changes, plan next week",
                    "energy": "winding_down",
                },
                "Saturday": {
                    "pattern": "weekend_optional",
                    "suggestion": "Optional: exploration, learning, or rest",
                    "energy": "relaxed",
                },
                "Sunday": {
                    "pattern": "week_prep",
                    "suggestion": "Optional: review upcoming week priorities",
                    "energy": "preparatory",
                },
            }

            # Time of day context
            time_context = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
            time_suggestions = {
                "morning": "Best for deep work and complex tasks",
                "afternoon": "Good for meetings, reviews, and lighter tasks",
                "evening": "Consider wrapping up and documenting progress",
            }

            # Get session continuity from session manager
            session_context = None
            last_focus = None
            if self.session_manager:
                try:
                    ctx = self.session_manager.load_session_context(max_age_hours=24)
                    if ctx:
                        session_context = {
                            "project": ctx.project,
                            "current_focus": ctx.current_focus,
                            "recent_work": (ctx.recent_work[:3] if ctx.recent_work else []),
                            "active_goals": (ctx.active_goals[:3] if ctx.active_goals else []),
                        }
                        last_focus = ctx.current_focus
                except Exception:
                    pass

            return {
                "day_of_week": day_of_week,
                "time_of_day": time_context,
                "hour": hour,
                "day_pattern": day_patterns.get(day_of_week, {}),
                "time_suggestion": time_suggestions.get(time_context, ""),
                "session_continuity": session_context,
                "last_focus": last_focus,
                "is_weekend": day_of_week in ["Saturday", "Sunday"],
            }
        except Exception as e:
            print(f"Warning: Could not get temporal context: {e}", file=sys.stderr)
            return None

    def _get_cross_project_insights(
        self, project_activity: List[ProjectActivity]
    ) -> Optional[Dict[str, Any]]:
        """Get cross-project intelligence: related work, shared patterns."""
        if not self.portfolio_memory:
            return None

        try:
            # Get portfolio-wide patterns
            cross_patterns = self.portfolio_memory.get_cross_project_patterns()

            # Find patterns used in multiple active projects
            active_project_names = (
                set(p.name for p in project_activity if p.commits_7d > 0)
                if project_activity
                else set()
            )
            shared_patterns = []
            for pattern in cross_patterns[:10]:
                pattern_projects = set(u["project"] for u in pattern.get("used_in", []))
                overlap = pattern_projects & active_project_names
                if len(overlap) > 1:
                    shared_patterns.append(
                        {
                            "pattern": pattern["pattern"],
                            "shared_by": list(overlap),
                            "total_projects": pattern["count"],
                        }
                    )

            # Get relevant lessons learned
            lessons = self.portfolio_memory.get_lessons_learned()
            relevant_lessons = []
            for lesson in lessons[:5]:
                if lesson.get("project") in active_project_names:
                    relevant_lessons.append(lesson)

            # Get portfolio health summary
            health_summary = None
            try:
                health_data = self.portfolio_memory.get_portfolio_health_summary(days=7)
                if "error" not in health_data:
                    health_summary = {
                        "healthy_count": len(health_data["aggregate"]["healthy_projects"]),
                        "at_risk_count": len(health_data["aggregate"]["at_risk_projects"]),
                        "critical_count": len(health_data["aggregate"]["critical_projects"]),
                        "overall_score": health_data.get("overall", {}).get("score", 0),
                    }
            except Exception:
                pass

            return {
                "shared_patterns": shared_patterns[:3],
                "relevant_lessons": relevant_lessons[:3],
                "portfolio_health": health_summary,
                "total_patterns_in_use": len(
                    [
                        p
                        for p in cross_patterns
                        if any(u["project"] in active_project_names for u in p.get("used_in", []))
                    ]
                ),
            }
        except Exception as e:
            print(f"Warning: Could not get cross-project insights: {e}", file=sys.stderr)
            return None

    def _get_predictive_insights(
        self,
        project_activity: List[ProjectActivity],
        goals: List[Goal],
        temporal_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Generate predictive insights: likely focus, optimal sequence."""
        try:
            predictions = []

            # Predict likely project focus based on recent activity
            if project_activity:
                # Sort by recent activity
                sorted_projects = sorted(
                    [p for p in project_activity if p.commits_7d > 0],
                    key=lambda p: (p.commits_7d, p.uncommitted_changes),
                    reverse=True,
                )

                if sorted_projects:
                    top_project = sorted_projects[0]
                    predictions.append(
                        {
                            "type": "likely_focus",
                            "prediction": f"Continue work on {top_project.name}",
                            "confidence": ("high" if top_project.commits_7d >= 5 else "medium"),
                            "reason": f"{top_project.commits_7d} commits this week, {top_project.uncommitted_changes} uncommitted changes",
                        }
                    )

            # Predict blockers based on patterns
            if goals:
                stalled_goals = [
                    g for g in goals if g.status == "in_progress" and g.priority == "A"
                ]
                for goal in stalled_goals[:2]:
                    if goal.blockers:
                        predictions.append(
                            {
                                "type": "potential_blocker",
                                "prediction": f"'{goal.title}' may stall",
                                "confidence": "medium",
                                "reason": f"Has unresolved blockers: {goal.blockers[0]}",
                            }
                        )

            # Optimal sequence based on time of day and energy
            optimal_sequence = []
            if temporal_context:
                time_of_day = temporal_context.get("time_of_day", "morning")
                day_pattern = temporal_context.get("day_pattern", {})

                # Morning: complex tasks first
                if time_of_day == "morning":
                    high_effort_tasks = [
                        a
                        for a in (goals or [])
                        if a.status in ["pending", "in_progress"] and a.priority == "A"
                    ][:2]
                    for task in high_effort_tasks:
                        optimal_sequence.append(
                            {
                                "task": task.title,
                                "reason": "High-priority - tackle while energy is high",
                                "project": task.project,
                            }
                        )

                # Afternoon: reviews and lighter tasks
                elif time_of_day == "afternoon":
                    if project_activity:
                        projects_with_uncommitted = [
                            p for p in project_activity if p.uncommitted_changes > 0
                        ][:2]
                        for proj in projects_with_uncommitted:
                            optimal_sequence.append(
                                {
                                    "task": f"Review and commit changes in {proj.name}",
                                    "reason": f"{proj.uncommitted_changes} uncommitted changes",
                                    "project": proj.name,
                                }
                            )

                # Friday special: cleanup tasks
                if day_pattern.get("pattern") == "week_close":
                    optimal_sequence.insert(
                        0,
                        {
                            "task": "Review and commit all pending changes",
                            "reason": "End of week - clean slate for Monday",
                            "project": "Portfolio-wide",
                        },
                    )

            return {
                "predictions": predictions[:3],
                "optimal_sequence": optimal_sequence[:3],
                "confidence_note": "Based on activity patterns and temporal context",
            }
        except Exception as e:
            print(f"Warning: Could not generate predictive insights: {e}", file=sys.stderr)
            return None

    def _get_resource_intelligence(self) -> Optional[Dict[str, Any]]:
        """
        Get AIO resource intelligence: consumption, pacing, optimization opportunities.

        This is HIGH-VALUE data for understanding API usage patterns and costs.
        """
        if not self.usage_optimizer:
            return None

        try:
            # Get usage summary for last 7 days
            usage_summary = self.usage_optimizer.get_usage_summary(days=7)
            compliance = self.usage_optimizer.get_compliance_report()

            # Calculate burn rate and pacing
            targets = compliance.get("targets", {})
            current = compliance.get("current", {})
            batch_usage = compliance.get("batch_usage", {})

            daily_hours = current.get("daily_real_time_hours", 0)
            target_hours = targets.get("daily_target_hours", 8.6)
            weekly_limit = targets.get("weekly_limit_hours", 60)

            # Normalize likely minute-based values if telemetry source changed units.
            # Heuristic: daily "hours" above 24 are implausible as true hours.
            if daily_hours > 24:
                daily_hours = daily_hours / 60.0
                current_weekly = current.get("weekly_real_time_hours", 0)
                if current_weekly > weekly_limit * 2:
                    current["weekly_real_time_hours"] = current_weekly / 60.0

            # Pacing status
            if daily_hours <= target_hours * 0.8:
                pacing_status = "under_budget"
                pacing_emoji = "🟢"
                pacing_advice = "Room to push harder on complex tasks"
            elif daily_hours <= target_hours:
                pacing_status = "on_track"
                pacing_emoji = "🟡"
                pacing_advice = "Sustainable pace - maintain current intensity"
            elif daily_hours <= target_hours * 1.3:
                pacing_status = "elevated"
                pacing_emoji = "🟠"
                pacing_advice = "Consider batching research tasks overnight"
            else:
                pacing_status = "over_budget"
                pacing_emoji = "🔴"
                pacing_advice = "High burn rate - shift to batch API immediately"

            # Batch optimization opportunities
            optimization = usage_summary.get("optimization", {})
            missed_opportunities = optimization.get("missed_opportunities", 0)
            potential_savings = optimization.get("potential_additional_savings", 0)

            # Weekly projection
            days_remaining = 7 - datetime.now().weekday()  # Days until week reset  # noqa: DTZ005
            projected_weekly = daily_hours * 7
            will_hit_limit = projected_weekly > weekly_limit

            return {
                "pacing": {
                    "status": pacing_status,
                    "emoji": pacing_emoji,
                    "daily_hours": round(daily_hours, 1),
                    "target_hours": target_hours,
                    "advice": pacing_advice,
                },
                "weekly": {
                    "used_hours": round(current.get("weekly_real_time_hours", 0), 1),
                    "limit_hours": weekly_limit,
                    "days_remaining": days_remaining,
                    "projected_total": round(projected_weekly, 1),
                    "will_hit_limit": will_hit_limit,
                },
                "batch_optimization": {
                    "current_percentage": batch_usage.get("percentage", 0),
                    "target_percentage": batch_usage.get("target_percentage", 40),
                    "on_track": batch_usage.get("on_track", False),
                    "missed_opportunities": missed_opportunities,
                    "potential_savings": round(potential_savings, 2),
                },
                "costs": {
                    "real_time_cost": usage_summary.get("real_time", {}).get("estimated_cost", 0),
                    "batch_cost": usage_summary.get("batch", {}).get("estimated_cost", 0),
                    "total_savings": usage_summary.get("batch", {}).get("total_savings", 0),
                },
                "recommendations": compliance.get("recommendations", []),
            }
        except Exception as e:
            print(f"Warning: Could not get resource intelligence: {e}", file=sys.stderr)
            return None

    def _get_orchestration_advisory(
        self,
        resource_intel: Optional[Dict[str, Any]],
        batch_queue_status: Optional[Dict[str, Any]],
        project_activity: List[ProjectActivity],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate orchestration recommendations: batch vs interactive, agent deployment.

        This advises on HOW to work, not just WHAT to work on.
        """
        try:
            advisory = {
                "mode_recommendation": None,
                "agent_recommendations": [],
                "batch_candidates": [],
                "parallelization_opportunities": [],
            }

            # Determine recommended mode based on resource status
            if resource_intel:
                pacing = resource_intel.get("pacing", {})
                status = pacing.get("status", "on_track")

                if status == "over_budget":
                    advisory["mode_recommendation"] = {
                        "mode": "batch_priority",
                        "reason": "High burn rate - queue non-urgent work for overnight batch",
                        "actions": [
                            "Use /batch-submit for research tasks",
                            "Defer code reviews to batch processing",
                            "Focus interactive sessions on critical path only",
                        ],
                    }
                elif status == "under_budget":
                    advisory["mode_recommendation"] = {
                        "mode": "interactive_ok",
                        "reason": "Under budget - can use interactive sessions freely",
                        "actions": [
                            "Tackle complex, iterative tasks interactively",
                            "Use deep exploration for architecture decisions",
                            "Consider proactive code improvements",
                        ],
                    }
                else:
                    advisory["mode_recommendation"] = {
                        "mode": "balanced",
                        "reason": "Sustainable pace - balance batch and interactive",
                        "actions": [
                            "Batch research and analysis tasks",
                            "Keep implementation interactive",
                            "Review batch results in morning",
                        ],
                    }

            # Agent deployment recommendations based on pending work
            if project_activity:
                active_projects = [p for p in project_activity if p.commits_7d > 0]

                # Test orchestrator recommendation
                projects_with_changes = [p for p in active_projects if p.uncommitted_changes > 0]
                if projects_with_changes:
                    advisory["agent_recommendations"].append(
                        {
                            "agent": "test-orchestrator",
                            "reason": f"{len(projects_with_changes)} projects with uncommitted changes",
                            "trigger": "Run before committing to catch issues early",
                        }
                    )

                # Multi-project activity - suggest parallelization
                if len(active_projects) >= 3:
                    advisory["parallelization_opportunities"].append(
                        {
                            "opportunity": "Cross-project batch analysis",
                            "projects": [p.name for p in active_projects[:5]],
                            "action": "Submit batch job for portfolio-wide code review",
                        }
                    )

            # Batch candidates from pending work
            if batch_queue_status:
                pending = batch_queue_status.get("pending_count", 0)
                scheduled = batch_queue_status.get("scheduled_count", 0)
                if pending + scheduled > 0:
                    advisory["batch_candidates"].append(
                        {
                            "type": "queued_tasks",
                            "count": pending + scheduled,
                            "status": "Ready for batch submission",
                        }
                    )

            # Suggest batching research if not already doing so
            batch_opt = resource_intel.get("batch_optimization", {}) if resource_intel else {}
            if batch_opt.get("current_percentage", 0) < batch_opt.get("target_percentage", 40):
                advisory["batch_candidates"].append(
                    {
                        "type": "research_tasks",
                        "suggestion": "Queue documentation and research queries for batch",
                        "potential_savings": f"${batch_opt.get('potential_savings', 0):.2f}/week",
                    }
                )

            return advisory
        except Exception as e:
            print(
                f"Warning: Could not generate orchestration advisory: {e}",
                file=sys.stderr,
            )
            return None

    def _get_batch_insights(self) -> Optional[Dict[str, Any]]:
        """
        Extract overnight batch insights from completed AI analysis tasks.

        Queries the SQLite batch queue for tasks completed in the last 24h,
        groups them by category (json_job_id prefix), and extracts the first
        ~200 chars of each result as a summary.
        """
        try:
            import sqlite3
            from pathlib import Path

            db_path = Path.home() / ".cortex" / "batch_queue.db"
            if not db_path.exists():
                return None

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    json_extract(metadata, '$.json_job_id') as job_id,
                    json_extract(metadata, '$.source') as source,
                    description,
                    length(stdout) as output_size,
                    substr(stdout, 1, 300) as output_preview,
                    completed_at,
                    actual_duration_seconds
                FROM batch_tasks
                WHERE state = 'completed'
                    AND json_extract(metadata, '$.sync_origin') = 'queue_sync'
                    AND completed_at >= datetime('now', '-24 hours')
                    AND stdout IS NOT NULL
                    AND length(stdout) > 50
                ORDER BY completed_at DESC
                LIMIT 20
            """
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return None

            # Group by category, stripping instance-specific suffixes.
            # "commit-analysis-87f54fbd" -> "commit-analysis" (hex hash)
            # "strategic-planning-20260209" -> "strategic-planning" (date)
            # "docs-completeness" -> "docs-completeness" (keep — suffix is a word)
            import re

            def _job_category(job_id: str) -> str:
                parts = job_id.rsplit("-", 1)
                if len(parts) == 2:
                    suffix = parts[1]
                    # Strip hex hashes (e.g. 87f54fbd) or dates (20260209)
                    if re.fullmatch(r"[0-9a-f]{6,}", suffix) or re.fullmatch(r"\d{8,}", suffix):
                        return parts[0]
                return job_id

            categories = {}
            for row in rows:
                job_id = row["job_id"] or "unknown"
                category = _job_category(job_id)

                if category not in categories:
                    categories[category] = []
                categories[category].append(
                    {
                        "job_id": job_id,
                        "description": row["description"],
                        "output_size": row["output_size"],
                        "preview": row["output_preview"],
                        "duration_s": row["actual_duration_seconds"],
                    }
                )

            return {
                "total_completed_24h": len(rows),
                "categories": {
                    cat: {
                        "count": len(items),
                        "total_output_kb": round(sum(i["output_size"] for i in items) / 1024, 1),
                        "sample_description": items[0]["description"],
                    }
                    for cat, items in categories.items()
                },
                "total_output_kb": round(sum(r["output_size"] for r in rows) / 1024, 1),
                "avg_duration_s": round(
                    sum(r["actual_duration_seconds"] or 0 for r in rows) / len(rows), 1
                ),
            }

        except Exception as e:
            print(f"Warning: Could not get batch insights: {e}", file=sys.stderr)
            return None

    def _get_velocity_metrics(self) -> Optional[Dict[str, Any]]:
        """Get velocity and ROI metrics from MetricsTracker."""
        if not self.metrics_tracker:
            return None

        try:
            velocity = self.metrics_tracker.get_velocity_stats(days=30)
            # Note: Additional metrics like mistakes and calibration could be added

            if velocity.get("total_tasks", 0) == 0:
                return None

            return {
                "total_tasks": velocity.get("total_tasks", 0),
                "total_savings_hours": velocity.get("total_savings_hours", 0),
                "avg_improvement_pct": velocity.get("avg_improvement_pct", 0),
                "by_project": velocity.get("by_project", {}),
                "roi_summary": f"{velocity.get('total_savings_hours', 0):.1f} hours saved across {velocity.get('total_tasks', 0)} tasks",
            }
        except Exception as e:
            print(f"Warning: Could not get velocity metrics: {e}", file=sys.stderr)
            return None

    def _get_bandwidth_contract_metrics(self) -> Optional[Dict[str, Any]]:
        """Get Phase 1 contract metrics from bandwidth research store."""
        if not self.contract_metrics_store:
            return None

        try:
            metrics = self.contract_metrics_store.aggregate(days=7)
            if metrics.get("sessions", 0) == 0:
                return None
            return metrics
        except Exception as e:
            print(f"Warning: Could not get bandwidth contract metrics: {e}", file=sys.stderr)
            return None

    def _get_queue_slo_metrics(self) -> Optional[Dict[str, Any]]:
        """Get interaction queue SLO status."""
        if not check_queue_slo:
            return None
        try:
            return check_queue_slo()
        except Exception as e:
            print(f"Warning: Could not get queue SLO metrics: {e}", file=sys.stderr)
            return None


def generate_daily_briefing(root_dir: Optional[Path] = None) -> BriefingData:
    """
    Convenience function to generate daily briefing.

    Args:
        root_dir: Root directory to scan (default: ~/projects)

    Returns:
        BriefingData with briefing information
    """
    generator = BriefingGenerator(root_dir)
    return generator.generate_daily_briefing()


# format_briefing migrated to briefing/formatters.py — see re-export below.


# format_briefing_json migrated to briefing/formatters.py — see re-export below.


# format_statusline migrated to briefing/formatters.py — see re-export below.


# format_statusline_json + get_executive_summary migrated to
# briefing/formatters.py. Re-exported at the bottom of this file.




# ============================================================================
# Re-exports for the briefing/formatters.py split (Phase 3b)
# ============================================================================
# Functions migrated to briefing.formatters are re-exported here so existing
# `from briefing import X` import sites continue to work unchanged. New
# callers should import directly from briefing.formatters.
from briefing.formatters import (  # noqa: E402
    _load_briefing_style,
    _build_progress_bar,
    detect_resume_context,
    detect_stale_items,
    format_briefing,
    format_briefing_json,
    format_compact,
    format_statusline,
    format_statusline_json,
    get_executive_summary,
)
from briefing.signal_quality import (  # noqa: E402
    _compute_signal_quality,
    _sparkline,
    get_briefing_signal_quality,
)


if __name__ == "__main__":
    # Test the briefing generator
    briefing = generate_daily_briefing()
    print(format_briefing(briefing))
    print("\n--- EXECUTIVE SUMMARY ---\n")
    print(get_executive_summary(briefing))
