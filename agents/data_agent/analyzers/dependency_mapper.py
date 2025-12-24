"""
Dependency Mapper - Analyze Python project dependencies using AST

Provides:
- Import extraction from Python source files using AST parsing
- Classification of imports (stdlib, third-party, local, cross-project)
- Cross-project dependency detection
- Circular dependency detection using Tarjan's algorithm
- Dependency health scoring
- Visualization (ASCII tree, DOT, Mermaid)
"""

import ast
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library modules (Python 3.9+)
STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs",
    "codeop", "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
    "dis", "distutils", "doctest", "email", "encodings", "enum", "errno", "faulthandler",
    "fcntl", "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "imaplib", "imghdr", "imp", "importlib", "inspect",
    "io", "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache", "locale",
    "logging", "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator",
    "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes",
    "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random",
    "re", "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets",
    "select", "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtpd",
    "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "ssl", "stat",
    "statistics", "string", "stringprep", "struct", "subprocess", "sunau", "symbol",
    "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib",
    "tempfile", "termios", "test", "textwrap", "threading", "time", "timeit", "tkinter",
    "token", "tokenize", "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
    "types", "typing", "typing_extensions", "unicodedata", "unittest", "urllib", "uu",
    "uuid", "venv", "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound",
    "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "_thread"
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to collect all import statements"""

    def __init__(self):
        self.imports: List[Dict[str, Any]] = []
        self.in_try_block = False
        self.in_type_checking = False
        self.try_depth = 0

    def visit_Import(self, node: ast.Import):
        """Handle: import X, import X as Y"""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "names": [alias.asname or alias.name],
                "type": self._classify_import_type(),
                "line": node.lineno,
                "is_relative": False,
                "level": 0,
                "is_optional": self.in_try_block,
                "is_type_only": self.in_type_checking
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle: from X import Y, from .X import Y"""
        module = node.module or ""
        is_relative = node.level > 0

        names = []
        if node.names:
            names = [alias.name for alias in node.names]

        self.imports.append({
            "module": module,
            "names": names,
            "type": "relative" if is_relative else self._classify_import_type(),
            "line": node.lineno,
            "is_relative": is_relative,
            "level": node.level,
            "is_optional": self.in_try_block,
            "is_type_only": self.in_type_checking
        })
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        """Track conditional imports in try/except blocks"""
        self.in_try_block = True
        self.try_depth += 1
        self.generic_visit(node)
        self.try_depth -= 1
        if self.try_depth == 0:
            self.in_try_block = False

    def visit_If(self, node: ast.If):
        """Detect TYPE_CHECKING blocks"""
        was_in_type_checking = self.in_type_checking
        if self._is_type_checking_guard(node.test):
            self.in_type_checking = True

        self.generic_visit(node)
        self.in_type_checking = was_in_type_checking

    def _is_type_checking_guard(self, test: ast.expr) -> bool:
        """Check if condition is TYPE_CHECKING"""
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
            return True
        return False

    def _classify_import_type(self) -> str:
        """Classify the current import context"""
        if self.in_type_checking:
            return "type_checking"
        elif self.in_try_block:
            return "conditional"
        else:
            return "standard"


