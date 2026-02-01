# Prompt Learning - Quick Start Guide

## What You Just Built

You now have a **self-improving intelligence system** that learns from your conversation patterns and optimizes Cortex recommendations based on what you actually ask for.

## The Power of Prompt Learning

Every conversation you have with Claude Code is now feeding into Cortex's learning system:

```
Your Prompt: "Debug the GRIB validation failing in VortexV2"
              ↓
         [CAPTURED & ANALYZED]
              ↓
     ┌────────┴────────┐
     │  Pattern Detected: │
     │  • Topic: "GRIB validation"   │
     │  • Project: VortexV2          │
     │  • Category: fix              │
     │  • Urgency: high              │
     │  • Frequency: 5 times/week    │
     └────────┬────────┘
              ↓
     [CORTEX LEARNS]
              ↓
     "fix" category weight: 0.7 → 1.2x
     "VortexV2" priority: +30%
     Next prediction: "You'll work on GRIB next"
              ↓
     [BETTER RECOMMENDATIONS]
```

## How It Works - 3 Layers

### Layer 1: Pattern Extraction
**File**: `cortex/intelligence/prompt_history.py`

Scans your Claude Code conversation history and extracts:
- **Topics** - What you work on ("GRIB validation", "authentication", "deployment")
- **Priorities** - What's important now (features vs fixes vs research)
- **Workflows** - Your typical sequences (investigate → plan → implement → test)
- **Urgency** - What's urgent vs exploratory
- **Tool Usage** - Which tools you use for which tasks

### Layer 2: Learning Loop
**File**: `cortex/intelligence/prompt_learning.py`

