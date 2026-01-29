# Prompt Learning Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         YOU (Human)                                 │
│                 Using Claude Code daily                             │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Every conversation
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVERSATION STORAGE                             │
│  ~/Library/Application Support/Claude/local-agent-mode-sessions/    │
│                                                                     │
│  Each session stores:                                              │
│    • User prompts (what you ask)                                   │
│    • Assistant responses                                           │
│    • Tool usage                                                    │
│    • Success/failure outcomes                                      │
│    • Timestamps, context, metadata                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Analyzed by
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│               PROMPT HISTORY ANALYZER                               │
│          cortex/intelligence/prompt_history.py                      │
│                                                                     │
│  Extracts:                                                         │
│    ┌─────────────┬─────────────┬─────────────┬─────────────┐      │
│    │  PATTERNS   │  PRIORITIES │  WORKFLOWS  │  SIGNALS    │      │
│    └──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┘      │
│           │             │             │             │              │
│    • Topics      • Categories  • Sequences  • Urgency              │
│    • Keywords    • Strength    • Success    • Recency              │
│    • Frequency   • Trends      • Duration   • Tools                │
│    • Projects    • Evidence    • Triggers   • Context              │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Feeds into
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   LEARNING LOOP                                     │
│          cortex/intelligence/prompt_learning.py                     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  1. RECOMMENDATION GENERATION                               │   │
│  │     • Priority-based: "Focus on X (60% of recent work)"     │   │
│  │     • Pattern-based: "Continue work on Y"                   │   │
│  │     • Workflow-based: "Follow your Z workflow"              │   │
│  │     • Context-based: "You haven't touched A in 14 days"     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  2. WEIGHT ADJUSTMENT                                       │   │
│  │     Category weights: {"fix": 1.3x, "feature": 0.8x, ...}  │   │
│  │     Based on YOUR actual priorities                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  3. OUTCOME CORRELATION                                     │   │
│  │     Tracks: What prompts → successful sessions?             │   │
│  │     Learns: "debug" prompts = 85% success rate              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  4. NEXT ACTION PREDICTION                                  │   │
│  │     "Based on patterns, you'll work on X next"              │   │
│  │     Uses: frequency + recency + project context             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Optimizes
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 EXISTING CORTEX SYSTEMS                             │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ PATTERN MEMORY   │  │ LEARNING SYSTEM  │  │ UNIFIED INTEL    │ │
│  │ pattern_memory.py│  │ learning.py      │  │ unified_intel.py │ │
│  │                  │  │                  │  │                  │ │
│  │ Cross-reference  │  │ Confidence       │  │ Context          │ │
│  │ conversation +   │  │ adjustment based │  │ selection based  │ │
│  │ git patterns     │  │ on weights       │  │ on predictions   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │ SESSION MGR      │  │ RECOMMENDATION   │  │ PORTFOLIO MEM    │ │
│  │ session_mgr.py   │  │ smart_gen.py     │  │ portfolio_mem.py │ │
│  │                  │  │                  │  │                  │ │
│  │ Continuity       │  │ Personalized     │  │ Project          │ │
│  │ across sessions  │  │ suggestions      │  │ associations     │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Produces
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PERSONALIZED RECOMMENDATIONS                           │
│                                                                     │
│  • Tuned to YOUR priorities                                        │
│  • Based on YOUR patterns                                          │
│  • Predicting YOUR next needs                                      │
│  • Optimized for YOUR workflow                                     │
│  • Improving OVER TIME                                             │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ Back to
                           ▼
                     YOU (next session)
                           │
                           └──────> LOOP CONTINUES
```

## Data Flow

### 1. Ingestion Phase
```
Claude Code Session
      ↓
User Prompt: "Debug GRIB validation in VortexV2"
      ↓
Saved to: audit.jsonl
      ↓
{
  "type": "user",
  "message": {"content": "Debug GRIB validation in VortexV2"},
  "timestamp": "2026-01-28T10:30:00Z",
  "session_id": "abc123",
  "cwd": "/Users/jesse/Dev/Vortex/VortexV2"
}
```

### 2. Analysis Phase
```
Prompt: "Debug GRIB validation in VortexV2"
      ↓
Pattern Extraction:
  • Topic: "debug grib validation in"
  • Keywords: ["debug", "grib", "validation", "vortex"]
  • Category: "fix"
  • Urgency: 0.8 (keyword "debug" detected)
  • Project: "VortexV2"
      ↓
