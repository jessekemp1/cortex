#!/usr/bin/env python3
"""
Goal Parser - Parses goals from ACTION_PLAN.md for Cortex

Extracts structured goal information including priority, status, and project.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Goal:
    """Parsed goal from ACTION_PLAN.md."""

    title: str
    priority: str  # "A", "B", "C"
    status: str  # "pending", "in_progress", "completed"
    project: Optional[str] = None
    description: str = ""
    actions: List[str] = field(default_factory=list)
    success_criteria: str = ""
    blockers: List[str] = field(default_factory=list)


class GoalParser:
    """Parses goals from ACTION_PLAN.md."""

    # Project name mapping (handles various formats)
    PROJECT_ALIASES = {
        "vortexv2": "VortexV2",
        "vortex v2": "VortexV2",
        "alpha arena": "alpha_arena",
        "alpha-arena": "alpha_arena",
        "alphaarena": "alpha_arena",
        "personal-ai-dataset": "personal-ai-dataset",
        "personal ai dataset": "personal-ai-dataset",
        "keto-tracker": "keto-tracker",
        "keto tracker": "keto-tracker",
        "ketotracker": "keto-tracker",
        "financial-aggregator": "financial-aggregator",
        "financial aggregator": "financial-aggregator",
        "ai-project-curator": "ai-project-curator",
        "cortex": "cortex",
        "converx": "cortex",
        "windfield": "Windfield",
        "vortex": "Vortex",
        "local-orchestrator": "local-orchestrator",
        "local orchestrator": "local-orchestrator",
        "databricks": "Databricks",
        "youtube-summarizer": "youtube-summarizer",
        "dj-copilot": "DJ-CoPilot",
    }

    def __init__(self, action_plan_path: Optional[Path] = None):
        if action_plan_path is None:
            action_plan_path = Path("/Users/jesse.kemp/Dev/ACTION_PLAN.md")
        self.action_plan_path = action_plan_path

    def parse(self) -> List[Goal]:
        """Parse goals from ACTION_PLAN.md."""
        if not self.action_plan_path.exists():
            return []

        content = self.action_plan_path.read_text()
        goals = []

        # Parse Priority A goals
        goals.extend(self._parse_priority_section(content, "A"))

        # Parse Priority B goals
        goals.extend(self._parse_priority_section(content, "B"))

        # Parse Priority C goals
        goals.extend(self._parse_priority_section(content, "C"))

        return goals

    def _parse_priority_section(self, content: str, priority: str) -> List[Goal]:
        """Parse goals from a priority section."""
        goals = []

        # Find the priority section
        patterns = [
            rf"###\s*Priority\s*{priority}[:\s]*.*?(?=###\s*Priority|##\s*[A-Z]|$)",
            rf"##\s*Priority\s*{priority}[:\s]*.*?(?=##\s*Priority|##\s*[A-Z]|$)",
        ]

        section_content = None
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                section_content = match.group(0)
                break

        if not section_content:
            return goals

        # Find numbered items (goals) in the section
        # Pattern: #### N. **Title** or #### N. Title
        goal_pattern = r"####\s*(\d+)\.\s*\*\*([^*]+)\*\*|####\s*(\d+)\.\s*([^\n]+)"

        matches = re.finditer(goal_pattern, section_content)

        for match in matches:
            # Get title from either capture group
            title = (match.group(2) or match.group(4) or "").strip()
            if not title:
                continue

            # Get content after this goal header until next goal or section
            start_pos = match.end()
            next_goal = re.search(r"####\s*\d+\.", section_content[start_pos:])
            if next_goal:
                goal_content = section_content[
                    start_pos : start_pos + next_goal.start()
                ]
            else:
                goal_content = section_content[start_pos:]

            # Parse goal details
            goal = self._parse_goal_content(title, priority, goal_content)
            goals.append(goal)

        # Also check for simpler list format
        if not goals:
            goals = self._parse_list_format(section_content, priority)

        return goals

    def _parse_list_format(self, section_content: str, priority: str) -> List[Goal]:
        """Parse goals from simple list format (1. Item, 2. Item)."""
        goals = []

        # Pattern for numbered list items
        pattern = r"^\s*(\d+)\.\s*\*\*([^*]+)\*\*|^\s*(\d+)\.\s*([^\n]+)"

        for match in re.finditer(pattern, section_content, re.MULTILINE):
            title = (match.group(2) or match.group(4) or "").strip()
            if not title:
                continue

            # Skip if it looks like a sub-item or action
            if title.startswith(("Create", "Add", "Update", "Run", "Verify")):
                continue

            goal = Goal(
                title=title,
                priority=priority,
                status=self._infer_status(title, section_content),
                project=self._extract_project(title),
            )
            goals.append(goal)

        return goals

    def _parse_goal_content(self, title: str, priority: str, content: str) -> Goal:
        """Parse detailed goal content."""
        # Extract status
        status = self._infer_status(title, content)

        # Extract project
        project = self._extract_project(title + " " + content)

        # Extract description (first paragraph after title)
        desc_match = re.search(r"\*\*Status\*\*:\s*([^\n]+)", content)
        description = desc_match.group(1).strip() if desc_match else ""

        # Extract actions (bulleted items)
        actions = []
        action_pattern = r"^\s*[-*]\s+(.+)$"
        for action_match in re.finditer(action_pattern, content, re.MULTILINE):
            action = action_match.group(1).strip()
            # Skip if it's a status or metadata line
            if not any(
                action.startswith(skip)
                for skip in ["Status:", "Impact:", "Gap:", "Tool"]
            ):
                actions.append(action)

        # Extract success criteria
        success_match = re.search(r"\*\*Success Criteria\*\*:\s*([^\n]+)", content)
        success_criteria = success_match.group(1).strip() if success_match else ""

        # Extract blockers
        blockers = []
        blocker_match = re.search(r"\*\*Gap\*\*:\s*([^\n]+)", content)
        if blocker_match:
            blockers.append(blocker_match.group(1).strip())

        return Goal(
            title=title,
            priority=priority,
            status=status,
            project=project,
            description=description,
            actions=actions[:5],  # Limit to 5 actions
            success_criteria=success_criteria,
            blockers=blockers,
        )

    def _infer_status(self, title: str, content: str) -> str:
        """Infer goal status from content."""
        combined = (title + " " + content).lower()

        # Check for explicit status markers
        if any(marker in combined for marker in ["✅", "complete", "done", "finished"]):
            return "completed"

        if any(
            marker in combined
            for marker in ["🔴", "critical", "urgent", "in progress", "active"]
        ):
            return "in_progress"

        if any(marker in combined for marker in ["🟡", "medium", "next"]):
            return "pending"

        # Default based on priority
        return "pending"

    def _extract_project(self, text: str) -> Optional[str]:
        """Extract project name from text."""
        text_lower = text.lower()

        # Check for direct project mentions
        for alias, project in self.PROJECT_ALIASES.items():
            if alias in text_lower:
                return project

        # Check for project patterns
        patterns = [
            r"\*\*(\w+[-_]?\w*)\*\*\s*[-:]",  # **ProjectName** -
            r"`(\w+[-_]?\w*)`",  # `project-name`
            r"\((\w+[-_]?\w*)\)",  # (ProjectName)
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).lower()
                if candidate in self.PROJECT_ALIASES:
                    return self.PROJECT_ALIASES[candidate]

        return None

    def parse_simple_goals(self, goals_md_path: Optional[Path] = None) -> List[Goal]:
        """
        Parse goals from GOALS.md (simple checkbox format).

        Format:
            ## High Priority
            - [ ] Goal title
            - [x] Completed goal

        Args:
            goals_md_path: Path to GOALS.md (defaults to /Users/jesse.kemp/Dev/GOALS.md)

        Returns:
            List of Goal objects
        """
        if goals_md_path is None:
            goals_md_path = Path("/Users/jesse.kemp/Dev/GOALS.md")

        if not goals_md_path.exists():
            return []

        content = goals_md_path.read_text()
        goals = []
        current_priority = "B"  # Default to medium priority

        for line in content.split("\n"):
            line = line.strip()

            # Detect priority sections
            if "high priority" in line.lower():
                current_priority = "A"
                continue
            elif "medium priority" in line.lower():
                current_priority = "B"
                continue
            elif "low priority" in line.lower():
                current_priority = "C"
                continue
            elif line.lower().startswith("## completed"):
                # Skip completed section
                break

            # Parse checkbox items: - [ ] or - [x]
            match = re.match(r"^-\s*\[([ xX])\]\s*(.+)$", line)
            if match:
                completed = match.group(1).lower() == "x"
                title = match.group(2).strip()

                # Skip if empty title
                if not title:
                    continue

                # Infer project from title
                project = self._extract_project(title)

                goals.append(
                    Goal(
                        title=title,
                        priority=current_priority,
                        status="completed" if completed else "pending",
                        project=project,
                    )
                )

        return goals

    def parse_all_goals(self) -> List[Goal]:
        """
        Parse goals from both GOALS.md and ACTION_PLAN.md.

        Tries GOALS.md first (simpler format), falls back to ACTION_PLAN.md.

        Returns:
            List of Goal objects from whichever file exists
        """
        # Try GOALS.md first
        simple_goals = self.parse_simple_goals()
        if simple_goals:
            return simple_goals

        # Fall back to ACTION_PLAN.md
        return self.parse()

    def get_priority_a_goals(self) -> List[Goal]:
        """Get only Priority A goals."""
        return [g for g in self.parse() if g.priority == "A"]

    def get_in_progress_goals(self) -> List[Goal]:
        """Get goals that are in progress."""
        return [g for g in self.parse() if g.status == "in_progress"]

    def get_blocked_goals(self) -> List[Goal]:
        """Get goals that have blockers."""
        return [g for g in self.parse() if g.blockers]


def main():
    """CLI for testing goal parser."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Parse goals from ACTION_PLAN.md")
    parser.add_argument("--path", help="Path to ACTION_PLAN.md")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--priority", choices=["A", "B", "C"], help="Filter by priority"
    )
    args = parser.parse_args()

    goal_parser = GoalParser(Path(args.path) if args.path else None)
    goals = goal_parser.parse()

    if args.priority:
        goals = [g for g in goals if g.priority == args.priority]

    if args.json:
        output = []
        for g in goals:
            output.append(
                {
                    "title": g.title,
                    "priority": g.priority,
                    "status": g.status,
                    "project": g.project,
                    "description": g.description,
                    "actions": g.actions,
                    "success_criteria": g.success_criteria,
                    "blockers": g.blockers,
                }
            )
        print(json.dumps(output, indent=2))
    else:
        print(f"Found {len(goals)} goals\n")

        for priority in ["A", "B", "C"]:
            priority_goals = [g for g in goals if g.priority == priority]
            if priority_goals:
                print(f"PRIORITY {priority}:")
                for g in priority_goals:
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "pending": "⏳",
                    }.get(g.status, "❓")
                    project_str = f" [{g.project}]" if g.project else ""
                    print(f"  {status_icon} {g.title}{project_str}")
                print()


if __name__ == "__main__":
    main()
