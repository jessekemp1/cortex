"""
Plan correlator - Match work items to plan steps.

Uses multiple signals to correlate detected work with planned items:
- File path overlap
- Title/description similarity
- Tag matching
- Project matching
"""

import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import DriftType, PlanDrift, WorkItem, WorkStatus

logger = logging.getLogger(__name__)


class PlanCorrelator:
    """
    Correlate work items with plan steps.

    Loads plans from:
    - ~/.cortex/plans/*.json
    - Project PLAN.md files
    - CORTEX_PLANNING_ITEMS.md

    Uses multi-factor matching:
    - File overlap (40% weight)
    - Title similarity (30% weight)
    - Tag overlap (20% weight)
    - Project match (10% weight)
    """

    def __init__(
        self,
        plans_dir: Optional[Path] = None,
        dev_dir: Optional[Path] = None,
    ):
        """
        Initialize correlator.

        Args:
            plans_dir: Directory containing plan JSON files
            dev_dir: Development root for finding project plans
        """
        self.plans_dir = plans_dir or Path.home() / ".cortex" / "plans"
        self.dev_dir = dev_dir or Path.home() / "Dev"
        self._plans_cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None

    def correlate(self, work_item: WorkItem) -> Optional[Tuple[str, float]]:
        """
        Find the best matching plan step for a work item.

        Args:
            work_item: The work item to correlate

        Returns:
            Tuple of (plan_step_id, confidence) or None if no match
        """
        best_match: Optional[str] = None
        best_confidence: float = 0.0
        threshold = 0.4  # Minimum confidence to consider a match

        plans = self._load_all_plans()

        for plan in plans:
            for step in plan.get("steps", []):
                confidence = self._calculate_match_confidence(work_item, step, plan)

                if confidence > best_confidence and confidence >= threshold:
                    best_confidence = confidence
                    best_match = step.get("id", step.get("title", "unknown"))

        if best_match:
            logger.debug(
                f"Correlated '{work_item.title}' to plan step '{best_match}' "
                f"(confidence: {best_confidence:.2f})"
            )
            return (best_match, best_confidence)

        return None

    def correlate_batch(
        self,
        work_items: List[WorkItem],
    ) -> Dict[str, Tuple[str, float]]:
        """
        Correlate multiple work items efficiently.

        Args:
            work_items: List of work items to correlate

        Returns:
            Dict mapping work_item.id to (plan_step_id, confidence)
        """
        results = {}
        self._load_all_plans()  # Load once for all items

        for item in work_items:
            result = self.correlate(item)
            if result:
                results[item.id] = result

        return results

    def _calculate_match_confidence(
        self,
        work_item: WorkItem,
        plan_step: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> float:
        """
        Calculate confidence score for work-to-plan match.

        Weights:
        - File overlap: 40%
        - Title similarity: 30%
        - Tag overlap: 20%
        - Project match: 10%
        """
        confidence = 0.0

        # File overlap (40% weight)
        step_files = plan_step.get("files", [])
        if step_files and work_item.files_touched:
            overlap = self._calculate_file_overlap(
                work_item.files_touched,
                step_files,
            )
            confidence += 0.4 * overlap

        # Title/description similarity (30% weight)
        work_text = f"{work_item.title} {work_item.description}".lower()
        step_text = f"{plan_step.get('title', '')} {plan_step.get('description', '')}".lower()
        text_sim = self._text_similarity(work_text, step_text)
        confidence += 0.3 * text_sim

        # Tag/keyword overlap (20% weight)
        if work_item.tags:
            step_keywords = self._extract_keywords(plan_step)
            if step_keywords:
                tag_overlap = len(set(work_item.tags) & step_keywords) / len(work_item.tags)
                confidence += 0.2 * tag_overlap

        # Project match (10% weight)
        plan_project = plan.get("project", "").lower()
        if plan_project and work_item.project.lower() in plan_project:
            confidence += 0.1
        elif work_item.project.lower() in str(plan_step).lower():
            confidence += 0.05

        return min(confidence, 1.0)

    def _calculate_file_overlap(
        self,
        work_files: List[str],
        plan_files: List[str],
    ) -> float:
        """Calculate overlap between file lists."""
        if not work_files or not plan_files:
            return 0.0

        # Normalize paths
        work_set = set(Path(f).name for f in work_files)
        plan_set = set(Path(f).name for f in plan_files)

        # Calculate Jaccard similarity
        intersection = work_set & plan_set
        union = work_set | plan_set

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        if not text1 or not text2:
            return 0.0

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, text1, text2).ratio()

    def _extract_keywords(self, plan_step: Dict[str, Any]) -> set:
        """Extract keywords from a plan step."""
        keywords = set()

        # Add explicit tags
        if "tags" in plan_step:
            keywords.update(t.lower() for t in plan_step["tags"])

        # Extract from title and description
        text = f"{plan_step.get('title', '')} {plan_step.get('description', '')}"
        text = text.lower()

        # Common stop words to exclude
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
        }

        # Extract words
        words = re.findall(r"\b[a-z]{3,}\b", text)
        keywords.update(w for w in words if w not in stop_words)

        return keywords

    def _load_all_plans(self) -> List[Dict[str, Any]]:
        """Load all plans from various sources."""
        # Use cache if recent (5 minutes)
        if self._cache_time and (datetime.now() - self._cache_time).seconds < 300:
            return list(self._plans_cache.values())

        plans = []

        # Load from ~/.cortex/plans/
        if self.plans_dir.exists():
            for plan_file in self.plans_dir.glob("*.json"):
                try:
                    with open(plan_file) as f:
                        plan = json.load(f)
                        plan["_source"] = str(plan_file)
                        plans.append(plan)
                except Exception as e:
                    logger.warning(f"Failed to load plan {plan_file}: {e}")

        # Load from project PLAN.md files
        for project_dir in self.dev_dir.iterdir():
            if not project_dir.is_dir():
                continue

            plan_md = project_dir / "PLAN.md"
            if plan_md.exists():
                plan = self._parse_plan_md(plan_md, project_dir.name)
                if plan:
                    plans.append(plan)

            # Also check cortex-specific planning files
            for name in ["CORTEX_PLANNING_ITEMS.md", "PLANNING.md"]:
                planning_file = project_dir / name
                if planning_file.exists():
                    plan = self._parse_plan_md(planning_file, project_dir.name)
                    if plan:
                        plans.append(plan)

        # Cache results
        self._plans_cache = {p.get("_source", str(i)): p for i, p in enumerate(plans)}
        self._cache_time = datetime.now()

        return plans

    def _parse_plan_md(self, plan_path: Path, project: str) -> Optional[Dict[str, Any]]:
        """Parse a PLAN.md file into structured plan data."""
        try:
            content = plan_path.read_text(encoding="utf-8", errors="ignore")

            plan = {
                "id": f"plan-{project}-{plan_path.stem}",
                "project": project,
                "title": f"{project} Plan",
                "steps": [],
                "_source": str(plan_path),
            }

            # Extract title from first H1
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                plan["title"] = title_match.group(1).strip()

            # Extract steps from headers and checkboxes
            steps = []

            # Find H2/H3 sections as major steps
            sections = re.findall(
                r"^(#{2,3})\s+(.+?)$\n([\s\S]*?)(?=^#{2,3}|\Z)",
                content,
                re.MULTILINE,
            )

            for level, title, body in sections:
                step = {
                    "id": f"{plan['id']}-{len(steps)}",
                    "title": title.strip(),
                    "description": "",
                    "files": [],
                    "tags": [],
                }

                # Extract description (first paragraph)
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                if paragraphs:
                    # Skip if it's just a list
                    if not paragraphs[0].startswith("-"):
                        step["description"] = paragraphs[0][:500]

                # Extract file references
                file_refs = re.findall(r"`([^`]+\.[a-z]+)`", body)
                step["files"] = file_refs[:10]

                # Extract tags from brackets
                tags = re.findall(r"\[([^\]]+)\]", title)
                step["tags"] = tags

                steps.append(step)

            # Also extract checkbox items as steps
            checkboxes = re.findall(
                r"^\s*-\s*\[[ x]\]\s*(.+)$", content, re.MULTILINE | re.IGNORECASE
            )
            for i, item in enumerate(checkboxes[:20]):  # Limit
                steps.append(
                    {
                        "id": f"{plan['id']}-checkbox-{i}",
                        "title": item.strip(),
                        "description": "",
                        "files": [],
                        "tags": [],
                    }
                )

            plan["steps"] = steps
            return plan

        except Exception as e:
            logger.warning(f"Failed to parse plan {plan_path}: {e}")
            return None

    def get_active_plans(self) -> List[Dict[str, Any]]:
        """Get all active plans for drift detection."""
        return [p for p in self._load_all_plans() if p.get("status") != "completed"]


