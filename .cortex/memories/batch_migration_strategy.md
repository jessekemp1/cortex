# Batch API Migration Strategy
## Reducing API Burn Rate from 1891% to Sustainable Levels

**Current State:** 162.1h/day vs 8.6h target (1891% over budget)
**Target:** 40% of work via batch API (50% cost savings)
**Status:** 0% batch utilization currently

---

## 📊 Root Cause Analysis

### Current Real-Time API Usage Breakdown

Based on work items and briefing data:

1. **Research & Investigation** (35-40% of usage)
   - Code exploration ("Where is X handled?")
   - Pattern matching across projects
   - Documentation review
   - Architecture understanding

2. **Code Review & Analysis** (25-30%)
   - PR reviews
   - Code quality checks
   - Test coverage analysis
   - Dependency audits

3. **Implementation** (20-25%)
   - Feature development (real-time needed)
   - Bug fixes (real-time needed)
   - Test writing

4. **Planning & Strategy** (10-15%)
   - Goal synthesis
   - Task breakdown
   - Decision support

### Why Burn Rate is High

- **VortexV2 sprint**: 123 commits/week = intensive real-time interaction
- **Multi-project context**: 10 active projects = constant context switching
- **Exploratory work**: Using Explore agents heavily (high token usage)
- **Unplanned work**: 4 items recently = reactive mode vs planned batching

---

## 🎯 Migration Strategy: 3-Phase Approach

### Phase 1: Low-Hanging Fruit (Week 1) - Target 15% batch usage

**What to Batch:**

✅ **Code Reviews** - Submit PRs for overnight review
```bash
# Instead of: /review (real-time)
cortex batch add "Review PR #4 for code quality, test coverage, security" \
  --priority normal --deadline 24h
```

✅ **Documentation Synthesis** - Generate docs overnight
```bash
cortex batch add "Generate API docs for VortexV2 multi-field endpoints" \
  --priority low --deadline 48h
```

✅ **Test Coverage Analysis** - Expensive, non-urgent
```bash
cortex batch add "Analyze test coverage gaps in alpha_arena" \
  --priority normal --deadline 24h
```

**Implementation:**
- Add batch prompts to `.claude/commands/review.md`, `docs.md`
- Update workflow: PR merge → trigger batch review (not real-time)
- Schedule overnight: 10pm-6am batch window

**Expected Savings:** ~50-80h/week → 15-20% burn rate reduction

---

### Phase 2: Pattern Detection (Week 2-3) - Target 30% batch usage

**What to Batch:**

✅ **Cross-Project Intelligence** - Cortex pattern matching
```bash
# Currently: runs in briefing (real-time, expensive)
# Instead: schedule nightly batch
cortex batch add "Scan all 10 active projects for anti-patterns" \
  --priority normal --deadline 12h --schedule cron
```

✅ **Dependency Audits** - Security scans
```bash
cortex batch add "Check all projects for vulnerable dependencies" \
  --priority high --deadline 24h
```

✅ **Code Quality Scans** - Linting, type checking
```bash
cortex batch add "Run ruff + mypy on VortexV2, alpha_arena, cortex" \
  --priority normal --deadline 48h
```

**Implementation:**
- Add to `cortex/runtime/agents/scheduled/`
  - `nightly_pattern_scan.py`
  - `weekly_dependency_audit.py`
- Use `/briefing` trigger to auto-submit batches
- Results cached → next day briefing includes them

**Expected Savings:** Additional 60-100h/week → 30-35% batch usage

---

### Phase 3: Strategic Work (Week 4+) - Target 40%+ batch usage

**What to Batch:**

✅ **Planning & Research** - Not time-sensitive
```bash
# Example: "Should we use Redis or in-memory cache?"
cortex batch add "Research caching options for VortexV2 forecast data" \
  --files Vortex/VortexV2/app/api.py \
  --priority low --deadline 72h
```

✅ **Refactoring Analysis** - Expensive, non-urgent
```bash
cortex batch add "Identify refactoring opportunities in alpha_arena/models/" \
  --priority low --deadline 96h
```

✅ **Test Generation** - Can run overnight
```bash
cortex batch add "Generate integration tests for VortexV2 wind field API" \
  --files Vortex/VortexV2/app/api.py \
  --priority normal --deadline 48h
```

