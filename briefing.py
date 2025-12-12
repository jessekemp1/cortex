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
    period: str = "24h"


class BriefingGenerator:
    """Generate daily briefings from cross-project data."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")
        self.root_dir = root_dir

        # Initialize tools
        self.project_scanner = ProjectScanner(str(root_dir)) if ProjectScanner else None
        self.goal_parser = GoalParser() if GoalParser else None
        self.recommendation_engine = (
            RecommendationEngine() if RecommendationEngine else None
        )

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
                    limit=5,
                )
            except Exception as e:
                print(
                    f"Warning: Could not generate recommendations: {e}", file=sys.stderr
                )

        # 4. Build briefing sections
        briefing = BriefingData(
            active_projects=self._get_active_projects(project_activity),
            recent_commits_24h=self._count_recent_commits(project_activity, hours=24),
            total_commits_7d=self._count_recent_commits(project_activity, days=7),
            blockers=self._get_blockers(project_activity, goals),
            priority_actions=self._get_priority_actions(recommendations, goals),
            patterns=self._detect_patterns(project_activity),
            waiting_on=self._get_waiting_on(goals, project_activity),
            generated_at=datetime.now(),
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
            key=lambda name: next(
                (p.commits_7d for p in projects if p.name == name), 0
            ),
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
        """Get top 3 priority actions from recommendations and goals."""
        actions = []

        # Add recommendations
        if recommendations:
            for rec in recommendations[:3]:
                actions.append(
                    {
                        "title": (
                            rec.action_title
                            if hasattr(rec, "action_title")
                            else rec.title
                        ),
                        "priority": rec.priority.upper(),
                        "project": (
                            rec.related_projects[0]
                            if rec.related_projects
                            else "General"
                        ),
                        "rationale": rec.rationale,
                        "source": "recommendation",
                    }
                )

        # Fill remaining with high-priority goals if needed
        if len(actions) < 3 and goals:
            priority_goals = [
                g
                for g in goals
                if g.priority == "A" and g.status in ["pending", "in_progress"]
            ]

            for goal in priority_goals[: 3 - len(actions)]:
                actions.append(
                    {
                        "title": goal.title,
                        "priority": "HIGH",
                        "project": goal.project or "General",
                        "rationale": goal.description[:100] if goal.description else "",
                        "source": "goal",
                    }
                )

        return actions[:3]

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
            p
            for p in projects
            if p.commits_7d > 0 and p.commits_30d <= p.commits_7d + 1
        ]
        if recently_awakened:
            patterns.append(f"Renewed focus on {recently_awakened[0].name}")

        # 4. Consistency patterns (commits every day vs burst)
        steady_projects = [
            p for p in active_projects if p.commits_7d >= 5 and p.commits_7d <= 10
        ]
        if steady_projects:
            patterns.append(
                f"Steady progress on {steady_projects[0].name} (daily commits)"
            )

        # 5. Burst activity
        burst_projects = [p for p in active_projects if p.commits_7d >= 15]
        if burst_projects:
            patterns.append(
                f"Sprint on {burst_projects[0].name} ({burst_projects[0].commits_7d} commits)"
            )

        return patterns[:3]  # Top 3 patterns

    def _get_waiting_on(
        self, goals: List[Goal], projects: List[ProjectActivity]
    ) -> List[str]:
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
    lines.append(
        f"{BOLD}DAILY BRIEFING - {briefing.generated_at.strftime('%B %d, %Y')}{RESET}"
    )
    lines.append("=" * 64)
    lines.append("")

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

    # Priority Actions
    lines.append(f"{BOLD}PRIORITY ACTIONS{RESET}")
    if briefing.priority_actions:
        for i, action in enumerate(briefing.priority_actions, 1):
            priority_color = (
                RED
                if action["priority"] == "HIGH"
                else YELLOW if action["priority"] == "MEDIUM" else GREEN
            )
            lines.append(
                f"  {i}. [{priority_color}{action['priority']}{RESET}] {action['title']}"
            )
            if action.get("project") and action["project"] != "General":
                lines.append(f"     Project: {action['project']}")
            if action.get("rationale"):
                # Truncate rationale to 80 chars
                rationale = (
                    action["rationale"][:80] + "..."
                    if len(action["rationale"]) > 80
                    else action["rationale"]
                )
                lines.append(f"     {rationale}")

        lines.append("")
        lines.append(f"{BOLD}💡 PROVIDE FEEDBACK{RESET}")
        lines.append("  After completing a recommendation, log the outcome:")
        lines.append(
            f"  {BLUE}cortex feedback --outcome <success|partial|failed>{RESET}"
        )
        lines.append("  This helps the learning system improve future recommendations.")
    else:
        lines.append("  No priority actions at this time")

    lines.append("")

    # Patterns Noticed
    lines.append(f"{BOLD}PATTERNS NOTICED{RESET}")
    if briefing.patterns:
        for pattern in briefing.patterns:
            lines.append(f"  {pattern}")
    else:
        lines.append("  No significant patterns detected")

    lines.append("")

    # Waiting On
    lines.append(f"{BOLD}WAITING ON YOU{RESET}")
    if briefing.waiting_on:
        for item in briefing.waiting_on:
            lines.append(f"  {item}")
    else:
        lines.append("  Nothing waiting on your input")

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
    }

    return json.dumps(data, indent=2)


if __name__ == "__main__":
    # Test the briefing generator
    briefing = generate_daily_briefing()
    print(format_briefing(briefing))
