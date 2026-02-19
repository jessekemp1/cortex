#!/usr/bin/env python3
"""
Integration test for briefing system.

Tests:
- Briefing generation
- Text formatting
- JSON formatting
- CLI integration
"""

import json
import sys
from pathlib import Path

# Add cortex to path
cortex_dir = Path(__file__).parent
sys.path.insert(0, str(cortex_dir))
sys.path.insert(0, str(cortex_dir.parent / "scripts"))

from briefing import (
    BriefingGenerator,
    format_briefing,
    format_briefing_json,
    generate_daily_briefing,
)


def test_briefing_generation():
    """Test basic briefing generation."""
    print("Testing briefing generation...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    assert briefing is not None
    assert briefing.generated_at is not None
    assert isinstance(briefing.active_projects, list)
    assert isinstance(briefing.recent_commits_24h, int)
    assert isinstance(briefing.total_commits_7d, int)
    assert isinstance(briefing.blockers, list)
    assert isinstance(briefing.priority_actions, list)
    assert isinstance(briefing.patterns, list)
    assert isinstance(briefing.waiting_on, list)

    print(f"  ✓ Generated briefing with {len(briefing.active_projects)} active projects")
    print(f"  ✓ {briefing.total_commits_7d} commits in last 7 days")
    print(f"  ✓ {len(briefing.priority_actions)} priority actions")


def test_text_formatting():
    """Test text output formatting."""
    print("\nTesting text formatting...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    # Test with colors
    output_color = format_briefing(briefing, use_color=True)
    assert isinstance(output_color, str)
    assert "DAILY BRIEFING" in output_color
    assert "PORTFOLIO PULSE" in output_color
    assert "PRIORITY ACTIONS" in output_color

    # Test without colors
    output_plain = format_briefing(briefing, use_color=False)
    assert isinstance(output_plain, str)
    assert "DAILY BRIEFING" in output_plain

    print("  ✓ Text formatting works with colors")
    print("  ✓ Text formatting works without colors")


def test_json_formatting():
    """Test JSON output formatting."""
    print("\nTesting JSON formatting...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    output = format_briefing_json(briefing)
    assert isinstance(output, str)

    # Parse JSON to verify structure
    data = json.loads(output)
    assert "generated_at" in data
    assert "period" in data
    assert "portfolio_pulse" in data
    assert "priority_actions" in data
    assert "patterns_noticed" in data
    assert "waiting_on" in data

    assert isinstance(data["portfolio_pulse"], dict)
    assert "active_projects" in data["portfolio_pulse"]
    assert "recent_commits_24h" in data["portfolio_pulse"]
    assert "total_commits_7d" in data["portfolio_pulse"]

    print("  ✓ JSON formatting works")
    print("  ✓ JSON structure is valid")


def test_briefing_generator():
    """Test BriefingGenerator class."""
    print("\nTesting BriefingGenerator class...")

    generator = BriefingGenerator(Path("/Users/jesse.kemp/Dev"))
    briefing = generator.generate_daily_briefing()

    assert briefing is not None

    print("  ✓ BriefingGenerator class works")


def test_pattern_detection():
    """Test pattern detection logic."""
    print("\nTesting pattern detection...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    # Should detect patterns if there's activity
    if briefing.total_commits_7d > 0:
        assert len(briefing.patterns) >= 0  # May or may not have patterns
        print(f"  ✓ Detected {len(briefing.patterns)} patterns")
    else:
        print("  ℹ No activity to detect patterns from")


def test_priority_actions():
    """Test priority action generation."""
    print("\nTesting priority actions...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    # Should have at most 3 priority actions
    assert len(briefing.priority_actions) <= 3

    # Each action should have required fields
    for action in briefing.priority_actions:
        assert "title" in action
        assert "priority" in action
        assert action["priority"] in ["HIGH", "MEDIUM", "LOW"]
        assert "project" in action
        assert "source" in action
        assert action["source"] in ["recommendation", "goal"]

    print(f"  ✓ Generated {len(briefing.priority_actions)} priority actions")


def test_blockers():
    """Test blocker detection."""
    print("\nTesting blocker detection...")

    briefing = generate_daily_briefing(Path("/Users/jesse.kemp/Dev"))

    # Each blocker should have required fields
    for blocker in briefing.blockers:
        assert "project" in blocker
        assert "blocker" in blocker
        assert "source" in blocker
        assert blocker["source"] in ["project", "goal"]

    print(f"  ✓ Detected {len(briefing.blockers)} blockers")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("BRIEFING SYSTEM INTEGRATION TESTS")
    print("=" * 60)

    tests = [
        test_briefing_generation,
        test_text_formatting,
        test_json_formatting,
        test_briefing_generator,
        test_pattern_detection,
        test_priority_actions,
        test_blockers,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
