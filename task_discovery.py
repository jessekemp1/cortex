"""Task discovery from tasks.yaml files"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add scripts directory to path for discover_tasks
scripts_dir = Path(__file__).parent.parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    from discover_tasks import discover_tasks
except ImportError:
    discover_tasks = None


# Cache configuration
CACHE_FILE = Path.home() / ".cache" / "cortex" / "task_discovery_cache.json"
CACHE_TTL_SECONDS = 300  # 5 minutes


def _load_cache_from_disk() -> Optional[List[Dict[str, Any]]]:
    """Load task cache from disk if valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)

        cache_time = datetime.fromisoformat(data.get("timestamp", ""))
        age_seconds = (datetime.now() - cache_time).total_seconds()

        if age_seconds < CACHE_TTL_SECONDS:
            return data.get("tasks", [])
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        pass

    return None


def _save_cache_to_disk(tasks: List[Dict[str, Any]]) -> None:
    """Save task cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {"timestamp": datetime.now().isoformat(), "tasks": tasks}

        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except (OSError, TypeError):
        # Ignore cache save failures
        pass


def _discover_tasks_uncached(root_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Discover tasks without using cache."""
    if root_dir is None:
        root_dir = Path("/Users/jesse.kemp/Dev")

    # Use efficient directory walking that excludes slow directories
    all_tasks = []

    # Directories to skip (these are huge and never contain tasks.yaml)
    skip_dirs = {
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "__pycache__",
        ".git",
        ".idea",
        ".vscode",
        "dist",
        "build",
        ".cache",
        ".tox",
        ".pytest_cache",
        "vendor",
        "target",
        "coverage",
        "htmlcov",
        "site-packages",
        "lib",
        "lib64",
    }

    def walk_filtered(path: Path, max_depth: int = 3, current_depth: int = 0):
        """Walk directory tree, skipping known slow directories."""
        if current_depth > max_depth:
            return

        try:
            for entry in path.iterdir():
                if entry.is_file() and entry.name == "tasks.yaml":
                    yield entry
                elif entry.is_dir() and entry.name not in skip_dirs:
                    yield from walk_filtered(entry, max_depth, current_depth + 1)
        except PermissionError:
            pass

    for tasks_file in walk_filtered(root_dir):
        try:
            with open(tasks_file, "r") as f:
                data = yaml.safe_load(f)

            project_name = tasks_file.parent.name
            tasks = data.get("tasks", [])
            for task in tasks:
                task["project"] = project_name
                task["project_path"] = str(tasks_file.parent)
                task["source_file"] = str(tasks_file)
                all_tasks.append(task)
        except Exception as e:
            print(f"Error reading {tasks_file}: {e}", file=sys.stderr)

    return all_tasks


def get_tasks_for_project(
    project_name: str, root_dir: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Get tasks for a specific project from tasks.yaml file.

    Args:
        project_name: Project name (e.g., "VortexV2", "cortex")
        root_dir: Root directory to search (defaults to /Users/jesse.kemp/Dev)

    Returns:
        List of task dictionaries
    """
    if root_dir is None:
        root_dir = Path("/Users/jesse.kemp/Dev")

    # Find project directory
    project_paths = [
        root_dir / project_name,
        root_dir / "Vortex" / project_name,  # VortexV2 is nested
    ]

    for project_path in project_paths:
        tasks_file = project_path / "tasks.yaml"
        if tasks_file.exists():
            try:
                with open(tasks_file, "r") as f:
                    data = yaml.safe_load(f)

                tasks = data.get("tasks", [])
                # Add project info to each task
                for task in tasks:
                    task["project"] = project_name
                    task["project_path"] = str(project_path)

                return tasks
            except Exception as e:
                print(f"Error reading {tasks_file}: {e}", file=sys.stderr)
                return []

    return []


def get_all_tasks(root_dir: Optional[Path] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Get all tasks from all projects.

    Args:
        root_dir: Root directory to search (defaults to /Users/jesse.kemp/Dev)
        use_cache: Whether to use cached results (default: True)

    Returns:
        List of all task dictionaries
    """
    # Check cache first
    if use_cache:
        cached_tasks = _load_cache_from_disk()
        if cached_tasks is not None:
            return cached_tasks

    # Cache miss or disabled - perform slow discovery
    tasks = _discover_tasks_uncached(root_dir)

    # Save to cache
    if use_cache:
        _save_cache_to_disk(tasks)

    return tasks
