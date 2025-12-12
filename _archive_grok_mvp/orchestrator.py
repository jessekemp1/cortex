#!/usr/bin/env python3
"""
Converx Orchestrator - Combines existing tools into strategist interface

Orchestrates:
- ai_intelligence.py (project activity)
- goal_parser.py (goals)
- recommendation_engine.py (recommendations)
- context_intelligence.py (context)
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path to import existing tools
# Path(__file__) is in converx/Grok MVP/, so parent.parent is /Users/jesse.kemp/Dev
script_dir = Path(__file__).parent
# Go up two levels: converx/Grok MVP -> converx -> Dev
dev_root = script_dir.parent.parent
sys.path.insert(0, str(dev_root))

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
    from context_intelligence import ContextIntelligence, ContextPrediction
except ImportError:
    ContextIntelligence = None
    ContextPrediction = None


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
class StrategistResponse:
    """Formatted strategist response."""

    current_state: Dict[str, Any]
    next_action: Optional[Recommendation]
    alternative_actions: List[Recommendation]
    context_predictions: List[ContextPrediction]
    system_health: SystemHealth


class ConverxOrchestrator:
    """Orchestrates existing tools to provide strategist interface."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir

        # Initialize tools (gracefully handle missing tools)
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = (
            RecommendationEngine() if RecommendationEngine else None
        )
        self.context_intel = (
            ContextIntelligence(root_dir) if ContextIntelligence else None
        )

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
                goals = self.goal_parser.parse()
            except Exception as e:
                print(f"Warning: Could not parse goals: {e}", file=sys.stderr)

        # 2. Get project activity (git repos + projects from goals)
        project_activity = []

        # 2a. Get git repos
        git_projects = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                git_projects = [
                    self.project_scanner.analyze_project(repo) for repo in repos
                ]
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
                recommendations = self.recommendation_engine.generate_recommendations(
                    project_activity=project_activity if project_activity else None,
                    limit=limit + 1,  # +1 for next action
                )
            except Exception as e:
                print(
                    f"Warning: Could not generate recommendations: {e}", file=sys.stderr
                )

        # 4. Filter by project if specified
        if project_filter and recommendations:
            project_lower = project_filter.lower()
            recommendations = [
                r
                for r in recommendations
                if any(project_lower in proj.lower() for proj in r.related_projects)
            ]

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

        # 6. Build current state summary
        current_state = self._build_current_state(project_activity, goals)

        # 7. Extract next action and alternatives
        next_action = recommendations[0] if recommendations else None
        alternative_actions = (
            recommendations[1 : limit + 1] if len(recommendations) > 1 else []
        )

        # 8. Build system health status (Golden Spec: Dependency Transparency)
        system_health = SystemHealth(
            project_scanner=self.project_scanner is not None,
            goal_parser=self.goal_parser is not None,
            recommendation_engine=self.recommendation_engine is not None,
            context_intelligence=self.context_intel is not None,
        )

        return StrategistResponse(
            current_state=current_state,
            next_action=next_action,
            alternative_actions=alternative_actions,
            context_predictions=context_predictions,
            system_health=system_health,
        )

    def _build_current_state(
        self, project_activity: List[ProjectActivity], goals: List[Goal]
    ) -> Dict[str, Any]:
        """Build current state summary."""
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
        }

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
        if (project_path / ".env.example").exists() and not (
            project_path / ".env"
        ).exists():
            blockers.append("Missing .env file")

        # Check for requirements.txt without venv
        if (project_path / "requirements.txt").exists():
            if (
                not (project_path / "venv").exists()
                and not (project_path / "env").exists()
            ):
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
