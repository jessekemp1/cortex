"""
Strategic Document Parser for Orchestration Intelligence.

Reads GOALS.md and PROJECT_STATUS.md to provide accurate metrics
for anomaly detection instead of relying on inferred/hardcoded values.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


def parse_project_status(root_dir: Path) -> Dict[str, Any]:
    """
    Parse PROJECT_STATUS.md to extract project metrics.

    Args:
        root_dir: Root directory containing PROJECT_STATUS.md

    Returns:
        Dictionary with:
        - active_projects: Number of active projects
        - backlog_projects: Number of backlog projects
        - inactive_projects: Number of inactive projects
        - total_projects: Total number of projects
        - active_project_names: List of active project names
    """
    project_status_path = root_dir / "PROJECT_STATUS.md"

    if not project_status_path.exists():
        # Fallback to default values if file doesn't exist
        return {
            "active_projects": 26,  # Conservative estimate
            "backlog_projects": 0,
            "inactive_projects": 0,
            "total_projects": 30,
            "active_project_names": [],
            "source": "default"
        }

    content = project_status_path.read_text()

    # Extract statistics from the table
    # Look for: | Active | 5 | 15% |
    active_match = re.search(r'\|\s*Active\s*\|\s*(\d+)\s*\|', content)
    backlog_match = re.search(r'\|\s*Backlog\s*\|\s*(\d+)\s*\|', content)
    inactive_match = re.search(r'\|\s*Inactive\s*\|\s*(\d+)\s*\|', content)
    total_match = re.search(r'\|\s*\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|', content)

    active_projects = int(active_match.group(1)) if active_match else 0
    backlog_projects = int(backlog_match.group(1)) if backlog_match else 0
    inactive_projects = int(inactive_match.group(1)) if inactive_match else 0
    total_projects = int(total_match.group(1)) if total_match else (active_projects + backlog_projects + inactive_projects)

    # Extract active project names
    # Look for numbered list under "## 🟢 ACTIVE"
    active_section_match = re.search(
        r'## 🟢 ACTIVE.*?\n(.*?)(?=##|\Z)',
        content,
        re.DOTALL
    )

    active_project_names = []
    if active_section_match:
        active_section = active_section_match.group(1)
        # Extract project names from lines like: "1. **cortex** - Description"
        for match in re.finditer(r'\d+\.\s+\*\*([^*]+)\*\*', active_section):
            active_project_names.append(match.group(1).strip())

    return {
        "active_projects": active_projects,
        "backlog_projects": backlog_projects,
        "inactive_projects": inactive_projects,
        "total_projects": total_projects,
        "active_project_names": active_project_names,
        "source": "PROJECT_STATUS.md"
    }


def parse_goals(root_dir: Path) -> Dict[str, Any]:
    """
    Parse GOALS.md to extract goal metrics.

    Args:
        root_dir: Root directory containing GOALS.md

    Returns:
        Dictionary with:
        - total_goals: Number of strategic goals
        - in_progress_goals: Number of goals in progress
        - pending_goals: Number of pending goals
        - completed_goals: Number of completed goals
        - goal_titles: List of goal titles
    """
    goals_path = root_dir / "GOALS.md"

    if not goals_path.exists():
        # Fallback to default values
        return {
            "total_goals": 0,
            "in_progress_goals": 0,
            "pending_goals": 0,
            "completed_goals": 0,
            "goal_titles": [],
            "source": "default"
        }

    content = goals_path.read_text()

    # Extract goals from "## 🎯 Current Goals" section
    goals_section_match = re.search(
        r'## 🎯 Current Goals.*?\n(.*?)(?=^## |\Z)',
        content,
        re.DOTALL | re.MULTILINE
    )

    if not goals_section_match:
        return {
            "total_goals": 0,
            "in_progress_goals": 0,
            "pending_goals": 0,
            "completed_goals": 0,
            "goal_titles": [],
            "source": "GOALS.md (no goals found)"
        }

    goals_section = goals_section_match.group(1)

    # Count goals by status
    in_progress = len(re.findall(r'\[IN PROGRESS\]', goals_section, re.IGNORECASE))
    pending = len(re.findall(r'Status:.*?Planning', goals_section, re.IGNORECASE))
    completed = len(re.findall(r'Status:.*?Complete', goals_section, re.IGNORECASE))

    # Extract goal titles from headers like "### Goal 1: Title"
    goal_titles = []
    for match in re.finditer(r'###\s+Goal\s+\d+:\s+([^\[]+)', goals_section):
        title = match.group(1).strip()
        goal_titles.append(title)

    total_goals = len(goal_titles)

    return {
        "total_goals": total_goals,
        "in_progress_goals": in_progress,
        "pending_goals": pending,
        "completed_goals": completed,
        "goal_titles": goal_titles,
        "source": "GOALS.md"
    }


def get_strategic_context(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get complete strategic context by parsing both documents.

    Args:
        root_dir: Root directory (defaults to /Users/jesse.kemp/Dev)

    Returns:
        Combined metrics from both documents
    """
    if root_dir is None:
        root_dir = Path("/Users/jesse.kemp/Dev")

    project_metrics = parse_project_status(root_dir)
    goal_metrics = parse_goals(root_dir)

    return {
        **project_metrics,
        **goal_metrics,
        "root_dir": str(root_dir)
    }


if __name__ == "__main__":
    # Quick test
    root = Path("/Users/jesse.kemp/Dev")
    project_data = parse_project_status(root)
    goal_data = parse_goals(root)
    context = get_strategic_context(root)

    print("📊 Strategic Context")
    print("=" * 50)
    print(f"Active Projects: {context['active_projects']}")
    print(f"Total Projects: {context['total_projects']}")
    print(f"Active Names: {', '.join(context['active_project_names'][:5])}")  # Show first 5
    print()
    print(f"Strategic Goals: {context['total_goals']}")
    print(f"In Progress: {context['in_progress_goals']}")
    print(f"Pending: {context['pending_goals']}")
    print("Goal Titles:")
    for title in context['goal_titles']:
        print(f"  - {title}")
    print()
    print("Data Sources:")
    print(f"  Projects: {project_data.get('source', 'unknown')}")
    print(f"  Goals: {goal_data.get('source', 'unknown')}")
