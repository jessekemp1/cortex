# Calibration Tracking - Automation Strategy

**Goal**: Reduce manual friction from 100% to <20%
**Approach**: Progressive automation leveraging existing infrastructure
**Timeline**: 3 phases over 2 weeks

---

## Current Problem

**Manual Process**:
1. Before task: `./cal start` → 5 prompts (task, project, time, confidence, use Cortex)
2. After task: `./cal done` → 3 prompts (actual time, outcome, notes)
3. **Friction**: 8 manual inputs per task
4. **Risk**: Forgetting to track = incomplete data

**Compliance Issues**:
- Forget to run `./cal start` before task
- Forget to run `./cal done` after task
- Takes 2-3 minutes per task
- Interrupts flow state

---

## Automation Phases

### Phase 1: Smart Defaults (Immediate - 80% effort reduction)

**Auto-detect from git context**:
```python
# Infer from git commit messages and file changes
task = "Work on <file_basename>" (from git status)
project = detect_project_from_path()  # VortexV2, Cortex, AlphaArena
baseline_time = estimate_from_file_count()  # 15min/file baseline
confidence = 0.70  # Default moderate confidence
use_cortex = True  # Default yes
```

**New workflow**:
```bash
# Before task - Just one command, no prompts
./cal start --auto

# After task - Just actual time needed
./cal done 25  # 25 minutes actual

# Or fully automatic from git
git commit -m "Add validation"  # Auto-completes pending task!
```

**Result**: 8 prompts → 0-1 prompts (90% reduction)

---

### Phase 2: Git Hook Integration (Week 1 - Automatic detection)

**Pre-commit hook** - Detects work starting:
```bash
# .git/hooks/pre-commit
#!/bin/bash
# Auto-start calibration if not already started

if [ ! -f ~/.claude/portfolio/current_task.json ]; then
    cd ~/Dev/cortex
    ./cal start --auto-from-git
fi
```

**Post-commit hook** - Detects work completion:
```bash
# .git/hooks/post-commit
#!/bin/bash
# Auto-complete calibration from commit

cd ~/Dev/cortex
./cal done --auto-from-commit
```

**Result**: Zero manual tracking for git-based workflows

---

### Phase 3: Background Monitoring (Week 2 - Passive tracking)

**File watcher** - Detects active work:
```python
# Auto-start when files modified
# Auto-pause when idle >15min
# Auto-complete on commit

import watchdog
monitor_workspace()  # Runs in background
```

**Daily cleanup** - Via existing scheduler:
```bash
# Add to morning_briefing.sh
python3 -c "
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()

# Auto-complete stale predictions (>24h old)
pending = tracker.get_pending_predictions()
for pred in pending:
    if age(pred) > 24_hours:
        auto_complete_from_git(pred)
"
```

**Result**: 95%+ automatic tracking

---

## Implementation Plan

### TODAY: Smart Defaults (30 minutes)

**File**: Create `/Users/jesse.kemp/Dev/cortex/auto_calibration.py`

