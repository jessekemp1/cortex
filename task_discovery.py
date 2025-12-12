"""Task discovery from tasks.yaml files"""

import sys
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


def get_all_tasks(root_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Get all tasks from all projects.

    Args:
        root_dir: Root directory to search (defaults to /Users/jesse.kemp/Dev)

    Returns:
        List of all task dictionaries
    """
    if discover_tasks:
        # Use the discovery script if available
        return discover_tasks(root_dir)
    else:
        # Fallback: manual discovery
        if root_dir is None:
            root_dir = Path("/Users/jesse.kemp/Dev")

        all_tasks = []
        for tasks_file in root_dir.rglob("tasks.yaml"):
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
