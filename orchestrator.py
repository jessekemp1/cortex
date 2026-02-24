import os
#!/usr/bin/env python3
"""
Cortex Orchestrator - Combines existing tools into strategist interface

Orchestrates:
- ai_intelligence.py (project activity)
- goal_parser.py (goals)
- recommendation_engine.py (recommendations)
- context_intelligence.py (context)
"""

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Priority(str, Enum):
    """Priority levels for recommendations"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Add parent directory to path to import existing tools
# Path(__file__) is in cortex/, so parent is ~/projects
script_dir = Path(__file__).parent
# Go up one level: cortex -> Dev
dev_root = script_dir.parent

# Prioritize cortex directory first (has latest versions), then scripts
sys.path.insert(0, str(script_dir))  # cortex/ directory (this directory)
sys.path.insert(1, str(dev_root))  # Dev/ directory
scripts_dir = dev_root / "scripts"
sys.path.insert(2, str(scripts_dir))  # scripts/ directory (legacy)

try:
    from ai_intelligence import ProjectActivity, ProjectScanner
except ImportError:
    try:
        from scripts.ai_intelligence import ProjectActivity, ProjectScanner
    except ImportError:
        ProjectScanner = None
        ProjectActivity = None

try:
    from goal_parser import Goal, GoalParser
except ImportError:
    try:
        from scripts.goal_parser import Goal, GoalParser
    except ImportError:
        GoalParser = None
        Goal = None

# Import recommendation engine from cortex (Layer 4)
# Legacy scripts/recommendation_engine.py no longer exists
try:
    from recommendation_engine import Recommendation, RecommendationEngine
except ImportError:
    RecommendationEngine = None
    Recommendation = None

try:
    from context_intelligence import ContextIntelligence, ContextPrediction
except ImportError:
    try:
        from scripts.context_intelligence import ContextIntelligence, ContextPrediction
    except ImportError:
        ContextIntelligence = None
        ContextPrediction = None

# Task discovery integration
try:
    from task_discovery import get_all_tasks, get_tasks_for_project

    TASK_DISCOVERY_AVAILABLE = True
except ImportError:
    get_tasks_for_project = None
    get_all_tasks = None
    TASK_DISCOVERY_AVAILABLE = False

# Optional local-orchestrator integration
try:
    from integration.local_orchestrator import CortexLocalOrchestratorIntegration

    LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE = True
except ImportError:
    CortexLocalOrchestratorIntegration = None
    LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE = False

# Enhanced integration: Learning and feedback
try:
    from integration.feedback_loop import FeedbackLoop
    from integration.history_analyzer import ExecutionHistoryAnalyzer

    LEARNING_AVAILABLE = True
except ImportError:
    FeedbackLoop = None
    ExecutionHistoryAnalyzer = None
    LEARNING_AVAILABLE = False

# Cortex learning system
try:
    from learning import LearningSystem

    CORTEX_LEARNING_AVAILABLE = True
except ImportError:
    LearningSystem = None
    CORTEX_LEARNING_AVAILABLE = False


@dataclass
class SystemHealth:
    """System health status for Golden Spec verification."""

    project_scanner: bool
    goal_parser: bool
    recommendation_engine: bool
    context_intelligence: bool

    @property
    def all_active(self) -> bool:
        """Check if all integrations are active."""
        return all(
            [
                self.project_scanner,
                self.goal_parser,
                self.recommendation_engine,
                self.context_intelligence,
            ]
        )

    @property
    def active_count(self) -> int:
        """Count of active integrations."""
        return sum(
            [
                self.project_scanner,
                self.goal_parser,
                self.recommendation_engine,
                self.context_intelligence,
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_scanner": self.project_scanner,
            "goal_parser": self.goal_parser,
            "recommendation_engine": self.recommendation_engine,
            "context_intelligence": self.context_intelligence,
            "all_active": self.all_active,
            "active_count": self.active_count,
            "total_integrations": 4,
        }


@dataclass
class CommandWorkflow:
    """Suggested command workflow based on learned patterns."""

    suggested_command: Optional[str] = None
    full_workflow: Optional[str] = None
    rationale: str = ""
    confidence: float = 0.0


@dataclass
class StrategistResponse:
    """Formatted strategist response."""

    current_state: Dict[str, Any]
    next_action: Optional[Recommendation]
    alternative_actions: List[Recommendation]
    context_predictions: List[ContextPrediction]
    system_health: SystemHealth
    command_workflow: Optional[CommandWorkflow] = None


class CortexOrchestrator:
    """Orchestrates existing tools to provide strategist interface."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))
        self.root_dir = root_dir

        # Initialize tools (gracefully handle missing tools)
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = RecommendationEngine() if RecommendationEngine else None
        self.context_intel = ContextIntelligence(root_dir) if ContextIntelligence else None

        # Optional local-orchestrator integration
        if LOCAL_ORCHESTRATOR_INTEGRATION_AVAILABLE and CortexLocalOrchestratorIntegration:
            self.local_orchestrator_integration = CortexLocalOrchestratorIntegration(root_dir)
        else:
            self.local_orchestrator_integration = None

        # Learning and feedback loop
        if LEARNING_AVAILABLE and FeedbackLoop:
            self.feedback_loop = FeedbackLoop(root_dir)
        else:
            self.feedback_loop = None

        if LEARNING_AVAILABLE and ExecutionHistoryAnalyzer:
            self.history_analyzer = ExecutionHistoryAnalyzer(root_dir)
        else:
            self.history_analyzer = None

        # Cortex learning system
        if CORTEX_LEARNING_AVAILABLE and LearningSystem:
            self.learning_system = LearningSystem()
        else:
            self.learning_system = None

    def get_next_action(
        self,
        project_filter: Optional[str] = None,
        include_context: bool = False,
        limit: int = 3,
    ) -> StrategistResponse:
        """
        Get next action with current state summary.

        Args:
            project_filter: Filter recommendations by project name
            include_context: Include context predictions
            limit: Number of alternative actions to return

        Returns:
            StrategistResponse with next action and state
        """
        # 1. Get goals first (needed for project detection)
        goals = []
        if self.goal_parser:
            try:
                goals = self.goal_parser.parse_all_goals()
            except Exception as e:
                print(f"Warning: Could not parse goals: {e}", file=sys.stderr)

        # 2. Get project activity (git repos + projects from goals)
        project_activity = []

        # 2a. Get git repos
        git_projects = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                git_projects = [self.project_scanner.analyze_project(repo) for repo in repos]
            except Exception as e:
                print(f"Warning: Could not scan git projects: {e}", file=sys.stderr)

        # 2b. Detect projects from goals (even if not git repos)
        goal_projects = self._detect_projects_from_goals(goals, git_projects)

        # 2c. Merge: git projects + goal projects (deduplicate by name)
        project_activity = self._merge_projects(git_projects, goal_projects)

        # 3. Get recommendations
        recommendations = []
        if self.recommendation_engine:
            try:
                # Build context from project activity
                context = (
                    {
                        "project_activity": project_activity,
                        "goals": (
                            [g.to_dict() if hasattr(g, "to_dict") else g for g in goals]
                            if goals
                            else []
                        ),
                    }
                    if project_activity
                    else None
                )

                recommendations = self.recommendation_engine.generate_recommendations(
                    context=context,
                    limit=limit + 1,  # +1 for next action
                )

                # Apply learning adjustments if available
                if self.learning_system and recommendations:
                    adjusted_recommendations = []
                    for rec in recommendations:
                        # Adjust confidence based on historical outcomes
                        adjusted_confidence, explanation = (
                            self.learning_system.adjust_confidence_based_on_history(
                                recommendation_type=rec.type,
                                base_confidence=rec.confidence,
                            )
                        )

                        # Update recommendation with adjusted confidence
                        rec.confidence = adjusted_confidence

                        # Enhance rationale with learning insight (if rationale exists)
                        rationale = getattr(rec, "rationale", None) or getattr(
                            rec, "description", ""
                        )
                        if rationale and "previous outcomes" not in rationale.lower():
                            if hasattr(rec, "rationale") and rec.rationale is not None:
                                rec.rationale = f"{rec.rationale} ({explanation})"
                            elif hasattr(rec, "description"):
                                rec.description = f"{rec.description} ({explanation})"

                        adjusted_recommendations.append(rec)
                    recommendations = adjusted_recommendations

            except Exception as e:
                print(f"Warning: Could not generate recommendations: {e}", file=sys.stderr)

        # 4. Filter by project if specified
        if project_filter and recommendations:
            project_lower = project_filter.lower()
            filtered = []
            for r in recommendations:
                related = getattr(r, "related_projects", None) or []
                if any(project_lower in proj.lower() for proj in related):
                    filtered.append(r)
            recommendations = (
                filtered if filtered else recommendations[:1]
            )  # Fallback to first if none match

        # 5. Get context predictions if requested
        context_predictions = []
        if include_context and self.context_intel:
            try:
                current_project = project_filter if project_filter else None
                context_predictions = self.context_intel.predict_context(
                    current_project=current_project
                )
            except Exception as e:
                print(f"Warning: Could not predict context: {e}", file=sys.stderr)

        # 6. Get tasks from tasks.yaml files if available
        discovered_tasks = []
        if TASK_DISCOVERY_AVAILABLE and get_all_tasks:
            try:
                all_tasks = get_all_tasks()
                # Filter by project if specified
                if project_filter:
                    discovered_tasks = [
                        t
                        for t in all_tasks
                        if t.get("project", "").lower() == project_filter.lower()
                    ]
                else:
                    discovered_tasks = all_tasks[:limit]  # Limit to avoid overwhelming
            except Exception as e:
                print(f"Warning: Could not discover tasks: {e}", file=sys.stderr)

        # 7. Build current state summary
        current_state = self._build_current_state(project_activity, goals, discovered_tasks)

        # 8. Extract next action and alternatives
        next_action = recommendations[0] if recommendations else None
        alternative_actions = recommendations[1 : limit + 1] if len(recommendations) > 1 else []

        # 9. Build system health status (Golden Spec: Dependency Transparency)
        system_health = SystemHealth(
            project_scanner=self.project_scanner is not None,
            goal_parser=self.goal_parser is not None,
            recommendation_engine=self.recommendation_engine is not None,
            context_intelligence=self.context_intel is not None,
        )

        # 10. Get command workflow suggestion based on learned patterns
        command_workflow = self._get_command_workflow_suggestion(
            project_filter=project_filter,
            task_type=next_action.type if next_action else None,
        )

        return StrategistResponse(
            current_state=current_state,
            next_action=next_action,
            alternative_actions=alternative_actions,
            context_predictions=context_predictions,
            system_health=system_health,
            command_workflow=command_workflow,
        )

    def _get_command_workflow_suggestion(
        self,
        project_filter: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> Optional[CommandWorkflow]:
        """
        Get command workflow suggestion from learned patterns.

        Uses the CommandTracker to suggest which slash commands to use
        based on historical success patterns.
        """
        try:
            from engines.command_tracker import get_tracker

            tracker = get_tracker()
            suggestion = tracker.suggest_for_context(
                project=project_filter,
                task_type=task_type,
            )

            if suggestion:
                return CommandWorkflow(
                    suggested_command=suggestion.get("suggested_command"),
                    full_workflow=suggestion.get("full_workflow"),
                    rationale=suggestion.get("rationale", ""),
                    confidence=suggestion.get("confidence", 0.0),
                )
        except Exception:
            pass  # Graceful degradation

        return None

    def _build_current_state(
        self,
        project_activity: List[ProjectActivity],
        goals: List[Goal],
        discovered_tasks: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build current state summary."""
        if discovered_tasks is None:
            discovered_tasks = []

        state = {
            "active_projects": 0,
            "recent_projects": 0,
            "dormant_projects": 0,
            "total_projects": len(project_activity) if project_activity else 0,
            "priority_a_goals": 0,
            "priority_b_goals": 0,
            "priority_c_goals": 0,
            "goals_pending": 0,
            "goals_in_progress": 0,
            "blockers": [],
            "discovered_tasks": len(discovered_tasks),
            "tasks_by_project": {},
        }

        # Group tasks by project
        for task in discovered_tasks:
            project = task.get("project", "unknown")
            if project not in state["tasks_by_project"]:
                state["tasks_by_project"][project] = []
            state["tasks_by_project"][project].append(
                {
                    "id": task.get("id"),
                    "name": task.get("name"),
                    "type": task.get("type"),
                    "schedule": task.get("schedule"),
                }
            )

        if project_activity:
            for project in project_activity:
                if project.status == "active":
                    state["active_projects"] += 1
                elif project.status == "recent":
                    state["recent_projects"] += 1
                elif project.status == "dormant":
                    state["dormant_projects"] += 1

                if project.blockers:
                    state["blockers"].extend(
                        [
                            {"project": project.name, "blocker": blocker}
                            for blocker in project.blockers
                        ]
                    )

        if goals:
            for goal in goals:
                if goal.priority == "A":
                    state["priority_a_goals"] += 1
                elif goal.priority == "B":
                    state["priority_b_goals"] += 1
                elif goal.priority == "C":
                    state["priority_c_goals"] += 1

                if goal.status == "pending":
                    state["goals_pending"] += 1
                elif goal.status == "in_progress":
                    state["goals_in_progress"] += 1

        return state

    def _detect_projects_from_goals(
        self, goals: List[Goal], existing_projects: List[ProjectActivity]
    ) -> List[ProjectActivity]:
        """
        Detect projects from goal project names.
        Creates ProjectActivity objects for projects that exist as directories
        but may not be git repos.
        """
        if not ProjectActivity or not goals:
            return []

        goal_projects = []
        existing_names = {p.name.lower() for p in existing_projects}

        for goal in goals:
            if not goal.project:
                continue

            # Skip if already detected as git repo
            if goal.project.lower() in existing_names:
                continue

            # Check if project directory exists
            project_path = self.root_dir / goal.project
            if not project_path.exists() or not project_path.is_dir():
                continue

            # Check if it looks like a project (has some project files)
            has_project_files = any(
                [
                    (project_path / "requirements.txt").exists(),
                    (project_path / "package.json").exists(),
                    (project_path / "README.md").exists(),
                    (project_path / "pyproject.toml").exists(),
                    (project_path / "setup.py").exists(),
                    (project_path / "src").exists(),
                    (project_path / "app").exists(),
                ]
            )

            if not has_project_files:
                continue

            # Create minimal ProjectActivity
            project = ProjectActivity(
                name=goal.project,
                path=project_path,
                status="active" if goal.status == "in_progress" else "recent",
                commits_7d=0,
                commits_30d=0,
                files_changed_7d=0,
                uncommitted_changes=0,
                blockers=[],
                current_branch="",
                last_commit_date=None,
                last_commit_msg="",
            )

            # Try to detect blockers for non-git projects
            project.blockers = self._detect_blockers_for_directory(project_path)

            goal_projects.append(project)

        return goal_projects

    def _detect_blockers_for_directory(self, project_path: Path) -> List[str]:
        """Detect potential blockers for a directory (non-git project)."""
        blockers = []

        # Check for .env.example without .env
        if (project_path / ".env.example").exists() and not (project_path / ".env").exists():
            blockers.append("Missing .env file")

        # Check for requirements.txt without venv
        if (project_path / "requirements.txt").exists():
            # Check standard venv names
            has_venv = any((project_path / d).exists() for d in ["venv", ".venv", "env", ".env"])
            if not has_venv:
                blockers.append("No virtualenv detected")

        return blockers

    def _merge_projects(
        self, git_projects: List[ProjectActivity], goal_projects: List[ProjectActivity]
    ) -> List[ProjectActivity]:
        """
        Merge git projects and goal projects, deduplicating by name.
        Prioritizes git projects (more accurate activity data).
        """
        merged = []
        seen_names = set()

        # Add git projects first (higher priority)
        for project in git_projects:
            merged.append(project)
            seen_names.add(project.name.lower())

        # Add goal projects that aren't already in git projects
        for project in goal_projects:
            if project.name.lower() not in seen_names:
                merged.append(project)
                seen_names.add(project.name.lower())

        return merged
