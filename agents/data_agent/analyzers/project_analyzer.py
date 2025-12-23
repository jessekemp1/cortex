"""
Project Analyzer - Multi-project health analysis

Analyzes multiple projects in a portfolio for health scoring,
comparison, and trend detection.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from .git_analyzer import GitAnalyzer
from .health_tracker import HealthTracker


class ProjectAnalyzer:
    """Analyze multiple projects for portfolio-wide insights"""

    def __init__(self, projects_root: Path = Path.home() / "Dev"):
        """
        Initialize analyzer with projects root

        Args:
            projects_root: Path to development root directory
        """
        self.projects_root = Path(projects_root)

        # Auto-discover projects (directories with .git)
        self.projects = self._discover_projects()

        # Initialize health tracker for caching
        self.health_tracker = HealthTracker()

    def _discover_projects(self) -> Dict[str, Path]:
        """
        Auto-discover git repositories in the workspace

        Returns:
            Dict mapping project name to path
        """
        projects = {}

        # Check if root is a git repo (monorepo case)
        if (self.projects_root / ".git").exists():
            projects["Dev"] = self.projects_root
            return projects

        # Look for git repos in subdirectories
        for item in self.projects_root.iterdir():
            if item.is_dir():
                git_dir = item / ".git"
                if git_dir.exists():
                    projects[item.name] = item

        return projects

    def analyze_project(
        self,
        project_name: str,
        days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a single project

        Args:
            project_name: Name of project to analyze
            days: Days to analyze

        Returns:
            Project analysis or None if project not found
        """
        if project_name not in self.projects:
            return None

        project_path = self.projects[project_name]

        try:
            analyzer = GitAnalyzer(project_path)
            return analyzer.get_project_summary(days)
        except Exception as e:
            return {
                "project": project_name,
                "error": str(e)
            }

    def analyze_all_projects(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze all discovered projects

        Args:
            days: Days to analyze

        Returns:
            Dict with all project analyses
        """
        results = {}

        for project_name in self.projects:
            results[project_name] = self.analyze_project(project_name, days)

        return {
            "timestamp": datetime.now().isoformat(),
            "projects_analyzed": len(results),
            "analysis_period_days": days,
            "projects": results
        }

    def get_portfolio_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get portfolio-wide summary with aggregated metrics

        Args:
            days: Days to analyze

        Returns:
            Portfolio summary with rankings and insights
        """
        all_projects = self.analyze_all_projects(days)

        # Extract health scores
        health_scores = []
        for project_name, data in all_projects["projects"].items():
            if data and "health" in data:
                health_scores.append({
                    "project": project_name,
                    "score": data["health"]["total_score"],
                    "assessment": data["health"]["assessment"],
                    "commits": data["commits"]["count"],
                    "trend": data["commits"]["trend"]
                })

        # Sort by health score
        health_scores.sort(key=lambda x: x["score"], reverse=True)

        # Calculate portfolio stats
        total_commits = sum(
            data["commits"]["count"]
            for data in all_projects["projects"].values()
            if data and "commits" in data
        )

        avg_health = (
            sum(s["score"] for s in health_scores) / len(health_scores)
            if health_scores else 0
        )

        # Identify concerns
        concerns = [
            s for s in health_scores
            if s["score"] < 40 or s["trend"] == "decreasing"
        ]

        # Identify stars
        stars = [
            s for s in health_scores
            if s["score"] >= 80 and s["commits"] >= 10
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_stats": {
                "total_projects": len(health_scores),
                "total_commits": total_commits,
                "average_health": round(avg_health, 1),
                "projects_with_concerns": len(concerns),
                "star_projects": len(stars)
            },
            "rankings": health_scores,
            "concerns": concerns,
            "stars": stars,
            "raw_data": all_projects
        }

    def compare_projects(
        self,
        project1: str,
        project2: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Compare two projects side-by-side

        Args:
            project1: First project name
            project2: Second project name
            days: Days to analyze

        Returns:
            Comparison data
        """
        data1 = self.analyze_project(project1, days)
        data2 = self.analyze_project(project2, days)

        if not data1 or not data2:
            return {
                "error": "One or both projects not found",
                "available": list(self.projects.keys())
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "comparison": {
                project1: {
                    "health_score": data1["health"]["total_score"],
                    "commits": data1["commits"]["count"],
                    "trend": data1["commits"]["trend"],
                    "uncommitted": data1["uncommitted"]["total"]
                },
                project2: {
                    "health_score": data2["health"]["total_score"],
                    "commits": data2["commits"]["count"],
                    "trend": data2["commits"]["trend"],
                    "uncommitted": data2["uncommitted"]["total"]
                }
            },
            "winner": {
                "health": project1 if data1["health"]["total_score"] > data2["health"]["total_score"] else project2,
                "activity": project1 if data1["commits"]["count"] > data2["commits"]["count"] else project2,
                "cleanliness": project1 if data1["uncommitted"]["total"] < data2["uncommitted"]["total"] else project2
            },
            "full_data": {
                project1: data1,
                project2: data2
            }
        }

    def get_trending_projects(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects with increasing activity

        Args:
            days: Days to analyze
            limit: Max number of projects to return

        Returns:
            List of trending projects
        """
        all_projects = self.analyze_all_projects(days)

        trending = []
        for project_name, data in all_projects["projects"].items():
            if data and "commits" in data:
                if data["commits"]["trend"] == "increasing":
                    trending.append({
                        "project": project_name,
                        "commits": data["commits"]["count"],
                        "trend": data["commits"]["trend"],
                        "health_score": data["health"]["total_score"]
                    })

        # Sort by commit count
        trending.sort(key=lambda x: x["commits"], reverse=True)

        return trending[:limit]

    def get_stale_projects(self, days: int = 30, threshold: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects with little or no activity

        Args:
            days: Days to analyze
            threshold: Max commits to be considered stale

        Returns:
            List of stale projects
        """
        all_projects = self.analyze_all_projects(days)

        stale = []
        for project_name, data in all_projects["projects"].items():
            if data and "commits" in data:
                if data["commits"]["count"] <= threshold:
                    stale.append({
                        "project": project_name,
                        "commits": data["commits"]["count"],
                        "days_since_last": days,
                        "health_score": data["health"]["total_score"]
                    })

        # Sort by health score (lowest first)
        stale.sort(key=lambda x: x["health_score"])

        return stale

    def get_project_health_trends(self, project_name: str) -> Dict[str, Any]:
        """
        Get comprehensive health trends for a project with caching

        Args:
            project_name: Name of project to analyze

        Returns:
            Dict with history, insights, and recommendations
        """
        if project_name not in self.projects:
            raise ValueError(f"Project '{project_name}' not found. Available: {list(self.projects.keys())}")

        project_path = self.projects[project_name]
        return self.health_tracker.get_health_trends(project_name, project_path)

    def get_portfolio_health_trends(self) -> Dict[str, Any]:
        """
        Get health trends for all projects in portfolio

        Returns:
            Portfolio-wide trend analysis with categorization
        """
        return self.health_tracker.get_portfolio_trends(self.projects)


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python project_analyzer.py <command> [args]")
        print("\nCommands:")
        print("  summary [days]           - Portfolio summary")
        print("  project <name> [days]    - Analyze specific project")
        print("  compare <proj1> <proj2>  - Compare two projects")
        print("  trending [days]          - Show trending projects")
        print("  stale [days]             - Show stale projects")
        print("  trends <name>            - Health trends for project")
        print("  portfolio-trends         - Health trends for all projects")
        sys.exit(1)

    command = sys.argv[1]
    analyzer = ProjectAnalyzer()

    if command == "summary":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = analyzer.get_portfolio_summary(days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "project":
        if len(sys.argv) < 3:
            print("Error: project name required")
            print("Available:", list(analyzer.projects.keys()))
            sys.exit(1)
        project_name = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        result = analyzer.analyze_project(project_name, days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Error: two project names required")
            print("Available:", list(analyzer.projects.keys()))
            sys.exit(1)
        proj1 = sys.argv[2]
        proj2 = sys.argv[3]
        result = analyzer.compare_projects(proj1, proj2)
        print(json.dumps(result, indent=2, default=str))

    elif command == "trending":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = analyzer.get_trending_projects(days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "stale":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = analyzer.get_stale_projects(days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "trends":
        if len(sys.argv) < 3:
            print("Error: project name required")
            print("Available:", list(analyzer.projects.keys()))
            sys.exit(1)
        project_name = sys.argv[2]
        result = analyzer.get_project_health_trends(project_name)
        print(json.dumps(result, indent=2, default=str))

    elif command == "portfolio-trends":
        result = analyzer.get_portfolio_health_trends()
        print(json.dumps(result, indent=2, default=str))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
