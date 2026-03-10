"""
Workflow runner — executes YAML-defined workflows step by step.

Handles:
- Sequential step execution with condition gating
- Context threading (one step's output → next step's prompt context)
- Shell execution via subprocess
- AI execution via supervisor dispatch (or stub for standalone use)
- Retry logic and failure handling
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortex.workflows.schema import OnFailure, Step, StepType, Workflow

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    step_id: str
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    duration_seconds: float = 0.0
    model_used: Optional[str] = None
    tokens_used: int = 0


@dataclass
class WorkflowResult:
    """Result of executing an entire workflow."""

    workflow_name: str
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_duration_seconds: float = 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        passed = sum(1 for s in self.steps if s.success)
        failed = sum(1 for s in self.steps if not s.success)
        status = "PASSED" if self.success else "FAILED"
        lines = [
            f"Workflow: {self.workflow_name} — {status}",
            f"Steps: {passed} passed, {failed} failed ({self.total_duration_seconds:.1f}s total)",
        ]
        for sr in self.steps:
            icon = "✓" if sr.success else "✗"
            lines.append(f"  {icon} {sr.step_id} ({sr.duration_seconds:.1f}s)")
            if sr.error:
                lines.append(f"    Error: {sr.error[:200]}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "workflow_name": self.workflow_name,
            "success": self.success,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
            "steps": [
                {
                    "step_id": s.step_id,
                    "success": s.success,
                    "output": s.output[:2000],
                    "error": s.error[:500],
                    "exit_code": s.exit_code,
                    "duration_seconds": s.duration_seconds,
                    "model_used": s.model_used,
                    "tokens_used": s.tokens_used,
                }
                for s in self.steps
            ],
        }


class WorkflowRunner:
    """Execute a Workflow definition step by step."""

    def __init__(
        self,
        workflow: Workflow,
        working_dir: Optional[Path] = None,
        ai_dispatcher: Optional[Any] = None,
        dry_run: bool = False,
    ):
        self.workflow = workflow
        self.working_dir = working_dir or Path.home() / "Dev"
        self.ai_dispatcher = ai_dispatcher
        self.dry_run = dry_run
        self._results: Dict[str, StepResult] = {}

    def run(self) -> WorkflowResult:
        """Execute all steps in sequence, respecting conditions and flow control."""
        started = datetime.now(timezone.utc)
        workflow_result = WorkflowResult(
            workflow_name=self.workflow.name,
            success=True,
            started_at=started.isoformat(),
        )

        for step in self.workflow.steps:
            # Evaluate condition
            if step.condition and not self._evaluate_condition(step.condition):
                logger.info("Skipping step '%s' — condition not met: %s", step.id, step.condition)
                skipped = StepResult(
                    step_id=step.id,
                    success=True,
                    output="[skipped — condition not met]",
                )
                self._results[step.id] = skipped
                workflow_result.steps.append(skipped)
                continue

            # Build context from previous steps
            context = self._build_context(step.context_from)

            # Execute with retries
            result = self._execute_with_retries(step, context)
            self._results[step.id] = result
            workflow_result.steps.append(result)

            # Handle failure
            if not result.success:
                if step.on_failure == OnFailure.STOP:
                    workflow_result.success = False
                    logger.error("Step '%s' failed — stopping workflow", step.id)
                    break
                elif step.on_failure == OnFailure.CONTINUE:
                    logger.warning("Step '%s' failed — continuing (on_failure=continue)", step.id)
                # RETRY already handled in _execute_with_retries

        completed = datetime.now(timezone.utc)
        workflow_result.completed_at = completed.isoformat()
        workflow_result.total_duration_seconds = (completed - started).total_seconds()

        # Persist result
        self._persist_result(workflow_result)

        return workflow_result

    def _execute_with_retries(self, step: Step, context: str) -> StepResult:
        """Execute a step, retrying on failure if configured."""
        max_attempts = step.retry_count + 1 if step.on_failure == OnFailure.RETRY else 1
        last_result = None

        for attempt in range(max_attempts):
            if attempt > 0:
                logger.info(
                    "Retrying step '%s' (attempt %d/%d)", step.id, attempt + 1, max_attempts
                )
                time.sleep(min(2**attempt, 30))  # Exponential backoff, cap at 30s

            if step.type == StepType.SHELL:
                last_result = self._run_shell(step)
            elif step.type == StepType.AI:
                last_result = self._run_ai(step, context)
            else:
                last_result = StepResult(
                    step_id=step.id, success=False, error=f"Unknown type: {step.type}"
                )

            if last_result.success:
                return last_result

        return last_result  # type: ignore[return-value]

    def _run_shell(self, step: Step) -> StepResult:
        """Execute a shell command."""
        if self.dry_run:
            return StepResult(
                step_id=step.id, success=True, output=f"[dry-run] Would run: {step.command}"
            )

        start = time.monotonic()
        try:
            proc = subprocess.run(
                step.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=step.timeout,
                cwd=str(self.working_dir),
            )
            duration = time.monotonic() - start
            return StepResult(
                step_id=step.id,
                success=proc.returncode == 0,
                output=proc.stdout[-5000:] if proc.stdout else "",
                error=proc.stderr[-2000:] if proc.stderr else "",
                exit_code=proc.returncode,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_id=step.id,
                success=False,
                error=f"Timed out after {step.timeout}s",
                duration_seconds=step.timeout,
            )
        except Exception as e:
            return StepResult(step_id=step.id, success=False, error=str(e))

    def _run_ai(self, step: Step, context: str) -> StepResult:
        """Execute an AI step via dispatcher or stub."""
        if self.dry_run:
            return StepResult(
                step_id=step.id,
                success=True,
                output=f"[dry-run] Would prompt ({step.model or 'default'}): {step.prompt[:100]}...",
                model_used=step.model,
            )

        if self.ai_dispatcher is None:
            return StepResult(
                step_id=step.id,
                success=False,
                error="No AI dispatcher configured — cannot run AI steps",
            )

        start = time.monotonic()
        try:
            # Build prompt with context from previous steps
            full_prompt = step.prompt or ""
            if context:
                full_prompt = f"Context from previous steps:\n{context}\n\n---\n\n{full_prompt}"

            # Dispatch via supervisor's AgentDispatcher
            from cortex.supervisor.models import WorkItem, WorkItemPriority

            work_item = WorkItem(
                id=f"workflow-{self.workflow.name}-{step.id}",
                source="workflow",
                task_type=step.model or "sonnet",
                description=step.description or step.prompt[:100] or step.id,
                prompt=full_prompt,
                system_prompt=step.system_prompt,
                project=self.workflow.project,
                priority=WorkItemPriority.MEDIUM,
                confidence=0.9,
            )

            result = self.ai_dispatcher.dispatch(work_item)
            duration = time.monotonic() - start

            return StepResult(
                step_id=step.id,
                success=result.success,
                output=result.output[:5000] if result.output else "",
                error=result.error or "",
                duration_seconds=duration,
                model_used=result.model_used,
                tokens_used=result.tokens_used,
            )
        except Exception as e:
            return StepResult(
                step_id=step.id,
                success=False,
                error=str(e),
                duration_seconds=time.monotonic() - start,
            )

    def _build_context(self, step_ids: List[str]) -> str:
        """Thread outputs from previous steps into context string."""
        if not step_ids:
            return ""

        parts = []
        for sid in step_ids:
            result = self._results.get(sid)
            if result and result.output and result.output != "[skipped — condition not met]":
                parts.append(f"=== Output from '{sid}' ===\n{result.output[-3000:]}")
        return "\n\n".join(parts)

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a step condition against collected results.

        Supports:
          - steps.<id>.success  → bool
          - steps.<id>.exit_code == 0  → comparison
          - not steps.<id>.success  → negation
          - steps.<id>.success and steps.<id2>.success  → conjunction
        """
        # Build a safe evaluation namespace
        steps_ns: Dict[str, Any] = {}
        for sid, result in self._results.items():
            steps_ns[sid] = {
                "success": result.success,
                "exit_code": result.exit_code,
                "output": result.output[:200],
            }

        # Wrap in a namespace object for dot access
        class _NS:
            def __init__(self, data: dict):
                for k, v in data.items():
                    if isinstance(v, dict):
                        setattr(self, k, _NS(v))
                    else:
                        setattr(self, k, v)

        namespace = {"steps": _NS(steps_ns)}

        try:
            return bool(eval(condition, {"__builtins__": {}}, namespace))  # noqa: S307
        except Exception as e:
            logger.warning("Condition evaluation failed for '%s': %s", condition, e)
            return False

    def _persist_result(self, result: WorkflowResult) -> None:
        """Write workflow result to disk for the supervisor to find."""
        try:
            runs_dir = Path.home() / ".cortex" / "workflow_runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            out = runs_dir / f"{self.workflow.name}_{ts}.json"
            out.write_text(json.dumps(result.to_dict(), indent=2))
            logger.info("Workflow result persisted to %s", out)
        except Exception as e:
            logger.warning("Failed to persist workflow result: %s", e)


def run_workflow_file(
    path: Path,
    working_dir: Optional[Path] = None,
    ai_dispatcher: Optional[Any] = None,
    dry_run: bool = False,
) -> WorkflowResult:
    """Convenience: load and run a workflow from a YAML file."""
    workflow = Workflow.from_yaml(path)
    runner = WorkflowRunner(
        workflow=workflow,
        working_dir=working_dir,
        ai_dispatcher=ai_dispatcher,
        dry_run=dry_run,
    )
    return runner.run()
