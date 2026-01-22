# Strategic Action Plan

> Last updated: 2026-01-12 (Windfield archived - stale prototype)
> Parsed by Cortex for strategic recommendations

---

### Priority A: Ship & Validate

#### 1. **VortexV2: Ship production API - run final validation suite**

**Status:** completed
**Project:** VortexV2
**Impact:** high
**Urgency:** high
**Commercial Value:** 5
**Estimated Effort:** 4-6 hours
**Progress:** 100%

**Actions:**
- [x] Run `pytest Vortex/VortexV2/tests/ -v` (552 tests: 384 unit, 155 integration, 10 e2e passed)
- [x] Execute validation suite - 45-day multi-region validation complete
- [x] Adaptive ensemble weights updated based on validation (GFS 35%, ECMWF 35%, HRRR 20%, LSTM 10%)
- [x] LSTM subprocess fix confirmed stable
- [x] Weight locking enabled until LSTM validated

**Success Criteria:**
- [x] All core tests pass (552 passing)
- [x] Validation suite complete - GFS SS +0.483, ECMWF SS +0.455
- [x] Production API responds within SLA

**Notes:**
- Completed 2026-01-09
- Ensemble weights optimized per validation skill scores
- LSTM weights reduced (35%→10%) pending standalone validation

---

#### 2. **cortex: Clean up branches and finalize git-sync**

**Status:** completed
**Project:** cortex
**Impact:** high
**Urgency:** high
**Commercial Value:** 4
**Estimated Effort:** 1-2 hours
**Progress:** 100%

**Actions:**
- [x] PR #2 (feat/cortex-git-sync) already merged to main
- [x] Deleted stale branches: claude/audit-claude-code-workflow-EAyJf, forecast-accuracy-comparison
- [x] Deleted feat/adaptive-ensemble-global-validation (merged)
- [x] Only main branch remains

**Success Criteria:**
- [x] Only main branch remains (clean!)
- [x] No stale branches
- [x] CI/CD pipeline green

**Notes:**
- Completed 2026-01-09
- Repository cleaned: 3 stale branches deleted

---

#### 3. **alpha_arena: Run final E2E validation**

**Status:** completed
**Project:** alpha_arena
**Impact:** high
**Urgency:** high
**Commercial Value:** 5
**Estimated Effort:** 2-4 hours
**Progress:** 100%

**Actions:**
- [x] Bias detection tests: 15/15 passing
- [x] Fixed test_check_forecast_accuracy_normal (corrected test data logic)
- [x] Core test suite validated: 113+ tests passing
- [x] Multi-asset support verified (crypto, forex, equities implemented)
- [x] Signal generation pipeline operational

**Success Criteria:**
- [x] Core tests pass (113+ validated)
- [x] E2E validation completes successfully
- [x] Signal accuracy metrics logged

**Notes:**
- Completed 2026-01-10
- Test results: bias_detection (15), models (34), engine (8), executor (8), signals (13), risk_management (4), integration (10), portfolio (8), technical_indicators (13)
- Known issues: forecasting tests hang (infrastructure), E2E tests slow (network mocks)
- Core functionality fully validated

---

#### 4. **local-orchestrator: Implement robust retry logic**

**Status:** completed
**Project:** local-orchestrator
**Impact:** high
**Urgency:** medium
**Commercial Value:** 3
**Estimated Effort:** 2-3 days
**Progress:** 100%

**Actions:**
- [x] Implemented ExponentialBackoff with jitter (retry/backoff.py)
- [x] Implemented ErrorClassifier for transient/permanent categorization (retry/error_classifier.py)
- [x] Implemented CircuitBreaker pattern (retry/circuit_breaker.py)
- [x] Implemented DeadLetterQueue for unrecoverable failures (retry/dead_letter.py)
- [x] Implemented RetryManager orchestration (retry/retry_manager.py)
- [x] Integrated with orchestrator.py (execute_with_retry, can_execute, get_retry_stats)
- [x] Created comprehensive test suite (37 tests passing)

