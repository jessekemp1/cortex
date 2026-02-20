#!/usr/bin/env python3
"""
Automatic Calibration with Smart Defaults
Reduces manual prompts from 8 to 0-1 by auto-detecting context
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from metrics_tracker import MetricsTracker


def detect_project():
    """Detect project from current directory"""
    cwd = Path.cwd()
    cwd_str = str(cwd)

    if "Vortex/backend" in cwd_str:
        return "vortex-backend"
    elif "alpha_arena" in cwd_str or "AlphaArena" in cwd_str:
        return "AlphaArena"
    elif "cortex" in cwd_str.lower():
        return "Cortex"
    elif "kempion" in cwd_str.lower():
        return "KempionSite"
    else:
        return "Other"


def get_changed_files():
    """Get files changed since last commit"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return [f for f in result.stdout.strip().split("\n") if f]
    except:
        pass

    # Fallback: check git status for unstaged changes
    try:
        result = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split("\n")
            return [line.split()[-1] for line in lines if line]
    except:
        pass

    return []


def estimate_baseline_time(files):
    """Estimate time based on file count and types"""
    if not files:
        return 30  # Default 30 min

    # Base: 15 min per file
    base_time = len(files) * 15

    # Adjust for file types
    adjustment = 0
    for f in files:
        if f.endswith(".md"):
            adjustment -= 5  # Docs faster
        elif f.endswith((".py", ".js", ".ts", ".tsx")):
            adjustment += 10  # Code slower
        elif f.endswith((".json", ".yaml", ".yml")):
            adjustment -= 10  # Config faster
        elif f.endswith(".sh"):
            adjustment += 5  # Scripts moderate

    total = base_time + adjustment

    # Clamp to reasonable range
    return max(15, min(total, 120))


def infer_task_description(files):
    """Infer task description from changed files"""
    if not files:
        # Try to get last commit message
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                return f"Continue: {result.stdout.strip()}"
        except:
            pass
        return "General development work"

    # Single file - use filename
    if len(files) == 1:
        filename = Path(files[0]).stem
        return f"Work on {filename}"

    # Multiple files - infer from directory or pattern
    dirs = {}
    for f in files:
        parts = Path(f).parts
        if len(parts) > 1:
            dir_name = parts[0]
            dirs[dir_name] = dirs.get(dir_name, 0) + 1

    if dirs:
        main_dir = max(dirs.items(), key=lambda x: x[1])[0]
        return f"Work on {main_dir} ({len(files)} files)"
    else:
        return f"Work on {len(files)} files"


def auto_start(force_manual=False):
    """Start calibration with smart defaults"""
    tracker = MetricsTracker()

    # Detect context
    project = detect_project()
    files = get_changed_files()
    task = infer_task_description(files)
    baseline = estimate_baseline_time(files)

    print(f"\n{'='*60}")
    print("  🤖 AUTO-CALIBRATION (Smart Defaults)")
    print(f"{'='*60}")
    print()
    print(f"📁 Project:   {project}")
    print(f"📝 Task:      {task}")
    print(f"⏱️  Baseline:  {baseline} minutes (estimated)")
    print("📊 Confidence: 70% (default)")
    print("🔧 Use Cortex: Yes (default)")

    if files:
        print(f"\n📂 Files detected ({len(files)}):")
        for f in files[:5]:
            print(f"   - {f}")
        if len(files) > 5:
            print(f"   ... and {len(files)-5} more")

    print()

    if force_manual:
        override = "e"
    else:
        override = input("✅ Accept (Enter) | ✏️  Edit (e) | ❌ Cancel (c): ").lower().strip()

    if override == "c":
        print("\n❌ Cancelled")
        return

    if override == "e":
        # Manual entry
        print("\n--- MANUAL ENTRY ---")
        task = input(f"Task [{task}]: ").strip() or task
        project_input = input(f"Project [{project}]: ").strip()
        project = project_input or project

        baseline_input = input(f"Baseline time (min) [{baseline}]: ").strip()
        baseline = int(baseline_input) if baseline_input else baseline

        confidence_input = input("Confidence (0.50-0.95) [0.70]: ").strip()
        confidence = float(confidence_input) if confidence_input else 0.70

        use_cortex_input = input("Use Cortex? (y/n) [y]: ").lower().strip()
        use_cortex = use_cortex_input != "n"
    else:
        # Use auto-detected values
        confidence = 0.70
        use_cortex = True

    # Generate prediction ID
    prediction_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Record prediction
    tracker.record_prediction(
        prediction_id=prediction_id,
        task=task,
        predicted_outcome="success",
        confidence=confidence,
        predicted_time=baseline,
        project=project,
    )

    # Save current task for completion
    task_file = Path.home() / ".claude" / "portfolio" / "current_task.json"
    task_data = {
        "prediction_id": prediction_id,
        "task": task,
        "baseline_min": baseline,
        "use_cortex": use_cortex,
        "project": project,
        "started_at": datetime.now().isoformat(),
        "files": files[:10],  # Store first 10 files for reference
    }

    task_file.parent.mkdir(parents=True, exist_ok=True)
    with open(task_file, "w") as f:
        json.dump(task_data, f, indent=2)

    print()
    print(f"✅ Prediction recorded: {prediction_id}")
    print(f"   Task: {task}")
    print(f"   Baseline: {baseline} min")
    print(f"   Confidence: {confidence:.0%}")
    print()
    print("📋 When done:")
    print("   ./cal done <actual_minutes>")
    print("   ./cal auto-done  (auto from commit)")
    print()


