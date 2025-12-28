"""Pattern Extraction Tools - Extract patterns from project code."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternExtractor:
    """Extract patterns from project codebases."""

    def __init__(self, root_dir: Path):
        """
        Initialize pattern extractor.

        Args:
            root_dir: Root directory containing projects
        """
        self.root_dir = Path(root_dir)

    def extract_patterns_from_project(
        self, project_path: Path, project_name: str
    ) -> List[Dict[str, Any]]:
        """
        Extract patterns from a single project.

        Args:
            project_path: Path to project directory
            project_name: Name of the project

        Returns:
            List of pattern dictionaries
        """
        patterns = []

        # Look for common pattern indicators
        # 1. FastAPI async route patterns
        patterns.extend(self._extract_fastapi_patterns(project_path, project_name))

        # 2. SQLAlchemy patterns
        patterns.extend(self._extract_sqlalchemy_patterns(project_path, project_name))

        # 3. Error handling patterns
        patterns.extend(self._extract_error_handling_patterns(project_path, project_name))

        # 4. Configuration patterns
        patterns.extend(self._extract_config_patterns(project_path, project_name))

        return patterns

    def _extract_fastapi_patterns(
        self, project_path: Path, project_name: str
    ) -> List[Dict[str, Any]]:
        """Extract FastAPI async route patterns."""
        patterns = []
        routes_files = list(project_path.rglob("**/routes*.py"))
        routes_files.extend(project_path.rglob("**/api*.py"))

        async_routes = 0
        for routes_file in routes_files[:5]:  # Limit to first 5 files
            try:
                content = routes_file.read_text()
                if "@router" in content or "@app" in content:
                    if "async def" in content:
                        async_routes += content.count("async def")
            except Exception:
                pass

        if async_routes > 0:
            patterns.append({
                "pattern": "async_fastapi_routes",
                "description": f"Uses async FastAPI routes ({async_routes} routes found)",
                "project": project_name,
                "success_metrics": {"async_routes_count": async_routes},
                "frequency": 1
            })

        return patterns

    def _extract_sqlalchemy_patterns(
        self, project_path: Path, project_name: str
    ) -> List[Dict[str, Any]]:
        """Extract SQLAlchemy patterns."""
        patterns = []
        model_files = list(project_path.rglob("**/models.py"))
        model_files.extend(project_path.rglob("**/model*.py"))

        sqlalchemy_usage = False
        for model_file in model_files[:5]:
            try:
                content = model_file.read_text()
                if "from sqlalchemy" in content or "import sqlalchemy" in content:
                    sqlalchemy_usage = True
                    break
            except Exception:
                pass

        if sqlalchemy_usage:
            patterns.append({
                "pattern": "sqlalchemy_orm",
                "description": "Uses SQLAlchemy ORM for database access",
                "project": project_name,
                "success_metrics": {},
                "frequency": 1
            })

        return patterns

    def _extract_error_handling_patterns(
        self, project_path: Path, project_name: str
    ) -> List[Dict[str, Any]]:
        """Extract error handling patterns."""
        patterns = []
        python_files = list(project_path.rglob("**/*.py"))[:20]  # Sample first 20 files

        try_except_count = 0
        for py_file in python_files:
            try:
                content = py_file.read_text()
                try_except_count += content.count("try:")
            except Exception:
                pass

        if try_except_count > 5:
            patterns.append({
                "pattern": "comprehensive_error_handling",
                "description": f"Uses try/except blocks for error handling ({try_except_count} instances)",
                "project": project_name,
                "success_metrics": {"try_except_count": try_except_count},
                "frequency": 1
            })

        return patterns

    def _extract_config_patterns(
        self, project_path: Path, project_name: str
    ) -> List[Dict[str, Any]]:
        """Extract configuration management patterns."""
        patterns = []
        config_files = [
            project_path / "config.py",
            project_path / "settings.py",
            project_path / ".env",
            project_path / "config.json"
        ]

        config_found = any(f.exists() for f in config_files)

        if config_found:
            patterns.append({
                "pattern": "centralized_config",
                "description": "Uses centralized configuration management",
                "project": project_name,
                "success_metrics": {},
                "frequency": 1
            })

        return patterns

    def extract_all_patterns(self) -> List[Dict[str, Any]]:
        """Extract patterns from all projects in root directory."""
        all_patterns = []

        for project_dir in self.root_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith("."):
                try:
                    patterns = self.extract_patterns_from_project(
                        project_dir, project_dir.name
                    )
                    all_patterns.extend(patterns)
                except Exception as e:
                    logger.warning(f"Failed to extract patterns from {project_dir}: {e}")

        # Deduplicate and aggregate patterns
        return self._aggregate_patterns(all_patterns)

    def _aggregate_patterns(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aggregate patterns by name, combining projects and metrics.
        
        Args:
            patterns: List of pattern dictionaries
            
        Returns:
            Aggregated patterns with combined project lists and metrics
        """
        pattern_map: Dict[str, Dict[str, Any]] = {}
        
        for pattern in patterns:
            pattern_name = pattern.get("pattern", "")
            if not pattern_name:
                continue
            
            if pattern_name not in pattern_map:
                pattern_map[pattern_name] = {
                    "pattern": pattern_name,
                    "description": pattern.get("description", ""),
                    "projects": [],
                    "success_metrics": {},
                    "frequency": 0,
                    "categories": set(),
                }
            
            # Add project if not already present
            project = pattern.get("project", "")
            if project and project not in pattern_map[pattern_name]["projects"]:
                pattern_map[pattern_name]["projects"].append(project)
            
            # Aggregate success metrics
            metrics = pattern.get("success_metrics", {})
            for key, value in metrics.items():
                if key not in pattern_map[pattern_name]["success_metrics"]:
                    pattern_map[pattern_name]["success_metrics"][key] = []
                if isinstance(value, (int, float)):
                    pattern_map[pattern_name]["success_metrics"][key].append(value)
            
            # Update frequency
            pattern_map[pattern_name]["frequency"] += pattern.get("frequency", 1)
        
        # Convert sets to lists and calculate aggregate metrics
        aggregated = []
        for pattern_name, pattern_data in pattern_map.items():
            # Calculate average metrics
            avg_metrics = {}
            for key, values in pattern_data["success_metrics"].items():
                if values:
                    avg_metrics[key] = sum(values) / len(values)
            
            aggregated.append({
                "pattern": pattern_name,
                "description": pattern_data["description"],
                "projects": pattern_data["projects"],
                "project_count": len(pattern_data["projects"]),
                "success_metrics": avg_metrics,
                "frequency": pattern_data["frequency"],
                "reusability_score": len(pattern_data["projects"]) * 0.1 + pattern_data["frequency"] * 0.05,
            })
        
        # Sort by reusability score
        aggregated.sort(key=lambda x: x.get("reusability_score", 0), reverse=True)
        return aggregated

    def validate_pattern_quality(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pattern quality and return quality metrics.
        
        Args:
            pattern: Pattern dictionary
            
        Returns:
            Dict with quality assessment
        """
        quality_score = 0.0
        issues = []
        
        # Check required fields
        if not pattern.get("pattern"):
            issues.append("Missing pattern name")
        else:
            quality_score += 0.2
        
        if not pattern.get("description"):
            issues.append("Missing description")
        else:
            quality_score += 0.2
        
        # Check project usage
        projects = pattern.get("projects", [])
        if len(projects) == 0:
            issues.append("No projects using this pattern")
        elif len(projects) == 1:
            issues.append("Pattern only used in one project (low reusability)")
        else:
            quality_score += 0.3  # Multi-project usage
        
        # Check success metrics
        metrics = pattern.get("success_metrics", {})
        if metrics:
            quality_score += 0.2
        else:
            issues.append("No success metrics available")
        
        # Check frequency
        frequency = pattern.get("frequency", 0)
        if frequency > 1:
            quality_score += 0.1
        
        return {
            "quality_score": min(quality_score, 1.0),
            "issues": issues,
            "is_high_quality": quality_score >= 0.7,
        }

