#!/usr/bin/env python3
"""
Outcome Logger - Helper for logging model selection outcomes.

This module provides a simple API for logging task completion outcomes
to be used by the model selection learning system.

Usage:
    from intelligence.outcome_logger import log_task_outcome

    log_task_outcome(
        task_id="task_001",
        task_type="bug_fix",
        description="Fix auth bug",
        model_used="sonnet",
        outcome="success",
        tokens=2500,
        time_seconds=180
    )
"""

from datetime import datetime
from typing import List, Optional

try:
    from intelligence.model_selection.models import ModelOutcomeEntry
    from intelligence.storage import get_storage

    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False


def log_task_outcome(
    task_id: str,
    task_type: str,
    description: str,
    model_used: str,
    outcome: str,
    tokens: int = 0,
    time_seconds: float = 0,
    error_count: int = 0,
    cost_usd: float = 0.0,
    project: str = "",
    files: Optional[List[str]] = None,
    model_recommended_by: str = "rules",
    complexity: str = "moderate",
    confidence: float = 0.6,
) -> bool:
    """
    Log a task outcome for model selection learning.

    Args:
        task_id: Unique task identifier
        task_type: Type of task (bug_fix, implement, refactor, etc.)
        description: Task description (truncated to 200 chars)
        model_used: Model that was used (haiku, sonnet, opus)
        outcome: Task outcome (success, partial, failed)
        tokens: Total tokens used
        time_seconds: Time taken in seconds
        error_count: Number of errors/corrections needed
        cost_usd: Estimated cost in USD
        project: Project name
        files: List of files touched
        model_recommended_by: How model was chosen (rules, learned, manual)
        complexity: Task complexity (simple, moderate, complex)
        confidence: Recommendation confidence (0.0-1.0)

    Returns:
        True if logged successfully, False otherwise
    """
    if not STORAGE_AVAILABLE:
        return False

    try:
        entry = ModelOutcomeEntry(
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            task_type=task_type,
            task_description=description[:200],
            model_used=model_used,
            model_recommended_by=model_recommended_by,
            complexity_classified=complexity,
            confidence=confidence,
            outcome=outcome,
            tokens_used=tokens,
            time_seconds=time_seconds,
            error_count=error_count,
            estimated_cost_usd=cost_usd,
            project_name=project,
            files_touched=files or [],
        )

        storage = get_storage()
        storage.log_model_outcome(entry)
        return True

    except Exception as e:
        # Fail gracefully - logging should never break the application
        print(f"Warning: Failed to log outcome: {e}")
        return False


def log_task_start(
    task_id: str,
    task_type: str,
    description: str,
    recommended_model: str,
    project: str = "",
) -> dict:
    """
    Log the start of a task and return metadata for completion logging.

    Args:
        task_id: Unique task identifier
        task_type: Type of task
        description: Task description
        recommended_model: Model that was recommended
        project: Project name

    Returns:
        Dict with metadata to pass to log_task_outcome
    """
    return {
        "task_id": task_id,
        "task_type": task_type,
        "description": description,
        "recommended_model": recommended_model,
        "project": project,
        "start_time": datetime.now(),
    }


def log_task_completion(
    task_metadata: dict,
    model_used: str,
    outcome: str,
    tokens: int = 0,
    error_count: int = 0,
    cost_usd: float = 0.0,
    files: Optional[List[str]] = None,
) -> bool:
    """
    Log task completion using metadata from log_task_start.

    Args:
        task_metadata: Metadata dict from log_task_start
        model_used: Model that was actually used
        outcome: Task outcome (success, partial, failed)
        tokens: Total tokens used
        error_count: Number of errors/corrections
        cost_usd: Actual cost in USD
        files: Files touched

    Returns:
        True if logged successfully, False otherwise
    """
    start_time = task_metadata.get("start_time", datetime.now())
    time_seconds = (datetime.now() - start_time).total_seconds()

    return log_task_outcome(
        task_id=task_metadata["task_id"],
        task_type=task_metadata["task_type"],
        description=task_metadata["description"],
        model_used=model_used,
        outcome=outcome,
        tokens=tokens,
        time_seconds=time_seconds,
        error_count=error_count,
        cost_usd=cost_usd,
        project=task_metadata.get("project", ""),
        files=files,
    )


