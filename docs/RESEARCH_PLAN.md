# Cortex V1 Research Plan: Maximizing Current Value

*Strategy for Getting the Most from Cortex V1*

**Version:** 1.0.0
**Date:** January 2026

---

## Executive Summary

Cortex V1 is feature-complete with significant untapped potential. Before building V2 capabilities, we should maximize the value of the current system. This document outlines a research plan focused on three areas:

1. **Deepening Usage**: Getting more value from existing features
2. **Quick Wins**: Low-effort improvements with high impact
3. **Foundation Building**: Preparing for V2 while improving V1

Estimated impact: 2-3x increase in recommendation accuracy and developer productivity without major architectural changes.

---

## 1. Current Capabilities Assessment

### 1.1 What V1 Can Do

| Capability | Status | Usage Level | Optimization Potential |
|------------|--------|-------------|------------------------|
| Daily briefings | Complete | Medium | High (underutilized) |
| Recommendations | Complete | High | Medium |
| Outcome tracking | Complete | Low | High |
| Learning system | Complete | Low | Very High |
| Work absorber | Complete | Low | High |
| Batch processing | Complete | Low | Medium |
| Git tracking | Complete | Medium | Medium |
| Spec validation | Complete | Low | Medium |
| MCP integration | Complete | Low | High |

### 1.2 Value Leakage Points

Where value is being lost:

**1. Outcome Tracking Underuse**
- Only ~30% of recommendations have logged outcomes
- Learning system starved of data
- Confidence calibration incomplete

**2. Briefing Consumption**
- Briefings generated but not consistently reviewed
- Priority actions ignored in favor of reactive work
- Pattern insights not acted upon

**3. Work Absorber Dormancy**
- Run infrequently (weekly vs. daily)
- Drift detected but not resolved
- Correlations not verified

**4. MCP Integration Unused**
- MCP server exists but not configured
- Cursor/Claude Code not connected
- Context sharing disabled

### 1.3 Hidden Capabilities

Features that exist but are rarely used:

1. **Batch API** - 50% cost savings available
2. **Skill execution** - `cortex skill run` for automated tasks
3. **Process monitoring** - Resource optimization suggestions
4. **Spec generation** - `cortex draft` for new projects
5. **Golden Spec validation** - `cortex check` for alignment

---

## 2. Quick Win Opportunities

### 2.1 Immediate Actions (1-2 hours each)

**A. Enable MCP Integration**

```bash
# Add to Claude Code config
{
  "mcpServers": {
    "cortex": {
      "command": "python3",
      "args": ["/path/to/cortex/mcp_server.py"]
    }
  }
}
```

**Impact**: Context available in all Claude Code sessions without manual injection.

**B. Automate Outcome Tracking**

Add git hook to prompt for outcome after significant commits:

```bash
# .git/hooks/post-commit
if git log -1 --oneline | grep -q "feat\|fix\|refactor"; then
    echo "Was this successful? (y/n/p for partial)"
    read outcome
    case $outcome in
        y) cortex feedback --outcome success --notes "$(git log -1 --oneline)" ;;
        n) cortex feedback --outcome failed --notes "$(git log -1 --oneline)" ;;
        p) cortex feedback --outcome partial --notes "$(git log -1 --oneline)" ;;
    esac
fi
```

**Impact**: 3x increase in outcome data, faster learning system convergence.

**C. Schedule Daily Briefings**

```bash
cortex schedule "0 8 * * *"  # Daily at 8 AM
```

**Impact**: Consistent portfolio awareness, proactive vs. reactive work.

**D. Enable Batch Processing**

```bash
export CORTEX_BATCH_RESEARCH_ENABLED=true
```

**Impact**: 50% cost reduction on eligible queries.

### 2.2 Short-Term Improvements (1-2 days each)

**A. Integrate Work Absorber into Daily Routine**

Add to morning briefing:
```python
# In briefing.py
def generate_daily_briefing(...):
    # ... existing code ...

    # Add work absorption status
    absorber = WorkAbsorber()
    drift_summary = absorber.get_drift_summary()
    if drift_summary["total"] > 0:
        briefing.drift_warning = drift_summary
```

**B. Create Outcome Inference from Git**

```python
# New: outcome_inference.py
def infer_outcomes_from_git():
    """Infer recommendation outcomes from git history.

    Success indicators:
    - Feature merged to main
    - No reverts within 24 hours
    - Tests passing

    Failure indicators:
    - Reverts within 24 hours
    - Abandoned branch
    - Multiple fix commits
    """
```

