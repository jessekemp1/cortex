# Week 3: Documentation Cleanup Plan

**Date**: 2026-01-21
**Priority**: LOW (Non-blocking)
**Status**: PLANNED
**Estimated Effort**: 4-6 hours

---

## 📋 Overview

After completing Week 1 (critical security) and Week 2 (high-priority improvements), security validation identified 45+ username exposures remaining in **documentation and archive files**.

**Risk Assessment**: LOW
- All runtime/production files are clean ✅
- Exposures are in non-executable documentation
- No production impact

---

## 🎯 Objectives

1. Remove username exposures from active documentation
2. Clean up archive directories (optional)
3. Update validation baseline
4. Establish documentation standards

---

## 📊 Current State

### ✅ Clean (Week 1 Complete)
- cortex/config.py
- cortex/requirements.txt
- alpha_arena/.env.template
- alpha_arena/requirements.txt
- Vortex/VortexV2/requirements.txt

### ⚠️ Remaining Exposures (45+ files)

**Active Documentation** (Priority 1):
- GOLDEN_SPEC.md
- ai-project-curator/README.md
- ai-project-curator/PROJECT_SUMMARY.md
- ai-project-curator/PROJECT_STATUS.md
- Databricks/README.md
- local-orchestrator/README.md
- cortex/batch/README.md
- cortex/skills/README.md
- Vortex/VortexV2/launch_site/README.md
- And 10+ more active project READMEs

**Completion Reports** (Priority 2):
- alpha_arena/PAPER_TRADING_COMPLETE.md
- alpha_arena/VENEZUELA_INTEGRATION_COMPLETE.md
- cortex/SECURITY_AUDIT_RESULTS.md
- cortex/SETUP_COMPLETE_2026-01-18.md
- And 13+ more status/completion documents

**Archive Directories** (Priority 3 - Optional):
- archive/vortex-legacy/README.md
- archive/cortex_archive_20251208/
- cortex/_archive_grok_mvp/
- cortex/_dead/
- And 5+ more archive locations

---

## 🔧 Implementation Plan

### Phase 1: Active Documentation (Priority 1)
**Effort**: 2 hours
**Files**: 19 active project READMEs

**Automated Approach**:
```bash
# Replace absolute paths with ~/Dev
find . -type f \( -name "README.md" -o -name "DEPLOYMENT.md" \) \
  ! -path "*/archive/*" \
  ! -path "*/\_dead/*" \
  ! -path "*/\_archive*" \
  -exec sed -i '' 's|/Users/[a-zA-Z][a-zA-Z0-9._-]*/Dev|~/Dev|g' {} +
```

**Validation**:
```bash
python3 cortex/scripts/validate_week1_security.py | \
  grep -v "archive\|_dead\|_archive"
```

### Phase 2: Completion Reports (Priority 2)
**Effort**: 1-2 hours
**Files**: 17 completion/status documents

**Automated Approach**:
```bash
# Clean completion and status reports
find . -type f -name "*.md" \
  \( -name "*COMPLETE*.md" -o -name "*STATUS*.md" -o -name "*SETUP*.md" \) \
  ! -path "*/archive/*" \
  ! -path "*/\_dead/*" \
  -exec sed -i '' 's|/Users/[a-zA-Z][a-zA-Z0-9._-]*/Dev|~/Dev|g' {} +
```

### Phase 3: Archive Cleanup (Priority 3 - Optional)
**Effort**: 1-2 hours
**Files**: 9 archive files

**Options**:
1. **Skip**: Archives are inactive, minimal risk (Recommended)
2. **Clean**: Apply same sed replacements
3. **Delete**: Remove if truly obsolete

---

## 🤖 Automation Script

Create `scripts/cleanup-username-exposures.sh`:

```bash
#!/bin/bash
# Documentation Cleanup Script

set -e

echo "=== Documentation Cleanup ==="

# Phase 1: Active Documentation
echo "Cleaning active documentation..."
find . -type f \( -name "README.md" -o -name "DEPLOYMENT.md" \) \
  ! -path "*/archive/*" \
  ! -path "*/\_dead/*" \
  ! -path "*/.git/*" \
  -exec sed -i '' 's|/Users/[a-zA-Z][a-zA-Z0-9._-]*/Dev|~/Dev|g' {} +

echo "✓ Active docs cleaned"

# Phase 2: Completion Reports
echo "Cleaning completion reports..."
find . -type f -name "*.md" \
  \( -name "*COMPLETE*.md" -o -name "*STATUS*.md" \) \
  ! -path "*/archive/*" \
  ! -path "*/\_dead/*" \
  -exec sed -i '' 's|/Users/[a-zA-Z][a-zA-Z0-9._-]*/Dev|~/Dev|g' {} +

echo "✓ Reports cleaned"

# Validation
echo "Validating..."
python3 cortex/scripts/validate_week1_security.py | \
  grep -v "archive\|_dead" | \
  grep "Username exposure" || echo "✓ No exposures in active files"

echo "=== Cleanup Complete ==="
```

