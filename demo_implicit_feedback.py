#!/usr/bin/env python3
"""
Demo: Implicit Feedback Collection

Shows how implicit feedback signals are collected automatically from user behavior.
"""

import time
from pathlib import Path

from intelligence.feedback.implicit_collector import ImplicitFeedbackCollector


def demo_basic_tracking():
    """Demo basic recommendation tracking and follow detection."""
    print("\n" + "=" * 60)
    print("Demo: Basic Tracking")
    print("=" * 60)

    # Initialize collector
    collector = ImplicitFeedbackCollector()

    # Simulate showing a recommendation to user
    recommendation = {
        "id": "rec_001",
        "title": "Fix failing tests in test_data_quality.py",
        "description": "Run pytest and fix the 3 failing test cases",
        "files": ["cortex/tests/test_data_quality.py"],
        "priority": "high",
        "confidence": 0.85,
    }

    print("\n1. Showing recommendation to user:")
    print(f"   {recommendation['title']}")

    collector.track_recommendation_shown("rec_001", recommendation)

    # Simulate user taking action after some time
    time.sleep(0.5)

    print("\n2. User takes action:")
    print("   'Fix failing tests in test_data_quality.py'")

    collector.track_action_taken(
        action="Fix failing tests in test_data_quality.py",
        files=["cortex/tests/test_data_quality.py"],
    )

    print("\n3. Session stats:")
    stats = collector.get_session_stats()
    print(f"   Recommendations shown: {stats['total_shown']}")
    print(f"   Followed: {stats['followed']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   Actions taken: {stats['actions_taken']}")


def demo_ignore_detection():
    """Demo ignore signal detection."""
    print("\n" + "=" * 60)
    print("Demo: Ignore Detection")
    print("=" * 60)

    collector = ImplicitFeedbackCollector()

    # Show multiple recommendations
    recommendations = [
        {
            "id": "rec_001",
            "title": "Update README documentation",
            "files": ["README.md"],
        },
        {
            "id": "rec_002",
            "title": "Fix type hints in bridge.py",
            "files": ["cortex/bridge.py"],
        },
        {"id": "rec_003", "title": "Add more unit tests", "files": []},
    ]

    print("\n1. Showing 3 recommendations:")
    for rec in recommendations:
        print(f"   - {rec['title']}")
        collector.track_recommendation_shown(rec["id"], rec)

    # User takes unrelated action
    print("\n2. User takes different action:")
    print("   'Refactor session manager code'")

    collector.track_action_taken(
        action="Refactor session manager code", files=["cortex/session_manager.py"]
    )

    # End session - recommendations are marked as ignored
    print("\n3. Session ends - marking ignored recommendations...")
    collector.session_end()

    # Load and display signals
    signals = collector.load_signals()
    print(f"\n4. Signals generated: {len(signals)}")
    for signal in signals:
        print(f"   - {signal.signal_type}: {signal.recommendation_id}")


def demo_override_detection():
    """Demo override signal detection."""
    print("\n" + "=" * 60)
    print("Demo: Override Detection")
    print("=" * 60)

    collector = ImplicitFeedbackCollector()

    # Show recommendation
    recommendation = {
        "id": "rec_001",
        "title": "Run full test suite with coverage",
        "description": "Execute pytest with coverage reporting",
        "files": [],
    }

    print("\n1. Showing recommendation:")
    print(f"   {recommendation['title']}")
    collector.track_recommendation_shown("rec_001", recommendation)

    # User takes similar but different action (override)
    print("\n2. User modifies recommendation:")
    print("   'Run specific test file only'")

    collector.track_action_taken(action="Run specific test file only", files=[])

    # Check if override was detected
    signals = collector.load_signals()
    print(f"\n3. Signals generated: {len(signals)}")
    for signal in signals:
        print(f"   - Type: {signal.signal_type}")
        print(f"   - Similarity: {signal.similarity:.2f}")
        if signal.alternative_taken:
            print(f"   - Alternative: {signal.alternative_taken}")


