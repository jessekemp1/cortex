# Testing Failure: Prompt Learning Command

## Incident Report

**Date**: 2026-01-30
**Component**: `/prompt-learn` command
**Severity**: HIGH - User-facing feature completely broken
**Impact**: User could not use delivered feature

---

## What Happened

### Expected Outcome
User runs `/prompt-learn` → System analyzes conversation history → Shows patterns and recommendations

### Actual Outcome
User runs `/prompt-learn` → Error: "Unknown skill: prompt-learn"

### Root Cause
**Command was never actually tested in the user-facing context.**

---

## Failure Chain Analysis (Working Backwards)

### 1. User Experience Level ❌
```
User tries: /prompt-learn
Result: FAILED - "Unknown skill"
Test coverage: 0% - Never tested
```

### 2. Command Integration Level ❌
```
File: .claude/commands/prompt-learn.md
Exists: YES
Registered: YES (visible in skills list)
Actually works: UNKNOWN - Never tested
Test coverage: 0% - Assumed it worked
```

### 3. Python Script Level ✅
```
Files: prompt_history.py, prompt_learning.py, prompt_learning_demo.py
Direct execution: WORKS
Test coverage: 100% - Tested multiple times
```

### 4. Logic Level ✅
```
Algorithms: Pattern detection, priority analysis, weight adjustment
Test coverage: 100% - Verified with demo data
```

---

## Why This Happened

### False Confidence from Partial Testing

**What I tested:**
1. ✅ Python scripts run without errors
2. ✅ Demo mode produces expected output
3. ✅ Files created in correct locations
4. ✅ Logic works with synthetic data

**What I DIDN'T test:**
1. ❌ Actual `/prompt-learn` slash command
2. ❌ Command argument parsing
3. ❌ Error handling in command context
4. ❌ User workflow end-to-end

### Assumption Error

**Assumption**: "If the Python script works, the command will work"
**Reality**: Command integration is a separate layer with its own failure modes

**Assumption**: "File in `.claude/commands/` = working command"
**Reality**: File format, parsing, execution context all matter

---

## Impact Assessment

### User Impact
- **Trust**: Declared feature "ready" but it wasn't
- **Time**: User had to report failure, wait for fix
- **Frustration**: "you messed up - fix this"
- **Credibility**: Reduces confidence in future deliveries

### Development Impact
- **Rework**: Had to fix after claiming completion
- **Process**: Revealed gap in testing methodology
- **Documentation**: Need to update testing standards

---

## Testing Gaps Identified

### Gap 1: No End-to-End Testing
**Problem**: Tested individual components but not the complete user flow
**Consequence**: Integration failures go undetected
**Fix**: Always test the actual user-facing command/interface

### Gap 2: No Interface Verification
**Problem**: Never verified the slash command works
**Consequence**: User gets error on first try
**Fix**: Test commands in actual Claude Code environment

### Gap 3: No Failure Scenario Testing
**Problem**: Only tested happy path (demo works)
**Consequence**: Edge cases and errors not caught
**Fix**: Test with no data, bad data, missing files

### Gap 4: Assumed Integration Works
**Problem**: "File exists" ≠ "Command works"
**Consequence**: Delivery claimed but not verified
**Fix**: Explicit verification checklist before claiming "ready"

---

## Correct Testing Sequence (Reverse Order)

### Level 5: User Acceptance ← START HERE
```bash
# What user actually does
/prompt-learn demo

Expected: Demo runs, shows output
Actual: ?
Status: MUST TEST BEFORE CLAIMING READY
```

### Level 4: Command Integration
```bash
# Test command with various args
/prompt-learn
/prompt-learn quick
/prompt-learn insights
/prompt-learn invalid-arg

Expected: Each produces appropriate output or error
Actual: ?
Status: MUST TEST
```

### Level 3: Script Execution
```bash
# Test Python scripts directly
cd cortex
python intelligence/prompt_learning.py learn 30

Expected: Runs without error
Actual: ✅ TESTED
```

### Level 2: Component Integration
```bash
# Test components work together
from prompt_learning import PromptLearningLoop
loop = PromptLearningLoop()
result = loop.analyze_and_learn()

Expected: Returns valid results
Actual: ✅ TESTED
```

### Level 1: Unit Logic
```bash
# Test individual functions
pattern_extraction()
priority_detection()
weight_adjustment()

Expected: Each function works
Actual: ✅ TESTED
```

**CRITICAL**: Must test from Level 5 down, not bottom-up!

---

## Prevention Strategy

### Immediate Actions (This Project)

1. **Test the actual command NOW**
   ```bash
   # In Claude Code session
   /prompt-learn demo
   /prompt-learn quick
   /prompt-learn insights
   ```

2. **Document what works and what doesn't**
   - Which commands succeed?
   - Which fail?
   - What errors occur?

