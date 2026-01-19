"""
Health Tracker - Historical project health tracking and aggregation

Tracks project health scores over time to identify trends and patterns.
Fresh calculation every time (depth-first principle: fresh > fast).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .git_analyzer import GitAnalyzer


class HealthTracker:
    """Track and aggregate project health metrics over time"""

    def __init__(self):
        """Initialize health tracker (no caching - always fresh)"""
        pass  # Simple initialization, no cache management

    def get_health_history(
        self, project_name: str, project_path: Path, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get health history for a project over multiple time periods

        Analyzes health at different intervals to show trends:
        - Last 7 days
        - Last 14 days
        - Last 30 days
        - Last 90 days (if days >= 90)

        Args:
            project_name: Name of project
            project_path: Path to project repository
            days: Maximum days to analyze

        Returns:
            Dict with health scores at different intervals
        """
        periods = [7, 14, 30]
        if days >= 90:
            periods.append(90)

        history = {
            "project": project_name,
            "path": str(project_path),
            "timestamp": datetime.now().isoformat(),
            "periods": {},
        }

        analyzer = GitAnalyzer(project_path)

        for period in periods:
            if period > days:
                continue

            # Get health for this period
            commits = analyzer.get_recent_commits(days=period)
            uncommitted = analyzer.get_uncommitted_changes()
            health = analyzer.calculate_health_score(commits, uncommitted)

            history["periods"][f"{period}d"] = {
                "days": period,
                "health_score": health["total_score"],
                "assessment": health["assessment"],
                "commits": commits["count"],
                "trend": commits["trend"],
                "uncommitted": uncommitted["total"],
            }

        # Calculate trend across periods
        history["overall_trend"] = self._calculate_multi_period_trend(history["periods"])

        return history

    def _calculate_multi_period_trend(self, periods: Dict[str, Dict]) -> str:
        """
        Calculate overall trend by comparing health scores across periods

        Args:
            periods: Dict of period data

        Returns:
            "improving", "declining", "stable", or "insufficient_data"
        """
        if len(periods) < 2:
            return "insufficient_data"

        # Sort periods by days (7d, 14d, 30d, etc.)
        sorted_periods = sorted(periods.items(), key=lambda x: x[1]["days"])

        # Get health scores
        scores = [p[1]["health_score"] for p in sorted_periods]

        # Compare recent vs older
        recent_avg = sum(scores[:2]) / 2 if len(scores) >= 2 else scores[0]
        older_avg = sum(scores[-2:]) / 2 if len(scores) >= 2 else scores[-1]

        # Determine trend
        if recent_avg > older_avg + 5:  # +5 threshold
            return "improving"
        elif recent_avg < older_avg - 5:  # -5 threshold
            return "declining"
        else:
            return "stable"


    def get_health_trends(self, project_name: str, project_path: Path) -> Dict[str, Any]:
        """
        Get comprehensive health trends with historical comparison

        Args:
            project_name: Name of project
            project_path: Path to project repository

        Returns:
            Dict with trends, insights, and recommendations
        """
        history = self.get_health_history(project_name, project_path, days=30)

        insights = []
        recommendations = []

        # Analyze trends
        periods = history["periods"]

        # Check for declining health
        if "7d" in periods and "30d" in periods:
            recent = periods["7d"]["health_score"]
            older = periods["30d"]["health_score"]

            if recent < older - 10:
                insights.append(
                    {
                        "type": "warning",
                        "message": f"Health declining: {older} → {recent} (down {older - recent} points in 30 days)",
                    }
                )
                recommendations.append(
                    {
                        "priority": "high",
                        "action": "Investigate cause of declining health",
                        "details": "Check recent commits, uncommitted work, and contributor activity",
                    }
                )

        # Check for low commit activity
        if "7d" in periods and periods["7d"]["commits"] < 3:
            insights.append(
                {
                    "type": "info",
                    "message": f"Low recent activity: {periods['7d']['commits']} commits in 7 days",
                }
            )

        # Check for high uncommitted changes
        if "7d" in periods and periods["7d"]["uncommitted"] > 20:
            insights.append(
                {
                    "type": "warning",
                    "message": f"High uncommitted changes: {periods['7d']['uncommitted']} files",
                }
            )
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Commit or clean up uncommitted work",
                    "details": "Large uncommitted work reduces project health score",
                }
            )

        # Check for positive trends
        if history["overall_trend"] == "improving":
            insights.append({"type": "success", "message": "Project health improving over time"})

        return {
            "project": project_name,
            "history": history,
            "insights": insights,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
        }


    def get_portfolio_trends(self, projects: Dict[str, Path]) -> Dict[str, Any]:
        """
        Get trends for entire portfolio

        Args:
            projects: Dict mapping project names to paths

        Returns:
            Portfolio-wide trend analysis
        """
        portfolio_trends = {
            "timestamp": datetime.now().isoformat(),
            "total_projects": len(projects),
            "projects": {},
            "summary": {"improving": [], "declining": [], "stable": [], "concerns": []},
        }

        for project_name, project_path in projects.items():
            try:
                trends = self.get_health_trends(project_name, project_path)
                portfolio_trends["projects"][project_name] = trends

                # Categorize by trend
                overall_trend = trends["history"]["overall_trend"]
                if overall_trend == "improving":
                    portfolio_trends["summary"]["improving"].append(project_name)
                elif overall_trend == "declining":
                    portfolio_trends["summary"]["declining"].append(project_name)
                else:
                    portfolio_trends["summary"]["stable"].append(project_name)

                # Track concerns
                if trends["recommendations"]:
                    portfolio_trends["summary"]["concerns"].append(
                        {
                            "project": project_name,
                            "recommendations": len(trends["recommendations"]),
                        }
                    )

            except Exception as e:
                portfolio_trends["projects"][project_name] = {"error": str(e)}

        return portfolio_trends


# CLI for testing
if __name__ == "__main__":
    import sys

    # Fix imports for standalone execution
    if __package__ is None:
        import sys
        from pathlib import Path as SysPath

        sys.path.insert(0, str(SysPath(__file__).parent.parent.parent))
        from agents.data_agent.analyzers.git_analyzer import GitAnalyzer as GA

        GitAnalyzer = GA

    if len(sys.argv) < 2:
        print("Usage: python health_tracker.py <command> [args]")
        print("\nCommands:")
        print("  history <project_path> [days]    - Get health history")
        print("  trends <project_path>             - Get comprehensive trends")
        sys.exit(1)

    command = sys.argv[1]
    tracker = HealthTracker()

    if command == "history":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)
        project_path = Path(sys.argv[2])
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        result = tracker.get_health_history("project", project_path, days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "trends":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)
        project_path = Path(sys.argv[2])
        result = tracker.get_health_trends("project", project_path)
        print(json.dumps(result, indent=2, default=str))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