**C. Add Recommendation Tracking Dashboard**

Simple weekly summary:
```
Last 7 Days:
- Recommendations shown: 15
- Followed: 12 (80%)
- Outcomes logged: 8
  - Success: 6
  - Partial: 1
  - Failed: 1
- Learning impact: Confidence adjustment +2%
```

### 2.3 Medium-Term Improvements (1-2 weeks)

**A. Implement Recommendation Persistence**

Track which recommendations have been shown:
```python
def get_recommendation(self, ...):
    rec = self._generate_recommendation(...)

    # Don't show same recommendation repeatedly
    if self._recently_shown(rec.id, hours=24):
        rec = self._get_alternative(rec)

    self._mark_shown(rec.id)
    return rec
```

**B. Add Context Quality Scoring**

Measure and improve context retrieval:
```python
def get_context(self, query: str):
    items = self._retrieve_items(query)

    # Score relevance
    for item in items:
        item["relevance_score"] = self._score_relevance(item, query)

    # Log for analysis
    self._log_retrieval(query, items)

    return sorted(items, key=lambda x: x["relevance_score"], reverse=True)
```

**C. Implement Learning Decay**

Older outcomes should have less influence:
```python
def get_confidence_adjustment(self, rec_type: str, project: str):
    outcomes = self._get_outcomes(rec_type, project)

    # Weight by recency (exponential decay)
    for outcome in outcomes:
        age_days = (now - outcome.timestamp).days
        outcome.weight = math.exp(-age_days / 30)  # 30-day half-life

    return self._calculate_adjustment(outcomes)
```

---

## 3. Deepening Usage

### 3.1 Establishing Routines

**Morning Routine (5 minutes)**
1. Run `cortex briefing`
2. Review priority actions
3. Check for blockers
4. Note any drift warnings

**End of Work Session (2 minutes)**
1. Run `cortex feedback --outcome <result>`
2. Quick note on what was accomplished
3. Run `cortex work absorb` if significant changes

**Weekly Review (15 minutes)**
1. Run `cortex learn` to review metrics
2. Check confidence calibration
3. Review outcome patterns
4. Run `cortex work report --days 7`

### 3.2 Integration Points

**Git Workflow**
```bash
# Pre-commit: Check for spec alignment
cortex check $(git rev-parse --show-toplevel)

# Post-commit: Trigger work absorption
cortex work absorb --project $(basename $(git rev-parse --show-toplevel))
```

**IDE Integration**
- MCP server for Claude Code/Cursor
- Briefing on session start
- Context injection for new files

**Calendar Integration**
- Sync priority actions to calendar
- Block time for high-priority work
- Meeting-free focus time suggestions

### 3.3 Feedback Loop Optimization

**Minimize Friction**
- `cortex done` alias for successful outcome
- `cortex fail` alias for failed outcome
- Keyboard shortcuts in terminal

**Maximize Signal**
- Structured notes template
- Automatic context capture
- Time tracking integration

---

## 4. Foundation Building for V2

### 4.1 Data Collection for V2

**Memory Usage Patterns**
```python
# Track what's accessed
def get_context(self, query: str):
    self._log_access(
        query=query,
        results=items,
        timestamp=now,
        session_id=current_session
    )
```

**Recommendation Effectiveness by Type**
```python
# Detailed outcome tracking
outcome_record = {
    "recommendation_id": rec.id,
    "type": rec.type,
    "confidence": rec.confidence,
    "context_used": rec.context_ids,  # What context influenced this
    "outcome": outcome,
    "time_to_outcome": completion_time - recommendation_time,
    "follow_up_needed": bool
}
```

**Context Relevance Scoring**
```python
# For future A-MEM implementation
def _score_relevance(self, item, query):
    score = {
        "semantic_similarity": self._semantic_score(item, query),
        "recency": self._recency_score(item),
        "usage_frequency": self._usage_score(item),
        "outcome_correlation": self._outcome_score(item)  # New
    }
    return weighted_average(score)
```

### 4.2 API Stability

Ensure V1 APIs remain stable for V2:

```python
# Version the Bridge API
class CortexBridge:
    VERSION = "1.0.0"

    def get_recommendation(self, **kwargs):
        """V1 API - stable contract.

        Returns:
            Recommendation with guaranteed fields:
            - id, type, priority, title, description
            - rationale, confidence
            - related_projects, related_goals
        """
```

