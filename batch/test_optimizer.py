#!/usr/bin/env python3
"""
Test script for adaptive batch queue optimizer.

Demonstrates:
1. Dynamic work generation (commits, TODOs, test failures)
2. Composite priority scoring
3. Bin packing algorithm
4. Performance tracking
5. Adaptive estimation
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from intelligent_orchestrator import BatchCapacity, BatchWorkItem
from optimizer import (
    AdaptiveEstimator,
    BatchPerformanceTracker,
    CapacityAwareQueueFiller,
    DynamicWorkGenerator,
    integrate_with_orchestrator,
)


def test_work_generation():
    """Test dynamic work generation"""
    print("=" * 80)
    print("TEST 1: Dynamic Work Generation")
    print("=" * 80)
    print()

    generator = DynamicWorkGenerator()

    print("Scanning recent commits (last 24 hours)...")
    commit_work = generator.scan_recent_commits(hours=24)
    print(f"Found {len(commit_work)} commit-based work items")

    for item in commit_work[:3]:
        print(f"  - [{item.priority.upper():9}] {item.title}")
        print(f"    Tokens: {item.total_tokens:,}")
    print()

    print("Scanning TODOs and FIXMEs...")
    todo_work = generator.scan_todos_and_fixmes()
    print(f"Found {len(todo_work)} TODO-based work items")

    for item in todo_work[:3]:
        print(f"  - [{item.priority.upper():9}] {item.title}")
        print(f"    Tokens: {item.total_tokens:,}")
    print()

    print("Scanning test failures...")
    test_work = generator.scan_test_failures()
    print(f"Found {len(test_work)} test failure work items")

    for item in test_work[:3]:
        print(f"  - [{item.priority.upper():9}] {item.title}")
        print(f"    Tokens: {item.total_tokens:,}")
    print()

    total_dynamic = len(commit_work) + len(todo_work) + len(test_work)
    print(f"Total dynamic work generated: {total_dynamic} items")
    print()

    return commit_work + todo_work + test_work


def test_priority_scoring():
    """Test composite priority scoring"""
    print("=" * 80)
    print("TEST 2: Composite Priority Scoring")
    print("=" * 80)
    print()

    # Create sample work items with different characteristics
    items = [
        BatchWorkItem(
            id="urgent-security",
            title="Critical security fix",
            description="Security vulnerability in auth",
            prompt="Fix security issue",
            priority="immediate",
            estimated_input_tokens=10_000,
            estimated_output_tokens=2_000,
            source="security",
            deadline_hours=8,
        ),
        BatchWorkItem(
            id="high-pattern",
            title="Code quality analysis",
            description="Analyze code patterns",
            prompt="Analyze patterns",
            priority="high",
            estimated_input_tokens=30_000,
            estimated_output_tokens=4_000,
            source="pattern",
            deadline_hours=12,
        ),
        BatchWorkItem(
            id="normal-docs",
            title="Update documentation",
            description="Update README",
            prompt="Update docs",
            priority="normal",
            estimated_input_tokens=15_000,
            estimated_output_tokens=3_000,
            source="docs",
            deadline_hours=48,
        ),
        BatchWorkItem(
            id="low-research",
            title="Research new libraries",
            description="Explore alternatives",
            prompt="Research libs",
            priority="low",
            estimated_input_tokens=20_000,
            estimated_output_tokens=5_000,
            source="research",
            deadline_hours=72,
        ),
    ]

    filler = CapacityAwareQueueFiller()

    print("Scoring work items:")
    print()

    for item in items:
        score = filler._calculate_composite_score(item)
        print(f"{item.title:30} | Score: {score:6.1f}")
        print(f"  Priority: {item.priority:9} (base={item.priority_score})")
        print(
            f"  Deadline: {item.deadline_hours:3}h (mult={filler._deadline_multiplier(item.deadline_hours):.1f}x)"
        )
        print(f"  Source:   {item.source:8} (value multiplier applied)")
        print()


def test_bin_packing():
    """Test bin packing algorithm"""
    print("=" * 80)
    print("TEST 3: Bin Packing Algorithm")
    print("=" * 80)
    print()

    # Create capacity with limited token budget
    capacity = BatchCapacity()
    capacity.weekly_token_budget = 1_000_000  # 1M tokens
    capacity.current_weekly_usage = 0  # Start fresh

    available = capacity.available_overnight_tokens()
    if available == 0:
        # Fallback if calculation yields 0
        available = 200_000  # Default to 200K tokens

    print(f"Available tokens: {available:,}")
    print(f"Target (90%):     {int(available * 0.9):,}")
    print()

    # Create diverse work items
    work_items = [
        BatchWorkItem(
            id=f"item-{i}",
            title=f"Work item {i}",
            description=f"Description {i}",
            prompt=f"Prompt {i}",
            priority=["immediate", "high", "normal", "low"][i % 4],
            estimated_input_tokens=20_000 + (i * 5_000),
            estimated_output_tokens=3_000,
            source=["security", "pattern", "docs", "research"][i % 4],
            deadline_hours=8 + (i * 4),
        )
        for i in range(10)
    ]

    filler = CapacityAwareQueueFiller(capacity)

    print("Filling queue with bin packing...")
    selected = filler.fill_queue(work_items, target_utilization=0.9)

    total_tokens = sum(item.total_tokens for item in selected)
    utilization = (total_tokens / available) * 100 if available > 0 else 0

    print(f"Selected:     {len(selected)} / {len(work_items)} items")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Utilization:  {utilization:.1f}%")
    print()

    print("Selected items:")
    for item in selected:
        print(f"  - [{item.priority.upper():9}] {item.title} ({item.total_tokens:,} tokens)")
    print()


def test_performance_tracking():
    """Test performance tracking"""
    print("=" * 80)
    print("TEST 4: Performance Tracking")
    print("=" * 80)
    print()

    tracker = BatchPerformanceTracker()

    # Simulate some task submissions and completions
    print("Simulating task submissions and completions...")

    sample_task = BatchWorkItem(
        id="test-task-1",
        title="Test security scan",
        description="Test task",
        prompt="Test prompt",
        priority="high",
        estimated_input_tokens=30_000,
        estimated_output_tokens=5_000,
        source="security",
        deadline_hours=12,
    )

    # Record submission
    tracker.record_submission(sample_task, "batch-job-123")
    print(f"Recorded submission: {sample_task.id}")

    # Simulate completion (with some variance from estimates)
    tracker.record_completion(
        "test-task-1",
        actual_tokens=(28_000, 6_200),  # Slightly different from estimates
        actual_duration=0.45,
        status="completed",
    )
    print("Recorded completion: test-task-1")
    print()

    # Check accuracy (will be empty if no historical data)
    accuracy = tracker.get_estimation_accuracy(days=30)

    if accuracy:
        print("Estimation accuracy:")
        for source, metrics in accuracy.items():
            print(f"  {source}: {metrics['task_count']} tasks")
            print(f"    Input:  {metrics['input_accuracy_pct']:.0f}% accurate")
            print(f"    Output: {metrics['output_accuracy_pct']:.0f}% accurate")
    else:
        print("Not enough historical data yet (need 3+ completed tasks)")
    print()


def test_adaptive_estimation():
    """Test adaptive estimation learning"""
    print("=" * 80)
    print("TEST 5: Adaptive Estimation")
    print("=" * 80)
    print()

    tracker = BatchPerformanceTracker()
    estimator = AdaptiveEstimator(tracker)

    print("Learning summary:")
    print()
    print(estimator.get_learning_summary())


def test_integration():
    """Test full integration"""
    print("=" * 80)
    print("TEST 6: Full Integration")
    print("=" * 80)
    print()

    print("Running full integration with optimizer...")
    print()

    try:
        selected_work = integrate_with_orchestrator()

        print(f"Generated and optimized: {len(selected_work)} work items")
        print()

        # Group by priority
        by_priority = {}
        for item in selected_work:
            by_priority.setdefault(item.priority, []).append(item)

        print("By priority:")
        for priority in ["immediate", "high", "normal", "low"]:
            count = len(by_priority.get(priority, []))
            if count > 0:
                print(f"  {priority.capitalize():9}: {count:2} items")
        print()

        # Token analysis
        total_tokens = sum(item.total_tokens for item in selected_work)
        avg_tokens = total_tokens / len(selected_work) if selected_work else 0

        print("Token analysis:")
        print(f"  Total:   {total_tokens:,}")
        print(f"  Average: {avg_tokens:,.0f}")
        print()

        # Show top 5
        print("Top 5 priority items:")
        for i, item in enumerate(selected_work[:5], 1):
            print(f"{i}. [{item.priority.upper():9}] {item.title}")
            print(
                f"   Source: {item.source:8} | Tokens: {item.total_tokens:,} | Deadline: {item.deadline_hours}h"
            )
        print()

        print("Integration successful!")

    except Exception as e:
        print(f"Integration failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run all tests"""
    print()
    print("ADAPTIVE BATCH QUEUE OPTIMIZER - TEST SUITE")
    print("=" * 80)
    print()

    try:
        # Test 1: Work generation
        test_work_generation()

        # Test 2: Priority scoring
        test_priority_scoring()

        # Test 3: Bin packing
        test_bin_packing()

        # Test 4: Performance tracking
        test_performance_tracking()

        # Test 5: Adaptive estimation
        test_adaptive_estimation()

        # Test 6: Full integration
        test_integration()

        print()
        print("=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
        print()

    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nTest suite failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
