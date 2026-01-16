# Cortex Intelligent Orchestrator

**Status:** Design Phase - Ready for Implementation
**Author:** Claude Sonnet 4.5
**Date:** 2026-01-15
**Version:** 2.0 (Orchestrator Scope)

## Executive Summary

Intelligent multi-agent orchestration system that maximizes productivity under time and cost constraints. Automatically plans optimal work sessions by:
1. Prioritizing tasks based on value and urgency
2. Decomposing complex workflows into parallel subtasks
3. Allocating resources to maximize output within budget
4. **Selecting optimal models (Haiku/Sonnet/Opus) per task**
5. Executing with intelligent failure recovery
6. Learning from outcomes to continuously improve

**Model Selection** is a critical component that enables context-aware model recommendations based on budget, time pressure, task criticality, and historical performance.

**Key Benefits:**
- **2-5x productivity increase** through intelligent orchestration
- **20-30% cost reduction** through optimal model selection
- **Reduced decision fatigue** - system makes 50+ decisions per session
- **Intelligent failure recovery** - automatic retry with model upgrades
- **Self-improving** - learns from outcomes over time

## Problem Statement

Currently, development workflows are manual and suboptimal:
- Users must manually prioritize tasks from many recommendations
- Model selection is manual (Haiku vs Sonnet vs Opus)
- No parallelization - tasks executed sequentially
- Failures require manual intervention and retry
- No learning from outcomes to improve over time

**Evidence from Cortex:**
- Recurring cortex-hint: "Pattern: Higher than usual corrections detected"
- This suggests suboptimal model selection AND task prioritization
- User goal: "increase productivity/output with intelligent full prioritized agent orchestration"
- Desired outcome: System handles orchestration, user focuses on code

## Solution: Intelligent Orchestration

**Core Innovation:** Instead of just recommending models, orchestrate entire work sessions to maximize productivity per dollar.

## Solution Architecture

### Five-Phase Orchestration Pipeline

```
USER INPUT: Time budget (2h), Cost budget ($5), Context
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: PLANNING                                           │
│  ┌────────────────┐  ┌─────────────────┐                   │
│  │ Task           │→ │ Workflow        │                   │
│  │ Prioritizer    │  │ Planner         │                   │
│  │ (existing)     │  │ (existing)      │                   │
│  │                │  │                 │                   │
│  │ • Get top 20   │  │ • Decompose     │                   │
│  │   tasks        │  │ • Parallelize   │                   │
│  │ • By priority  │  │ • Dependencies  │                   │
│  └────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: OPTIMIZATION [CORE]                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Multi-Objective Resource Allocator [NEW]            │  │
│  │                                                      │  │
│  │ Inputs:                                              │  │
│  │  • Workflows (estimated value, time, cost)          │  │
│  │  • Constraints (time_budget, cost_budget)           │  │
│  │                                                      │  │
│  │ Optimization (weighted):                            │  │
│  │  • 40%: Maximize high-priority tasks                │  │
│  │  • 30%: Maximize total tasks                        │  │
│  │  • 30%: Minimize budget waste                       │  │
│  │                                                      │  │
│  │ Algorithm: Weighted scoring + knapsack              │  │
│  │                                                      │  │
│  │ Outputs:                                             │  │
│  │  • Selected workflows (optimal subset)              │  │
│  │  • Wave structure (parallelization plan)            │  │
│  │  • Resource allocation (time/cost per wave)         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: MODEL SELECTION [THIS DESIGN]                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Context-Aware Model Recommender                      │  │
│  │                                                      │  │
│  │ For each task in selected workflows:                │  │
│  │                                                      │  │
│  │ Inputs:                                              │  │
│  │  • Task description & type                          │  │
│  │  • Remaining budget (from allocator)                │  │
│  │  • Remaining time (from allocator)                  │  │
│  │  • Task criticality (from prioritizer)              │  │
│  │  • Parallel load (from allocator)                   │  │
│  │  • Historical data (from learner)                   │  │
│  │                                                      │  │
│  │ Process:                                             │  │
│  │  1. Classify complexity (keyword + context)         │  │
│  │  2. Check learned recommendations                   │  │
│  │  3. Fall back to rules if needed                    │  │
│  │  4. Apply context adjustments                       │  │
│  │     - Low budget → prefer Haiku                     │  │
│  │     - Critical + retry → upgrade model              │  │
│  │     - Time pressure → prefer faster                 │  │
│  │                                                      │  │
│  │ Output: Model (haiku|sonnet|opus) + reasoning       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: EXECUTION                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Wave         │→ │ Progress     │→ │ Failure         │  │
│  │ Executor     │  │ Monitor      │  │ Handler [NEW]   │  │
│  │              │  │              │  │                 │  │
│  │ • Launch     │  │ • Track      │  │ Decision tree:  │  │
│  │   parallel   │  │   outcomes   │  │ 1. Classify     │  │
│  │   agents     │  │ • Real-time  │  │    failure      │  │
│  │ • Wait for   │  │   metrics    │  │ 2. Choose       │  │
│  │   completion │  │              │  │    recovery     │  │
│  │              │  │              │  │ 3. Execute      │  │
│  │              │  │              │  │    • Retry      │  │
│  │              │  │              │  │    • Upgrade    │  │
│  │              │  │              │  │    • Ask user   │  │
│  │              │  │              │  │    • Skip       │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: LEARNING                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Outcome Tracker (feedback.py extended)               │  │
│  │                                                      │  │
│  │ Three levels of tracking:                            │  │
│  │  • Model outcomes (per task)                        │  │
│  │  • Workflow outcomes (per workflow)                 │  │
│  │  • Session outcomes (per session)                   │  │
│  │                                                      │  │
│  │ Feeds into learners:                                 │  │
│  │  • Model learner → improve model selection          │  │
│  │  • Workflow learner → improve decomposition         │  │
│  │  • Allocator learner → improve optimization         │  │
│  │                                                      │  │
│  │ Storage: Pluggable (JSONL → SQLite when needed)     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
                   CONTINUOUS IMPROVEMENT
```

