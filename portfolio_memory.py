"""
Portfolio Memory - Access cross-project patterns, lessons, and metadata

Reads from ~/.claude/portfolio/project_index.json to provide:
- Project statistics and metadata
- Cross-project patterns
- Lessons learned from past work
- Project context for intelligence queries
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get portfolio statistics"""
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
        
        return {
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
    
    def get_project_context(self, project: str) -> Dict[str, Any]:
        """
        Get detailed context for a specific project
        
        Args:
            project: Project name (e.g., 'VortexV2', 'cortex')
        
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
        
        return {
            "project": project,
            "path": project_data.get("path", ""),
            "priority": project_data.get("priority", "tier3"),
            "activity_7d": project_data.get("activity_commits_7d", 0),
            "tech_stack": project_data.get("tech_stack", []),
            "patterns": pattern_context,
            "common_issues": project_data.get("common_issues", []),
            "related_projects": project_data.get("related_projects", [])
        }
    
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