class DriftAnalyzer:
    """
    Analyze drift between plans and actual work.

    Detects:
    - UNPLANNED_WORK: Work done that's not in any plan
    - STALE_PLAN: Plan items with no recent activity
    - SCOPE_CREEP: Work that exceeds plan scope
    - BLOCKED: Explicitly blocked items
    """

    def __init__(self, correlator: Optional[PlanCorrelator] = None):
        """
        Initialize drift analyzer.

        Args:
            correlator: PlanCorrelator instance to reuse
        """
        self.correlator = correlator or PlanCorrelator()

    def analyze(
        self,
        work_items: List[WorkItem],
        lookback_days: int = 7,
    ) -> List[PlanDrift]:
        """
        Detect all types of drift.

        Args:
            work_items: Recent work items to analyze
            lookback_days: Days to consider for staleness

        Returns:
            List of PlanDrift objects
        """
        drifts = []

        # Detect unplanned work (orphaned items)
        drifts.extend(self._detect_unplanned_work(work_items))

        # Detect stale plans (no activity)
        drifts.extend(self._detect_stale_plans(work_items, lookback_days))

        # Detect scope creep
        drifts.extend(self._detect_scope_creep(work_items))

        return drifts

    def _detect_unplanned_work(self, work_items: List[WorkItem]) -> List[PlanDrift]:
        """Find work items with no plan correlation."""
        drifts = []

        for item in work_items:
            if item.status == WorkStatus.ORPHANED:
                # Determine severity based on effort
                if item.estimated_effort_hours > 4:
                    severity = "warning"
                elif item.estimated_effort_hours > 8:
                    severity = "critical"
                else:
                    severity = "info"

                drift = PlanDrift(
                    id=f"drift-unplanned-{item.id}",
                    project=item.project,
                    detected_at=datetime.now(),
                    drift_type=DriftType.UNPLANNED_WORK,
                    severity=severity,
                    work_item_id=item.id,
                    description=f"Work on '{item.title}' not found in any plan",
                    suggested_action="Consider adding to plan retroactively or marking as ad-hoc work",
                )
                drifts.append(drift)

        return drifts

    def _detect_stale_plans(
        self,
        work_items: List[WorkItem],
        lookback_days: int,
    ) -> List[PlanDrift]:
        """Find plan items with no recent activity."""
        drifts = []

        # Get correlated plan steps from work items
        active_steps = set()
        for item in work_items:
            if item.plan_step_id:
                active_steps.add(item.plan_step_id)

        # Check all plan steps
        plans = self.correlator.get_active_plans()

        for plan in plans:
            for step in plan.get("steps", []):
                step_id = step.get("id", step.get("title"))
                status = step.get("status", "pending")

                # Skip completed or explicitly deferred
                if status in ["completed", "deferred", "cancelled"]:
                    continue

                # Check if step has activity
                if step_id not in active_steps:
                    # This step has no recent work
                    drift = PlanDrift(
                        id=f"drift-stale-{step_id}",
                        project=plan.get("project", "unknown"),
                        detected_at=datetime.now(),
                        drift_type=DriftType.STALE_PLAN,
                        severity="info",
                        plan_step_id=step_id,
                        description=f"Plan step '{step.get('title', step_id)}' has no activity in {lookback_days} days",
                        suggested_action="Review if step is still relevant or needs to be started",
                    )
                    drifts.append(drift)

        return drifts

    def _detect_scope_creep(self, work_items: List[WorkItem]) -> List[PlanDrift]:
        """Detect work that exceeds original plan scope."""
        drifts = []

        # Group work items by plan step
        items_by_step: Dict[str, List[WorkItem]] = {}
        for item in work_items:
            if item.plan_step_id:
                items_by_step.setdefault(item.plan_step_id, []).append(item)

        # Check for steps with excessive work
        for step_id, items in items_by_step.items():
            total_effort = sum(i.estimated_effort_hours for i in items)
            total_files = len(set(f for i in items for f in i.files_touched))

            # Heuristic: more than 20 hours or 50 files suggests scope creep
            if total_effort > 20 or total_files > 50:
                drift = PlanDrift(
                    id=f"drift-scope-{step_id}",
                    project=items[0].project if items else "unknown",
                    detected_at=datetime.now(),
                    drift_type=DriftType.SCOPE_CREEP,
                    severity="warning",
                    plan_step_id=step_id,
                    description=f"Plan step '{step_id}' has {total_effort:.1f}h of work across {total_files} files",
                    suggested_action="Consider breaking this into smaller plan steps",
                )
                drifts.append(drift)

        return drifts