## Data Structures

### ModelOutcomeEntry
```python
@dataclass
class ModelOutcomeEntry:
    """Track model performance for learning."""
    timestamp: str
    task_id: str
    task_type: str              # "explore", "implement", "debug", etc.
    task_description: str        # First 200 chars

    # Model selection
    model_used: str              # "haiku" | "sonnet" | "opus"
    model_recommended_by: str    # "rules" | "learned" | "user_override"
    complexity_classified: str   # "simple" | "moderate" | "complex"
    confidence: float            # 0.0-1.0

    # Performance
    outcome: str                 # "success" | "partial" | "failed" | "retry_needed"
    tokens_used: int
    time_seconds: float
    error_count: int             # Number of corrections needed

    # Cost analysis
    estimated_cost_usd: float
    alternative_models: List[Dict[str, Any]]

    # Context
    project_name: str
    files_touched: List[str]
    context: Optional[Dict[str, Any]] = None
```

### ModelRecommendation
```python
@dataclass
class ModelRecommendation:
    """Recommendation with reasoning and alternatives."""
    model: str                      # "haiku" | "sonnet" | "opus"
    confidence: float               # 0.0-1.0
    reasoning: str                  # Human-readable explanation

    # Predictions
    estimated_success_rate: float   # Based on historical data
    estimated_tokens: int
    estimated_cost_usd: float

    # Evidence
    similar_tasks_count: int        # Historical sample size
    historical_success_rate: float  # For this model + task combo
    alternatives: List[Dict[str, Any]]
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Immediate value with rule-based recommendations

**Deliverables:**
1. Data structures in `feedback.py`
2. `TaskComplexityClassifier` - keyword + context analysis
3. `RuleBasedRecommender` - hardcoded rules for task types
4. `/next` command shows model recommendation
5. Logging infrastructure for model outcomes

**Success Criteria:**
- ✅ `/next` shows model recommendations
- ✅ All task types have rule-based coverage
- ✅ Model outcomes being logged

**Rules:**
```python
RULES = {
    "explore": "haiku",      # Fast exploration
    "search": "haiku",       # Simple search
    "read_file": "haiku",    # File reading
    "bug_fix": "sonnet",     # Needs context
    "implement": "sonnet",   # Multi-step
    "refactor": "opus",      # Complex architectural
    "design": "opus"         # Deep reasoning
}
```

### Phase 2: Learning Pipeline (Week 2-3)
**Goal:** Learn from actual usage patterns

**Deliverables:**
1. `ModelPerformanceLearner` - analyze historical outcomes
2. Hybrid recommender (learned + rules)
3. Confidence-based switching (use learned when confident)
4. Dashboard: model performance stats

**Success Criteria:**
- ✅ System learns from 50+ outcomes
- ✅ Learned recommendations when data sufficient
- ✅ Confidence scores improve with more data

**Learning Algorithm:**
```python
def get_best_model(task_type: str, optimize_for: str):
    """
    For each model, calculate:
    - Success rate from historical outcomes
    - Average token usage
    - Average cost

    Score based on optimization goal:
    - cost_efficiency: success_rate / cost
    - accuracy: success_rate
    - speed: 1 / tokens

    Return model with highest score + confidence
    """