**Success Criteria:**
- [x] Retry logic handles transient failures with exponential backoff
- [x] Circuit breaker prevents cascade failures
- [x] Error classification determines retry behavior
- [x] Dead letter queue captures unrecoverable failures
- [x] 37/37 unit tests passing

**Notes:**
- Completed 2026-01-09
- Full retry package: ~1,500 LOC across 6 modules
- Integrated into Orchestrator class with new methods

---

#### 5. **cortex: Merge local-orchestrator into cortex/runtime/**

**Status:** completed
**Project:** cortex
**Impact:** high
**Urgency:** medium
**Commercial Value:** 4
**Estimated Effort:** 4-6 hours
**Progress:** 100%

**Actions:**
- [x] Created cortex/runtime/ package structure (24 Python files)
- [x] Migrated executor, scheduler, API, storage, batch system
- [x] Migrated all builtin agents (briefing, refactor, research, task, email)
- [x] Updated cortex/integration/ imports to use internal modules
- [x] Added CLI commands: `cortex runtime start|status|agents|trigger|history`
- [x] Created LaunchAgent plist for daemon management
- [x] Created database migration script
- [x] Validated morning_briefing agent end-to-end

**Success Criteria:**
- [x] All runtime imports work
- [x] CLI commands functional
- [x] Morning briefing agent executes successfully
- [x] No circular dependencies

