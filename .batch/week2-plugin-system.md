# Week 2: Plugin System - Batch Implementation Spec

**Job Type:** Comprehensive implementation
**Timeline:** Complete 7-day plan in single batch execution
**Cost Savings:** 50% vs interactive implementation
**Priority:** Normal (can run overnight)

---

## 🎯 Objective

Build complete plugin system for Cortex following the Week 2 plan in `Docs/week2-plugin-system-plan.md`.

**Critical Requirements:**
1. ✅ All code must be tested (Python scripts AND user-facing commands)
2. ✅ Follow TESTING_CHECKLIST.md requirements
3. ✅ Test actual /plugin commands, not just Python modules
4. ✅ Verify end-to-end user workflows

---

## 📋 Implementation Tasks

### Day 1: Foundation
**Files to Create:**
- `cortex/plugins/__init__.py`
- `cortex/plugins/base.py` (BasePlugin class)
- `cortex/plugins/loader.py` (PluginLoader with auto-discovery)
- `cortex/plugins/registry.py` (PluginRegistry for metadata)
- `tests/test_plugin_loader.py`
- `Docs/PLUGIN_FORMAT.md`

**Tests Required:**
- ✅ BasePlugin can be subclassed
- ✅ PluginLoader discovers plugins correctly
- ✅ PluginLoader loads valid plugins
- ✅ PluginLoader skips invalid plugins with grace
- ✅ PLUGIN.md frontmatter parsed correctly

---

### Day 2: Template & First Plugin (Status)
**Files to Create:**
- `cortex/plugins/_template/PLUGIN.md.template`
- `cortex/plugins/_template/plugin.py.template`
- `cortex/plugins/_template/tests/test_template.py`
- `cortex/plugins/status/PLUGIN.md`
- `cortex/plugins/status/plugin.py`
- `cortex/plugins/status/tests/test_status.py`
- `Docs/PLUGIN_DEVELOPMENT.md`

**Tests Required:**
- ✅ Template can be copied & modified
- ✅ Status plugin loads from loader
- ✅ Status plugin executes successfully
- ✅ `/status` command works (NOT just Python script)
- ✅ Status plugin help displays PLUGIN.md content

---

### Day 3: Core Plugins (Briefing, Next)
**Files to Create:**
- `cortex/plugins/briefing/PLUGIN.md`
- `cortex/plugins/briefing/plugin.py`
- `cortex/plugins/briefing/tests/test_briefing.py`
- `cortex/plugins/next/PLUGIN.md`
- `cortex/plugins/next/plugin.py`
- `cortex/plugins/next/tests/test_next.py`

**Tests Required:**
- ✅ Both plugins load successfully
- ✅ Original functionality preserved
- ✅ `/briefing` and `/next` commands work
- ✅ No regressions from original implementation

---

### Day 4: Core Plugins (Test, Commit)
**Files to Create:**
- `cortex/plugins/test/PLUGIN.md`
- `cortex/plugins/test/plugin.py`
- `cortex/plugins/test/tests/test_test.py`
- `cortex/plugins/commit/PLUGIN.md`
- `cortex/plugins/commit/plugin.py`
- `cortex/plugins/commit/tests/test_commit.py`

**Tests Required:**
- ✅ All 5 plugins load and execute
- ✅ `/test` and `/commit` commands work
- ✅ Integration tests pass
- ✅ Performance benchmark (no regression)

---

### Day 5: CLI Integration
**Files to Create:**
- `cortex/plugins/cli.py` (Plugin CLI commands)
- `cortex/plugins/commands.py` (Command handlers)
- `tests/test_plugin_cli.py`

**Tests Required:**
- ✅ `/plugin list` shows all plugins
- ✅ `/plugin info <name>` displays metadata
- ✅ `/plugin enable <name>` works
- ✅ `/plugin disable <name>` persists
- ✅ `/plugin install <path>` can load external plugin

---

### Day 6: Documentation
**Files to Create:**
- `Docs/PLUGIN_DEVELOPMENT.md` (complete guide)
- `Docs/PLUGIN_TUTORIAL.md` (step-by-step)
- `Docs/PLUGIN_MIGRATION.md` (for remaining 49 commands)
- `cortex/plugins/_examples/hello/` (example plugin)
- `cortex/plugins/_examples/simple_monitor/` (example)

**Tests Required:**
- ✅ Example plugins load and execute
- ✅ Tutorial can be followed successfully
- ✅ New plugin can be created in <15 minutes

---

