"""
Project Analyzer - Multi-project health analysis

Analyzes multiple projects in a portfolio for health scoring,
comparison, and trend detection.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .architecture_analyzer import ArchitectureAnalyzer
from .code_quality_analyzer import CodeQualityAnalyzer
from .git_analyzer import GitAnalyzer
from .health_tracker import HealthTracker
from .tech_stack_detector import TechStackDetector


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
        self, project_name: str, days: int = 30, include_deep_analysis: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a single project with deep analysis capabilities.

        Args:
            project_name: Name of project to analyze
            days: Days to analyze
            include_deep_analysis: Whether to include deep analysis (tech stack, architecture, quality)

        Returns:
            Project analysis with deep analysis results or None if project not found
        """
        if project_name not in self.projects:
            return None

        project_path = self.projects[project_name]

        try:
            analyzer = GitAnalyzer(project_path)
            analysis = analyzer.get_project_summary(days)

            # Add deep analysis if requested
            if include_deep_analysis:
                # Tech stack detection
                tech_detector = TechStackDetector(project_path)
                analysis["tech_stack"] = tech_detector.detect_tech_stack()

                # Architecture analysis
                arch_analyzer = ArchitectureAnalyzer(project_path)
                analysis["architecture"] = arch_analyzer.analyze_architecture()

                # Code quality analysis
                quality_analyzer = CodeQualityAnalyzer(project_path)
                analysis["code_quality"] = quality_analyzer.analyze_quality()

            return analysis
        except Exception as e:
            return {"project": project_name, "error": str(e)}

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
            "projects": results,
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
                health_scores.append(
                    {
                        "project": project_name,
                        "score": data["health"]["total_score"],
                        "assessment": data["health"]["assessment"],
                        "commits": data["commits"]["count"],
                        "trend": data["commits"]["trend"],
                    }
                )

        # Sort by health score
        health_scores.sort(key=lambda x: x["score"], reverse=True)

        # Calculate portfolio stats
        total_commits = sum(
            data["commits"]["count"]
            for data in all_projects["projects"].values()
            if data and "commits" in data
        )

        avg_health = (
            sum(s["score"] for s in health_scores) / len(health_scores) if health_scores else 0
        )

        # Identify concerns
        concerns = [s for s in health_scores if s["score"] < 40 or s["trend"] == "decreasing"]

        # Identify stars
        stars = [s for s in health_scores if s["score"] >= 80 and s["commits"] >= 10]

        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio_stats": {
                "total_projects": len(health_scores),
                "total_commits": total_commits,
                "average_health": round(avg_health, 1),
                "projects_with_concerns": len(concerns),
                "star_projects": len(stars),
            },
            "rankings": health_scores,
            "concerns": concerns,
            "stars": stars,
            "raw_data": all_projects,
        }

    def compare_projects(self, project1: str, project2: str, days: int = 30) -> Dict[str, Any]:
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
                "available": list(self.projects.keys()),
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "comparison": {
                project1: {
                    "health_score": data1["health"]["total_score"],
                    "commits": data1["commits"]["count"],
                    "trend": data1["commits"]["trend"],
                    "uncommitted": data1["uncommitted"]["total"],
                },
                project2: {
                    "health_score": data2["health"]["total_score"],
                    "commits": data2["commits"]["count"],
                    "trend": data2["commits"]["trend"],
                    "uncommitted": data2["uncommitted"]["total"],
                },
            },
            "winner": {
                "health": (
                    project1
                    if data1["health"]["total_score"] > data2["health"]["total_score"]
                    else project2
                ),
                "activity": (
                    project1 if data1["commits"]["count"] > data2["commits"]["count"] else project2
                ),
                "cleanliness": (
                    project1
                    if data1["uncommitted"]["total"] < data2["uncommitted"]["total"]
                    else project2
                ),
            },
            "full_data": {project1: data1, project2: data2},
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
                    trending.append(
                        {
                            "project": project_name,
                            "commits": data["commits"]["count"],
                            "trend": data["commits"]["trend"],
                            "health_score": data["health"]["total_score"],
                        }
                    )

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
                    stale.append(
                        {
                            "project": project_name,
                            "commits": data["commits"]["count"],
                            "days_since_last": days,
                            "health_score": data["health"]["total_score"],
                        }
                    )

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
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        project_path = self.projects[project_name]
        return self.health_tracker.get_health_trends(project_name, project_path)

    def get_portfolio_health_trends(self) -> Dict[str, Any]:
        """
        Get health trends for all projects in portfolio

        Returns:
            Portfolio-wide trend analysis with categorization
        """
        return self.health_tracker.get_portfolio_trends(self.projects)

    def get_dependency_analysis(self, project_name: str) -> Dict[str, Any]:
        """
        Get dependency analysis for a project.

        Args:
            project_name: Name of project to analyze

        Returns:
            Dependency analysis dict
        """
        if project_name not in self.projects:
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        from .dependency_mapper import DependencyMapper

        project_path = self.projects[project_name]
        mapper = DependencyMapper(project_path)
        return mapper.get_cached_analysis()

    def get_dependency_health(self, project_name: str) -> Dict[str, Any]:
        """
        Get dependency health score for a project.

        Args:
            project_name: Name of project to analyze

        Returns:
            Health score dict
        """
        if project_name not in self.projects:
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        from .dependency_mapper import DependencyMapper

        project_path = self.projects[project_name]
        mapper = DependencyMapper(project_path)
        return mapper.calculate_dependency_health()

    def find_circular_dependencies(self, project_name: str) -> Dict[str, Any]:
        """
        Find circular dependencies in a project.

        Args:
            project_name: Name of project to analyze

        Returns:
            Circular dependency analysis dict
        """
        if project_name not in self.projects:
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        from .dependency_mapper import DependencyMapper

        project_path = self.projects[project_name]
        mapper = DependencyMapper(project_path)
        return mapper.find_circular_dependencies()

    def get_package_dependencies(self, project_name: str) -> Dict[str, Any]:
        """
        Get declared dependencies from package manager files.

        Args:
            project_name: Name of project to analyze

        Returns:
            Package file parsing results
        """
        if project_name not in self.projects:
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        from .package_parser import PackageParser

        project_path = self.projects[project_name]
        parser = PackageParser(project_path)
        return parser.get_all_declared_dependencies()

    def compare_package_dependencies(self, project_name: str) -> Dict[str, Any]:
        """
        Compare declared vs actual dependencies for a project.

        Args:
            project_name: Name of project to analyze

        Returns:
            Comparison dict with declared, actual, unused, undeclared
        """
        if project_name not in self.projects:
            raise ValueError(
                f"Project '{project_name}' not found. Available: {list(self.projects.keys())}"
            )

        from .dependency_mapper import DependencyMapper

        project_path = self.projects[project_name]
        mapper = DependencyMapper(project_path)
        return mapper.compare_declared_vs_actual()

    def analyze_portfolio_dependencies(
        self, project_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze dependencies across entire portfolio (monorepo-wide).

        Args:
            project_filter: Optional project name to focus analysis on

        Returns:
            Dict with:
            - cross_project_graph: Dict mapping project -> Set[projects it depends on]
            - coupling_analysis: Analysis of inter-project coupling
            - shared_dependencies: Dependencies used by multiple projects
            - recommendations: Recommendations for decoupling
        """
        from collections import defaultdict

        from .dependency_mapper import DependencyMapper

        result = {
            "projects_analyzed": [],
            "cross_project_graph": {},
            "coupling_analysis": {},
            "shared_dependencies": defaultdict(list),
            "project_dependencies": {},
            "recommendations": [],
            "timestamp": datetime.now().isoformat(),
        }

        # Analyze each project
        projects_to_analyze = [project_filter] if project_filter else list(self.projects.keys())

        for project_name in projects_to_analyze:
            if project_name not in self.projects:
                continue

            try:
                project_path = self.projects[project_name]
                mapper = DependencyMapper(project_path)
                analysis = mapper.get_cached_analysis()

                result["projects_analyzed"].append(project_name)

                # Get external dependencies
                external_deps = set(analysis.get("external_deps", []))
                result["project_dependencies"][project_name] = {
                    "external_deps": sorted(external_deps),
                    "external_count": len(external_deps),
                }

                # Track shared dependencies
                for dep in external_deps:
                    result["shared_dependencies"][dep].append(project_name)

                # Check for cross-project imports
                cross_project = analysis.get("cross_project", {})
                if cross_project:
                    result["cross_project_graph"][project_name] = list(cross_project.keys())

            except Exception as e:
                result["project_dependencies"][project_name] = {"error": str(e)}

        # Analyze coupling
        coupling_scores = {}
        for project, deps in result["cross_project_graph"].items():
            coupling_scores[project] = {
                "outgoing": len(deps),
                "incoming": sum(
                    1
                    for p, d in result["cross_project_graph"].items()
                    if p != project and project in d
                ),
                "bidirectional": sum(
                    1 for dep in deps if project in result["cross_project_graph"].get(dep, [])
                ),
            }

        result["coupling_analysis"] = coupling_scores

        # Find shared dependencies (used by 2+ projects)
        shared = {
            dep: projects
            for dep, projects in result["shared_dependencies"].items()
            if len(projects) > 1
        }
        result["shared_dependencies"] = {k: sorted(v) for k, v in sorted(shared.items())}

        # Generate recommendations
        # High coupling projects
        high_coupling = [p for p, c in coupling_scores.items() if c["outgoing"] + c["incoming"] > 3]
        if high_coupling:
            result["recommendations"].append(
                {
                    "priority": "medium",
                    "action": "Review high coupling projects",
                    "details": f"Projects with high coupling: {', '.join(high_coupling)}",
                }
            )

        # Bidirectional coupling (circular dependencies across projects)
        circular = [p for p, c in coupling_scores.items() if c["bidirectional"] > 0]
        if circular:
            result["recommendations"].append(
                {
                    "priority": "high",
                    "action": "Resolve circular project dependencies",
                    "details": f"Projects with bidirectional coupling: {', '.join(circular)}",
                }
            )

        # Shared dependencies opportunities
        if len(result["shared_dependencies"]) > 5:
            result["recommendations"].append(
                {
                    "priority": "low",
                    "action": "Consider shared utility library",
                    "details": f"{len(result['shared_dependencies'])} dependencies shared across projects",
                }
            )

        return result


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
