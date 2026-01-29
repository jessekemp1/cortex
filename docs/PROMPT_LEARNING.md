# Prompt Learning System

## Overview

The Prompt Learning System creates a closed feedback loop between your conversation patterns and Cortex's intelligence. It learns from **what you actually ask for** to optimize recommendations, predict your next needs, and auto-tune the system.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   YOUR CONVERSATIONS                         │
│  (Claude Code sessions in ~/Library/Application Support)     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Extract & Analyze
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PROMPT HISTORY ANALYZER                         │
│  • Extracts patterns from audit.jsonl files                  │
│  • Detects topics, priorities, workflows                     │
│  • Calculates urgency and frequency                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Patterns, Priorities, Workflows
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              LEARNING LOOP                                   │
│  • Generates recommendations based on patterns               │
│  • Updates Cortex confidence weights                         │
│  • Correlates prompts with outcomes                          │
│  • Predicts next actions                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Optimized Recommendations
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              CORTEX INTELLIGENCE                             │
│  • PatternMemory, UnifiedIntelligence                        │
│  • LearningSystem with updated weights                       │
│  • SessionManager with context                               │
└─────────────────────────────────────────────────────────────┘
                     │
                     │ Better Recommendations
                     ▼
                  YOU (next session)
                     │
                     └──────> LOOP CONTINUES
```

## What It Learns

### 1. Prompt Patterns
- **Topics** - What you work on most frequently
- **Keywords** - Significant terms that appear repeatedly
- **Frequency** - How often each pattern appears
- **Recency** - When you last worked on this
- **Project Associations** - Which projects patterns relate to
- **Tool Usage** - Which tools you use for each pattern
- **Urgency Signals** - Which patterns are urgent vs exploratory

### 2. Priorities
Detected from your recent activity (last 7 days by default):
- **Category** - feature, fix, research, refactor, test, docs, deploy
- **Strength** - What % of your recent work is in this category
- **Trend** - increasing, stable, decreasing, new
- **Evidence** - Recent prompts that support this priority
- **Projects Affected** - Which projects this priority applies to

### 3. Workflows
Common sequences of actions detected from your conversations:
- **Steps** - Typical sequence (e.g., investigate → plan → implement → test)
- **Success Rate** - How often this workflow completes successfully
- **Duration** - Average time this workflow takes
- **Trigger Keywords** - What typically starts this workflow
- **Frequency** - How often you use this workflow

## How It Optimizes Cortex

### 1. Recommendation Confidence Adjustment
When Cortex makes a recommendation, the learning system adjusts its confidence based on your actual behavior:

```python
# Before: Generic recommendation
recommendation = "Work on VortexV2 testing"
confidence = 0.7

# After: Adjusted by prompt history
# You've asked about testing 15 times in last 7 days = high priority
adjusted_confidence = 0.7 * 1.5 = 1.0  # Boosted!
explanation = "Boosted by 50% based on your recent focus"
```

### 2. Next Action Prediction
Predicts what you'll work on next based on:
- Most frequent patterns in current project
- Recent activity trends
- Time of day patterns
- Workflow stage you're currently in

### 3. Priority Reweighting
Automatically adjusts category weights in the learning system:

```json
{
  "feature": 1.2,    // You're doing 20% more feature work than average
  "fix": 0.8,        // 20% less bug fixing
  "research": 1.5,   // 50% more research - this becomes top priority
  "test": 1.0        // Baseline
}
```

These weights then influence all future Cortex recommendations.

### 4. Workflow Suggestions
When you start a new task, Cortex can suggest:
- Your typical workflow for this type of task
- Expected duration based on history
- Tools you typically use
- What usually comes next

## Usage

### Run Learning Loop
```bash
# Full analysis (30 days)
/prompt-learn

# Quick analysis (7 days)
/prompt-learn quick

# Detailed analysis with correlations
/prompt-learn analyze

# Show current insights
/prompt-learn insights
```

### Python API
```python
from cortex.intelligence.prompt_learning import PromptLearningLoop

# Initialize
loop = PromptLearningLoop()

# Run learning loop
result = loop.analyze_and_learn(days_back=30)

# Get recommendations
for rec in result['recommendations']:
    print(f"[{rec['confidence']:.0%}] {rec['content']}")

# Get optimized confidence for a recommendation
adjusted, explanation = loop.get_optimized_recommendation(
    recommendation_type="feature",
    base_confidence=0.7,
    context={"project": "VortexV2"}
)

# Correlate prompts with outcomes
correlations = loop.correlate_prompts_with_outcomes()
```

### Integrate with Existing Skills
```python
# In /status command
from cortex.intelligence.prompt_learning import PromptLearningLoop

loop = PromptLearningLoop()
prediction = loop.get_next_action_prediction({
    "cwd": "/Users/jesse.kemp/Dev/Vortex/VortexV2",
    "time_of_day": "morning"
})

