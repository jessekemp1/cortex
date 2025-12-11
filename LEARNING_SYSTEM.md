# Cortex Learning System

The Cortex learning system enables the strategic orchestrator to learn from recommendation outcomes over time, continuously improving its recommendations.

## Overview

The learning system tracks:
- **Recommendation outcomes** - Success, partial success, or failure
- **Recommendation accuracy** - What percentage of followed recommendations succeed
- **Outcome patterns** - Which types of recommendations work best
- **Confidence calibration** - Are high-confidence recommendations more successful?

## Components

### 1. Enhanced Feedback Tracking (`feedback.py`)

**New Features:**
- `OutcomeEntry` dataclass for structured outcome tracking
- `log_outcome()` method for logging detailed outcomes
- `load_outcomes()` method for retrieving all outcomes
- Storage in `~/.cortex/outcomes.jsonl` (JSONL format for easy append)

**Outcome Fields:**
```python
{
    "timestamp": "2025-12-09T00:00:00",
    "recommendation_id": "rec_123",
    "recommendation_title": "Fix blocker",
    "recommendation_type": "blocker_resolution",
    "priority": "A",
    "confidence": 0.85,
    "followed": true,
    "outcome": "success",  # success|partial|failed|unknown
    "notes": "Blocker resolved quickly",
    "context": {"project": "VortexV2", "goal": "Deploy v1.0"}
}
```

### 2. Learning Metrics (`learning.py`)

**Core Functions:**

- `calculate_recommendation_accuracy()` - % of followed recommendations that succeeded
  - Success = 1.0, Partial = 0.5, Failed = 0.0

- `get_outcome_patterns()` - Success rates by recommendation type
  - Shows which types of recommendations work best
  - Includes total count, followed count, success rate, avg confidence

- `get_confidence_calibration()` - Success rates by confidence bucket
  - High (0.8-1.0), Medium (0.5-0.8), Low (0.0-0.5)
  - Validates if confidence scores are accurate predictors

- `adjust_confidence_based_on_history()` - Adjust confidence using historical data
  - Blends base confidence with historical success rate
  - Weight increases with more data (up to 40% historical, 60% base)
  - Requires minimum 3 outcomes to adjust

**LearningMetrics Dataclass:**
```python
@dataclass
class LearningMetrics:
    total_outcomes: int
    followed_count: int
    success_rate: float
    partial_rate: float
    failed_rate: float
    recommendation_accuracy: float
    confidence_calibration: Dict[str, float]
    outcome_patterns: Dict[str, Dict[str, Any]]
```

### 3. Orchestrator Integration (`orchestrator.py`)

The learning system is integrated into the recommendation flow:

1. Recommendations are generated normally
2. For each recommendation, confidence is adjusted based on historical outcomes
3. Rationale is enhanced with learning insight (e.g., "Based on 10 previous outcomes (80% success rate)")
4. Adjusted recommendations are returned to user

**Example:**
```python
# Original recommendation
confidence = 0.7
type = "blocker_resolution"

# After learning adjustment
# If blocker_resolution has 85% historical success rate
# Adjusted = 0.7 * 0.75 + 0.85 * 0.25 = 0.525 + 0.2125 = 0.7375
confidence = 0.74
rationale += " (Based on 10 previous outcomes (85% success rate))"
```

### 4. CLI Command (`cortex learn`)

Display comprehensive learning metrics and patterns.

**Usage:**
```bash
cortex learn
```

**Output:**
- Overall metrics (total outcomes, success rate, accuracy)
- Confidence calibration (visual bars showing success by confidence level)
- Outcome patterns by type (sorted by success rate)

## Workflow

### 1. Get Recommendation
```bash
cortex next
```

### 2. Follow Recommendation
Execute the recommended action.

### 3. Log Outcome
```python
from feedback import FeedbackLogger

logger = FeedbackLogger()
logger.log_outcome(
    recommendation_id="rec_123",
    recommendation_title="Fix blocker in VortexV2",
    recommendation_type="blocker_resolution",
    priority="A",
    confidence=0.85,
    followed=True,
    outcome="success",  # or "partial" or "failed"
    notes="Blocker resolved by updating dependencies",
    context={"project": "VortexV2"}
)
```

### 4. View Learning Metrics
```bash
cortex learn
```

## Data Storage

- **Feedback Log**: `~/.cortex/feedback.json` (backward compatible)
- **Outcomes Log**: `~/.cortex/outcomes.jsonl` (JSONL for easy append)

**Why JSONL?**
- Easy to append (no need to read entire file)
- Each line is a valid JSON object
- Efficient for streaming/incremental processing
- Human-readable and greppable

## Testing

Comprehensive tests in `/Users/jesse.kemp/Dev/cortex/tests/test_learning.py`:

- `test_empty_outcomes` - No data case
- `test_recommendation_accuracy` - Accuracy calculation
- `test_outcome_patterns` - Pattern analysis by type
- `test_confidence_calibration` - Calibration by bucket
- `test_adjust_confidence_no_history` - No data adjustment
- `test_adjust_confidence_limited_data` - Limited data adjustment
- `test_adjust_confidence_with_history` - Full adjustment with sufficient data
- `test_get_learning_metrics_comprehensive` - Complete metrics

**Run tests:**
```bash
cd /Users/jesse.kemp/Dev/cortex
pytest tests/test_learning.py -v
```

## Example Workflow

See `/Users/jesse.kemp/Dev/cortex/example_learning_workflow.py` for a complete example demonstrating:
1. Getting recommendations
2. Logging outcomes
3. Viewing metrics
4. Observing confidence adjustments

**Run example:**
```bash
cd /Users/jesse.kemp/Dev/cortex
python example_learning_workflow.py
```

## Future Enhancements

Potential future improvements:
- ML-based confidence adjustment (beyond simple blending)
- Time-decay for old outcomes (recent data weighted more)
- Context-aware learning (learn per project, per goal type, etc.)
- A/B testing framework for recommendation strategies
- Anomaly detection (sudden drops in success rate)
- Recommendation explanation improvements (why this confidence?)

## Philosophy

The learning system follows Cortex's philosophy:
- **Simple but effective** - JSONL storage, simple blending algorithm
- **Transparent** - Clear metrics, visible adjustments
- **Incremental** - Start simple, improve over time
- **Data-driven** - Let outcomes guide improvements
- **Human-in-the-loop** - Users log outcomes, system learns

The goal is not to build complex ML, but to systematically track what works and adjust accordingly.
