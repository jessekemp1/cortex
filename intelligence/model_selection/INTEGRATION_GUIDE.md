# Model Selection - Week 1 Integration Guide

**Status:** Ready for Integration
**Created:** 2026-01-15
**Components:** Foundation layer for intelligent model selection

## Overview

Week 1 implements the foundation for context-aware model selection:
- ✅ Data structures for outcome tracking
- ✅ Pluggable storage layer (JSONL implementation)
- ✅ Task complexity classifier
- ✅ Rule-based recommender (fallback)
- ✅ Context-aware model selector

## Quick Start

### 1. Setup Python Path

Add cortex to your PYTHONPATH:

```bash
export PYTHONPATH="/Users/jesse.kemp/Dev/cortex:$PYTHONPATH"
```

Or add to your `.bashrc`/`.zshrc`.

### 2. Test Installation

```bash
cd /Users/jesse.kemp/Dev/cortex
python3 -c "from intelligence.model_selection import ContextAwareModelRecommender; print('✓ Import successful')"
```

### 3. Run Tests

```bash
pytest tests/test_model_selection.py -v
```

## Usage Examples

### Basic Model Recommendation

```python
from datetime import timedelta
from intelligence.model_selection import (
    ContextAwareModelRecommender,
    OrchestrationContext
)

# Create recommender
recommender = ContextAwareModelRecommender()

# Create context
context = OrchestrationContext(
    remaining_budget=5.00,
    remaining_time=timedelta(hours=2),
    task_priority="high",
    project="cortex",
    files=[]
)

# Get recommendation
rec = recommender.recommend(
    task_description="fix authentication bug in user_service.py",
    task_type="bug_fix",
    context=context
)

print(f"Recommended model: {rec.model}")
print(f"Reasoning: {rec.reasoning}")
print(f"Estimated cost: ${rec.estimated_cost_usd:.4f}")
```

### Log Model Outcomes

```python
from datetime import datetime
from intelligence.model_selection.models import ModelOutcomeEntry
from intelligence.storage import get_storage

# After task completes, log outcome
entry = ModelOutcomeEntry(
    timestamp=datetime.now().isoformat(),
    task_id="task_001",
    task_type="bug_fix",
    task_description="Fix auth bug",
    model_used="sonnet",
    model_recommended_by="rules",
    complexity_classified="moderate",
    confidence=0.7,
    outcome="success",
    tokens_used=2500,
    time_seconds=180,
    error_count=0,
    estimated_cost_usd=0.019,
    project_name="cortex",
    files_touched=["user_service.py"]
)

# Save to storage
storage = get_storage()
storage.log_model_outcome(entry)
```

### Load Historical Outcomes

```python
from intelligence.storage import get_storage

storage = get_storage()

# Load all outcomes from last 30 days
outcomes = storage.load_model_outcomes(days=30)

print(f"Total outcomes: {len(outcomes)}")

# Filter by task type
bug_fixes = storage.load_model_outcomes(days=30, task_type="bug_fix")
print(f"Bug fix outcomes: {len(bug_fixes)}")
```

## Integration with Existing Cortex

### Extend `/next` Command

Add model recommendation to the `/next` command:

```python
# In cli.py or wherever /next is implemented

from intelligence.model_selection import ContextAwareModelRecommender, OrchestrationContext
from datetime import timedelta

def cmd_next():
    """Get next recommended action with model suggestion."""

    # Existing recommendation logic
    engine = RecommendationEngine()
    recs = engine.generate_recommendations(limit=1)

    if not recs:
        print("No recommendations at this time.")
        return

    top_rec = recs[0]

    # NEW: Add model recommendation
    recommender = ContextAwareModelRecommender()
    context = OrchestrationContext(
        remaining_budget=5.00,  # TODO: Get from user config
        remaining_time=timedelta(hours=2),
        task_priority=top_rec.priority,
        project="cortex",  # TODO: Detect current project
        files=top_rec.files or []
    )

    model_rec = recommender.recommend(
        task_description=top_rec.description,
        task_type=top_rec.type,
        context=context
    )

    # Display
    print(f"\n🎯 Next Action: {top_rec.title}")
    print(f"   {top_rec.description}\n")
    print(f"📊 Recommended Model: {model_rec.model.upper()} (confidence: {model_rec.confidence:.0%})")
    print(f"   {model_rec.reasoning}")
    print(f"   Estimated: ~{model_rec.estimated_tokens} tokens, ${model_rec.estimated_cost_usd:.4f}\n")

    if model_rec.alternatives:
        print("   Alternatives:")
        for alt in model_rec.alternatives[:2]:
            print(f"   • {alt['model']}: ${alt['estimated_cost']:.4f}, {alt['note']}")
```

