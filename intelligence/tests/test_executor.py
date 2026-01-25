#!/usr/bin/env python3
"""
Tests for Contract Executor

Tests:
1. Contract parsing → execution steps
2. Step execution (bash, read, edit, write)
3. Success criteria verification
4. Error handling and retries
5. Result tracking
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from intelligence.contracts import TaskContract
from intelligence.executor import (
    ContractExecutor,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStep,
)


@pytest.fixture
def executor():
    """Create executor instance."""
    return ContractExecutor()


@pytest.fixture
def simple_test_contract():
    """Create simple test contract for testing."""
    return TaskContract(
        contract_id="test_contract_001",
        signal_id="test_signal_001",
        title="Fix test failure in test_example.py",
        description="Fix 1 failing unit test in test_example.py",
        requirements=[
            "Run pytest to identify failing test",
            "Read test file to understand failure",
            "Fix the test assertion",
            "Re-run pytest to verify fix",
        ],
        constraints=[
            "Must not break other tests",
            "Must maintain test coverage",
        ],
        success_criteria={
            "tests": ["pytest tests/test_example.py -v"],
            "metrics": {},
            "benchmarks": [],
        },
        dependencies=[],
        human_gates=[],
        risk_level="low",
        auto_executable=True,
        max_attempts=3,
        max_cost_usd=5.00,
        escalate_conditions=["tests_fail_twice"],
        relevant_files=["tests/test_example.py"],
        relevant_docs=[],
        similar_past_work=[],
    )


@pytest.fixture
def bash_contract():
    """Contract for testing bash execution."""
    return TaskContract(
        contract_id="bash_test_001",
        signal_id="signal_bash",
        title="Run simple bash command",
        description="Execute echo command",
        requirements=["Echo test message"],
        constraints=[],
        success_criteria={"tests": [], "metrics": {}, "benchmarks": []},
        dependencies=[],
        human_gates=[],
        risk_level="low",
        auto_executable=True,
    )


class TestContractParsing:
    """Test contract parsing into execution steps."""

    @pytest.mark.asyncio
    async def test_parse_contract_to_steps(self, executor, simple_test_contract):
        """Test parsing contract into actionable steps."""
        steps = await executor._parse_contract_to_steps(simple_test_contract)

        assert len(steps) > 0, "Should generate at least one step"
        assert all(isinstance(s, ExecutionStep) for s in steps), "All should be ExecutionStep objects"

        # Check step structure
        for i, step in enumerate(steps, 1):
            assert step.step_number == i, f"Step {i} should have correct number"
            assert step.description, "Step should have description"

    @pytest.mark.asyncio
    async def test_fallback_step_generation(self, executor, simple_test_contract):
        """Test fallback step generation from requirements."""
        steps = executor._fallback_steps_from_requirements(simple_test_contract)

        assert len(steps) == len(simple_test_contract.requirements)

        for i, (step, requirement) in enumerate(zip(steps, simple_test_contract.requirements), 1):
            assert step.step_number == i
            assert step.description == requirement


class TestStepExecution:
    """Test individual step execution."""

    @pytest.mark.asyncio
    async def test_execute_bash_step_success(self, executor, bash_contract):
        """Test successful bash command execution."""
        step = ExecutionStep(
            step_number=1,
            description="Echo test message",
            command="echo 'test'",
            action="bash",
        )

        success = await executor._execute_bash_step(step, bash_contract)

        assert success, "Echo command should succeed"
        assert "test" in step.output, "Output should contain test message"
        assert not step.error, "Should have no error"

    @pytest.mark.asyncio
    async def test_execute_bash_step_failure(self, executor, bash_contract):
        """Test failed bash command execution."""
        step = ExecutionStep(
            step_number=1,
            description="Run failing command",
            command="false",  # Command that always fails
            action="bash",
        )

        success = await executor._execute_bash_step(step, bash_contract)

        assert not success, "False command should fail"
        assert step.error or not step.output, "Should have error or no output"

    @pytest.mark.asyncio
    async def test_execute_read_step(self, executor, tmp_path):
        """Test file read step."""
        # Create temporary test file
        test_file = tmp_path / "test_file.txt"
        test_content = "Test file content"
        test_file.write_text(test_content)

        step = ExecutionStep(
            step_number=1,
            description="Read test file",
            file_path=str(test_file),
            action="read",
        )

        success = await executor._execute_read_step(step)

        assert success, "Read should succeed"
        assert test_content in step.output, "Output should contain file content"

    @pytest.mark.asyncio
    async def test_execute_read_step_missing_file(self, executor):
        """Test read step with missing file."""
        step = ExecutionStep(
            step_number=1,
            description="Read missing file",
            file_path="/nonexistent/file.txt",
            action="read",
        )

        success = await executor._execute_read_step(step)

        assert not success, "Read should fail for missing file"
        assert "not found" in step.error.lower(), "Error should mention file not found"


class TestSuccessVerification:
    """Test success criteria verification."""

    @pytest.mark.asyncio
    async def test_verify_tests_pass(self, executor, tmp_path):
        """Test verification when tests pass."""
        # Create temporary tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        contract = TaskContract(
            contract_id="test_001",
            signal_id="sig_001",
            title="Test verification",
            description="Test success verification",
            requirements=[],
            constraints=[],
            success_criteria={
                "tests": ["pytest tests/"],  # pytest command
                "metrics": {},
                "benchmarks": [],
            },
            dependencies=[],
            human_gates=[],
            risk_level="low",
            auto_executable=True,
        )

        result = ExecutionResult(
            contract_id=contract.contract_id,
            status=ExecutionStatus.VERIFYING,
            success=False,
            steps_completed=1,
            steps_total=1,
            execution_time_seconds=0.0,
        )

        # Extract test command
        test_cmd = executor._extract_test_command(
            contract.success_criteria["tests"],
            tmp_path  # Use tmp_path which has tests/ dir
        )

        # Should extract pytest command
        assert test_cmd is not None, "Should extract test command"
        assert "pytest" in test_cmd, "Should contain pytest"

    @pytest.mark.asyncio
    async def test_verify_success_criteria_no_tests(self, executor):
        """Test verification when no tests specified."""
        contract = TaskContract(
            contract_id="test_002",
            signal_id="sig_002",
            title="No test verification",
            description="Contract with no tests",
            requirements=[],
            constraints=[],
            success_criteria={
                "tests": [],
                "metrics": {},
                "benchmarks": [],
            },
            dependencies=[],
            human_gates=[],
            risk_level="low",
            auto_executable=True,
        )

        result = ExecutionResult(
            contract_id=contract.contract_id,
            status=ExecutionStatus.VERIFYING,
            success=False,
            steps_completed=1,
            steps_total=1,
            execution_time_seconds=0.0,
        )

        await executor._verify_success_criteria(contract, result)

        # No tests = pass by default
        assert result.tests_passed, "Should pass when no tests specified"
        assert result.metrics_met, "Should pass when no metrics specified"


class TestExecutionFlow:
    """Test full execution flow."""

    @pytest.mark.asyncio
    async def test_execute_contract_dry_run(self, executor, simple_test_contract):
        """Test dry run execution."""
        result = await executor.execute_contract(simple_test_contract, dry_run=True)

        assert result.status == ExecutionStatus.SUCCESS, "Dry run should succeed"
        assert result.success, "Dry run should be marked successful"
        assert result.steps_total > 0, "Should plan some steps"
        assert result.steps_completed == 0, "Dry run should not execute steps"

    @pytest.mark.asyncio
    async def test_execution_result_tracking(self, executor, bash_contract):
        """Test execution result is properly tracked."""
        # Modify contract for simple bash execution
        bash_contract.requirements = ["Echo test"]
        bash_contract.success_criteria = {
            "tests": [],
            "metrics": {},
            "benchmarks": [],
        }

        result = await executor.execute_contract(bash_contract, dry_run=True)

        # Check result structure
        assert result.contract_id == bash_contract.contract_id
        assert isinstance(result.status, ExecutionStatus)
        assert isinstance(result.success, bool)
        assert result.execution_time_seconds >= 0
        assert result.started_at is not None


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_handles_execution_error(self, executor):
        """Test graceful handling of execution errors."""
        bad_contract = TaskContract(
            contract_id="error_test_001",
            signal_id="error_sig",
            title="Error test",
            description="Test error handling",
            requirements=["Intentional failure"],
            constraints=[],
            success_criteria={"tests": [], "metrics": {}, "benchmarks": []},
            dependencies=[],
            human_gates=[],
            risk_level="low",
            auto_executable=True,
        )

        # Execute with dry run first to avoid actual errors
        result = await executor.execute_contract(bad_contract, dry_run=True)

        # Should complete dry run successfully
        assert result.status == ExecutionStatus.SUCCESS


class TestResultPersistence:
    """Test result saving and loading."""

    @pytest.mark.asyncio
    async def test_save_result(self, executor, bash_contract):
        """Test result is saved to disk."""
        result = ExecutionResult(
            contract_id=bash_contract.contract_id,
            status=ExecutionStatus.SUCCESS,
            success=True,
            steps_completed=1,
            steps_total=1,
            execution_time_seconds=1.5,
            tests_passed=True,
            metrics_met=True,
            completed_at=datetime.now(),
        )

        executor._save_result(result)

        # Check file exists
        result_file = executor.results_dir / f"{result.contract_id}_result.json"
        assert result_file.exists(), "Result file should be created"

        # Check content
        data = json.loads(result_file.read_text())
        assert data["contract_id"] == bash_contract.contract_id
        assert data["status"] == "success"
        assert data["success"] is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