Creates a feedback loop:
1. Analyzes patterns from Layer 1
2. Generates recommendations based on what you actually do
3. Adjusts Cortex confidence weights based on your priorities
4. Correlates prompts with outcomes (what works vs what doesn't)
5. Predicts your next actions

### Layer 3: Integration
Feeds learning back into existing Cortex systems:
- **PatternMemory** - Cross-reference conversation patterns with git patterns
- **LearningSystem** - Adjust recommendation confidence scores
- **UnifiedIntelligence** - Inform context selection
- **SessionManager** - Maintain continuity across sessions

## How To Use It

### Option 1: Automatic (Recommended)
Add to `~/.cortex/prompt_learning_config.json`:
```json
{
  "auto_run_on_startup": true,
  "cache_ttl_hours": 24
}
```

Now every time you start a session, Cortex automatically learns from your recent conversations.

### Option 2: Manual
Run the learning loop whenever you want:

```bash
# Analyze last 30 days and optimize Cortex
/prompt-learn

# Quick analysis (7 days)
/prompt-learn quick

# See what it learned
/prompt-learn insights

# Detailed analysis with correlations
/prompt-learn analyze
```

### Option 3: Programmatic
```python
from cortex.intelligence.prompt_learning import PromptLearningLoop

loop = PromptLearningLoop()

# Run learning
result = loop.analyze_and_learn(days_back=30)

# Get recommendations
for rec in result['recommendations']:
    print(f"[{rec['confidence']:.0%}] {rec['content']}")

# Use for next prediction
prediction = loop.get_next_action_prediction({
    "cwd": "/Users/jesse.kemp/Dev/Vortex/VortexV2"
})
```

## Example Scenario

**Day 1-7: You work on bug fixes**
```
Your prompts:
- "Fix authentication failing"
- "Debug GRIB parser error"
- "Investigate test failures"
- "Quick fix for deployment"
```

**Learning System Detects:**
```
Priority: "fix" (80% of activity)
Trend: increasing
Urgency: high
```

**Cortex Adjusts:**
```
Recommendation confidence:
  fix work: +40% boost
  feature work: -30% reduction

Next prediction:
  "You'll likely continue debugging - check error logs"
```

**Day 8: Cortex proactively suggests:**
```
[0.85] Focus on fix work - 80% of recent activity (increasing)
[0.72] Check VortexV2 GRIB validation - worked on 5 times this week
[0.68] Your typical workflow: investigate → plan → implement → test
```

**Day 14: Pattern shifts**
```
New priority detected: "feature" (60% of activity)
Trend: increasing
Old priority "fix": decreasing

Cortex adapts:
  feature work: +30% boost
  fix work: back to baseline

Reminder:
  "You haven't worked on 'authentication' in 10 days - was this resolved?"
```

## What Gets Smarter

### 1. Recommendations
Before: Generic suggestions based on static rules
After: Personalized based on YOUR actual patterns

### 2. Confidence Scores
Before: Fixed confidence (0.7, 0.8, etc.)
After: Dynamic adjustment (+/- 50% based on your priorities)

### 3. Context Selection
Before: Generic context loading
After: "You asked about GRIB 5 times - loading GRIB-related context"

### 4. Next Action Prediction
Before: No prediction
After: "Based on your workflow, you'll likely run tests next"

### 5. Workflow Optimization
Before: No workflow awareness
After: "You typically spend 45min on this type of task with 87% success rate"

## The Self-Improving Loop

```
┌─────────────────────────────────────────────────┐
│  Week 1: Baseline                               │
│  Cortex makes generic recommendations           │
│  Confidence: 0.7                                │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  You: "Fix GRIB validation" (5 times)           │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  Learning: "fix" is high priority               │
│  Adjust weights: fix = 1.3x                     │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  Week 2: Improved                               │
│  Cortex boosts fix recommendations              │
│  Confidence: 0.7 × 1.3 = 0.91                   │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  You: Follow recommendations more (92% success) │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  Learning: High success rate → increase further │
│  Adjust weights: fix = 1.5x                     │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│  Week 3: Optimized                              │
│  Cortex highly tuned to your patterns           │
│  Success rate: 95%                              │
└─────────────────────────────────────────────────┘
```

**The more you use it, the smarter it gets!**

## Where Data Lives

All data stays local on your machine:

```
~/.cortex/prompt_learning/
  ├── prompt_analysis.json        # Current patterns/priorities/workflows
  ├── category_weights.json       # Learning weights
  └── learning_state.jsonl        # Historical learning log

~/Library/Application Support/Claude/
  └── local-agent-mode-sessions/  # Your conversation history (source data)
```

## Integration with Existing Commands

The learning system automatically enhances your existing skills:

### `/status` - Now shows predicted next action
```
=== Status ===
...
Next Action (predicted): Continue work on GRIB validation
  Based on: 5 sessions this week, 87% success rate
```

### `/next` - Now uses prompt patterns
```
=== Next Recommendation ===
[0.92] Focus on VortexV2 GRIB debugging
  (Your top priority - 60% of recent work)
```

### `/briefing` - Now includes pattern insights
```
=== Morning Briefing ===
Priorities detected from your recent work:
  • fix: 70% (increasing) ← Top priority
  • test: 20% (stable)
  • feature: 10% (decreasing)

Recommended focus today: Continue debugging work
```

## Quick Reference

| Command | What It Does |
|---------|-------------|
| `/prompt-learn` | Full analysis (30 days) + optimize Cortex |
| `/prompt-learn quick` | Quick analysis (7 days) |
| `/prompt-learn insights` | Show current recommendations |
| `/prompt-learn analyze` | Detailed analysis with correlations |

| File | Purpose |
|------|---------|
| `prompt_history.py` | Pattern extraction from conversations |
| `prompt_learning.py` | Learning loop and optimization |
| `PROMPT_LEARNING.md` | Full documentation |
| `PROMPT_LEARNING_QUICKSTART.md` | This guide |

## Next Steps

1. **Let it learn**: Just use Claude Code normally for a week
2. **Run analysis**: After a week, run `/prompt-learn`
3. **See the magic**: Watch your recommendations get better
4. **Iterate**: The system improves continuously

## Advanced: Create Custom Learning Rules

You can create custom learning rules in `~/.cortex/prompt_learning_config.json`:

```json
{
  "category_weights": {
    "fix": 1.2,        // Boost bug fix recommendations by 20%
    "research": 0.8,   // Reduce research recommendations by 20%
    "deploy": 1.5      // Strongly boost deployment recommendations
  },
  "workflow_templates": {
    "debug": ["investigate", "reproduce", "fix", "test", "deploy"],
    "feature": ["research", "plan", "implement", "test", "docs", "deploy"]
  },
  "urgency_boost": 1.3,  // How much to boost urgent items
  "recency_decay_days": 14  // How quickly old patterns decay
}
```

## Troubleshooting

**"No sessions found"**
- You need to have used Claude Code for a while to build history
- Check `~/Library/Application Support/Claude/local-agent-mode-sessions/` exists
- Try with longer timeframe: `/prompt-learn` (analyzes 30 days by default)

**"Recommendations seem off"**
- Learning needs more data - use Claude Code for another week
- Clear cache and re-analyze: `rm ~/.cortex/prompt_learning/*.json && /prompt-learn`
- Adjust weights manually in `~/.cortex/prompt_learning_config.json`

**"Performance is slow"**
- Reduce analysis window: edit `days_to_analyze` in config
- Increase `min_pattern_frequency` to filter noise
- Clear old sessions from `~/Library/Application Support/Claude/`

## The Big Picture

This system creates **exponential idea augmentation** by:

1. **Learning YOUR patterns** - Not generic best practices, YOUR actual workflow
2. **Predicting YOUR needs** - Based on what you actually ask for
3. **Optimizing FOR YOU** - Recommendations tuned to your priorities
4. **Improving OVER TIME** - Gets smarter the more you use it

**Result**: A truly personalized AI collaborator that understands how you work and helps you work better.

---

**Start the learning loop:**
```bash
/prompt-learn
```

🧠 **The more conversations you have, the smarter Cortex becomes!**