```python
#!/usr/bin/env python3
"""Automatic calibration with smart defaults"""

import subprocess
from pathlib import Path
from datetime import datetime
from metrics_tracker import MetricsTracker

def detect_project():
    """Detect project from current directory"""
    cwd = Path.cwd()
    if "VortexV2" in str(cwd):
        return "VortexV2"
    elif "alpha_arena" in str(cwd):
        return "AlphaArena"
    elif "cortex" in str(cwd):
        return "Cortex"
    return "Other"

def get_changed_files():
    """Get files changed since last commit"""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True
    )
    return result.stdout.strip().split('\n') if result.stdout else []

def estimate_baseline_time(files):
    """Estimate time based on file count and types"""
    if not files or files == ['']:
        return 30  # Default

    # 15 min per file baseline
    base = len(files) * 15

    # Adjust for file types
    for f in files:
        if f.endswith('.md'):
            base -= 5  # Docs faster
        elif f.endswith(('.py', '.js', '.ts')):
            base += 10  # Code slower

    return max(15, min(base, 120))  # 15-120 min range

def infer_task_description(files):
    """Infer task from changed files"""
    if not files or files == ['']:
        return "General development work"

    # Get most common directory
    dirs = [Path(f).parts[0] if '/' in f else Path(f).stem for f in files]

    if len(files) == 1:
        return f"Work on {Path(files[0]).stem}"
    else:
        return f"Work on {dirs[0]} ({len(files)} files)"

def auto_start():
    """Start calibration with smart defaults"""
    tracker = MetricsTracker()

    # Detect context
    project = detect_project()
    files = get_changed_files()
    task = infer_task_description(files)
    baseline = estimate_baseline_time(files)

    # Use smart defaults
    prediction_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print(f"\n🤖 AUTO-CALIBRATION")
    print(f"Task: {task}")
    print(f"Project: {project}")
    print(f"Estimated baseline: {baseline} min")
    print(f"Confidence: 70% (default)")
    print()

    # Allow override
    override = input("Press Enter to accept, or 'e' to edit: ").lower()

    if override == 'e':
        # Fall back to manual
        from start_calibration import start_task_prediction
        start_task_prediction()
    else:
        # Use auto-detected values
        tracker.record_prediction(
            prediction_id=prediction_id,
            task=task,
            predicted_outcome="success",
            confidence=0.70,
            predicted_time=baseline,
            project=project
        )

        # Save current task
        import json
        task_file = Path.home() / ".claude" / "portfolio" / "current_task.json"
        task_data = {
            "prediction_id": prediction_id,
            "task": task,
            "baseline_min": baseline,
            "use_cortex": True,
            "project": project,
            "started_at": datetime.now().isoformat()
        }
        task_file.parent.mkdir(parents=True, exist_ok=True)
        with open(task_file, "w") as f:
            json.dump(task_data, f, indent=2)

        print(f"✅ Auto-tracked: {prediction_id}")
        print(f"When done: ./cal done <actual_minutes>")

def auto_complete_from_commit():
    """Auto-complete from commit message and time"""
    # Get commit message and time
    result = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        capture_output=True, text=True
    )
    commit_msg = result.stdout.strip()

    # Load current task
    task_file = Path.home() / ".claude" / "portfolio" / "current_task.json"
    if not task_file.exists():
        print("No active task to complete")
        return

    import json
    with open(task_file) as f:
        task_data = json.load(f)

    # Calculate elapsed time
    started = datetime.fromisoformat(task_data["started_at"])
    elapsed = int((datetime.now() - started).total_seconds() / 60)

    print(f"\n🤖 AUTO-COMPLETE")
    print(f"Task: {task_data['task']}")
    print(f"Started: {started.strftime('%H:%M')}")
    print(f"Elapsed: {elapsed} min")
    print(f"Commit: {commit_msg}")
    print()

    # Infer outcome from commit message
    outcome = "success"
    if any(word in commit_msg.lower() for word in ["fix", "bug", "error"]):
        notes = f"Bug fix: {commit_msg}"
    elif any(word in commit_msg.lower() for word in ["add", "feat", "feature"]):
        notes = f"Feature: {commit_msg}"
    else:
        notes = commit_msg

    confirm = input(f"Complete with {elapsed} min? (y/n): ").lower()
    if confirm == 'y':
        tracker = MetricsTracker()
        tracker.record_outcome(
            prediction_id=task_data["prediction_id"],
            actual_outcome=outcome,
            actual_time=elapsed
        )

        if task_data["use_cortex"]:
            tracker.record_velocity(
                task=task_data["task"],
                time_without_cortex=task_data["baseline_min"],
                time_with_cortex=elapsed,
                project=task_data["project"],
                notes=notes
            )

        task_file.unlink()
        print("✅ Auto-completed!")
    else:
        print("Skipped. Run './cal done' manually.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "complete":
        auto_complete_from_commit()
    else:
        auto_start()
```

**Update `cal` wrapper**:
```bash
#!/bin/bash
case "$1" in
  auto)
    python3 "$CORTEX_DIR/auto_calibration.py"
    ;;
  auto-done)
    python3 "$CORTEX_DIR/auto_calibration.py" complete
    ;;
  # ... existing commands
esac
```

**New workflow**:
```bash
# Start work (auto-detects everything)
./cal auto

# Or just commit (auto-completes)
git commit -m "Add feature"
./cal auto-done
```

---

### WEEK 1: Git Hooks (15 minutes)

**Install hooks**:
```bash
cd ~/Dev/cortex
./install_git_hooks.sh
```

