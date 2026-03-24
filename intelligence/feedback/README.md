# Implicit Feedback Collection

Automatic tracking of user interactions with recommendations to enable learning from implicit signals.

## Overview

The Implicit Feedback Collector tracks user behavior to detect:
- **Follows**: User executes recommended action
- **Ignores**: User sees recommendation but doesn't act
- **Overrides**: User modifies recommendation before executing
- **Time-to-action**: How long from seeing to executing

This provides **10-100x more feedback signals** than explicit feedback alone.

## Quick Start

```python
from intelligence.feedback import ImplicitFeedbackCollector

# Initialize collector
collector = ImplicitFeedbackCollector()

# 1. Track when recommendation is shown
recommendation = {
    "id": "rec_001",
    "title": "Fix failing tests",
    "files": ["tests/test_data.py"],
}
collector.track_recommendation_shown("rec_001", recommendation)

# 2. Track when user takes action
collector.track_action_taken(
    action="Fix failing tests in test_data.py",
    files=["tests/test_data.py"]
)

# 3. End session to mark ignores
collector.session_end()

# 4. View statistics
stats = collector.get_stats(days=7)
print(f"Follow rate: {stats['follow_rate']:.1%}")
```

## Architecture

### Signal Types

| Signal Type | Trigger | Similarity Range |
|------------|---------|------------------|
| **Followed** | Action matches recommendation closely | > 0.7 |
| **Overridden** | Action similar but modified | 0.3 - 0.7 |
| **Ignored** | No matching action before session end | 0.0 |

### Matching Algorithm

The collector uses a **hybrid matching algorithm**:

1. **Text Similarity** (60% weight)
   - Uses SequenceMatcher to compare action text with recommendation title/description
   - Case-insensitive comparison

2. **File Overlap** (40% weight)
   - Compares file basenames (not full paths)
   - Jaccard similarity (intersection / union)

3. **Combined Score**
   - Weighted average of text and file similarity
   - Falls back to text-only if no files involved

### Storage

Signals are stored in **JSONL format** at `~/.cortex/implicit_feedback.jsonl`:

```json
{"timestamp": "2026-02-01T15:30:45", "recommendation_id": "rec_001", "signal_type": "followed", "similarity": 0.85, "time_to_action": 12.5, "context": {}}
{"timestamp": "2026-02-01T15:45:00", "recommendation_id": "rec_002", "signal_type": "ignored", "similarity": 0.0, "context": {}}
```

## Integration Points

### 1. Briefing (Showing Recommendations)

```python
# In briefing.py
from intelligence.feedback import ImplicitFeedbackCollector

collector = ImplicitFeedbackCollector()

# Track each recommendation shown
for rec in recommendations:
    collector.track_recommendation_shown(
        rec_id=rec.id,
        recommendation={
            "title": rec.title,
            "description": rec.description,
            "files": rec.files,
            "priority": rec.priority,
        },
        context={"source": "briefing", "project": project_name}
    )
```

### 2. Bridge (Tracking Actions)

```python
# In bridge.py
def trigger_action(self, action: str, files: List[str]):
    """Execute action and track for implicit feedback."""

    # Track action
    if hasattr(self, 'implicit_collector'):
        self.implicit_collector.track_action_taken(
            action=action,
            files=files,
            context={"agent": "bridge", "timestamp": datetime.now()}
        )

    # Execute action
    result = execute(action, files)
    return result
```

### 3. Session Manager (Session Lifecycle)

```python
# In session_manager.py
class SessionManager:
    def __init__(self):
        self.implicit_collector = ImplicitFeedbackCollector()

    def end_session(self):
        """End session and mark ignored recommendations."""
        self.implicit_collector.session_end()

        # Show session stats
        stats = self.implicit_collector.get_session_stats()
        print(f"Session complete: {stats['followed']}/{stats['total_shown']} followed")
```

## API Reference

### ImplicitFeedbackCollector

#### Methods

**`track_recommendation_shown(rec_id, recommendation, context=None)`**
- Tracks when a recommendation is displayed to user
- Args:
  - `rec_id` (str): Unique recommendation identifier
  - `recommendation` (dict): Recommendation with title, description, files, etc.
  - `context` (dict, optional): Additional context (project, goal, etc.)

**`track_action_taken(action, files=None, context=None)`**
- Tracks user actions and correlates with pending recommendations
- Args:
  - `action` (str): Description of action taken
  - `files` (list, optional): Files involved in the action
  - `context` (dict, optional): Additional context

**`session_end()`**
- Marks un-acted recommendations as ignored
- Clears session state
- Call at end of session or after timeout

**`get_session_stats()`**
- Returns: Dict with total_shown, followed, pending, actions_taken

**`load_signals(limit=None)`**
- Loads stored signals from disk
- Args:
  - `limit` (int, optional): Maximum signals to load (most recent)
- Returns: List of ImplicitSignal objects

**`get_stats(days=7)`**
- Returns statistics for time period
- Args:
  - `days` (int): Number of days to analyze
