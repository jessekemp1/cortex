#!/usr/bin/env python3
"""
Example: Cortex Learning System Workflow

Demonstrates:
1. Getting recommendations
2. Logging outcomes
3. Seeing learning metrics
4. Observing confidence adjustments
"""

from pathlib import Path
from feedback import FeedbackLogger
from learning import LearningSystem
from orchestrator import CortexOrchestrator


def main():
    print("=" * 60)
    print("CORTEX LEARNING SYSTEM - EXAMPLE WORKFLOW")
    print("=" * 60)
    print()

    # Initialize components
    logger = FeedbackLogger()
    learning = LearningSystem()
    orchestrator = CortexOrchestrator(root_dir=Path("/Users/jesse.kemp/Dev"))

    # Step 1: Get a recommendation
    print("STEP 1: Get Recommendation")
    print("-" * 60)
    response = orchestrator.get_next_action(limit=1)

    if response.next_action:
        rec = response.next_action
        print(f"Title: {rec.title}")
        print(f"Type: {rec.type}")
        print(f"Priority: {rec.priority}")
        print(f"Confidence: {rec.confidence:.2f}")
        print(f"Rationale: {rec.rationale[:200]}...")
        print()

        # Step 2: Simulate following the recommendation and logging outcome
        print("STEP 2: Log Outcome")
        print("-" * 60)
        print("Simulating: User followed recommendation with SUCCESS outcome")

        logger.log_outcome(
            recommendation_id=rec.id,
            recommendation_title=rec.title,
            recommendation_type=rec.type,
            priority=rec.priority,
            confidence=rec.confidence,
            followed=True,
            outcome="success",
            notes="Example workflow - simulated success",
            context={
                "project": rec.related_projects[0] if rec.related_projects else "unknown"
            }
        )
        print("✓ Outcome logged")
        print()

    # Step 3: Show learning metrics
    print("STEP 3: Learning Metrics")
    print("-" * 60)
    metrics = learning.get_learning_metrics()

    print(f"Total Outcomes: {metrics.total_outcomes}")
    print(f"Followed: {metrics.followed_count}")
    if metrics.followed_count > 0:
        print(f"Success Rate: {metrics.success_rate:.1%}")
        print(f"Recommendation Accuracy: {metrics.recommendation_accuracy:.1%}")
    print()

    # Step 4: Show confidence calibration
    if metrics.confidence_calibration:
        print("STEP 4: Confidence Calibration")
        print("-" * 60)
        for bucket, rate in sorted(metrics.confidence_calibration.items(), reverse=True):
            if rate > 0:
                print(f"  {bucket}: {rate:.1%}")
        print()

    # Step 5: Show outcome patterns
    if metrics.outcome_patterns:
        print("STEP 5: Outcome Patterns")
        print("-" * 60)
        sorted_patterns = sorted(
            metrics.outcome_patterns.items(),
            key=lambda x: x[1]['success_rate'],
            reverse=True
        )
        for rec_type, pattern in sorted_patterns[:3]:  # Top 3
            if pattern['followed'] > 0:
                print(f"  {rec_type}:")
                print(f"    Success Rate: {pattern['success_rate']:.1%} ({pattern['followed']} outcomes)")
        print()

    # Step 6: Demonstrate confidence adjustment
    print("STEP 6: Confidence Adjustment Example")
    print("-" * 60)
    base_confidence = 0.7

    for rec_type in ["goal_progress", "blocker_resolution", "optimization"]:
        if rec_type in metrics.outcome_patterns:
            adjusted, explanation = learning.adjust_confidence_based_on_history(
                recommendation_type=rec_type,
                base_confidence=base_confidence
            )
            print(f"{rec_type}:")
            print(f"  Base: {base_confidence:.2f} → Adjusted: {adjusted:.2f}")
            print(f"  {explanation}")
            print()

    print("=" * 60)
    print("To use this in real workflow:")
    print("  1. cortex next              # Get recommendation")
    print("  2. [Follow recommendation]")
    print("  3. cortex feedback --outcome success|partial|failed")
    print("  4. cortex learn             # See metrics")
    print("=" * 60)


if __name__ == "__main__":
    main()
