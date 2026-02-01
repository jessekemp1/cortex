#!/usr/bin/env python3
"""
Data Quality Framework Demo

Demonstrates the quality tracking system with real Cortex data.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

from feedback import FeedbackLogger, OutcomeEntry
from intelligence.quality.data_quality import DataQualityTracker
from intelligence.quality.report import generate_markdown_report


def main():
    """Demo the data quality framework."""
    print("=" * 60)
    print("Cortex Data Quality Framework Demo")
    print("=" * 60)
    print()

    # Initialize tracker
    tracker = DataQualityTracker()

    # Load real outcomes
    logger = FeedbackLogger()
    outcomes = logger.load_outcomes()

    print(f"Loaded {len(outcomes)} outcomes from ~/.cortex/outcomes.jsonl")
    print()

    if outcomes:
        # Assess first few outcomes
        print("Assessing quality of recent outcomes...")
        print()

        for i, outcome in enumerate(outcomes[-5:], 1):
            quality = tracker.assess_outcome(outcome)

            print(f"{i}. {outcome.recommendation_title[:50]}...")
            print(f"   Overall Quality: {quality.overall_score():.1%}")
            print(
                f"   Completeness: {quality.completeness:.1%} | "
                f"Consistency: {quality.consistency:.1%} | "
                f"Accuracy: {quality.accuracy:.1%}"
            )
            print(
                f"   Timeliness: {quality.timeliness:.1%} | "
                f"Uniqueness: {quality.uniqueness:.1%} | "
                f"Validity: {quality.validity:.1%}"
            )
            print()

    # Generate comprehensive report
    print("Generating comprehensive quality report...")
    print()

    report = tracker.get_quality_report()

    print(f"Total items assessed: {report.total_items_assessed}")
    print(f"Overall quality score: {report.overall_quality():.1%}")
    print()

    # Generate markdown report
    markdown = generate_markdown_report(report)

    print("=" * 60)
    print("Full Quality Report (Markdown)")
    print("=" * 60)
    print()
    print(markdown)

    # Save report
    report_path = Path.home() / ".cortex" / "quality_report.md"
    with open(report_path, "w") as f:
        f.write(markdown)

    print()
    print(f"Report saved to: {report_path}")
    print()

    # Demo: Create a sample outcome with quality assessment
    print("=" * 60)
    print("Demo: Creating new outcome with quality tracking")
    print("=" * 60)
    print()

    sample_outcome = OutcomeEntry(
        timestamp=datetime.now().isoformat(),
        recommendation_id="demo_rec_001",
        recommendation_title="Implement data quality framework",
        recommendation_type="feature",
        priority="A",
        confidence=0.95,
        followed=True,
        outcome="success",
        notes="Successfully implemented all 6 quality dimensions",
        context={"project": "cortex", "improvement": "7"},
    )

    quality = tracker.assess_outcome(sample_outcome)

    print("Sample Outcome Quality Assessment:")
    print(f"  Title: {sample_outcome.recommendation_title}")
    print(f"  Overall Quality: {quality.overall_score():.1%}")
    print()
    print("  Dimension Breakdown:")
    print(f"    Completeness:  {quality.completeness:.1%}")
    print(f"    Consistency:   {quality.consistency:.1%}")
    print(f"    Accuracy:      {quality.accuracy:.1%}")
    print(f"    Timeliness:    {quality.timeliness:.1%}")
    print(f"    Uniqueness:    {quality.uniqueness:.1%}")
    print(f"    Validity:      {quality.validity:.1%}")
    print()

    # Track quality
    tracker.track_quality("outcome", quality)

    print("Quality tracked successfully!")
    print()
    print("=" * 60)
    print("Demo Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
