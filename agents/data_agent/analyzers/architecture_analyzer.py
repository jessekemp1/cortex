"""Architecture Analyzer - Detect architectural patterns and design decisions."""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class ArchitectureAnalyzer:
    """Analyze project architecture and detect patterns."""

    def __init__(self, project_path: Path):
        """Initialize architecture analyzer."""
        self.project_path = Path(project_path)

    def analyze_architecture(self) -> Dict[str, Any]:
        """
        Analyze project architecture and detect patterns.
        
        Returns:
            Dict with architectural analysis including patterns and structure
        """
        analysis = {
            "structure_type": self._detect_structure_type(),
            "architectural_patterns": self._detect_architectural_patterns(),
            "design_decisions": self._detect_design_decisions(),
            "module_organization": self._analyze_module_organization(),
            "dependency_structure": self._analyze_dependency_structure(),
        }

        return analysis

    def _detect_structure_type(self) -> str:
        """Detect overall project structure type."""
        # Check for common structure patterns
        if (self.project_path / "src").exists() and (self.project_path / "tests").exists():
            return "src_layout"
        elif (self.project_path / "app").exists() or (self.project_path / "application").exists():
            return "app_layout"
        elif (self.project_path / "lib").exists() or (self.project_path / "libs").exists():
            return "library_layout"
        elif any(self.project_path.glob("*.py")) and not (self.project_path / "src").exists():
            return "flat_layout"
        else:
            return "custom"

    def _detect_architectural_patterns(self) -> List[str]:
        """Detect architectural patterns in code."""
        patterns = []

        # Check Python files for patterns
        python_files = list(self.project_path.rglob("*.py"))[:50]  # Sample first 50

        # MVC pattern
        if self._has_mvc_structure():
            patterns.append("MVC")

        # Repository pattern
        if self._has_repository_pattern():
            patterns.append("Repository")

        # Service layer pattern
        if self._has_service_layer():
            patterns.append("Service Layer")

        # Dependency Injection
        if self._has_dependency_injection():
            patterns.append("Dependency Injection")

        # Factory pattern
        if self._has_factory_pattern():
            patterns.append("Factory")

        # Observer pattern
        if self._has_observer_pattern():
            patterns.append("Observer")

        # API Gateway pattern (FastAPI/Flask routes)
        if self._has_api_gateway():
            patterns.append("API Gateway")

        return patterns

    def _detect_design_decisions(self) -> List[Dict[str, Any]]:
        """Detect key design decisions from code structure."""
        decisions = []

        # Async/await usage
        if self._uses_async():
            decisions.append({
                "decision": "Async/await for concurrency",
                "rationale": "Project uses async/await patterns",
                "impact": "high",
            })

        # Type hints
        if self._uses_type_hints():
            decisions.append({
                "decision": "Type hints for type safety",
                "rationale": "Project uses type annotations",
                "impact": "medium",
            })

        # Dependency management
        if (self.project_path / "poetry.lock").exists():
            decisions.append({
                "decision": "Poetry for dependency management",
                "rationale": "Uses Poetry instead of pip",
                "impact": "medium",
            })
        elif (self.project_path / "requirements.txt").exists():
            decisions.append({
                "decision": "Requirements.txt for dependencies",
                "rationale": "Traditional pip-based dependency management",
                "impact": "low",
            })

        # Testing strategy
        test_files = list(self.project_path.rglob("test_*.py")) + \
                    list(self.project_path.rglob("*_test.py"))
        if len(test_files) > 10:
            decisions.append({
                "decision": "Comprehensive testing",
                "rationale": f"Found {len(test_files)} test files",
                "impact": "high",
            })

        return decisions

    def _analyze_module_organization(self) -> Dict[str, Any]:
        """Analyze how modules are organized."""
        python_files = list(self.project_path.rglob("*.py"))
        
        # Count files by directory depth
        depth_counts = {}
        for py_file in python_files:
            depth = len(py_file.relative_to(self.project_path).parts) - 1
            depth_counts[depth] = depth_counts.get(depth, 0) + 1

        # Identify main modules
        main_modules = []
        for py_file in python_files[:20]:  # Sample
            rel_path = py_file.relative_to(self.project_path)
            if len(rel_path.parts) == 1:  # Root level
                main_modules.append(py_file.stem)

        return {
            "total_modules": len(python_files),
            "depth_distribution": depth_counts,
            "main_modules": sorted(set(main_modules))[:10],
            "organization_style": self._classify_organization_style(depth_counts),
        }

    def _analyze_dependency_structure(self) -> Dict[str, Any]:
        """Analyze dependency structure and coupling."""
        # This would require AST parsing of imports
        # Simplified version for now
        return {
            "analysis": "dependency_analysis_requires_ast_parsing",
            "note": "Full dependency analysis requires AST parsing of all Python files",
        }

    def _has_mvc_structure(self) -> bool:
        """Check for MVC structure (models, views, controllers)."""
        has_models = any(self.project_path.rglob("**/models*.py"))
        has_views = any(self.project_path.rglob("**/views*.py")) or \
                   any(self.project_path.rglob("**/templates"))
        has_controllers = any(self.project_path.rglob("**/controllers*.py")) or \
                         any(self.project_path.rglob("**/routes*.py"))
        return has_models and (has_views or has_controllers)

    def _has_repository_pattern(self) -> bool:
        """Check for repository pattern."""
        return any(self.project_path.rglob("**/repositories*.py")) or \
               any(self.project_path.rglob("**/repository*.py"))

    def _has_service_layer(self) -> bool:
        """Check for service layer pattern."""
        return any(self.project_path.rglob("**/services*.py")) or \
               any(self.project_path.rglob("**/service*.py"))

    def _has_dependency_injection(self) -> bool:
        """Check for dependency injection patterns."""
        python_files = list(self.project_path.rglob("*.py"))[:30]
        for py_file in python_files:
            try:
                content = py_file.read_text()
                # Look for DI indicators
                if "inject" in content.lower() or "@inject" in content:
                    return True
            except Exception:
                pass
        return False

    def _has_factory_pattern(self) -> bool:
        """Check for factory pattern."""
        return any(self.project_path.rglob("**/factory*.py")) or \
               any(self.project_path.rglob("**/factories*.py"))

    def _has_observer_pattern(self) -> bool:
        """Check for observer pattern."""
        python_files = list(self.project_path.rglob("*.py"))[:30]
        for py_file in python_files:
            try:
                content = py_file.read_text()
                if "observer" in content.lower() or "subscribe" in content.lower():
                    return True
            except Exception:
                pass
        return False

    def _has_api_gateway(self) -> bool:
        """Check for API Gateway pattern (routes, endpoints)."""
        return any(self.project_path.rglob("**/routes*.py")) or \
               any(self.project_path.rglob("**/endpoints*.py")) or \
               any(self.project_path.rglob("**/api*.py"))

    def _uses_async(self) -> bool:
        """Check if project uses async/await."""
        python_files = list(self.project_path.rglob("*.py"))[:30]
        for py_file in python_files:
            try:
                content = py_file.read_text()
                if "async def" in content or "await " in content:
                    return True
            except Exception:
                pass
        return False

    def _uses_type_hints(self) -> bool:
        """Check if project uses type hints."""
        python_files = list(self.project_path.rglob("*.py"))[:30]
        type_hint_count = 0
        for py_file in python_files:
            try:
                content = py_file.read_text()
                if "->" in content or ": " in content and ("str" in content or "int" in content or "List" in content):
                    type_hint_count += 1
            except Exception:
                pass
        return type_hint_count > 5  # At least 5 files with type hints

    def _classify_organization_style(self, depth_counts: Dict[int, int]) -> str:
        """Classify module organization style."""
        if not depth_counts:
            return "unknown"
        
        max_depth = max(depth_counts.keys())
        shallow_files = sum(count for depth, count in depth_counts.items() if depth <= 1)
        total_files = sum(depth_counts.values())
        
        if shallow_files / total_files > 0.7:
            return "flat"
        elif max_depth <= 2:
            return "shallow"
        elif max_depth >= 4:
            return "deeply_nested"
        else:
            return "moderate"