def auto_complete_from_commit():
    """Auto-complete from commit message and elapsed time"""
    # Load current task
    task_file = Path.home() / ".claude" / "portfolio" / "current_task.json"
    if not task_file.exists():
        print("❌ No active task to complete")
        print("Start one with: ./cal auto")
        return

    with open(task_file) as f:
        task_data = json.load(f)

    # Get commit message
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True,
            text=True,
            check=False,
        )
        commit_msg = result.stdout.strip() if result.returncode == 0 else "No commit"
    except:
        commit_msg = "Unknown"

    # Calculate elapsed time
    started = datetime.fromisoformat(task_data["started_at"])
    elapsed = int((datetime.now() - started).total_seconds() / 60)

    print(f"\n{'='*60}")
    print("  🤖 AUTO-COMPLETE from Commit")
    print(f"{'='*60}")
    print()
    print(f"📝 Task:     {task_data['task']}")
    print(f"📁 Project:  {task_data['project']}")
    print(f"⏱️  Started:  {started.strftime('%H:%M')}")
    print(f"⏱️  Elapsed:  {elapsed} minutes")
    print(f"📝 Commit:   {commit_msg}")
    print()

    # Infer outcome from commit message
    outcome = "success"
    if any(word in commit_msg.lower() for word in ["fix", "bug", "error", "hotfix"]):
        notes = f"Bug fix: {commit_msg}"
    elif any(word in commit_msg.lower() for word in ["wip", "partial", "temp"]):
        outcome = "partial"
        notes = f"Partial: {commit_msg}"
    elif any(word in commit_msg.lower() for word in ["add", "feat", "feature", "implement"]):
        notes = f"Feature: {commit_msg}"
    elif any(word in commit_msg.lower() for word in ["refactor", "cleanup", "improve"]):
        notes = f"Refactor: {commit_msg}"
    elif any(word in commit_msg.lower() for word in ["docs", "doc", "readme"]):
        notes = f"Docs: {commit_msg}"
    else:
        notes = commit_msg

    confirm = (
        input(f"✅ Complete with {elapsed} min, outcome={outcome}? (y/n) [y]: ").lower().strip()
    )

    if confirm in ("", "y", "yes"):
        tracker = MetricsTracker()

        # Record outcome
        tracker.record_outcome(
            prediction_id=task_data["prediction_id"],
            actual_outcome=outcome,
            actual_time=elapsed,
        )

        # Record velocity if using Cortex
        if task_data.get("use_cortex"):
            tracker.record_velocity(
                task=task_data["task"],
                time_without_cortex=task_data["baseline_min"],
                time_with_cortex=elapsed,
                project=task_data["project"],
                notes=notes,
            )

        # Calculate savings
        saved = task_data["baseline_min"] - elapsed
        saved_pct = (
            (saved / task_data["baseline_min"]) * 100 if task_data["baseline_min"] > 0 else 0
        )

        print()
        print("✅ Task completed!")
        print(f"   Predicted: {task_data['baseline_min']} min")
        print(f"   Actual: {elapsed} min")
        print(f"   Difference: {saved:+d} min ({saved_pct:+.1f}%)")

        if task_data.get("use_cortex") and saved > 0:
            print(f"   🎉 Saved {saved} minutes with Cortex!")
        elif saved < 0:
            print("   ⏱️  Took longer than estimated")

        # Remove current task file
        task_file.unlink()

        # Show next steps
        print()
        print("📊 Check progress: ./cal stats")
        print("📋 Next task: ./cal auto")
    else:
        print("\n❌ Cancelled. Run './cal done' manually when ready.")


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "complete":
            auto_complete_from_commit()
        elif cmd == "manual":
            auto_start(force_manual=True)
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: auto_calibration.py [complete|manual]")
    else:
        auto_start()


if __name__ == "__main__":
    main()
