# Cortex Lean Specification

**Version**: 1.0.0
**Date**: 2026-02-11
**Status**: MVP (Guardian #1 deployed)

---

## 1. Product Identity

**Cortex Lean** is a developer workflow guardian that learns your mistakes so you don't repeat them.

### What it is
- Local-first behavioral pattern detector for developer workflows
- Proactive intervention system that warns before costly mistakes
- Privacy-preserving learning that stays on your machine

### What it is NOT
- **NOT a memory tool** (crowded space with 10+ competitors: Mem0, claude-mem, Cursor, Windsurf, Letta, Augment, Cline)
- **NOT a code understanding engine** (outgunned by Augment, Cody, Cursor)
- **NOT a code completion tool** (saturated by Copilot, Tabnine, Windsurf)

### Unique Value Proposition
Cortex Lean closes the **Observe → Auto-detect pattern → Proactively intervene** loop automatically. No existing competitor does all three stages:
- Memory tools stop at observation and storage
- IntelliCode (killed by Microsoft Dec 2025) was the closest but never automated intervention
- thefuck is reactive, not predictive
- CLAUDE.md requires manual rule authoring

---

## 2. Competitive Positioning

### Market Validation
- **claude-mem**: 1,739 stars in 24 hours → demand for developer memory
- **Mem0**: $24M Series A → VCs backing memory infrastructure
- **IntelliCode autopsy**: Microsoft killed local pattern detection Dec 2025, leaving this space **vacant**
- **AWS Kiro**: Agent Hooks prove event-driven intervention is viable
- **Academic**: 23-min context recovery cost, $50K/dev/yr context-switching waste

### Differentiation Strategy
**We INTERVENE, others only remember.**

| Feature | Cortex Lean | Memory Tools | Code Intelligence |
|---------|------------|--------------|-------------------|
| Observe patterns | ✅ | ✅ | ✅ |
| Auto-detect anti-patterns | ✅ | ❌ | Partial |
| Proactive intervention | ✅ | ❌ | ❌ |
| Local-first privacy | ✅ | Varies | ❌ |
| Behavioral learning | ✅ | Context only | Syntax only |

### Key Risks
1. **Name collision**: Cortex.io is Gartner-recognized enterprise portal (may need rebranding)
2. **Commoditization**: Memory features shipping in all IDEs by Q2 2026
3. **IntelliCode mystery**: Was it market failure or strategic cannibalization? Needs research.

---

## 3. Trust UX Specification

Developer tools must earn trust through restraint. Cortex Lean's design principles:

### Noise Budget
- **Maximum 5 interventions per day per repo**
- Beyond this threshold, suppress all warnings until next day
- Telemetry tracks when budget is hit (signal for tuning)

### Escalation Ladder
Interventions follow a four-level hierarchy:

1. **Silent**: Pattern detected, logged for learning, no user notification
2. **Suggest**: Informational hint, easily dismissible
3. **Warn**: Visible warning with evidence, requires acknowledgment
4. **Block**: Prevents action, always bypassable with explicit override

**Blocks are rare** (reserved for data loss scenarios) and **always bypassable** (developer has final say).

### Suppression
- Per-file, per-day suppression
- Suppress a warning → won't repeat for that file until next session
- Suppression logged for pattern analysis (high suppression rate = bad rule)

### Bypass
- Every intervention includes "Proceed anyway" option
- Bypass logged with timestamp for outcome correlation
- High bypass rates (>20%) trigger rule review

### Evidence Requirements
Every warning must include:
- **Reason**: Why this pattern is risky
- **Last occurrence**: Timestamp of last time this pattern caused failure
- **Example**: Concrete instance from your history (if available)

### Fail-Open Guarantee
**Cortex failure never blocks work.**
- Hook crashes → log error, allow tool execution
- Database corruption → disable Cortex, notify user
- Network timeout (future cloud sync) → continue with local-only mode

---

## 4. MVP Definition: Guardian #1 (Edit-without-Read)

### Problem Statement
Data audit of 59,917 events across 34 days shows:
- **Edit failure rate**: 75.7% (2,600 failures / 3,433 attempts)
- **Blind edit rate**: 13% (434 / 3,341 edits had no prior Read)
- Blind edits are high-risk: `old_string` mismatch is the #1 failure mode

### Solution Design
**PreToolUse hook** warns before Edit executes if target file wasn't Read in this session.

**Implementation**: `edit_without_read_guard.py` (129 lines, already deployed)

#### Hooks
1. **SessionStart**: Clears `~/.cortex-lean/session_reads.jsonl`
2. **PostToolUse:Read**: Appends file path to session state
3. **PreToolUse:Edit**: Checks if file in session state
   - ✅ Present → silent pass, log `pass_read_verified`
   - ❌ Missing → warn, log `warn_blind_edit`

#### State Files
- **`~/.cortex-lean/session_reads.jsonl`**: One file path per line (read files this session)
- **`~/.cortex-lean/guardian_log.jsonl`**: Activation telemetry (timestamps, events, outcomes)

#### Warning Message
```
[Guardian] Editing file not Read this session: scheduler.py
   Consider reading it first to verify old_string matches actual content.
```

### Measurement Plan
**7-day observation window** (minimum):
- Baseline: 75.7% Edit failure rate
- Metric: Rolling 7-day Edit failure rate
- Success gate: **≥20% reduction** (i.e., failure rate drops to ≤60.6%)

### V1 Comparison
**rule_adherence_hook.py** (PostToolUse, 223 lines):
- Detects same pattern but **after** Edit executes (forensic, not preventive)
- Writes to `~/.cortex/rule_events.jsonl` (V1 data path)
- 4-hour TTL on session state vs. Lean's session-scoped state
- More complex (session state TTL, file-based persistence)

**Key difference**: V1 is reactive (logs violations), Lean is proactive (prevents violations).

---

## 5. Level Gates (Progressive Enhancement)

Cortex Lean unlocks capabilities through validated usage, not feature flags.

### Gate 1 → 2: Single Guardian Validation
**Requirement**: Edit-without-Read rate drops ≥20% for 7 consecutive days
**Unlocks**:
- Guardian #2 deployment (Bash failure streak detector)
- Pattern detection for multi-guardian correlation

### Gate 2 → 3: Multi-Guardian Stability
**Requirement**: 3+ guardians active with <20% bypass rate for 14 days
**Unlocks**:
- Context Graph activation (cross-guardian pattern linking)
- Automated rule suggestion (Cortex proposes new guardians from patterns)

### Gate 3 → 4: Graph Intelligence
**Requirement**: Context Graph has 100+ edges with retrieval relevance >70%
**Unlocks**:
- Predictive intervention (warn before pattern fully develops)
- Cross-project learning (anonymized pattern sharing)

### Rationale
**Prove value at each layer before adding complexity.** V1 failed by building all layers before validating any.

---

## 6. V1 Teardown Plan

### Current State (2026-02-11)
- V2 Prime Engines: 6,643 cycles run, **0 signals processed** (broken import at `interaction_capture.py:356`)
- ContextGraph: 11 nodes, 0 edges, dead since Jan 15
- Dead code: `engines/v2/`, `engines/v21/` (never imported outside own tests)
- **162K lines Python, 537 files → 85% dead weight**

### Teardown Phases

#### Phase 1: Parallel Operation (NOW - Gate 1)
- ✅ Lean guardian deployed alongside V1 hooks
- ✅ Both systems write telemetry (V1: `~/.cortex/`, Lean: `~/.cortex-lean/`)
- ✅ Existing 530 tests remain passing
- **No V1 deletion** (runs in shadow mode for comparison)

#### Phase 2: Archive Dead Code (After Gate 1)
- Archive `engines/v2/` and `engines/v21/` to `cortex/archive/`
- Fix broken import at `interaction_capture.py:356` (or delete if unused)
- Document why deleted: "Never imported, 0 signals processed in 6,643 cycles"

#### Phase 3: Consolidate to Lean (After Gate 2)
- Stop V1 flywheel/work-absorber daemons
- Migrate V1 telemetry to Lean schema (one-time data migration)
- Archive remaining V1 infrastructure to `cortex/archive/v1/`
- Update tests to use Lean-only paths

### Important: DO NOT DELETE, ARCHIVE
Previous v2/v21 rewrites prove that **deleting didn't help** — just created amnesia and rework. Archive preserves context for future retrospectives.

---

## 7. Privacy Specification

Cortex Lean is **local-first** by design. All data stays on your machine.

### Capture Schema
Events logged to `~/.cortex-lean/guardian_log.jsonl`:

```json
{
  "event_id": "uuid-v4",
  "schema_version": 1,
  "timestamp": "2026-02-11T14:32:01Z",
  "project": "/path/to/project",
  "tool": "Edit",
  "target_path": "/path/to/project/cortex/lean/SPEC.md",
  "status": "warn_blind_edit",
  "error_signature": null
}
```

### Data Boundaries

#### ALWAYS Capture
- Event metadata: timestamp, tool name, file path
- Status: pass / warn / block / bypass
- Error signatures: type + message (e.g., `"FileNotFoundError: old_string not found"`)
- Project path (for multi-repo correlation)

#### NEVER Capture
- **File contents** (even snippets)
- **stdout/stderr** (may contain secrets)
- **Environment variables** (credentials, tokens)
- **Command arguments** (may contain passwords)
- **IP addresses, hostnames** (privacy leakage)

### Retention Policy
- **Raw events**: 30 days (JSONL append-only)
- **Aggregated patterns**: Indefinite (counts, not content)
- **Migration**: Daily batch job (JSONL → SQLite aggregation)

### User Controls (Future CLI)
```bash
cortex show-data              # Display all captured data
cortex purge --before 2026-01-01  # Delete events before date
cortex purge --all            # Nuclear option (requires confirmation)
cortex export --anonymize     # Export patterns for sharing (strips paths)
```

### Storage Location
- **SQLite**: `~/.cortex-lean/cortex.db` (aggregated patterns)
- **JSONL**: `~/.cortex-lean/guardian_log.jsonl` (raw events)
- **Session state**: `~/.cortex-lean/session_reads.jsonl` (ephemeral)

All files are **user-readable** (JSONL text, SQLite schema documented).

---

## 8. Metrics

### Primary Metric: Edit Failure Rate
**Definition**: Percentage of Edit calls that fail (return error or empty result)
**Baseline**: 75.7% (2,600 failures / 3,433 attempts, 34-day audit)
**Target**: ≤60.6% (20% reduction)
**Measurement**: Rolling 7-day average

**Formula**:
```
Edit Failure Rate = (failed_edits / total_edits) * 100
where:
  failed_edits = count(status IN ('error', 'empty_result'))
  total_edits = count(tool_name = 'Edit')
```

### Secondary Metrics

#### Blind Edit Rate
**Definition**: Percentage of Edit calls with no prior Read
**Baseline**: 13% (434 / 3,341 edits)
**Target**: <5%
**Data source**: `guardian_log.jsonl` (events with `warn_blind_edit`)

#### Guardian Bypass Rate
**Definition**: Percentage of warnings that user proceeded through
**Threshold**: <20% (above this triggers rule review)
**Data source**: Future bypass tracking (not in MVP)

#### Intervention Acceptance Proxy
**Definition**: Percentage of warnings followed by successful Edit (vs. retry/abandon)
**Why proxy**: True acceptance requires UI feedback (not in MVP)
**Formula**:
```
Acceptance Proxy = warnings_followed_by_success / total_warnings
where:
  warnings_followed_by_success = count(
    warn_blind_edit at T
    AND pass_read_verified at T+1..T+60s
    AND edit_success at T+61..T+120s
  )
```

#### False Positive Rate
**Definition**: Guardian warnings that didn't prevent a failure
**Calculation**: Manually sampled (not automated in MVP)
**Example**: "File was edited successfully despite blind edit warning"

### Data Sources
- **V1 baseline**: `~/.cortex/rule_events.jsonl` (59,917 events, 34 days)
- **Lean telemetry**: `~/.cortex-lean/guardian_log.jsonl` (ongoing)
- **Edit outcomes**: Parse tool responses for `error` / `success` status

### Reporting Cadence
- **Daily**: Append to metrics log (not displayed)
- **Weekly**: Generate report comparing current vs. baseline
- **Gate evaluation**: After 7 consecutive days of improvement

---

## 9. Guardian #2 Candidates (Prioritized by Data Audit)

Data audit found **103 distinct actionable patterns**. Top candidates ranked by impact:

### 1. Bash Failure Streak Detector (HIGHEST PRIORITY)
**Frequency**: 967 occurrences in 34-day audit
**Pattern**: Same Bash command fails 3+ times in succession
**Intervention**: Suggest alternative approach or surface error pattern
**Example**:
```
[Guardian] This Bash command failed 3 times in a row:
  pytest Vortex/VortexV2/tests/test_scheduler.py

Last error: ModuleNotFoundError: No module named 'herbie'

Suggestion: Check virtual environment activation or install dependencies.
```

**Implementation complexity**: Low (30 lines)
**Expected impact**: High (reduces retry waste)

### 2. Edit Fail → Retry Detector
**Frequency**: 1,199 occurrences (35% of Edit failures)
**Pattern**: Edit fails, Claude retries with identical `old_string`
**Intervention**: Suggest Read to verify actual file state
**Example**:
```
[Guardian] This Edit failed and you're retrying with the same old_string.

Consider: Read the file first to see why the match failed.
```

**Implementation complexity**: Medium (50 lines, requires call correlation)
**Expected impact**: Medium (reduces retry loops)

### 3. Test-Fix-Test Cycle Detector
**Frequency**: 193 occurrences
**Pattern**: Test → failure → Edit → Test → failure (3+ iterations)
**Intervention**: Surface pattern for learning, suggest debugging approach
**Example**:
```
[Guardian] You've been in a Test-Fix-Test loop for 4 iterations.

Pattern: test_scheduler.py has failed 4 times with assertion errors.

Suggestion: Add debug logging or run test in isolation to understand root cause.
```

**Implementation complexity**: High (100 lines, multi-step correlation)
**Expected impact**: High (reduces thrashing, improves debugging)

### Candidate Backlog (Not Prioritized)
- Write fail → Edit fallback (216 occurrences)
- Read failure investigation (54% Read failure rate — likely hook artifact)
- High re-edit frequency (scheduler.py edited 71x, MEMORY.md 60x)

---

## 10. Data Contract

### Event Schema (v1)
```json
{
  "event_id": "uuid-v4",           // Unique event identifier
  "schema_version": 1,             // For future migrations
  "timestamp": "2026-02-11T14:32:01.123Z",  // ISO8601 with milliseconds
  "project": "/abs/path/to/project",        // Repository root
  "tool": "Edit",                   // Tool name (Edit, Read, Bash, etc.)
  "target_path": "/abs/path/to/file.py",    // File being acted upon
  "status": "warn_blind_edit",      // pass | warn | block | bypass
  "error_signature": "FileNotFoundError: old_string not found",  // Nullable
  "session_id": "uuid-v4"           // Optional session correlator
}
```

### Storage Architecture

#### Layer 1: JSONL (Append-Only)
**Path**: `~/.cortex-lean/guardian_log.jsonl`
**Purpose**: Raw event stream, immutable audit log
**Retention**: 30 days
**Format**: One JSON object per line (newline-delimited)

**Advantages**:
- Simple append (no locking)
- Human-readable with `jq`
- Easy to back up / transfer
- Crash-safe (no partial writes)

#### Layer 2: SQLite (Aggregated Patterns)
**Path**: `~/.cortex-lean/cortex.db`
**Purpose**: Fast queries for pattern detection
**Retention**: Indefinite
**Schema**:
```sql
CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  timestamp INTEGER,  -- Unix epoch for fast range queries
  project TEXT,
  tool TEXT,
  target_path TEXT,
  status TEXT,
  error_signature TEXT
);

CREATE INDEX idx_timestamp ON events(timestamp);
CREATE INDEX idx_project_tool ON events(project, tool);
CREATE INDEX idx_target_path ON events(target_path);

CREATE TABLE patterns (
  pattern_id TEXT PRIMARY KEY,
  pattern_type TEXT,  -- e.g., "bash_failure_streak"
  occurrences INTEGER,
  last_seen INTEGER,
  metadata JSON       -- Flexible storage for pattern-specific data
);
```

### Migration Process
**Batch job** (not real-time):
1. Read JSONL events newer than last migration timestamp
2. Insert into SQLite with deduplication (event_id unique constraint)
3. Update patterns table with new occurrences
4. Prune JSONL events older than 30 days

**Trigger**: Daily at 3 AM local time (low-activity window)
**Failure mode**: Skip migration, retry next day (JSONL is source of truth)

### Schema Evolution
**Versioning**: `schema_version` field enables migrations
**Process**:
1. New schema version ships with migration script
2. First hook invocation checks `SELECT MAX(schema_version) FROM events`
3. If outdated, runs migration (e.g., add column, backfill nulls)
4. Updates `schema_version` in config

**Example migration** (v1 → v2, add `duration_ms` field):
```python
def migrate_v1_to_v2():
    db.execute("ALTER TABLE events ADD COLUMN duration_ms INTEGER")
    db.execute("UPDATE events SET duration_ms = NULL WHERE schema_version = 1")
    db.execute("UPDATE events SET schema_version = 2")
```

---

## 11. Implementation Roadmap

### Phase 0: Foundation (COMPLETE)
- ✅ Data audit (59,917 events analyzed)
- ✅ Competitive research (landscape mapped)
- ✅ MVP Guardian #1 deployed (`edit_without_read_guard.py`)
- ✅ State management (`~/.cortex-lean/` directory structure)
- ✅ Telemetry pipeline (`guardian_log.jsonl`)

### Phase 1: Validation (IN PROGRESS)
**Timeline**: 7-14 days
**Goal**: Prove Guardian #1 reduces Edit failure rate by ≥20%

**Tasks**:
- [ ] Collect 7 days of telemetry
- [ ] Calculate baseline vs. current Edit failure rate
- [ ] Analyze bypass patterns (if any)
- [ ] Document false positives
- [ ] Gate 1 decision: proceed to Phase 2 or iterate

### Phase 2: Guardian #2 (PENDING GATE 1)
**Timeline**: 7 days after Gate 1
**Goal**: Deploy Bash failure streak detector, validate multi-guardian UX

**Tasks**:
- [ ] Implement Bash failure streak hook (30 lines)
- [ ] Test noise budget enforcement (≤5 interventions/day)
- [ ] Measure cross-guardian correlation
- [ ] Gate 2 decision: proceed to Phase 3 or tune

### Phase 3: Graph Intelligence (PENDING GATE 2)
**Timeline**: 14 days after Gate 2
**Goal**: Activate Context Graph, automate pattern suggestion

**Tasks**:
- [ ] Build Context Graph from telemetry (nodes = files, edges = co-edited)
- [ ] Implement retrieval relevance scoring
- [ ] Surface top pattern candidates to user for approval
- [ ] Gate 3 decision: scale or stabilize

### Phase 4: V1 Consolidation (PENDING GATE 2)
**Timeline**: Parallel with Phase 3
**Goal**: Archive dead V1 code, migrate to Lean-only

**Tasks**:
- [ ] Archive `engines/v2/`, `engines/v21/`
- [ ] Stop V1 daemons (flywheel, work-absorber)
- [ ] Migrate V1 telemetry to Lean schema
- [ ] Update tests to use `~/.cortex-lean/` paths
- [ ] Document V1 → Lean migration in `/cortex/CHANGELOG.md`

---

## 12. Success Criteria

### MVP Success (Gate 1)
**Quantitative**:
- Edit failure rate drops to ≤60.6% (baseline: 75.7%)
- Blind edit rate drops to <5% (baseline: 13%)
- Zero Cortex-caused work blockages

**Qualitative**:
- Guardian warnings are useful (not noise)
- Developer trusts warnings enough to act on them
- No complaints about performance impact

### Product-Market Fit Signals
**Early adopters** (target: 10 developers by Q2 2026):
- Voluntary installation (not mandated)
- Daily active usage (hook invocations)
- Positive feedback on intervention quality

**Market validation**:
- GitHub stars >100 (interest)
- Inbound issues/PRs (engagement)
- No major forks (product direction accepted)

### Failure Conditions (Kill Gates)
**Kill if any occur**:
1. Edit failure rate **increases** after 14 days of Guardian #1
2. Bypass rate >50% (warnings are noise)
3. Developer disables Cortex permanently
4. Competitor ships equivalent feature before Gate 2

---

## 13. Open Questions

### Product
1. **Branding**: Keep "Cortex" despite cortex.io collision? Alternative names?
2. **Telemetry opt-in**: Should telemetry be default-on or default-off?
3. **Cross-project learning**: When/how to share anonymized patterns across repos?

### Technical
1. **SessionStart reliability**: Claude SDK doesn't guarantee SessionStart hook — how to handle mid-session joins?
2. **Hook performance**: What's acceptable latency for PreToolUse warnings? (target: <100ms)
3. **SQLite concurrency**: Handle multi-session writes (rare but possible with parallel Claude instances)?

### Market
1. **IntelliCode autopsy**: Why did Microsoft kill it? Strategic cannibalization or market rejection?
2. **Pricing model**: Free tier limits? Pro tier features? (if we ship cloud sync)
3. **Enterprise adoption**: Do we need team-level pattern sharing? Compliance features?

---

## Appendix A: Terminology

- **Guardian**: A specific pattern detector + intervention (e.g., Edit-without-Read Guardian)
- **Pattern**: A recurring sequence of tool calls (e.g., Edit fail → retry loop)
- **Intervention**: A warning, suggestion, or block presented to the developer
- **Bypass**: User chooses to proceed despite intervention
- **Blind edit**: Edit call on a file not Read in the current session
- **Noise budget**: Maximum interventions per day before suppression
- **Fail open**: System failure allows work to continue (never blocks)
- **Context Graph**: Network of files/tools with co-occurrence edges (future)

## Appendix B: References

### Source Documents
- `CORTEX_LEAN_STRATEGY.md`: Data audit, competitive analysis, strategy decisions
- `edit_without_read_guard.py`: MVP Guardian #1 implementation (129 lines)
- `rule_adherence_hook.py`: V1 implementation for comparison (223 lines)

### Data Audit Summary
- **59,917 events** across 34 days, 211 sessions, 47 tools, 21 projects
- **103 distinct patterns** detected (threshold: 10 occurrences)
- **Top pain points**: Edit failure (75.7%), Bash streaks (967), retry loops (1,199)

### Competitive Landscape
- **Memory tools**: Mem0, claude-mem, Cursor, Windsurf, Letta, Augment, Cline
- **Code intelligence**: Augment Code, Cody, Cursor
- **Killed competitors**: IntelliCode (Microsoft, Dec 2025)
- **Validation**: AWS Kiro (agent hooks), academic research ($50K/yr context cost)

---

**Document Status**: Living specification, updated as gates are cleared.
**Last Updated**: 2026-02-11
**Next Review**: After Gate 1 evaluation (7-day telemetry complete)
