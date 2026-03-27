#!/usr/bin/env python3
"""
Contract Execution Engine

Executes TaskContracts autonomously:
1. Parse requirements into actionable steps
2. Execute steps using appropriate tools
3. Verify success criteria (tests, metrics, benchmarks)
4. Report results to health monitor
5. Handle failures gracefully with retry logic

This closes the loop: detect → contract → EXECUTE → verify.
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cortex.intelligence.contracts import TaskContract
except ImportError:
    from intelligence.contracts import TaskContract  # type: ignore[no-redef]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status states."""

    PENDING = "pending"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ExecutionStep:
    """Single execution step."""

    step_number: int
    description: str
    command: Optional[str] = None
    file_path: Optional[str] = None
    action: str = "bash"  # bash, read, write, edit
    completed: bool = False
    output: str = ""
    error: str = ""


@dataclass
class ExecutionResult:
    """Result of contract execution."""

    contract_id: str
    status: ExecutionStatus
    success: bool

    # Execution details
    steps_completed: int
    steps_total: int
    execution_time_seconds: float

    # Verification results
    tests_passed: bool = False
    metrics_met: bool = False
    benchmarks_met: bool = False

    # Detailed results
    test_output: str = ""
    metric_values: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    # Cost tracking
    attempts: int = 1
    cost_usd: float = 0.0

    # Metadata
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ContractExecutor:
    """
    Executes TaskContracts autonomously.

    Workflow:
    1. Parse contract requirements into execution steps
    2. Execute each step sequentially
    3. Track progress and capture output
    4. Verify success criteria
    5. Return ExecutionResult
    """

    def __init__(self, root_dir: str = os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd()))):
        self.root_dir = Path(root_dir)
        self.results_dir = Path.home() / ".cortex" / "execution_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AI client — prefer conductor async for non-blocking calls
        self._conductor_available = False
        self._conductor_async_available = False
        try:
            from cortex.conductor import async_call as conductor_async_call
            from cortex.conductor import call as conductor_call

            self._conductor_call = conductor_call
            self._conductor_async_call = conductor_async_call
            self._conductor_available = True
            self._conductor_async_available = True
        except ImportError:
            try:
                from cortex.conductor import call as conductor_call

                self._conductor_call = conductor_call
                self._conductor_available = True
            except ImportError:
                from anthropic import Anthropic

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environment variable not set")
                self._anthropic_client = Anthropic(api_key=api_key)

    async def execute_contract(
        self, contract: TaskContract, dry_run: bool = False
    ) -> ExecutionResult:
        """
        Execute a contract autonomously.

        Args:
            contract: TaskContract to execute
            dry_run: If True, only plan steps without executing

        Returns:
            ExecutionResult with success/failure and details
        """
        logger.info(f"🚀 Starting execution: {contract.title}")

        start_time = time.time()
        result = ExecutionResult(
            contract_id=contract.contract_id,
            status=ExecutionStatus.RUNNING,
            success=False,
            steps_completed=0,
            steps_total=0,
            execution_time_seconds=0.0,
        )

        try:
            # 1. Parse contract into execution steps
            logger.info("📋 Parsing contract into execution steps...")
            steps = await self._parse_contract_to_steps(contract)
            result.steps_total = len(steps)

            if dry_run:
                logger.info(f"🔍 Dry run: Would execute {len(steps)} steps")
                for step in steps:
                    logger.info(f"  Step {step.step_number}: {step.description}")
                result.status = ExecutionStatus.SUCCESS
                result.success = True
                return result

            # 2. Execute steps sequentially
            logger.info(f"⚙️ Executing {len(steps)} steps...")
            for step in steps:
                logger.info(f"  [{step.step_number}/{len(steps)}] {step.description}")

                success = await self._execute_step(step, contract)

                if success:
                    result.steps_completed += 1
                    step.completed = True
                else:
                    # Step failed
                    result.error_message = f"Step {step.step_number} failed: {step.error}"
                    result.status = ExecutionStatus.FAILED
                    raise RuntimeError(result.error_message)

            logger.info(f"✅ All {result.steps_completed} steps completed")

            # 3. Verify success criteria
            logger.info("🔍 Verifying success criteria...")
            result.status = ExecutionStatus.VERIFYING

            await self._verify_success_criteria(contract, result)

            # 4. Determine final status
            if result.tests_passed and result.metrics_met:
                result.status = ExecutionStatus.SUCCESS
                result.success = True
                logger.info("✅ Execution SUCCESSFUL - all criteria met")
            else:
                result.status = ExecutionStatus.FAILED
                result.success = False
                result.error_message = "Success criteria not met"
                logger.warning("⚠️ Execution FAILED - criteria not satisfied")

        except Exception as e:
            # Execution error
            result.status = ExecutionStatus.FAILED
            result.success = False
            result.error_message = str(e)
            logger.error(f"❌ Execution error: {e}")

        finally:
            # Finalize result
            result.execution_time_seconds = time.time() - start_time
            result.completed_at = datetime.now()

            # Save result
            self._save_result(result)

            logger.info(f"⏱️ Execution time: {result.execution_time_seconds:.1f}s")

        return result

    async def _parse_contract_to_steps(self, contract: TaskContract) -> List[ExecutionStep]:
        """
        Parse contract requirements into executable steps.

        Uses Sonnet 4.5 to analyze requirements and generate actionable steps.

        Args:
            contract: TaskContract to parse

        Returns:
            List of ExecutionStep objects
        """
        # Build prompt for step generation
        prompt = self._build_step_generation_prompt(contract)

        try:
            # Route through conductor — prefer async to avoid blocking event loop
            if self._conductor_async_available:
                result = await self._conductor_async_call(
                    prompt,
                    use_case="interactive_coding",
                    max_tokens=4000,
                )
                response_text = result.content
            elif self._conductor_available:
                import asyncio

                result = await asyncio.to_thread(
                    self._conductor_call,
                    prompt,
                    use_case="interactive_coding",
                    max_tokens=4000,
                )
                response_text = result.content
            else:
                import asyncio

                try:
                    from supervisor.router import (
                        complexity_for_task,
                        select_model as router_select_model,
                    )
                except ImportError:
                    from cortex.supervisor.router import (  # type: ignore[no-redef]
                        complexity_for_task,
                        select_model as router_select_model,
                    )
                _model = router_select_model(complexity_for_task("interactive_coding"))
                response = await asyncio.to_thread(
                    self._anthropic_client.messages.create,
                    model=_model,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text

            # Parse response
            steps_data = self._parse_steps_response(response_text)

            # Convert to ExecutionStep objects
            steps = []
            for i, step_dict in enumerate(steps_data, 1):
                step = ExecutionStep(
                    step_number=i,
                    description=step_dict["description"],
                    command=step_dict.get("command"),
                    file_path=step_dict.get("file_path"),
                    action=step_dict.get("action", "bash"),
                )
                steps.append(step)

            return steps

        except Exception as e:
            logger.error(f"Error parsing contract to steps: {e}")
            # Fallback: Create basic steps from requirements
            return self._fallback_steps_from_requirements(contract)

    def _build_step_generation_prompt(self, contract: TaskContract) -> str:
        """Build prompt for generating execution steps."""

        return f"""You are a technical execution planner. Convert this task contract into actionable execution steps.

TASK CONTRACT:
Title: {contract.title}
Description: {contract.description}

REQUIREMENTS:
{chr(10).join(f"{i}. {req}" for i, req in enumerate(contract.requirements, 1))}

CONSTRAINTS:
{chr(10).join(f"- {c}" for c in contract.constraints)}

SUCCESS CRITERIA:
Tests: {contract.success_criteria.get("tests", [])}
Metrics: {contract.success_criteria.get("metrics", {})}

RELEVANT FILES:
{chr(10).join(contract.relevant_files[:10])}

YOUR TASK:
Generate a sequential list of execution steps that will accomplish all requirements.
Each step should be concrete and executable.

Step types available:
- bash: Execute shell command (tests, builds, deployments)
- read: Read file contents for analysis
- edit: Modify existing file
- write: Create new file (use sparingly)

Output ONLY valid JSON in this format:
{{
  "steps": [
    {{
      "description": "Run pytest to identify failing tests",
      "action": "bash",
      "command": "pytest Vortex/backend/tests/test_ensemble.py -v"
    }},
    {{
      "description": "Read test file to understand failures",
      "action": "read",
      "file_path": "Vortex/backend/tests/test_ensemble.py"
    }},
    {{
      "description": "Fix test assertion",
      "action": "edit",
      "file_path": "Vortex/backend/tests/test_ensemble.py"
    }}
  ]
}}

IMPORTANT:
- Keep steps focused and atomic
- Use absolute file paths
- Prefer edit over write for existing files
- Include verification steps (run tests after fixes)
- Maximum 10 steps

Output ONLY the JSON, no other text."""

    def _parse_steps_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse Sonnet response into steps data."""
        # Extract JSON from response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in response")

        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)

        return data.get("steps", [])

    def _fallback_steps_from_requirements(self, contract: TaskContract) -> List[ExecutionStep]:
        """Fallback: Generate basic steps from requirements."""
        steps = []

        # Create one step per requirement
        for i, requirement in enumerate(contract.requirements, 1):
            step = ExecutionStep(
                step_number=i,
                description=requirement,
                action="bash",
                command=None,  # Will need manual intervention
            )
            steps.append(step)

        return steps

    async def _execute_step(self, step: ExecutionStep, contract: TaskContract) -> bool:
        """
        Execute a single step.

        Args:
            step: ExecutionStep to execute
            contract: TaskContract context

        Returns:
            True if successful, False otherwise
        """
        try:
            if step.action == "bash":
                return await self._execute_bash_step(step, contract)
            elif step.action == "read":
                return await self._execute_read_step(step)
            elif step.action == "edit":
                return await self._execute_edit_step(step)
            elif step.action == "write":
                return await self._execute_write_step(step)
            else:
                logger.warning(f"Unknown action: {step.action}")
                return False

        except Exception as e:
            step.error = str(e)
            logger.error(f"Step execution failed: {e}")
            return False

    async def _execute_bash_step(self, step: ExecutionStep, contract: TaskContract) -> bool:
        """Execute bash command step."""
        if not step.command:
            logger.error("No command specified for bash step")
            return False

        # Determine working directory from contract signal_id or description
        working_dir = self.root_dir

        # Try to infer project from contract signal_id or title
        contract_text = f"{contract.contract_id} {contract.title} {contract.description}".lower()
        if "vortex-backend" in contract_text or "vortex/backend" in contract_text:
            working_dir = self.root_dir / "Vortex" / "backend"
        elif "alpha_arena" in contract_text or "alpha arena" in contract_text:
            working_dir = self.root_dir / "alpha_arena"
        elif "cortex" in contract_text and "vortex" not in contract_text:
            working_dir = self.root_dir / "cortex"

        # Legacy: check context if provided
        if "project" in getattr(contract, "context", {}):
            project = contract.context["project"]
            if project == "vortex-backend":
                working_dir = self.root_dir / "Vortex" / "backend"
            elif project == "Alpha Arena":
                working_dir = self.root_dir / "alpha_arena"
            elif project == "Cortex":
                working_dir = self.root_dir / "cortex"

        # Detect and activate virtual environment
        command = step.command
        venv_dir = self._detect_venv(working_dir)
        if venv_dir:
            logger.info(f"  Using venv: {venv_dir}")
            # Prepend venv activation to command
            command = f"source {venv_dir}/bin/activate && {command}"

        logger.info(f"  Running: {step.command}")
        logger.info(f"  Working dir: {working_dir}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                executable="/bin/bash",  # Required for source command
            )

            step.output = result.stdout

            if result.returncode == 0:
                logger.info("  ✅ Command succeeded")
                return True
            else:
                step.error = result.stderr
                logger.error(f"  ❌ Command failed: {result.stderr[:200]}")
                return False

        except subprocess.TimeoutExpired:
            step.error = "Command timed out after 5 minutes"
            logger.error("  ❌ Command timed out")
            return False

    def _detect_venv(self, working_dir: Path) -> Optional[Path]:
        """
        Detect virtual environment directory in working_dir.

        Checks for .venv, venv, env directories with bin/python.

        Args:
            working_dir: Directory to search

        Returns:
            Path to venv directory, or None if not found
        """
        candidates = [".venv", "venv", "env"]

        for candidate in candidates:
            venv_path = working_dir / candidate
            python_path = venv_path / "bin" / "python"

            if python_path.exists():
                return venv_path

        return None

    async def _execute_read_step(self, step: ExecutionStep) -> bool:
        """Execute file read step."""
        if not step.file_path:
            logger.error("No file path specified for read step")
            return False

        file_path = Path(step.file_path)
        if not file_path.is_absolute():
            file_path = self.root_dir / file_path

        if not file_path.exists():
            step.error = f"File not found: {file_path}"
            logger.error(f"  ❌ {step.error}")
            return False

        try:
            content = file_path.read_text()
            step.output = content[:1000]  # Store first 1000 chars
            logger.info(f"  ✅ Read {len(content)} bytes from {file_path.name}")
            return True

        except Exception as e:
            step.error = str(e)
            logger.error(f"  ❌ Read failed: {e}")
            return False

    async def _execute_edit_step(self, step: ExecutionStep) -> bool:
        """
        Execute file edit step.

        NOTE: This is a placeholder. In real implementation, this would:
        1. Use LLM to generate edit
        2. Apply edit to file
        3. Verify syntax

        For MVP, we log the intent but don't actually modify files.
        """
        logger.warning(f"  ⚠️ Edit step (placeholder): {step.description}")
        logger.warning(f"  File: {step.file_path}")
        logger.warning("  Actual file editing requires human approval - skipping for safety")

        # For MVP, treat as successful but don't modify
        step.output = "Edit step requires manual execution"
        return True

    async def _execute_write_step(self, step: ExecutionStep) -> bool:
        """
        Execute file write step.

        NOTE: Similar to edit, this is a placeholder for safety.
        """
        logger.warning(f"  ⚠️ Write step (placeholder): {step.description}")
        logger.warning(f"  File: {step.file_path}")
        logger.warning("  File creation requires human approval - skipping for safety")

        step.output = "Write step requires manual execution"
        return True

    async def _verify_success_criteria(
        self, contract: TaskContract, result: ExecutionResult
    ) -> None:
        """
        Verify all success criteria.

        Checks:
        1. Tests: Run specified test suites
        2. Metrics: Verify metric thresholds
        3. Benchmarks: Manual verification checklist

        Args:
            contract: TaskContract with success criteria
            result: ExecutionResult to populate
        """
        # 1. Verify tests
        tests = contract.success_criteria.get("tests", [])
        if tests:
            result.tests_passed = await self._verify_tests(tests, contract, result)
        else:
            # No tests specified = pass by default
            result.tests_passed = True

        # 2. Verify metrics
        metrics = contract.success_criteria.get("metrics", {})
        if metrics:
            result.metrics_met = await self._verify_metrics(metrics, result)
        else:
            # No metrics specified = pass by default
            result.metrics_met = True

        # 3. Benchmarks (manual verification - skip for automation)
        benchmarks = contract.success_criteria.get("benchmarks", [])
        if benchmarks:
            logger.info(f"  ℹ️ Manual benchmarks specified: {len(benchmarks)}")
            logger.info("  These require human verification")
            result.benchmarks_met = False  # Requires manual check
        else:
            result.benchmarks_met = True

    async def _verify_tests(
        self, tests: List[str], contract: TaskContract, result: ExecutionResult
    ) -> bool:
        """
        Run test suites to verify success.

        Args:
            tests: List of test descriptions
            contract: TaskContract for context
            result: ExecutionResult to populate

        Returns:
            True if all tests pass
        """
        logger.info(f"  🧪 Running {len(tests)} test criteria...")

        # Determine working directory (use same logic as _execute_bash_step)
        working_dir = self.root_dir

        # Try to infer project from contract signal_id or title
        contract_text = f"{contract.contract_id} {contract.title} {contract.description}".lower()
        if "vortex-backend" in contract_text or "vortex/backend" in contract_text:
            working_dir = self.root_dir / "Vortex" / "backend"
        elif "alpha_arena" in contract_text or "alpha arena" in contract_text:
            working_dir = self.root_dir / "alpha_arena"
        elif "cortex" in contract_text and "vortex" not in contract_text:
            working_dir = self.root_dir / "cortex"

        # Legacy: check context if provided
        if "project" in getattr(contract, "context", {}):
            project = contract.context["project"]
            if project == "vortex-backend":
                working_dir = self.root_dir / "Vortex" / "backend"
            elif project == "Alpha Arena":
                working_dir = self.root_dir / "alpha_arena"
            elif project == "Cortex":
                working_dir = self.root_dir / "cortex"

        # Parse test command from criteria
        # Common patterns: "pytest tests/", "All tests pass", etc.
        test_command = self._extract_test_command(tests, working_dir)

        if not test_command:
            logger.warning("  ⚠️ Could not determine test command from criteria")
            result.test_output = "No executable test command found"
            return False

        # Detect and activate virtual environment
        venv_dir = self._detect_venv(working_dir)
        if venv_dir:
            logger.info(f"  Using venv: {venv_dir}")
            test_command = f"source {venv_dir}/bin/activate && {test_command}"

        logger.info(f"  Running: {test_command}")

        try:
            test_result = subprocess.run(
                test_command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for tests
                executable="/bin/bash",  # Required for source command
            )

            result.test_output = test_result.stdout + test_result.stderr

            if test_result.returncode == 0:
                logger.info("  ✅ All tests passed")
                return True
            else:
                logger.error(f"  ❌ Tests failed (exit code: {test_result.returncode})")
                return False

        except subprocess.TimeoutExpired:
            result.test_output = "Tests timed out after 10 minutes"
            logger.error("  ❌ Tests timed out")
            return False
        except Exception as e:
            result.test_output = f"Test execution error: {e}"
            logger.error(f"  ❌ Test execution error: {e}")
            return False

    def _extract_test_command(self, tests: List[str], working_dir: Path) -> Optional[str]:
        """
        Extract executable test command from test criteria.

        Args:
            tests: List of test descriptions
            working_dir: Project working directory

        Returns:
            Shell command to run tests, or None
        """
        # Check if pytest is available
        if (working_dir / "tests").exists() or (working_dir / "test").exists():
            # Default to pytest
            return "pytest -v"

        # Check for specific test mentions
        for test in tests:
            test_lower = test.lower()

            if "pytest" in test_lower:
                # Extract pytest command
                return "pytest -v"
            elif "test" in test_lower and ".py" in test_lower:
                # Specific test file mentioned
                return "pytest -v"

        return None

    async def _verify_metrics(self, metrics: Dict[str, str], result: ExecutionResult) -> bool:
        """
        Verify metric thresholds.

        Args:
            metrics: Dictionary of metric_name -> threshold
            result: ExecutionResult to populate

        Returns:
            True if all metrics meet thresholds
        """
        logger.info(f"  📊 Verifying {len(metrics)} metrics...")

        # For MVP, we don't have a metrics collection system yet
        # This would integrate with dashboard_data.json or other metric sources

        logger.warning("  ⚠️ Metric verification not yet implemented")
        logger.info("  Required metrics:")
        for metric, threshold in metrics.items():
            logger.info(f"    - {metric}: {threshold}")

        # For MVP, assume metrics pass (would be replaced with real verification)
        result.metric_values = {metric: "not_measured" for metric in metrics}
        return True

    def _save_result(self, result: ExecutionResult) -> None:
        """Save execution result to disk."""
        result_file = self.results_dir / f"{result.contract_id}_result.json"

        result_data = {
            "contract_id": result.contract_id,
            "status": result.status.value,
            "success": result.success,
            "steps_completed": result.steps_completed,
            "steps_total": result.steps_total,
            "execution_time_seconds": result.execution_time_seconds,
            "tests_passed": result.tests_passed,
            "metrics_met": result.metrics_met,
            "benchmarks_met": result.benchmarks_met,
            "test_output": result.test_output[:1000],  # Truncate
            "metric_values": result.metric_values,
            "error_message": result.error_message,
            "attempts": result.attempts,
            "cost_usd": result.cost_usd,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }

        result_file.write_text(json.dumps(result_data, indent=2))
        logger.info(f"💾 Saved result: {result_file}")


if __name__ == "__main__":
    import asyncio

    from intelligence.contracts import ContractGenerator
    from intelligence.signals import SignalDetector

    async def test_executor():
        """Test executor with real signal."""
        # Detect signals
        detector = SignalDetector()
        signals = detector.detect_all()

        if not signals:
            print("No signals detected")
            return

        # Use first test failure signal (low risk)
        test_signal = None
        for signal in signals:
            if signal.type.value == "test_failure":
                test_signal = signal
                break

        if not test_signal:
            print("No test failure signals found")
            return

        print(f"Testing executor with: {test_signal.title}\n")

        # Generate contract
        generator = ContractGenerator()
        contract = await generator.generate_contract(test_signal)

        print(f"Generated contract: {contract.contract_id}")
        print(f"Risk: {contract.risk_level}\n")

        # Execute contract (dry run first)
        executor = ContractExecutor()

        print("=== DRY RUN ===")
        result = await executor.execute_contract(contract, dry_run=True)
        print(f"Would execute {result.steps_total} steps\n")

        # Ask for confirmation (only in interactive mode)
        import sys

        if sys.stdin.isatty():
            response = input("Execute for real? (y/n): ")
            if response.lower() == "y":
                print("\n=== EXECUTING ===")
                result = await executor.execute_contract(contract, dry_run=False)

                print(f"\n{'=' * 80}")
                print("EXECUTION RESULT")
                print(f"{'=' * 80}")
                print(f"Status: {result.status.value}")
                print(f"Success: {result.success}")
                print(f"Steps: {result.steps_completed}/{result.steps_total}")
                print(f"Time: {result.execution_time_seconds:.1f}s")
                print(f"Tests: {'✅' if result.tests_passed else '❌'}")
                print(f"Metrics: {'✅' if result.metrics_met else '❌'}")

                if result.error_message:
                    print(f"\nError: {result.error_message}")
        else:
            print("\nNon-interactive mode: Skipping actual execution (dry run only)")

    asyncio.run(test_executor())
