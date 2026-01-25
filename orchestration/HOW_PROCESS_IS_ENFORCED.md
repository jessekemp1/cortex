# How Cortex Ensures: investigate → plan → build → test → launch

**Status:** ✅ IMPLEMENTED & VERIFIED
**Component:** Phase Verification Engine (`orchestration/verifier.py`)
**Last Updated:** 2026-01-25

---

## Overview

Cortex enforces a strict workflow process to ensure quality and proper validation at each step. The `PhaseVerifier` component acts as a gatekeeper, preventing tasks from skipping critical phases and ensuring each phase meets its completion criteria before moving forward.

`★ Insight ─────────────────────────────────────`
**Why enforce phases?** Without enforcement, it's easy to skip investigation (leading to wrong solutions), skip planning (leading to rework), skip testing (leading to broken code), or deploy without verification. The PhaseVerifier makes this impossible - every task must prove it completed each phase before advancing.
`─────────────────────────────────────────────────`

---

## The Workflow

```
QUEUED → INVESTIGATING → PLANNING → IMPLEMENTING → TESTING → COMPLETED
                                                         ↓
                                                      FAILED
```

### Phase Transitions (State Machine)

| From Phase     | Can Transition To           | Why                                    |
|----------------|-----------------------------|----------------------------------------|
| QUEUED         | INVESTIGATING               | Start work                             |
| INVESTIGATING  | PLANNING, FAILED            | Analysis done or investigation failed  |
| PLANNING       | IMPLEMENTING, FAILED        | Plan approved or planning failed       |
| IMPLEMENTING   | TESTING, FAILED             | Code written or implementation failed  |
| TESTING        | COMPLETED, IMPLEMENTING, FAILED | Tests passed, need fixes, or failed |
| COMPLETED      | (terminal)                  | Done                                   |
| FAILED         | (terminal)                  | Stopped                                |

**Key Rule:** You cannot skip phases. QUEUED cannot go directly to TESTING.

---

## How Verification Works

### 1. Phase Transition Request

```python
from orchestration.verifier import PhaseVerifier
from orchestration.task import Task, TaskPhase

verifier = PhaseVerifier()
result = verifier.transition(task, TaskPhase.PLANNING)
# Automatically verifies current phase before transitioning
```

### 2. Verification Checks

Each phase has specific requirements that must be met:

#### QUEUED Phase
**Requirements:** None (entry point)

#### INVESTIGATING Phase
**Requirements:**
- ✓ Investigation report exists (`task.context['investigation_report']`)
- ✓ Report contains problem analysis keywords: `problem`, `issue`, `root cause`, `analysis`
- ✓ Report contains proposed approaches: `approach`, `solution`, `option`, `recommend`

**Example:**
```markdown
# Investigation Report

## Problem Analysis
The root cause is X breaking when Y happens.

## Proposed Approaches
- Option 1: Fix X to handle Y
- Option 2: Prevent Y from happening (Recommended)
```

#### PLANNING Phase
**Requirements:**
- ✓ Plan document exists (`task.context['plan_document']`)
- ✓ Contains implementation steps: `step`, `implementation`, `phase`, `stage`
- ✓ Contains file list: `file`, `module`, `component`, `.py`, `.js`
- ✓ Contains test strategy: `test`, `validation`, `verify`, `coverage`

**Example:**
```markdown
# Implementation Plan

## Steps
1. Create models.py with Task dataclass
2. Implement phase verification logic
3. Add transition validation

## Files
- orchestration/models.py (create)
- orchestration/verifier.py (create)

## Test Strategy
- Unit tests for each phase verifier
- Integration test for full workflow
- Coverage target: 90%
```

#### IMPLEMENTING Phase
**Requirements:**
- ✓ Required files created (`task.validation_criteria.required_files`)
- ✓ Git changes committed or present
- ✓ No merge conflicts

**Example:**
```python
task.validation_criteria = ValidationCriteria(
    required_files=[
        "/path/to/models.py",
        "/path/to/verifier.py"
    ]
)
```

#### TESTING Phase
**Requirements:**
- ✓ Test commands execute successfully
- ✓ Success patterns found in output
- ✓ NO failure patterns found in output
- ✓ Coverage targets met (if specified)

**Example:**
```python
task.validation_criteria = ValidationCriteria(
    test_commands=[
        "pytest orchestration/test_verifier.py -v",
        "pytest orchestration/test_models.py -v"
    ],
    success_patterns=["passed", "100%"],
    failure_patterns=["FAILED", "ERROR", "AssertionError"],
    min_coverage_percent=90.0
)
```

---

## Enforcement Mechanisms

### 1. **Transition Validation (Compile-Time Guard)**

```python
# This will FAIL at runtime
verifier.transition(task, TaskPhase.TESTING)  # From QUEUED
# PhaseTransitionError: Invalid transition: queued → testing
```

The verifier checks the VALID_TRANSITIONS graph before allowing any transition.

### 2. **Verification Validation (Evidence-Based Guard)**

```python
# This will FAIL if no investigation report
verifier.transition(task, TaskPhase.PLANNING)  # From INVESTIGATING
# ValidationFailure: Phase investigating verification failed: ['investigation_report_exists']
```

The verifier runs phase-specific checks and requires evidence.

### 3. **Audit Trail (Accountability Guard)**

```python
# Every transition is recorded
phase_history = verifier.get_phase_history(task)
for event in phase_history:
    print(f"{event.details['from_phase']} → {event.details['to_phase']}")
```

