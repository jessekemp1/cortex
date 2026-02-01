#!/usr/bin/env python3
"""
Demo script for the Cortex Prompt Versioning System.

Shows:
- Loading templates from registry
- Variable rendering
- A/B testing
- Quality tracking
"""

from cortex.prompts.ab_testing import ABTestManager, simple_ab_test
from cortex.prompts.base import PromptTemplate
from cortex.prompts.registry import get_registry


def demo_basic_usage():
    """Demonstrate basic template loading and rendering."""
    print("=" * 60)
    print("DEMO 1: Basic Template Usage")
    print("=" * 60)

    registry = get_registry()

    # Load briefing template
    template = registry.get_prompt("briefing_generation")

    if template:
        print(f"\nLoaded template: {template.name} v{template.version}")
        print(f"Description: {template.description}")
        print(f"Required variables: {template.variables}")

        # Render with sample data
        result = template.render(
            date="2026-02-01",
            portfolio_pulse="3 active projects, 2 with commits in last 24h",
            active_goals="Goal 1: Complete VortexV2 testing (75% complete, in progress)",
            recent_activity="15 commits across projects in last 24h",
        )

        print("\n--- Rendered Template ---")
        print(result[:500] + "..." if len(result) > 500 else result)
    else:
        print("Template not found")


def demo_list_templates():
    """Demonstrate listing all available templates."""
    print("\n\n" + "=" * 60)
    print("DEMO 2: List All Templates")
    print("=" * 60)

    registry = get_registry()
    templates = registry.list_prompts()

    print(f"\nFound {len(templates)} templates:")
    for t in templates:
        print(f"\n  • {t['name']} ({t['version']})")
        print(f"    Description: {t['description'][:60]}...")
        print(f"    Variables: {', '.join(t['variables'][:3])}")
        if t.get("usage_count", 0) > 0:
            print(f"    Usage: {t['usage_count']} times")


def demo_ab_testing():
    """Demonstrate A/B testing functionality."""
    print("\n\n" + "=" * 60)
    print("DEMO 3: A/B Testing")
    print("=" * 60)

    # Simulate 100 users
    print("\nRunning 50/50 A/B test for 100 users...")

    variants = {"v1": 0, "v2": 0}

    for i in range(100):
        variant = simple_ab_test(
            prompt_name="recommendation_generation",
            user_id=f"user{i}",
            control="v1",
            treatment="v2",
        )
        variants[variant] += 1

    print("\nResults:")
    print(f"  v1 (control):  {variants['v1']} users ({variants['v1']}%)")
    print(f"  v2 (treatment): {variants['v2']} users ({variants['v2']}%)")

    # Test consistency
    print("\n\nTesting assignment consistency...")
    variant1 = simple_ab_test("test", "user42", "v1", "v2")
    variant2 = simple_ab_test("test", "user42", "v1", "v2")
    print(f"  First assignment:  {variant1}")
    print(f"  Second assignment: {variant2}")
    print(f"  Consistent: {variant1 == variant2} ✅" if variant1 == variant2 else "  ❌ INCONSISTENT")

    # Weighted test
    print("\n\nRunning weighted test (80% v1, 20% v2)...")
    manager = ABTestManager()

    weighted_variants = {"v1": 0, "v2": 0}
    for i in range(100):
        variant = manager.get_variant(
            prompt_name="weighted_test",
            user_id=f"user{i}",
            variants={"v1": 0.8, "v2": 0.2},
        )
        weighted_variants[variant] += 1

    print("\nResults:")
    print(f"  v1 (80%): {weighted_variants['v1']} users ({weighted_variants['v1']}%)")
    print(f"  v2 (20%): {weighted_variants['v2']} users ({weighted_variants['v2']}%)")


def demo_quality_tracking():
    """Demonstrate quality tracking."""
    print("\n\n" + "=" * 60)
    print("DEMO 4: Quality Tracking")
    print("=" * 60)

    # Create a test template
    template = PromptTemplate(
        name="demo_template",
        version="1.0.0",
        template="Demo template for {purpose}",
        variables=["purpose"],
        description="Demo template",
    )

    print("\nInitial state:")
    print(f"  Usage count: {template.metadata.get('usage_count', 0)}")
    print(f"  Quality score: {template.metadata.get('avg_quality_score', 'None')}")

    # Record usage
    print("\nRecording 5 uses...")
    for _ in range(5):
        template.record_usage()

    print(f"  Usage count: {template.metadata['usage_count']}")

    # Record quality scores
    print("\nRecording quality scores...")
    scores = [0.85, 0.90, 0.88, 0.92, 0.87]
    for score in scores:
        template.record_quality_score(score)
        print(f"  Added score: {score}")

    print("\nFinal metrics:")
    print(f"  Usage count: {template.metadata['usage_count']}")
    print(f"  Avg quality: {template.metadata['avg_quality_score']:.2f}")
    print(f"  Score history: {len(template.metadata['quality_scores'])} entries")


def demo_version_comparison():
    """Demonstrate version comparison."""
    print("\n\n" + "=" * 60)
    print("DEMO 5: Version Comparison")
    print("=" * 60)

    v1 = PromptTemplate(name="test", version="1.0.0", template="", variables=[])
    v2 = PromptTemplate(name="test", version="1.0.1", template="", variables=[])
    v3 = PromptTemplate(name="test", version="2.0.0", template="", variables=[])

    print("\nComparing versions:")
    print(f"  v1.0.0 < v1.0.1: {v1.compare_version(v2) == -1} ✅")
    print(f"  v1.0.1 > v1.0.0: {v2.compare_version(v1) == 1} ✅")
    print(f"  v1.0.0 == v1.0.0: {v1.compare_version(v1) == 0} ✅")
    print(f"  v1.0.0 < v2.0.0: {v1.compare_version(v3) == -1} ✅")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("CORTEX PROMPT VERSIONING SYSTEM - DEMO")
    print("=" * 60)

    demo_basic_usage()
    demo_list_templates()
    demo_ab_testing()
    demo_quality_tracking()
    demo_version_comparison()

    print("\n\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    print("\nFor more information, see cortex/prompts/README.md")
    print("Run tests with: pytest cortex/tests/test_prompts.py -v\n")


if __name__ == "__main__":
    main()