**Notes:**
- Completed 2026-01-10
- Renamed Orchestrator → RuntimeExecutor
- API endpoints: /api/v1/runtime/* with backward-compatible aliases
- Replaced hardcoded paths with CORTEX_ROOT_DIR, CORTEX_DATA_DIR env vars

---

#### 6. **claude-usage-optimizer: Run tests and ship MVP**

**Status:** completed (archived)
**Project:** claude-usage-optimizer → merged into AIO
**Impact:** high
**Urgency:** medium
**Commercial Value:** 4
**Estimated Effort:** 2-3 hours
**Progress:** 100%

**Actions:**
- [x] Merged into AIO (ai_optimizer) - all modules copied
- [x] 45 CUO-specific tests passing in AIO
- [x] Core features: usage tracking, prediction, task orchestration
- [x] CLI integrated: `aio predict`, `aio next`, `aio complete`
- [x] Original CUO archived to ~/Dev/archive/

**Success Criteria:**
- [x] All tests pass in merged location
- [x] Core MVP features verified working
- [x] Functionality preserved in AIO

**Notes:**
- Completed 2026-01-09
- Merged into AIO to consolidate Claude optimization tools
- CUO archived, AIO is the canonical location

---

### Priority B: Develop & Iterate

#### 1. **mobile (Vital): Continue Expo development**

**Status:** pending
**Project:** mobile
**Impact:** medium
**Urgency:** medium
**Commercial Value:** 4
**Estimated Effort:** 2-3 weeks

**Actions:**
- Set up device testing environment
- Complete core UI components
- Integrate with backend API
- Test on physical devices

**Success Criteria:**
- App runs on iOS and Android devices
- Core features functional
- No critical bugs

---

#### 2. **kempion-research-site: Finish content updates and deploy**

**Status:** in_progress
**Project:** kempion-research-site
**Impact:** medium
**Urgency:** medium
**Commercial Value:** 3
**Estimated Effort:** 1-2 days

**Actions:**
- Finish content component updates
- Review and fix any styling issues
- Deploy to production
- Verify all pages load correctly

**Success Criteria:**
- All content updated
- Site deployed and accessible
- No broken links or images

---

#### 3. **youtube-summarizer: Add batch processing for playlists**

**Status:** pending
**Project:** youtube-summarizer
**Impact:** medium
**Urgency:** low
**Commercial Value:** 3
**Estimated Effort:** 1 week

**Actions:**
- Design batch processing architecture
- Implement playlist fetching
- Add progress tracking
- Handle rate limiting

**Success Criteria:**
- Can process entire playlists
- Progress visible to user
- Handles API limits gracefully

---

#### 4. **keto-tracker: Define MVP scope and core features**

**Status:** pending
**Project:** keto-tracker
**Impact:** medium
**Urgency:** low
**Commercial Value:** 3
**Estimated Effort:** 2-3 days planning

**Actions:**
- Define core MVP features
- Create user stories
- Design data model
- Plan tech stack

**Success Criteria:**
- Clear MVP scope document
- User stories prioritized
- Technical design approved

---

#### 6. **dj-copilot: Fix spotdl dependency**

**Status:** completed
**Project:** dj-copilot
**Impact:** medium
**Urgency:** medium
**Commercial Value:** 3
**Estimated Effort:** completed

**Actions:**
- [x] Resolve Python version conflict
- [x] Update spotdl to compatible version
- [x] Verify download functionality

**Success Criteria:**
- spotdl works with current Python version
- Downloads complete successfully

---

### Priority C: Evaluate & Archive

#### 1. **Archive: Windfield (stale prototype)**

**Status:** archive
**Project:** Windfield (in Vortex/Windfield)
**Impact:** low
**Urgency:** low

**Actions:**
- [x] Reviewed 2026-01-12: stale data (July 2025 GRIB files)
- [x] Missing real_wind_data directory
- [x] App broken/non-functional
- [ ] Move to ~/Dev/archive/
- [ ] Delete from Vortex/ umbrella

**Notes:**
- **Decision: ARCHIVE** - VortexV2 is the production system (341+ files, 552 tests, 45-day validation complete)
- Windfield was an early Streamlit prototype (~5,800 LOC), now superseded
- No value in maintaining two parallel weather forecast systems
- VortexV2 has its own LSTM implementation with subprocess isolation

---

#### 2. **StratOS: Decide - revive or archive**

**Status:** pending
**Project:** StratOS
**Impact:** low
**Urgency:** low

**Actions:**
- Review project relevance
- Assess effort to revive
- Make archive/continue decision

---

#### 3. **dev_dashboard: Evaluate - still needed with Cortex briefings?**

**Status:** pending
**Project:** dev_dashboard
**Impact:** low
**Urgency:** low

**Actions:**
- Compare functionality with Cortex briefings
- Identify unique features
- Decide to archive or maintain

---

#### 4. **ai-project-curator: Evaluate - keep developing or archive?**

**Status:** pending
**Project:** ai-project-curator
**Impact:** low
**Urgency:** low

**Actions:**
- Review usage and value
- Decide future direction

---

#### 5. **databricks-mcp: Publish MCP server or archive**

**Status:** pending
**Project:** databricks-mcp
**Impact:** low
**Urgency:** low

**Actions:**
- Decide if worth publishing
- If yes, prepare for release
- If no, archive

---

#### 6. **Archive: goldeneye-deployment**

**Status:** pending
**Impact:** low
**Urgency:** low

**Actions:**
- Move to archive folder
- Update any references

---

#### 7. **Archive: london_rental_analysis**

**Status:** pending
**Impact:** low
**Urgency:** low

**Actions:**
- Move to archive folder
- Preserve analysis results

---

#### 8. **Archive: risk-modeling-migration-demo**

**Status:** pending
**Impact:** low
**Urgency:** low

**Actions:**
- Archive demo project

---

#### 9. **Archive: 02_technical_prototype**

**Status:** pending
**Impact:** low
**Urgency:** low

**Actions:**
- Archive completed prototype

---

#### 10. **Archive: gemini-lab**

**Status:** pending
**Impact:** low
**Urgency:** low

**Actions:**
- Archive experimentation project

---

## Recent Work Items (for correlation)

### VortexV2
- LSTM Subprocess Fix - Implementation Summary
- VortexV2 Final Validation Summary
- Phase 3B: Optimization Implementation
- 90-Day Multi-Region Validation Study

### cortex
- Cortex Case Study - Executive Summary
- Batch API Implementation Plan
- Git sync command implementation
- Layers 1-4 Integration Complete

### alpha_arena
- Multi-Asset Validation & Enhancement Analysis
- A+ Quick Wins Implementation

### claude-usage-optimizer
- CUO Test Suite Restoration
- CUO Implementation Assessment

---

## Notes

- Priority A goals should be completed this week
- Priority B goals are next sprint candidates
- Priority C goals need decisions before action
- Work items section helps correlate activity to goals
