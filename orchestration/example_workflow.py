"""
Example workflow demonstrating phase enforcement with PhaseVerifier.

This shows how Cortex ensures the investigate → plan → build → test → launch
process is followed and verified at each step.

Run with: python orchestration/example_workflow.py
"""

import tempfile
from pathlib import Path

from orchestration.database import OrchestrationDatabase
from orchestration.models import ValidationCriteria
from orchestration.task import Task, TaskPhase, TaskPriority
from orchestration.verifier import PhaseTransitionError, PhaseVerifier, ValidationFailure


def example_enforce_phase_order():
    """Example: Cannot skip phases - must follow investigate → plan → implement → test → complete."""

    print("=" * 70)
    print("Example 1: Phase Enforcement - Cannot Skip Phases")
    print("=" * 70)

    # Create temp database
    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    # Create a task in QUEUED state
    task = Task(
        id="task-001",
        title="Add new feature",
        description="Implement user authentication",
        priority=TaskPriority.B,
        phase=TaskPhase.QUEUED,
    )
    db.create_task(task)

    print(f"\n✓ Task created: {task.title}")
    print(f"  Current phase: {task.phase.value}")

    # Try to skip directly to TESTING (should fail)
    print("\n✗ Attempting to skip to TESTING...")
    try:
        verifier.transition(task, TaskPhase.TESTING)
        print("  ERROR: Should have failed!")
    except PhaseTransitionError as e:
        print(f"  ✓ Correctly blocked: {e}")

    # Proper flow: QUEUED → INVESTIGATING
    print("\n✓ Transitioning QUEUED → INVESTIGATING (forced for demo)")
    result = verifier.transition(task, TaskPhase.INVESTIGATING, force=True)
    print(f"  {result}")

    print(f"\n✓ Current phase: {task.phase.value}")


def example_investigation_verification():
    """Example: Investigation phase requires report with problem analysis."""

    print("\n" + "=" * 70)
    print("Example 2: Investigation Verification - Requires Report")
    print("=" * 70)

    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    task = Task(
        id="task-002",
        title="Fix login bug",
        description="Users can't log in",
        priority=TaskPriority.A,
        phase=TaskPhase.INVESTIGATING,
    )
    db.create_task(task)

    # Try to transition without investigation report
    print("\n✗ Attempting to transition without investigation report...")
    try:
        verifier.transition(task, TaskPhase.PLANNING)
        print("  ERROR: Should have failed!")
    except ValidationFailure as e:
        print(f"  ✓ Correctly blocked: {e}")

    # Create investigation report
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""
        # Investigation Report

        ## Problem Analysis
        Root cause: Session token expiration not handled properly

        ## Proposed Approaches
        - Option 1: Refresh tokens before expiration
        - Option 2: Redirect to login on 401 (Recommended)
        """)
        report_path = f.name

    task.context = {"investigation_report": report_path}

    print(f"\n✓ Investigation report created at: {report_path}")
    print("  Verifying investigation phase...")

    result = verifier.verify_phase_completion(task)
    print(f"  {result}")
    print(f"  Checks passed: {result.checks_passed}")

    # Now transition should work
    print("\n✓ Transitioning INVESTIGATING → PLANNING")
    verifier.transition(task, TaskPhase.PLANNING, force=False)
    print(f"  Current phase: {task.phase.value}")

    # Cleanup
    Path(report_path).unlink()


def example_testing_verification():
    """Example: Testing phase runs commands and checks patterns."""

    print("\n" + "=" * 70)
    print("Example 3: Testing Verification - Run Tests & Check Patterns")
    print("=" * 70)

    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    task = Task(
        id="task-003",
        title="Implement feature",
        description="Add export functionality",
        priority=TaskPriority.B,
        phase=TaskPhase.TESTING,
    )
    db.create_task(task)

    # Set validation criteria
    task.validation_criteria = ValidationCriteria(
        test_commands=["echo 'Running tests...'; echo '✓ All tests passed'"],
        success_patterns=["tests passed", "✓"],
        failure_patterns=["FAILED", "ERROR"],
    )

    print("\n✓ Task in TESTING phase")
    print(f"  Test commands: {task.validation_criteria.test_commands}")
    print(f"  Success patterns: {task.validation_criteria.success_patterns}")
    print(f"  Failure patterns: {task.validation_criteria.failure_patterns}")

    print("\n  Running verification...")
    result = verifier.verify_phase_completion(task)

    print(f"\n  {result}")
    print(f"  Checks run: {result.checks_run}")
    print(f"  Checks passed: {result.checks_passed}")
    print(f"  Checks failed: {result.checks_failed}")

    if result.passed:
        print("\n✓ All tests passed! Transitioning to COMPLETED")
        verifier.transition(task, TaskPhase.COMPLETED)
        print(f"  Final phase: {task.phase.value}")


def example_full_workflow():
    """Example: Complete workflow from QUEUED to COMPLETED."""

    print("\n" + "=" * 70)
    print("Example 4: Full Workflow - QUEUED → COMPLETED")
    print("=" * 70)

    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    task = Task(
        id="task-004",
        title="Add search feature",
        description="Implement full-text search",
        priority=TaskPriority.B,
        phase=TaskPhase.QUEUED,
    )
    db.create_task(task)

    print(f"\n✓ Starting task: {task.title}")
    print(f"  Initial phase: {task.phase.value}\n")

    # Phase 1: QUEUED → INVESTIGATING
    print("  [1/5] QUEUED → INVESTIGATING")
    verifier.transition(task, TaskPhase.INVESTIGATING, force=True)

    # Phase 2: INVESTIGATING → PLANNING
    print("  [2/5] INVESTIGATING → PLANNING")
    verifier.transition(task, TaskPhase.PLANNING, force=True)

    # Phase 3: PLANNING → IMPLEMENTING
    print("  [3/5] PLANNING → IMPLEMENTING")
    verifier.transition(task, TaskPhase.IMPLEMENTING, force=True)

    # Phase 4: IMPLEMENTING → TESTING
    print("  [4/5] IMPLEMENTING → TESTING")
    task.validation_criteria = ValidationCriteria(test_commands=["echo 'tests pass'"])
    verifier.transition(task, TaskPhase.TESTING, force=True)

    # Phase 5: TESTING → COMPLETED
    print("  [5/5] TESTING → COMPLETED")
    verifier.transition(task, TaskPhase.COMPLETED, force=True)

    print("\n✓ Workflow complete!")
    print(f"  Final phase: {task.phase.value}")

    # Show audit trail
    phase_history = verifier.get_phase_history(task)
    print(f"\n  Audit trail ({len(phase_history)} transitions):")
    for i, event in enumerate(phase_history, 1):
        from_phase = event.details.get("from_phase", "?")
        to_phase = event.details.get("to_phase", "?")
        print(f"    {i}. {from_phase} → {to_phase}")


if __name__ == "__main__":
    example_enforce_phase_order()
    example_investigation_verification()
    example_testing_verification()
    example_full_workflow()

    print("\n" + "=" * 70)
    print("✓ All examples completed successfully!")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("1. Phases must be followed in order (no skipping)")
    print("2. Each phase has verification requirements")
    print("3. Investigation requires report with problem analysis")
    print("4. Testing runs commands and checks success/failure patterns")
    print("5. Full audit trail is maintained for all transitions")
    print("=" * 70)
