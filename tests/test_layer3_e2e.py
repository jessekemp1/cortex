#!/usr/bin/env python3
"""
End-to-end test for Layer 3 (Warning System) implementation.

Tests the core functionality of metric tracking without complex integrations.
"""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

from intelligence.monitoring.metric_tracker import MetricTracker, MetricType


def test_metric_tracking():
    """Test basic metric tracking functionality."""
    print("=" * 60)
    print("Layer 3 E2E Test: Metric Tracking")
    print("=" * 60)
    print()

    tracker = MetricTracker()
    project = "cortex_test"

    # Test 1: Track coverage metric
    print("Test 1: Track coverage metric")
    print("-" * 60)
    tracker.track_coverage(project, 75.5, {"test_files": 50, "total_files": 100})
    print("✓ Successfully tracked coverage metric")
    print()

    # Test 2: Retrieve metrics
    print("Test 2: Retrieve tracked metrics")
    print("-" * 60)
    metrics = tracker.get_metrics(project, MetricType.COVERAGE, days=7)
    assert metrics, "No metrics retrieved"
    latest = metrics[-1]
    print(f"✓ Retrieved {len(metrics)} metric(s)")
    print(f"  Latest value: {latest.metric_value:.2f}%")
    print(f"  Timestamp: {latest.timestamp}")
    print(f"  Metadata: {latest.metadata}")
    print()

    # Test 3: Track multiple metric types
    print("Test 3: Track multiple metric types")
    print("-" * 60)
    tracker.track_commits(project, 15, timeframe="24h", metadata={"branch": "main"})
    tracker.track_violations(project, 3, metadata={"type": "lint_errors"})
    print("✓ Successfully tracked multiple metric types")
    print()

    # Test 4: Retrieve all metrics for project
    print("Test 4: Retrieve all metrics for project")
    print("-" * 60)
    all_metrics = []
    for metric_type in [
        MetricType.COVERAGE,
        MetricType.COMMITS,
        MetricType.VIOLATIONS,
    ]:
        metrics = tracker.get_metrics(project, metric_type, days=7)
        all_metrics.extend(metrics)

    print(f"✓ Retrieved {len(all_metrics)} total metrics")
    for metric in all_metrics:
        print(f"  - {metric.metric_type.value}: {metric.metric_value}")
    print()

    # Test 5: Track time series data
    print("Test 5: Track time series data (simulated)")
    print("-" * 60)
    # Simulate tracking over multiple days
    for i in range(5):
        coverage_value = 70 + i * 2  # Simulated improvement
        tracker.track_coverage(project, coverage_value, {"day": i})

    metrics = tracker.get_metrics(project, MetricType.COVERAGE, days=7)
    print(f"✓ Tracked {len(metrics)} data points over time")

    # Check trend
    if len(metrics) >= 2:
        start_value = metrics[0].metric_value
        end_value = metrics[-1].metric_value
        change = end_value - start_value
        print(f"  Coverage change: {start_value:.1f}% → {end_value:.1f}% ({change:+.1f}%)")
    print()

    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)


def test_metric_persistence():
    """Test that metrics persist across tracker instances."""
    print("\n")
    print("=" * 60)
    print("Layer 3 E2E Test: Metric Persistence")
    print("=" * 60)
    print()

    project = "cortex_persistence_test"

    # Create first tracker and save data
    print("Test: Save metrics with first tracker instance")
    print("-" * 60)
    tracker1 = MetricTracker()
    tracker1.track_coverage(project, 85.0, {"source": "tracker1"})
    print("✓ Saved metric with tracker1")
    print()

    # Create second tracker and retrieve data
    print("Test: Retrieve metrics with second tracker instance")
    print("-" * 60)
    tracker2 = MetricTracker()
    metrics = tracker2.get_metrics(project, MetricType.COVERAGE, days=7)

    assert metrics and len(metrics) > 0, "Failed to retrieve metrics from second tracker"
    print(f"✓ Retrieved {len(metrics)} metric(s) with tracker2")
    latest = metrics[-1]
    print(f"  Value: {latest.metric_value:.1f}%")
    print(f"  Metadata: {latest.metadata}")
    print()
    print("=" * 60)
    print("✓ Persistence test passed!")
    print("=" * 60)


if __name__ == "__main__":
    failed = False

    # Run tests
    try:
        test_metric_tracking()
    except Exception as e:
        print(f"❌ test_metric_tracking failed: {e}")
        failed = True

    try:
        test_metric_persistence()
    except Exception as e:
        print(f"❌ test_metric_persistence failed: {e}")
        failed = True

    print("\n")
    if not failed:
        print("🎉 All Layer 3 E2E tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
