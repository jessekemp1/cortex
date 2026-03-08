"""
Work intake -- discovers and creates WorkItems from multiple sources.

Sources:
  - GOALS.md immediate actions
  - Cortex taskboard (~/.cortex/taskboard.json)
  - CLI freetext input
  - Cortex recommendation engine
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from .models import WorkItem, WorkItemPriority

log = logging.getLogger(__name__)

# Keywords that map to task_type
_TYPE_KEYWORDS: Dict[str, list[str]] = {
    "test": ["test", "tests", "testing", "coverage", "assert"],
    "fix": ["fix", "bug", "broken", "error", "crash", "regression"],
    "deploy": ["deploy", "ship", "release", "production", "merge"],
    "research": ["research", "investigate", "explore", "spike", "evaluate"],
    "refactor": ["refactor", "clean", "simplify", "extract", "rename"],
    "feature": ["add", "implement", "create", "build", "wire", "integrate"],
    "review": ["review", "audit", "check", "verify", "validate"],
    "docs": ["doc", "docs", "document", "readme", "guide"],
}

_TASKBOARD_PATH = Path.home() / ".cortex" / "taskboard.json"
_BRIDGE_URL = "http://localhost:8765"

_PRIORITY_MAP: Dict[str, WorkItemPriority] = {
    "critical": WorkItemPriority.CRITICAL,
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
    """Multi-source work item intake.

    Discovers actionable work from GOALS.md, the Cortex taskboard,
    CLI input, and the Cortex recommendation engine.
    """

    def from_goals(self, goals_path: Path) -> List[WorkItem]:
        """Parse GOALS.md and extract work items from actionable sections.

        Looks for bullet items (``- [ ]``, ``- ``, numbered) under
        "Immediate Actions" or "Next phase" headings.
        """
        if not goals_path.exists():
            log.warning("GOALS.md not found at %s", goals_path)
            return []

        text = goals_path.read_text(encoding="utf-8")
        items: List[WorkItem] = []
        in_section = False
        current_header = ""

        for line in text.splitlines():
            # Detect section headers
            if re.match(r"^#{1,3}\s+", line):
                header_lower = line.lower()
                in_section = any(
                    kw in header_lower for kw in ["immediate action", "next phase", "this week"]
                )
                current_header = line.lstrip("#").strip()
                continue

            if not in_section:
                continue

            # Match unchecked checkboxes, plain bullets, or numbered items
            m = re.match(r"^\s*(?:-\s*\[[ ]\]\s*|-\s+|\d+[.)]\s+)(.+)$", line)
            if not m:
                continue

            description = m.group(1).strip()
            if not description:
                continue

            items.append(
                WorkItem(
                    id=_make_id(),
                    source="goals",
                    task_type=_infer_task_type(description),
                    description=description,
                    project=_infer_project(description, current_header),
                    priority=WorkItemPriority.HIGH,
                    confidence=0.7,
                )
            )

        log.info("Parsed %d work items from GOALS.md", len(items))
        return items

    def from_taskboard(self) -> List[WorkItem]:
        """Read the Cortex taskboard JSON and return non-completed items."""
        if not _TASKBOARD_PATH.exists():
            log.info("Taskboard not found at %s", _TASKBOARD_PATH)
            return []

        try:
            data = json.loads(_TASKBOARD_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Failed to read taskboard: %s", exc)
            return []

        items: List[WorkItem] = []
        for entry in data:
            status = entry.get("status", "")
            if status == "done":
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

        log.info("Loaded %d items from taskboard", len(items))
        return items

    def from_cli(
        self,
        description: str,
        project: str = "",
        priority: str = "medium",
    ) -> WorkItem:
        """Create a single WorkItem from CLI freetext input."""
        return WorkItem(
            id=_make_id(),
            source="cli",
            task_type=_infer_task_type(description),
            description=description,
            project=project or _infer_project(description),
            priority=_PRIORITY_MAP.get(priority.lower(), WorkItemPriority.MEDIUM),
            confidence=0.9,
        )

    def from_recommendations(self) -> List[WorkItem]:
        """Query the Cortex bridge for recommendations and convert to WorkItems."""
        items: List[WorkItem] = []
        try:
            resp = httpx.get(
                f"{_BRIDGE_URL}/intelligence/recommendations",
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, OSError) as exc:
            log.warning("Failed to fetch recommendations from bridge: %s", exc)
            return []

        recs = data if isinstance(data, list) else data.get("recommendations", [])
        for rec in recs:
            description = rec.get("title") or rec.get("description", "")
            if not description:
                continue

            priority_str = rec.get("priority", "medium").lower()
            items.append(
                WorkItem(
                    id=_make_id(),
                    source="recommendations",
                    task_type=_infer_task_type(description),
                    description=description,
                    project=rec.get("project", ""),
                    priority=_PRIORITY_MAP.get(priority_str, WorkItemPriority.MEDIUM),
                    confidence=rec.get("confidence", 0.6),
                    metadata={"recommendation_id": rec.get("id", "")},
                )
            )

        log.info("Fetched %d recommendations from bridge", len(items))
        return items

    def discover_all(self, goals_path: Optional[Path] = None) -> List[WorkItem]:
        """Run all intake sources, deduplicate, and sort by priority.

        Deduplication uses word-overlap similarity (threshold 0.7).
        Sorting is by priority score descending, then confidence descending.
        """
        all_items: List[WorkItem] = []

        # Goals
        if goals_path is None:
            goals_path = Path.cwd() / "GOALS.md"
        all_items.extend(self.from_goals(goals_path))

        # Taskboard
        all_items.extend(self.from_taskboard())

        # Recommendations (best-effort, don't block on failure)
        all_items.extend(self.from_recommendations())

        # Deduplicate by description similarity
        deduplicated: List[WorkItem] = []
        for item in all_items:
            is_dup = any(
                _similarity(item.description, existing.description) >= 0.7
                for existing in deduplicated
            )
            if not is_dup:
                deduplicated.append(item)

        # Sort: priority descending, then confidence descending
        deduplicated.sort(
            key=lambda wi: (
                _PRIORITY_SCORE.get(wi.priority, 0),
                wi.confidence,
            ),
            reverse=True,
        )

        log.info(
            "Discovered %d items (%d after dedup)",
            len(all_items),
            len(deduplicated),
        )
        return deduplicated
