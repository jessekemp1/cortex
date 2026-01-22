# Cortex Organization Assessment

**Date:** 2026-01-20
**Issue:** Batch system and analysis reports are disorganized

---

## 🔍 CURRENT STATE (PROBLEMS)

### ❌ Reports Scattered in ~/Dev Root
```
~/Dev/
├── SECURITY-SCAN.md (24K)
├── TEST-COVERAGE-ANALYSIS.md (42K)
├── CODE-QUALITY-SCAN.md (18K)
├── DEPENDENCY-AUDIT.md (15K)
├── DOCS-COMPLETENESS.md (12K)
├── OVERNIGHT_ANALYSIS_SUMMARY.md (3.5K)
├── CODE_QUALITY_ANALYSIS.md (duplicate)
├── DEPENDENCY_AUDIT.md (duplicate)
... and 8 more analysis markdown files
```
**Problem:** 14+ analysis reports polluting Dev root directory

### ❌ Cortex Root Cluttered
```
cortex/
├── BATCH_ANALYSIS_2026-01-18.md
├── BATCH_ANALYSIS_JOBS_EXPLAINED.md
├── BATCH_FIRST_SUBMISSION_SUCCESS.md
├── BATCH_ORCHESTRATOR_FIXED.md
├── BATCH_TASKS_COMPLETE.md
├── TONIGHT_BATCH_SUMMARY.md
... dozens of status/summary markdown files
```
**Problem:** Implementation notes mixed with codebase

### ❌ Batch System Not Fully in Cortex
```
Batch files created but not committed:
- cortex/batch/queue_manager.py ← Created but needs integration
- cortex/batch/queue.sh ← Created but needs integration
```
**Problem:** New batch orchestration not integrated with existing batch/ directory

### ❌ No Clear Analysis Archive Structure
**Problem:** No organized way to store historical analysis reports

---

## ✅ WHAT'S ALREADY CORRECT

### Good: Runtime Data Separation
```
~/.cortex/
├── batches/
│   ├── remediation_queue.json ← Queue state (runtime)
│   ├── msgbatch_*_metadata.json ← Batch metadata (runtime)
│   ├── msgbatch_*_results/ ← Raw batch output (runtime)
│   └── queue_manager.log ← Process logs (runtime)
```
**Good:** Runtime data properly separated from code

### Good: Batch API Client
```
cortex/batch/
├── batch_api_client.py ← Core API wrapper (GOOD)
├── batch_config.py ← Configuration (GOOD)
└── tests/ ← Tests (GOOD)
```
**Good:** Batch API foundation is solid

---

## 🎯 PROPOSED STRUCTURE

### Cortex Project Organization

```
cortex/
├── batch/                          ← Batch orchestration (EXPAND)
│   ├── __init__.py
│   ├── batch_api_client.py        ← Existing: Core API wrapper
│   ├── batch_config.py             ← Existing: Configuration
│   ├── queue_manager.py            ← NEW: Queue orchestration
│   ├── queue.sh                    ← NEW: CLI helper script
│   ├── queues/                     ← NEW: Queue definitions
│   │   ├── remediation_queue.json ← Move from ~/.cortex
│   │   ├── learning_queue.json
│   │   └── analysis_queue.json
│   ├── orchestrators/              ← NEW: High-level orchestration
│   │   ├── __init__.py
│   │   ├── remediation_orchestrator.py
│   │   └── intelligence_orchestrator.py
│   └── tests/
│       ├── test_batch_api_client.py
│       └── test_queue_manager.py
│
├── analysis/                       ← NEW: Analysis storage & tools
│   ├── __init__.py
│   ├── reports/                    ← Structured analysis reports
│   │   ├── 2026-01-19-overnight/   ← Date-stamped analysis
│   │   │   ├── summary.md
│   │   │   ├── security.md
│   │   │   ├── test-coverage.md
│   │   │   ├── code-quality.md
│   │   │   ├── dependencies.md
│   │   │   └── documentation.md
│   │   └── archive/                ← Historical analyses
│   ├── templates/                  ← Analysis prompt templates
│   │   ├── security_audit.yaml
│   │   ├── test_coverage.yaml
│   │   └── dependency_audit.yaml
│   └── processors/                 ← Analysis result processors
│       ├── __init__.py
│       ├── security_processor.py
│       └── coverage_processor.py
│
├── intelligence/                   ← Existing: Intelligence engines
│   ├── portfolio_memory.py         ← Should learn from analysis
│   ├── recommendation_engine.py
│   └── context_intelligence.py
│
├── cli/                            ← NEW: CLI command organization
│   ├── __init__.py
│   ├── batch_commands.py           ← /batch-* commands
│   ├── analysis_commands.py        ← /analyze commands
│   └── queue_commands.py           ← /queue commands
│
├── runtime/                        ← Runtime state management
│   └── state_manager.py
│
└── docs/                           ← Project documentation (not runtime notes)
    ├── batch_system.md
    ├── analysis_system.md
    └── architecture.md
```