- Returns: Dict with total_signals, follows, ignores, overrides, avg_time_to_action, follow_rate

### ImplicitSignal

**Dataclass fields:**
- `timestamp` (str): ISO format timestamp
- `recommendation_id` (str): Recommendation identifier
- `signal_type` (str): "followed", "ignored", or "overridden"
- `similarity` (float): Match similarity 0-1
- `time_to_action` (float, optional): Seconds from shown to acted
- `alternative_taken` (str, optional): What user did instead (for overrides)
- `context` (dict): Additional context

## Statistics & Metrics

### Success Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Signals/day** | 50+ | Total implicit signals collected daily |
| **Follow detection accuracy** | >80% | % of true follows correctly detected |
| **Override detection accuracy** | >70% | % of true overrides correctly detected |

### Analysis Examples

**Follow rate over time:**
```python
stats = collector.get_stats(days=30)
print(f"Follow rate (30 days): {stats['follow_rate']:.1%}")
```

**Average time to action:**
```python
stats = collector.get_stats(days=7)
print(f"Avg time to action: {stats['avg_time_to_action']:.1f}s")
```

**Signal breakdown:**
```python
signals = collector.load_signals(limit=100)
follows = [s for s in signals if s.signal_type == "followed"]
ignores = [s for s in signals if s.signal_type == "ignored"]
overrides = [s for s in signals if s.signal_type == "overridden"]

print(f"Follows: {len(follows)}")
print(f"Ignores: {len(ignores)}")
print(f"Overrides: {len(overrides)}")
```

## Testing

Run the test suite:

```bash
pytest tests/test_implicit_feedback.py -v
```

**Test coverage:** 28 tests covering:
- Recommendation tracking
- Action correlation (follow/ignore/override detection)
- Session management
- Signal persistence (JSONL storage)
- Statistics calculation
- Text similarity & file overlap
- Edge cases & error handling

Run the demo:

```bash
python demo_implicit_feedback.py
```

## Design Decisions

### 1. Similarity Thresholds

| Threshold | Rationale |
|-----------|-----------|
| > 0.7 = Follow | High similarity indicates user followed recommendation closely |
| 0.3 - 0.7 = Override | Medium similarity suggests similar intent, different execution |
| < 0.3 = Ignore | Low similarity means action unrelated to recommendation |

These thresholds were chosen based on testing with sample data. They can be tuned based on production feedback.

### 2. Text Similarity Algorithm

**Choice:** SequenceMatcher (Python's difflib)

**Alternatives considered:**
- Levenshtein distance: More complex, similar results
- Embedding similarity: Requires embeddings client, adds latency
- Keyword matching: Too simple, misses semantic similarity

**Rationale:** SequenceMatcher provides good balance of accuracy and performance for short text comparison.

### 3. File Matching Strategy

**Choice:** Compare basenames only (not full paths)

**Rationale:**
- Recommendations may use relative paths, actions use absolute paths
- Same file might be referenced different ways
- Basename matching provides flexibility while remaining accurate

### 4. Storage Format

**Choice:** JSONL (JSON Lines)

**Rationale:**
- Append-only writes (efficient for streaming data)
- Human-readable for debugging
- Easy to process line-by-line
- Standard format with good tool support (jq, grep, etc.)

### 5. Session Lifecycle

**Choice:** Explicit `session_end()` call

**Alternatives considered:**
- Auto-timeout: Complex, requires background thread
- Per-recommendation timeout: Harder to implement
- No session concept: Can't distinguish ignores from pending

**Rationale:** Explicit session management is simple and gives integration points full control.

## Future Enhancements

### Phase 1 Improvements (Current)
- ✅ Basic follow/ignore/override detection
- ✅ Text and file similarity matching
- ✅ JSONL storage and statistics

### Phase 2 (Planned)
- [ ] Semantic similarity using embeddings (for better matching)
- [ ] Learning from signal patterns (adjust similarity thresholds)
- [ ] Integration with AI-as-a-Judge (quality scoring)
- [ ] Recommendation quality feedback loop

### Phase 3 (Future)
- [ ] Auto-timeout for session management
- [ ] Per-recommendation decay (stale recommendations auto-ignored)
- [ ] Dashboard for signal visualization
- [ ] A/B testing based on follow rates

## Related Improvements

- **Improvement 2**: AI-as-a-Judge Evaluation
  - Uses implicit signals to calibrate quality scores
  - Validates recommendation quality over time

- **Improvement 4**: Prompt Versioning
  - A/B tests can use follow rate as success metric
  - Different prompts may lead to different follow rates

- **Improvement 7**: Data Quality Framework
  - Implicit signals contribute to quality assessment
  - High follow rate indicates high-quality recommendations

## References

- PRD: `docs/AI_ENGINEERING_IMPROVEMENTS_PRD.md` (Improvement 3)
- Book: "AI Engineering" Chapter 8, pp. 220-235 (Implicit Feedback)
- Implementation: `intelligence/feedback/implicit_collector.py`
- Tests: `tests/test_implicit_feedback.py`