def demo_statistics():
    """Demo statistics calculation."""
    print("\n" + "=" * 60)
    print("Demo: Statistics Over Time")
    print("=" * 60)

    collector = ImplicitFeedbackCollector()

    # Simulate multiple sessions
    print("\n1. Simulating user sessions...")

    # Session 1: High follow rate
    for i in range(5):
        rec = {
            "id": f"rec_{i:03d}",
            "title": f"Task {i}: Fix issue",
            "files": [f"file_{i}.py"],
        }
        collector.track_recommendation_shown(rec["id"], rec)

    # Follow 3 out of 5
    for i in range(3):
        collector.track_action_taken(
            action=f"Task {i}: Fix issue", files=[f"file_{i}.py"]
        )

    collector.session_end()

    # Session 2: Low follow rate
    for i in range(5, 10):
        rec = {
            "id": f"rec_{i:03d}",
            "title": f"Task {i}: Update docs",
            "files": [f"file_{i}.md"],
        }
        collector.track_recommendation_shown(rec["id"], rec)

    # Follow 1 out of 5
    collector.track_action_taken(
        action="Task 5: Update docs", files=["file_5.md"]
    )

    collector.session_end()

    # Display statistics
    print("\n2. Overall statistics (last 7 days):")
    stats = collector.get_stats(days=7)
    print(f"   Total signals: {stats['total_signals']}")
    print(f"   Follows: {stats['follows']}")
    print(f"   Ignores: {stats['ignores']}")
    print(f"   Overrides: {stats['overrides']}")
    print(f"   Follow rate: {stats['follow_rate']:.1%}")
    print(f"   Avg time to action: {stats['avg_time_to_action']:.2f}s")


def demo_integration_example():
    """Demo integration with recommendation engine."""
    print("\n" + "=" * 60)
    print("Demo: Integration Example")
    print("=" * 60)

    collector = ImplicitFeedbackCollector()

    print("\n1. Simulating daily briefing workflow:")

    # Briefing shows recommendations
    recommendations = [
        {
            "id": "rec_daily_001",
            "title": "Complete validation for Improvement 3",
            "priority": "high",
            "confidence": 0.9,
            "files": ["cortex/tests/test_implicit_feedback.py"],
        },
        {
            "id": "rec_daily_002",
            "title": "Update PRD with implementation status",
            "priority": "medium",
            "confidence": 0.75,
            "files": ["cortex/docs/AI_ENGINEERING_IMPROVEMENTS_PRD.md"],
        },
    ]

    print("\n   /briefing shows recommendations:")
    for rec in recommendations:
        print(f"   - [{rec['priority']}] {rec['title']}")
        collector.track_recommendation_shown(rec["id"], rec)

    # User works on tasks
    print("\n2. User works on tasks:")
    print("   $ pytest cortex/tests/test_implicit_feedback.py")

    collector.track_action_taken(
        action="Run pytest on test_implicit_feedback.py",
        files=["cortex/tests/test_implicit_feedback.py"],
    )

    # End of day
    print("\n3. End of day - session closes")
    collector.session_end()

    # Show results
    print("\n4. Implicit signals collected:")
    signals = collector.load_signals()
    for signal in signals[-2:]:  # Last 2 signals
        print(f"   - {signal.signal_type}: {signal.recommendation_id}")
        if signal.time_to_action:
            print(f"     Time to action: {signal.time_to_action:.1f}s")


def main():
    """Run all demos."""
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Cortex Implicit Feedback Collection Demo               ║")
    print("║  Automatic tracking of follows, ignores, and overrides  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    demo_basic_tracking()
    demo_ignore_detection()
    demo_override_detection()
    demo_statistics()
    demo_integration_example()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    print("\nStorage location: ~/.cortex/implicit_feedback.jsonl")
    print("View signals: cat ~/.cortex/implicit_feedback.jsonl | jq .")
    print()


if __name__ == "__main__":
    main()
