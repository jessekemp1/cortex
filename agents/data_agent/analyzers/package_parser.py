"""
Package Parser - Parse package manager files to identify declared dependencies

Supports:
- requirements.txt (pip)
- pyproject.toml (Poetry/PEP 621)
- package.json (Node.js)
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

# Try to import tomli for TOML parsing (Python 3.11+ has tomllib built-in)
try:
    import tomli
except ImportError:
    try:
        # Python 3.11+ has tomllib built-in
        import tomllib as tomli
    except ImportError:
        tomli = None


class PackageParser:
    """
    Parse package manager files to extract declared dependencies.
    """

    def __init__(self, project_path: Path):
        """
        Initialize parser for a project.

        Args:
            project_path: Root directory of project
        """
        self.project_path = Path(project_path)

    def parse_requirements_txt(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Parse requirements.txt file.

        Args:
            file_path: Path to requirements.txt (default: project_path/requirements.txt)

        Returns:
            Dict with:
            - packages: List[Dict] with name, version, extras
            - file: str (path)
            - error: Optional[str]
        """
        if file_path is None:
            file_path = self.project_path / "requirements.txt"

        result = {
            "file": (str(file_path.relative_to(self.project_path)) if file_path.exists() else None),
            "packages": [],
            "error": None,
        }

        if not file_path.exists():
            return result

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Remove inline comments
                    if "#" in line:
                        line = line[: line.index("#")].strip()

                    # Parse package spec
                    # Format: package[extras]==version
                    # Examples:
                    #   requests
                    #   requests==2.28.0
                    #   requests[security]==2.28.0
                    #   requests>=2.28.0,<3.0.0
                    #   git+https://github.com/user/repo.git@branch
                    #   file:///path/to/local/package

                    package_info = {
                        "name": None,
                        "version_spec": None,
                        "extras": None,
                        "source": None,
                        "line": line_num,
                        "raw": line,
                    }

                    # Check for VCS or file URLs
                    if line.startswith(("git+", "hg+", "svn+", "bzr+", "file://")):
                        package_info["source"] = "vcs"
                        # Extract package name from URL if possible
                        if "@" in line:
                            # git+https://...@branch#egg=package_name
                            if "#egg=" in line:
                                package_info["name"] = line.split("#egg=")[1].split("-")[0]
                            else:
                                # Try to extract from URL
                                parts = line.split("/")
                                if parts:
                                    package_info["name"] = (
                                        parts[-1].split("@")[0].replace(".git", "")
                                    )
                    else:
                        # Regular package spec
                        # Extract extras: package[extras]
                        if "[" in line and "]" in line:
                            match = re.match(r"^([^\[]+)\[([^\]]+)\](.*)$", line)
                            if match:
                                package_info["name"] = match.group(1).strip()
                                package_info["extras"] = match.group(2).strip()
                                version_part = match.group(3).strip()
                            else:
                                version_part = line
                        else:
                            version_part = line

                        # Extract name and version
                        # Split on ==, >=, <=, >, <, ~=, !=
                        version_pattern = r"(==|>=|<=|>|<|~=|!=)"
                        parts = re.split(version_pattern, version_part, 1)

                        if parts:
                            package_info["name"] = parts[0].strip()
                            if len(parts) > 1:
                                package_info["version_spec"] = "".join(parts[1:]).strip()

                    if package_info["name"]:
                        result["packages"].append(package_info)

        except Exception as e:
            result["error"] = str(e)

        return result

    def parse_pyproject_toml(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Parse pyproject.toml file (Poetry or PEP 621 format).

        Args:
            file_path: Path to pyproject.toml (default: project_path/pyproject.toml)

        Returns:
            Dict with:
            - packages: List[Dict] with name, version, extras
            - dev_packages: List[Dict] (development dependencies)
            - file: str (path)
            - error: Optional[str]
        """
        if file_path is None:
            file_path = self.project_path / "pyproject.toml"

        result = {
            "file": (str(file_path.relative_to(self.project_path)) if file_path.exists() else None),
            "packages": [],
            "dev_packages": [],
            "error": None,
        }

        if not file_path.exists():
            return result

        if tomli is None:
            result["error"] = "tomli not available (install with: pip install tomli)"
            return result

        try:
            with open(file_path, "rb") as f:
                data = tomli.load(f)

            # PEP 621 format: [project] dependencies
            if "project" in data and "dependencies" in data["project"]:
                deps = data["project"]["dependencies"]
                for dep in deps:
                    package_info = self._parse_dependency_string(dep)
                    if package_info:
                        result["packages"].append(package_info)

                # Optional dependencies (extras)
                if "optional-dependencies" in data["project"]:
                    for extra_name, extra_deps in data["project"]["optional-dependencies"].items():
                        for dep in extra_deps:
                            package_info = self._parse_dependency_string(dep)
                            if package_info:
                                package_info["extra"] = extra_name
                                result["packages"].append(package_info)

            # Poetry format: [tool.poetry] dependencies
            elif "tool" in data and "poetry" in data["tool"]:
                poetry = data["tool"]["poetry"]

                # Main dependencies
                if "dependencies" in poetry:
                    for name, spec in poetry["dependencies"].items():
                        if name == "python":
                            continue  # Skip Python version spec

                        package_info = {
                            "name": name,
                            "version_spec": None,
                            "extras": None,
                        }

                        if isinstance(spec, str):
                            package_info["version_spec"] = spec
                        elif isinstance(spec, dict):
                            if "version" in spec:
                                package_info["version_spec"] = spec["version"]
                            if "extras" in spec:
                                package_info["extras"] = ",".join(spec["extras"])

                        result["packages"].append(package_info)

                # Dev dependencies
                if "group" in poetry and "dev" in poetry["group"]:
                    if "dependencies" in poetry["group"]["dev"]:
                        for name, spec in poetry["group"]["dev"]["dependencies"].items():
                            package_info = {
                                "name": name,
                                "version_spec": None,
                                "extras": None,
                            }

                            if isinstance(spec, str):
                                package_info["version_spec"] = spec
                            elif isinstance(spec, dict):
                                if "version" in spec:
                                    package_info["version_spec"] = spec["version"]

                            package_info["dev"] = True
                            result["dev_packages"].append(package_info)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _parse_dependency_string(self, dep_string: str) -> Optional[Dict[str, Any]]:
        """
        Parse a dependency string (PEP 508 format).

        Examples:
            requests
            requests==2.28.0
            requests[security]==2.28.0
            requests>=2.28.0,<3.0.0
        """
        package_info = {"name": None, "version_spec": None, "extras": None}

        # Extract extras: package[extras]
        if "[" in dep_string and "]" in dep_string:
            match = re.match(r"^([^\[]+)\[([^\]]+)\](.*)$", dep_string)
            if match:
                package_info["name"] = match.group(1).strip()
                package_info["extras"] = match.group(2).strip()
                version_part = match.group(3).strip()
            else:
                version_part = dep_string
        else:
            version_part = dep_string

        # Extract name and version
        # Split on version operators
        version_pattern = r"(==|>=|<=|>|<|~=|!=)"
        parts = re.split(version_pattern, version_part, 1)

        if parts:
            package_info["name"] = parts[0].strip()
            if len(parts) > 1:
                package_info["version_spec"] = "".join(parts[1:]).strip()

        return package_info if package_info["name"] else None

    def parse_package_json(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Parse package.json file (Node.js).

        Args:
            file_path: Path to package.json (default: project_path/package.json)

        Returns:
            Dict with:
            - packages: List[Dict] with name, version
            - dev_packages: List[Dict] (devDependencies)
            - file: str (path)
            - error: Optional[str]
        """
        if file_path is None:
            file_path = self.project_path / "package.json"

        result = {
            "file": (str(file_path.relative_to(self.project_path)) if file_path.exists() else None),
            "packages": [],
            "dev_packages": [],
            "error": None,
        }

        if not file_path.exists():
            return result

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Dependencies
            if "dependencies" in data:
                for name, version in data["dependencies"].items():
                    result["packages"].append({"name": name, "version_spec": version})

            # Dev dependencies
            if "devDependencies" in data:
                for name, version in data["devDependencies"].items():
                    result["dev_packages"].append(
                        {"name": name, "version_spec": version, "dev": True}
                    )

        except Exception as e:
            result["error"] = str(e)

        return result

    def get_all_declared_dependencies(self) -> Dict[str, Any]:
        """
        Parse all package manager files in project.

        Returns:
            Dict with:
            - all_packages: Set[str] (all declared package names)
            - by_file: Dict mapping file type to parsed results
            - errors: List[str]
        """
        result = {"all_packages": set(), "by_file": {}, "errors": []}

        # Try requirements.txt
        req_result = self.parse_requirements_txt()
        if req_result["file"]:
            result["by_file"]["requirements.txt"] = req_result
            for pkg in req_result["packages"]:
                if pkg["name"]:
                    result["all_packages"].add(pkg["name"].lower())
            if req_result["error"]:
                result["errors"].append(f"requirements.txt: {req_result['error']}")

        # Try pyproject.toml
        pyproject_result = self.parse_pyproject_toml()
        if pyproject_result["file"]:
            result["by_file"]["pyproject.toml"] = pyproject_result
            for pkg in pyproject_result["packages"]:
                if pkg["name"]:
                    result["all_packages"].add(pkg["name"].lower())
            for pkg in pyproject_result["dev_packages"]:
                if pkg["name"]:
                    result["all_packages"].add(pkg["name"].lower())
            if pyproject_result["error"]:
                result["errors"].append(f"pyproject.toml: {pyproject_result['error']}")

        # Try package.json
        package_json_result = self.parse_package_json()
        if package_json_result["file"]:
            result["by_file"]["package.json"] = package_json_result
            for pkg in package_json_result["packages"]:
                if pkg["name"]:
                    result["all_packages"].add(pkg["name"].lower())
            for pkg in package_json_result["dev_packages"]:
                if pkg["name"]:
                    result["all_packages"].add(pkg["name"].lower())
            if package_json_result["error"]:
                result["errors"].append(f"package.json: {package_json_result['error']}")

        result["all_packages"] = sorted(result["all_packages"])

        return result
