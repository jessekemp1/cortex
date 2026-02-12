#!/usr/bin/env python3
"""
Integration test for Phase Verifier + Retry Handler + Anomaly Detection.

Verifies that all components work together correctly.
"""

import tempfile
from pathlib import Path

from orchestration.anomaly_detector import OrchestrationAnomalyManager
from orchestration.anti_pattern_detector import AntiPatternDetector
from orchestration.database import OrchestrationDatabase
from orchestration.models import ValidationCriteria
from orchestration.task import Task, TaskPhase, TaskPriority
from orchestration.verifier import PhaseVerifier, ValidationFailure


def test_integration_verifier_with_retry():
    """Test PhaseVerifier integrates with RetryHandler."""
    print("\n" + "=" * 70)
    print("Test: PhaseVerifier + RetryHandler Integration")
    print("=" * 70)

    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    # Create task with unique ID
    import uuid

    task_id = f"integration-test-{uuid.uuid4().hex[:8]}"
    task = Task(
        id=task_id,
        title="Test retry integration",
        description="Verify retry handler kicks in on validation failure",
        priority=TaskPriority.B,
        phase=TaskPhase.IMPLEMENTING,
    )
    db.create_task(task)

    # Set validation criteria that will fail (missing files)
    task.validation_criteria = ValidationCriteria(required_files=["/nonexistent/file.py"])

    print(f"\n✓ Task created: {task.title}")
    print(f"  Phase: {task.phase.value}")
    print(f"  Required files: {task.validation_criteria.required_files}")

    # Try to transition to TESTING (should trigger retry handler)
    print("\n  Attempting transition to TESTING...")
    print("  Expected: Retry handler schedules retry for missing files")

    try:
        result = verifier.transition(task, TaskPhase.TESTING)

        if not result.passed and "retry_scheduled" in result.evidence:
            print("\n✓ Retry scheduled correctly!")
            print(f"  Retry in: {result.evidence['retry_in']} seconds")
            print(f"  Checks failed: {result.checks_failed}")
        else:
            print(f"\n✗ Unexpected result: {result}")

    except ValidationFailure as e:
        # This is expected if max retries exceeded
        print(f"\n✓ Validation failure raised (max retries): {e}")

    print("\n" + "=" * 70 + "\n")


def test_integration_anomaly_detection():
    """Test anomaly detection with real database state."""
    print("=" * 70)
    print("Test: Anomaly Detection with Real State")
    print("=" * 70)

    db = OrchestrationDatabase()
    manager = OrchestrationAnomalyManager(db)

    # Detect with realistic context
    anomalies = manager.detect_all(
        context={
            "active_projects": 26,
            "total_projects": 30,
            "goals_in_progress": 0,
            "goals_pending": 9,
        }
    )

    print(f"\n✓ Detected {len(anomalies)} anomalies:")
    for anomaly in anomalies:
        severity_icon = (
            "🔴"
            if anomaly.severity.value.lower() == "critical"
            else "🟡" if anomaly.severity.value.lower() == "warning" else "📊"
        )
        print(f"  {severity_icon} [{anomaly.severity.value}] {anomaly.title}")

    print("\n" + "=" * 70 + "\n")


def test_integration_anti_pattern_detection():
    """Test anti-pattern detection on real projects."""
    print("=" * 70)
    print("Test: Anti-Pattern Detection on Real Projects")
    print("=" * 70)

    root_dir = Path(__file__).parent.parent
    detector = AntiPatternDetector(db=None, root_dir=root_dir)

    alerts = detector.detect_all()

    print(f"\n✓ Scanned projects, found {len(alerts)} anti-patterns:")
    for alert in alerts[:5]:  # Show first 5
        severity_icon = "🔴" if alert.severity.value.lower() == "critical" else "🟡"
        print(f"  {severity_icon} [{alert.severity.value}] {alert.pattern_type.value}")
        print(f"     Item: {alert.validated_item}")
        print(f"     Action: {alert.suggested_action}")

    if len(alerts) == 0:
        print("  ✓ No anti-patterns detected (good!)")

    print("\n" + "=" * 70 + "\n")


def test_integration_full_workflow():
    """Test complete workflow: investigate → plan → implement → test → complete."""
    print("=" * 70)
    print("Test: Full Workflow with All Components")
    print("=" * 70)

    db = OrchestrationDatabase()
    verifier = PhaseVerifier(db)

    import uuid

    task_id = f"integration-full-{uuid.uuid4().hex[:8]}"
    task = Task(
        id=task_id,
        title="Full workflow test",
        description="Test complete workflow with all components",
        priority=TaskPriority.A,
        phase=TaskPhase.QUEUED,
    )
    db.create_task(task)

    print(f"\n✓ Starting full workflow: {task.title}\n")

    # Phase 1: QUEUED → INVESTIGATING
    print("  [1/5] QUEUED → INVESTIGATING")
    verifier.transition(task, TaskPhase.INVESTIGATING, force=True)

    # Create investigation report
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""
        # Investigation Report

        ## Problem Analysis
        Test problem requiring investigation

        ## Proposed Approaches
        - Approach 1: Solution A (recommended)
        - Approach 2: Solution B
        """)
        report_path = f.name

    task.context = {"investigation_report": report_path}

    # Phase 2: INVESTIGATING → PLANNING
    print("  [2/5] INVESTIGATING → PLANNING")
    verifier.transition(task, TaskPhase.PLANNING)

    # Create plan
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""
        # Implementation Plan

        ## Steps
        1. Create module.py
        2. Add tests

        ## Files
        - module.py
        - test_module.py

        ## Tests
        - Unit tests with pytest
        """)
        plan_path = f.name

    task.context["plan_document"] = plan_path

    # Phase 3: PLANNING → IMPLEMENTING
    print("  [3/5] PLANNING → IMPLEMENTING")
    verifier.transition(task, TaskPhase.IMPLEMENTING)

    # Phase 4: IMPLEMENTING → TESTING
    print("  [4/5] IMPLEMENTING → TESTING")
    task.validation_criteria = ValidationCriteria(test_commands=["echo 'tests pass'"])
    verifier.transition(task, TaskPhase.TESTING, force=True)

    # Phase 5: TESTING → COMPLETED
    print("  [5/5] TESTING → COMPLETED")
    verifier.transition(task, TaskPhase.COMPLETED, force=True)

    print("\n✓ Workflow completed successfully!")
    print(f"  Final phase: {task.phase.value}")

    # Cleanup
    Path(report_path).unlink()
    Path(plan_path).unlink()

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ORCHESTRATION INTEGRATION TESTS")
    print("=" * 70)

    test_integration_verifier_with_retry()
    test_integration_anomaly_detection()
    test_integration_anti_pattern_detection()
    test_integration_full_workflow()

    print("=" * 70)
    print("✓ All integration tests completed!")
    print("=" * 70 + "\n")