**Implementation:**
- **Batch-first workflow**: `/plan` → auto-creates batch tasks
- **Scheduled research**: Weekly "strategic questions" batch
- **Overnight test generation**: After each feature merge

**Expected Savings:** Additional 40-60h/week → 40-45% batch usage

---

## 🔧 Technical Implementation

### 1. Enhanced Batch Scheduler

**Current Gap:** No automatic batch submission from workflows

**Solution:** Add workflow hooks
```python
# cortex/batch/workflow_hooks.py
class WorkflowBatchHooks:
    @staticmethod
    def on_pr_created(pr_url: str):
        """Auto-batch code review when PR created"""
        batch_cli.add_task(
            title=f"Review {pr_url}",
            prompt=f"Review PR for quality, tests, security: {pr_url}",
            priority="normal",
            deadline_hours=24
        )

    @staticmethod
    def on_feature_complete(project: str, files: List[str]):
        """Auto-batch documentation generation"""
        batch_cli.add_task(
            title=f"Generate docs for {project}",
            prompt=f"Document new features in: {', '.join(files)}",
            priority="low",
            deadline_hours=48
        )
```

### 2. Skill Integration

**Update Skills:** Add `--batch` flag to research/review skills
```bash
# .claude/commands/review.md
/review [--batch]  # If --batch, queues for overnight instead of real-time
```

### 3. Batch Result Integration

**Morning Briefing Enhancement:**
```python
# briefing.py - add section
def get_overnight_batch_results():
    """Show completed batch jobs in morning briefing"""
    results = batch_cli.get_completed_since(hours=12)
    return format_batch_results(results)  # "✅ Reviewed PR #4: 3 issues found"
```

### 4. Intelligent Batching

**Decision Tree:**
```
Is task time-sensitive? (< 2h deadline)
├─ YES → Real-time
└─ NO → Is it exploratory/research?
    ├─ YES → Batch (overnight)
    └─ NO → Is it > 20k tokens?
        ├─ YES → Batch (chunked)
        └─ NO → User preference
```

---

## 📋 Quick Win Actions (Next 24h)

1. **Add batch wrapper to existing skills**
   ```bash
   cd /Users/jesse.kemp/Dev/cortex
   # Create batch-submit.md skill
   # Modify /review to auto-batch non-urgent PRs
   ```

2. **Schedule nightly pattern scan**
   ```bash
   python cli.py batch add \
     "Scan 10 active projects for anti-patterns, circular imports, security issues" \
     --priority normal --deadline 12h
   ```

3. **Update `/briefing` to trigger batch submission**
   ```python
   # In briefing.py, after generating briefing:
   submit_pending_batches()  # Auto-submit ready tasks
   ```

4. **Add batch metrics to status**
   ```python
   # cli.py status command - add:
   print(f"Batch utilization: {batch_pct}% (target: 40%)")
   ```

---

## 🎯 Success Metrics

| Metric | Current | Week 1 | Week 2 | Week 4 |
|--------|---------|--------|--------|--------|
| **Batch %** | 0% | 15% | 30% | 40% |
| **Daily burn** | 162h | 137h | 113h | 97h |
| **Weekly budget** | 1135h/60h | 959h/60h | 791h/60h | 679h/60h |
| **Overage** | 1891% | 1598% | 1318% | 1131% |

**Still over?** Yes, but 40% batch usage = **$456 saved/week** at 50% discount

---

## 🚧 Blockers to Address

1. **No batch skill exists** → Create `.claude/commands/batch-submit.md`
2. **Manual batch submission** → Add cron job to auto-submit at 10pm
3. **No batch result notifications** → Add to morning briefing
4. **No workflow integration** → Add PR/commit hooks

---

## 💡 Long-Term Optimizations

1. **Predictive Batching**: Cortex learns what you typically research → auto-batches overnight
2. **Batch Queuing**: "I'll need to research X tomorrow" → queue for tonight
3. **Smart Chunking**: Large codebases split into parallel batch jobs
4. **Result Caching**: Batch results cached → instant retrieval next day

---

**Next Actions:**
1. Implement Phase 1 batch wrappers (2h effort)
2. Add batch metrics to status command (30min)
3. Schedule first overnight batch scan (10min)
4. Monitor for 1 week → adjust

**Estimated ROI:**
- Time investment: 3-4 hours
- Savings: $456/week = $23,712/year
- Payback: < 1 week
