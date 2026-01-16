#!/usr/bin/env python3
"""
Test /next integration directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from datetime import timedelta

from recommendation_engine import Recommendation

# Test model selection availability
try:
    from intelligence.model_selection import (
        ContextAwareModelRecommender,
        OrchestrationContext,
    )

    print("✓ Model selection imports working")
    MODEL_SELECTION_AVAILABLE = True
except ImportError as e:
    print(f"✗ Model selection imports failed: {e}")
    MODEL_SELECTION_AVAILABLE = False
    sys.exit(1)


def get_model_recommendation(recommendation, budget=5.00):
    """Test the helper function."""
    try:
        recommender = ContextAwareModelRecommender()

        context = OrchestrationContext(
            remaining_budget=budget,
            remaining_time=timedelta(hours=2),
            task_priority=recommendation.priority,
            project=(
                recommendation.related_projects[0] if recommendation.related_projects else "cortex"
            ),
            files=recommendation.files or [],
        )

        model_rec = recommender.recommend(
            task_description=recommendation.description,
            task_type=recommendation.type,
            context=context,
        )

        return {
            "model": model_rec.model,
            "reasoning": model_rec.reasoning,
            "confidence": model_rec.confidence,
            "estimated_cost_usd": model_rec.estimated_cost_usd,
            "estimated_tokens": model_rec.estimated_tokens,
            "alternatives": (model_rec.alternatives[:2] if model_rec.alternatives else []),
        }
    except Exception as e:
        return {"error": str(e)}


# Create a test recommendation
rec = Recommendation(
    type="bug_fix",
    title="Address zombie_process alerts",
    description="Multiple zombie processes detected",
    priority="medium",
    confidence=0.9,
    files=[],
    related_projects=["cortex"],
)

print("✓ Created test recommendation")

# Get model recommendation
model_rec = get_model_recommendation(rec)

if "error" in model_rec:
    print(f"✗ Model recommendation failed: {model_rec['error']}")
    sys.exit(1)

print("✓ Got model recommendation")
print(f"  Model: {model_rec['model']}")
print(f"  Confidence: {model_rec['confidence']:.0%}")
print(f"  Cost: ${model_rec['estimated_cost_usd']:.4f}")

# Add to recommendation (like cli.py does)
rec.model_recommendation = model_rec
print("✓ Added to recommendation object")

# Test display logic (like cli.py does)
model_rec_display = getattr(rec, "model_recommendation", None)

if model_rec_display and "error" not in model_rec_display:
    print("\n✅ Display test PASSED")
    print("\n📊 Recommended Model")
    print("─" * 50)
    print(
        f"Model: {model_rec_display['model'].upper()} (confidence: {model_rec_display['confidence']:.0%})"
    )
    print(
        f"Cost: ~${model_rec_display['estimated_cost_usd']:.4f} (~{model_rec_display['estimated_tokens']} tokens)"
    )
    print(f"\nReasoning: {model_rec_display['reasoning']}")
    if model_rec_display.get("alternatives"):
        print("\nAlternatives:")
        for alt in model_rec_display["alternatives"]:
            print(f"  • {alt['model']}: ${alt['estimated_cost']:.4f} - {alt['note']}")
else:
    print("\n✗ Display test FAILED")
    print(f"model_rec_display: {model_rec_display}")

print("\n✅ Integration test complete")
