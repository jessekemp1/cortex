"""
Cortex Recommendations Engine

Generates intelligent, actionable recommendations based on:
- Project health scores and trends
- Dependency analysis
- GOALS.md priorities
- Portfolio patterns and lessons

Provides:
- Priority project recommendations
- Risk alerts
- Next action suggestions
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cortex.portfolio_memory import PortfolioMemory
except ImportError:  # Backward compatibility for legacy direct execution contexts.
    from portfolio_memory import PortfolioMemory


class RecommendationEngine:
    """Generate smart recommendations based on portfolio health and goals."""

    def __init__(self, dev_path: Path = None):
        self.dev_path = dev_path or Path("/Users/jesse.kemp/Dev")
        self.portfolio = PortfolioMemory()
        self._goals_cache = None
        self._goals_cache_time = None

    def _parse_goals(self) -> Dict[str, Any]:
        """Parse GOALS.md into structured data."""
        # Use cache if fresh (< 5 minutes)
        if self._goals_cache and self._goals_cache_time:
            age = (datetime.now() - self._goals_cache_time).seconds
            if age < 300:
                return self._goals_cache

        goals_path = self.dev_path / "GOALS.md"
        if not goals_path.exists():
            return {"high": [], "medium": [], "low": [], "completed": []}

        content = goals_path.read_text()
        goals = {"high": [], "medium": [], "low": [], "completed": []}

        current_priority = None
        for line in content.split("\n"):
            line = line.strip()

            # Detect section headers
            if "## High Priority" in line:
                current_priority = "high"
            elif "## Medium Priority" in line:
                current_priority = "medium"
            elif "## Low Priority" in line:
                current_priority = "low"
            elif "## Completed" in line:
                current_priority = "completed"
            elif "## Archive" in line or "## Notes" in line:
                current_priority = None

            # Parse goal items
            if current_priority and line.startswith("- ["):
                completed = line.startswith("- [x]")
                # Extract goal text
                match = re.match(r"- \[.\] (.+)", line)
                if match:
                    goal_text = match.group(1)
                    # Extract project name if present
                    project_match = re.match(r"(\w+):", goal_text)
                    project = project_match.group(1) if project_match else None

                    goal = {
                        "text": goal_text,
                        "completed": completed,
                        "project": project,
                        "priority": current_priority,
                    }

                    if completed:
                        goals["completed"].append(goal)
                    else:
                        goals[current_priority].append(goal)

        self._goals_cache = goals
        self._goals_cache_time = datetime.now()
        return goals

    def _get_dependency_health(self, project: str) -> Optional[Dict[str, Any]]:
        """Get dependency health for a project."""
        try:
            from agents.data_agent.analyzers.dependency_mapper import DependencyMapper

            mapper = DependencyMapper()
            # Map project name to path
            project_paths = {
                "cortex": self.dev_path / "cortex",
                "VortexV2": self.dev_path / "Vortex" / "VortexV2",
                "alpha_arena": self.dev_path / "alpha_arena",
                "DJ-CoPilot": self.dev_path / "DJ-CoPilot",
            }

            path = project_paths.get(project)
            if not path or not path.exists():
                return None

            health = mapper.get_health_score(path)
            return health
        except Exception:
            return None

    def get_priority_projects(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects that need attention, prioritized by:
        1. Uncompleted high-priority goals
        2. Low health scores
        3. Stale activity

        Returns:
            List of priority projects with reasons
        """
        priorities = []
        goals = self._parse_goals()

        # Get portfolio health
        health_summary = self.portfolio.get_portfolio_health_summary(days=7)
        project_health = health_summary.get("projects", {})

        # Process high-priority goals first
        for goal in goals["high"]:
            if goal["completed"]:
                continue

            project = goal.get("project")
            health = project_health.get(project, {}) if project else {}

            priorities.append(
                {
                    "project": project or "General",
                    "priority": "HIGH",
                    "reason": f"Uncompleted goal: {goal['text'][:60]}...",
                    "health_score": health.get("score"),
                    "source": "goals",
                }
            )

        # Add at-risk projects from health analysis
        at_risk = health_summary.get("aggregate", {}).get("at_risk_projects", [])
        for project in at_risk:
            # Skip if already in list
            if any(p["project"] == project for p in priorities):
                continue

            health = project_health.get(project, {})
            priorities.append(
                {
                    "project": project,
                    "priority": "MEDIUM",
                    "reason": f"Health declining: {health.get('assessment', 'unknown')}",
                    "health_score": health.get("score"),
                    "source": "health",
                }
            )

        # Sort by priority and health
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        priorities.sort(
            key=lambda x: (
                priority_order.get(x["priority"], 2),
                -(x.get("health_score") or 100),
            )
        )

        return priorities[:limit]

    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """
        Get risk alerts across the portfolio.

        Checks:
        - Low health scores (< 50)
        - Circular dependencies
        - Stale projects (no commits in 7+ days)
        - High external dependency count

        Returns:
            List of risk alerts with severity
        """
        alerts = []

        # Check health
        health_summary = self.portfolio.get_portfolio_health_summary(days=7)
        overall = health_summary.get("overall", {})

        if overall.get("score", 100) < 50:
            alerts.append(
                {
                    "severity": "HIGH",
                    "type": "health",
                    "message": f"Portfolio health is critical: {overall.get('score')}/100",
                    "recommendation": "Review recent commits and address test failures",
                }
            )

        # Check for stale commits
        if overall.get("commits", 0) == 0:
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "type": "activity",
                    "message": "No commits in analysis period",
                    "recommendation": "Resume development activity",
                }
            )

        # Check uncommitted files
        uncommitted = overall.get("uncommitted", 0)
        if uncommitted > 20:
            alerts.append(
                {
                    "severity": "LOW",
                    "type": "uncommitted",
                    "message": f"{uncommitted} uncommitted files",
                    "recommendation": "Commit or stash pending changes",
                }
            )

        # Check dependency health for key projects
        for project in ["cortex", "VortexV2"]:
            dep_health = self._get_dependency_health(project)
            if dep_health and dep_health.get("total_score", 100) < 60:
                concerns = dep_health.get("concerns", [])
                alerts.append(
                    {
                        "severity": "MEDIUM",
                        "type": "dependencies",
                        "project": project,
                        "message": f"{project} dependency health: {dep_health.get('total_score')}/100",
                        "concerns": concerns[:2],
                        "recommendation": "Review and consolidate dependencies",
                    }
                )

        # Sort by severity
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 2))

        return alerts

    def _get_session_activity(self, hours: int = 24) -> Dict[str, Any]:
        """Read recent session summaries to understand activity patterns."""
        session_file = Path.home() / ".cortex" / "session_summaries.jsonl"
        if not session_file.exists():
            return {"sessions": 0, "total_insights": 0, "total_patterns": 0}

        cutoff = datetime.now() - __import__("datetime").timedelta(hours=hours)
        sessions = 0
        total_insights = 0
        total_patterns = 0
        projects_touched = set()

        try:
            for line in session_file.read_text().splitlines()[-100:]:  # Last 100 entries
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("timestamp", ""))
                    if ts > cutoff:
                        sessions += 1
                        total_insights += entry.get("insights_captured", 0)
                        total_patterns += entry.get("patterns_extracted", 0)
                        cwd = entry.get("cwd", "")
                        if cwd:
                            projects_touched.add(Path(cwd).name)
                except (json.JSONDecodeError, ValueError):
                    continue
        except Exception:
            pass

        return {
            "sessions": sessions,
            "total_insights": total_insights,
            "total_patterns": total_patterns,
            "projects_touched": list(projects_touched),
        }

    def get_recommended_next_action(self) -> Dict[str, Any]:
        """
        Get single most important next action.

        Considers:
        - Highest priority uncompleted goal
        - Critical risk alerts
        - Health-based recommendations
        - Recent session activity patterns

        Returns:
            Recommended action with context
        """
        # Check for critical alerts first
        alerts = self.get_risk_alerts()
        critical_alerts = [a for a in alerts if a["severity"] == "HIGH"]

        if critical_alerts:
            alert = critical_alerts[0]
            return {
                "action": alert["recommendation"],
                "reason": alert["message"],
                "priority": "CRITICAL",
                "type": "alert",
            }

        # Get priority projects
        priorities = self.get_priority_projects(limit=1)

        if priorities:
            top = priorities[0]
            return {
                "action": top["reason"],
                "project": top["project"],
                "priority": top["priority"],
                "type": "goal",
                "health_score": top.get("health_score"),
            }

        # Check session activity for staleness patterns
        activity = self._get_session_activity(hours=24)
        if activity["sessions"] > 5 and activity["total_insights"] == 0:
            return {
                "action": "High session count but no insights extracted — review learning pipeline",
                "priority": "MEDIUM",
                "type": "activity_pattern",
                "sessions_24h": activity["sessions"],
            }

        # Default - everything is good!
        return {
            "action": "All goals on track - consider adding new objectives",
            "priority": "LOW",
            "type": "maintenance",
        }

    def get_full_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive recommendations report.

        Returns:
            Full report with priorities, alerts, and suggestions
        """
        return {
            "generated_at": datetime.now().isoformat(),
            "next_action": self.get_recommended_next_action(),
            "priority_projects": self.get_priority_projects(limit=5),
            "risk_alerts": self.get_risk_alerts(),
            "goals_summary": {
                "high_pending": len(self._parse_goals()["high"]),
                "medium_pending": len(self._parse_goals()["medium"]),
                "completed": len(self._parse_goals()["completed"]),
            },
            "session_activity_24h": self._get_session_activity(hours=24),
        }


# CLI interface
if __name__ == "__main__":
    import sys

    engine = RecommendationEngine()

    if len(sys.argv) < 2:
        print("Usage: python recommendations.py <command>")
        print("Commands: next, priorities, alerts, report")
        sys.exit(1)

    command = sys.argv[1]

    if command == "next":
        action = engine.get_recommended_next_action()
        print("\n🎯 Recommended Next Action")
        print(f"   Priority: {action['priority']}")
        print(f"   Action: {action['action']}")
        if action.get("project"):
            print(f"   Project: {action['project']}")

    elif command == "priorities":
        priorities = engine.get_priority_projects()
        print(f"\n📋 Priority Projects ({len(priorities)})")
        for i, p in enumerate(priorities, 1):
            health = f" [{p['health_score']}/100]" if p.get("health_score") else ""
            print(f"   {i}. [{p['priority']}] {p['project']}{health}")
            print(f"      {p['reason']}")

    elif command == "alerts":
        alerts = engine.get_risk_alerts()
        if not alerts:
            print("\n✅ No risk alerts")
        else:
            print(f"\n⚠️  Risk Alerts ({len(alerts)})")
            for alert in alerts:
                icon = (
                    "🔴"
                    if alert["severity"] == "HIGH"
                    else "🟡" if alert["severity"] == "MEDIUM" else "🟢"
                )
                print(f"   {icon} [{alert['severity']}] {alert['message']}")
                print(f"      → {alert['recommendation']}")

    elif command == "report":
        report = engine.get_full_report()
        print(json.dumps(report, indent=2, default=str))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
