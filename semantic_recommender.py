"""
Semantic Recommender - Interprets high-level goals from plans.

Parses natural language action plans (ACTION_PLAN.md) to generate
aligned recommendations for Cortex.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlanAction:
    title: str
    priority: str
    context: str
    steps: List[str]


class SemanticRecommender:
    """Interprets strategic plans into tactical recommendations."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def analyze_plan(self, plan_path: Path) -> List[Dict[str, Any]]:
        """
        Parse ACTION_PLAN.md and return recommendation dictionaries.

        Returns:
            List of dicts compatible with Recommendation objects.
        """
        if not plan_path.exists():
            return []

        content = plan_path.read_text()
        return self._parse_markdown_plan(content)

    def _parse_markdown_plan(self, content: str) -> List[Dict[str, Any]]:
        """
        Heuristic parser for standard ACTION_PLAN.md format.
        Looks for 'Priority A' sections and 'Immediate Actions'.
        """
        recommendations = []

        # 1. Extract Priority A Section
        # Matches "### Priority A" until "### Priority B" or end of section "---"
        priority_a_match = re.search(
            r"### Priority A.*?(?=### Priority B|---)",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        if not priority_a_match:
            return []

        section_content = priority_a_match.group(0)

        # 2. Extract Projects/Goals within Priority A
        # "#### 1. **Git Repository Cleanup**"
        # Use robust split on "#### N."
        goal_blocks = re.split(r"####\s+\d+\.", section_content)

        # Skip the first split as it's the header before "#### 1."
        for block in goal_blocks[1:]:
            rec = self._parse_goal_block(block)
            if rec:
                recommendations.append(rec)

        return recommendations

    def _parse_goal_block(self, block: str) -> Optional[Dict[str, Any]]:
        """Parse a single goal block into a recommendation."""
        lines = block.strip().split("\n")
        if not lines:
            return None

        # Line 1: "**Git Repository Cleanup** 🔴 CRITICAL" -> "Git Repository Cleanup"
        title_line = lines[0]
        title_match = re.search(r"\*\*(.*?)\*\*", title_line)
        title = title_match.group(1) if title_match else title_line.split("**")[0].strip()

        # Determine Priority
        is_critical = "CRITICAL" in title_line or "🔴" in title_line
        priority = "high" if is_critical else "medium"

        # Extract Rationale/Status
        rationale = "Strategic Goal from ACTION_PLAN.md"
        status_match = re.search(r"\*\*Status\*\*: (.*)", block)
        if status_match:
            rationale = status_match.group(1).strip()

        # Extract Actions
        action_steps = []
        # Look for numbered lists "1. " or "1. [ ]"
        action_matches = re.finditer(r"^\d+\.\s+(?:✅|\[.?\])?\s*(.*)", block, re.MULTILINE)
        for m in action_matches:
            step = m.group(1).strip()
            # If step is already done (checked), we might skip or mark as done context
            # But here we just grab them all to form the description
            # Simple heuristic: if it has "✅", it's done.
            line_full = m.group(0)
            if "✅" not in line_full and "[x]" not in line_full:
                action_steps.append(step)

        if not action_steps:
            # If no unchecked steps found, maybe the goal is done?
            # For now, if no steps, we assume it's info only or fully done.
            return None

        description = "Next steps from Action Plan:\n" + "\n".join(f"• {s}" for s in action_steps)

        # Generate ID
        rec_id = f"strategy_{hash(title) % 10000}"

        return {
            "id": rec_id,
            "title": f"Execute Strategy: {title}",
            "type": "strategic_alignment",
            "priority": priority,
            "estimated_impact": "high",
            "confidence": 0.95,
            "rationale": rationale,
            "description": description,
            "related_projects": [],  # Could extract from title
            "estimated_effort": "Variable",
        }
