#!/usr/bin/env python3
"""
Test anti-pattern detection on real project data.

Run this script to check for validated-but-undeployed code in
actual VortexV2 and alpha_arena projects.
"""

from pathlib import Path

from orchestration.anti_pattern_detector import AntiPatternDetector, Severity


def main():
    """Run detection and print results."""
    root_dir = Path(__file__).parent.parent
    print(f"Scanning projects in: {root_dir}\n")

    detector = AntiPatternDetector(db=None, root_dir=root_dir)

    # Run detection
    print("Running anti-pattern detection...")
    alerts = detector.detect_all()

    # Print results
    print(f"\n{'='*70}")
    print("ANTI-PATTERN DETECTION RESULTS")
    print(f"{'='*70}\n")

    if not alerts:
        print("No anti-patterns detected!")
        return

    print(f"Found {len(alerts)} anti-patterns:\n")

    # Group by severity
    by_severity = {}
    for alert in alerts:
        severity = alert.severity.value
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append(alert)

    # Print by severity (critical first)
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        severity_alerts = by_severity.get(severity.value, [])
        if not severity_alerts:
            continue

        print(f"\n{severity.value.upper()} SEVERITY ({len(severity_alerts)}):")
        print("-" * 70)

        for alert in severity_alerts:
            print(f"\nProject: {alert.project}")
            print(f"Type: {alert.pattern_type.value}")
            print(f"Item: {alert.validated_item}")
            print(f"Source: {alert.validation_source}")

            if alert.improvement_metrics:
                print(f"Metrics: {alert.improvement_metrics}")

            if alert.production_item:
                print(f"Current Production: {alert.production_item}")

            print(f"Action: {alert.suggested_action}")

            if alert.estimated_effort:
                print(f"Effort: {alert.estimated_effort}")

            if alert.evidence:
                print("Evidence:")
                for evidence in alert.evidence[:3]:  # Show first 3
                    print(f"  - {evidence}")

    print(f"\n{'='*70}\n")

    # Summary
    critical_count = len(by_severity.get(Severity.CRITICAL.value, []))
    high_count = len(by_severity.get(Severity.HIGH.value, []))

    if critical_count > 0:
        print(f"CRITICAL: {critical_count} validated improvements need immediate deployment")
    if high_count > 0:
        print(f"HIGH: {high_count} validated improvements should be deployed soon")

    print("\nRecommendation: Review alerts and create deployment plan.")


if __name__ == "__main__":
    main()
