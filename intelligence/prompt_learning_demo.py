#!/usr/bin/env python3
"""
Demo/Test mode for Prompt Learning - Shows how it works with synthetic data.
"""

import json
from datetime import datetime, timedelta

from prompt_learning import PromptLearningLoop


def create_demo_sessions():
    """Create synthetic conversation sessions for demo purposes."""
    sessions = []
    now = datetime.now()

    # Week 1-2: Heavy debugging work
    debug_prompts = [
        "Debug GRIB validation failing in VortexV2",
        "Fix authentication error in login flow",
        "Investigate why ensemble forecasts are incorrect",
        "Quick fix for broken deployment pipeline",
        "Debug test failures in validation suite",
    ]

    for i, prompt in enumerate(debug_prompts):
        sessions.append(
            {
                "session_id": f"debug_session_{i}",
                "cwd": "/Users/jesse.kemp/Dev/Vortex/VortexV2",
                "start_time": now - timedelta(days=14 - i),
                "prompts": [{"text": prompt, "timestamp": now - timedelta(days=14 - i)}],
                "responses": [{"stop_reason": "end_turn", "error": None}],
                "tools_used": ["Read", "Bash", "Edit", "Test"],
            }
        )

    # Week 2-3: Mix of feature work and research
    mixed_prompts = [
        "Add new forecast visualization to VortexV2",
        "Research best practices for GRIB data compression",
        "Implement batch processing for Alpha Arena",
        "Investigate neural network architectures for trading",
        "Add tests for new ensemble model",
    ]

    for i, prompt in enumerate(mixed_prompts):
        sessions.append(
            {
                "session_id": f"mixed_session_{i}",
                "cwd": (
                    "/Users/jesse.kemp/Dev/alpha_arena"
                    if i % 2
                    else "/Users/jesse.kemp/Dev/Vortex/VortexV2"
                ),
                "start_time": now - timedelta(days=10 - i),
                "prompts": [{"text": prompt, "timestamp": now - timedelta(days=10 - i)}],
                "responses": [{"stop_reason": "end_turn", "error": None}],
                "tools_used": ["Read", "Write", "Test", "WebSearch"],
            }
        )

    # Week 3-4 (recent): Focus on Cortex and research
    recent_prompts = [
        "Build prompt history analyzer for Cortex",
        "Research pattern extraction from conversations",
        "Implement learning loop for Cortex intelligence",
        "Add documentation for prompt learning system",
        "Test prompt analysis on real conversation data",
    ]

    for i, prompt in enumerate(recent_prompts):
        sessions.append(
            {
                "session_id": f"recent_session_{i}",
                "cwd": "/Users/jesse.kemp/Dev/cortex",
                "start_time": now - timedelta(days=5 - i),
                "prompts": [{"text": prompt, "timestamp": now - timedelta(days=5 - i)}],
                "responses": [{"stop_reason": "end_turn", "error": None}],
                "tools_used": ["Write", "Read", "Edit", "Task"],
            }
        )

    return sessions


def run_demo():
    """Run the demo with synthetic data."""
    print("🎭 DEMO MODE - Using synthetic conversation data\n")
    print("=" * 60)

    # Create synthetic sessions
    sessions = create_demo_sessions()
    print(f"Created {len(sessions)} synthetic sessions spanning 4 weeks\n")

    # Initialize learning loop
    loop = PromptLearningLoop()

    # Analyze patterns
    print("Analyzing prompt patterns...")
    patterns = loop.analyzer.analyze_prompt_patterns(sessions)

    print(f"\n📊 DETECTED PATTERNS ({len(patterns)} total)\n")
    for i, pattern in enumerate(patterns[:5], 1):
        print(f"{i}. {pattern.topic}")
        print(f"   Frequency: {pattern.frequency} sessions")
        print(f"   Projects: {', '.join(pattern.projects)}")
        print(f"   Urgency: {pattern.urgency_score:.0%}")
        print(f"   Tools: {', '.join(pattern.tools_used[:3])}")
        print()

    # Analyze priorities
    print("\n🎯 CURRENT PRIORITIES (Last 7 Days)\n")
    priorities = loop.analyzer.analyze_priorities(sessions, lookback_days=7)

    for i, priority in enumerate(priorities, 1):
        arrow = (
            "📈"
            if priority.trend == "increasing"
            else "📉" if priority.trend == "decreasing" else "➡️"
        )
        print(f"{i}. {priority.category.upper()}")
        print(f"   Strength: {priority.strength:.0%} of recent work")
        print(f"   Trend: {arrow} {priority.trend}")
        print(f"   Projects: {', '.join(priority.projects_affected)}")
        print()

    # Detect workflows
    print("\n🔄 WORKFLOW PATTERNS\n")
    workflows = loop.analyzer.detect_workflows(sessions)

    for i, workflow in enumerate(workflows[:3], 1):
        print(f"{i}. {workflow.name}")
        print(f"   Frequency: {workflow.frequency} times")
        print(f"   Success rate: {workflow.success_rate:.0%}")
        print(f"   Avg duration: {workflow.avg_duration_minutes:.0f} minutes")
        print()

    # Generate recommendations
    print("\n💡 GENERATED RECOMMENDATIONS\n")
    recommendations = loop._generate_recommendations(patterns, priorities, workflows)

    for i, rec in enumerate(recommendations[:5], 1):
        confidence_bar = "█" * int(rec.confidence * 10)
        print(f"{i}. [{rec.confidence:.0%}] {confidence_bar}")
        print(f"   {rec.content}")
        print(f"   Based on: {', '.join(rec.based_on)}")
        print()

    # Show category weights
    print("\n⚖️  LEARNING WEIGHTS\n")
    loop._update_learning_weights(patterns, priorities)

    weights_file = loop.cache_dir / "category_weights.json"
    if weights_file.exists():
        with open(weights_file, "r") as f:
            data = json.load(f)

        print("Category weights (multipliers for recommendation confidence):")
        for category, weight in sorted(data["weights"].items(), key=lambda x: x[1], reverse=True):
            arrow = "↑" if weight > 1.0 else "↓" if weight < 1.0 else "→"
            bar = "▰" * int(weight * 5)
            print(f"  {arrow} {category:10s}: {weight:.2f}x {bar}")

    print("\n" + "=" * 60)
    print("\n✨ This is what the system learns from YOUR conversations!")
    print("   The more you use Claude Code, the more personalized it becomes.\n")


if __name__ == "__main__":
    run_demo()
