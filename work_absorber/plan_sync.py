"""
Plan Sync - Synchronize absorbed work progress back to planning documents.

Updates PLAN.md and other planning files with:
- Step completion status based on detected work
- Progress notes from evidence
- Completion timestamps
- Overall plan progress percentage
"""

import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from .models import WorkItem, ProgressEntry, WorkStatus
from .storage import WorkAbsorberStorage

logger = logging.getLogger(__name__)


class PlanProgressSync:
    """
    Synchronize absorbed work progress back to plans.

    Supports:
    - JSON plan files (structured)
    - Markdown PLAN.md files (with checkboxes)
    - CORTEX_PLANNING_ITEMS.md format
    """

    def __init__(
        self,
        storage: Optional[WorkAbsorberStorage] = None,
        plans_dir: Optional[Path] = None,
        dev_dir: Optional[Path] = None,
    ):
        """
        Initialize plan sync.

        Args:
            storage: Work absorber storage
            plans_dir: Directory for JSON plans
            dev_dir: Development root for project plans
        """
        self.storage = storage or WorkAbsorberStorage()
        self.plans_dir = plans_dir or Path.home() / ".cortex" / "plans"
        self.dev_dir = dev_dir or Path.home() / "Dev"

    def sync_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync progress to all plans.

        Args:
            dry_run: If True, don't write changes, just report what would change

        Returns:
            Summary of sync operations
        """
        result = {
            "json_plans_updated": [],
            "markdown_plans_updated": [],
            "steps_completed": 0,
            "steps_started": 0,
            "errors": [],
        }

        # Sync JSON plans
        json_result = self._sync_json_plans(dry_run)
        result["json_plans_updated"] = json_result.get("updated", [])
        result["errors"].extend(json_result.get("errors", []))

        # Sync markdown plans
        md_result = self._sync_markdown_plans(dry_run)
        result["markdown_plans_updated"] = md_result.get("updated", [])
        result["steps_completed"] += md_result.get("steps_completed", 0)
        result["steps_started"] += md_result.get("steps_started", 0)
        result["errors"].extend(md_result.get("errors", []))

        return result

    def sync_project(self, project: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync progress for a specific project.

        Args:
            project: Project name
            dry_run: If True, don't write changes

        Returns:
            Sync result for the project
        """
        project_path = self.dev_dir / project
        if not project_path.exists():
            return {"error": f"Project not found: {project}"}

        result = {
            "project": project,
            "plan_updated": False,
            "steps_completed": 0,
            "steps_started": 0,
            "changes": [],
        }

        # Find plan files
        plan_files = [
            project_path / "PLAN.md",
            project_path / "CORTEX_PLANNING_ITEMS.md",
            project_path / "PLANNING.md",
        ]

        for plan_file in plan_files:
            if plan_file.exists():
                changes = self._sync_markdown_file(plan_file, project, dry_run)
                if changes:
                    result["plan_updated"] = True
                    result["steps_completed"] += changes.get("completed", 0)
                    result["steps_started"] += changes.get("started", 0)
                    result["changes"].extend(changes.get("changes", []))

        return result

    def _sync_json_plans(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync JSON plan files in ~/.cortex/plans/."""
        result = {"updated": [], "errors": []}

        if not self.plans_dir.exists():
            return result

        for plan_file in self.plans_dir.glob("*.json"):
            try:
                with open(plan_file) as f:
                    plan = json.load(f)

                updated = False
                project = plan.get("project", "unknown")

                for step in plan.get("steps", []):
                    step_id = step.get("id", step.get("title"))

                    # Get progress entries for this step
                    entries = self.storage.get_progress_for_plan_step(step_id)

                    if entries:
                        cumulative = max(e.cumulative_progress for e in entries)
                        current_status = step.get("status", "pending")

                        # Update status based on progress
                        if cumulative >= 1.0 and current_status != "completed":
                            step["status"] = "completed"
                            step["completed_at"] = datetime.now().isoformat()
                            updated = True
                        elif cumulative > 0 and current_status == "pending":
                            step["status"] = "in_progress"
                            step["started_at"] = entries[0].timestamp.isoformat()
                            updated = True

                        # Add progress notes
                        step.setdefault("progress_notes", [])
                        for entry in entries:
                            note = f"{entry.timestamp.strftime('%Y-%m-%d')}: {entry.evidence_summary}"
                            if note not in step["progress_notes"]:
                                step["progress_notes"].append(note)
                                updated = True

                if updated:
                    # Calculate overall progress
                    plan["progress"] = self._calculate_plan_progress(plan)
                    plan["last_synced"] = datetime.now().isoformat()

                    if not dry_run:
                        with open(plan_file, "w") as f:
                            json.dump(plan, f, indent=2)

                    result["updated"].append(plan_file.name)

            except Exception as e:
                result["errors"].append(f"{plan_file.name}: {str(e)}")

        return result

    def _sync_markdown_plans(self, dry_run: bool = False) -> Dict[str, Any]:
        """Sync markdown plan files in projects."""
        result = {
            "updated": [],
            "steps_completed": 0,
            "steps_started": 0,
            "errors": [],
        }

        for project_dir in self.dev_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            project = project_dir.name

            for plan_name in ["PLAN.md", "CORTEX_PLANNING_ITEMS.md", "PLANNING.md"]:
                plan_file = project_dir / plan_name
                if plan_file.exists():
                    try:
                        changes = self._sync_markdown_file(plan_file, project, dry_run)
                        if changes and changes.get("updated"):
                            result["updated"].append(f"{project}/{plan_name}")
                            result["steps_completed"] += changes.get("completed", 0)
                            result["steps_started"] += changes.get("started", 0)
                    except Exception as e:
                        result["errors"].append(f"{project}/{plan_name}: {str(e)}")

        return result

    def _sync_markdown_file(
        self,
        plan_file: Path,
        project: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync a single markdown plan file.

        Updates checkboxes from [ ] to [x] based on detected work.
        """
        result = {
            "updated": False,
            "completed": 0,
            "started": 0,
            "changes": [],
        }

        content = plan_file.read_text(encoding="utf-8", errors="ignore")
        original_content = content

        # Get work items for this project
        work_items = self.storage.get_work_items_by_project(project)
        correlated_items = [w for w in work_items if w.status == WorkStatus.CORRELATED]

        # Find checkboxes and try to match with work items
        checkbox_pattern = r"^(\s*-\s*)\[( |x)\]\s*(.+)$"

        def replace_checkbox(match):
            nonlocal result
            prefix = match.group(1)
            checked = match.group(2)
            text = match.group(3)

            if checked == "x":
                return match.group(0)  # Already checked

            # Try to match with completed work
            text_lower = text.lower()

            for item in correlated_items:
                # Check if work item matches this checkbox
                if self._text_matches(item.title, text) or \
                   self._text_matches(item.description, text):
                    # Mark as completed
                    result["completed"] += 1
                    result["changes"].append(f"Completed: {text[:50]}")
                    result["updated"] = True
                    return f"{prefix}[x] {text}"

            return match.group(0)

        content = re.sub(checkbox_pattern, replace_checkbox, content, flags=re.MULTILINE)

        # Add progress summary if significant changes
        if result["completed"] > 0:
            # Add a sync timestamp comment
            sync_marker = f"\n<!-- Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"

            # Check if we already have a sync marker and update it
            if "<!-- Last synced:" in content:
                content = re.sub(
                    r"<!-- Last synced: .+? -->",
                    f"<!-- Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')} -->",
                    content
                )
            else:
                # Add at end of file
                content = content.rstrip() + sync_marker

        if content != original_content and not dry_run:
            plan_file.write_text(content, encoding="utf-8")

        return result

    def _text_matches(self, work_text: str, plan_text: str) -> bool:
        """Check if work text matches plan text."""
        if not work_text or not plan_text:
            return False

        work_lower = work_text.lower()
        plan_lower = plan_text.lower()

        # Exact match
        if work_lower == plan_lower:
            return True

        # Work text contains plan text or vice versa
        if plan_lower in work_lower or work_lower in plan_lower:
            return True

        # Word overlap
        work_words = set(re.findall(r"\b\w{4,}\b", work_lower))
        plan_words = set(re.findall(r"\b\w{4,}\b", plan_lower))

        if work_words and plan_words:
            overlap = len(work_words & plan_words)
            min_words = min(len(work_words), len(plan_words))
            if min_words > 0 and overlap / min_words > 0.5:
                return True

        return False

    def _calculate_plan_progress(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall plan progress."""
        steps = plan.get("steps", [])
        if not steps:
            return {"percentage": 0, "completed": 0, "total": 0}

        completed = sum(1 for s in steps if s.get("status") == "completed")
        in_progress = sum(1 for s in steps if s.get("status") == "in_progress")

        return {
            "percentage": round(completed / len(steps) * 100, 1),
            "completed": completed,
            "in_progress": in_progress,
            "total": len(steps),
        }

    def generate_progress_report(self, project: Optional[str] = None) -> str:
        """
        Generate a markdown progress report.

        Args:
            project: Optional project filter

        Returns:
            Markdown formatted progress report
        """
        lines = [
            "# Work Progress Report",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # Get work items
        if project:
            items = self.storage.get_work_items_by_project(project)
            lines.append(f"## {project}")
        else:
            items = self.storage.get_all_work_items(limit=100)
            lines.append("## All Projects")

        lines.append("")

        # Summary
        correlated = [i for i in items if i.plan_step_id]
        orphaned = [i for i in items if not i.plan_step_id]

        lines.extend([
            f"- **Total work items:** {len(items)}",
            f"- **Correlated to plans:** {len(correlated)}",
            f"- **Unplanned work:** {len(orphaned)}",
            "",
        ])

        # Correlated work
        if correlated:
            lines.extend([
                "### Planned Work Completed",
                "",
            ])
            for item in correlated[:20]:
                lines.append(f"- [x] **{item.title}** ({item.project})")
                lines.append(f"  - Plan step: {item.plan_step_id}")
                lines.append(f"  - Confidence: {item.correlation_confidence:.0%}")
                lines.append("")

        # Unplanned work
        if orphaned:
            lines.extend([
                "### Unplanned Work",
                "",
            ])
            for item in orphaned[:20]:
                lines.append(f"- [ ] **{item.title}** ({item.project})")
                lines.append(f"  - Scope: {item.scope or 'unknown'}")
                lines.append(f"  - Files: {len(item.files_touched)}")
                lines.append("")

        return "\n".join(lines)


def sync_plans_cli(project: Optional[str] = None, dry_run: bool = False) -> None:
    """CLI helper for plan sync."""
    sync = PlanProgressSync()

    if project:
        result = sync.sync_project(project, dry_run=dry_run)
    else:
        result = sync.sync_all(dry_run=dry_run)

    print(f"Plan Sync {'(dry run)' if dry_run else ''}")
    print("=" * 40)

    if project:
        print(f"Project: {project}")
        print(f"Plan updated: {result.get('plan_updated', False)}")
        print(f"Steps completed: {result.get('steps_completed', 0)}")
        print(f"Steps started: {result.get('steps_started', 0)}")
    else:
        updated = result.get("json_plans_updated", []) + result.get("markdown_plans_updated", [])
        print(f"Plans updated: {len(updated)}")
        for plan in updated:
            print(f"  - {plan}")

        print(f"Steps completed: {result.get('steps_completed', 0)}")
        print(f"Steps started: {result.get('steps_started', 0)}")

    errors = result.get("errors", [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors[:5]:
            print(f"  - {error}")