### 4.3 Migration Preparation

**Memory Format Evolution**
```python
# Add version to stored data
outcomes_data = {
    "version": "1.0.0",
    "outcomes": [...],
    "metadata": {
        "migrated_from": None,
        "migration_date": None
    }
}
```

**Schema Forward Compatibility**
```python
# Unknown fields preserved, not rejected
def load_outcomes(self):
    data = json.load(self.path)
    self.version = data.get("version", "0.0.0")
    self.outcomes = [Outcome(**o) for o in data["outcomes"]]
    self._extra = {k: v for k, v in data.items()
                   if k not in ["version", "outcomes"]}
```

---

## 5. Metrics and Success Criteria

### 5.1 Key Metrics to Track

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Outcome logging rate | 30% | 80% | Logged / Shown |
| Recommendation accuracy | 85% | 90% | Success / Followed |
| Daily briefing usage | 3x/week | 5x/week | Sessions started with briefing |
| Learning system data | 127 outcomes | 500+ | Total outcomes logged |
| Confidence calibration error | 8% | 5% | Predicted - Actual success |
| Batch API usage | 0% | 50% | Batch / Total eligible queries |

### 5.2 Monthly Review Checklist

1. **Usage Review**
   - [ ] Check outcome logging rate
   - [ ] Review recommendation follow-through
   - [ ] Verify batch API savings

2. **Learning Review**
   - [ ] Check confidence calibration
   - [ ] Review pattern emergence
   - [ ] Identify systematic errors

3. **System Health**
   - [ ] Check memory file sizes
   - [ ] Verify MCP server uptime
   - [ ] Review error logs

4. **Improvement Identification**
   - [ ] Note friction points
   - [ ] Capture feature requests
   - [ ] Document workflow gaps

---

## 6. Research Experiments

### 6.1 Context Retrieval Optimization

**Experiment**: Compare retrieval strategies

**Setup**:
1. Log current retrieval patterns
2. Implement alternative strategies:
   - Semantic only
   - Semantic + recency
   - Semantic + outcome correlation
3. A/B test with outcome tracking

**Success Metric**: Recommendations using better context have higher success rates

### 6.2 Proactive Recommendations

**Experiment**: Test proactive vs. reactive recommendations

**Setup**:
1. Baseline: Recommendations shown on request
2. Treatment: Recommendations pushed at session start
3. Track outcomes for both groups

**Success Metric**: Higher follow-through for proactive recommendations

### 6.3 Confidence Calibration Techniques

**Experiment**: Compare calibration methods

**Setup**:
1. Current: Linear adjustment based on history
2. Alternative: Isotonic regression calibration
3. Alternative: Platt scaling
4. Compare calibration error

**Success Metric**: Lower calibration error (predicted matches actual)

### 6.4 Outcome Inference Accuracy

**Experiment**: Validate git-based outcome inference

**Setup**:
1. Infer outcomes from git patterns
2. Compare to explicit user feedback
3. Measure agreement rate

**Success Metric**: >80% agreement between inferred and explicit outcomes

---

## 7. Implementation Priority

### Immediate (This Week)

1. [ ] Enable MCP integration
2. [ ] Set up daily briefing schedule
3. [ ] Add outcome logging aliases
4. [ ] Enable batch processing

### Short-Term (This Month)

5. [ ] Implement git-based outcome inference
6. [ ] Add recommendation tracking dashboard
7. [ ] Integrate work absorber into briefing
8. [ ] Create weekly review routine

### Medium-Term (This Quarter)

9. [ ] Implement recommendation persistence
10. [ ] Add context quality scoring
11. [ ] Deploy learning decay
12. [ ] Run retrieval optimization experiments

### Ongoing

- Maintain 80%+ outcome logging rate
- Review metrics monthly
- Document learnings for V2

---

## 8. Conclusion

Cortex V1 has more capability than is currently being utilized. Before building V2 features, we should:

1. **Use what exists**: MCP, batch API, work absorber are underutilized
2. **Close the loop**: Outcome tracking is the key to learning
3. **Build habits**: Daily briefings and regular reviews
4. **Collect data**: Everything logged helps V2

The path to V2 runs through V1 mastery. Every outcome logged, every pattern detected, every recommendation followed feeds the learning system that will power V2's advanced capabilities.

Focus: Not new features, but deep usage of existing ones.

---

*This research plan should be reviewed monthly and updated based on learnings.*