print(f"Predicted next: {prediction}")
```

## Output Files

All analysis is cached in `~/.cortex/prompt_learning/`:

- `prompt_analysis.json` - Full pattern/priority/workflow analysis
- `category_weights.json` - Current category weights for learning system
- `learning_state.jsonl` - Historical learning states (append-only log)

## Examples

### Example 1: Detecting Priority Shift

**Your Prompts (Last 7 Days):**
```
- "Fix authentication bug in VortexV2"
- "Debug GRIB parsing error"
- "Investigate test failures"
- "Quick fix for login issue"
- "Fix broken deployment"
```

**Learning System Detects:**
```
Priority: "fix"
Strength: 70%
Trend: increasing
Recommendation: "Focus on fix work - this is 70% of recent activity and increasing"
Confidence: 0.70
```

**Cortex Adjusts:**
- Boosts confidence on bug fix recommendations by 1.4x
- Lowers confidence on feature recommendations by 0.7x
- Suggests focusing on stability before new features

### Example 2: Workflow Detection

**Your Typical Sequence:**
```
1. "Investigate why X is failing" (research)
2. "Show me the code for Y" (research)
3. "Create a plan to fix X" (plan)
4. "Implement the fix" (fix)
5. "Run tests to verify" (test)
6. "Commit the changes" (deploy)
```

**Learning System Detects:**
```
Workflow: "research → research → plan → fix → test → deploy"
Frequency: 8 times in 30 days
Success Rate: 87.5%
Avg Duration: 45 minutes
```

**Cortex Suggests:**
```
When you say "Investigate why...", Cortex knows:
- You'll likely need to see code next
- Then make a plan
- Then implement
- Expected time: ~45 minutes
- Success probability: 87.5%
```

### Example 3: Abandoned Work Detection

**Pattern Detected:**
```
Topic: "cortex batch orchestration improvements"
Frequency: 5 sessions
Last Active: 14 days ago
Projects: cortex
```

**Recommendation:**
```
Type: context
Content: "You haven't worked on 'cortex batch orchestration improvements'
         in 14 days - was this intentional?"
Confidence: 0.6
```

This helps you remember abandoned work that might still be important.

## Advanced: Self-Improving Loop

The system creates a **self-improving feedback loop**:

1. **You ask Cortex for something**
   - "Help me debug VortexV2 forecasts"

2. **Cortex makes recommendation**
   - "Check GRIB data validation in forecasts/ensemble.py"
   - Confidence: 0.7

3. **You follow (or don't follow) the recommendation**
   - Session completes successfully (or fails)

4. **Learning system correlates**
   - "debug" + "VortexV2" + "GRIB" = 85% success rate
   - Adjusts future confidence: 0.7 → 0.85

5. **Next time you ask similar question**
   - Same recommendation now has 0.85 confidence
   - You're more likely to follow it
   - Success rate improves further

**Over time**: Cortex learns your personal patterns and becomes increasingly accurate at predicting what you need.

## Integration Points

### With Existing Systems

**PatternMemory** (`cortex/intelligence/memory/pattern_memory.py`)
- Prompt patterns feed into git pattern memory
- Cross-reference: "You asked about this AND worked on similar code"

**LearningSystem** (`cortex/learning.py`)
- Category weights adjust recommendation confidence
- Outcome correlation improves accuracy

**UnifiedIntelligence** (`cortex/intelligence/unified_intelligence.py`)
- Prompt predictions inform context selection
- Priority signals guide recommendation ranking

**SessionManager** (`cortex/intelligence/session_manager.py`)
- Session context enriched with prompt history
- Continuity across sessions based on patterns

## Configuration

Create `~/.cortex/prompt_learning_config.json`:

```json
{
  "days_to_analyze": 30,
  "min_pattern_frequency": 2,
  "priority_lookback_days": 7,
  "workflow_min_occurrences": 3,
  "confidence_boost_max": 1.5,
  "confidence_penalty_max": 0.5,
  "auto_run_on_startup": true,
  "cache_ttl_hours": 24
}
```

## Future Enhancements

### Phase 2: Deep Pattern Analysis
- NLP-based topic modeling (instead of simple heuristics)
- Embedding-based similarity search for prompts
- Temporal patterns (time-of-day, day-of-week preferences)
- Multi-session workflow detection

### Phase 3: Predictive Intelligence
- Predict when you'll abandon a task (and remind you)
- Suggest optimal time to start certain types of work
- Detect when you're stuck and offer help proactively
- Learn your "coding style" and suggest patterns

### Phase 4: Cross-User Learning (Optional)
- Aggregate patterns across team (privacy-preserving)
- "Others working on X typically also work on Y"
- Benchmark your patterns against best practices

## Privacy & Security

- All data stays local in `~/.cortex/` and `~/Library/Application Support/Claude/`
- No data sent to external services
- Can be disabled by setting `auto_run_on_startup: false`
- Can clear cache: `rm -rf ~/.cortex/prompt_learning/`

## Testing

```bash
# Run analyzer tests
pytest cortex/tests/test_prompt_history.py

# Run learning loop tests
pytest cortex/tests/test_prompt_learning.py

# Integration test
python cortex/intelligence/prompt_learning.py learn 7
python cortex/intelligence/prompt_learning.py correlations
```

## Troubleshooting

**No sessions found:**
- Check `~/Library/Application Support/Claude/local-agent-mode-sessions/` exists
- Verify you have audit.jsonl files
- Try `ls -la ~/Library/Application\ Support/Claude/local-agent-mode-sessions/`

**Analysis seems wrong:**
- Clear cache: `rm ~/.cortex/prompt_learning/prompt_analysis.json`
- Re-run with more days: `/prompt-learn analyze`
- Check category patterns in `prompt_history.py:CATEGORY_PATTERNS`

**Performance issues:**
- Reduce `days_to_analyze` in config
- Increase `min_pattern_frequency` to filter noise
- Use `max_sessions` parameter to limit processing

## Learn More

- `cortex/intelligence/prompt_history.py` - Core analyzer
- `cortex/intelligence/prompt_learning.py` - Learning loop
- `cortex/learning.py` - Base learning system
- `cortex/intelligence/memory/pattern_memory.py` - Pattern memory

---

**Start learning now:**
```bash
/prompt-learn
```

The more you use Claude Code, the smarter Cortex becomes! 🧠✨
