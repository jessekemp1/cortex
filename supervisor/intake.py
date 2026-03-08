"""
Work intake -- discovers and creates WorkItems from multiple sources.

Sources:
  - GOALS.md immediate actions and priority sections
  - Cortex taskboard (~/.cortex/taskboard.json)
  - CLI freetext input
  - Cortex recommendation engine
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .models import WorkItem, WorkItemPriority

log = logging.getLogger(__name__)

# Directory containing this file: cortex/supervisor/
_THIS_DIR = Path(__file__).resolve().parent


def _find_repo_root() -> Path:
    """Walk up from this module's directory to find the monorepo root (.git dir)."""
    current = _THIS_DIR
    for _ in range(10):  # safety limit
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fall back to cwd if we can't find a .git directory
    return Path.cwd()


# Keywords that map to task_type
_TYPE_KEYWORDS: Dict[str, list[str]] = {
    # Opus-tier task types (high complexity)
    "architecture": ["architect", "architecture", "design system", "redesign", "migrate"],
    "security": ["security", "vulnerability", "cve", "auth", "encryption", "xss", "injection"],
    "planning": ["plan", "spec", "specification", "rfc", "proposal", "strategy"],
    # Sonnet-tier task types (medium complexity)
    "test": ["test", "tests", "testing", "coverage", "assert"],
    "fix": ["fix", "bug", "broken", "error", "crash", "regression"],
    "research": ["research", "investigate", "explore", "spike", "evaluate"],
    "refactor": ["refactor", "clean", "simplify", "extract", "rename"],
    "review": ["review", "audit", "check", "verify", "validate"],
    "feature": ["add", "implement", "create", "build", "wire", "integrate"],
    # Haiku-tier task types (low complexity)
    "deploy": ["deploy", "ship", "release", "production", "merge"],
    "docs": ["doc", "docs", "document", "readme", "guide"],
    "classify": ["classify", "triage", "categorize", "tag", "label", "sort"],
}

_TASKBOARD_PATH = Path.home() / ".cortex" / "taskboard.json"

_PRIORITY_MAP: Dict[str, WorkItemPriority] = {
    "critical": WorkItemPriority.CRITICAL,
    "high": WorkItemPriority.HIGH,
    "medium": WorkItemPriority.MEDIUM,
    "low": WorkItemPriority.LOW,
}

_GOALS_PRIORITY_MAP: Dict[str, WorkItemPriority] = {
    "high": WorkItemPriority.HIGH,
    "medium": WorkItemPriority.MEDIUM,
    "low": WorkItemPriority.LOW,
}

_PRIORITY_SCORE: Dict[WorkItemPriority, int] = {
    WorkItemPriority.CRITICAL: 4,
    WorkItemPriority.HIGH: 3,
    WorkItemPriority.MEDIUM: 2,
    WorkItemPriority.LOW: 1,
}


def _infer_task_type(text: str) -> str:
    """Infer task type from description keywords."""
    lower = text.lower()
    for task_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return task_type
    return "task"


def _infer_project(text: str, section_header: str = "") -> str:
    """Infer project name from text or section header."""
    combined = f"{section_header} {text}".lower()
    projects = ["vortex", "cortex", "winfield", "pupil", "alpha_arena", "dj-copilot"]
    for project in projects:
        if project.replace("_", " ") in combined or project in combined:
            return project
    return ""


def _make_id() -> str:
    return f"wi_{uuid.uuid4().hex[:12]}"


def _similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two descriptions."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))