Aggregation:
  • "fix" category: 5th occurrence this week
  • "GRIB" topic: 3rd occurrence this week
  • VortexV2 project: 80% of recent work
```

### 3. Learning Phase
```
Aggregated Data:
  • "fix" appears 8 times in 7 days = 57% of activity
  • "feature" appears 3 times = 21%
  • "research" appears 3 times = 21%
      ↓
Priority Calculation:
  • "fix": strength=0.57, trend=increasing
  • "feature": strength=0.21, trend=stable
      ↓
Weight Adjustment:
  • "fix": 1.0 → 1.3x (boosted)
  • "feature": 1.0 → 0.8x (reduced)
      ↓
Saved to: category_weights.json
```

### 4. Recommendation Phase
```
Next session starts
      ↓
Cortex makes recommendation:
  • Base: "Work on VortexV2 validation"
  • Confidence: 0.7
      ↓
Optimization:
  • Load weights: {"fix": 1.3x}
  • Adjust: 0.7 × 1.3 = 0.91
  • Reason: "Boosted by 30% - your top priority (fix work)"
      ↓
Enhanced recommendation:
  [0.91] Work on VortexV2 GRIB validation
    (Your top priority - 57% of recent work, increasing trend)
```

### 5. Outcome Correlation Phase
```
Session Outcome:
  • User followed recommendation: YES
  • Session completed successfully: YES
      ↓
Correlation Update:
  • "fix" + "VortexV2" + success → 85% success rate (was 80%)
  • Next time: boost confidence even more
      ↓
Self-improvement:
  Week 1: 0.7 → Week 2: 0.91 → Week 3: 0.95
```

## Key Components

### PromptHistoryAnalyzer
**File**: `cortex/intelligence/prompt_history.py`

**Responsibilities**:
- Extract sessions from audit.jsonl files
- Parse prompts, responses, tool usage
- Detect patterns, priorities, workflows
- Calculate urgency, recency, frequency
- Save analysis to cache

**Key Methods**:
- `extract_sessions(days_back)` - Get conversation data
- `analyze_prompt_patterns(sessions)` - Find recurring patterns
- `analyze_priorities(sessions)` - Detect current priorities
- `detect_workflows(sessions)` - Find common sequences
- `save_analysis()` - Cache results

### PromptLearningLoop
**File**: `cortex/intelligence/prompt_learning.py`

**Responsibilities**:
- Run full learning cycle
- Generate recommendations from patterns
- Update Cortex learning weights
- Correlate prompts with outcomes
- Predict next actions

**Key Methods**:
- `analyze_and_learn(days_back)` - Main entry point
- `get_optimized_recommendation()` - Adjust confidence
- `get_next_action_prediction()` - Predict next work
- `correlate_prompts_with_outcomes()` - Learn success patterns

### Integration Points

**PatternMemory** (`pattern_memory.py`)
```python
# Cross-reference prompt patterns with git patterns
prompt_patterns = analyzer.analyze_prompt_patterns(sessions)
git_patterns = pattern_memory.find_similar_solutions(task)

# Combine insights:
"You asked about X 5 times AND modified similar code 3 times"
```

**LearningSystem** (`learning.py`)
```python
# Adjust confidence based on prompt-derived weights
adjusted, reason = learning_loop.get_optimized_recommendation(
    recommendation_type="fix",
    base_confidence=0.7,
    context={}
)
# Result: (0.91, "Boosted by 30% - your top priority")
```

**UnifiedIntelligence** (`unified_intelligence.py`)
```python
# Use predictions to inform recommendations
prediction = loop.get_next_action_prediction(context)
# "Based on your patterns, you'll work on GRIB validation next"

# Load relevant context proactively
intelligence.load_context_for(prediction)
```

## Storage Layout

```
~/.cortex/prompt_learning/
├── prompt_analysis.json          # Current state
│   ├── timestamp
│   ├── patterns[]                # Detected patterns
│   ├── priorities[]              # Current priorities
│   └── workflows[]               # Workflow sequences
│
├── category_weights.json         # Learning weights
│   ├── timestamp
│   ├── weights{}                 # {"fix": 1.3, "feature": 0.8}
│   └── priorities[]              # Evidence
│
└── learning_state.jsonl          # Historical log
    └── [append-only history]
```

## Execution Flow

### Manual Execution
```bash
/prompt-learn
      ↓