---

## ✅ Success Criteria

### Phase 1 (Active Docs)
- [ ] All active READMEs cleaned
- [ ] No username exposures in project documentation
- [ ] Validation passes for non-archive files

### Phase 2 (Completion Reports)
- [ ] All status/completion docs cleaned
- [ ] Historical context preserved
- [ ] Paths use ~/Dev or relative references

### Phase 3 (Archives - Optional)
- [ ] Decision made: skip/clean/delete
- [ ] If cleaning: all archives processed

---

## 🔒 Documentation Standards (Going Forward)

### New Standard: Never Use Absolute Paths in Docs

**Good**:
```markdown
cd ~/Dev/project
./setup.sh
```

**Bad**:
```markdown
cd /Users/jesse.kemp/Dev/project
./setup.sh
```

### Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Check for username exposures in staged docs

staged_docs=$(git diff --cached --name-only | grep "\.md$")

if [ -n "$staged_docs" ]; then
  for file in $staged_docs; do
    if grep -q "/Users/[a-zA-Z]" "$file" 2>/dev/null; then
      echo "❌ Username exposure in $file"
      exit 1
    fi
  done
fi
```

---

## 📊 Effort Estimate

| Phase | Priority | Effort | Risk |
|-------|----------|--------|------|
| Phase 1: Active Docs | HIGH | 2 hours | Low |
| Phase 2: Completion Reports | MEDIUM | 1-2 hours | Low |
| Phase 3: Archives | LOW | 1-2 hours | Minimal |
| **Total** | - | **4-6 hours** | **Low** |

---

## 🎯 Recommended Timeline

**Option 1: Quick Win (Recommended)**
- **When**: This week
- **Scope**: Phase 1 only (active docs)
- **Effort**: 2 hours
- **Impact**: Highest value, minimal effort

**Option 2: Comprehensive**
- **When**: This month
- **Scope**: Phase 1 + 2 (skip archives)
- **Effort**: 3-4 hours
- **Impact**: All active content clean

**Option 3: Complete**
- **When**: Next quarter
- **Scope**: All phases including archives
- **Effort**: 4-6 hours
- **Impact**: 100% clean

---

## 🚦 Blocking vs Non-Blocking

### ✅ Non-Blocking for Production
This work does NOT block:
- Production deployment
- Feature development
- Team onboarding
- Testing activities

### 📅 Best Completed During
- Code cleanup sprints
- Documentation review cycles
- Before external audits
- Maintenance windows

---

## 💡 Key Insight

```
★ Insight ─────────────────────────────────────
Documentation cleanup follows the 80/20 rule:

**80% of value from 20% of effort**:
- Phase 1 (active docs): 2 hours, high impact
- Cleans what developers see daily
- Professional appearance
- Easiest to execute

**20% of value from 80% of effort**:
- Phases 2-3: 2-4 hours, low impact
- Historical documents rarely viewed
- Archives may be obsolete
- Can defer indefinitely

**Strategy**: Execute Phase 1 as quick win, defer rest.
─────────────────────────────────────────────────
```

---

## 🎯 Recommendation

**Execute Phase 1 only** (Active Documentation):
- ✅ 2 hours effort
- ✅ Highest impact
- ✅ Non-disruptive
- ✅ Quick win

**Defer Phase 2 & 3**:
- Wait for natural documentation updates
- Fix incrementally as files are edited
- Or during next cleanup sprint

**Outcome**:
- Active project docs clean
- Minimal time investment
- Professional appearance maintained
- Production unaffected

---

## 📝 Next Steps

### Immediate
1. Review and approve this plan
2. Decide: Phase 1 only vs comprehensive
3. Schedule execution window

### Execution (If Approved)
1. Create cleanup script
2. Test on single file
3. Run on all active docs
4. Validate results
5. Commit changes

### Future
1. Add to documentation standards
2. Consider pre-commit hook
3. Review in quarterly cleanup

---

**Plan Status**: DRAFT - Awaiting Approval
**Created**: 2026-01-21
**Owner**: Security Remediation Team
**Next Review**: 2026-01-28

---

## 🔗 Related Documents

- cortex/analysis/reports/2026-01-21-execution/FINAL_REMEDIATION_COMPLETE.md
- cortex/scripts/validate_week1_security.py
- cortex/security.py
- .claude/memories/gotchas.md
