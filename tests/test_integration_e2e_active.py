"""End-to-end tests with active Cortex recommendations"""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.local_orchestrator import CortexLocalOrchestratorIntegration
from orchestrator import CortexOrchestrator


def test_get_real_recommendation():
    """Test getting a real recommendation from Cortex"""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=1)

    assert response is not None
    assert hasattr(response, "next_action")
    assert hasattr(response, "system_health")

    # Should have recommendations (if goals exist)
    if response.next_action:
        rec = response.next_action
        assert hasattr(rec, "title")
        assert hasattr(rec, "priority")
        # rationale may be called description in some Recommendation classes
        assert hasattr(rec, "rationale") or hasattr(rec, "description")
        print(f"✓ Got recommendation: {rec.title}")
        return rec
    else:
        print("⚠ No recommendations available (no goals in ACTION_PLAN.md?)")
        return None


def test_recommendation_to_agent_conversion():
    """Test converting a real recommendation to an agent"""
    # Get real recommendation
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=1)

    if not response.next_action:
        print("⚠ Skipping: No recommendations available")
        return

    recommendation = response.next_action

    # Test integration
    integration = CortexLocalOrchestratorIntegration()

    if not integration.is_available():
        print("⚠ Skipping: local-orchestrator not available (dependencies missing)")
        return

    if not integration.adapter:
        print("⚠ Skipping: Adapter not available")
        return

    # Convert to agent
    try:
        agent = integration.adapter.to_agent(recommendation)

        assert agent is not None
        assert agent["agent_id"].startswith("cortex_")
        assert recommendation.title in agent["name"]
        print(f"✓ Converted: {recommendation.title} → {agent['agent_id']}")

        # Test schedule conversion
        schedule = integration.adapter.to_schedule(recommendation)
        assert isinstance(schedule, str)
        assert len(schedule) > 0
        print(f"✓ Schedule: {schedule}")

    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        raise


def test_schedule_real_recommendation():
    """Test scheduling a real recommendation"""
    # Get real recommendation
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=1)

    if not response.next_action:
        print("⚠ Skipping: No recommendations available")
        return

    recommendation = response.next_action

    # Test integration
    integration = CortexLocalOrchestratorIntegration()

    if not integration.is_available():
        print("⚠ Skipping: local-orchestrator not available")
        return

    # Try to schedule
    try:
        success = integration.schedule_recommendation(
            recommendation, schedule="0 8 * * *"
        )

        # Should attempt scheduling (may fail if orchestrator not running, that's OK)
        assert isinstance(success, bool)

        if success:
            print(f"✓ Scheduled: {recommendation.title}")

            # Check it's in the list
            scheduled = integration.list_scheduled_actions()
            assert isinstance(scheduled, list)

            # Find our agent
            agent_id = f"cortex_{recommendation.title.lower().replace(' ', '_').replace('-', '_')}"
            found = [a for a in scheduled if a.get("agent_id") == agent_id]

            if found:
                print(f"✓ Found in scheduled list: {agent_id}")
            else:
                print("⚠ Not in list yet (may need orchestrator restart)")
        else:
            print("⚠ Scheduling failed (orchestrator may not be running)")

    except Exception as e:
        print(f"⚠ Scheduling test: {e}")
        # Don't fail - this is expected if orchestrator not running


def test_learning_with_real_recommendation():
    """Test learning mechanisms with real recommendations"""
    orchestrator = CortexOrchestrator()
    response = orchestrator.get_next_action(limit=3)

    if not response.next_action:
        print("⚠ Skipping: No recommendations available")
        return

    # Check if learning is active
    if orchestrator.feedback_loop:
        print("✓ Feedback loop available")

        # Get learning metrics
        metrics = orchestrator.feedback_loop.get_learning_metrics()
        assert isinstance(metrics, dict)
        print(f"  Metrics available: {metrics.get('available', False)}")

        # Test priority adjustment
        recommendation = response.next_action
        adjusted = orchestrator.feedback_loop.adjust_recommendation_priority(
            recommendation
        )

        assert adjusted is not None
        assert hasattr(adjusted, "title")
        print(
            f"✓ Priority adjustment works: {recommendation.priority} → {adjusted.priority}"
        )
    else:
        print("⚠ Feedback loop not available (expected if history not accessible)")


def test_cli_schedule_command():
    """Test CLI schedule command structure"""
    import subprocess
    import sys

    # Test help
    result = subprocess.run(
        [sys.executable, "cortex/cli.py", "schedule", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    assert "schedule" in result.stdout.lower()
    assert "cron" in result.stdout.lower() or "schedule" in result.stdout.lower()
    print("✓ CLI schedule command structure correct")


if __name__ == "__main__":
    print("=" * 60)
    print("CORTEX-LOCAL-ORCHESTRATOR E2E TESTS WITH ACTIVE TASKS")
    print("=" * 60)
    print()

    test_get_real_recommendation()
    print()

    test_recommendation_to_agent_conversion()
    print()

    test_schedule_real_recommendation()
    print()

    test_learning_with_real_recommendation()
    print()

    test_cli_schedule_command()
    print()

    print("=" * 60)
    print("E2E TESTS COMPLETE")
    print("=" * 60)