### Hook into Task Completion

Log outcomes when tasks complete:

```python
# In task completion handler (wherever tasks finish)

from datetime import datetime
from intelligence.model_selection.models import ModelOutcomeEntry
from intelligence.storage import get_storage

def on_task_complete(task_id, task_type, description, model_used, outcome_data):
    """Called when a task completes."""

    entry = ModelOutcomeEntry(
        timestamp=datetime.now().isoformat(),
        task_id=task_id,
        task_type=task_type,
        task_description=description[:200],
        model_used=model_used,
        model_recommended_by="rules",  # Will be "learned" in Week 2
        complexity_classified=outcome_data.get("complexity", "moderate"),
        confidence=outcome_data.get("confidence", 0.6),
        outcome=outcome_data.get("outcome", "success"),
        tokens_used=outcome_data.get("tokens", 0),
        time_seconds=outcome_data.get("time", 0),
        error_count=outcome_data.get("corrections", 0),
        estimated_cost_usd=outcome_data.get("cost", 0.0),
        project_name=outcome_data.get("project", ""),
        files_touched=outcome_data.get("files", [])
    )

    storage = get_storage()
    storage.log_model_outcome(entry)
```

## File Structure

```
cortex/
├── intelligence/
│   ├── model_selection/
│   │   ├── __init__.py                 # Package exports
│   │   ├── models.py                   # Data structures
│   │   ├── classifier.py               # TaskComplexityClassifier
│   │   ├── rules.py                    # RuleBasedRecommender
│   │   ├── recommender.py              # ContextAwareModelRecommender
│   │   └── INTEGRATION_GUIDE.md        # This file
│   │
│   └── storage/
│       ├── __init__.py                 # Storage interface
│       └── jsonl_storage.py            # JSONL implementation
│
└── tests/
    └── test_model_selection.py         # Tests
```

## Storage Files

Data is stored in `~/.cortex/`:

```
~/.cortex/
├── model_outcomes.jsonl          # Model performance data
├── workflow_outcomes.jsonl        # Workflow-level outcomes (Week 2)
└── session_outcomes.jsonl         # Session-level outcomes (Week 2)
```

## Next Steps (Week 2)

Week 1 provides the foundation. Week 2 will add:

1. **ModelPerformanceLearner** - Learn from historical outcomes
2. **Hybrid Recommender** - Switch between learned and rules based on confidence
3. **Multi-Objective Allocator** - Resource optimization
4. **Session Planner** - Full orchestration

## Troubleshooting

### Import Errors

If you get import errors:

```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Should include /Users/jesse.kemp/Dev/cortex
export PYTHONPATH="/Users/jesse.kemp/Dev/cortex:$PYTHONPATH"
```

### Storage Errors

If storage fails:

```bash
# Check directory exists and is writable
ls -la ~/.cortex/

# Create if needed
mkdir -p ~/.cortex/
chmod 755 ~/.cortex/
```

### Test Failures

If tests fail:

```bash
# Run with verbose output
pytest tests/test_model_selection.py -vv

# Run specific test
pytest tests/test_model_selection.py::TestContextAwareRecommender::test_low_budget_forces_haiku -v
```

## API Reference

### ContextAwareModelRecommender

```python
class ContextAwareModelRecommender:
    def recommend(
        self,
        task_description: str,
        task_type: str,
        context: OrchestrationContext
    ) -> ModelRecommendation
```

### TaskComplexityClassifier

```python
class TaskComplexityClassifier:
    def classify(
        self,
        task_description: str,
        context: Dict[str, Any]
    ) -> Tuple[str, float]  # (complexity, confidence)
```

### OutcomeStorage

```python
class OutcomeStorage(ABC):
    def log_model_outcome(self, entry: ModelOutcomeEntry) -> None
    def load_model_outcomes(self, days: int = 30, task_type: Optional[str] = None) -> List[ModelOutcomeEntry]
```

## Configuration

Currently, no configuration needed. Week 2 will add:

- `CORTEX_MODEL_SELECTION_ENABLED` - Enable/disable (default: false)
- `CORTEX_MODEL_OPTIMIZE_FOR` - "cost_efficiency" | "accuracy" | "speed"
- `CORTEX_STORAGE_BACKEND` - "jsonl" | "sqlite" (future)

## Support

Questions or issues:
- Check `/Users/jesse.kemp/Dev/cortex/docs/MODEL_SELECTION.md` for full design
- Run tests to verify installation
- Check storage files in `~/.cortex/` for data

---

**Week 1 Status:** ✅ Complete and ready for integration
**Next:** Week 2 - Learning pipeline and resource allocation