class WorkIntake:
    """Converts work from multiple sources into WorkItems for the supervisor.

    Discovers actionable work from GOALS.md, the Cortex taskboard,
    CLI input, and the Cortex recommendation engine.
    """

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is not None:
            self.root_dir = root_dir
        else:
            env_root = os.environ.get("CORTEX_ROOT_DIR")
            self.root_dir = Path(env_root) if env_root else _find_repo_root()

    def from_cli(
        self,
        task_description: str,
        project: Optional[str] = None,
        priority: str = "medium",
    ) -> WorkItem:
        """Create a WorkItem from a CLI command.

        Parses the description to infer task_type from keywords,
        generates a unique id, and sets source='cli'.
        """
        return WorkItem(
            id=_make_id(),
            source="cli",
            task_type=_infer_task_type(task_description),
            description=task_description,
            project=project or _infer_project(task_description),
            priority=_PRIORITY_MAP.get(priority.lower(), WorkItemPriority.MEDIUM),
            confidence=0.9,
        )

    def from_goals(self, goals_path: Optional[Path] = None) -> List[WorkItem]:
        """Parse GOALS.md and create WorkItems from active priorities.

        Reads GOALS.md (default: root_dir/GOALS.md) and extracts work items
        from priority sections (High/Medium/Low) and actionable sections
        (Immediate Actions, Next Phase, This Week).

        Priority mapping:
          - High Priority → WorkItemPriority.HIGH
          - Medium Priority → WorkItemPriority.MEDIUM
          - Low Priority → WorkItemPriority.LOW
          - Immediate Actions → WorkItemPriority.HIGH (always urgent)
        """
        if goals_path is None:
            goals_path = self.root_dir / "GOALS.md"
        elif isinstance(goals_path, str):
            goals_path = Path(goals_path)

        if not goals_path.exists():
            log.warning("GOALS.md not found at %s", goals_path)
            return []

        text = goals_path.read_text(encoding="utf-8")
        items: List[WorkItem] = []
        in_actionable_section = False
        in_priority_section: Optional[str] = None  # "high", "medium", or "low"
        current_header = ""

        actionable_level = 0  # heading depth that triggered actionable mode
        priority_level = 0

        for line in text.splitlines():
            # Detect section headers
            hm = re.match(r"^(#{1,4})\s+", line)
            if hm:
                level = len(hm.group(1))
                header_lower = line.lower()
                current_header = line.lstrip("#").strip()

                # Check for actionable sections (Immediate Actions, etc.)
                if any(
                    kw in header_lower for kw in ["immediate action", "next phase", "this week"]
                ):
                    in_actionable_section = True
                    actionable_level = level
                elif level <= actionable_level:
                    # Higher or same level header exits actionable section
                    in_actionable_section = False
                    actionable_level = 0
                # Sub-headers within actionable section stay actionable

                # Check for priority sections (High Priority, Medium Priority, etc.)
                if "high priority" in header_lower:
                    in_priority_section = "high"
                    priority_level = level
                elif "medium priority" in header_lower:
                    in_priority_section = "medium"
                    priority_level = level
                elif "low priority" in header_lower:
                    in_priority_section = "low"
                    priority_level = level
                elif level <= priority_level and in_priority_section:
                    in_priority_section = None
                    priority_level = 0

                continue

            if not in_actionable_section and not in_priority_section:
                continue

            # Match unchecked checkboxes, plain bullets, or numbered items
            m = re.match(r"^\s*(?:-\s*\[[ ]\]\s*|-\s+|\d+[.)]\s+)(.+)$", line)
            if not m:
                continue

            description = m.group(1).strip()
            if not description:
                continue

            # Determine priority based on which section we're in
            if in_priority_section:
                priority = _GOALS_PRIORITY_MAP.get(in_priority_section, WorkItemPriority.MEDIUM)
            else:
                # Immediate actions are always HIGH
                priority = WorkItemPriority.HIGH

            items.append(
                WorkItem(
                    id=_make_id(),
                    source="goals",
                    task_type=_infer_task_type(description),
                    description=description,
                    project=_infer_project(description, current_header),
                    priority=priority,
                    confidence=0.7,
                )
            )

        log.info("Parsed %d work items from GOALS.md", len(items))
        return items

    def from_taskboard(
        self,
        status: str = "pending",
        taskboard_path: Optional[Path] = None,
    ) -> List[WorkItem]:
        """Read taskboard items and create WorkItems.

        Reads from ~/.cortex/taskboard.json and filters by status.
        Items with status='done' are always excluded. When status is
        specified, only items matching that status are returned.
        """
        path = taskboard_path or _TASKBOARD_PATH
        if not path.exists():
            log.info("Taskboard not found at %s", path)
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to read taskboard: %s", exc)
            return []

        items: List[WorkItem] = []
        for entry in data:
            entry_status = entry.get("status", "pending")
            if entry_status == "done":
                continue
            if status and entry_status != status:
                continue

            priority_str = entry.get("priority", "medium").lower()
            priority = _PRIORITY_MAP.get(priority_str, WorkItemPriority.MEDIUM)

            items.append(
                WorkItem(
                    id=entry.get("id", _make_id()),
                    source="taskboard",
                    task_type=_infer_task_type(entry.get("title", "")),
                    description=entry.get("title", "Untitled task"),
                    project=entry.get("project", ""),
                    priority=priority,
                    confidence=0.8,
                )
            )

        log.info("Loaded %d items from taskboard (status=%s)", len(items), status)
        return items

    def from_recommendation(self, recommendation: dict) -> WorkItem:
        """Convert a single Cortex recommendation dict into a WorkItem.

        Expected fields in recommendation:
          - title or description (str)
          - priority (str, default 'medium')
          - project (str, optional)
          - confidence (float, default 0.6)
          - id (str, optional)
        """
        description = recommendation.get("title") or recommendation.get("description", "")
        priority_str = recommendation.get("priority", "medium").lower()

        return WorkItem(
            id=_make_id(),
            source="recommendation",
            task_type=_infer_task_type(description),
            description=description,
            project=recommendation.get("project", ""),
            priority=_PRIORITY_MAP.get(priority_str, WorkItemPriority.MEDIUM),
            confidence=recommendation.get("confidence", 0.6),
            metadata={"recommendation_id": recommendation.get("id", "")},
        )

    def from_batch_jobs(
        self,
        batch_dir: Optional[Path] = None,
    ) -> List[WorkItem]:
        """Scan ~/.cortex/batch/ for pending batch jobs and convert to WorkItems.

        Looks for:
          - *.json files with status='pending' or status='queued'
          - Batch queue DB entries in PENDING state

        Returns WorkItems sorted by creation time (oldest first).
        """
        batch_path = batch_dir or (Path.home() / ".cortex" / "batch")
        if not batch_path.exists():
            log.info("Batch directory not found at %s", batch_path)
            return []

        items: List[WorkItem] = []

        # 1. Scan JSON job files
        for json_file in sorted(batch_path.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Failed to read batch file %s: %s", json_file.name, exc)
                continue

            # Support both single job and list-of-jobs formats
            jobs = data if isinstance(data, list) else [data]
            for job in jobs:
                status = job.get("status", "").lower()
                if status not in ("pending", "queued", "ready"):
                    continue

                description = (
                    job.get("description")
                    or job.get("title")
                    or job.get("command")
                    or json_file.stem
                )
                priority_str = job.get("priority", "medium").lower()

                items.append(
                    WorkItem(
                        id=job.get("id", _make_id()),
                        source="batch",
                        task_type=_infer_task_type(description),
                        description=description,
                        command=job.get("command"),
                        prompt=job.get("prompt"),
                        project=job.get("project", _infer_project(description)),
                        priority=_PRIORITY_MAP.get(priority_str, WorkItemPriority.MEDIUM),
                        confidence=0.8,
                        metadata={
                            "batch_file": json_file.name,
                            **{
                                k: v
                                for k, v in job.items()
                                if k
                                not in (
                                    "id",
                                    "description",
                                    "title",
                                    "command",
                                    "prompt",
                                    "project",
                                    "priority",
                                    "status",
                                )
                            },
                        },
                    )
                )

        log.info("Found %d pending batch jobs in %s", len(items), batch_path)
        return items

    def from_recommendations_api(self) -> List[WorkItem]:
        """Query the Cortex bridge for recommendations and convert to WorkItems.

        Requires httpx. Falls back to empty list if bridge is unavailable.
        """
        try:
            import httpx
        except ImportError:
            log.warning("httpx not installed; skipping recommendations API")
            return []

        items: List[WorkItem] = []
        try:
            resp = httpx.get(
                "http://localhost:8765/intelligence/recommendations",
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, OSError) as exc:
            log.warning("Failed to fetch recommendations from bridge: %s", exc)
            return []

        recs = data if isinstance(data, list) else data.get("recommendations", [])
        for rec in recs:
            if rec.get("title") or rec.get("description"):
                items.append(self.from_recommendation(rec))

        log.info("Fetched %d recommendations from bridge", len(items))
        return items

    def discover_all(self, goals_path: Optional[Path] = None) -> List[WorkItem]:
        """Discover work from ALL sources, deduplicated and priority-sorted.

        Collects from: goals, taskboard, recommendations API.
        Deduplicates by description similarity (threshold 0.7).
        Sorts by priority_score descending.
        """
        all_items: List[WorkItem] = []

        # Goals
        all_items.extend(self.from_goals(goals_path))

        # Taskboard (all non-done statuses)
        all_items.extend(self.from_taskboard(status=""))

        # Batch jobs from ~/.cortex/batch/
        all_items.extend(self.from_batch_jobs())

        # Recommendations (best-effort, don't block on failure)
        all_items.extend(self.from_recommendations_api())

        # Deduplicate by description similarity
        deduplicated: List[WorkItem] = []
        for item in all_items:
            is_dup = any(
                _similarity(item.description, existing.description) >= 0.7
                for existing in deduplicated
            )
            if not is_dup:
                deduplicated.append(item)

        # Sort by priority_score descending (uses WorkItem.priority_score property)
        deduplicated.sort(key=lambda wi: wi.priority_score, reverse=True)

        log.info(
            "Discovered %d items (%d after dedup)",
            len(all_items),
            len(deduplicated),
        )
        return deduplicated