def compare_model_performance(
    task_type: Optional[str] = None,
    project: Optional[str] = None,
    min_samples: int = 3,
) -> dict:
    """
    Compare model performance across task types and projects.

    Closes the cross-model intelligence gap: answers "which model
    performs best for this type of work in this project?"

    Args:
        task_type: Filter by task type (optional)
        project: Filter by project (optional)
        min_samples: Minimum samples to include a model (default: 3)

    Returns:
        Dict with model comparison data:
        {
            "by_model": {"sonnet": {"success_rate": 0.85, ...}},
            "by_task_type": {"bug_fix": {"best_model": "opus", ...}},
            "recommendation": "For bug_fix tasks, opus has 92% success rate"
        }
    """
    if not STORAGE_AVAILABLE:
        return {"error": "Storage not available"}

    try:
        storage = get_storage()
        outcome_entries = storage.load_model_outcomes(days=90, task_type=task_type)

        # Filter by project if specified
        if project:
            outcome_entries = [e for e in outcome_entries if e.project_name == project]

        if not outcome_entries:
            return {"error": "No outcome data yet", "by_model": {}, "by_task_type": {}}

        # Aggregate by model
        by_model: dict = {}
        for e in outcome_entries:
            model = e.model_used
            if model not in by_model:
                by_model[model] = {
                    "total": 0,
                    "success": 0,
                    "partial": 0,
                    "failed": 0,
                    "total_tokens": 0,
                    "total_time": 0.0,
                    "total_cost": 0.0,
                }
            stats = by_model[model]
            stats["total"] += 1
            outcome = e.outcome
            if outcome in stats:
                stats[outcome] += 1
            stats["total_tokens"] += e.tokens_used
            stats["total_time"] += e.time_seconds
            stats["total_cost"] += e.estimated_cost_usd

        # Calculate rates
        for model, stats in by_model.items():
            total = stats["total"]
            if total > 0:
                stats["success_rate"] = round(stats["success"] / total, 3)
                stats["avg_tokens"] = int(stats["total_tokens"] / total)
                stats["avg_time_s"] = round(stats["total_time"] / total, 1)
                stats["avg_cost_usd"] = round(stats["total_cost"] / total, 4)

        # Filter by min_samples
        by_model = {m: s for m, s in by_model.items() if s["total"] >= min_samples}

        # Aggregate by task type
        by_task: dict = {}
        for e in outcome_entries:
            tt = e.task_type
            model = e.model_used
            outcome = e.outcome

            if tt not in by_task:
                by_task[tt] = {}
            if model not in by_task[tt]:
                by_task[tt][model] = {"total": 0, "success": 0}

            by_task[tt][model]["total"] += 1
            if outcome == "success":
                by_task[tt][model]["success"] += 1

        # Find best model per task type
        by_task_summary = {}
        for tt, models in by_task.items():
            best_model = None
            best_rate = -1.0
            for model, stats in models.items():
                if stats["total"] >= min_samples:
                    rate = stats["success"] / stats["total"]
                    if rate > best_rate:
                        best_rate = rate
                        best_model = model
            if best_model:
                by_task_summary[tt] = {
                    "best_model": best_model,
                    "success_rate": round(best_rate, 3),
                    "samples": models[best_model]["total"],
                    "all_models": {
                        m: round(s["success"] / s["total"], 3)
                        for m, s in models.items()
                        if s["total"] >= min_samples
                    },
                }

        # Generate recommendation
        recommendations = []
        for tt, summary in by_task_summary.items():
            rate_pct = int(summary["success_rate"] * 100)
            recommendations.append(
                f"For {tt}: {summary['best_model']} ({rate_pct}% success, n={summary['samples']})"
            )

        return {
            "by_model": by_model,
            "by_task_type": by_task_summary,
            "recommendations": recommendations,
            "total_outcomes": len(outcome_entries),
        }

    except Exception as e:
        return {"error": str(e), "by_model": {}, "by_task_type": {}}


# Example usage (for documentation)
if __name__ == "__main__":
    # Example 1: Simple logging
    log_task_outcome(
        task_id="task_001",
        task_type="bug_fix",
        description="Fix authentication bug in user_service.py",
        model_used="sonnet",
        outcome="success",
        tokens=2500,
        time_seconds=180,
        error_count=0,
        cost_usd=0.019,
        project="cortex",
        files=["user_service.py"],
    )

    # Example 2: Start/Complete pattern
    metadata = log_task_start(
        task_id="task_002",
        task_type="implement",
        description="Add user authentication",
        recommended_model="sonnet",
        project="cortex",
    )

    # ... do work ...

    log_task_completion(
        task_metadata=metadata,
        model_used="sonnet",
        outcome="success",
        tokens=5000,
        error_count=2,
        cost_usd=0.038,
        files=["auth.py", "user.py"],
    )

    print("✓ Outcome logging examples complete")
