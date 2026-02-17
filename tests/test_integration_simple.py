#!/usr/bin/env python3
"""
Simple integration test for model selection in /next command.
"""

import sys
from datetime import timedelta
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.model_selection import (
    ContextAwareModelRecommender,
    OrchestrationContext,
)
from recommendation_engine import Recommendation


def test_model_recommendation():
    """Test that we can add model recommendations to Recommendation objects."""

    # Create a sample recommendation (like /next would)
    rec = Recommendation(
        type="bug_fix",
        title="Fix auth bug",
        description="Fix authentication bug in user_service.py",
        priority="high",
        confidence=0.85,
        files=["user_service.py"],
        related_projects=["cortex"],
    )

    print("✓ Created Recommendation object")

    # Get model recommendation
    recommender = ContextAwareModelRecommender()

    context = OrchestrationContext(
        remaining_budget=5.00,
        remaining_time=timedelta(hours=2),
        task_priority=rec.priority,
        project=rec.related_projects[0] if rec.related_projects else "cortex",
        files=rec.files or [],
    )

    model_rec = recommender.recommend(
        task_description=rec.description,
        task_type=rec.type,
        context=context,
    )

    print("✓ Got model recommendation")
    print(f"  Model: {model_rec.model}")
    print(f"  Confidence: {model_rec.confidence:.0%}")
    print(f"  Cost: ${model_rec.estimated_cost_usd:.4f}")

    # Add to recommendation
    rec.model_recommendation = {
        "model": model_rec.model,
        "reasoning": model_rec.reasoning,
        "confidence": model_rec.confidence,
        "estimated_cost_usd": model_rec.estimated_cost_usd,
        "estimated_tokens": model_rec.estimated_tokens,
    }

    print("✓ Added model_recommendation to Recommendation object")

    # Verify we can access it
    assert hasattr(rec, "model_recommendation")
    assert rec.model_recommendation["model"] == model_rec.model

    print("\n✅ Integration test PASSED")
    print(f"   Recommendation has model_recommendation: {rec.model_recommendation['model']}")


if __name__ == "__main__":
    test_model_recommendation()
