# Git Cleanup Plan - SAFE Strategy

**Created**: 2025-12-18
**Status**: Ready for review
**Risk Level**: LOW (preserves all active work)

---

## Current State Analysis

### Modified Files (ACTIVE WORK - DO NOT TOUCH)
- **VortexV2**: 87 modified files
  - Major changes: cache.py (+524), app/main.py (167), ensemble.py (114)
  - Status: **ACTIVE DEVELOPMENT**
- **Vital**: 6 modified files (Health Connect sync work)
  - Status: **ACTIVE DEVELOPMENT**
- **DJ-CoPilot**: 1 modified file (stem_separator.py, 161 changes)
  - Status: **ACTIVE DEVELOPMENT**
- **cortex**: 30+ modified files
  - Status: **ACTIVE DEVELOPMENT**
- **local-orchestrator**: 20+ modified files
  - Status: **ACTIVE DEVELOPMENT**

**Total Modified: 130+ files** ⚠️ **ALL PRESERVED - NOT TOUCHED**

---

## Untracked Files Analysis

### Category 1: Documentation (.md files) - SAFE TO COMMIT
**Total: 50+ documentation files**

#### Workspace-Level Docs
- `.SYSTEM_STATUS_FINAL.md`
- `MIGRATION_READY.md`
- `.claude/CORTEX_*.md` (10 files)
- `.claude/CUSTOM_SKILLS_ASSESSMENT.md`
- `.claude/GOLDEN_SPEC_*.md` (2 files)
- `.claude/STRESS_TEST_REPORT.md`
- `golden-spec-method/GOLDEN_SPEC_CORTEX_EDITION.md`

#### VortexV2 Docs
- `Vortex/VortexV2/VORTEX_PERFORMANCE_OPTIMIZATION_SUMMARY.md`
- `Vortex/VortexV2/docs/API_PERFORMANCE_FIX.md`
- `Vortex/VortexV3/*.md` (3 spec files)

#### Vital Docs
- `Vital/HEALTH_CONNECT_*.md` (2 files)
- `Vital/SYNC_*.md` (4 files)
- `Vital/TESTING_*.md` (2 files)
- `Vital/NETWORK_DEBUG.md`
- `Vital/QUICK_SYNC_CHECK.md`

#### DJ-CoPilot Docs
- `DJ-CoPilot/STEM_SEPARATION_IMPLEMENTATION.md`
- `DJ-CoPilot/STEM_SEPARATION_IMPLEMENTATION_GUIDE.md`

#### Alpha Arena Docs
- `alpha_arena/VALIDATION_*.md` (3 files)

#### Cortex Docs
- `cortex/.claude/BATCH_*.md` (2 files)
- `cortex/skills/IMPLEMENTATION_COMPLETE.md`

#### Local Orchestrator Docs
- `local-orchestrator/agents/dynamic/ARCHITECTURE_IMPACT_REPORT.md`
- `local-orchestrator/tasks/MORNING_BRIEFING_ANALYSIS.md`
- `local-orchestrator/tasks/REFINEMENT_*.md` (2 files)
- `local-orchestrator/test_spec.md`

### Category 2: Python Code Files - **ACTIVE WORK - PRESERVE**
**Total: 25+ .py files** ⚠️ **DO NOT COMMIT - ACTIVE WORK**

- `DJ-CoPilot/test_stem_separation.py`
- `Vortex/VortexV2/app/models/lstm_warmer.py`
- `Vortex/VortexV2/alembic/versions/c522397b1f01_*.py`
- `alpha_arena/scripts/intelligence_validation/*.py` (4 files)
- `alpha_arena/src/intelligence/testing/*.py` (3 files)
- `cortex/intelligence/*.py` (6 files)
- `cortex/skills/*.py` (5 files)
- `cortex/check_batches.py`
- `cortex/portfolio_memory.py`
- `cortex/.claude/hooks/*.py` (2 files)
- `local-orchestrator/agents/validation/golden_spec_validator_agent.py`
- `local-orchestrator/tasks/morning_briefing_refined.py`
- `local-orchestrator/tests/test_what_if.py`

### Category 3: Configuration Files - SAFE TO COMMIT
- `.claude/commands/plan.md`
- `.claude/skills/*.yaml` (3 skill definitions)
- `.claude/skills/README.md`
- `Vital/backend/com.jessekemp.vital-backend.plist`
- `Vital/backend/install_vital_backend_daemon.sh`
- `Vortex/VortexV2/com.jessekemp.vortexv2-api.plist`
- `Vortex/VortexV2/com.jessekemp.vortexv2-dashboard.plist`
- `local-orchestrator/com.jessekemp.local-orchestrator.plist`
- `local-orchestrator/install_daemon.sh`

### Category 4: Data/JSON Files - INVESTIGATE
- `local-orchestrator/agents/dynamic/*.json` (3 files)
- `cortex/.claude/agents/grib-validator.md`
- `Vortex/VortexV2/reports/` (directory)

### Category 5: Unknown Directories - INVESTIGATE
- `kempion-research-site/` - New directory?
- `Docs/Health Protocol/Operators_Edge_Whitepaper.md`

---

