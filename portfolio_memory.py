"""
Portfolio Memory - Access cross-project patterns, lessons, and metadata

Reads from ~/.claude/portfolio/project_index.json to provide:
- Project statistics and metadata
- Cross-project patterns
- Lessons learned from past work
- Project context for intelligence queries
- Project health tracking and trends
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class PortfolioMemory:
    """Access portfolio-wide patterns, lessons, and project metadata"""

    def __init__(self, portfolio_path: Path = Path.home() / ".claude" / "portfolio"):
        self.portfolio_path = portfolio_path
        self.index_file = portfolio_path / "project_index.json"
        self.portfolio_data = self._load_portfolio()

        # Lazy load health tracker
        self._health_tracker = None
    
    def _load_portfolio(self) -> Dict[str, Any]:
        """Load portfolio data from project_index.json"""
        if not self.index_file.exists():
            return {
                "meta": {
                    "last_updated": datetime.now().isoformat(),
                    "total_projects": 0,
                    "total_specs": 0
                },
                "projects": {}
            }

        with open(self.index_file, 'r') as f:
            return json.load(f)

    def _get_health_tracker(self):
        """Lazy load HealthTracker to avoid import errors"""
        if self._health_tracker is None:
            try:
                # Try absolute import first
                from cortex.agents.data_agent.analyzers.health_tracker import HealthTracker
                self._health_tracker = HealthTracker()
            except ImportError:
                try:
                    # Try relative import
                    from agents.data_agent.analyzers.health_tracker import HealthTracker
                    self._health_tracker = HealthTracker()
                except ImportError:
                    # HealthTracker not available
                    pass
        return self._health_tracker
    
    def get_stats(self, include_health: bool = True) -> Dict[str, Any]:
        """
        Get portfolio statistics

        Args:
            include_health: Include health summary (default: True)

        Returns:
            Portfolio statistics with optional health data
        """
        projects = self.portfolio_data.get("projects", {})

        # Calculate stats
        total_projects = len(projects)
        tier1_count = sum(1 for p in projects.values() if p.get("priority") == "tier1")
        tier2_count = sum(1 for p in projects.values() if p.get("priority") == "tier2")
        tier3_count = sum(1 for p in projects.values() if p.get("priority") == "tier3")

        # Active projects (commits in last 7 days)
        active_projects = [
            name for name, data in projects.items()
            if data.get("activity_commits_7d", 0) > 0
        ]

        # Tech stack distribution
        all_tech = []
        for proj_data in projects.values():
            all_tech.extend(proj_data.get("tech_stack", []))

        from collections import Counter
        tech_counts = Counter(all_tech)
        top_tech = dict(tech_counts.most_common(10))

        # Pattern distribution
        all_patterns = []
        for proj_data in projects.values():
            all_patterns.extend(proj_data.get("common_patterns", []))

        pattern_counts = Counter(all_patterns)
        top_patterns = dict(pattern_counts.most_common(10))

        stats = {
            "total_projects": total_projects,
            "by_priority": {
                "tier1": tier1_count,
                "tier2": tier2_count,
                "tier3": tier3_count
            },
            "active_projects": len(active_projects),
            "active_project_names": active_projects[:10],  # Top 10
            "top_technologies": top_tech,
            "top_patterns": top_patterns,
            "last_updated": self.portfolio_data.get("meta", {}).get("last_updated", "Unknown")
        }

        # Add health summary if requested
        if include_health:
            health_summary = self.get_portfolio_health_summary(days=7)
            if "error" not in health_summary:
                stats["health"] = {
                    "healthy_count": len(health_summary["aggregate"]["healthy_projects"]),
                    "at_risk_count": len(health_summary["aggregate"]["at_risk_projects"]),
                    "critical_count": len(health_summary["aggregate"]["critical_projects"]),
                    "projects": health_summary["projects"]
                }

        return stats
    
    def get_cross_project_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns
        
        Args:
            pattern_type: Optional filter (e.g., 'async_fastapi_routes', 'sqlalchemy_2.0_queries')
        
        Returns:
            List of pattern dictionaries with usage examples
        """
        projects = self.portfolio_data.get("projects", {})
        
        # Collect all patterns with their project usage
        pattern_usage = {}
        for project_name, project_data in projects.items():
            patterns = project_data.get("common_patterns", [])
            for pattern in patterns:
                if pattern_type and pattern != pattern_type:
                    continue
                
                if pattern not in pattern_usage:
                    pattern_usage[pattern] = {
                        "pattern": pattern,
                        "used_in": [],
                        "count": 0
                    }
                
                pattern_usage[pattern]["used_in"].append({
                    "project": project_name,
                    "priority": project_data.get("priority", "tier3"),
                    "path": project_data.get("path", "")
                })
                pattern_usage[pattern]["count"] += 1
        
        # Sort by usage count (most common first)
        patterns_list = sorted(
            pattern_usage.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        return patterns_list
    
    def get_lessons_learned(
        self, 
        project: Optional[str] = None, 
        pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get lessons learned from past work
        
        Args:
            project: Optional project filter
            pattern: Optional pattern filter (e.g., 'async', 'sqlalchemy')
        
        Returns:
            List of lesson dictionaries
        """
        projects = self.portfolio_data.get("projects", {})
        lessons = []
        
        for project_name, project_data in projects.items():
            # Filter by project if specified
            if project and project_name != project:
                continue
            
            # Extract issues as lessons
            issues = project_data.get("common_issues", [])
            for issue in issues:
                # Filter by pattern if specified
                if pattern and pattern.lower() not in issue.lower():
                    continue
                
                lessons.append({
                    "lesson": issue,
                    "project": project_name,
                    "priority": project_data.get("priority", "tier3"),
                    "source": "common_issues"
                })
            
            # Extract from related_projects context (migration lessons)
            related = project_data.get("related_projects", [])
            if related and "migration" in str(project_data.get("tech_stack", [])).lower():
                lessons.append({
                    "lesson": f"Project shares context with: {', '.join(related)}",
                    "project": project_name,
                    "priority": project_data.get("priority", "tier3"),
                    "source": "related_projects"
                })
        
        return lessons
    
    def get_project_context(self, project: str, include_health: bool = True) -> Dict[str, Any]:
        """
        Get detailed context for a specific project

        Args:
            project: Project name (e.g., 'VortexV2', 'cortex')
            include_health: Include health score data (default: True)

        Returns:
            Project context dictionary
        """
        projects = self.portfolio_data.get("projects", {})

        if project not in projects:
            # Try case-insensitive match
            project_lower = project.lower()
            for proj_name in projects.keys():
                if proj_name.lower() == project_lower:
                    project = proj_name
                    break
            else:
                return {
                    "error": f"Project '{project}' not found in portfolio",
                    "available_projects": list(projects.keys())[:10]
                }

        project_data = projects[project]

        # Enrich with cross-project context
        patterns = project_data.get("common_patterns", [])
        pattern_context = []
        for pattern in patterns:
            cross_project_patterns = self.get_cross_project_patterns(pattern)
            if cross_project_patterns:
                pattern_context.append({
                    "pattern": pattern,
                    "also_used_in": [
                        p["project"] for p in cross_project_patterns[0]["used_in"]
                        if p["project"] != project
                    ][:5]  # Top 5 other projects
                })

        context = {
            "project": project,
            "path": project_data.get("path", ""),
            "priority": project_data.get("priority", "tier3"),
            "activity_7d": project_data.get("activity_commits_7d", 0),
            "tech_stack": project_data.get("tech_stack", []),
            "patterns": pattern_context,
            "common_issues": project_data.get("common_issues", []),
            "related_projects": project_data.get("related_projects", [])
        }

        # Add health data if requested
        if include_health:
            # Use Dev directory as git repo root
            health_data = self._get_health_for_project(project, days=7)
            if health_data:
                context["health"] = health_data

        return context
    
    def search_projects(self, query: str) -> List[str]:
        """
        Search for projects by name or technology

        Args:
            query: Search query (project name or tech)

        Returns:
            List of matching project names
        """
        projects = self.portfolio_data.get("projects", {})
        query_lower = query.lower()
        matches = []

        for project_name, project_data in projects.items():
            # Match on project name
            if query_lower in project_name.lower():
                matches.append(project_name)
                continue

            # Match on tech stack
            tech_stack = project_data.get("tech_stack", [])
            if any(query_lower in tech.lower() for tech in tech_stack):
                matches.append(project_name)
                continue

            # Match on patterns
            patterns = project_data.get("common_patterns", [])
            if any(query_lower in pattern.lower() for pattern in patterns):
                matches.append(project_name)

        return matches

    def _get_health_for_project(self, project_name: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Internal method to get health data for a project

        Since all projects are in the Dev git repo, we analyze the entire repo.
        This is a helper for get_project_context.

        Args:
            project_name: Project name
            days: Days to analyze

        Returns:
            Dict with score, assessment, trend, commits_7d, uncommitted_files or None
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return None

        # Use Dev directory as the git root
        dev_path = Path("/Users/jesse.kemp/Dev")
        if not (dev_path / ".git").exists():
            return None

        try:
            result = tracker.get_cached_health("Dev", dev_path, days=days)

            # Extract health metrics from nested structure
            health_section = result.get("health", {})
            commits_section = result.get("commits", {})
            uncommitted_section = result.get("uncommitted", {})

            return {
                "score": health_section.get("total_score", 0),
                "assessment": health_section.get("assessment", "unknown"),
                "trend": commits_section.get("trend", "unknown"),
                "commits_7d": commits_section.get("count", 0),
                "uncommitted_files": uncommitted_section.get("total", 0)
            }
        except Exception:
            return None

    def get_project_health(
        self,
        project_name: str,
        days: int = 7,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get health score and analysis for a specific project

        Args:
            project_name: Project name (e.g., 'VortexV2', 'cortex')
            days: Days to analyze (default: 7)
            force_refresh: Force cache refresh

        Returns:
            Dict with health score, assessment, recommendations

        Example:
            >>> pm = PortfolioMemory()
            >>> health = pm.get_project_health("cortex")
            >>> print(health["score"])
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {
                "error": "HealthTracker not available",
                "project": project_name
            }

        projects = self.portfolio_data.get("projects", {})

        # Find project (case-insensitive)
        actual_name = project_name
        for proj_name in projects.keys():
            if proj_name.lower() == project_name.lower():
                actual_name = proj_name
                break

        # Use Dev directory as git root (all projects are in one repo)
        dev_path = Path("/Users/jesse.kemp/Dev")
        if not (dev_path / ".git").exists():
            return {
                "error": "Git repository not found",
                "project": actual_name
            }

        try:
            result = tracker.get_cached_health(
                "Dev",
                dev_path,
                days=days,
                force_refresh=force_refresh
            )

            # Extract and flatten health data
            health_section = result.get("health", {})
            commits_section = result.get("commits", {})
            uncommitted_section = result.get("uncommitted", {})

            return {
                "project": actual_name,
                "score": health_section.get("total_score", 0),
                "assessment": health_section.get("assessment", "unknown"),
                "breakdown": health_section.get("breakdown", {}),
                "trend": commits_section.get("trend", "unknown"),
                "commits_7d": commits_section.get("count", 0),
                "uncommitted_files": uncommitted_section.get("total", 0),
                "analysis_period_days": days,
                "from_cache": result.get("from_cache", False)
            }
        except Exception as e:
            return {
                "error": str(e),
                "project": actual_name
            }

    def get_portfolio_health_summary(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get health summary for all projects in portfolio

        Args:
            days: Days to analyze (default: 7)

        Returns:
            Dict with health scores for all projects

        Example:
            >>> pm = PortfolioMemory()
            >>> summary = pm.get_portfolio_health_summary()
            >>> for project, health in summary["projects"].items():
            ...     print(f"{project}: {health['score']}")
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {
                "error": "HealthTracker not available"
            }

        projects = self.portfolio_data.get("projects", {})

        # Get health for Dev repo (contains all projects)
        dev_path = Path("/Users/jesse.kemp/Dev")
        if not (dev_path / ".git").exists():
            return {
                "error": "Git repository not found"
            }

        try:
            result = tracker.get_cached_health("Dev", dev_path, days=days)
            health_section = result.get("health", {})
            commits_section = result.get("commits", {})
            uncommitted_section = result.get("uncommitted", {})

            score = health_section.get("total_score", 0)
            assessment = health_section.get("assessment", "unknown")
            trend = commits_section.get("trend", "unknown")
            commits = commits_section.get("count", 0)
            uncommitted = uncommitted_section.get("total", 0)

        except Exception as e:
            return {
                "error": str(e)
            }

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_projects": len(projects),
            "analysis_period_days": days,
            "projects": {},
            "aggregate": {
                "healthy_projects": [],
                "at_risk_projects": [],
                "critical_projects": []
            },
            "overall": {
                "score": score,
                "assessment": assessment,
                "trend": trend,
                "commits": commits,
                "uncommitted": uncommitted
            }
        }

        # Apply same health metrics to all projects (since they're in same repo)
        for project_name in projects.keys():
            summary["projects"][project_name] = {
                "score": score,
                "assessment": assessment,
                "trend": trend,
                "commits": commits,
                "uncommitted": uncommitted
            }

            # Categorize by health
            if score >= 70:
                summary["aggregate"]["healthy_projects"].append(project_name)
            elif score >= 50:
                summary["aggregate"]["at_risk_projects"].append(project_name)
            else:
                summary["aggregate"]["critical_projects"].append(project_name)

        return summary

    def get_project_health_trends(
        self,
        project_name: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive health trends for a project

        Args:
            project_name: Project name

        Returns:
            Dict with trends, insights, recommendations

        Example:
            >>> pm = PortfolioMemory()
            >>> trends = pm.get_project_health_trends("cortex")
            >>> print(trends["insights"])
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {
                "error": "HealthTracker not available",
                "project": project_name
            }

        projects = self.portfolio_data.get("projects", {})

        # Find project (case-insensitive)
        project_data = None
        actual_name = project_name
        for proj_name, data in projects.items():
            if proj_name.lower() == project_name.lower():
                project_data = data
                actual_name = proj_name
                break

        if not project_data:
            return {
                "error": f"Project '{project_name}' not found in portfolio"
            }

        project_path = Path(project_data.get("path", ""))
        if not project_path.exists():
            return {
                "error": f"Project path not found: {project_path}"
            }

        try:
            trends = tracker.get_health_trends(actual_name, project_path)
            return trends
        except Exception as e:
            return {
                "error": str(e),
                "project": actual_name
            }


# CLI helper for testing
if __name__ == "__main__":
    import sys
    
    pm = PortfolioMemory()
    
    if len(sys.argv) < 2:
        print("Usage: python portfolio_memory.py <command> [args]")
        print("Commands: stats, patterns, lessons, project <name>, search <query>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "stats":
        import json
        print(json.dumps(pm.get_stats(), indent=2))
    
    elif command == "patterns":
        pattern_type = sys.argv[2] if len(sys.argv) > 2 else None
        patterns = pm.get_cross_project_patterns(pattern_type)
        for p in patterns:
            print(f"\n{p['pattern']} (used in {p['count']} projects)")
            for usage in p['used_in'][:3]:
                print(f"  - {usage['project']} ({usage['priority']})")
    
    elif command == "lessons":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        lessons = pm.get_lessons_learned(project=project)
        for lesson in lessons:
            print(f"\n[{lesson['project']}] {lesson['lesson']}")
    
    elif command == "project":
        if len(sys.argv) < 3:
            print("Usage: python portfolio_memory.py project <name>")
            sys.exit(1)
        project_name = sys.argv[2]
        context = pm.get_project_context(project_name)
        import json
        print(json.dumps(context, indent=2))
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python portfolio_memory.py search <query>")
            sys.exit(1)
        query = sys.argv[2]
        matches = pm.search_projects(query)
        print(f"Found {len(matches)} projects matching '{query}':")
        for match in matches:
            print(f"  - {match}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