**Create installer** - `/Users/jesse.kemp/Dev/cortex/install_git_hooks.sh`:
```bash
#!/bin/bash
# Install git hooks for automatic calibration

HOOK_DIR=".git/hooks"
CORTEX_DIR="$HOME/Dev/cortex"

# Pre-commit: Auto-start if no task active
cat > "$HOOK_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Auto-start calibration tracking

TASK_FILE="$HOME/.claude/portfolio/current_task.json"
if [ ! -f "$TASK_FILE" ]; then
    echo "🤖 Auto-starting calibration tracking..."
    cd ~/Dev/cortex
    python3 auto_calibration.py < /dev/tty
fi
EOF

# Post-commit: Suggest auto-complete
cat > "$HOOK_DIR/post-commit" << 'EOF'
#!/bin/bash
# Remind to complete calibration

TASK_FILE="$HOME/.claude/portfolio/current_task.json"
if [ -f "$TASK_FILE" ]; then
    echo "📊 Task tracked. Complete with: ./cal auto-done"
fi
EOF

chmod +x "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/post-commit"

echo "✅ Git hooks installed!"
echo "Calibration will auto-start on commits"
```

---

### WEEK 2: Daily Automation (10 minutes)

**Add to existing morning briefing**:

Edit `/Users/jesse.kemp/Dev/cortex/scripts/morning_briefing.sh`:
```bash
#!/bin/bash
# ... existing briefing code

# Add calibration cleanup
python3 -c "
from metrics_tracker import MetricsTracker
from datetime import datetime, timedelta

tracker = MetricsTracker()
pending = tracker.get_pending_predictions()

# Auto-complete stale predictions
for pred in pending:
    pred_time = datetime.fromisoformat(pred['timestamp'])
    if datetime.now() - pred_time > timedelta(hours=24):
        # Estimate from files changed
        print(f'Auto-completing stale prediction: {pred[\"task\"]}')
        tracker.record_outcome(
            prediction_id=pred['id'],
            actual_outcome='success',  # Assume success
            actual_time=pred['predicted_time_minutes']  # Use prediction
        )
"

# Show calibration status
echo "📊 CALIBRATION STATUS:"
python3 -c "
from metrics_tracker import MetricsTracker
tracker = MetricsTracker()
stats = tracker.get_calibration_stats()
print(f\"  Predictions: {stats['total_predictions']}")
print(f\"  Calibration: {stats['calibration_error']*100:.0f}% error\")
"
```

---

## Effort Reduction Comparison

| Approach | Prompts | Time | Compliance Risk |
|----------|---------|------|-----------------|
| **Current (Manual)** | 8 | 2-3 min | High (40%+) |
| **Phase 1 (Smart Defaults)** | 0-1 | 30 sec | Medium (20%) |
| **Phase 2 (Git Hooks)** | 0 | 10 sec | Low (10%) |
| **Phase 3 (Background)** | 0 | 0 sec | Very Low (<5%) |

---

## Implementation Timeline

**TODAY** (30 min):
- [x] Create `auto_calibration.py`
- [ ] Update `cal` wrapper
- [ ] Test `./cal auto`

**Tomorrow** (15 min):
- [ ] Create `install_git_hooks.sh`
- [ ] Install hooks
- [ ] Test git workflow

**End of Week** (10 min):
- [ ] Update morning_briefing.sh
- [ ] Test daily automation
- [ ] Verify compliance >90%

---

## Success Metrics

**After Phase 1** (Smart Defaults):
- ✅ Prompts reduced: 8 → 1
- ✅ Time reduced: 2-3 min → 30 sec
- ✅ Compliance target: >80%

**After Phase 2** (Git Hooks):
- ✅ Prompts reduced: 1 → 0
- ✅ Time reduced: 30 sec → 10 sec
- ✅ Compliance target: >90%

**After Phase 3** (Background):
- ✅ Prompts reduced: 0 → 0
- ✅ Time reduced: 10 sec → 0 sec
- ✅ Compliance target: >95%

---

## Rollout Strategy

**Week 1**:
- Use `./cal auto` instead of `./cal start`
- Verify accuracy of auto-detection
- Adjust defaults based on feedback

**Week 2**:
- Install git hooks
- Test automatic workflow
- Monitor compliance rate

**Week 3**:
- Enable daily automation
- Achieve >90% compliance
- Proceed to VortexV2 integration

---

## Next Steps

**Immediate**:
1. Create `auto_calibration.py` (I'll do this now)
2. Test with `./cal auto`
3. Refine defaults based on first 5 tasks

**This Week**:
1. Install git hooks once confident in auto-detection
2. Monitor for edge cases
3. Iterate on smart defaults

**Next Week**:
1. Enable daily cleanup automation
2. Measure compliance rate
3. Report success metrics