```

### Phase 3: Integration & Automation (Week 4)
**Goal:** Automatic model selection in workflows

**Deliverables:**
1. `/next` auto-suggests model with alternatives
2. Task completion auto-logs model performance
3. Dashboard shows trends and patterns
4. CLI commands: `/model-stats`, `/model-recommend`

**Success Criteria:**
- ✅ 80%+ recommendations use learned data
- ✅ Auto-logging on task completion
- ✅ Dashboard shows actionable insights

### Phase 4: Advanced Features (Week 5+)
**Goal:** Predictive optimization

**Deliverables:**
1. `CostOptimizationAdvisor` - find savings opportunities
2. `RetryPredictor` - predict if retry likely
3. Pattern-based recommendations (using embeddings)
4. Batch analysis of optimal models

**Success Criteria:**
- ✅ Identifies 10%+ cost savings
- ✅ Retry predictor 70%+ accurate
- ✅ Monthly cost reduced via automation

## Integration Points

### Extends Existing Cortex Systems

**1. Learning System (`learning.py:34`)**
```python
class LearningSystem:
    def __init__(self, ...):
        self.model_learner = ModelPerformanceLearner(...)

    def get_model_recommendation(self, task_type, description, context):
        return ModelRecommender().recommend(...)
```

**2. Recommendation Engine (`recommendation_engine.py:155`)**
```python
class RecommendationEngine:
    def generate_recommendations(self, ...):
        # ... existing logic ...

        # Add model suggestions
        for rec in recommendations:
            model_rec = self.model_recommender.recommend(...)
            rec.metadata["recommended_model"] = model_rec.model
            rec.metadata["model_confidence"] = model_rec.confidence
```

**3. Process Monitor (`intelligence/process_monitor/tracker.py`)**
```python
class ProcessTracker:
    def track_claude_code_session(self, session_data):
        if "model_used" in session_data:
            feedback_logger.log_model_outcome(...)
```

**4. Batch Processing (`batch/batch_config.py`)**
```python
# Add "model_selection" feature flag
CORTEX_BATCH_MODEL_SELECTION_ENABLED=true
```

**5. CLI Commands (`.claude/commands/`)**
- `/model-stats` - Show performance statistics
- `/model-recommend [description]` - Get recommendation
- `/model-optimize` - Find cost savings

## File Structure

```
cortex/
├── feedback.py                          [EXTEND] Add ModelOutcomeEntry
├── learning.py                          [EXTEND] Add model_learner
├── recommendation_engine.py             [EXTEND] Add model metadata
│
├── intelligence/
│   └── model_selection/                 [NEW]
│       ├── __init__.py
│       ├── classifier.py                # TaskComplexityClassifier
│       ├── recommender.py               # ModelRecommender (hybrid)
│       ├── rules.py                     # RuleBasedRecommender
│       ├── learning.py                  # ModelPerformanceLearner
│       ├── tracker.py                   # PerformanceTracker
│       ├── analyzer.py                  # Analysis utilities
│       └── cost_optimizer.py            # CostOptimizationAdvisor
│
├── batch/
│   └── model_selection_batcher.py       [NEW]
│
├── .claude/
│   └── commands/
│       ├── model-stats.md               [NEW]
│       ├── model-recommend.md           [NEW]
│       └── model-optimize.md            [NEW]
│
└── docs/
    └── MODEL_SELECTION.md               [THIS FILE]
```

## Configuration

### Environment Variables

```bash
# Enable/disable model selection intelligence
CORTEX_MODEL_SELECTION=true

# Default optimization goal
CORTEX_MODEL_OPTIMIZE_FOR=cost_efficiency  # or "accuracy" or "speed"

# Minimum sample size before using learned recommendations
CORTEX_MODEL_MIN_SAMPLES=10