Every transition creates a `TraceEvent` in the database with:
- Timestamp
- From/to phase
- Whether it was forced
- Who made the transition (if applicable)

---

## Force Override (Emergency Escape Hatch)

For development/testing, you can force transitions:

```python
verifier.transition(task, TaskPhase.TESTING, force=True)
```

**⚠️ WARNING:** Force should ONLY be used for:
- Development/testing
- Emergency situations with explicit approval
- Migrating existing tasks into the system

**Force is recorded in audit trail** - you can see when rules were bypassed.

---

## Loop-Back for Fixes

Testing can loop back to Implementation for fixes:

```
TESTING (tests fail) → IMPLEMENTING (fix code) → TESTING (retest) → COMPLETED
```

This is the only allowed loop in the workflow, enabling iterative development while maintaining phase integrity.

---

## Real-World Example

```python
from orchestration.verifier import PhaseVerifier
from orchestration.task import Task, TaskPhase, TaskPriority
from orchestration.models import ValidationCriteria
from pathlib import Path

# Create task
task = Task(
    id="feature-auth",
    title="Add user authentication",
    description="Implement JWT-based auth",
    priority=TaskPriority.B,
    phase=TaskPhase.QUEUED
)

verifier = PhaseVerifier()

# 1. QUEUED → INVESTIGATING (start work)
verifier.transition(task, TaskPhase.INVESTIGATING, force=True)

# 2. Do investigation, create report
Path("investigation.md").write_text("""
# Investigation: Auth System

## Problem
Need secure authentication for API.

## Approaches
- Option 1: JWT tokens (recommended)
- Option 2: Session-based
""")
task.context = {"investigation_report": "investigation.md"}

# 3. INVESTIGATING → PLANNING (verified automatically)
verifier.transition(task, TaskPhase.PLANNING)  # Passes verification

# 4. Create plan
Path("plan.md").write_text("""
# Auth Implementation Plan

## Steps
1. Create User model
2. Implement JWT generation
3. Add middleware

## Files
- models/user.py
- auth/jwt.py
- middleware/auth.py

## Tests
- Unit tests for JWT
- Integration tests for protected routes
""")
task.context["plan_document"] = "plan.md"

# 5. PLANNING → IMPLEMENTING (verified)
verifier.transition(task, TaskPhase.IMPLEMENTING)

# 6. Implement code
Path("models/user.py").write_text("# User model")
Path("auth/jwt.py").write_text("# JWT logic")
task.validation_criteria = ValidationCriteria(
    required_files=["models/user.py", "auth/jwt.py"]
)

# 7. IMPLEMENTING → TESTING (files verified)
verifier.transition(task, TaskPhase.TESTING)

# 8. Run tests
task.validation_criteria.test_commands = ["pytest tests/auth/ -v"]
task.validation_criteria.success_patterns = ["passed"]

# 9. TESTING → COMPLETED (tests verified)
result = verifier.verify_phase_completion(task)
if result.passed:
    verifier.transition(task, TaskPhase.COMPLETED)
```

---

## Integration with Cortex Intelligence

The PhaseVerifier integrates with:

### 1. **Orchestration Database**
- All tasks stored with current phase
- Phase history tracked in `trace_events` table
- Query by phase: `SELECT * FROM tasks WHERE phase = 'testing'`

### 2. **Batch Optimizer**
- Only queues tasks in QUEUED or FAILED phases
- Skips tasks already in progress

### 3. **Dashboard**
- Shows task distribution by phase
- Highlights stuck tasks (phase unchanged for > 24 hours)
- Alerts on validation failures

### 4. **CLI Status**
- Reports: "3 tasks stuck in INVESTIGATING (>48h)"
- Suggests: "Review investigation reports for task-001, task-002, task-003"

---

## Benefits

### ✅ **Quality Assurance**
- Every task is investigated before coding
- Every implementation is tested before deployment
- No "cowboy coding" - process is enforced

### ✅ **Audit Trail**
- Full history of what happened and when
- Can debug: "Why was this task marked complete without tests?"
- Answer: Check trace_events - was it forced?

### ✅ **Predictability**
- Know exactly where each task is in the workflow
- Estimate completion based on phase
- Bottleneck detection (e.g., "10 tasks stuck in TESTING")

### ✅ **Learning**
- Track: How long does each phase take?
- Pattern: Tasks in INVESTIGATING average 2 hours
- Improve: Provide better investigation templates

---

## Running the Demo

```bash
# See it in action
python -m orchestration.example_workflow

# Expected output:
# ✓ Cannot skip phases (enforced)
# ✓ Investigation requires report (verified)
# ✓ Testing runs commands and checks patterns (verified)
# ✓ Full workflow maintains audit trail
```

---

## Summary

| Question | Answer |
|----------|--------|
| **How is process enforced?** | `PhaseVerifier` blocks invalid transitions |
| **How is verification done?** | Each phase has requirements checked before transition |
| **What if requirements not met?** | `ValidationFailure` exception, transition blocked |
| **Can it be bypassed?** | Only with `force=True` (recorded in audit trail) |
| **What's the audit trail?** | Every transition logged with timestamp, from/to phase, forced flag |
| **Can tasks loop back?** | Yes, TESTING → IMPLEMENTING → TESTING (for fixes) |

---

**Bottom Line:** The investigate → plan → build → test → launch process is not a suggestion - it's enforced by code with evidence-based verification at each step.
