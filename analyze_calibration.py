#!/usr/bin/env python3
"""
Week 2 Calibration Analysis
Comprehensive report for Month 1, Week 1-2 calibration data
"""

from metrics_tracker import MetricsTracker
from datetime import datetime
import json

def generate_report():
    """Generate comprehensive calibration report"""
    tracker = MetricsTracker()

    # Get all calibration data
    cal_data = tracker.get_calibration_data()
    stats = tracker.get_calibration_stats()
    time_stats = tracker.get_time_estimation_stats()

    print("=" * 60)
    print(" " * 15 + "WEEK 1-2 CALIBRATION REPORT")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # === SECTION 1: PREDICTION SUMMARY ===
    print("1. PREDICTION SUMMARY")
    print("-" * 60)
    print(f"Total predictions: {len(cal_data['predictions'])}")
    print(f"Completed: {len(cal_data['outcomes'])}")
    print(f"Pending: {cal_data['pending_count']}")
    print()

    if len(cal_data['outcomes']) == 0:
        print("⚠️ No completed predictions yet.")
        print("Complete at least 10 tasks to generate a meaningful report.")
        return

    # === SECTION 2: OUTCOME ACCURACY ===
    print("2. OUTCOME ACCURACY")
    print("-" * 60)
    print(f"Success rate: {stats['accuracy']*100:.1f}%")
    print(f"Average confidence: {stats['avg_confidence']*100:.1f}%")
    print(f"Calibration error: {stats['calibration_error']*100:.1f}%")
    print()

    # Calibration assessment
    if stats['calibration_error'] < 0.10:
        assessment = "✅ EXCELLENT - Very well calibrated"
    elif stats['calibration_error'] < 0.15:
        assessment = "✅ GOOD - Well calibrated"
    elif stats['calibration_error'] < 0.25:
        assessment = "⚠️ MODERATE - Needs adjustment"
    else:
        assessment = "❌ POOR - Significant calibration error"
    print(f"Assessment: {assessment}")
    print()

    # === SECTION 3: CONFIDENCE BUCKETS ===
    print("3. CALIBRATION CURVE (Confidence Buckets)")
    print("-" * 60)
    buckets = stats.get('by_confidence_bucket', {})
    if buckets:
        print(f"{'Confidence Range':<20} {'Predictions':<15} {'Accuracy':<15} {'Gap'}")
        print("-" * 60)
        for bucket_range, bucket_stats in sorted(buckets.items()):
            pred_count = bucket_stats['predictions']
            accuracy = bucket_stats['accuracy']

            # Parse bucket range to get midpoint
            low, high = bucket_range.split('-')
            midpoint = (float(low) + float(high)) / 2
            gap = accuracy - midpoint
            gap_str = f"{gap:+.1%}"

            accuracy_str = f"{accuracy:.0%}"
            print(f"{bucket_range:<20} {pred_count:<15} {accuracy_str:<15} {gap_str}")
    else:
        print("Not enough data for bucket analysis (need 5+ completed predictions)")
    print()

    # === SECTION 4: TIME ESTIMATION ACCURACY ===
    print("4. TIME ESTIMATION ACCURACY")
    print("-" * 60)
    if time_stats['count'] > 0:
        print(f"Mean estimation error: {time_stats['mean_error_pct']:.1f}%")
        print(f"Underestimates: {time_stats['underestimates']}")
        print(f"Overestimates: {time_stats['overestimates']}")
        print()

        # Bias detection
        if time_stats['underestimates'] > time_stats['overestimates'] * 1.5:
            print("⚠️ BIAS DETECTED: You tend to UNDERESTIMATE task duration")
            print("   Recommendation: Increase your time estimates by 20-30%")
        elif time_stats['overestimates'] > time_stats['underestimates'] * 1.5:
            print("⚠️ BIAS DETECTED: You tend to OVERESTIMATE task duration")
            print("   Recommendation: Decrease your time estimates by 10-20%")
        else:
            print("✅ BALANCED: No systematic time estimation bias detected")
        print()

        # Time estimation assessment
        if time_stats['mean_error_pct'] < 20:
            print("✅ EXCELLENT time estimation (< 20% error)")
        elif time_stats['mean_error_pct'] < 30:
            print("✅ GOOD time estimation (20-30% error)")
        elif time_stats['mean_error_pct'] < 40:
            print("⚠️ MODERATE time estimation (30-40% error)")
        else:
            print("❌ POOR time estimation (> 40% error)")
    else:
        print("No completed predictions with time data")
    print()

    # === SECTION 5: PROJECT BREAKDOWN ===
    print("5. PROJECT BREAKDOWN")
    print("-" * 60)
    project_counts = {}
    for pred in cal_data['predictions']:
        project = pred.get('project', 'Unknown')
        if pred.get('outcome_recorded'):
            project_counts[project] = project_counts.get(project, 0) + 1

    if project_counts:
        for project, count in sorted(project_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{project:<20} {count} predictions")
    else:
        print("No project data available")
    print()

    # === SECTION 6: WEEK 1-2 GOALS ===
    print("6. WEEK 1-2 GOALS PROGRESS")
    print("-" * 60)
    goal_completed = len(cal_data['outcomes'])
    goal_target = 20

    print(f"Target: {goal_target} completed predictions")
    print(f"Current: {goal_completed} completed")
    print(f"Progress: {goal_completed}/{goal_target} ({goal_completed/goal_target*100:.0f}%)")
    print()

    if goal_completed >= goal_target:
        print("✅ GOAL ACHIEVED: Week 1-2 target completed!")
    elif goal_completed >= goal_target * 0.5:
        remaining = goal_target - goal_completed
        print(f"⚠️ HALFWAY: Complete {remaining} more tasks to reach goal")
    else:
        remaining = goal_target - goal_completed
        print(f"❌ BEHIND: Complete {remaining} more tasks to reach goal")
    print()

    # === SECTION 7: RECOMMENDATIONS ===
    print("7. RECOMMENDATIONS")
    print("-" * 60)

    recommendations = []

    # Goal completion
    if goal_completed < goal_target:
        recommendations.append(
            f"Record {goal_target - goal_completed} more predictions to reach Week 1-2 goal"
        )

    # Calibration error
    if stats['calibration_error'] > 0.20:
        if stats['avg_confidence'] > stats['accuracy']:
            recommendations.append(
                "You're OVERCONFIDENT - lower your confidence levels by 10-15%"
            )
        else:
            recommendations.append(
                "You're UNDERCONFIDENT - increase your confidence levels by 10-15%"
            )

    # Time estimation
    if time_stats['count'] > 5:
        if time_stats['mean_error_pct'] > 40:
            recommendations.append(
                "Time estimates need significant improvement (>40% error)"
            )
        if time_stats['underestimates'] > time_stats['overestimates'] * 1.5:
            recommendations.append(
                "Add 20-30% buffer to your time estimates (you tend to underestimate)"
            )

    # Pending predictions
    if cal_data['pending_count'] > 5:
        recommendations.append(
            f"Complete {cal_data['pending_count']} pending predictions to keep data current"
        )

    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("✅ No major issues detected! Keep up the good work.")
    print()

    # === SECTION 8: NEXT STEPS ===
    print("8. NEXT STEPS")
    print("-" * 60)
    print("Week 3-4: VortexV2 Forecast Calibration")
    print("  - Design VortexV2 integration architecture")
    print("  - Add Cortex hook to validation pipeline")
    print("  - Record 30+ forecast predictions")
    print()
    print("Continue development velocity tracking:")
    print("  - Before task: ./cal start")
    print("  - After task: ./cal done")
    print("  - Check progress: ./cal stats")
    print()

    print("=" * 60)
    print(f"Report saved to: {datetime.now().strftime('%Y%m%d')}_calibration_report.txt")
    print("=" * 60)


if __name__ == "__main__":
    generate_report()
