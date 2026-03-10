"""Tests for cortex.workflows — schema validation and runner execution."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from cortex.workflows.runner import StepResult, WorkflowResult, WorkflowRunner
from cortex.workflows.schema import Workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_yaml() -> str:
    return textwrap.dedent("""\
        name: ci-pipeline
        project: vortex
        steps:
          - id: lint
            type: shell
            command: "echo lint-ok"
          - id: test
            type: shell
            command: "echo test-ok"
          - id: summarize
            type: ai
            prompt: "Summarize results."
            context_from: [lint, test]
    """)


@pytest.fixture()
def two_step_yaml() -> str:
    """Shell step A -> conditional shell step B."""
    return textwrap.dedent("""\
        name: gated
        steps:
          - id: a
            type: shell
            command: "echo step-a"
          - id: b
            type: shell
            command: "echo step-b"
            condition: "steps.a.success"
    """)


# ===================================================================
# Schema tests
# ===================================================================


class TestSchemaValidation:
    """Tests for cortex.workflows.schema.Workflow."""

    # 1. Load valid workflow from YAML string
    def test_load_valid_workflow_from_yaml_string(self, simple_yaml: str) -> None:
        wf = Workflow.from_yaml_string(simple_yaml)
        assert wf.name == "ci-pipeline"
        assert wf.project == "vortex"
        assert len(wf.steps) == 3
        assert wf.steps[0].id == "lint"
        assert wf.steps[2].type.value == "ai"
        assert wf.steps[2].context_from == ["lint", "test"]

    # 2. Reject duplicate step IDs
    def test_reject_duplicate_step_ids(self) -> None:
        yaml_str = textwrap.dedent("""\
            name: dup
            steps:
              - id: build
                type: shell
                command: "make"
              - id: build
                type: shell
                command: "make again"
        """)
        with pytest.raises(ValidationError, match="Duplicate step ID: build"):
            Workflow.from_yaml_string(yaml_str)

    # 3. Reject shell step without command
    def test_reject_shell_step_without_command(self) -> None:
        yaml_str = textwrap.dedent("""\
            name: bad-shell
            steps:
              - id: oops
                type: shell
        """)
        with pytest.raises(ValidationError, match="Shell step 'oops' requires 'command'"):
            Workflow.from_yaml_string(yaml_str)

    # 4. Reject AI step without prompt
    def test_reject_ai_step_without_prompt(self) -> None:
        yaml_str = textwrap.dedent("""\
            name: bad-ai
            steps:
              - id: think
                type: ai
                model: sonnet
        """)
        with pytest.raises(ValidationError, match="AI step 'think' requires 'prompt'"):
            Workflow.from_yaml_string(yaml_str)

    # 5. Reject condition referencing unknown step ID
    def test_reject_condition_referencing_unknown_step(self) -> None:
        yaml_str = textwrap.dedent("""\
            name: bad-cond
            steps:
              - id: deploy
                type: shell
                command: "deploy.sh"
                condition: "steps.test.success"
        """)
        with pytest.raises(ValidationError, match="Condition references unknown step 'test'"):
            Workflow.from_yaml_string(yaml_str)

    # 6. Reject context_from referencing future step (not yet defined)
    def test_reject_context_from_future_step(self) -> None:
        yaml_str = textwrap.dedent("""\
            name: future-ref
            steps:
              - id: early
                type: shell
                command: "echo hi"
                context_from: [later]
              - id: later
                type: shell
                command: "echo bye"
        """)
        with pytest.raises(
            ValidationError, match="references 'later' in context_from.*hasn't been defined"
        ):
            Workflow.from_yaml_string(yaml_str)

    # 7. Load from YAML file (use tmp_path fixture)
    def test_load_from_yaml_file(self, tmp_path: Path, simple_yaml: str) -> None:
        yaml_file = tmp_path / "workflow.yaml"
        yaml_file.write_text(simple_yaml)

        wf = Workflow.from_yaml(yaml_file)
        assert wf.name == "ci-pipeline"
        assert len(wf.steps) == 3


# ===================================================================
# Runner tests
# ===================================================================


class TestWorkflowRunner:
    """Tests for cortex.workflows.runner.WorkflowRunner."""

    # 8. Dry-run executes all steps as success
    def test_dry_run_all_steps_succeed(self, simple_yaml: str) -> None:
        wf = Workflow.from_yaml_string(simple_yaml)
        runner = WorkflowRunner(wf, dry_run=True)
        result = runner.run()

        assert result.success is True
        assert len(result.steps) == 3
        for sr in result.steps:
            assert sr.success is True
            assert "[dry-run]" in sr.output

    # 9. Shell step executes real command (echo hello)
    def test_shell_step_executes_real_command(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: echo-test
            steps:
              - id: greet
                type: shell
                command: "echo hello"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert result.success is True
        assert len(result.steps) == 1
        assert result.steps[0].success is True
        assert "hello" in result.steps[0].output
        assert result.steps[0].exit_code == 0

    # 10. Shell step fails on bad command (exit 1)
    def test_shell_step_fails_on_bad_command(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: fail-test
            steps:
              - id: boom
                type: shell
                command: "exit 1"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert result.success is False
        assert result.steps[0].success is False
        assert result.steps[0].exit_code == 1

    # 11. Condition gates step execution (step skipped when condition false)
    def test_condition_gates_step_execution(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: gated
            steps:
              - id: fail_first
                type: shell
                command: "exit 1"
                on_failure: continue
              - id: gated_step
                type: shell
                command: "echo should-not-run"
                condition: "steps.fail_first.success"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert result.steps[0].success is False
        assert result.steps[1].output == "[skipped — condition not met]"
        assert result.steps[1].success is True  # skipped steps are marked success

    # 12. Context threading passes output from step A to step B
    def test_context_threading(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: context-test
            steps:
              - id: producer
                type: shell
                command: "echo PRODUCED_VALUE_42"
              - id: consumer
                type: shell
                command: "echo consumed"
                context_from: [producer]
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert result.success is True
        # Verify the runner internally built context from producer's output
        context = runner._build_context(["producer"])
        assert "PRODUCED_VALUE_42" in context
        assert "Output from 'producer'" in context

    # 13. on_failure=stop halts workflow on failure
    def test_on_failure_stop_halts_workflow(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: stop-test
            steps:
              - id: fail_step
                type: shell
                command: "exit 1"
                on_failure: stop
              - id: never_reached
                type: shell
                command: "echo unreachable"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert result.success is False
        assert len(result.steps) == 1  # second step never executed
        assert result.steps[0].step_id == "fail_step"

    # 14. on_failure=continue proceeds past failure
    def test_on_failure_continue_proceeds(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: continue-test
            steps:
              - id: fail_step
                type: shell
                command: "exit 1"
                on_failure: continue
              - id: after_fail
                type: shell
                command: "echo still-running"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        result = runner.run()

        assert len(result.steps) == 2
        assert result.steps[0].success is False
        assert result.steps[1].success is True
        assert "still-running" in result.steps[1].output

    # 15. Retry logic retries N times on failure
    def test_retry_logic(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Eliminate sleep between retries for test speed
        monkeypatch.setattr("cortex.workflows.runner.time.sleep", lambda _: None)

        yaml_str = textwrap.dedent("""\
            name: retry-test
            steps:
              - id: flaky
                type: shell
                command: "exit 1"
                on_failure: retry
                retry_count: 2
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)

        call_count = 0
        original_run_shell = runner._run_shell

        def counting_run_shell(step):
            nonlocal call_count
            call_count += 1
            return original_run_shell(step)

        monkeypatch.setattr(runner, "_run_shell", counting_run_shell)
        result = runner.run()

        # retry_count=2 means 1 initial + 2 retries = 3 total attempts
        assert call_count == 3
        assert result.steps[0].success is False

    # 16. AI step fails gracefully without dispatcher
    def test_ai_step_fails_without_dispatcher(self, tmp_path: Path) -> None:
        yaml_str = textwrap.dedent("""\
            name: ai-no-dispatch
            steps:
              - id: think
                type: ai
                prompt: "Summarize everything"
                on_failure: continue
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path, ai_dispatcher=None)
        result = runner.run()

        assert len(result.steps) == 1
        assert result.steps[0].success is False
        assert "No AI dispatcher configured" in result.steps[0].error

    # 17. Result persistence writes to ~/.cortex/workflow_runs/
    def test_result_persistence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Redirect ~/.cortex to tmp_path so we don't pollute the real home
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

        yaml_str = textwrap.dedent("""\
            name: persist-test
            steps:
              - id: ok
                type: shell
                command: "echo persisted"
        """)
        wf = Workflow.from_yaml_string(yaml_str)
        runner = WorkflowRunner(wf, working_dir=tmp_path)
        runner.run()

        runs_dir = fake_home / ".cortex" / "workflow_runs"
        assert runs_dir.exists()

        json_files = list(runs_dir.glob("persist-test_*.json"))
        assert len(json_files) == 1

        data = json.loads(json_files[0].read_text())
        assert data["workflow_name"] == "persist-test"
        assert data["success"] is True
        assert len(data["steps"]) == 1
        assert data["steps"][0]["step_id"] == "ok"

    # 18. WorkflowResult.summary() returns readable string
    def test_workflow_result_summary(self) -> None:
        wr = WorkflowResult(
            workflow_name="my-flow",
            success=False,
            total_duration_seconds=12.5,
            steps=[
                StepResult(step_id="build", success=True, duration_seconds=5.0),
                StepResult(
                    step_id="deploy",
                    success=False,
                    duration_seconds=7.5,
                    error="Connection refused",
                ),
            ],
        )
        summary = wr.summary()

        assert "my-flow" in summary
        assert "FAILED" in summary
        assert "1 passed" in summary
        assert "1 failed" in summary
        assert "12.5s total" in summary
        assert "build" in summary
        assert "deploy" in summary
        assert "Connection refused" in summary
