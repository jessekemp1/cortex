"""Code Quality Analyzer - Calculate code quality metrics and detect code smells."""

import ast
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CodeQualityAnalyzer:
    """Analyze code quality metrics and detect issues."""

    def __init__(self, project_path: Path):
        """Initialize code quality analyzer."""
        self.project_path = Path(project_path)

    def analyze_quality(self) -> Dict[str, Any]:
        """
        Analyze code quality metrics.
        
        Returns:
            Dict with quality metrics, test coverage, and code smells
        """
        return {
            "test_coverage": self._analyze_test_coverage(),
            "code_smells": self._detect_code_smells(),
            "complexity_metrics": self._calculate_complexity(),
            "code_metrics": self._calculate_code_metrics(),
        }

    def _analyze_test_coverage(self) -> Dict[str, Any]:
        """Analyze test coverage."""
        # Count test files
        test_files = list(self.project_path.rglob("test_*.py")) + \
                    list(self.project_path.rglob("*_test.py")) + \
                    list(self.project_path.rglob("tests/**/*.py"))
        
        # Count source files
        source_files = [f for f in self.project_path.rglob("*.py")
                        if not any(part in str(f) for part in ["test", "tests", "__pycache__"])]
        
        # Try to read actual coverage report
        coverage_report = self._read_coverage_report()
        
        test_file_count = len(test_files)
        source_file_count = len(source_files)
        estimated_coverage = min((test_file_count / source_file_count * 100) if source_file_count > 0 else 0, 100)
        
        return {
            "test_files": test_file_count,
            "source_files": source_file_count,
            "estimated_coverage": round(estimated_coverage, 1),
            "actual_coverage": coverage_report.get("coverage_percent", None),
            "is_low": estimated_coverage < 50,
            "coverage_report_path": coverage_report.get("path"),
        }

    def _read_coverage_report(self) -> Dict[str, Any]:
        """Try to read coverage report if available."""
        # Check for common coverage report locations
        coverage_files = [
            self.project_path / "htmlcov" / "index.html",
            self.project_path / ".coverage",
            self.project_path / "coverage.xml",
        ]
        
        for coverage_file in coverage_files:
            if coverage_file.exists():
                if coverage_file.suffix == ".xml":
                    # Parse XML coverage report
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(coverage_file)
                        root = tree.getroot()
                        # Extract coverage percentage
                        coverage_attr = root.get("line-rate", "0")
                        if coverage_attr:
                            return {
                                "coverage_percent": float(coverage_attr) * 100,
                                "path": str(coverage_file),
                            }
                    except Exception:
                        pass
        
        return {}

    def _detect_code_smells(self) -> List[Dict[str, Any]]:
        """Detect common code smells."""
        smells = []
        python_files = list(self.project_path.rglob("*.py"))[:50]  # Sample

        for py_file in python_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content, filename=str(py_file))
                
                # Long functions
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        lines = len(node.body) if node.body else 0
                        if lines > 50:
                            smells.append({
                                "type": "long_function",
                                "file": str(py_file.relative_to(self.project_path)),
                                "function": node.name,
                                "lines": lines,
                                "severity": "medium",
                            })
                
                # Deep nesting
                max_depth = self._calculate_max_nesting(tree)
                if max_depth > 4:
                    smells.append({
                        "type": "deep_nesting",
                        "file": str(py_file.relative_to(self.project_path)),
                        "max_depth": max_depth,
                        "severity": "medium",
                    })
                
                # Too many parameters
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        param_count = len(node.args.args)
                        if param_count > 7:
                            smells.append({
                                "type": "too_many_parameters",
                                "file": str(py_file.relative_to(self.project_path)),
                                "function": node.name,
                                "parameter_count": param_count,
                                "severity": "low",
                            })

            except Exception as e:
                logger.debug(f"Failed to analyze {py_file}: {e}")

        return smells[:20]  # Limit to top 20

    def _calculate_complexity(self) -> Dict[str, Any]:
        """Calculate code complexity metrics."""
        python_files = list(self.project_path.rglob("*.py"))[:50]
        
        total_lines = 0
        total_functions = 0
        total_classes = 0
        complex_functions = 0

        for py_file in python_files:
            try:
                content = py_file.read_text()
                tree = ast.parse(content, filename=str(py_file))
                
                total_lines += len(content.split("\n"))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        total_functions += 1
                        # Simple complexity: count branches
                        complexity = self._calculate_function_complexity(node)
                        if complexity > 10:
                            complex_functions += 1
                    elif isinstance(node, ast.ClassDef):
                        total_classes += 1

            except Exception:
                pass

        avg_complexity = complex_functions / total_functions if total_functions > 0 else 0

        return {
            "total_lines": total_lines,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "complex_functions": complex_functions,
            "avg_complexity": round(avg_complexity, 2),
        }

    def _calculate_code_metrics(self) -> Dict[str, Any]:
        """Calculate basic code metrics."""
        python_files = list(self.project_path.rglob("*.py"))
        
        metrics = {
            "total_files": len(python_files),
            "total_lines": 0,
            "avg_file_size": 0,
            "largest_file": None,
            "largest_file_size": 0,
        }

        file_sizes = []
        for py_file in python_files:
            try:
                lines = len(py_file.read_text().split("\n"))
                file_sizes.append(lines)
                metrics["total_lines"] += lines
                
                if lines > metrics["largest_file_size"]:
                    metrics["largest_file_size"] = lines
                    metrics["largest_file"] = str(py_file.relative_to(self.project_path))
            except Exception:
                pass

        if file_sizes:
            metrics["avg_file_size"] = round(sum(file_sizes) / len(file_sizes), 1)

        return metrics

    def _calculate_max_nesting(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth in AST."""
        max_depth = 0

        def visit(node: ast.AST, depth: int):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            
            for child in ast.iter_child_nodes(node):
                # Increase depth for control flow nodes
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    visit(child, depth + 1)
                else:
                    visit(child, depth)

        visit(tree, 0)
        return max_depth

    def _calculate_function_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)):
                complexity += 1
        
        return complexity