# Confidence threshold for using learned vs rules
CORTEX_MODEL_CONFIDENCE_THRESHOLD=0.6

# Batch processing for model analysis
CORTEX_BATCH_MODEL_SELECTION_ENABLED=false
```

## Usage Examples

### 1. Get Next Action with Model Recommendation
```bash
$ cx next

🎯 Next Action: Fix authentication bug in user_service.py
   The login endpoint is returning 500 errors

📊 Recommended Model: SONNET (confidence: 85%)
   [LEARNED] Based on 23 similar "bug_fix" tasks with 87% success rate

   Alternatives:
   • haiku: 62% success rate, $0.002 avg (not recommended - high retry rate)
   • opus: 91% success rate, $0.018 avg (minimal improvement for 3x cost)

   Estimated: ~2,500 tokens, $0.006, 87% success probability
```

### 2. Check Model Performance
```bash
$ cx model-stats

📊 Model Performance (Last 30 Days)

EXPLORE:
  haiku    | Success:  98% | Tokens:  1,200 | Cost: $0.0024 | (n=42)
  sonnet   | Success:  99% | Tokens:  2,100 | Cost: $0.0063 | (n=8)
  opus     | Success: 100% | Tokens:  3,400 | Cost: $0.0204 | (n=2)
  → Recommendation: Use Haiku (98% success, 50% cost of Sonnet)

BUG_FIX:
  haiku    | Success:  65% | Tokens:  1,800 | Cost: $0.0036 | (n=15)
  sonnet   | Success:  87% | Tokens:  3,200 | Cost: $0.0096 | (n=23)
  opus     | Success:  94% | Tokens:  5,100 | Cost: $0.0306 | (n=7)
  → Recommendation: Use Sonnet (best cost/accuracy balance)
```

### 3. Find Cost Optimization Opportunities
```bash
$ cx model-optimize

💰 Cost Optimization Analysis

Found 12 opportunities to save $8.40/month:

1. Task type "explore" - Switch from Sonnet to Haiku
   • 8 tasks last month
   • Haiku has 98% success rate vs 99% for Sonnet
   • Potential savings: $3.20/month

2. Task type "search" - Switch from Sonnet to Haiku
   • 15 tasks last month
   • Haiku has 100% success rate
   • Potential savings: $5.20/month
```

### 4. Get Recommendation for Custom Task
```bash
$ cx model-recommend "refactor the entire authentication system to use JWT"

📊 Model Recommendation: OPUS

Reasoning: [LEARNED] Based on 5 similar "refactor" tasks
- Complexity: COMPLEX (multi-file, architectural changes)
- Historical: 92% success with Opus vs 68% with Sonnet
- Estimated: ~8,500 tokens, $0.051

Alternatives:
• sonnet: 68% success, but high retry rate (avg 2.3 retries)
• haiku: Not recommended (0% success for complex refactoring)

⚠️  High complexity task - Opus recommended despite higher cost
```

### 5. Orchestrate Work Session (PRIMARY USE CASE)
```bash
$ cx orchestrate --time 2h --budget 5.00

🎯 Analyzing tasks and creating optimal plan...

📊 Orchestration Plan (2h 0m, $5.00 budget)
════════════════════════════════════════════════

Wave 1 (Parallel - Start immediately):
  ✓ Fix authentication bug in user_service.py [SONNET]
    Priority: HIGH | Est: 30min, $1.50 | Success: 87%

  ✓ Search for test coverage gaps [HAIKU]
    Priority: MEDIUM | Est: 10min, $0.30 | Success: 98%

Wave 2 (After Wave 1 completes):
  ✓ Implement JWT refresh token logic [SONNET]
    Priority: HIGH | Est: 45min, $2.10 | Success: 82%

Wave 3 (Quick wins batch):
  ✓ Fix typo in user_model.py [HAIKU]
  ✓ Update import statements in auth module [HAIKU]
  ✓ Add docstring to validate_token function [HAIKU]
    Priority: LOW | Est: 15min, $0.60 | Success: 99%

════════════════════════════════════════════════
Expected Outcomes:
  • Tasks completed: 6 / 20 candidates
  • High-priority tasks: 2 / 3 available
  • Total cost: $4.50 (90% budget utilization)
  • Total time: ~90min (75% time utilization)
  • Reserve: $0.50, 30min (for failures/adjustments)

