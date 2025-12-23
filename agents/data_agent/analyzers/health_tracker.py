"""
Health Tracker - Historical project health tracking and aggregation

Tracks project health scores over time to identify trends and patterns.
Provides caching to avoid expensive git operations.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .git_analyzer import GitAnalyzer


class HealthTracker:
    """Track and aggregate project health metrics over time"""

    def __init__(self, cache_dir: Path = Path.home() / ".claude" / "health_cache"):
        """
        Initialize health tracker with cache directory

        Args:
            cache_dir: Directory to store cached health data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache TTL (time to live) in seconds - default 1 hour
        self.cache_ttl = 3600

    def _get_cache_path(self, project_name: str) -> Path:
        """Get cache file path for a project"""
        # Sanitize project name for filesystem
        safe_name = project_name.replace("/", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_name}_health.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid (within TTL)"""
        if not cache_path.exists():
            return False

        # Check if cache is within TTL
        cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
        return cache_age < self.cache_ttl

    def _read_cache(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Read cached health data for a project"""
        cache_path = self._get_cache_path(project_name)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _write_cache(self, project_name: str, data: Dict[str, Any]):
        """Write health data to cache"""
        cache_path = self._get_cache_path(project_name)

        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except IOError:
            # Silently fail on cache write errors
            pass

    def get_health_history(
        self,
        project_name: str,
        project_path: Path,
        days: int = 30
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
            "periods": {}
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
                "uncommitted": uncommitted["total"]
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
        sorted_periods = sorted(
            periods.items(),
            key=lambda x: x[1]["days"]
        )

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

    def get_cached_health(
        self,
        project_name: str,
        project_path: Path,
        days: int = 7,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get health data with caching

        Args:
            project_name: Name of project
            project_path: Path to project repository
            days: Days to analyze
            force_refresh: Force cache refresh even if valid

        Returns:
            Health data (from cache or fresh analysis)
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self._read_cache(project_name)
            if cached and cached.get("analysis_period_days") == days:
                cached["from_cache"] = True
                return cached

        # Perform fresh analysis
        analyzer = GitAnalyzer(project_path)
        data = analyzer.get_project_summary(days)
        data["from_cache"] = False

        # Write to cache
        self._write_cache(project_name, data)

        return data

    def get_health_trends(
        self,
        project_name: str,
        project_path: Path
    ) -> Dict[str, Any]:
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
                insights.append({
                    "type": "warning",
                    "message": f"Health declining: {older} → {recent} (down {older - recent} points in 30 days)"
                })
                recommendations.append({
                    "priority": "high",
                    "action": "Investigate cause of declining health",
                    "details": "Check recent commits, uncommitted work, and contributor activity"
                })

        # Check for low commit activity
        if "7d" in periods and periods["7d"]["commits"] < 3:
            insights.append({
                "type": "info",
                "message": f"Low recent activity: {periods['7d']['commits']} commits in 7 days"
            })

        # Check for high uncommitted changes
        if "7d" in periods and periods["7d"]["uncommitted"] > 20:
            insights.append({
                "type": "warning",
                "message": f"High uncommitted changes: {periods['7d']['uncommitted']} files"
            })
            recommendations.append({
                "priority": "medium",
                "action": "Commit or clean up uncommitted work",
                "details": "Large uncommitted work reduces project health score"
            })

        # Check for positive trends
        if history["overall_trend"] == "improving":
            insights.append({
                "type": "success",
                "message": "Project health improving over time"
            })

        return {
            "project": project_name,
            "history": history,
            "insights": insights,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }

    def clear_cache(self, project_name: Optional[str] = None):
        """
        Clear health cache

        Args:
            project_name: Specific project to clear, or None for all
        """
        if project_name:
            cache_path = self._get_cache_path(project_name)
            if cache_path.exists():
                cache_path.unlink()
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*_health.json"):
                cache_file.unlink()

    def get_portfolio_trends(
        self,
        projects: Dict[str, Path]
    ) -> Dict[str, Any]:
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
            "summary": {
                "improving": [],
                "declining": [],
                "stable": [],
                "concerns": []
            }
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
                    portfolio_trends["summary"]["concerns"].append({
                        "project": project_name,
                        "recommendations": len(trends["recommendations"])
                    })

            except Exception as e:
                portfolio_trends["projects"][project_name] = {
                    "error": str(e)
                }

        return portfolio_trends


# CLI for testing
if __name__ == "__main__":
    import sys
    from pathlib import Path as PathLib

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
        print("  cached <project_path> [days]      - Get cached health (or fresh)")
        print("  clear [project_name]              - Clear cache")
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

    elif command == "cached":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)
        project_path = Path(sys.argv[2])
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        result = tracker.get_cached_health("project", project_path, days)
        print(json.dumps(result, indent=2, default=str))

    elif command == "clear":
        project_name = sys.argv[2] if len(sys.argv) > 2 else None
        tracker.clear_cache(project_name)
        print(f"Cache cleared for: {project_name or 'all projects'}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
