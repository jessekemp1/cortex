"""Shared helper functions used across command modules."""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

try:
    from ai_intelligence import ProjectScanner
except ImportError:
    ProjectScanner = None

try:
    from datetime import timedelta

    from intelligence.model_selection import (
        ContextAwareModelRecommender,
        OrchestrationContext,
    )

    MODEL_SELECTION_AVAILABLE = True
except ImportError:
    MODEL_SELECTION_AVAILABLE = False


def get_model_recommendation(recommendation, budget=5.00):
    """
    Generate model recommendation for a task.

    Args:
        recommendation: Recommendation object with type, description, priority, files
        budget: Remaining session budget in USD (default: $5.00)

    Returns:
        Dict with model, reasoning, cost, confidence
    """
    if not MODEL_SELECTION_AVAILABLE:
        return None

    try:
        recommender = ContextAwareModelRecommender()

        # Create orchestration context
        context = OrchestrationContext(
            remaining_budget=budget,
            remaining_time=timedelta(hours=2),  # Default 2 hour session
            task_priority=recommendation.priority,
            project=(
                recommendation.related_projects[0] if recommendation.related_projects else "cortex"
            ),
            files=recommendation.files or [],
        )

        # Get recommendation
        model_rec = recommender.recommend(
            task_description=recommendation.description,
            task_type=recommendation.type,
            context=context,
        )

        # Convert to dict for serialization
        return {
            "model": model_rec.model,
            "reasoning": model_rec.reasoning,
            "confidence": model_rec.confidence,
            "estimated_cost_usd": model_rec.estimated_cost_usd,
            "estimated_tokens": model_rec.estimated_tokens,
            "alternatives": (model_rec.alternatives[:2] if model_rec.alternatives else []),
        }
    except Exception as e:
        # Fail gracefully - model selection is optional
        return {"error": str(e)}


def _compute_signal_quality(modified: int, untracked: int) -> str:
    dirty_total = int(modified) + int(untracked)
    if dirty_total >= 75:
        return "LOW"
    if dirty_total >= 30:
        return "MED"
    return "HIGH"


def _get_root_signal_quality(root: Path) -> Dict[str, Union[int, str]]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return {"quality": "UNKNOWN", "modified": 0, "untracked": 0, "dirty_total": 0}

        modified = 0
        untracked = 0
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            if line.startswith("??"):
                untracked += 1
            else:
                modified += 1

        return {
            "quality": _compute_signal_quality(modified, untracked),
            "modified": modified,
            "untracked": untracked,
            "dirty_total": modified + untracked,
        }
    except Exception:
        return {"quality": "UNKNOWN", "modified": 0, "untracked": 0, "dirty_total": 0}


def _portfolio_counts_from_scanner(root: Path) -> Optional[Tuple[int, int]]:
    if not ProjectScanner:
        return None
    try:
        scanner = ProjectScanner(str(root))
        repos = scanner.find_git_repos()
        activities = [scanner.analyze_project(repo) for repo in repos]
        by_name = {}
        for activity in activities:
            existing = by_name.get(activity.name)
            if existing is None or activity.commits_7d > existing.commits_7d:
                by_name[activity.name] = activity
        total = len(by_name)
        active = sum(1 for activity in by_name.values() if activity.commits_7d > 0)
        return active, total
    except Exception:
        return None


def _goal_counts_from_parser(root: Path) -> Optional[Tuple[int, int]]:
    try:
        action_plan = root / "ACTION_PLAN.md"
        # Allow overriding ACTION_PLAN location via state dir only when root file is absent
        state_dir = os.getenv("CORTEX_STATE_DIR")
        if state_dir and not action_plan.exists():
            candidate = Path(state_dir) / "ACTION_PLAN.md"
            if candidate.exists():
                action_plan = candidate
        if not action_plan.exists():
            return (0, 0)

        text = action_plan.read_text(encoding="utf-8")
        # Lightweight count keyed on explicit status markers to make tests deterministic.
        in_progress = len([m for m in re.finditer(r"in_progress", text, re.IGNORECASE)])
        pending = len([m for m in re.finditer(r"pending", text, re.IGNORECASE)])
        return in_progress, pending
    except Exception:
        return None


def _apply_signal_gate_to_briefing(briefing, signal: Dict[str, Union[int, str]]) -> None:
    if signal.get("quality") != "LOW":
        return
    dirty_total = int(signal.get("dirty_total", 0))
    modified = int(signal.get("modified", 0))
    untracked = int(signal.get("untracked", 0))
    briefing.priority_actions = [
        {
            "title": "Reduce working tree noise before trusting recommendations",
            "priority": "HIGH",
            "project": "General",
            "rationale": (
                f"Signal gate active: {dirty_total} local changes "
                f"({modified} modified, {untracked} untracked)."
            ),
            "source": "signal_gate",
            "steps": [
                "Commit or stash active edits by project.",
                "Archive scratch artifacts and generated outputs.",
                "Re-run briefing/status after noise falls below threshold.",
            ],
            "estimated_impact": "high",
        }
    ]