1. Extract sessions (30 days)
2. Analyze patterns/priorities/workflows
3. Generate recommendations
4. Update weights
5. Save to cache
6. Display results
```

### Automatic Execution (Future)
```bash
claude start
      ↓
startup hook → /prompt-learn quick (if cache > 24h old)
      ↓
1. Quick analysis (7 days)
2. Silent update
3. Ready for session with optimized weights
```

### API Usage
```python
from cortex.intelligence.prompt_learning import PromptLearningLoop

loop = PromptLearningLoop()

# Full analysis
result = loop.analyze_and_learn(days_back=30)

# Use in recommendations
for rec in result['recommendations']:
    print(f"[{rec['confidence']:.0%}] {rec['content']}")

# Optimize existing recommendation
adjusted, reason = loop.get_optimized_recommendation(
    recommendation_type="fix",
    base_confidence=0.7,
    context={"project": "VortexV2"}
)
```

## Performance Characteristics

### Time Complexity
- Session extraction: O(n) where n = number of audit.jsonl files
- Pattern analysis: O(m) where m = number of prompts
- Total: ~1-5 seconds for 30 days of history

### Space Complexity
- Cache files: ~10-50 KB
- Analysis data: ~100-500 KB
- Total: < 1 MB

### Optimization Strategies
- File read is parallelizable (future enhancement)
- Cache with TTL (24h default)
- Incremental updates (only process new sessions)

## Security & Privacy

### Data Isolation
- All data stays local (no external APIs)
- No telemetry or reporting
- Can be disabled completely

### Access Control
- Files owned by user
- Standard file permissions
- No network access required

### Data Retention
- User controls retention period
- Can clear cache at any time: `rm -rf ~/.cortex/prompt_learning/`
- Source data (audit.jsonl) managed by Claude Code

## Extension Points

### Custom Analyzers
```python
class CustomPromptAnalyzer(PromptHistoryAnalyzer):
    def _categorize_prompt(self, prompt: str) -> List[str]:
        # Add custom categories
        categories = super()._categorize_prompt(prompt)

        # Your custom logic
        if "optimization" in prompt.lower():
            categories.append("performance")

        return categories
```

### Custom Learning Rules
```python
class CustomLearningLoop(PromptLearningLoop):
    def _generate_recommendations(self, patterns, priorities, workflows):
        # Add custom recommendation logic
        recs = super()._generate_recommendations(patterns, priorities, workflows)

        # Your custom recommendations
        recs.append(PromptBasedRecommendation(...))

        return recs
```

### Plugin Architecture (Future)
```python
# ~/.cortex/plugins/my_prompt_plugin.py
class MyPromptPlugin:
    def on_pattern_detected(self, pattern):
        # React to detected patterns
        pass

    def on_learning_complete(self, result):
        # React to learning completion
        pass
```

## Monitoring & Debugging

### Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("cortex.prompt_learning")

# Will log:
# - Sessions extracted
# - Patterns detected
# - Weights adjusted
# - Recommendations generated
```

### Debug Mode
```bash
# Verbose output
CORTEX_DEBUG=1 /prompt-learn analyze

# Show detailed analysis
python cortex/intelligence/prompt_history.py stats
python cortex/intelligence/prompt_learning.py weights
```

### Health Checks
```bash
# Check if analysis is fresh
stat ~/.cortex/prompt_learning/prompt_analysis.json

# Validate cache
python cortex/intelligence/prompt_learning.py correlations
```

## Integration Timeline

### Phase 1: Core (✅ Complete)
- [x] Prompt history extraction
- [x] Pattern analysis
- [x] Learning loop
- [x] Weight optimization
- [x] Documentation

### Phase 2: Enhanced Integration (Next)
- [ ] Auto-run on startup hook
- [ ] Integrate with `/status` command
- [ ] Integrate with `/next` command
- [ ] Integrate with `/briefing` command

### Phase 3: Advanced Features (Future)
- [ ] NLP-based topic modeling
- [ ] Embedding-based similarity
- [ ] Temporal patterns (time-of-day)
- [ ] Multi-session workflow detection

### Phase 4: Intelligence Amplification (Future)
- [ ] Proactive reminders
- [ ] Stuck detection
- [ ] Optimal timing suggestions
- [ ] Style learning

---

**This creates exponential idea augmentation through continuous learning from your actual behavior.**
