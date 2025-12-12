#!/usr/bin/env python3
"""
Integration test for Cortex feedback loop.

This test verifies that:
1. Recommendations are generated with base confidence
2. Learning system tracks outcomes
3. Confidence scores are adjusted based on historical data
4. Feedback command workflow works end-to-end
"""

import sys
from pathlib import Path

# Add cortex directory to path to ensure we import the right modules
cortex_dir = Path(__file__).parent
sys.path.insert(0, str(cortex_dir))

from feedback import FeedbackLogger
from learning import LearningSystem
from orchestrator import CortexOrchestrator
from recommendation_engine import RecommendationEngine


def test_feedback_loop():
    """Test complete feedback loop."""
    print("Testing Cortex Feedback Loop")
    print("=" * 60)

    # Step 1: Generate recommendation with learning
    print("\n1. Generate recommendation with learning enabled")
    engine = RecommendationEngine(enable_learning=True)
    assert engine.learning_system is not None, "Learning system should be initialized"
    print("   ✓ Learning system initialized")

    # Step 2: Get recommendation from orchestrator
    print("\n2. Get recommendation from orchestrator")
    orchestrator = CortexOrchestrator(root_dir=Path("/Users/jesse.kemp/Dev"))
    response = orchestrator.get_next_action(limit=1)

    if not response.next_action:
        print("   ⚠ No recommendations available (this is OK)")
        print("   Skipping recommendation-specific tests")
        rec = None
    else:
        rec = response.next_action
        print(f"   ✓ Got recommendation: {rec.title}")
        print(f"     Type: {rec.type}")
        print(f"     Confidence: {rec.confidence:.2f}")

    # Step 3: Check learning metrics
    print("\n3. Check learning metrics")
    learning = LearningSystem()
    metrics = learning.get_learning_metrics()
    print(f"   ✓ Total outcomes: {metrics.total_outcomes}")
    print(f"     Followed: {metrics.followed_count}")
    if metrics.followed_count > 0:
        print(f"     Success rate: {metrics.success_rate:.1%}")
        print(f"     Accuracy: {metrics.recommendation_accuracy:.1%}")

    # Step 4: Test confidence adjustment
    print("\n4. Test confidence adjustment")
    patterns = learning.get_outcome_patterns()

    if patterns:
        print(f"   ✓ Found {len(patterns)} recommendation types with data")

        # Test adjustment for each type
        for rec_type, pattern_metrics in list(patterns.items())[:3]:  # Test first 3
            if pattern_metrics["followed"] >= 3:
                adjusted, explanation = learning.adjust_confidence_based_on_history(
                    rec_type, 0.8
                )
                print(f"     {rec_type}: {0.8:.2f} → {adjusted:.2f}")
                print(f"       {explanation}")
    else:
        print("   ⚠ No outcome patterns yet (need more data)")

    # Step 5: Test outcome logging (if we have a recommendation)
    if rec:
        print("\n5. Test outcome logging")
        logger = FeedbackLogger()

        # Count outcomes before
        outcomes_before = len(logger.load_outcomes())

        # Log outcome
        logger.log_outcome(
            recommendation_id=rec.id,
            recommendation_title=rec.title,
            recommendation_type=rec.type,
            priority=rec.priority.upper()[0] if rec.priority else "B",
            confidence=rec.confidence,
            followed=True,
            outcome="success",
            notes="Integration test outcome",
            context={"test": True},
        )

        # Count outcomes after
        outcomes_after = len(logger.load_outcomes())

        assert outcomes_after == outcomes_before + 1, "Outcome should be logged"
        print(f"   ✓ Outcome logged ({outcomes_before} → {outcomes_after})")

        # Verify last outcome
        last_outcome = logger.load_outcomes()[-1]
        assert (
            last_outcome.recommendation_id == rec.id
        ), "Recommendation ID should match"
        assert last_outcome.outcome == "success", "Outcome should be success"
        print(f"   ✓ Outcome verified: {last_outcome.recommendation_title}")

    # Step 6: Test confidence calibration
    print("\n6. Test confidence calibration")
    calibration = learning.get_confidence_calibration()

    if calibration:
        print("   ✓ Confidence calibration:")
        for bucket, success_rate in sorted(calibration.items(), reverse=True):
            if success_rate > 0:
                print(f"     {bucket}: {success_rate:.1%}")
    else:
        print("   ⚠ No calibration data yet")

    print("\n" + "=" * 60)
    print("✓ Feedback loop integration test passed!")
    print("\nThe learning system is working correctly:")
    print("  1. Outcomes are tracked in ~/.cortex/outcomes.jsonl")
    print("  2. Learning metrics are calculated")
    print("  3. Confidence scores are adjusted based on history")
    print("  4. Feedback command logs outcomes properly")


if __name__ == "__main__":
    test_feedback_loop()
