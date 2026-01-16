#!/usr/bin/env python3
"""Quick script to complete task predictions"""
import json
import sys
from datetime import datetime
from pathlib import Path

from metrics_tracker import MetricsTracker

CURRENT_TASK_FILE = Path.home() / ".claude" / "portfolio" / "current_task.json"


def complete_current_task():
    """Complete the current task prediction"""
    tracker = MetricsTracker()

    # Load current task from persistent storage
    try:
        with open(CURRENT_TASK_FILE, "r") as f:
            task_data = json.load(f)

        prediction_id = task_data["prediction_id"]
        task = task_data["task"]
        baseline_min = task_data["baseline_min"]
        use_cortex = task_data["use_cortex"]
        project = task_data.get("project", "Unknown")

    except FileNotFoundError:
        print("❌ No active task found. Start one with:")
        print("   python3 start_calibration.py")
        print()
        print("Or complete a specific prediction:")
        print("   python3 start_calibration.py --list-pending")
        return
    except (json.JSONDecodeError, KeyError) as e:
        print(f"❌ Error reading task file: {e}")
        print("File may be corrupted. Please start a new task.")
        return

    print("\n=== COMPLETE TASK PREDICTION ===")
    print(f"Task: {task}")
    print(f"Project: {project}")
    print(f"Baseline estimate: {baseline_min} min")
    print()

    actual_min = int(input("Actual time taken (minutes): "))

    outcome = input("Outcome (success/partial/failure): ")
    notes = input("Notes (what helped/hindered): ")

    # Record outcome
    success = tracker.record_outcome(
        prediction_id=prediction_id, actual_outcome=outcome, actual_time=actual_min
    )

    if not success:
        print(f"⚠️ Warning: Could not find prediction {prediction_id}")
        print("Prediction may have already been completed.")

    # Also record velocity metric if Cortex was used
    if use_cortex:
        tracker.record_velocity(
            task=task,
            time_without_cortex=baseline_min,
            time_with_cortex=actual_min,
            project=project,
            notes=notes,
        )

    # Calculate accuracy
    time_diff = actual_min - baseline_min
    time_diff_pct = (time_diff / baseline_min) * 100 if baseline_min > 0 else 0

    print(f"\n✅ Task complete!")
    print(f"   Predicted: {baseline_min} min")
    print(f"   Actual: {actual_min} min")
    print(f"   Difference: {time_diff:+d} min ({time_diff_pct:+.1f}%)")

    if use_cortex:
        if actual_min < baseline_min:
            saved = baseline_min - actual_min
            print(f"   🎉 Saved {saved} minutes with Cortex!")
        elif actual_min == baseline_min:
            print(f"   ✅ Matched baseline estimate")
        else:
            extra = actual_min - baseline_min
            print(f"   ⚠️ Took {extra} minutes longer than baseline")
    else:
        if actual_min < baseline_min:
            print(f"   ⚡ Faster than expected!")
        elif actual_min > baseline_min:
            print(f"   ⏱️ Took longer than expected")

    print()
    print("Next steps:")
    print("  - Check progress: python3 start_calibration.py --stats")
    print("  - Start next task: python3 start_calibration.py")
    print()

    # Clear current task file
    try:
        CURRENT_TASK_FILE.unlink()
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    complete_current_task()
