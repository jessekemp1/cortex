#!/usr/bin/env python3
"""
Project Profiler - Deep analysis of project structure and health.

Layer 1 of Cortex Intelligence Stack: Foundation data for smart recommendations.

Capabilities:
- Tech stack detection (languages, frameworks, databases)
- Test coverage estimation
- Critical file identification
- Linter/formatter detection
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class TechStack:
    """Detected technology stack for a project."""

    languages: Set[str] = field(default_factory=set)
    frameworks: Set[str] = field(default_factory=set)
    databases: Set[str] = field(default_factory=set)
    tools: Set[str] = field(default_factory=set)
    version_info: Dict[str, str] = field(default_factory=dict)

    def primary_language(self) -> Optional[str]:
        """Get primary language (first detected)."""
        return next(iter(self.languages)) if self.languages else None

    def to_compact_str(self) -> str:
        """Convert to compact string for context injection."""
        parts = []

        # Language with version if available
        if self.languages:
            lang = next(iter(self.languages))
            version = self.version_info.get(lang, "")
            if version:
                parts.append(f"{lang} {version}")
            else:
                parts.append(lang)

        # Framework (first one)
        if self.frameworks:
            parts.append(next(iter(self.frameworks)))

        # Database (first one)
        if self.databases:
            parts.append(next(iter(self.databases)))

        return "/".join(parts)


@dataclass
class TestCoverage:
    """Test coverage metrics."""

    test_files: int = 0
    source_files: int = 0
    coverage_percent: Optional[float] = None
    has_coverage_report: bool = False

    @property
    def estimated_coverage(self) -> float:
        """Estimate coverage based on test-to-source ratio."""
        if self.coverage_percent is not None:
            return self.coverage_percent

        if self.source_files == 0:
            return 0.0

        # Rough heuristic: test files / source files * 60%
        # (not perfect but gives ballpark estimate)
        ratio = self.test_files / max(1, self.source_files)
        return min(100.0, ratio * 60.0)

    @property
    def is_low(self) -> bool:
        """Check if coverage is below recommended threshold."""
        return self.estimated_coverage < 50.0

    def to_compact_str(self) -> str:
        """Convert to compact string for warnings."""
        cov = int(self.estimated_coverage)
        if self.has_coverage_report:
            return f"Test coverage: {cov}% (measured)"
        return f"Test coverage: ~{cov}% (estimated)"


@dataclass
class CriticalFile:
    """A critical file in the project."""

    path: str
    reason: str
    change_frequency: int = 0


@dataclass
class ProjectProfile:
    """Complete project profile."""

    project_name: str
    project_path: Path
    tech_stack: TechStack
    test_coverage: TestCoverage
    critical_files: List[CriticalFile] = field(default_factory=list)
    has_linter: bool = False
    has_formatter: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_context_str(self, max_chars: int = 100) -> str:
        """
        Convert profile to context string for injection.

        Format: "Project (Tech Stack) | Warning"
        Example: "Vortex backend (Python 3.11/FastAPI/PostgreSQL) | Test coverage: 45%"
        """
        parts = []

        # Project name with tech stack
        tech = self.tech_stack.to_compact_str()
        if tech:
            parts.append(f"{self.project_name} ({tech})")
        else:
            parts.append(self.project_name)

        # Add most important warning (if any)
        if self.warnings:
            warning = self.warnings[0]
            parts.append(f"⚠️  {warning}")

        result = " | ".join(parts)

        # Truncate if needed
        if len(result) > max_chars:
            result = result[: max_chars - 3] + "..."

        return result


class ProjectProfiler:
    """Deep project analysis engine."""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path).resolve()
        self.project_name = self.project_path.name

    def profile(self, quick: bool = False) -> ProjectProfile:
        """
        Run full project profile analysis.

        Args:
            quick: If True, skip expensive operations (critical files, git log)

        Returns:
            ProjectProfile with all detected information
        """
        tech_stack = self._detect_tech_stack()
        test_coverage = self._estimate_test_coverage(quick=quick)

        # Skip expensive operations in quick mode
        if quick:
            critical_files = []
        else:
            critical_files = self._identify_critical_files()

        has_linter = self._has_linter()
        has_formatter = self._has_formatter()
        warnings = self._generate_warnings(tech_stack, test_coverage)

        return ProjectProfile(
            project_name=self.project_name,
            project_path=self.project_path,
            tech_stack=tech_stack,
            test_coverage=test_coverage,
            critical_files=critical_files,
            has_linter=has_linter,
            has_formatter=has_formatter,
            warnings=warnings,
        )

    def _detect_tech_stack(self) -> TechStack:
        """Detect technology stack from project files."""
        stack = TechStack()

        # Python
        if (self.project_path / "requirements.txt").exists() or (
            self.project_path / "pyproject.toml"
        ).exists():
            stack.languages.add("Python")

            # Detect Python version
            python_version = self._detect_python_version()
            if python_version:
                stack.version_info["Python"] = python_version

            # Detect Python frameworks
            stack.frameworks.update(self._detect_python_frameworks())

        # JavaScript/TypeScript
        if (self.project_path / "package.json").exists():
            package_json = self._read_json("package.json")
            if package_json:
                # Detect if TypeScript
                deps = {
                    **package_json.get("dependencies", {}),
                    **package_json.get("devDependencies", {}),
                }
                if "typescript" in deps:
                    stack.languages.add("TypeScript")
                else:
                    stack.languages.add("JavaScript")

                # Detect JS frameworks
                stack.frameworks.update(self._detect_js_frameworks(package_json))

        # Go
        if (self.project_path / "go.mod").exists():
            stack.languages.add("Go")
            go_version = self._detect_go_version()
            if go_version:
                stack.version_info["Go"] = go_version

        # Rust
        if (self.project_path / "Cargo.toml").exists():
            stack.languages.add("Rust")

        # Databases
        stack.databases.update(self._detect_databases())

        # Tools
        stack.tools.update(self._detect_tools())

        return stack

    def _detect_python_version(self) -> Optional[str]:
        """Detect Python version from pyproject.toml or .python-version."""
        # Try .python-version first
        python_version_file = self.project_path / ".python-version"
        if python_version_file.exists():
            version = python_version_file.read_text().strip()
            if version:
                return version

        # Try pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Look for python = "^3.11" or similar
            match = re.search(r'python\s*=\s*["\'][\^>=~]*([0-9.]+)', content)
            if match:
                return match.group(1)

        return None

    def _detect_python_frameworks(self) -> Set[str]:
        """Detect Python frameworks from requirements or imports."""
        frameworks = set()

        # Read requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text().lower()
            if "fastapi" in content:
                frameworks.add("FastAPI")
            elif "flask" in content:
                frameworks.add("Flask")
            elif "django" in content:
                frameworks.add("Django")

            if "streamlit" in content:
                frameworks.add("Streamlit")

        # Read pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text().lower()
            if "fastapi" in content:
                frameworks.add("FastAPI")
            elif "flask" in content:
                frameworks.add("Flask")
            elif "django" in content:
                frameworks.add("Django")

        return frameworks

    def _detect_js_frameworks(self, package_json: Dict) -> Set[str]:
        """Detect JavaScript/TypeScript frameworks."""
        frameworks = set()
        deps = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        if "react" in deps:
            frameworks.add("React")
        if "vue" in deps:
            frameworks.add("Vue")
        if "next" in deps:
            frameworks.add("Next.js")
        if "express" in deps:
            frameworks.add("Express")
        if "react-native" in deps:
            frameworks.add("React Native")

        return frameworks

    def _detect_go_version(self) -> Optional[str]:
        """Detect Go version from go.mod."""
        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            content = go_mod.read_text()
            match = re.search(r"go\s+([0-9.]+)", content)
            if match:
                return match.group(1)
        return None

    def _detect_databases(self) -> Set[str]:
        """Detect databases from dependencies and config files."""
        databases = set()

        # Python databases
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text().lower()
            if "psycopg2" in content or "asyncpg" in content:
                databases.add("PostgreSQL")
            if "pymongo" in content:
                databases.add("MongoDB")
            if "redis" in content:
                databases.add("Redis")
            if "mysql" in content:
                databases.add("MySQL")
            if "sqlite" in content:
                databases.add("SQLite")

        # JS databases
        package_json = self._read_json("package.json")
        if package_json:
            deps = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {}),
            }
            if "pg" in deps or "postgres" in deps:
                databases.add("PostgreSQL")
            if "mongodb" in deps:
                databases.add("MongoDB")
            if "redis" in deps:
                databases.add("Redis")
            if "mysql" in deps:
                databases.add("MySQL")

        return databases

    def _detect_tools(self) -> Set[str]:
        """Detect development tools."""
        tools = set()

        if (self.project_path / "docker-compose.yml").exists():
            tools.add("Docker Compose")
        elif (self.project_path / "Dockerfile").exists():
            tools.add("Docker")

        if (self.project_path / ".github" / "workflows").exists():
            tools.add("GitHub Actions")

        return tools

    def _estimate_test_coverage(self, quick: bool = False) -> TestCoverage:
        """
        Estimate test coverage from file counts and coverage reports.

        Args:
            quick: If True, skip file counting (faster but less accurate)
        """
        coverage = TestCoverage()

        # In quick mode, only check for coverage reports
        if quick:
            coverage_files = [
                ".coverage",
                "coverage.xml",
                "htmlcov/index.html",
                "coverage/lcov.info",
            ]
            for cov_file in coverage_files:
                if (self.project_path / cov_file).exists():
                    coverage.has_coverage_report = True
                    actual_coverage = self._parse_coverage_report()
                    if actual_coverage is not None:
                        coverage.coverage_percent = actual_coverage
                    break
            return coverage

        # Count test files
        test_patterns = [
            "**/test_*.py",
            "**/tests/**/*.py",
            "**/*.test.ts",
            "**/*.test.js",
            "**/*.spec.ts",
        ]
        test_files = set()
        for pattern in test_patterns:
            test_files.update(self.project_path.glob(pattern))

        coverage.test_files = len(test_files)

        # Count source files (exclude tests, venv, node_modules)
        source_patterns = ["**/*.py", "**/*.ts", "**/*.js", "**/*.go", "**/*.rs"]
        exclude_patterns = [
            "venv",
            "env",
            "node_modules",
            ".venv",
            "dist",
            "build",
            "__pycache__",
            "tests",
            "test",
        ]

        source_files = set()
        for pattern in source_patterns:
            for file in self.project_path.glob(pattern):
                # Exclude if in excluded directory
                if any(excluded in file.parts for excluded in exclude_patterns):
                    continue
                source_files.add(file)

        coverage.source_files = len(source_files)

        # Check for coverage reports
        coverage_files = [
            ".coverage",
            "coverage.xml",
            "htmlcov/index.html",
            "coverage/lcov.info",
        ]
        for cov_file in coverage_files:
            if (self.project_path / cov_file).exists():
                coverage.has_coverage_report = True
                # Try to parse actual coverage
                actual_coverage = self._parse_coverage_report()
                if actual_coverage is not None:
                    coverage.coverage_percent = actual_coverage
                break

        return coverage

    def _parse_coverage_report(self) -> Optional[float]:
        """Parse actual coverage percentage from coverage reports."""
        # Try to parse Python coverage
        coverage_file = self.project_path / ".coverage"
        if coverage_file.exists():
            try:
                # Try to run coverage report
                result = subprocess.run(
                    ["coverage", "report", "--precision=0"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    # Parse "TOTAL    100"
                    match = re.search(r"TOTAL\s+(\d+)%", result.stdout)
                    if match:
                        return float(match.group(1))
            except Exception:
                pass

        return None

    def _identify_critical_files(self, limit: int = 10) -> List[CriticalFile]:
        """
        Identify critical files based on git history and complexity.

        Critical files are those that:
        1. Change frequently (git log)
        2. Are central to the architecture (main.py, app.py, etc.)
        """
        critical_files = []

        # Architecture-critical files (by name pattern)
        critical_patterns = {
            "main.py": "Application entry point",
            "app.py": "Application core",
            "__init__.py": "Package initialization",
            "config.py": "Configuration",
            "settings.py": "Settings",
            "models.py": "Data models",
            "engine.py": "Core engine",
            "index.ts": "TypeScript entry point",
            "App.tsx": "React app root",
        }

        # Exclude patterns for directories to ignore
        exclude_patterns = [
            "venv",
            "env",
            ".venv",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
        ]

        for pattern, reason in critical_patterns.items():
            matches = list(self.project_path.glob(f"**/{pattern}"))
            for match in matches[:3]:  # Limit to 3 per pattern
                # Skip if in excluded directory
                if any(excluded in match.parts for excluded in exclude_patterns):
                    continue

                rel_path = match.relative_to(self.project_path)
                critical_files.append(
                    CriticalFile(path=str(rel_path), reason=reason, change_frequency=0)
                )

        # Get frequently changed files from git (with limits for performance)
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--pretty=format:",
                    "--name-only",
                    "--since=1.month",
                    "--max-count=100",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=3,  # Reduced timeout
            )
            if result.returncode == 0:
                # Count file changes
                file_changes = {}
                for line in result.stdout.split("\n"):
                    if line.strip():
                        file_changes[line.strip()] = file_changes.get(line.strip(), 0) + 1

                # Add top frequently changed files
                sorted_files = sorted(file_changes.items(), key=lambda x: x[1], reverse=True)
                for file_path, count in sorted_files[:5]:
                    # Skip if already in list
                    if not any(cf.path == file_path for cf in critical_files):
                        critical_files.append(
                            CriticalFile(
                                path=file_path,
                                reason=f"High change frequency ({count} changes in 3mo)",
                                change_frequency=count,
                            )
                        )
        except Exception:
            pass

        return critical_files[:limit]

    def _has_linter(self) -> bool:
        """Check if project has linter configured."""
        linter_files = [
            ".pylintrc",
            ".flake8",
            "pyproject.toml",  # Can contain ruff/black config
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.json",
        ]

        for linter_file in linter_files:
            if (self.project_path / linter_file).exists():
                return True

        return False

    def _has_formatter(self) -> bool:
        """Check if project has formatter configured."""
        formatter_files = [
            ".prettierrc",
            ".prettierrc.json",
            "pyproject.toml",  # Can contain black config
        ]

        for formatter_file in formatter_files:
            if (self.project_path / formatter_file).exists():
                return True

        return False

    def _generate_warnings(self, tech_stack: TechStack, test_coverage: TestCoverage) -> List[str]:
        """Generate warnings based on project analysis."""
        warnings = []

        # Low test coverage warning (only if we actually counted files)
        if test_coverage.source_files > 0 and test_coverage.is_low:
            warnings.append(
                f"Test coverage: {int(test_coverage.estimated_coverage)}% (target: 70%)"
            )

        # No linter warning
        if not self._has_linter() and tech_stack.primary_language():
            warnings.append(f"No linter configured for {tech_stack.primary_language()}")

        # No tests at all (only if we actually counted files)
        if test_coverage.source_files > 5 and test_coverage.test_files == 0:
            warnings.append("No test files detected")

        return warnings

    def _read_json(self, filename: str) -> Optional[Dict]:
        """Read and parse JSON file."""
        file_path = self.project_path / filename
        if file_path.exists():
            try:
                return json.loads(file_path.read_text())
            except Exception:
                pass
        return None


def profile_project(project_path: Path, quick: bool = False) -> ProjectProfile:
    """
    Profile a project and return comprehensive analysis.

    Args:
        project_path: Path to project directory
        quick: If True, skip expensive operations (for fast context injection)

    Returns:
        ProjectProfile with tech stack, coverage, critical files, warnings
    """
    profiler = ProjectProfiler(project_path)
    return profiler.profile(quick=quick)


def main():
    """CLI for testing project profiler."""
    import sys

    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1])
    else:
        project_path = Path.cwd()

    profile = profile_project(project_path)

    print(f"=== Project Profile: {profile.project_name} ===\n")

    # Tech stack
    print(f"Tech Stack: {profile.tech_stack.to_compact_str()}")
    print(f"  Languages: {', '.join(profile.tech_stack.languages)}")
    if profile.tech_stack.frameworks:
        print(f"  Frameworks: {', '.join(profile.tech_stack.frameworks)}")
    if profile.tech_stack.databases:
        print(f"  Databases: {', '.join(profile.tech_stack.databases)}")

    # Test coverage
    print(f"\n{profile.test_coverage.to_compact_str()}")
    print(f"  Test files: {profile.test_coverage.test_files}")
    print(f"  Source files: {profile.test_coverage.source_files}")

    # Quality tools
    print("\nQuality Tools:")
    print(f"  Linter: {'✓' if profile.has_linter else '✗'}")
    print(f"  Formatter: {'✓' if profile.has_formatter else '✗'}")

    # Warnings
    if profile.warnings:
        print("\n⚠️  Warnings:")
        for warning in profile.warnings:
            print(f"  • {warning}")

    # Critical files
    if profile.critical_files:
        print(f"\nCritical Files ({len(profile.critical_files)}):")
        for cf in profile.critical_files[:5]:
            print(f"  • {cf.path} - {cf.reason}")

    # Context string (what would be injected)
    print("\nContext String (for injection):")
    print(f"  {profile.to_context_str()}")


if __name__ == "__main__":
    main()
