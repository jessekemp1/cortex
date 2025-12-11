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
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# Add parent directory to path to import existing tools
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ai_intelligence import ProjectScanner, ProjectActivity
except ImportError:
    ProjectScanner = None
    ProjectActivity = None

try:
    from goal_parser import GoalParser, Goal
except ImportError:
    GoalParser = None
    Goal = None

try:
    from recommendation_engine import RecommendationEngine, Recommendation
except ImportError:
    RecommendationEngine = None
    Recommendation = None

try:
    from context_intelligence import ContextIntelligence, ContextPrediction
except ImportError:
    ContextIntelligence = None
    ContextPrediction = None


@dataclass
class StrategistResponse:
    """Formatted strategist response."""
    current_state: Dict[str, Any]
    next_action: Optional[Recommendation]
    alternative_actions: List[Recommendation]
    context_predictions: List[ContextPrediction]


class ConverxOrchestrator:
    """Orchestrates existing tools to provide strategist interface."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir

        # Initialize tools (gracefully handle missing tools)
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = RecommendationEngine() if RecommendationEngine else None
        self.context_intel = ContextIntelligence(root_dir) if ContextIntelligence else None

    def get_next_action(
        self,
        project_filter: Optional[str] = None,
        include_context: bool = False,
        limit: int = 3
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
        # 1. Get project activity
        project_activity = []
        if self.project_scanner:
            try:
                repos = self.project_scanner.find_git_repos()
                project_activity = [
                    self.project_scanner.analyze_project(repo) for repo in repos
                ]
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
                    limit=limit + 1  # +1 for next action
                )
            except Exception as e:
                print(f"Warning: Could not generate recommendations: {e}", file=sys.stderr)

        # 4. Filter by project if specified
        if project_filter and recommendations:
            project_lower = project_filter.lower()
            recommendations = [
                r for r in recommendations
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
        alternative_actions = recommendations[1:limit + 1] if len(recommendations) > 1 else []

        return StrategistResponse(
            current_state=current_state,
            next_action=next_action,
            alternative_actions=alternative_actions,
            context_predictions=context_predictions
        )

    def _build_current_state(
        self,
        project_activity: List[ProjectActivity],
        goals: List[Goal]
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
            "blockers": []
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
                    state["blockers"].extend([
                        {"project": project.name, "blocker": blocker}
                        for blocker in project.blockers
                    ])

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