Efficiency: 1.33 tasks/$, 4 tasks/hr

Reasoning:
  • Prioritized high-value auth bug fix
  • Parallelized search task (independent, fast)
  • Reserved budget for potential model upgrades
  • Batched quick wins for efficient completion
════════════════════════════════════════════════

Continue with this plan? [Y/n] y

🚀 Executing orchestration plan...

[Wave 1] Launching 2 agents in parallel...
  ✓ Agent 1 (Sonnet): Fix authentication bug... RUNNING
  ✓ Agent 2 (Haiku): Search test coverage... RUNNING

[Wave 1] Agent 2 completed successfully (8min, $0.28)
  ✓ Found 5 files with <80% coverage

[Wave 1] Agent 1 completed successfully (32min, $1.58)
  ✓ Auth bug fixed, tests passing

[Wave 2] Launching 1 agent...
  ✓ Agent 1 (Sonnet): Implement JWT refresh... RUNNING

[Wave 2] Agent 1 FAILED (12min, $0.52)
  ⚠️  Error: "Cannot determine token expiry logic without requirements"

  🔧 Intelligent Recovery:
     Failure type: Ambiguous requirements
     Recovery: Requesting clarification

     The task needs clarification on JWT refresh token expiry.
     Options:
       1. Use standard 7-day expiry (recommended)
       2. Make configurable (more work)
       3. Skip and ask in team standup

     Your choice: 1

  ✓ Retrying with additional context...
  ✓ Agent 1 (Sonnet): Implement JWT refresh... RUNNING
  ✓ Agent 1 completed successfully (38min, $1.98)

[Wave 3] Launching 3 quick-win tasks...
  ✓ All 3 tasks completed (12min, $0.54)

════════════════════════════════════════════════
📈 Session Complete!

Planned vs Actual:
  • Tasks: 6 / 6 completed (100%)
  • Cost: $4.90 / $5.00 (98% utilization)
  • Time: 102min / 120min (85% utilization)

  • High-priority: 2 / 2 completed ✓
  • Failures: 1 (recovered automatically)
  • Model upgrades: 0

Productivity:
  • 1.22 tasks/$ (vs 1.33 estimated)
  • 3.5 tasks/hr (vs 4.0 estimated)

  ⭐ Efficiency: 92% of optimal
════════════════════════════════════════════════

📊 Savings: Without orchestration, these tasks would have cost ~$7.20
    💰 You saved $2.30 through intelligent model selection
```

### 6. Session Performance Dashboard
```bash
$ cx session-stats

📊 Orchestration Performance (Last 30 Days)
════════════════════════════════════════════════

Sessions: 12
Avg duration: 98min
Avg cost: $4.23
Avg tasks completed: 5.8

Efficiency Trends:
  Tasks per dollar:     1.37 avg (↑ 18% vs Week 1)
  Tasks per hour:       3.54 avg (↑ 22% vs Week 1)
  Budget utilization:   88% avg
  Time utilization:     82% avg

High-Priority Task Completion:
  Planned: 34 tasks
  Completed: 31 tasks (91%)

Multi-Objective Success:
  ✓ Maximizing high-priority: 91% completion
  ✓ Maximizing total tasks: 5.8 avg vs 3.2 manual
  ✓ Minimizing waste: 88% budget utilization

Failure Recovery:
  Total failures: 8
  Auto-recovered: 7 (87%)
  Model upgrades used: 5
  User escalations: 1

  Recovery success rate: 87%
  Avg recovery cost: $0.45 additional

Learning Progress:
  Model selection confidence: 78% (was 55% Week 1)
  Learned task types: 18
  Orchestration improvements:
    • Better wave sizing (fewer context switches)
    • Smarter reserve allocation (reduced waste)
    • Improved failure prediction (80% accuracy)

════════════════════════════════════════════════
💡 Insights:

1. Orchestration has increased your productivity by 2.4x
   (vs manual task-by-task execution)

2. You're saving ~$2.80/session through smart model selection

3. High-priority tasks are completing 91% of the time
   (vs 73% before orchestration)

4. Suggestion: Enable more parallel agents (currently 2-3 avg)
   to increase tasks/hour further
