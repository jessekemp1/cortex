# Converx → Cortex Rename Plan

**Date**: December 8, 2025  
**Purpose**: Comprehensive plan to rename Converx to Cortex

---

## Overview

Rename all references from "Converx" to "Cortex" across:
- File/folder names
- Code (imports, class names, variables)
- Documentation
- CLI commands
- Entry points

---

## Scope

### Files to Rename

**Directory**:
- `converx/` → `cortex/`

**Entry Point**:
- `converx/converx` → `cortex/cortex`

**No file renames needed** (Python files keep same names, just in new directory)

### Code Changes

**Python Files**:
- `converx/cli.py` → `cortex/cli.py` (update imports, class names)
- `converx/orchestrator.py` → `cortex/orchestrator.py` (update class names)
- `converx/formatter.py` → `cortex/formatter.py` (update class names)
- `converx/feedback.py` → `cortex/feedback.py` (update class names)
- `converx/week1_automation.py` → `cortex/week1_automation.py` (update paths)
- `converx/__init__.py` → `cortex/__init__.py` (update package name)

**Shell Scripts**:
- `converx/run_week1_daily.sh` → `cortex/run_week1_daily.sh` (update paths)

**Tests**:
- `converx/tests/*.py` → `cortex/tests/*.py` (update imports)

### Documentation Changes

**All `.md` files** in `converx/`:
- Replace "Converx" with "Cortex"
- Replace "converx" with "cortex" (lowercase)
- Update code examples
- Update file paths in examples

**Key Files**:
- `README.md`
- `DESIGN_SPEC.md`
- `DOCUMENTATION_INDEX.md`
- `MIGRATION_COMPLETE.md`
- All `WEEK_1_*.md` files
- All other documentation

### Import/Reference Changes

**Class Names**:
- `ConverxOrchestrator` → `CortexOrchestrator`
- `ConverxFormatter` → `CortexFormatter`
- Any other "Converx" class names

**Variable Names**:
- `converx_dir` → `cortex_dir`
- `converx_script` → `cortex_script`
- Any other "converx" variable names

**CLI Commands**:
- `converx next` → `cortex next`
- `converx status` → `cortex status`
- `converx health` → `cortex health`
- `converx feedback` → `cortex feedback`

**Comments/Docstrings**:
- Update all references in comments
- Update all docstrings

---

## Migration Strategy

### Phase 1: Create New Structure
1. Create `cortex/` directory
2. Copy all files from `converx/` to `cortex/`
3. Rename entry point: `cortex/cortex`

### Phase 2: Update Code
1. Update all class names (Converx → Cortex)
2. Update all variable names (converx → cortex)
3. Update all imports
4. Update CLI command names
5. Update entry point script

### Phase 3: Update Documentation
1. Update all markdown files
2. Update code examples
3. Update file paths
4. Update README

### Phase 4: Update Tests
1. Update test imports
2. Update test class names
3. Update test file paths
4. Run tests to verify

### Phase 5: Cleanup
1. Archive `converx/` folder
2. Update any external references
3. Verify everything works

---

## Detailed Changes

### Class Name Changes

```python
# Before
class ConverxOrchestrator:
    pass

class ConverxFormatter:
    pass

# After
class CortexOrchestrator:
    pass

class CortexFormatter:
    pass
```

### CLI Command Changes

```python
# Before
parser = argparse.ArgumentParser(prog='converx', ...)

# After
parser = argparse.ArgumentParser(prog='cortex', ...)
```

### Import Changes

```python
# Before
from converx.cli import main
from converx.orchestrator import ConverxOrchestrator

# After
from cortex.cli import main
from cortex.orchestrator import CortexOrchestrator
```

### Documentation Changes

```markdown
# Before
# Converx - Strategic Orchestrator
python3 converx/cli.py next

# After
# Cortex - Strategic Orchestrator
python3 cortex/cli.py next
```

---

## Verification Steps

1. **Code Verification**:
   ```bash
   python3 cortex/cli.py health
   python3 cortex/cli.py next
   python3 cortex/cli.py status
   ./cortex/cortex next
   ```

2. **Test Verification**:
   ```bash
   python3 -m pytest cortex/tests/
   ```

3. **Documentation Verification**:
   - Check all `.md` files for "Converx" → "Cortex"
   - Verify code examples use new paths
   - Check README accuracy

4. **Integration Verification**:
   - Verify integrations still work (4/4 active)
   - Test week1_automation.py
   - Test run_week1_daily.sh

---

## Risk Mitigation

- **Backup**: Keep `converx/` folder until migration verified
- **Incremental**: Test after each phase
- **Rollback**: Can revert by moving files back if issues found

---

## Success Criteria

- ✅ All files in `cortex/` directory
- ✅ All class names updated (Converx → Cortex)
- ✅ All CLI commands work (`cortex next`, etc.)
- ✅ All tests passing
- ✅ All documentation updated
- ✅ No references to "Converx" in code
- ✅ Entry point script works (`./cortex/cortex`)
- ✅ Integrations still working (4/4 active)

---

## Estimated Time

- **Phase 1** (Create structure): 15 minutes
- **Phase 2** (Update code): 1-2 hours
- **Phase 3** (Update docs): 1 hour
- **Phase 4** (Update tests): 30 minutes
- **Phase 5** (Cleanup): 15 minutes

**Total**: 3-4 hours / ~60-80K tokens

---

## Notes

- Keep `converx/_archive_grok_mvp/` as-is (historical archive)
- Update any external scripts that reference `converx/`
- Consider updating project description in root README
- May need to update git history if desired (optional)

