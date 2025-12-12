# Converx Optimization Checklist

**Version**: 1.0  
**Date**: January 2025

---

## Overview

This checklist helps you optimize Converx for maximum value. Each section includes specific actions, success criteria, and troubleshooting tips.

**Key Principle**: Optimization is iterative. Start with basics, add complexity only when value is proven.

---

## Setup Optimization

### ACTION_PLAN.md Structure

**Goal**: Ensure Converx can parse your goals accurately

**Checklist**:
- [ ] ACTION_PLAN.md exists in repository root
- [ ] Goals are clearly marked with Priority (A/B/C)
- [ ] Goals have Status (pending/in_progress/completed)
- [ ] Goals have clear Descriptions
- [ ] Goals reference specific projects when relevant
- [ ] Completed goals are marked and removed or archived

**Example Structure**:
```markdown
### Priority A: HIGH IMPACT, HIGH URGENCY

#### 1. VortexV2 MVP Completion
**Status**: in_progress
**Description**: Complete Blocks 1.2-1.4 to reach MVP
**Projects**: VortexV2
**Blockers**: Missing sensor preprocessing
```

**Success Criteria**: `converx status` shows accurate goal counts

**Troubleshooting**:
- If goals not parsed: Check ACTION_PLAN.md format
- If priorities wrong: Ensure Priority markers are clear
- If status wrong: Update goal status regularly

---

### Goal Formatting

**Goal**: Make goals parseable and actionable

**Checklist**:
- [ ] Goals are specific (not vague)
- [ ] Goals have clear success criteria
- [ ] Goals reference projects when relevant
- [ ] Goals include effort estimates (optional but helpful)
- [ ] Goals are updated as progress changes

**Good Goal Examples**:
- ✅ "Complete Block 1.2: Sensor Preprocessing (4-6 hours)"
- ✅ "Ship VortexV2 MVP by Jan 16 (Blocks 1.2-1.4 remaining)"
- ❌ "Work on VortexV2" (too vague)
- ❌ "Make progress" (no success criteria)

**Success Criteria**: Recommendations reference specific goals

---

## Data Quality

### Project Activity Accuracy

**Goal**: Ensure Converx sees accurate project activity

**Checklist**:
- [ ] Git repos are in expected locations
- [ ] Repos have recent commits (active projects)
- [ ] Repo names are clear and consistent
- [ ] Blockers are documented in git state or ACTION_PLAN.md
- [ ] Project status reflects reality

**Verification**:
```bash
converx status    # Check active projects count
# Should match your actual active projects
```

**Troubleshooting**:
- If projects missing: Check git repo locations
- If activity wrong: Ensure recent commits exist
- If status wrong: Update git state (commit, push)

---

### Goal Tracking Accuracy

**Goal**: Keep goals current and accurate

**Checklist**:
- [ ] Goals are updated weekly
- [ ] Completed goals are marked
- [ ] New goals are added as priorities change
- [ ] Goal status reflects actual progress
- [ ] Blockers are documented in goals

**Weekly Review**:
1. Review all goals in ACTION_PLAN.md
2. Update status (pending → in_progress → completed)
3. Remove or archive completed goals
4. Add new goals as priorities emerge
5. Document blockers

**Success Criteria**: `converx status` shows accurate goal counts and status

---

### Blocker Documentation

**Goal**: Ensure Converx identifies and tracks blockers

