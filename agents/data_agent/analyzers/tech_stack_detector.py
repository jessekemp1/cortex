"""Tech Stack Detector - Enhanced detection of frameworks, libraries, and tools."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TechStackDetector:
    """Enhanced tech stack detection with version information."""

    def __init__(self, project_path: Path):
        """Initialize tech stack detector."""
        self.project_path = Path(project_path)

    def detect_tech_stack(self) -> Dict[str, Any]:
        """
        Detect comprehensive tech stack for a project.

        Returns:
            Dict with languages, frameworks, libraries, tools, and versions
        """
        stack = {
            "languages": set(),
            "frameworks": set(),
            "libraries": set(),
            "databases": set(),
            "tools": set(),
            "version_info": {},
            "detection_method": {},
        }

        # Detect Python stack
        python_stack = self._detect_python_stack()
        stack["languages"].update(python_stack.get("languages", []))
        stack["frameworks"].update(python_stack.get("frameworks", []))
        stack["libraries"].update(python_stack.get("libraries", []))
        stack["databases"].update(python_stack.get("databases", []))
        stack["version_info"].update(python_stack.get("version_info", {}))

        # Detect JavaScript/TypeScript stack
        js_stack = self._detect_javascript_stack()
        stack["languages"].update(js_stack.get("languages", []))
        stack["frameworks"].update(js_stack.get("frameworks", []))
        stack["libraries"].update(js_stack.get("libraries", []))
        stack["version_info"].update(js_stack.get("version_info", {}))

        # Detect other languages
        other_stack = self._detect_other_languages()
        stack["languages"].update(other_stack.get("languages", []))
        stack["frameworks"].update(other_stack.get("frameworks", []))
        stack["version_info"].update(other_stack.get("version_info", {}))

        # Detect databases
        databases = self._detect_databases()
        stack["databases"].update(databases)

        # Detect tools
        tools = self._detect_tools()
        stack["tools"].update(tools)

        # Convert sets to lists for JSON serialization
        return {
            "languages": sorted(list(stack["languages"])),
            "frameworks": sorted(list(stack["frameworks"])),
            "libraries": sorted(list(stack["libraries"])),
            "databases": sorted(list(stack["databases"])),
            "tools": sorted(list(stack["tools"])),
            "version_info": stack["version_info"],
        }

    def _detect_python_stack(self) -> Dict[str, Any]:
        """Detect Python tech stack."""
        stack = {
            "languages": [],
            "frameworks": [],
            "libraries": [],
            "databases": [],
            "version_info": {},
        }

        # Check for Python
        if (
            (self.project_path / "requirements.txt").exists()
            or (self.project_path / "pyproject.toml").exists()
            or (self.project_path / "setup.py").exists()
        ):
            stack["languages"].append("Python")

            # Detect Python version
            python_version = self._detect_python_version()
            if python_version:
                stack["version_info"]["Python"] = python_version

            # Read dependencies
            deps = self._read_python_dependencies()

            # Detect frameworks
            framework_patterns = {
                "FastAPI": ["fastapi"],
                "Flask": ["flask"],
                "Django": ["django"],
                "Streamlit": ["streamlit"],
                "PyTorch": ["torch", "pytorch"],
                "TensorFlow": ["tensorflow"],
            }

            for framework, patterns in framework_patterns.items():
                if any(pattern in deps for pattern in patterns):
                    stack["frameworks"].append(framework)

            # Detect ML libraries
            ml_libraries = ["scikit-learn", "numpy", "pandas", "matplotlib", "seaborn"]
            for lib in ml_libraries:
                if lib in deps:
                    stack["libraries"].append(lib)

            # Detect database libraries
            db_patterns = {
                "SQLAlchemy": ["sqlalchemy"],
                "Psycopg2": ["psycopg2", "psycopg2-binary"],
                "Redis": ["redis"],
                "MongoDB": ["pymongo", "motor"],
            }

            for db, patterns in db_patterns.items():
                if any(pattern in deps for pattern in patterns):
                    stack["databases"].append(db)

        return stack

    def _detect_javascript_stack(self) -> Dict[str, Any]:
        """Detect JavaScript/TypeScript tech stack."""
        stack = {
            "languages": [],
            "frameworks": [],
            "libraries": [],
            "version_info": {},
        }

        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }

                # Detect language
                if "typescript" in deps:
                    stack["languages"].append("TypeScript")
                    # Get TypeScript version
                    ts_version = deps.get("typescript", "").replace("^", "").replace("~", "")
                    if ts_version:
                        stack["version_info"]["TypeScript"] = ts_version
                else:
                    stack["languages"].append("JavaScript")

                # Detect frameworks
                framework_patterns = {
                    "React": ["react"],
                    "Next.js": ["next"],
                    "Vue": ["vue"],
                    "Angular": ["@angular/core"],
                    "Express": ["express"],
                    "NestJS": ["@nestjs/core"],
                }

                for framework, patterns in framework_patterns.items():
                    if any(pattern in deps for pattern in patterns):
                        stack["frameworks"].append(framework)

                # Detect Node version
                if "engines" in data and "node" in data["engines"]:
                    node_version = data["engines"]["node"]
                    stack["version_info"]["Node.js"] = node_version

            except Exception as e:
                logger.warning(f"Failed to parse package.json: {e}")

        return stack

    def _detect_other_languages(self) -> Dict[str, Any]:
        """Detect other programming languages."""
        stack = {
            "languages": [],
            "frameworks": [],
            "version_info": {},
        }

        # Go
        if (self.project_path / "go.mod").exists():
            stack["languages"].append("Go")
            go_version = self._detect_go_version()
            if go_version:
                stack["version_info"]["Go"] = go_version

        # Rust
        if (self.project_path / "Cargo.toml").exists():
            stack["languages"].append("Rust")

        # Java
        if (self.project_path / "pom.xml").exists() or (
            self.project_path / "build.gradle"
        ).exists():
            stack["languages"].append("Java")

        # C/C++
        if any(self.project_path.glob("*.cpp")) or any(self.project_path.glob("*.c")):
            stack["languages"].append("C++" if any(self.project_path.glob("*.cpp")) else "C")

        return stack

    def _detect_databases(self) -> Set[str]:
        """Detect database usage from configuration files."""
        databases = set()

        # Check for database config files
        config_files = [
            self.project_path / ".env",
            self.project_path / "config.py",
            self.project_path / "settings.py",
            self.project_path / "docker-compose.yml",
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    content = config_file.read_text().lower()

                    db_patterns = {
                        "PostgreSQL": ["postgres", "postgresql", "psql"],
                        "MySQL": ["mysql", "mariadb"],
                        "MongoDB": ["mongodb", "mongo"],
                        "Redis": ["redis"],
                        "SQLite": ["sqlite"],
                        "DuckDB": ["duckdb"],
                    }

                    for db, patterns in db_patterns.items():
                        if any(pattern in content for pattern in patterns):
                            databases.add(db)
                except Exception:
                    pass

        return databases

    def _detect_tools(self) -> Set[str]:
        """Detect development tools and infrastructure."""
        tools = set()

        # CI/CD
        if (self.project_path / ".github").exists():
            tools.add("GitHub Actions")
        if (self.project_path / ".gitlab-ci.yml").exists():
            tools.add("GitLab CI")
        if (self.project_path / ".circleci").exists():
            tools.add("CircleCI")

        # Containerization
        if (self.project_path / "Dockerfile").exists():
            tools.add("Docker")
        if (self.project_path / "docker-compose.yml").exists():
            tools.add("Docker Compose")
        if (self.project_path / "Kubernetes").exists() or (self.project_path / "k8s").exists():
            tools.add("Kubernetes")

        # Testing
        if (self.project_path / "pytest.ini").exists() or (self.project_path / "tests").exists():
            tools.add("pytest")
        if (self.project_path / "jest.config.js").exists():
            tools.add("Jest")

        # Linting/Formatting
        if (self.project_path / ".ruff.toml").exists() or (
            self.project_path / "ruff.toml"
        ).exists():
            tools.add("Ruff")
        if (self.project_path / ".eslintrc").exists():
            tools.add("ESLint")
        if (self.project_path / ".prettierrc").exists():
            tools.add("Prettier")

        return tools

    def _read_python_dependencies(self) -> List[str]:
        """Read Python dependencies from various files."""
        deps = []

        # requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name (before == or @)
                        pkg = (
                            line.split("==")[0].split("@")[0].split(">=")[0].split("<=")[0].strip()
                        )
                        if pkg:
                            deps.append(pkg.lower())
            except Exception:
                pass

        # pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli

                data = tomli.loads(pyproject.read_text())
                project_deps = data.get("project", {}).get("dependencies", [])
                for dep in project_deps:
                    pkg = dep.split(">=")[0].split("==")[0].split("@")[0].strip()
                    if pkg:
                        deps.append(pkg.lower())
            except Exception:
                pass

        return deps

    def _detect_python_version(self) -> Optional[str]:
        """Detect Python version from various sources."""
        # Check .python-version
        py_version_file = self.project_path / ".python-version"
        if py_version_file.exists():
            return py_version_file.read_text().strip()

        # Check runtime.txt (for platforms like Heroku)
        runtime_file = self.project_path / "runtime.txt"
        if runtime_file.exists():
            content = runtime_file.read_text()
            match = re.search(r"python-(\d+\.\d+)", content)
            if match:
                return match.group(1)

        # Check pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli

                data = tomli.loads(pyproject.read_text())
                requires = data.get("project", {}).get("requires-python", "")
                if requires:
                    match = re.search(r">=(\d+\.\d+)", requires)
                    if match:
                        return match.group(1)
            except Exception:
                pass

        return None

    def _detect_go_version(self) -> Optional[str]:
        """Detect Go version from go.mod."""
        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text()
                match = re.search(r"go\s+(\d+\.\d+)", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None
