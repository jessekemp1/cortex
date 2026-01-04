# Cortex Feedback Loop - Usage Guide

The Cortex feedback loop enables the system to learn from your actions and improve future recommendations over time.

## How It Works

1. **Get Recommendation**: Cortex generates recommendations with confidence scores
2. **Act**: You complete (or attempt) the recommended task
3. **Provide Feedback**: You log the outcome
4. **Learn**: The system adjusts future confidence scores based on historical outcomes

## Quick Start

### 1. Get Your Daily Briefing
```bash
cortex briefing
```

This shows:
- Active projects
- Priority actions (recommendations)
- Patterns noticed
- Instructions for providing feedback

### 2. Complete a Task

Work on one of the recommended tasks.

### 3. Log the Outcome

After completing (or attempting) the task:

```bash
# Success - task completed successfully
cortex feedback --outcome success

# Partial - made progress but not complete
cortex feedback --outcome partial

# Failed - didn't work or hit blockers
cortex feedback --outcome failed

# Add notes for context
cortex feedback --outcome success --notes "Fixed the virtualenv issue"
```

### 4. View Learning Metrics

See how the system is learning:

```bash
cortex learn
```

This shows:
- Overall success rate
- Confidence calibration (are high-confidence recommendations actually better?)
- Outcome patterns by recommendation type
- Which types of recommendations work best for you

## Example Workflow

```bash
# Morning: Get briefing
$ cortex briefing

PRIORITY ACTIONS
  1. [HIGH] Resolve blocker in VortexV2: No virtualenv detected
     Project: VortexV2
     Rationale: Blockers prevent progress...

💡 PROVIDE FEEDBACK
  After completing a recommendation, log the outcome:
  cortex feedback --outcome <success|partial|failed>

# Work on task...
$ cd VortexV2
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt

# Log success
$ cortex feedback --outcome success --notes "Created venv and installed deps"
✅ Outcome logged: Resolve blocker in VortexV2: No virtualenv detected
   Result: success
   Notes: Created venv and installed deps

Learning system updated. Run 'cortex learn' to see metrics.

# Check learning
$ cortex learn

📊 OVERALL METRICS
────────────────
Total Outcomes: 48
Followed Recommendations: 39
Success Rate: 66.7%
Recommendation Accuracy: 76.9%

🎯 CONFIDENCE CALIBRATION
────────────────
  high (0.8-1.0): ██████████████████░░ 93.5%
  medium (0.5-0.8): ███████████░░░░░░░░░ 56.7%

📈 OUTCOME PATTERNS BY TYPE
────────────────
  blocker_resolution
    Total: 13, Followed: 11
    Success Rate: 86.4%
    Avg Confidence: 0.79
```

## How Learning Affects Recommendations

The learning system adjusts confidence scores based on historical success rates:

### Example: Blocker Resolution

**First few recommendations**:
- Base confidence: 0.85
- Adjusted: 0.85 (no historical data)
- Explanation: "No historical data for this recommendation type"

**After 10 outcomes (85% success rate)**:
- Base confidence: 0.85
- Adjusted: 0.87
- Explanation: "Based on 10 previous outcomes (85% success rate)"

**After 10 outcomes (25% success rate)**:
- Base confidence: 0.80
- Adjusted: 0.69
- Explanation: "Based on 10 previous outcomes (25% success rate)"

The system learns which types of recommendations work best for your workflow and adjusts accordingly.

## Data Storage

All feedback is stored locally:

- **Outcomes**: `~/.cortex/outcomes.jsonl`
  - JSONL format (one JSON object per line)
  - Each entry includes: recommendation type, confidence, outcome, notes, context

- **Legacy Feedback**: `~/.cortex/feedback.json`
  - Simple feedback log (backward compatible)

## Advanced Usage

### View Feedback Stats
```bash
cortex feedback --stats
```

### View Recent Feedback
```bash
cortex feedback --stats recent
```

### Quick Note (not tied to recommendation)
```bash
cortex feedback --log "Discovered new optimization opportunity in Alpha Arena"
```

## Integration with Other Commands

The feedback loop integrates seamlessly:

- **`cortex next`**: Recommendations use learning-adjusted confidence
- **`cortex briefing`**: Shows feedback instructions
- **`cortex execute`**: Auto-logs outcomes when executing recommendations
- **`cortex learn`**: Displays learning metrics and patterns

## Tips

1. **Provide feedback consistently**: The more data, the better the learning
2. **Use partial outcomes**: If you made progress but hit blockers, log it as partial
3. **Add notes**: Context helps you remember what worked and what didn't
4. **Check patterns**: Run `cortex learn` weekly to see what's working
5. **Adjust workflow**: If certain recommendation types consistently fail, that's valuable signal

## Troubleshooting

**Q: My feedback isn't showing up**
- Check `~/.cortex/outcomes.jsonl` exists
- Verify last line matches your feedback: `tail -1 ~/.cortex/outcomes.jsonl`

**Q: Learning metrics show "Limited data"**
- Need at least 3 outcomes per recommendation type for meaningful patterns
- Keep providing feedback - the system learns over time

**Q: Confidence scores aren't changing**
- Adjustments are gradual (max 40% weight to historical data)
- Need 20+ outcomes for maximum adjustment weight

**Q: I want to reset learning data**
```bash
# Backup first
cp ~/.cortex/outcomes.jsonl ~/.cortex/outcomes.jsonl.backup

# Clear (keeps file structure)
echo "" > ~/.cortex/outcomes.jsonl
```

## Summary

The feedback loop is simple:
1. Get recommendations: `cortex briefing` or `cortex next`
2. Do the work
3. Log outcome: `cortex feedback --outcome success`
4. Watch the system learn: `cortex learn`

Over time, Cortex learns your workflow patterns and provides increasingly accurate recommendations.