## Safe Cleanup Strategy

### Phase 1: Commit Documentation (SAFE)
**Risk**: NONE
**Action**: Commit all .md files

```bash
# Add all documentation
git add *.md .claude/*.md */**.md

# Create documentation commit
git commit -m "docs: add comprehensive project documentation

- VortexV2 performance optimization docs
- Vital Health Connect implementation docs
- DJ-CoPilot stem separation guides
- Alpha Arena validation reports
- Cortex enhancement and batch processing docs
- Local orchestrator refinement docs
- Migration readiness documentation
- System status reports

Generated during recent development sprints across all projects."
```

**Files Committed**: ~50 .md files
**Active Work Preserved**: ✅ All .py files untouched

### Phase 2: Commit Configuration Files (SAFE)
**Risk**: LOW
**Action**: Commit .claude configs and LaunchDaemon files

```bash
# Add Claude Code configuration
git add .claude/commands/plan.md
git add .claude/skills/

# Add LaunchDaemon configs
git add Vital/backend/*.plist Vital/backend/*.sh
git add Vortex/VortexV2/*.plist
git add local-orchestrator/*.plist local-orchestrator/*.sh

# Commit
git commit -m "chore: add LaunchDaemon configs and Claude skills

- Added /plan command
- Added 3 custom skills (audio, forecasting, trading)
- Added LaunchDaemon configs for background services
  - Vital backend daemon
  - VortexV2 API and dashboard daemons
  - Local orchestrator daemon"
```

**Files Committed**: ~12 config files
**Active Work Preserved**: ✅ All .py files untouched

### Phase 3: Investigate Unknown Items (CAREFUL)
**Risk**: MEDIUM
**Action**: Check what these are before deciding

```bash
# Check kempion-research-site
ls -la kempion-research-site/

# Check VortexV2 reports
ls -la Vortex/VortexV2/reports/

# Check JSON files
cat local-orchestrator/agents/dynamic/*.json | head -20
```

**Decision**: After investigation:
- If generated/cache → add to .gitignore
- If important → commit
- If junk → delete

### Phase 4: Update .gitignore (SAFE)
**Risk**: NONE
**Action**: Prevent future clutter

```bash
# Add to .gitignore
cat >> .gitignore << 'EOF'

# Generated reports and caches
**/reports/
**/agents/dynamic/*.json

# Temporary files
**/*_TEMP.md
**/*_DEBUG.md

EOF

git add .gitignore
git commit -m "chore: update .gitignore for generated files"
```

---

## What This DOES NOT Touch

### ✅ PRESERVED - ACTIVE WORK
1. **All 130+ modified files** - Left untouched for active development
2. **All 25+ untracked .py files** - Left untouched (active code)
3. **VortexV2 cache refactor** - Preserved
4. **Vital Health Connect** - Preserved
5. **DJ-CoPilot stem separation** - Preserved
6. **cortex intelligence** - Preserved
7. **local-orchestrator refinements** - Preserved

---

## Expected Results

### After Phase 1-2
```bash
git status
# Should show:
# - ~60 documentation files committed
# - ~12 config files committed
# - All .py files still untracked (active work)
# - All modified files still modified (active work)
```

### Clean State Criteria
✅ Documentation organized and versioned
✅ Configuration versioned
⚠️ Active code work preserved (not committed yet)
⚠️ Modified files preserved (not committed yet)

**NOT a clean state for migration** - Still have active work
**IS progress** - Documentation and config organized

---

## Migration Readiness

### After This Cleanup
- [ ] Documentation committed ✅
- [ ] Config committed ✅
- [ ] Active .py files still untracked ⚠️
- [ ] Modified files still modified ⚠️

### To Reach Migration Readiness
**Still need to:**
1. Complete and commit VortexV2 active work
2. Complete and commit Vital active work
3. Complete and commit DJ-CoPilot active work
4. Complete and commit cortex active work
5. Complete and commit local-orchestrator active work

**Estimated Time to Clean State**: Depends on active work completion

---

## Execution Commands

### Quick Execute (Phases 1-2)
```bash
cd /Users/jesse.kemp/Dev

# Phase 1: Documentation
git add "*.md" ".claude/*.md"
git commit -m "docs: add comprehensive project documentation"

# Phase 2: Configuration
git add .claude/commands/ .claude/skills/
git add Vital/backend/*.plist Vital/backend/*.sh
git add Vortex/VortexV2/*.plist
git add local-orchestrator/*.plist local-orchestrator/*.sh
git commit -m "chore: add LaunchDaemon configs and Claude skills"

# Push
git push origin main
```

### Verify After
```bash
git status
# Should see reduced untracked count
# All active work (.py, modified files) still present
```

---

## Risk Assessment

**Phase 1 Risk**: NONE - Documentation only
**Phase 2 Risk**: LOW - Config files only
**Phase 3 Risk**: MEDIUM - Requires investigation
**Phase 4 Risk**: NONE - .gitignore update

**Overall Risk**: LOW
**Active Work Safety**: 100% - Nothing touched

---

**Status**: Ready for execution
**Recommendation**: Execute Phases 1-2, then reassess
**Next Step**: Complete active development work before migration