### Runtime Data (~/.cortex)

```
~/.cortex/
├── batches/                        ← Batch runtime data
│   ├── active/                     ← Active batch metadata
│   │   ├── msgbatch_*_metadata.json
│   │   └── queue_state.json        ← Current queue state
│   ├── results/                    ← Raw batch results
│   │   └── msgbatch_*/
│   └── logs/
│       ├── queue_manager.log
│       └── batch_submissions.log
│
├── memory/                         ← Portfolio memory data
│   ├── patterns.json
│   └── sessions.json
│
└── config.yaml                     ← User configuration
```

---

## 📋 REORGANIZATION PLAN

### Phase 1: Clean Up Dev Root (Immediate)
1. **Move analysis reports to cortex/analysis/reports/**
   - Create date-stamped directory: `2026-01-19-overnight/`
   - Move all *SCAN.md, *ANALYSIS.md files
   - Delete duplicates

2. **Move implementation notes to cortex/docs/archive/**
   - Move BATCH_*.md files
   - Move SESSION_*.md files
   - Keep only essential docs in cortex root

### Phase 2: Integrate Queue System (This session)
1. **Fix import issues in queue_manager.py**
   - Ensure proper module structure
   - Add to cortex/__init__.py

2. **Create cortex/batch/queues/ directory**
   - Move remediation_queue.json template
   - Add queue schema validation

3. **Integrate with CLI**
   - Add `/queue` commands to cli.py
   - Add `/batch-queue` command
   - Link to existing /batch-status

### Phase 3: Analysis System (Next session)
1. **Create cortex/analysis/ module**
   - Analysis processors for each report type
   - Template system for prompts
   - Integration with portfolio memory

2. **Add analysis CLI commands**
   - `/analyze security`
   - `/analyze coverage`
   - `/analyze dependencies`

### Phase 4: Memory Integration (Future)
1. **Teach portfolio memory from analyses**
   - Security patterns → Remember for future
   - Test gaps → Recommend tests proactively
   - Code smells → Suggest refactorings

---

## 🚀 IMMEDIATE ACTIONS (NOW)

1. ✅ Create cortex/analysis/reports/2026-01-19-overnight/
2. ✅ Move all analysis .md files from ~/Dev to structured location
3. ✅ Create cortex/docs/archive/ and move implementation notes
4. ✅ Fix batch/queue_manager.py imports
5. ✅ Update queue.sh paths
6. ✅ Test queue system end-to-end
7. ✅ Clean up ~/Dev root
8. ✅ Update README with new structure

---

## 🎯 SUCCESS CRITERIA

**Clean Structure:**
- [ ] ~/Dev contains ONLY CLAUDE.md, project dirs, and active summary docs
- [ ] All analysis reports in cortex/analysis/reports/YYYY-MM-DD-*/
- [ ] All batch code in cortex/batch/
- [ ] Queue system fully functional and tested

**Usable System:**
- [ ] `/queue status` shows current queue state
- [ ] `/batch-status` shows batch progress
- [ ] Queue manager auto-submits on capacity
- [ ] Analysis reports accessible via CLI

**Future-Proof:**
- [ ] Clear separation: code vs runtime data vs reports
- [ ] Extensible: Easy to add new analysis types
- [ ] Integrated: Analysis feeds portfolio memory
- [ ] Documented: Clear README and docs/

---

**Next:** Execute Phase 1 & 2 reorganization NOW.