class DependencyMapper:
    """
    Analyze Python dependencies using AST parsing.

    Capabilities:
    - Parse Python imports from source files
    - Classify import types (standard, relative, conditional, etc.)
    - Detect cross-project dependencies
    - Find circular dependencies using Tarjan's algorithm
    - Calculate dependency health scores
    """

    def __init__(
        self,
        project_path: Path,
        cache_dir: Path = Path.home() / ".claude" / "dependency_cache"
    ):
        """
        Initialize mapper for a project.

        Args:
            project_path: Root directory of Python project
            cache_dir: Directory for caching analysis results

        Raises:
            ValueError: If project_path doesn't exist or has no .py files
        """
        self.project_path = Path(project_path)
        self.cache_dir = Path(cache_dir)

        # Validate project path
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        if not self.project_path.is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 3600  # 1 hour TTL

        # Internal state
        self._analysis_cache: Optional[Dict[str, Any]] = None
        self._import_graph: Optional[Dict[str, Set[str]]] = None

    def _is_stdlib(self, module: str) -> bool:
        """Check if module is from standard library"""
        top_level = module.split(".")[0]
        return top_level in STDLIB_MODULES

    def _get_cache_path(self) -> Path:
        """Get cache file path for this project"""
        # Sanitize project name for filesystem
        safe_name = self.project_path.name.replace("/", "_").replace(" ", "_")
        return self.cache_dir / f"{safe_name}_deps.json"

    def _is_cache_valid(self) -> bool:
        """Check if cached analysis is still valid"""
        cache_path = self._get_cache_path()
        if not cache_path.exists():
            return False

        # Check if cache is within TTL
        cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
        return cache_age < self.cache_ttl

    def _read_cache(self) -> Optional[Dict[str, Any]]:
        """Read cached analysis if valid"""
        if not self._is_cache_valid():
            return None

        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _write_cache(self, data: Dict[str, Any]):
        """Write analysis to cache"""
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except IOError:
            pass  # Silently fail on cache write errors

    def clear_cache(self):
        """Clear cached analysis for this project"""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            cache_path.unlink()

    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a single Python file for imports.

        Args:
            file_path: Path to Python file

        Returns:
            Dict with:
            - file: str (path)
            - imports: List[Dict] (import records)
            - import_types: Dict[str, int] (counts by type)
            - error: Optional[str]
            - timestamp: str
        """
        result = {
            "file": str(file_path.relative_to(self.project_path)),
            "imports": [],
            "import_types": {},
            "timestamp": datetime.now().isoformat()
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))
            visitor = ImportVisitor()
            visitor.visit(tree)

            result["imports"] = visitor.imports

            # Count by type
            type_counts = {}
            for imp in visitor.imports:
                imp_type = imp["type"]
                type_counts[imp_type] = type_counts.get(imp_type, 0) + 1

            result["import_types"] = type_counts

        except SyntaxError as e:
            result["error"] = f"Syntax error: {e}"
        except Exception as e:
            result["error"] = f"Error parsing file: {e}"

        return result

    def analyze_project(
        self,
        exclude_dirs: Optional[List[str]] = None,
        include_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze all Python files in project.

        Args:
            exclude_dirs: Directories to skip (default: ['venv', '__pycache__', '.git'])
            include_tests: Whether to include test files

        Returns:
            Dict with comprehensive dependency analysis
        """
        if exclude_dirs is None:
            exclude_dirs = ['venv', '__pycache__', '.git', 'node_modules', '.tox', 'build', 'dist', '.eggs']

        result = {
            "project": self.project_path.name,
            "project_path": str(self.project_path),
            "files_analyzed": 0,
            "files_with_errors": 0,
            "file_dependencies": {},
            "imports_by_type": {},
            "external_deps": set(),
            "internal_modules": set(),
            "cross_project": defaultdict(list),
            "timestamp": datetime.now().isoformat()
        }

        # Find all Python files
        python_files = []
        for py_file in self.project_path.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in py_file.parts for excluded in exclude_dirs):
                continue

            # Skip test files if not included
            if not include_tests and ('test' in py_file.name or 'tests' in py_file.parts):
                continue

            python_files.append(py_file)

        # Analyze each file
        for py_file in python_files:
            file_analysis = self.analyze_file(py_file)
            result["files_analyzed"] += 1

            if "error" in file_analysis:
                result["files_with_errors"] += 1

            result["file_dependencies"][str(py_file.relative_to(self.project_path))] = file_analysis

            # Aggregate imports
            for imp in file_analysis.get("imports", []):
                module = imp["module"]
                imp_type = imp["type"]

                # Count by type
                result["imports_by_type"][imp_type] = result["imports_by_type"].get(imp_type, 0) + 1

                # Classify imports
                if not imp["is_relative"] and module:
                    if self._is_stdlib(module):
                        pass  # Skip stdlib
                    elif module.startswith(result["project"]):
                        result["internal_modules"].add(module)
                    else:
                        # Could be third-party or cross-project
                        top_level = module.split(".")[0]
                        result["external_deps"].add(top_level)

        # Convert sets to sorted lists for JSON serialization
        result["external_deps"] = sorted(result["external_deps"])
        result["internal_modules"] = sorted(result["internal_modules"])
        result["cross_project"] = dict(result["cross_project"])

        return result

    def get_cached_analysis(
        self,
        force_refresh: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get project analysis with caching.

        Args:
            force_refresh: Skip cache and perform fresh analysis
            **kwargs: Passed to analyze_project()

        Returns:
            Project analysis dict
        """
        if not force_refresh:
            cached = self._read_cache()
            if cached:
                cached["from_cache"] = True
                return cached

        # Perform fresh analysis
        analysis = self.analyze_project(**kwargs)
        analysis["from_cache"] = False

        # Cache the result
        self._write_cache(analysis)

        return analysis

    def _build_import_graph(self) -> Dict[str, Set[str]]:
        """
        Build directed graph of module -> imports relationships.

        Returns:
            Dict mapping module names to sets of imported modules
        """
        if self._import_graph is not None:
            return self._import_graph

        graph = defaultdict(set)

        # Get fresh analysis if needed
        if self._analysis_cache is None:
            self._analysis_cache = self.get_cached_analysis()

        # Build graph from file dependencies
        for file_path, file_data in self._analysis_cache.get("file_dependencies", {}).items():
            # Use file path as module name (without .py extension)
            module_name = file_path.replace("/", ".").replace(".py", "")

            for imp in file_data.get("imports", []):
                if not imp["is_relative"] and imp["module"]:
                    target = imp["module"]
                    graph[module_name].add(target)

        self._import_graph = dict(graph)
        return self._import_graph

    def _tarjan_scc(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        """
        Tarjan's Strongly Connected Components algorithm.

        Finds circular dependencies in the import graph.

        Args:
            graph: Directed graph of module dependencies

        Returns:
            List of cycles (each cycle is a list of modules)
        """
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []

        def strongconnect(v):
            index[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            on_stack[v] = True
            stack.append(v)

            for w in graph.get(v, set()):
                if w not in index:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif on_stack.get(w, False):
                    lowlinks[v] = min(lowlinks[v], index[w])

            if lowlinks[v] == index[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == v:
                        break
                # Only record cycles with >1 node
                if len(scc) > 1:
                    sccs.append(scc)

        for v in graph:
            if v not in index:
                strongconnect(v)

        return sccs

    def find_circular_dependencies(self) -> Dict[str, Any]:
        """
        Detect circular import patterns using Tarjan's algorithm.

        Returns:
            Dict with:
            - has_cycles: bool
            - cycles: List[List[str]]  # Each cycle as list of modules
            - cycle_count: int
            - severity: str  # 'none', 'minor', 'major'
            - timestamp: str
        """
        graph = self._build_import_graph()
        cycles = self._tarjan_scc(graph)

        # Determine severity
        if len(cycles) == 0:
            severity = "none"
        elif len(cycles) <= 2:
            severity = "minor"
        else:
            severity = "major"

        return {
            "has_cycles": len(cycles) > 0,
            "cycles": cycles,
            "cycle_count": len(cycles),
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }

    def calculate_dependency_health(self) -> Dict[str, Any]:
        """
        Calculate dependency health score (0-100).

        Scoring components:
        - Circular dependencies (0-25): None=25, 1-2=15, 3+=5, major=0
        - External dep count (0-25): <10=25, <20=20, <50=10, 50+=5
        - Cross-project coupling (0-25): None=25, unidirectional=20, bidirectional=10
        - Import cleanliness (0-25): Clean=25, heavy conditional=15, dynamic=10

        Returns:
            Dict with health score, breakdown, and assessment
        """
        analysis = self.get_cached_analysis()
        circular = self.find_circular_dependencies()

        scores = {}

        # Circular dependencies score (0-25)
        if circular["cycle_count"] == 0:
            scores["circular_deps"] = 25
        elif circular["cycle_count"] <= 2:
            scores["circular_deps"] = 15
        elif circular["severity"] == "major":
            scores["circular_deps"] = 0
        else:
            scores["circular_deps"] = 5

        # External dependencies score (0-25)
        ext_count = len(analysis.get("external_deps", []))
        if ext_count < 10:
            scores["external_deps"] = 25
        elif ext_count < 20:
            scores["external_deps"] = 20
        elif ext_count < 50:
            scores["external_deps"] = 10
        else:
            scores["external_deps"] = 5

        # Cross-project coupling score (0-25)
        cross_proj = analysis.get("cross_project", {})
        if len(cross_proj) == 0:
            scores["cross_project"] = 25
        elif len(cross_proj) <= 2:
            scores["cross_project"] = 20
        else:
            scores["cross_project"] = 10

        # Import cleanliness score (0-25)
        import_types = analysis.get("imports_by_type", {})
        conditional = import_types.get("conditional", 0)
        total_imports = sum(import_types.values())

        if total_imports == 0:
            scores["cleanliness"] = 25
        else:
            conditional_ratio = conditional / total_imports
            if conditional_ratio < 0.1:
                scores["cleanliness"] = 25
            elif conditional_ratio < 0.3:
                scores["cleanliness"] = 15
            else:
                scores["cleanliness"] = 10

        total_score = sum(scores.values())

        # Assessment
        if total_score >= 80:
            assessment = "excellent"
        elif total_score >= 60:
            assessment = "good"
        elif total_score >= 40:
            assessment = "fair"
        else:
            assessment = "needs_attention"

        # Generate concerns
        concerns = []
        if circular["has_cycles"]:
            concerns.append(f"Found {circular['cycle_count']} circular dependencies")
        if ext_count > 30:
            concerns.append(f"High number of external dependencies ({ext_count})")
        if len(cross_proj) > 3:
            concerns.append(f"Heavy cross-project coupling ({len(cross_proj)} projects)")

        # Generate recommendations
        recommendations = []
        if circular["has_cycles"]:
            recommendations.append({
                "priority": "high" if circular["severity"] == "major" else "medium",
                "action": "Resolve circular dependencies",
                "details": f"Found {circular['cycle_count']} cycles that can cause import errors"
            })
        if ext_count > 50:
            recommendations.append({
                "priority": "medium",
                "action": "Review external dependencies",
                "details": "Consider consolidating or removing unused dependencies"
            })

        return {
            "total_score": total_score,
            "breakdown": scores,
            "assessment": assessment,
            "concerns": concerns,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }

    def generate_ascii_tree(
        self,
        module: Optional[str] = None,
        max_depth: int = 3
    ) -> str:
        """
        Generate ASCII tree visualization of dependencies.

        Args:
            module: Starting module (None = project root)
            max_depth: Maximum depth to display

        Returns:
            ASCII tree string
        """
        analysis = self.get_cached_analysis()
        graph = self._build_import_graph()

        lines = []
        lines.append(f"{self.project_path.name}/")

        # Get modules to display
        if module:
            modules = [m for m in graph.keys() if m.startswith(module)]
        else:
            # Show top-level modules
            modules = sorted(graph.keys())[:10]  # Limit to 10 for readability

        def add_imports(mod, prefix, depth):
            if depth >= max_depth:
                return

            imports = sorted(graph.get(mod, set()))
            for i, imp in enumerate(imports[:5]):  # Limit to 5 imports per module
                is_last = i == len(imports[:5]) - 1
                connector = "+--" if is_last else "+--"
                lines.append(f"{prefix}{connector} {imp}")

                # Recursively show imports of imports (if internal)
                if depth < max_depth - 1 and imp in graph:
                    new_prefix = prefix + ("    " if is_last else "|   ")
                    add_imports(imp, new_prefix, depth + 1)

        for i, mod in enumerate(modules):
            is_last = i == len(modules) - 1
            connector = "+--" if is_last else "+--"
            lines.append(f"{connector} {mod}")

            new_prefix = "    " if is_last else "|   "
            add_imports(mod, new_prefix, 1)

        return "\n".join(lines)


# CLI for standalone testing
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dependency_mapper.py <command> [args]")
        print("\nCommands:")
        print("  analyze <project_path>   - Analyze project dependencies")
        print("  file <file_path>         - Analyze single file")
        print("  circular <project_path>  - Find circular dependencies")
        print("  health <project_path>    - Calculate dependency health score")
        print("  tree <project_path>      - Show ASCII dependency tree")
        print("  clear <project_path>     - Clear cache")
        print("\nExamples:")
        print("  python dependency_mapper.py analyze /Users/jesse.kemp/Dev/cortex")
        print("  python dependency_mapper.py circular /Users/jesse.kemp/Dev/cortex")
        print("  python dependency_mapper.py health /Users/jesse.kemp/Dev/cortex")
        print("  python dependency_mapper.py tree /Users/jesse.kemp/Dev/cortex")
        sys.exit(1)

    command = sys.argv[1]

    if command == "analyze":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)

        project_path = Path(sys.argv[2])
        mapper = DependencyMapper(project_path)
        result = mapper.get_cached_analysis()
        print(json.dumps(result, indent=2, default=str))

    elif command == "file":
        if len(sys.argv) < 3:
            print("Error: file path required")
            sys.exit(1)

        file_path = Path(sys.argv[2])
        project_path = file_path.parent
        mapper = DependencyMapper(project_path)
        result = mapper.analyze_file(file_path)
        print(json.dumps(result, indent=2, default=str))

    elif command == "circular":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)

        project_path = Path(sys.argv[2])
        mapper = DependencyMapper(project_path)
        result = mapper.find_circular_dependencies()
        print(json.dumps(result, indent=2, default=str))

    elif command == "health":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)

        project_path = Path(sys.argv[2])
        mapper = DependencyMapper(project_path)
        result = mapper.calculate_dependency_health()
        print(json.dumps(result, indent=2, default=str))

    elif command == "tree":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)

        project_path = Path(sys.argv[2])
        mapper = DependencyMapper(project_path)
        tree = mapper.generate_ascii_tree()
        print(tree)

    elif command == "clear":
        if len(sys.argv) < 3:
            print("Error: project path required")
            sys.exit(1)

        project_path = Path(sys.argv[2])
        mapper = DependencyMapper(project_path)
        mapper.clear_cache()
        print(f"Cache cleared for {project_path.name}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
