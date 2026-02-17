"""
Quick test of planning functionality.
"""

from pathlib import Path

from intelligence.planning import PlanExecutor, Planner, PlanPriority
from recommendation_engine import Recommendation, RecommendationEngine


def test_basic_planning():
    """Test basic planning flow."""
    print("🧪 Testing Cortex Planning Module\n")

    # Create some sample recommendations
    recommendations = [
        Recommendation(
            type="coverage",
            title="Improve test coverage for auth module",
            description="Add tests for authentication edge cases",
            priority=85,
            confidence=0.9,
            files=["auth.py", "test_auth.py"],
            steps=[
                "Review existing auth tests",
                "Identify untested edge cases",
                "Write new test cases",
                "Run test suite and verify coverage",
            ],
        ),
        Recommendation(
            type="refactor",
            title="Refactor database connection pooling",
            description="Optimize database connection management",
            priority=70,
            confidence=0.8,
            files=["db.py"],
            steps=[
                "Audit current connection usage",
                "Implement connection pooling",
                "Add connection health checks",
            ],
        ),
    ]

    # Test 1: Create plan from recommendations
    print("1️⃣ Creating plan from recommendations...")
    planner = Planner()
    plan = planner.create_plan_from_recommendations(
        recommendations=recommendations,
        title="Q1 Technical Improvements",
        priority=PlanPriority.HIGH,
    )
    print(f"   ✅ Created plan: {plan.id}")
    print(f"   • Title: {plan.title}")
    print(f"   • Steps: {len(plan.steps)}")
    print(f"   • Estimated time: {plan.estimated_total_time} minutes\n")

    # Test 2: Save and load plan
    print("2️⃣ Saving and loading plan...")
    executor = PlanExecutor()
    executor.save_plan(plan)
    loaded_plan = executor.load_plan(plan.id)
    print(f"   ✅ Plan loaded: {loaded_plan.id}")
    print(f"   • Status: {loaded_plan.status.value}\n")

    # Test 3: Start plan execution
    print("3️⃣ Starting plan execution...")
    executor.start_plan(loaded_plan)
    print(f"   ✅ Plan started: {loaded_plan.status.value}")

    next_step = executor.get_next_step()
    if next_step:
        print(f"   • Next step: {next_step.title}\n")

    # Test 4: Complete first step
    print("4️⃣ Completing first step...")
    if next_step:
        executor.start_step(next_step.id)
        executor.complete_step(next_step.id, notes="Completed successfully")
        print(f"   ✅ Step completed: {next_step.id}")

        progress = executor.get_progress()
        print(f"   • Progress: {progress['completion_pct']:.1f}%")
        print(f"   • Completed: {progress['completed']}/{progress['total_steps']}\n")

    # Test 5: Export to markdown
    print("5️⃣ Exporting plan to markdown...")
    markdown = executor.export_plan_markdown()
    markdown_file = Path("/tmp/test_plan.md")
    markdown_file.write_text(markdown)
    print(f"   ✅ Exported to: {markdown_file}\n")

    # Test 6: List all plans
    print("6️⃣ Listing all plans...")
    plans = executor.list_plans()
    print(f"   ✅ Found {len(plans)} plan(s)")
    for p in plans[:3]:  # Show first 3
        print(
            f"   • [{p['status']}] {p['title']} ({p['progress'].get('completion_pct', 0):.0f}% complete)"
        )
    print()

    print("✅ All tests passed!\n")
    print(f"📝 Plan ID: {plan.id}")
    print(f"📄 Markdown: {markdown_file}")


def test_recommendation_engine_integration():
    """Test planning integration with RecommendationEngine."""
    print("\n🔗 Testing RecommendationEngine Integration\n")

    # Initialize engine
    engine = RecommendationEngine(project_path=Path.cwd())

    # Create plan with auto-generated recommendations
    print("1️⃣ Creating plan from auto-generated recommendations...")
    engine.create_plan(
        title="Auto-generated improvement plan",
        auto_generate=False,  # Skip auto-generation for now
    )
    print("   ⚠️  Skipped (no recommendations to convert)\n")

    # Test getting active plan
    print("2️⃣ Getting active plan...")
    active_plan = engine.get_active_plan()
    if active_plan:
        print(f"   ✅ Active plan: {active_plan.title}")
        print(f"   • Status: {active_plan.status.value}")
    else:
        print("   • No active plan\n")

    print("✅ Integration test complete!\n")


if __name__ == "__main__":
    try:
        test_basic_planning()
        test_recommendation_engine_integration()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
