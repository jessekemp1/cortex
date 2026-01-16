#!/usr/bin/env python3
"""
Complete Example: Model Selection + Outcome Logging

This demonstrates the full Week 1 model selection workflow:
1. Get task recommendation from /next
2. Get model recommendation
3. Execute task
4. Log outcome

Run: python3 examples/model_selection_example.py
"""

import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.model_selection import (
    ContextAwareModelRecommender,
    OrchestrationContext,
)
from intelligence.outcome_logger import log_task_outcome
from recommendation_engine import Recommendation


def example_workflow():
    """Complete workflow example."""

    print("=" * 60)
    print("EXAMPLE: Model Selection + Outcome Logging Workflow")
    print("=" * 60)
    print()

    # Step 1: Get a task recommendation (simulated)
    print("Step 1: Get task recommendation from /next")
    print("-" * 60)

    task = Recommendation(
        type="bug_fix",
        title="Fix authentication timeout",
        description="Users are getting logged out after 5 minutes instead of 30 minutes",
        priority="high",
        confidence=0.85,
        files=["auth/session.py", "auth/middleware.py"],
        related_projects=["cortex"],
        estimated_effort="30 minutes",
        estimated_impact="high",
    )

    print(f"Task: {task.title}")
    print(f"Type: {task.type} | Priority: {task.priority}")
    print(f"Files: {', '.join(task.files)}")
    print()

    # Step 2: Get model recommendation
    print("Step 2: Get model recommendation")
    print("-" * 60)

    recommender = ContextAwareModelRecommender()

    context = OrchestrationContext(
        remaining_budget=5.00,  # $5 remaining in session
        remaining_time=timedelta(hours=2),
        task_priority=task.priority,
        project="cortex",
        files=task.files,
    )

    model_rec = recommender.recommend(
        task_description=task.description,
        task_type=task.type,
        context=context,
    )

    print(f"Recommended Model: {model_rec.model.upper()}")
    print(f"Confidence: {model_rec.confidence:.0%}")
    print(f"Estimated Cost: ${model_rec.estimated_cost_usd:.4f}")
    print(f"Estimated Tokens: ~{model_rec.estimated_tokens}")
    print(f"\nReasoning: {model_rec.reasoning}")
    print()

    # Step 3: Execute task (simulated)
    print("Step 3: Execute task")
    print("-" * 60)
    print("# User works on the task using Sonnet...")
    print("# Task completes successfully")
    print()

    # Step 4: Log outcome
    print("Step 4: Log outcome for learning")
    print("-" * 60)

    task_id = f"task_{uuid4().hex[:8]}"

    success = log_task_outcome(
        task_id=task_id,
        task_type=task.type,
        description=task.description,
        model_used=model_rec.model,
        outcome="success",
        tokens=2850,
        time_seconds=1800,  # 30 minutes
        error_count=1,  # One correction needed
        cost_usd=0.0214,
        project="cortex",
        files=task.files,
        model_recommended_by="rules",
        complexity="moderate",
        confidence=model_rec.confidence,
    )

    if success:
        print(f"✓ Outcome logged: {task_id}")
        print(f"  Model: {model_rec.model}")
        print("  Outcome: success")
        print("  Tokens: 2,850")
        print("  Time: 30 minutes")
        print("  Errors: 1 correction")
        print("  Cost: $0.0214")
    else:
        print("✗ Failed to log outcome")

    print()

    # Show stored data
    print("Step 5: Verify data storage")
    print("-" * 60)

    import subprocess

    result = subprocess.run(
        ["tail", "-1", str(Path.home() / ".cortex/model_outcomes.jsonl")],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        import json

        data = json.loads(result.stdout)
        print("✓ Latest outcome stored:")
        print(f"  Task ID: {data['task_id']}")
        print(f"  Type: {data['task_type']}")
        print(f"  Model: {data['model_used']}")
        print(f"  Outcome: {data['outcome']}")
        print(f"  Tokens: {data['tokens_used']}")

    print()
    print("=" * 60)
    print("✅ WORKFLOW COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run /next to get real recommendations")
    print("  2. Complete tasks and log outcomes")
    print("  3. After ~20 outcomes, Week 2 learning will improve recommendations")
    print()


if __name__ == "__main__":
    example_workflow()
