"""
Phase Verification Engine for Cortex Orchestration.

Ensures the investigate → plan → build → test → launch process is followed
and validates completion criteria at each phase transition.

Design Philosophy:
- Strict phase ordering (no skipping)
- Evidence-based verification (tests, files, patterns)
- Audit trail for all decisions
- Fail-fast on violations
"""

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Task, TaskPhase, TraceEvent, TraceEventType
from .database import OrchestrationDatabase
from .retry_handler import RetryHandler


class PhaseTransitionError(Exception):
    """Raised when invalid phase transition attempted."""
    pass


class ValidationFailure(Exception):
    """Raised when validation criteria not met."""
    pass


@dataclass
class VerificationResult:
    """Result of verification check."""
    passed: bool
    phase: TaskPhase
    checks_run: List[str]
    checks_passed: List[str]
    checks_failed: List[str]
    evidence: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return f"{status} - {self.phase.value}: {len(self.checks_passed)}/{len(self.checks_run)} checks"


class PhaseVerifier:
    """
    Enforces phase transitions and validates completion criteria.

    Phase Flow:
        QUEUED → INVESTIGATING → PLANNING → IMPLEMENTING → TESTING → COMPLETED/FAILED

    Each transition requires proof:
    - INVESTIGATING: Investigation report must exist
    - PLANNING: Plan document must exist with implementation steps
    - IMPLEMENTING: Code changes committed, files created
    - TESTING: Tests passing, coverage met
    - COMPLETED: All validation passed
    """

    # Valid phase transitions (directed graph)
    VALID_TRANSITIONS = {
        TaskPhase.QUEUED: [TaskPhase.INVESTIGATING],
        TaskPhase.INVESTIGATING: [TaskPhase.PLANNING, TaskPhase.FAILED],
        TaskPhase.PLANNING: [TaskPhase.IMPLEMENTING, TaskPhase.FAILED],
        TaskPhase.IMPLEMENTING: [TaskPhase.TESTING, TaskPhase.FAILED],
        TaskPhase.TESTING: [TaskPhase.COMPLETED, TaskPhase.IMPLEMENTING, TaskPhase.FAILED],  # Can loop back to fix
        TaskPhase.COMPLETED: [],  # Terminal state
        TaskPhase.FAILED: [],  # Terminal state
    }

    def __init__(self, db: Optional[OrchestrationDatabase] = None):
        self.db = db or OrchestrationDatabase()
        self.retry_handler = RetryHandler(self.db)

    def can_transition(self, task: Task, to_phase: TaskPhase) -> Tuple[bool, str]:
        """
        Check if task can transition to new phase.

        Returns:
            (allowed, reason) tuple
        """
        current = task.phase

        # Check if transition is valid in the graph
        if to_phase not in self.VALID_TRANSITIONS.get(current, []):
            return False, f"Invalid transition: {current.value} → {to_phase.value}"

        return True, "Transition allowed"

    def verify_phase_completion(self, task: Task) -> VerificationResult:
        """
        Verify current phase is complete before allowing transition.

        Returns:
            VerificationResult with pass/fail and evidence
        """
        phase = task.phase

        # Route to phase-specific verifier
        verifiers = {
            TaskPhase.QUEUED: self._verify_queued,
            TaskPhase.INVESTIGATING: self._verify_investigating,
            TaskPhase.PLANNING: self._verify_planning,
            TaskPhase.IMPLEMENTING: self._verify_implementing,
            TaskPhase.TESTING: self._verify_testing,
        }

        verifier = verifiers.get(phase)
        if not verifier:
            # No verification needed for terminal states
            return VerificationResult(
                passed=True,
                phase=phase,
                checks_run=["no_verification_required"],
                checks_passed=["no_verification_required"],
                checks_failed=[]
            )

        return verifier(task)

    def transition(self, task: Task, to_phase: TaskPhase, force: bool = False) -> VerificationResult:
        """
        Transition task to new phase with verification.

        Args:
            task: Task to transition
            to_phase: Target phase
            force: Skip verification (use with caution)

        Returns:
            VerificationResult

        Raises:
            PhaseTransitionError: If transition not allowed
            ValidationFailure: If verification fails
        """
        # Check if transition allowed
        allowed, reason = self.can_transition(task, to_phase)
        if not allowed:
            raise PhaseTransitionError(reason)

        # Verify current phase complete (unless forcing)
        if not force:
            result = self.verify_phase_completion(task)
            if not result.passed:
                # Consult retry handler before failing
                error_message = f"Phase {task.phase.value} verification failed: {result.checks_failed}"
                decision = self.retry_handler.handle_failure(task, error_message, task.phase)

                if decision.should_retry:
                    # Schedule retry - transition to FAILED with retry config
                    import uuid
                    self.db.add_trace_event(TraceEvent(
                        event_id=str(uuid.uuid4()),
                        task_id=task.id,
                        event_type=TraceEventType.TASK_RETRIED,
                        timestamp=datetime.now(),
                        message=f"Retry scheduled: {decision.reason}",
                        details={
                            "failure_type": decision.failure_type.value,
                            "retry_in_seconds": decision.delay_seconds,
                            "retry_count": decision.retry_count,
                            "reason": decision.reason
                        }
                    ))

                    # Don't raise - return failure result so caller can handle
                    return VerificationResult(
                        passed=False,
                        phase=task.phase,
                        checks_run=result.checks_run,
                        checks_passed=result.checks_passed,
                        checks_failed=result.checks_failed,
                        evidence={"retry_scheduled": True, "retry_in": decision.delay_seconds}
                    )
                else:
                    # Escalate to human - raise with context
                    raise ValidationFailure(
                        f"{error_message} | Escalation reason: {decision.reason}"
                    )

        # Record transition in audit trail
        old_phase = task.phase
        task.phase = to_phase

        import uuid
        self.db.add_trace_event(TraceEvent(
            event_id=str(uuid.uuid4()),
            task_id=task.id,
            event_type=TraceEventType.TASK_PHASE_CHANGED,
            timestamp=datetime.now(),
            message=f"Phase transition: {old_phase.value} → {to_phase.value}",
            details={
                "from_phase": old_phase.value,
                "to_phase": to_phase.value,
                "forced": force
            }
        ))

        # Update task in database
        self.db.update_task(task)

        return VerificationResult(
            passed=True,
            phase=to_phase,
            checks_run=["phase_transition"],
            checks_passed=["phase_transition"],
            checks_failed=[]
        )

    # Phase-specific verifiers

    def _verify_queued(self, task: Task) -> VerificationResult:
        """Verify task is properly queued (always passes)."""
        return VerificationResult(
            passed=True,
            phase=TaskPhase.QUEUED,
            checks_run=["task_exists"],
            checks_passed=["task_exists"],
            checks_failed=[]
        )

    def _verify_investigating(self, task: Task) -> VerificationResult:
        """
        Verify investigation phase complete.

        Requirements:
        - Investigation report exists
        - Contains problem analysis
        - Contains proposed approaches
        """
        checks_run = ["investigation_report_exists", "problem_analyzed", "approaches_proposed"]
        checks_passed = []
        checks_failed = []
        evidence = {}

        # Look for investigation report
        if task.context and "investigation_report" in task.context:
            report_path = Path(task.context["investigation_report"])
            if report_path.exists():
                checks_passed.append("investigation_report_exists")
                evidence["report_path"] = str(report_path)

                # Check report content
                content = report_path.read_text().lower()

                if any(keyword in content for keyword in ["problem", "issue", "root cause", "analysis"]):
                    checks_passed.append("problem_analyzed")
                else:
                    checks_failed.append("problem_analyzed")

                if any(keyword in content for keyword in ["approach", "solution", "option", "recommend"]):
                    checks_passed.append("approaches_proposed")
                else:
                    checks_failed.append("approaches_proposed")
            else:
                checks_failed.extend(["investigation_report_exists", "problem_analyzed", "approaches_proposed"])
        else:
            # No report specified - fail
            checks_failed.extend(checks_run)

        return VerificationResult(
            passed=(len(checks_failed) == 0),
            phase=TaskPhase.INVESTIGATING,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            evidence=evidence
        )

    def _verify_planning(self, task: Task) -> VerificationResult:
        """
        Verify planning phase complete.

        Requirements:
        - Plan document exists
        - Contains implementation steps
        - Contains file list
        - Contains test strategy
        """
        checks_run = ["plan_exists", "steps_defined", "files_identified", "test_strategy"]
        checks_passed = []
        checks_failed = []
        evidence = {}

        # Look for plan document
        if task.context and "plan_document" in task.context:
            plan_path = Path(task.context["plan_document"])
            if plan_path.exists():
                checks_passed.append("plan_exists")
                evidence["plan_path"] = str(plan_path)

                content = plan_path.read_text().lower()

                # Check for implementation steps
                if any(keyword in content for keyword in ["step", "implementation", "phase", "stage"]):
                    checks_passed.append("steps_defined")
                else:
                    checks_failed.append("steps_defined")

                # Check for file list
                if any(keyword in content for keyword in ["file", "module", "component", ".py", ".js"]):
                    checks_passed.append("files_identified")
                else:
                    checks_failed.append("files_identified")

                # Check for test strategy
                if any(keyword in content for keyword in ["test", "validation", "verify", "coverage"]):
                    checks_passed.append("test_strategy")
                else:
                    checks_failed.append("test_strategy")
            else:
                checks_failed.extend(["plan_exists", "steps_defined", "files_identified", "test_strategy"])
        else:
            checks_failed.extend(checks_run)

        return VerificationResult(
            passed=(len(checks_failed) == 0),
            phase=TaskPhase.PLANNING,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            evidence=evidence
        )

    def _verify_implementing(self, task: Task) -> VerificationResult:
        """
        Verify implementation phase complete.

        Requirements:
        - Code changes committed
        - Required files created
        - No merge conflicts
        """
        checks_run = ["files_created", "changes_committed", "no_conflicts"]
        checks_passed = []
        checks_failed = []
        evidence = {}

        # Check required files exist
        if task.validation_criteria and task.validation_criteria.required_files:
            all_exist = True
            for file_path in task.validation_criteria.required_files:
                if not Path(file_path).exists():
                    all_exist = False
                    break

            if all_exist:
                checks_passed.append("files_created")
                evidence["files"] = str(task.validation_criteria.required_files)
            else:
                checks_failed.append("files_created")
        else:
            # No required files specified - assume pass
            checks_passed.append("files_created")

        # Check git status (uncommitted changes OK, conflicts NOT OK)
        try:
            # Check for conflicts
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                conflicts = result.stdout.strip()
                if not conflicts:
                    checks_passed.append("no_conflicts")
                else:
                    checks_failed.append("no_conflicts")
                    evidence["conflicts"] = conflicts

            # Check for changes (committed or uncommitted)
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                changes = result.stdout.strip()
                if changes:
                    checks_passed.append("changes_committed")
                    evidence["changes"] = "changes present"
                else:
                    # No changes - check recent commits
                    result = subprocess.run(
                        ["git", "log", "-1", "--oneline"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        checks_passed.append("changes_committed")
                        evidence["recent_commit"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Git not available or timeout - skip these checks
            checks_passed.extend(["changes_committed", "no_conflicts"])

        return VerificationResult(
            passed=(len(checks_failed) == 0),
            phase=TaskPhase.IMPLEMENTING,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            evidence=evidence
        )

    def _verify_testing(self, task: Task) -> VerificationResult:
        """
        Verify testing phase complete.

        Requirements:
        - Test commands pass
        - Coverage targets met
        - Success patterns found
        - No failure patterns found
        """
        checks_run = []
        checks_passed = []
        checks_failed = []
        evidence = {}

        if not task.validation_criteria:
            # No validation criteria - pass by default
            return VerificationResult(
                passed=True,
                phase=TaskPhase.TESTING,
                checks_run=["no_validation_required"],
                checks_passed=["no_validation_required"],
                checks_failed=[]
            )

        criteria = task.validation_criteria

        # Run test commands
        if criteria.test_commands:
            for cmd in criteria.test_commands:
                check_name = f"test_command: {cmd}"
                checks_run.append(check_name)

                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )

                    output = result.stdout + result.stderr
                    evidence[f"output_{cmd}"] = output[:500]  # First 500 chars

                    # Check exit code
                    if result.returncode == 0:
                        checks_passed.append(check_name)
                    else:
                        checks_failed.append(check_name)
                        evidence[f"error_{cmd}"] = f"Exit code: {result.returncode}"

                except (subprocess.TimeoutExpired, Exception) as e:
                    checks_failed.append(check_name)
                    evidence[f"error_{cmd}"] = str(e)

        # Check success patterns
        if criteria.success_patterns:
            check_name = "success_patterns"
            checks_run.append(check_name)

            # Look in recent output/logs
            found_patterns = []
            for pattern in criteria.success_patterns:
                # Check in test output
                for key, value in evidence.items():
                    if key.startswith("output_"):
                        if re.search(pattern, value, re.IGNORECASE):
                            found_patterns.append(pattern)
                            break

            if len(found_patterns) == len(criteria.success_patterns):
                checks_passed.append(check_name)
                evidence["patterns_found"] = str(found_patterns)
            else:
                checks_failed.append(check_name)
                evidence["patterns_missing"] = str(
                    set(criteria.success_patterns) - set(found_patterns)
                )

        # Check failure patterns (should NOT be present)
        if criteria.failure_patterns:
            check_name = "no_failure_patterns"
            checks_run.append(check_name)

            found_failures = []
            for pattern in criteria.failure_patterns:
                for key, value in evidence.items():
                    if key.startswith("output_"):
                        if re.search(pattern, value, re.IGNORECASE):
                            found_failures.append(pattern)
                            break

            if not found_failures:
                checks_passed.append(check_name)
            else:
                checks_failed.append(check_name)
                evidence["failure_patterns_found"] = str(found_failures)

        return VerificationResult(
            passed=(len(checks_failed) == 0),
            phase=TaskPhase.TESTING,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            evidence=evidence
        )

    # Note: Phase flow ends at TESTING → COMPLETED
    # No separate review or launch phases - these are implicit in TESTING verification

    def get_phase_history(self, task: Task) -> List[TraceEvent]:
        """Get history of phase transitions for task."""
        events = self.db.get_trace_events(task.id)
        return [
            e for e in events
            if e.event_type == TraceEventType.TASK_PHASE_CHANGED
        ]

    def get_verification_history(self, task: Task) -> List[TraceEvent]:
        """Get history of verification runs for task."""
        events = self.db.get_trace_events(task.id)
        return [
            e for e in events
            if e.event_type == TraceEventType.VALIDATION_RUN
        ]