```

## Expected Results

### Productivity Gains (Primary Metric)
```
Week 1:  1.5x productivity (rule-based orchestration, parallel execution)
Week 2:  1.8x productivity (basic learned model selection)
Week 4:  2.2x productivity (confident orchestration, fewer failures)
Week 8:  2.5-3x productivity (mature system, optimal resource allocation)

Measured as: (tasks completed per hour) vs baseline manual execution
```

### Cost Efficiency Trajectory
```
Week 1:  5-10% savings (avoid obvious over-engineering)
Week 2:  10-15% savings (basic learned model selection)
Week 4:  20-25% savings (confident model recommendations)
Week 8:  25-35% savings (mature system with pattern matching)

Includes both:
- Model selection savings (20-30%)
- Parallelization efficiency gains (5-10%)
```

### High-Priority Task Completion
```
Week 1:  80% of high-priority tasks completed (vs 70% manual)
Week 2:  85% (better resource allocation)
Week 4:  90% (confident prioritization)
Week 8:  92-95% (mature optimization)

Multi-objective optimization ensures high-value work gets done first
```

### Learning Curve (Model Selection Component)
```
Week 1:  Rule-based (60% accuracy)
Week 2:  10 learned task types (70% accuracy)
Week 4:  30 learned task types (80% accuracy)
Week 8:  50+ learned task types (85%+ accuracy)
```

### Failure Recovery Success Rate
```
Week 1:  70% auto-recovery (rule-based classification)
Week 2:  80% auto-recovery (learned failure patterns)
Week 4:  85% auto-recovery (confident recovery strategies)
Week 8:  90%+ auto-recovery (mature intelligent recovery)

Reduces user interruptions and maintains productivity momentum
```

### Confidence Growth (Model Selection)
```
Initial:   Rules have 0.5-0.6 confidence
10 tasks:  0.6-0.7 confidence
50 tasks:  0.7-0.8 confidence
100 tasks: 0.8-0.9 confidence
```

## Key Design Principles

1. **Opt-in by default** - Enable via environment variable
2. **No breaking changes** - Purely additive enhancements
3. **Explainable recommendations** - Always show reasoning
4. **Graceful degradation** - Fall back to rules when data insufficient
5. **Self-improving** - Automatically learns from usage
6. **Cost-conscious** - Optimize for cost-efficiency by default
7. **Transparent** - Show alternatives and tradeoffs

## Risk Mitigation

### Risk: Insufficient data for learning
**Mitigation:** Rule-based fallback always available

### Risk: Model recommendations cause failures
**Mitigation:** Track outcomes, downrank failing recommendations

### Risk: Over-optimization for cost (sacrificing quality)
**Mitigation:** Configurable optimization goal, always show alternatives

### Risk: Learning from biased data
**Mitigation:** Show sample sizes, confidence scores, allow user override

### Risk: Integration breaks existing workflows
**Mitigation:** Opt-in via environment variable, no changes to existing code

## Future Enhancements

1. **Context-aware recommendations** - Consider time of day, project phase
2. **Team learning** - Share model performance data across team
3. **A/B testing** - Randomly try alternative models to gather data
4. **Prompt optimization** - Suggest prompt improvements based on outcomes
5. **Budget constraints** - Respect daily/monthly cost limits
6. **Multi-model workflows** - Use different models for different subtasks

## Success Metrics

**Phase 1 (Week 1):**
- ✅ Rule-based recommendations in `/next`
- ✅ 100% task type coverage
- ✅ Logging infrastructure working

**Phase 2 (Week 3):**
- ✅ 50+ logged outcomes
- ✅ 10+ task types with learned recommendations
- ✅ Confidence > 0.7 for learned recommendations

**Phase 3 (Week 4):**
- ✅ 80% of recommendations use learned data
- ✅ Dashboard shows actionable insights
- ✅ Auto-logging on task completion

**Phase 4 (Week 8):**
- ✅ 20% cost reduction achieved
- ✅ Retry rate decreased by 15%
- ✅ 85%+ recommendation accuracy

## References

- Existing Cortex learning system: `learning.py:34`
- Feedback infrastructure: `feedback.py:29`
- Pattern memory: `intelligence/memory/pattern_memory.py`
- Batch processing: `batch/batch_config.py`
- Process monitoring: `intelligence/process_monitor/`

---

**Next Steps:**
1. Review and refine this design
2. Get team/user approval
3. Implement Phase 1
4. Deploy and collect data
5. Iterate based on learnings
