#!/usr/bin/env python3
"""
Briefing Generator - Daily briefing system for cross-project status

Synthesizes:
- Portfolio pulse (active projects, commits, blockers)
- Priority actions (top recommendations)
- Patterns noticed (activity trends)
- Waiting on (decisions needed)
"""

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


class BriefingGenerator:
    """Generate daily briefings from cross-project data."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
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
                recommendations = self.recommendation_engine.generate_recommendations(
                    project_activity=project_activity if project_activity else None,
                    limit=5,
                )
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
            generated_at=datetime.now(),
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
        )

        return briefing

    def _get_active_projects(self, projects: List[ProjectActivity]) -> List[str]:
        """Get list of active project names."""
        if not projects:
            return []

        # Active = has commits in last 7 days
        active = [p.name for p in projects if p.commits_7d > 0]

        # Sort by activity (most commits first)
        active.sort(
            key=lambda name: next((p.commits_7d for p in projects if p.name == name), 0),
            reverse=True,
        )

        return active

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
        now = datetime.now()

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

            # Remove project prefix (e.g., "cortex: " or "VortexV2: ")
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

        # 1. Most productive project
        active_projects = [p for p in projects if p.commits_7d > 0]
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
            now = datetime.now()
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
            days_remaining = 7 - datetime.now().weekday()  # Days until week reset
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
            cursor = conn.execute("""
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
            """)
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


def generate_daily_briefing(root_dir: Optional[Path] = None) -> BriefingData:
    """
    Convenience function to generate daily briefing.

    Args:
        root_dir: Root directory to scan (default: /Users/jesse.kemp/Dev)

    Returns:
        BriefingData with briefing information
    """
    generator = BriefingGenerator(root_dir)
    return generator.generate_daily_briefing()


def format_briefing(briefing: BriefingData, use_color: bool = True) -> str:
    """
    Format briefing data into readable text output.

    Args:
        briefing: BriefingData to format
        use_color: Use terminal colors (if available)

    Returns:
        Formatted briefing string
    """
    lines = []

    # Try to use rich/colorama for colors, fallback to plain text
    try:
        if use_color:
            from colorama import Fore, Style, init

            init(autoreset=True)
            BOLD = Style.BRIGHT
            RESET = Style.RESET_ALL
            BLUE = Fore.BLUE
            GREEN = Fore.GREEN
            YELLOW = Fore.YELLOW
            RED = Fore.RED
        else:
            raise ImportError
    except ImportError:
        BOLD = RESET = BLUE = GREEN = YELLOW = RED = ""

    # Header
    lines.append("=" * 64)
    lines.append(f"{BOLD}DAILY BRIEFING - {briefing.generated_at.strftime('%B %d, %Y')}{RESET}")
    lines.append("=" * 64)
    lines.append("")

    # ==================== TL;DR SECTION ====================
    lines.append(f"{BOLD}TL;DR{RESET}")
    lines.append("")

    # Portfolio status bullet
    active_count = len(briefing.active_projects)
    blocker_count = len(briefing.blockers)
    blocker_status = (
        f"{RED}{blocker_count} blockers{RESET}"
        if blocker_count > 0
        else f"{GREEN}no blockers{RESET}"
    )
    lines.append(
        f"  • {BOLD}Portfolio:{RESET} {active_count} active projects, {briefing.total_commits_7d} commits this week, {blocker_status}"
    )

    # Top priority bullet
    if briefing.priority_actions:
        top = briefing.priority_actions[0]
        priority_color = (
            RED if top["priority"] == "HIGH" else YELLOW if top["priority"] == "MEDIUM" else GREEN
        )
        lines.append(
            f"  • {BOLD}Top Priority:{RESET} [{priority_color}{top['priority']}{RESET}] {top['title']}"
        )

    # Git status bullet
    if briefing.git_status and briefing.git_status.get("summary"):
        gs = briefing.git_status["summary"]
        branch = gs.get("current_branch", "unknown")
        modified = gs.get("working_tree", {}).get("modified", 0)
        untracked = gs.get("working_tree", {}).get("untracked", 0)
        pr_count = len(gs.get("pull_requests", []))
        pr_text = f", {pr_count} open PR{'s' if pr_count != 1 else ''}" if pr_count > 0 else ""
        lines.append(
            f"  • {BOLD}Git:{RESET} on `{branch}`, {modified} modified, {untracked} untracked{pr_text}"
        )

    # Work progress bullet
    if briefing.work_progress:
        wp = briefing.work_progress
        items_24h = wp.get("items_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)
        drifts = wp.get("drifts_total", 0)
        orphan_text = f", {YELLOW}{orphaned} unplanned{RESET}" if orphaned > 0 else ""
        drift_text = f", {YELLOW}{drifts} drift items{RESET}" if drifts > 0 else ""
        lines.append(f"  • {BOLD}Work:{RESET} {items_24h} items today{orphan_text}{drift_text}")

    # Resource status bullet
    if briefing.resource_status:
        rs = briefing.resource_status
        cpu_avail = rs.get("cpu_available", 0)
        mem_used = rs.get("memory_usage_percent", 0)
        cpu_color = RED if cpu_avail < 30 else YELLOW if cpu_avail < 60 else GREEN
        mem_color = RED if mem_used > 80 else YELLOW if mem_used > 60 else GREEN
        waste = rs.get("waste_items", 0)
        waste_text = f", {YELLOW}{waste} waste items{RESET}" if waste > 10 else ""
        lines.append(
            f"  • {BOLD}System:{RESET} {cpu_color}{cpu_avail:.0f}% CPU free{RESET}, {mem_color}{mem_used:.0f}% mem used{RESET}{waste_text}"
        )

    # Batch queue bullet
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status
        running = bq.get("running_count", 0)
        pending = bq.get("pending_count", 0) + bq.get("scheduled_count", 0)
        failed = bq.get("failed_count", 0)
        if running > 0 or pending > 0 or failed > 0:
            parts = []
            if running > 0:
                parts.append(f"{running} running")
            if pending > 0:
                parts.append(f"{pending} queued")
            if failed > 0:
                parts.append(f"{RED}{failed} failed{RESET}")
            lines.append(f"  • {BOLD}Batch:{RESET} {', '.join(parts)}")

    # V2a Batch orchestration status
    try:
        from batch.v2a_sprint_orchestrator import V2aSprintOrchestrator

        orchestrator = V2aSprintOrchestrator()
        v2a_status = orchestrator.get_overall_status()

        if v2a_status["total_tasks"] > 0:
            completed = v2a_status["completed"]
            total = v2a_status["total_tasks"]
            current_wave = v2a_status["current_wave"]
            progress_pct = v2a_status["progress_pct"]

            if progress_pct >= 100:
                lines.append(f"  • {BOLD}V2a Batch:{RESET} {GREEN}All complete ✓{RESET}")
            elif v2a_status["running"] > 0:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {current_wave} in progress ({completed}/{total} complete, {progress_pct:.0f}%)"
                )
            elif v2a_status["failed"] > 0:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {RED}{v2a_status['failed']} failed{RESET} ({completed}/{total} complete)"
                )
            else:
                lines.append(
                    f"  • {BOLD}V2a Batch:{RESET} {completed}/{total} complete ({progress_pct:.0f}%), ready for {current_wave}"
                )
    except Exception:
        # V2a batch orchestration may not be active
        pass

    # Temporal context bullet (day intelligence)
    if briefing.temporal_context:
        tc = briefing.temporal_context
        day = tc.get("day_of_week", "")
        day_pattern = tc.get("day_pattern", {})
        suggestion = day_pattern.get("suggestion", "")
        if suggestion:
            lines.append(f"  • {BOLD}Today:{RESET} {day} - {suggestion[:50]}")

    # Strategic alignment bullet (drift warning)
    if briefing.strategic_alignment:
        sa = briefing.strategic_alignment
        if sa.get("has_strategic_drift"):
            drift_count = len(sa.get("drift_indicators", []))
            lines.append(
                f"  • {BOLD}Strategy:{RESET} {YELLOW}⚠ {drift_count} drift indicator{'s' if drift_count != 1 else ''} detected{RESET}"
            )
        else:
            velocity = sa.get("velocity_status", "unknown")
            if velocity == "healthy":
                lines.append(f"  • {BOLD}Strategy:{RESET} {GREEN}On track{RESET}")

    # Predictive insight bullet
    if briefing.predictive_insights:
        pi = briefing.predictive_insights
        predictions = pi.get("predictions", [])
        if predictions:
            top_pred = predictions[0]
            conf = top_pred.get("confidence", "medium")
            conf_color = GREEN if conf == "high" else YELLOW
            lines.append(
                f"  • {BOLD}Predicted:{RESET} [{conf_color}{conf.upper()}{RESET}] {top_pred['prediction'][:45]}"
            )

    lines.append("")
    lines.append("-" * 64)
    lines.append("")

    # ==================== RESOURCE INTELLIGENCE (HIGH-VALUE) ====================

    if briefing.resource_intelligence:
        ri = briefing.resource_intelligence
        pacing = ri.get("pacing", {})
        weekly = ri.get("weekly", {})
        batch_opt = ri.get("batch_optimization", {})

        lines.append(f"{BOLD}⚡ RESOURCE INTELLIGENCE{RESET}")
        lines.append("")

        # Pacing status - THE most important metric
        emoji = pacing.get("emoji", "🟡")
        status = pacing.get("status", "unknown").replace("_", " ").title()
        daily_hrs = pacing.get("daily_hours", 0)
        target_hrs = pacing.get("target_hours", 8.6)
        advice = pacing.get("advice", "")

        status_color = (
            GREEN
            if pacing.get("status") == "under_budget"
            else YELLOW
            if pacing.get("status") in ["on_track", "elevated"]
            else RED
        )
        lines.append(
            f"  {emoji} {BOLD}Pacing:{RESET} {status_color}{status}{RESET} ({daily_hrs:.1f}h/day vs {target_hrs:.1f}h target)"
        )
        if advice:
            lines.append(f"     → {advice}")

        # Weekly projection
        used = weekly.get("used_hours", 0)
        limit = weekly.get("limit_hours", 60)
        days_left = weekly.get("days_remaining", 0)
        projected = weekly.get("projected_total", 0)
        will_hit = weekly.get("will_hit_limit", False)

        pct_used = (used / limit * 100) if limit > 0 else 0
        weekly_color = GREEN if pct_used < 70 else YELLOW if pct_used < 90 else RED
        lines.append(
            f"  📊 {BOLD}Weekly:{RESET} {weekly_color}{used:.1f}h/{limit}h used ({pct_used:.0f}%){RESET}, {days_left} days left"
        )
        if will_hit:
            lines.append(f"     {RED}⚠ Projected to hit limit at current pace{RESET}")

        # Batch optimization
        batch_pct = batch_opt.get("current_percentage", 0)
        batch_target = batch_opt.get("target_percentage", 40)
        on_track = batch_opt.get("on_track", False)
        potential_savings = batch_opt.get("potential_savings", 0)

        batch_color = GREEN if on_track else YELLOW
        lines.append(
            f"  🔄 {BOLD}Batch API:{RESET} {batch_color}{batch_pct:.0f}%{RESET} of work (target: {batch_target}%)"
        )
        if not on_track and potential_savings > 0:
            lines.append(f"     → Shift more to batch: save ${potential_savings:.2f}/week")

        lines.append("")

    # ==================== ORCHESTRATION ADVISORY ====================

    if briefing.orchestration_advisory:
        oa = briefing.orchestration_advisory
        mode_rec = oa.get("mode_recommendation")

        lines.append(f"{BOLD}🎮 ORCHESTRATION ADVISORY{RESET}")
        lines.append("")

        # Mode recommendation
        if mode_rec:
            mode = mode_rec.get("mode", "balanced")
            reason = mode_rec.get("reason", "")
            actions = mode_rec.get("actions", [])

            mode_emoji = (
                "🟢" if mode == "interactive_ok" else "🔴" if mode == "batch_priority" else "🟡"
            )
            mode_label = mode.replace("_", " ").title()
            lines.append(f"  {mode_emoji} {BOLD}Recommended Mode:{RESET} {mode_label}")
            lines.append(f"     {reason}")
            if actions:
                lines.append("     Actions:")
                for action in actions[:2]:
                    lines.append(f"       • {action}")

        # Agent recommendations
        agent_recs = oa.get("agent_recommendations", [])
        if agent_recs:
            lines.append(f"  🤖 {BOLD}Deploy Agents:{RESET}")
            for rec in agent_recs[:2]:
                lines.append(f"     • {rec['agent']}: {rec['reason']}")

        # Parallelization opportunities
        parallel = oa.get("parallelization_opportunities", [])
        if parallel:
            lines.append(f"  ⚡ {BOLD}Parallelize:{RESET}")
            for opp in parallel[:1]:
                lines.append(f"     • {opp['opportunity']}")

        lines.append("")

    # ==================== VELOCITY & ROI ====================

    if briefing.velocity_metrics:
        vm = briefing.velocity_metrics
        lines.append(f"{BOLD}📈 VELOCITY & ROI{RESET}")
        total_hrs = vm.get("total_savings_hours", 0)
        tasks = vm.get("total_tasks", 0)
        avg_pct = vm.get("avg_improvement_pct", 0)

        lines.append(
            f"  30-Day Impact: {GREEN}{total_hrs:.1f} hours saved{RESET} across {tasks} tasks ({avg_pct:.0f}% faster)"
        )

        by_project = vm.get("by_project", {})
        if by_project:
            top_projects = sorted(
                by_project.items(), key=lambda x: x[1].get("savings", 0), reverse=True
            )[:3]
            if top_projects:
                lines.append("  Top contributors:")
                for proj, data in top_projects:
                    lines.append(f"    • {proj}: {data.get('savings', 0):.0f} min saved")

        lines.append("")

    lines.append("-" * 64)
    lines.append("")

    # ==================== EXPANDED DETAILS ====================

    # Portfolio Pulse
    lines.append(f"{BOLD}PORTFOLIO PULSE{RESET}")
    lines.append(
        f"  Active projects: {len(briefing.active_projects)} ({', '.join(briefing.active_projects[:5])}{'...' if len(briefing.active_projects) > 5 else ''})"
    )
    lines.append(
        f"  Recent commits: {briefing.recent_commits_24h} in last 24h, {briefing.total_commits_7d} in last 7d"
    )

    if briefing.blockers:
        lines.append(f"  {RED}Blockers: {len(briefing.blockers)}{RESET}")
        for blocker in briefing.blockers[:3]:
            lines.append(f"    - {blocker['project']}: {blocker['blocker']}")
    else:
        lines.append(f"  {GREEN}Blockers: None{RESET}")

    lines.append("")

    # Git & GitHub Status
    if briefing.git_status and briefing.git_status.get("formatted"):
        lines.append(briefing.git_status["formatted"])
        lines.append("")

    # Work Progress (from Work Absorber)
    if briefing.work_progress:
        wp = briefing.work_progress
        lines.append(f"{BOLD}WORK PROGRESS{RESET}")

        items_24h = wp.get("items_24h", 0)
        items_7d = wp.get("items_7d", 0)
        correlated = wp.get("correlated_24h", 0)
        orphaned = wp.get("orphaned_24h", 0)

        lines.append(f"  Work items: {items_24h} in 24h, {items_7d} in 7d")

        if items_24h > 0:
            if correlated > 0:
                lines.append(f"  {GREEN}Planned work: {correlated} items{RESET}")
            if orphaned > 0:
                lines.append(f"  {YELLOW}Unplanned work: {orphaned} items{RESET}")

        # Show drifts
        drifts = wp.get("drifts_total", 0)
        if drifts > 0:
            drift_types = wp.get("drifts_by_type", {})
            drift_summary = ", ".join(f"{k}: {v}" for k, v in list(drift_types.items())[:3])
            lines.append(f"  {YELLOW}Plan drift: {drifts} ({drift_summary}){RESET}")

        # Recent work
        recent = wp.get("recent_work", [])
        if recent:
            lines.append("  Recent:")
            for item in recent[:3]:
                scope_badge = f"[{item.get('scope', 'misc')}]" if item.get("scope") else ""
                lines.append(f"    - {item['title'][:45]} {scope_badge}")

        lines.append("")

    # Resource Pulse
    if briefing.resource_status:
        lines.append(f"{BOLD}⚡ RESOURCE PULSE{RESET}")
        rs = briefing.resource_status

        # CPU and Memory
        cpu_color = (
            RED if rs["cpu_available"] < 30 else YELLOW if rs["cpu_available"] < 60 else GREEN
        )
        mem_color = (
            RED
            if rs["memory_usage_percent"] > 80
            else YELLOW
            if rs["memory_usage_percent"] > 60
            else GREEN
        )

        lines.append(
            f"  CPU: {cpu_color}{rs['cpu_available']:.0f}% available{RESET} | Memory: {mem_color}{rs['memory_usage_percent']:.0f}% used{RESET}"
        )
        lines.append(f"  Processes: {rs['process_count']}")

        # AI Tools & Services
        if rs.get("ai_tool_cpu", 0) > 0 or rs.get("dev_service_cpu", 0) > 0:
            lines.append(
                f"  AI Tools: {rs.get('ai_tool_cpu', 0):.1f}% CPU | Dev Services: {rs.get('dev_service_cpu', 0):.1f}% CPU"
            )

        # Alerts and Waste
        alerts_color = (
            RED
            if rs.get("critical_alerts", 0) > 0
            else YELLOW
            if rs.get("alerts_count", 0) > 5
            else ""
        )
        waste_color = YELLOW if rs.get("waste_items", 0) > 10 else ""

        if rs.get("alerts_count", 0) > 0:
            lines.append(
                f"  Alerts: {alerts_color}{rs.get('alerts_count', 0)} ({rs.get('critical_alerts', 0)} critical){RESET}"
            )

        if rs.get("waste_items", 0) > 0:
            lines.append(
                f"  Resource Waste: {waste_color}{rs.get('waste_items', 0)} items detected{RESET}"
            )

        # Optimization opportunities
        if rs.get("optimization_opportunities", 0) > 0:
            lines.append(
                f"  💡 {rs.get('optimization_opportunities', 0)} optimization opportunities"
            )

        lines.append("")

    # Batch Queue Status
    if briefing.batch_queue_status:
        bq = briefing.batch_queue_status

        # Only show if there are tasks in the queue
        total_tasks = (
            bq.get("pending_count", 0) + bq.get("scheduled_count", 0) + bq.get("running_count", 0)
        )

        if total_tasks > 0 or bq.get("completed_count", 0) > 0 or bq.get("failed_count", 0) > 0:
            lines.append(f"{BOLD}📋 BATCH QUEUE{RESET}")

            # Show running tasks with details
            running_tasks = bq.get("running_tasks", [])
            if running_tasks:
                lines.append(f"  {YELLOW}▶️  Running Now:{RESET}")
                for task in running_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:50] + "..."
                        if len(task.description) > 50
                        else task.description
                    )
                    elapsed = ""
                    if task.started_at:
                        from datetime import datetime

                        elapsed_sec = (datetime.now() - task.started_at).total_seconds()
                        if elapsed_sec < 60:
                            elapsed = f" ({elapsed_sec:.0f}s elapsed)"
                        else:
                            elapsed = f" ({elapsed_sec / 60:.1f}m elapsed)"
                    lines.append(f"     • {desc}{elapsed}")
                if len(running_tasks) > 3:
                    lines.append(f"     ... and {len(running_tasks) - 3} more")
                lines.append("")

            # Show scheduled tasks with times
            scheduled_tasks = bq.get("scheduled_tasks", [])
            if scheduled_tasks:
                lines.append("  📅 Scheduled:")
                for task in scheduled_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    when = ""
                    if task.scheduled_time:
                        from datetime import datetime

                        now = datetime.now()
                        time_until = (task.scheduled_time - now).total_seconds()

                        if time_until < 0:
                            when = " (ready now)"
                        elif time_until < 60:
                            when = f" (in {time_until:.0f}s)"
                        elif time_until < 3600:
                            when = f" (in {time_until / 60:.0f}m)"
                        elif time_until < 86400:
                            when = f" (at {task.scheduled_time.strftime('%H:%M')})"
                        else:
                            when = f" ({task.scheduled_time.strftime('%b %d %H:%M')})"

                    priority_marker = ""
                    if task.priority == "immediate":
                        priority_marker = f" {RED}[!]{RESET}"
                    elif task.priority == "high":
                        priority_marker = f" {YELLOW}[H]{RESET}"

                    lines.append(f"     • {desc}{when}{priority_marker}")

                if len(scheduled_tasks) > 3:
                    lines.append(f"     ... and {len(scheduled_tasks) - 3} more")
                lines.append("")

            # Show pending tasks
            pending_tasks = bq.get("pending_tasks", [])
            if pending_tasks:
                lines.append("  ⏳ Pending (not yet scheduled):")
                for task in pending_tasks[:3]:  # Show up to 3
                    desc = (
                        task.description[:50] + "..."
                        if len(task.description) > 50
                        else task.description
                    )
                    lines.append(f"     • {desc}")
                if len(pending_tasks) > 3:
                    lines.append(f"     ... and {len(pending_tasks) - 3} more")
                lines.append("")

            # Show recent completions with details
            recent_completed = bq.get("recent_completed", [])
            if recent_completed:
                lines.append(f"  {GREEN}✅ Recently Completed:{RESET}")
                for task in recent_completed:
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    duration = ""
                    if task.actual_duration_seconds is not None:
                        if task.actual_duration_seconds < 1:
                            duration = f" ({task.actual_duration_seconds * 1000:.0f}ms)"
                        elif task.actual_duration_seconds < 60:
                            duration = f" ({task.actual_duration_seconds:.1f}s)"
                        else:
                            duration = f" ({task.actual_duration_seconds / 60:.1f}m)"
                    lines.append(f"     • {desc}{duration}")
                lines.append("")

            # Show recent failures with error details
            recent_failed = bq.get("recent_failed", [])
            if recent_failed:
                lines.append(f"  {RED}❌ Recently Failed:{RESET}")
                for task in recent_failed:
                    desc = (
                        task.description[:45] + "..."
                        if len(task.description) > 45
                        else task.description
                    )
                    lines.append(f"     • {desc}")
                    if task.error_message:
                        error = (
                            task.error_message[:60] + "..."
                            if len(task.error_message) > 60
                            else task.error_message
                        )
                        lines.append(f"       Error: {error}")
                lines.append(f"  💡 View details: {BLUE}cortex batch list --state failed{RESET}")
                lines.append("")

            # Show overall stats summary
            if bq.get("completed_count", 0) > 0 or bq.get("failed_count", 0) > 0:
                completed = bq.get("completed_count", 0)
                failed = bq.get("failed_count", 0)
                total = completed + failed

                if total > 0:
                    success_rate = bq.get("success_rate", 0)
                    success_color = (
                        GREEN if success_rate >= 0.9 else YELLOW if success_rate >= 0.7 else RED
                    )
                    lines.append(
                        f"  Overall: {completed} completed, {failed} failed ({success_color}{success_rate:.0%} success{RESET})"
                    )
                    lines.append("")

            lines.append("")

    # Overnight Batch Insights (AI analysis results from last 24h)
    if briefing.batch_insights:
        bi = briefing.batch_insights
        lines.append(f"{BOLD}🔬 OVERNIGHT BATCH INSIGHTS{RESET}")
        lines.append(
            f"  {bi['total_completed_24h']} analyses completed "
            f"({bi['total_output_kb']:.0f} KB output, "
            f"avg {bi['avg_duration_s']:.0f}s each)"
        )
        lines.append("")

        # Show categories with counts
        category_labels = {
            "commit-analysis": "Commit Reviews",
            "security-commit": "Security Scans",
            "test-failure": "Test Failure Analysis",
            "todo-analysis": "TODO/FIXME Scans",
            "strategic-planning": "Strategic Planning",
            "performance-analysis": "Performance Analysis",
            "dependency-audit": "Dependency Audit",
            "docs-completeness": "Documentation Audit",
            "code-quality-scan": "Code Quality",
            "test-coverage-analysis": "Test Coverage Gaps",
            "api-docs-generation": "API Docs",
        }
        for cat, info in sorted(bi["categories"].items(), key=lambda x: -x[1]["count"]):
            label = category_labels.get(cat, cat.replace("-", " ").title())
            lines.append(f"  • {label}: {info['count']} runs, {info['total_output_kb']:.0f} KB")

        lines.append("")
        lines.append(
            f"  💡 Query results: {BLUE}sqlite3 ~/.cortex/batch_queue.db "
            f'"SELECT description, substr(stdout,1,500) FROM batch_tasks '
            f"WHERE state='completed' ORDER BY completed_at DESC LIMIT 5;\"{RESET}"
        )
        lines.append("")

    # V2a Sprint Batch Status (if active)
    if briefing.batch_queue_status and "v2a_sprint" in briefing.batch_queue_status:
        v2a = briefing.batch_queue_status["v2a_sprint"]

        # Only show if there are active V2a tasks
        if v2a.get("total_tasks", 0) > 0:
            lines.append(f"{BOLD}🌊 V2A SPRINT BATCH{RESET}")

            progress_pct = v2a.get("progress_pct", 0)
            completed = v2a.get("completed", 0)
            total = v2a.get("total_tasks", 0)
            running = v2a.get("running", 0)
            failed = v2a.get("failed", 0)

            # Progress bar
            progress_color = GREEN if progress_pct >= 75 else YELLOW if progress_pct >= 25 else ""
            lines.append(
                f"  Progress: {progress_color}{completed}/{total} tasks ({progress_pct:.0f}%){RESET}"
            )

            if running > 0:
                lines.append(f"  {YELLOW}▶️  {running} running{RESET}")

            if failed > 0:
                lines.append(f"  {RED}❌ {failed} failed{RESET}")

            # Current wave
            current_wave = v2a.get("current_wave", "unknown")
            lines.append(f"  Current wave: {current_wave}")

            # Wave breakdown
            waves = v2a.get("waves", {})
            if waves:
                lines.append("")
                for wave_id in ["wave_1", "wave_2", "wave_3", "wave_4"]:
                    if wave_id in waves:
                        wave = waves[wave_id]
                        wave_completed = wave.get("completed", 0)
                        wave_total = wave.get("total", 0)
                        wave_progress = wave.get("progress_pct", 0)

                        if wave_completed == wave_total and wave_total > 0:
                            icon = "✅"
                        elif wave.get("running", 0) > 0:
                            icon = "🔄"
                        elif wave.get("ready", 0) > 0:
                            icon = "📋"
                        else:
                            icon = "⏸️"

                        status_text = f"{wave_completed}/{wave_total} ({wave_progress:.0f}%)"

                        if wave.get("ready", 0) > 0:
                            status_text += f" • {GREEN}{wave['ready']} ready{RESET}"
                        elif wave.get("blocked", 0) > 0:
                            status_text += f" • {wave['blocked']} blocked"

                        lines.append(f"    {icon} {wave_id}: {status_text}")

            # Estimated remaining time
            est_remaining = v2a.get("estimated_remaining_minutes", 0)
            if est_remaining > 0:
                if est_remaining < 60:
                    est_text = f"{est_remaining:.0f} minutes"
                else:
                    est_text = f"{est_remaining / 60:.1f} hours"
                lines.append(f"\n  Estimated remaining: {est_text}")

            lines.append(f"  💡 Check status: {BLUE}cortex v2a-batch status{RESET}")
            lines.append("")

    # Priority Actions
    lines.append(f"{BOLD}PRIORITY ACTIONS{RESET}")
    if briefing.priority_actions:
        for i, action in enumerate(briefing.priority_actions, 1):
            priority_color = (
                RED
                if action["priority"] == "HIGH"
                else YELLOW
                if action["priority"] == "MEDIUM"
                else GREEN
            )

            # Title with project inline
            project_suffix = (
                f" ({action['project']})"
                if action.get("project") and action["project"] != "General"
                else ""
            )
            lines.append(
                f"  {i}. [{priority_color}{action['priority']}{RESET}] {action['title']}{project_suffix}"
            )

            # Show progress if available
            if action.get("completion_percentage", 0) > 0:
                pct = action["completion_percentage"]
                progress_bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"     Progress: [{progress_bar}] {pct}%")

            # Show steps/actions if available
            steps = action.get("steps", [])
            if steps:
                lines.append(f"     {YELLOW}Next steps:{RESET}")
                for step in steps[:3]:
                    step_text = step[:70] + "..." if len(step) > 70 else step
                    lines.append(f"       → {step_text}")

            # Show success criteria if available
            if action.get("success_criteria"):
                criteria = action["success_criteria"]
                criteria_text = criteria[:80] + "..." if len(criteria) > 80 else criteria
                lines.append(f"     {GREEN}Done when:{RESET} {criteria_text}")

            # Show effort/impact for recommendations
            if action.get("estimated_effort") or action.get("estimated_impact"):
                meta_parts = []
                if action.get("estimated_effort"):
                    meta_parts.append(f"Effort: {action['estimated_effort']}")
                if action.get("estimated_impact"):
                    meta_parts.append(f"Impact: {action['estimated_impact']}")
                if meta_parts:
                    lines.append(f"     {BLUE}{' | '.join(meta_parts)}{RESET}")

            lines.append("")  # Spacing between actions

    else:
        lines.append("  No priority actions at this time")

    lines.append("")

    # ==================== ENHANCED INTELLIGENCE SECTIONS ====================

    # Temporal Context & Day Intelligence
    if briefing.temporal_context:
        tc = briefing.temporal_context
        lines.append(f"{BOLD}🕐 TODAY'S CONTEXT{RESET}")

        day = tc.get("day_of_week", "")
        time_of_day = tc.get("time_of_day", "")
        day_pattern = tc.get("day_pattern", {})

        lines.append(f"  {day} {time_of_day.title()}")
        if day_pattern.get("suggestion"):
            lines.append(f"  💡 {day_pattern['suggestion']}")

        # Session continuity
        session = tc.get("session_continuity")
        if session and session.get("last_focus"):
            lines.append(f"  📍 Last focus: {session['current_focus'][:60]}")

        lines.append("")

    # Predictive Insights
    if briefing.predictive_insights:
        pi = briefing.predictive_insights
        predictions = pi.get("predictions", [])
        optimal_sequence = pi.get("optimal_sequence", [])

        if predictions or optimal_sequence:
            lines.append(f"{BOLD}🔮 PREDICTIVE INSIGHTS{RESET}")

            if predictions:
                for pred in predictions[:2]:
                    conf_color = GREEN if pred.get("confidence") == "high" else YELLOW
                    lines.append(
                        f"  [{conf_color}{pred.get('confidence', 'medium').upper()}{RESET}] {pred['prediction']}"
                    )
                    if pred.get("reason"):
                        lines.append(f"      ↳ {pred['reason'][:60]}")

            if optimal_sequence:
                lines.append(f"  {BLUE}Suggested sequence for today:{RESET}")
                for i, item in enumerate(optimal_sequence[:3], 1):
                    lines.append(f"    {i}. {item['task'][:50]}")

            lines.append("")

    # Strategic Alignment
    if briefing.strategic_alignment:
        sa = briefing.strategic_alignment
        lines.append(f"{BOLD}🎯 STRATEGIC ALIGNMENT{RESET}")

        # Goal velocity status
        velocity = sa.get("velocity_status", "unknown")
        velocity_color = (
            GREEN if velocity == "healthy" else YELLOW if velocity == "backlog_growing" else RED
        )
        velocity_label = {
            "healthy": "On Track",
            "blocked": "Blocked",
            "backlog_growing": "Backlog Growing",
        }.get(velocity, velocity.title())

        completed = sa.get("completed", 0)
        in_progress = sa.get("in_progress", 0)
        pending = sa.get("pending", 0)
        blocked = sa.get("blocked", 0)

        lines.append(f"  Goal Velocity: [{velocity_color}{velocity_label}{RESET}]")
        lines.append(
            f"  Goals: {completed} done, {in_progress} active, {pending} pending, {blocked} blocked"
        )

        # High priority focus
        hp_total = sa.get("high_priority_total", 0)
        hp_completed = sa.get("high_priority_completed", 0)
        if hp_total > 0:
            hp_rate = hp_completed / hp_total * 100
            hp_color = GREEN if hp_rate >= 50 else YELLOW if hp_rate >= 25 else RED
            lines.append(
                f"  High-Priority: {hp_completed}/{hp_total} ({hp_color}{hp_rate:.0f}%{RESET})"
            )

        # Drift indicators
        drift_indicators = sa.get("drift_indicators", [])
        if drift_indicators:
            lines.append(f"  {YELLOW}⚠ Strategic Drift Detected:{RESET}")
            for drift in drift_indicators[:2]:
                lines.append(f"    - {drift}")

        lines.append("")

    # Intelligence Metrics (Learning System)
    if briefing.intelligence_metrics:
        im = briefing.intelligence_metrics
        if im.get("has_sufficient_data"):
            lines.append(f"{BOLD}🧠 CORTEX LEARNING{RESET}")

            accuracy = im.get("recommendation_accuracy", 0) * 100
            accuracy_color = GREEN if accuracy >= 70 else YELLOW if accuracy >= 50 else RED
            lines.append(
                f"  Recommendation Accuracy: {accuracy_color}{accuracy:.0f}%{RESET} ({im.get('followed_count', 0)} tracked)"
            )

            # Best performing type
            best = im.get("best_performing_type")
            if best:
                lines.append(
                    f"  {GREEN}Best performing:{RESET} {best['type']} ({best['success_rate'] * 100:.0f}% success)"
                )

            # Confidence calibration insight
            calibration = im.get("confidence_calibration", {})
            high_conf = calibration.get("high (0.8-1.0)", 0)
            low_conf = calibration.get("low (0.0-0.5)", 0)
            if high_conf > 0 and low_conf > 0:
                if high_conf > low_conf + 0.2:
                    lines.append("  💡 High-confidence recommendations performing well")
                elif low_conf > high_conf:
                    lines.append(f"  {YELLOW}💡 Confidence calibration needs adjustment{RESET}")

            lines.append("")

    # Cross-Project Insights
    if briefing.cross_project_insights:
        cpi = briefing.cross_project_insights
        shared_patterns = cpi.get("shared_patterns", [])
        relevant_lessons = cpi.get("relevant_lessons", [])
        health = cpi.get("portfolio_health")

        if shared_patterns or relevant_lessons or health:
            lines.append(f"{BOLD}🔗 CROSS-PROJECT INTELLIGENCE{RESET}")

            # Portfolio health
            if health:
                healthy = health.get("healthy_count", 0)
                at_risk = health.get("at_risk_count", 0)
                critical = health.get("critical_count", 0)
                if at_risk > 0 or critical > 0:
                    lines.append(
                        f"  Portfolio Health: {GREEN}{healthy} healthy{RESET}, {YELLOW}{at_risk} at risk{RESET}, {RED}{critical} critical{RESET}"
                    )
                else:
                    lines.append(
                        f"  Portfolio Health: {GREEN}All {healthy} projects healthy{RESET}"
                    )

            # Shared patterns
            if shared_patterns:
                lines.append("  Shared patterns in active projects:")
                for pattern in shared_patterns[:2]:
                    projects = ", ".join(pattern.get("shared_by", [])[:3])
                    lines.append(f"    - {pattern['pattern']} ({projects})")

            # Relevant lessons
            if relevant_lessons:
                lines.append(f"  {YELLOW}Relevant lessons:{RESET}")
                for lesson in relevant_lessons[:2]:
                    lesson_text = lesson.get("lesson", "")[:60]
                    lines.append(f"    - [{lesson.get('project', 'General')}] {lesson_text}")

            lines.append("")

    # Patterns Noticed
    lines.append(f"{BOLD}PATTERNS NOTICED{RESET}")
    if briefing.patterns:
        for pattern in briefing.patterns:
            lines.append(f"  {pattern}")
    else:
        lines.append("  No significant patterns detected")

    lines.append("=" * 64)

    return "\n".join(lines)


def format_briefing_json(briefing: BriefingData) -> str:
    """
    Format briefing as JSON.

    Args:
        briefing: BriefingData to format

    Returns:
        JSON string
    """
    import json

    data = {
        "generated_at": briefing.generated_at.isoformat(),
        "period": briefing.period,
        "portfolio_pulse": {
            "active_projects": briefing.active_projects,
            "recent_commits_24h": briefing.recent_commits_24h,
            "total_commits_7d": briefing.total_commits_7d,
            "blockers": briefing.blockers,
        },
        "priority_actions": briefing.priority_actions,
        "patterns_noticed": briefing.patterns,
        "waiting_on": briefing.waiting_on,
        # Enhanced intelligence fields
        "intelligence_metrics": briefing.intelligence_metrics,
        "strategic_alignment": briefing.strategic_alignment,
        "temporal_context": briefing.temporal_context,
        "cross_project_insights": briefing.cross_project_insights,
        "predictive_insights": briefing.predictive_insights,
    }

    return json.dumps(data, indent=2, default=str)


def get_executive_summary(briefing: BriefingData) -> str:
    """
    Generate a concise, high-impact executive summary (Operator Persona).

    Enhanced format with intelligence: greeting, status, priority, prediction, day context.
    """
    parts = []

    # Greeting based on time with day context
    hour = datetime.now().hour
    greeting = "Morning" if 5 <= hour < 12 else "Afternoon" if 12 <= hour < 17 else "Evening"
    day_suffix = ""
    if briefing.temporal_context:
        day = briefing.temporal_context.get("day_of_week", "")
        if day:
            day_suffix = f" ({day})"
    parts.append(f"{greeting}, Jesse{day_suffix}.")

    # Pulse with velocity
    active_count = len(briefing.active_projects)
    velocity_suffix = ""
    if briefing.strategic_alignment:
        velocity = briefing.strategic_alignment.get("velocity_status", "")
        if velocity == "healthy":
            velocity_suffix = " ✓"
        elif velocity == "blocked":
            velocity_suffix = " ⚠"
    parts.append(f"{active_count} Active Projects{velocity_suffix}.")

    # Blockers or strategic drift warning
    blocker_count = len(briefing.blockers)
    has_drift = briefing.strategic_alignment and briefing.strategic_alignment.get(
        "has_strategic_drift"
    )
    if blocker_count > 0:
        parts.append(f"{blocker_count} Blockers.")
    elif has_drift:
        parts.append("Strategic Drift Detected.")
    else:
        parts.append("Systems Nominal.")

    # Top Priority with prediction context
    if briefing.priority_actions:
        top_action = briefing.priority_actions[0]
        parts.append(f"Priority: {top_action['title'][:40]}.")
    elif briefing.predictive_insights:
        predictions = briefing.predictive_insights.get("predictions", [])
        if predictions:
            parts.append(f"Suggested: {predictions[0]['prediction'][:40]}.")
    else:
        parts.append("No immediate actions.")

    # Day intelligence suggestion (if available and relevant)
    if briefing.temporal_context:
        day_pattern = briefing.temporal_context.get("day_pattern", {})
        energy = day_pattern.get("energy", "")
        if energy in ["fresh_start", "high"]:
            parts.append("High energy day.")
        elif energy == "winding_down":
            parts.append("Wrap-up day.")

    # Recommendation accuracy insight (if sufficient data)
    if briefing.intelligence_metrics:
        im = briefing.intelligence_metrics
        if im.get("has_sufficient_data"):
            accuracy = im.get("recommendation_accuracy", 0) * 100
            if accuracy >= 70:
                parts.append(f"Cortex: {accuracy:.0f}% accurate.")

    return " ".join(parts)


if __name__ == "__main__":
    # Test the briefing generator
    briefing = generate_daily_briefing()
    print(format_briefing(briefing))
    print("\n--- EXECUTIVE SUMMARY ---\n")
    print(get_executive_summary(briefing))