**Checklist**:
- [ ] Blockers are documented in ACTION_PLAN.md
- [ ] Blockers reference specific projects
- [ ] Blockers are updated as resolved
- [ ] Blockers include context (why blocked, what's needed)

**Example Blocker Format**:
```markdown
**Blockers**:
- VortexV2: Missing sensor preprocessing (blocks Block 1.2)
- Alpha Arena: API rate limits (need API key upgrade)
```

**Success Criteria**: `converx status` shows accurate blocker list

---

## Context Engineering

### Maximizing context_intelligence Value

**Goal**: Get accurate context predictions

**Checklist**:
- [ ] `context_intelligence.py` is available
- [ ] Personal-ai-dataset is set up (if using)
- [ ] Context predictions are relevant
- [ ] Context predictions are used when starting new work

**Optimization**:
- Use `--with-context` when starting new projects
- Track context prediction accuracy
- Improve context by maintaining good documentation
- Use personal-ai-dataset for knowledge retrieval

**Success Criteria**: Context predictions are relevant and useful

---

### Knowledge Base Integration

**Goal**: Leverage personal-ai-dataset for richer context

**Checklist**:
- [ ] personal-ai-dataset is set up
- [ ] Knowledge base is indexed and searchable
- [ ] Context predictions include knowledge base results
- [ ] Knowledge base is updated regularly

**Setup** (if not done):
1. Set up personal-ai-dataset
2. Sync Google Drive documents
3. Index knowledge base
4. Enable in context_intelligence.py

**Success Criteria**: Context predictions include relevant knowledge base results

---

## Pattern Recognition

### What to Look For

**Goal**: Identify patterns that help or hurt you

**Checklist**:
- [ ] Track estimation accuracy (predicted vs actual)
- [ ] Identify systematic biases (optimism, scope creep)
- [ ] Recognize energy patterns (when you're most effective)
- [ ] Notice blocker patterns (what types of blockers recur)
- [ ] Observe completion patterns (what you finish vs avoid)

**Weekly Pattern Review**:
1. Review recommendations from past week
2. Compare estimates to actuals
3. Identify patterns (biases, energy, blockers)
4. Adjust expectations based on patterns
5. Update ACTION_PLAN.md to account for patterns

**Success Criteria**: You recognize patterns and adjust behavior

---

### Pattern Documentation

**Goal**: Document patterns for future reference

**Checklist**:
- [ ] Create pattern journal (notes file or spreadsheet)
- [ ] Record patterns as you identify them
- [ ] Update patterns as you learn more
- [ ] Use patterns to improve recommendations

**Pattern Journal Template**:
```
Pattern: Estimation Bias
Observation: Consistently underestimate by 25%
Action: Multiply estimates by 1.25
Accuracy: Improved from 60% to 85%

Pattern: Energy Levels
Observation: Most productive 8am-12pm
Action: Schedule deep work in morning
Impact: 2x more productive hours
```

**Success Criteria**: Patterns documented and used to improve

---

## Calibration

### Improving Prediction Accuracy

**Goal**: Make Converx predictions more accurate over time

**Checklist**:
- [ ] Track effort estimates (predicted vs actual hours)
- [ ] Track outcome predictions (did recommendations happen?)
- [ ] Track scenario accuracy (which scenario actually occurred?)
- [ ] Record actuals for comparison
- [ ] Adjust interpretation based on accuracy

**Calibration Process**:
1. Record predictions (effort, outcomes, scenarios)
2. Record actuals when available
3. Compare predictions to actuals
4. Identify systematic biases
5. Adjust expectations (e.g., "multiply by 1.25")
6. Update ACTION_PLAN.md structure if needed

**Success Criteria**: Prediction accuracy improves over time (target: 80%+)

---

### Calibration Metrics

**Goal**: Measure calibration accuracy

**Metrics to Track**:
- **Effort Estimate Accuracy**: Predicted hours vs actual hours
- **Recommendation Completion Rate**: % of recommendations you followed
- **Scenario Tracking Accuracy**: Which scenario actually occurred?
- **Blocker Prediction Accuracy**: Did Converx identify blockers before you hit them?

**Tracking Method**:
- Simple: Note file with predictions and actuals
- Advanced: Spreadsheet with formulas
- Automated: Script that parses `converx next --json` output

**Success Criteria**: Metrics show improving accuracy over time

---

## Integration

### Connecting Other Tools

**Goal**: Maximize value by connecting data sources

**Checklist**:
- [ ] Identify available data sources (GitHub, health trackers, etc.)
- [ ] Set up connectors (Phase 3 feature)
- [ ] Verify data quality
- [ ] Use integrated data in recommendations

**Priority Order**:
1. **personal-ai-dataset**: Knowledge base (high value, low friction)
2. **GitHub**: Repo status (if using GitHub)
3. **Health Trackers**: Sleep, activity (if available)
4. **Financial Data**: Portfolio, expenses (if using Alpha Arena)
5. **Custom**: Your specific tools

**Success Criteria**: Integrated data improves recommendation quality

---

### Workflow Integration

**Goal**: Make Converx part of your natural workflow

**Checklist**:
- [ ] Morning check-in routine established
- [ ] Evening reflection routine established
- [ ] Project-specific workflows integrated
- [ ] Decision-making workflows include Converx
- [ ] Weekly review includes Converx analysis

**Workflow Examples**:
- **Morning**: `converx next` → pick focus for day
- **Midday**: `converx next PROJECT` → project-specific check
- **Evening**: `converx status` → reflect on day
- **Weekly**: Full review with pattern analysis

**Success Criteria**: Converx is natural part of workflow, not extra step

---

## Advanced Optimization

### Custom Heuristics

**Goal**: Create personal rules based on your patterns

**Checklist**:
- [ ] Identify patterns that consistently appear
- [ ] Create heuristics based on patterns
- [ ] Apply heuristics to improve recommendations
- [ ] Update heuristics as you learn more

**Example Heuristics**:
- "Integration work = multiply estimate by 1.25"
- "No complex work after 8pm"
- "Tuesday afternoon = low energy, schedule meetings"
- "Quick Slack check = 15 min average, not 2 min"

**Success Criteria**: Heuristics improve decision quality

---

### Automation

**Goal**: Automate routine Converx operations

**Checklist**:
- [ ] Set up shell aliases for common commands
- [ ] Create scripts for routine workflows
- [ ] Automate data collection where possible
- [ ] Use playbooks for repetitive tasks (Phase 4)

**Alias Examples**:
```bash
alias cx='converx'
alias cxn='converx next'
alias cxs='converx status'
```

**Script Examples**:
- Morning check-in script
- Weekly review script
- Pattern analysis script

**Success Criteria**: Routine operations are automated

---

## Troubleshooting

### Common Issues

**Issue**: Recommendations not relevant
- **Check**: ACTION_PLAN.md is current and well-structured
- **Check**: Project activity is accurate
- **Check**: Goals are specific and actionable
- **Fix**: Update ACTION_PLAN.md, ensure git repos are active

**Issue**: Estimates inaccurate
- **Check**: Are you tracking actuals?
- **Check**: Are there systematic biases?
- **Fix**: Calibrate expectations, adjust interpretation

**Issue**: Context predictions not useful
- **Check**: Is context_intelligence.py available?
- **Check**: Is personal-ai-dataset set up?
- **Fix**: Set up knowledge base, improve documentation

**Issue**: Not using Converx regularly
- **Check**: Is it part of your routine?
- **Check**: Is it providing value?
- **Fix**: Establish habits, track value, adjust usage

---

## Success Criteria Summary

### Setup Optimization
- [ ] ACTION_PLAN.md is well-structured
- [ ] Goals are specific and actionable
- [ ] Goals are updated regularly

### Data Quality
- [ ] Project activity is accurate
- [ ] Goal tracking is current
- [ ] Blockers are documented

### Context Engineering
- [ ] Context predictions are relevant
- [ ] Knowledge base is integrated
- [ ] Context is used effectively

### Pattern Recognition
- [ ] Patterns are identified
- [ ] Patterns are documented
- [ ] Patterns are used to improve

### Calibration
- [ ] Predictions are tracked
- [ ] Accuracy is measured
- [ ] Calibration improves over time

### Integration
- [ ] Other tools are connected
- [ ] Workflow is integrated
- [ ] Value is maximized

---

*"Optimization is not about perfection. It's about continuous improvement. Start with basics. Add complexity only when value is proven. Track progress. Adjust based on results."*
