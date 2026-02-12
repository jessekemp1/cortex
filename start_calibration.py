#!/usr/bin/env python3
"""
Cortex Calibration Starter - Month 1, Week 1
Quick script to record your first development task predictions
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from metrics_tracker import MetricsTracker

CURRENT_TASK_FILE = Path.home() / ".claude" / "portfolio" / "current_task.json"


def start_task_prediction():
    """Interactive task prediction recording"""
    tracker = MetricsTracker()

    print("\n=== CORTEX DEVELOPMENT VELOCITY CALIBRATION ===")
    print("Month 1, Week 1: Recording prediction for task")
    print()

    # Collect task information
    task = input("Task description: ")
    project = input("Project (VortexV2/AlphaArena/Cortex/Other): ")

    print("\n--- Prediction ---")
    print("Estimate how long this will take WITHOUT Cortex (baseline)")
    baseline_min = int(input("Baseline time (minutes): "))

    print("\nHow confident are you in this estimate?")
    print("0.50 = Not very confident (50/50)")
    print("0.70 = Somewhat confident")
    print("0.80 = Confident")
    print("0.90 = Very confident")
    print("0.95 = Extremely confident")
    confidence = float(input("Confidence (0.50-0.95): "))

    print("\nWill you use Cortex for this task? (spec search, patterns, lessons)")
    use_cortex = input("Use Cortex? (y/n): ").lower() == "y"

    # Generate prediction ID
    prediction_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Record prediction
    tracker.record_prediction(
        prediction_id=prediction_id,
        task=task,
        predicted_outcome="success",
        confidence=confidence,
        predicted_time=baseline_min,
        project=project,
    )

    print(f"\n✅ Prediction recorded: {prediction_id}")
    print(f"   Task: {task}")
    print(f"   Baseline estimate: {baseline_min} min")
    print(f"   Confidence: {confidence}")
    print(f"   Using Cortex: {use_cortex}")
    print()
    print("📋 When task is complete, run:")
    print("   python3 complete_task.py")
    print()

    # Save prediction ID for easy completion (persistent storage)
    task_data = {
        "prediction_id": prediction_id,
        "task": task,
        "baseline_min": baseline_min,
        "use_cortex": use_cortex,
        "project": project,
        "started_at": datetime.now().isoformat(),
    }

    CURRENT_TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CURRENT_TASK_FILE, "w") as f:
        json.dump(task_data, f, indent=2)

    return prediction_id


def list_pending_predictions():
    """List all pending predictions"""
    tracker = MetricsTracker()
    pending = tracker.get_pending_predictions()

    print("\n=== PENDING PREDICTIONS ===")
    if not pending:
        print("No pending predictions. Great job staying current!")
        return

    print(f"Total: {len(pending)}")
    print()

    for i, pred in enumerate(pending, 1):
        print(f"{i}. {pred['id']}")
        print(f"   Task: {pred['task']}")
        print(f"   Project: {pred.get('project', 'Unknown')}")
        print(f"   Predicted time: {pred['predicted_time_minutes']} min")
        print(f"   Confidence: {pred['confidence']:.0%}")
        print(f"   Started: {pred['timestamp'][:19]}")
        print()


def show_calibration_stats():
    """Show current calibration statistics"""
    tracker = MetricsTracker()
    cal_stats = tracker.get_calibration_stats()
    time_stats = tracker.get_time_estimation_stats()
    cal_data = tracker.get_calibration_data()

    print("\n=== CALIBRATION STATISTICS ===")
    print(f"Total predictions: {len(cal_data['predictions'])}")
    print(f"Completed: {len(cal_data['outcomes'])}")
    print(f"Pending: {cal_data['pending_count']}")
    print()

    if cal_stats["total_predictions"] == 0:
        print("No completed predictions yet.")
        print("Complete some tasks to see calibration stats!")
        return

    print("Outcome Accuracy:")
    print(f"  Success rate: {cal_stats['accuracy']*100:.1f}%")
    print(f"  Avg confidence: {cal_stats['avg_confidence']*100:.1f}%")
    print(f"  Calibration error: {cal_stats['calibration_error']*100:.1f}%")

    if cal_stats["calibration_error"] < 0.15:
        print("  Status: ✅ Well calibrated")
    elif cal_stats["calibration_error"] < 0.25:
        print("  Status: ⚠️ Moderate calibration error")
    else:
        print("  Status: ❌ Poor calibration")
    print()

    if time_stats["count"] > 0:
        print("Time Estimation:")
        print(f"  Mean error: {time_stats['mean_error_pct']:.1f}%")
        print(f"  Underestimates: {time_stats['underestimates']}")
        print(f"  Overestimates: {time_stats['overestimates']}")

        if time_stats["underestimates"] > time_stats["overestimates"] * 1.5:
            print("  Bias: ⚠️ You tend to underestimate")
        elif time_stats["overestimates"] > time_stats["underestimates"] * 1.5:
            print("  Bias: ⚠️ You tend to overestimate")
        else:
            print("  Bias: ✅ Relatively balanced")
    print()


def show_analysis():
    """Show detailed calibration analysis"""
    tracker = MetricsTracker()
    cal_stats = tracker.get_calibration_stats()
    time_stats = tracker.get_time_estimation_stats()

    print("\n=== DETAILED CALIBRATION ANALYSIS ===")

    if cal_stats["total_predictions"] == 0:
        print("No completed predictions to analyze.")
        print("Complete at least 10 tasks to see meaningful analysis.")
        return

    # Confidence bucket analysis
    print("\nCalibration Curve (Confidence Buckets):")
    buckets = cal_stats.get("by_confidence_bucket", {})
    if buckets:
        for bucket_range, stats in sorted(buckets.items()):
            pred_count = stats["predictions"]
            accuracy = stats["accuracy"] * 100
            print(f"  {bucket_range}: {pred_count} predictions, {accuracy:.0f}% accuracy")

    print()
    print("Target: Confidence should match accuracy")
    print(f"Current calibration error: {cal_stats['calibration_error']*100:.1f}%")

    # Recommendations
    print("\n📊 Recommendations:")
    if cal_stats["total_predictions"] < 20:
        print(
            f"  - Record {20 - cal_stats['total_predictions']} more predictions to reach Week 1-2 goal"
        )

    if cal_stats["calibration_error"] > 0.20:
        print(
            f"  - Adjust your confidence levels (currently off by {cal_stats['calibration_error']*100:.0f}%)"
        )

    if time_stats["count"] > 5:
        if time_stats["mean_error_pct"] > 40:
            print(
                f"  - Time estimates off by {time_stats['mean_error_pct']:.0f}% on average - need improvement"
            )
        elif time_stats["mean_error_pct"] > 25:
            print(
                f"  - Time estimates off by {time_stats['mean_error_pct']:.0f}% - getting better!"
            )
        else:
            print(f"  - Time estimates are good ({time_stats['mean_error_pct']:.0f}% error)")

    print()


def main():
    parser = argparse.ArgumentParser(description="Cortex Calibration Tracking")
    parser.add_argument("--list-pending", action="store_true", help="List pending predictions")
    parser.add_argument("--stats", action="store_true", help="Show calibration statistics")
    parser.add_argument("--analyze", action="store_true", help="Show detailed analysis")

    args = parser.parse_args()

    if args.list_pending:
        list_pending_predictions()
    elif args.stats:
        show_calibration_stats()
    elif args.analyze:
        show_analysis()
    else:
        # Default: start new prediction
        start_task_prediction()


if __name__ == "__main__":
    main()
