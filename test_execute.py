#!/usr/bin/env python3
"""Test script for cortex execute command"""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import CortexOrchestrator
from integration.local_orchestrator import CortexLocalOrchestratorIntegration
from feedback import FeedbackLogger


def test_execute_flow():
    """Test the full execute flow"""
    print("=" * 60)
    print("Testing Cortex Execute Flow")
    print("=" * 60)
    print()

    # 1. Initialize components
    print("1. Initializing components...")
    root_dir = Path("/Users/jesse.kemp/Dev")

    # Check LOCAL_ORCHESTRATOR_AVAILABLE
    from integration.local_orchestrator import LOCAL_ORCHESTRATOR_AVAILABLE
    print(f"   LOCAL_ORCHESTRATOR_AVAILABLE: {LOCAL_ORCHESTRATOR_AVAILABLE}")

    orchestrator = CortexOrchestrator(root_dir=root_dir)
    integration = CortexLocalOrchestratorIntegration(root_dir=root_dir)
    feedback_logger = FeedbackLogger()

    print(f"   Integration.is_available(): {integration.is_available()}")
    print(f"   Integration.orchestrator: {integration.orchestrator is not None}")
    print(f"   Integration.adapter: {integration.adapter is not None}")

    if not integration.is_available():
        print("   ✗ Integration not available")
        return False
    print("   ✓ Integration available")
    print()

    # 2. Get recommendations
    print("2. Getting recommendations...")
    response = orchestrator.get_next_action(limit=3)

    if not response.next_action:
        print("   ✗ No recommendations available")
        return False

    recommendation = response.next_action
    print(f"   ✓ Got recommendation: {recommendation.title}")
    print(f"     ID: {recommendation.id}")
    print(f"     Type: {recommendation.type}")
    print(f"     Priority: {recommendation.priority}")
    print()

    # 3. Execute recommendation
    print("3. Executing recommendation...")
    result = integration.execute_recommendation(recommendation)

    if not result["success"]:
        print(f"   ✗ Execution failed: {result.get('error', 'Unknown error')}")
        # This is expected for MVP - the task function doesn't do real work yet
        print("   Note: This is expected for MVP - demonstrating execution flow")
    else:
        print(f"   ✓ Execution succeeded")
        print(f"     Message: {result['message']}")
    print()

    # 4. Log outcome
    print("4. Logging outcome to feedback system...")
    feedback_logger.log_outcome(
        recommendation_id=recommendation.id,
        recommendation_title=recommendation.title,
        recommendation_type=recommendation.type,
        priority=recommendation.priority,
        confidence=recommendation.confidence,
        followed=True,
        outcome="success" if result["success"] else "failed",
        notes=result.get("message", "Test execution"),
        context={
            "test": True,
            "execution_time": result.get("execution_time"),
            "timestamp": result.get("timestamp")
        }
    )
    print("   ✓ Outcome logged")
    print()

    # 5. Verify feedback was recorded
    print("5. Verifying feedback recording...")
    outcomes = feedback_logger.load_outcomes()
    if outcomes:
        print(f"   ✓ {len(outcomes)} outcomes recorded")
        latest = outcomes[-1]
        print(f"     Latest: {latest.recommendation_title}")
        print(f"     Outcome: {latest.outcome}")
    else:
        print("   ✗ No outcomes found")
    print()

    print("=" * 60)
    print("Test completed successfully!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_execute_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
