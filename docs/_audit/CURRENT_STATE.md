# Cortex V1 Current State Inventory

**Generated**: 2026-01-02
**Purpose**: Pre-V2 Prime reconnaissance before architectural transformation

---

## Root Directory Status

**Files in cortex/ root**: 80+ markdown files (digital hoarding)
**Status**: CRITICAL - requires 80% reduction per V2 Prime directive

### Status Artifact Patterns to Archive:
- `*_COMPLETE.md` - 15+ files
- `*_STATUS.md` - 5+ files  
- `*_PLAN.md` - 10+ files
- `BRIEFING_*.md` - 3+ files
- `*SUMMARY.md` - 5+ files
- `*_READY.md` - 3+ files
- `WEEK*` patterns - 10+ files

### Core Files to KEEP:
- `__init__.py`
- `bridge.py` (2220 lines) - Universal Bridge API
- `cli.py` (2115 lines) - Command-line interface
- `orchestrator.py` - Core orchestrator
- `learning.py` - Learning system
- `mcp_server.py` - MCP integration
- `README.md`
- `requirements.txt`
- `config.py`

---

## docs/ Directory Status

**Files in docs/**: 25 files
**Status**: CRITICAL - 60%+ redundancy, needs consolidation

### Redundant File Groups:

1. **Whitepapers (4 files -> 0)**: Archive all, superseded by V2 Prime
   - WHITEPAPER_V1.md (568 lines)
   - WHITEPAPER_V2.md (779 lines)
   - CORTEX_V1_WHITEPAPER.md (1252 lines) - DUPLICATE
   - CORTEX_V2_WHITEPAPER.md (797 lines) - DUPLICATE

2. **Technical Specs (4 files -> 1 TECHNICAL_REFERENCE.md)**:
   - GOLDEN_SPEC.md (1359 lines)
   - TECHNICAL_SPECIFICATION.md (2017 lines)
   - ARCHITECTURE.md (780 lines)
   - DESIGN.md (857 lines)

3. **Plans/Reviews (4 files -> 0)**: Archive all
   - plan.md (123 lines)
   - DOCUMENTATION_PLAN.md (492 lines)
   - RESEARCH_PLAN.md (513 lines)
   - QUALITY_REVIEW.md (884 lines) - self-review

4. **Keep as-is**:
   - API.md (1069 lines) - API reference
   - DEPLOYMENT.md (565 lines) + INSTALLATION.md (537 lines) -> merge
   - METRICS.md (423 lines)
   - PLANNING_MODULE.md (531 lines)
   - TROUBLESHOOTING.md (302 lines)
   - CONTRIBUTING.md (160 lines)
   - COMPETITIVE_ANALYSIS.md (544 lines)
   - CASE_STUDY*.md (3 files) - evidence
   - LIMITATIONS.md (792 lines) - honest assessment
   - user_guide/, developer/, api/ directories

---

## Core Python Modules

| Module | Lines | Purpose | V2 Prime Role |
|--------|-------|---------|---------------|
| bridge.py | 2220 | Universal Bridge API | Engine C: Action Broker integration |
| cli.py | 2115 | Command-line interface | CLI for V2 engines |
| orchestrator.py | ~800 | Core orchestrator | Engine B: Synthesis Core |
| learning.py | ~600 | Learning system | Outcome tracking |
| mcp_server.py | ~400 | MCP integration | Engine A: IDE Bridge |
| portfolio_memory.py | ~500 | Portfolio storage | Graph node storage |
| session_manager.py | ~300 | Session context | Signal context |

---

## V1 Capabilities Assessment

| Capability | Status | V2 Prime Upgrade |
|------------|--------|------------------|
| Portfolio Memory | FUNCTIONAL | -> Context Graph nodes |
| Recommendation Engine | FUNCTIONAL | -> Action Broker |
| Learning System | PARTIAL (127 outcomes) | -> Confidence Calibration |
| Context Retrieval | FUNCTIONAL | -> Synthesis Core |
| Active Monitoring | NOT IMPLEMENTED | -> Context Absorber (NEW) |
| Proactive Intervention | NOT IMPLEMENTED | -> Action Broker (NEW) |
| Inter-Agent Protocol | NOT IMPLEMENTED | -> IAP Handler (NEW) |
| Real-time Signals | NOT IMPLEMENTED | -> FileWatcher/ShellListener (NEW) |

---

## Data Storage

### ~/.claude/portfolio/
- project_index.json - Project registry
- patterns.json - Pattern library
- lessons.json - Lessons learned
- goals.json - Active goals
- outcomes.json - Outcome history (127 entries)
- metrics.json - Performance metrics

### ~/.cortex/
- config.json - Configuration
- outcomes.jsonl - Outcome log (append-only)
- logs/ - Application logs

---

## Integration Points

| Integration | Status | Notes |
|-------------|--------|-------|
| MCP Server | ACTIVE | Basic tooling exposed |
| Git Hooks | ACTIVE | commit-msg, post-commit |
| Shell Hooks | PARTIAL | zsh startup context |
| Local Orchestrator | ACTIVE | Agent triggering |
| Batch API | ACTIVE | Background processing |

---

## Conclusion

**V1 Architecture is fundamentally passive** - waits for user commands rather than proactively managing context.

**V2 Prime addresses this** with the 3-Engine Active Model:
1. **Context Absorber** (Input) - Real-time signal ingestion
2. **Synthesis Core** (Processing) - Graph-based context synthesis
3. **Action Broker** (Output) - Proactive interventions

**Next Step**: Execute Phase 1 Purge to reduce file clutter before architectural transformation.