### Day 7: Polish & Integration Testing
**Files to Create:**
- `tests/integration/test_plugin_system.py`
- `tests/e2e/test_plugin_workflow.py`
- `Docs/week2-implementation-complete.md`
- `TESTING_CHECKLIST.md` (if doesn't exist)

**Tests Required:**
- ✅ All unit tests pass (>90% coverage)
- ✅ All integration tests pass
- ✅ End-to-end workflow tests pass
- ✅ User-facing commands tested (NOT just Python)
- ✅ TESTING_CHECKLIST.md completed

---

## 🧪 Critical Testing Requirements

### MUST Test User-Facing Interface
**Anti-Pattern to Avoid:** "Python script works ≠ /command works"

**Required Tests:**
```bash
# Test actual commands, not just Python modules
/plugin list                    # MUST work
/plugin info status             # MUST display metadata
/status                         # MUST execute via plugin system
/status --help                  # MUST show plugin help
/briefing                       # MUST work through plugins
/next                           # MUST work through plugins
/test                           # MUST work through plugins
/commit                         # MUST work through plugins

# Test plugin lifecycle
/plugin disable briefing        # MUST disable
/briefing                       # MUST fail gracefully
/plugin enable briefing         # MUST re-enable
/briefing                       # MUST work again

# Test external plugin
/plugin install /path/to/example  # MUST load
/example                        # MUST execute
```

### Integration Test Checklist
- [ ] Plugin loader discovers all 5 plugins
- [ ] All 5 plugins load without errors
- [ ] All 5 plugins execute successfully
- [ ] Plugin CLI commands work (/plugin list, info, enable, disable)
- [ ] Plugin help system works
- [ ] Plugin dependencies checked
- [ ] Plugin enable/disable persists
- [ ] External plugins can be installed
- [ ] Example plugins work
- [ ] No regressions from original commands
- [ ] Performance acceptable (<100ms overhead)

---

## 📊 Success Criteria

### Code Quality
- ✅ All files follow Python style guidelines
- ✅ Type hints on all public methods
- ✅ Docstrings for all classes/methods
- ✅ Error handling comprehensive
- ✅ Logging for debugging

### Testing
- ✅ Unit test coverage >90%
- ✅ All integration tests pass
- ✅ User-facing commands tested
- ✅ No regressions detected
- ✅ Performance benchmarks acceptable

### Documentation
- ✅ PLUGIN_FORMAT.md complete
- ✅ PLUGIN_DEVELOPMENT.md comprehensive
- ✅ PLUGIN_TUTORIAL.md step-by-step
- ✅ PLUGIN_MIGRATION.md actionable
- ✅ All plugins have complete PLUGIN.md

### Deliverables
- ✅ 1,800 lines of production code
- ✅ 5 working plugins (status, briefing, next, test, commit)
- ✅ Plugin system core (loader, registry, CLI)
- ✅ Template for new plugins
- ✅ 2 example plugins
- ✅ 4 documentation guides
- ✅ Complete test suite

---

## 🚨 Critical Reminders

### From CLAUDE.md
1. **"Tested code but not interface"** - NEVER claim "ready" without testing actual /commands
2. **TESTING_CHECKLIST.md** - Complete ALL items before claiming "ready"
3. **No orphaned code** - If plugin validates, wire it to CLI
4. **Circular imports** - Import inside functions if needed

### Validation Requirements
Before completion, verify:
1. ✅ All /plugin commands work
2. ✅ All 5 converted plugins work via /command
3. ✅ Example from tutorial runs successfully
4. ✅ External plugin can be installed & executed
5. ✅ TESTING_CHECKLIST.md fully completed

---

## 📦 Batch Job Configuration

**Input Files:**
- `Docs/week2-plugin-system-plan.md` (design spec)
- `CLAUDE.md` (anti-patterns, gotchas)
- Existing slash command implementations (for conversion)

**Output Files:**
- Complete plugin system (1,800 lines)
- Test suite (>90% coverage)
- Documentation (4 guides)
- Implementation summary

**Estimated Token Usage:** ~100K tokens (design complete, clear requirements)

**Priority:** Normal (can run overnight)

**Timeout:** 6 hours (maximum)

---

## ✅ Completion Checklist

Before marking batch job complete:
- [ ] All 5 plugins created and documented
- [ ] Plugin loader auto-discovers plugins
- [ ] Plugin CLI commands implemented (/plugin list, info, enable, disable, install)
- [ ] All plugins tested via actual /commands (not just Python)
- [ ] Template plugin created and documented
- [ ] 2 example plugins working
- [ ] All documentation complete
- [ ] TESTING_CHECKLIST.md completed
- [ ] week2-implementation-complete.md created
- [ ] No anti-patterns violated
- [ ] Ready for production use

---

## 🎯 Expected Outcome

**User Experience After Batch Job:**
```bash
$ /plugin list
Available Plugins (5):
  ✓ status     - Comprehensive project status
  ✓ briefing   - Morning briefing with recommendations
  ✓ next       - Next action recommendations
  ✓ test       - Smart test execution
  ✓ commit     - Intelligent git commit

$ /plugin info status
Plugin: status (v1.0.0)
Description: Show comprehensive project status with Cortex intelligence
Author: Jesse Kemp
Status: ✓ Enabled
Dependencies: ✓ All satisfied

$ /status
📊 Cortex Portfolio Status
[... full status output ...]

$ /plugin disable briefing
✓ Plugin 'briefing' disabled

$ /briefing
✗ Plugin 'briefing' is disabled. Enable with: /plugin enable briefing
```

**Developer Experience:**
```bash
$ cp -r cortex/plugins/_template cortex/plugins/my_feature
$ vim cortex/plugins/my_feature/PLUGIN.md
$ vim cortex/plugins/my_feature/plugin.py
# Plugin auto-discovered and loaded
$ /my_feature
[... plugin executes ...]
```

---

**Ready for batch submission:** ✅
**Cost savings:** 50% vs interactive
**Timeline:** Overnight completion
**Confidence:** HIGH (90%) - Clear spec, proven patterns