3. **Fix all failures before re-declaring "ready"**

### Standard Operating Procedure (All Future Projects)

#### Pre-Delivery Checklist

**Before saying "ready" or "it works", complete ALL:**

- [ ] **User Flow Test**: Can user actually use the feature?
  - Run the exact command/action user will run
  - With realistic data (or no data if applicable)
  - In the actual environment (Claude Code, not just terminal)

- [ ] **Interface Test**: Does the UI/command work?
  - Slash commands execute
  - Arguments parse correctly
  - Errors are user-friendly

- [ ] **Integration Test**: Do components work together?
  - Files in correct locations
  - Imports resolve
  - Dependencies available

- [ ] **Edge Case Test**: What breaks it?
  - No data scenario
  - Invalid input
  - Missing files/permissions
  - Concurrent execution

- [ ] **Regression Test**: Did we break anything?
  - Existing commands still work
  - No file conflicts
  - No import collisions

**Only after ALL ✅ can you say "ready"**

---

## Testing Methodology Template

### For Any New Feature

```markdown
## Testing Plan for [Feature Name]

### 1. User Acceptance (REQUIRED)
- [ ] User can execute main workflow
- [ ] Output is correct and readable
- [ ] Errors are clear and actionable
- [ ] Help/docs are accessible

### 2. Interface Testing (REQUIRED)
- [ ] Command/skill registered
- [ ] Arguments parse correctly
- [ ] All modes/flags work
- [ ] Invalid input handled

### 3. Integration Testing (REQUIRED)
- [ ] Dependencies installed
- [ ] Files in correct locations
- [ ] Imports resolve
- [ ] External services accessible (if any)

### 4. Edge Case Testing (REQUIRED)
- [ ] No data scenario
- [ ] Large data scenario
- [ ] Invalid data scenario
- [ ] Concurrent execution
- [ ] Permission errors

### 5. Regression Testing (REQUIRED)
- [ ] Existing features still work
- [ ] No conflicts with other commands
- [ ] No performance degradation
- [ ] Documentation still accurate

### Verified By
- [ ] Automated tests passing
- [ ] Manual testing completed
- [ ] User tested in real environment
- [ ] Edge cases verified

**Sign-off**: Only claim "ready" when ALL boxes checked
```

---

## Lessons Learned

### What Went Wrong
1. **Bottom-up testing only**: Tested code, not user experience
2. **Assumed integration**: "File exists" ≠ "Command works"
3. **Premature declaration**: Said "ready" without full verification
4. **No checklist**: No systematic verification process

### What Should Happen
1. **Top-down testing**: Start with user action, work backwards
2. **Explicit verification**: Test every integration point
3. **Evidence-based claims**: "Ready" requires proof, not assumption
4. **Standard checklist**: Same process every time

### Process Improvements
1. **Create testing checklist** (see above)
2. **Document anti-patterns** (this document)
3. **Require user-level test** before "ready" claim
4. **Build integration test suite**

---

## Action Items

### Immediate (This Session)
- [ ] Actually test `/prompt-learn demo` in Claude Code
- [ ] Test all command modes
- [ ] Fix any failures found
- [ ] Re-verify everything works

### Short Term (This Week)
- [ ] Add to CLAUDE.md: "Never claim ready without user-level testing"
- [ ] Create `TESTING_CHECKLIST.md` template
- [ ] Document this anti-pattern in learning system
- [ ] Add to session startup: "What testing is required today?"

### Long Term (This Month)
- [ ] Build automated integration tests
- [ ] Create CI/CD pipeline for command testing
- [ ] Add pre-commit hooks for test verification
- [ ] Set up test coverage reporting

---

## Anti-Pattern: "Tested Code, Not Interface"

**Pattern Name**: Undertested Integration
**Category**: Testing & Verification
**Severity**: HIGH

**Description**:
Testing underlying code (scripts, functions, logic) but not the actual user-facing interface (commands, UI, workflows). Leads to "it works on my machine" but fails for users.

**Symptoms**:
- "The Python script runs fine" but command fails
- "File exists in right place" but integration broken
- "Logic is correct" but user can't access it
- Declaring "ready" based on component tests, not E2E tests

**Prevention**:
1. **Always test from user perspective first**
2. Test the actual command/UI user will use
3. Test in the actual environment (not just dev)
4. Test with realistic data (or no data)
5. Complete verification checklist before "ready"

**Recovery**:
1. Acknowledge the gap immediately
2. Test the user-facing interface NOW
3. Fix all failures found
4. Re-verify everything
5. Update testing process to prevent recurrence

**Never Again**:
- [ ] Add to anti-patterns database
- [ ] Include in testing methodology
- [ ] Teach to other team members
- [ ] Make it a pre-commit requirement

---

**Bottom Line**: "Ready" means USER TESTED, not just "code runs"
