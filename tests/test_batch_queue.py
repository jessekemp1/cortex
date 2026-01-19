"""
Tests for batch queue command validation.

Ensures AI prompts are rejected, shell commands are accepted.
"""

import tempfile
from pathlib import Path

import pytest


class TestCommandValidation:
    """Tests for _validate_command method."""

    def setup_method(self):
        """Create a batch queue with temp directory."""
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

        self.tmpdir = tempfile.mkdtemp()
        self.queue = BatchTaskQueue(db_path=Path(self.tmpdir) / "test_queue.db")

    def test_valid_python_command(self):
        """Python commands should be valid."""
        is_valid, error = self.queue._validate_command("python -m cortex briefing")
        assert is_valid
        assert error == ""

    def test_valid_pytest_command(self):
        """Pytest commands should be valid."""
        is_valid, error = self.queue._validate_command("pytest cortex/tests/ -v")
        assert is_valid
        assert error == ""

    def test_valid_bash_command(self):
        """Bash commands should be valid."""
        is_valid, error = self.queue._validate_command("bash -c 'echo hello'")
        assert is_valid
        assert error == ""

    def test_valid_git_command(self):
        """Git commands should be valid."""
        is_valid, error = self.queue._validate_command("git status")
        assert is_valid
        assert error == ""

    def test_valid_absolute_path(self):
        """Absolute paths should be valid."""
        is_valid, error = self.queue._validate_command("/usr/bin/python3 script.py")
        assert is_valid
        assert error == ""

    def test_valid_relative_path(self):
        """Relative paths should be valid."""
        is_valid, error = self.queue._validate_command("./scripts/run.sh")
        assert is_valid
        assert error == ""

    def test_valid_pip_command(self):
        """Pip commands should be valid."""
        is_valid, error = self.queue._validate_command("pip install requests")
        assert is_valid
        assert error == ""

    def test_valid_piped_command(self):
        """Piped commands should be valid."""
        is_valid, error = self.queue._validate_command("cat file.txt | grep pattern")
        assert is_valid
        assert error == ""

    def test_invalid_ai_prompt_measure(self):
        """AI prompt starting with 'Measure' should be rejected."""
        is_valid, error = self.queue._validate_command(
            "Measure context compression ratio by comparing three format types"
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_invalid_ai_prompt_analyze(self):
        """AI prompt starting with 'Analyze' should be rejected."""
        is_valid, error = self.queue._validate_command(
            "Analyze the effectiveness of different context injection strategies"
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_invalid_ai_prompt_with_question(self):
        """AI prompt ending with question mark should be rejected."""
        is_valid, error = self.queue._validate_command(
            "What is the optimal context window size for code generation?"
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_invalid_ai_prompt_with_please(self):
        """AI prompt containing 'please' should be rejected."""
        is_valid, error = self.queue._validate_command(
            "Please generate a report on bandwidth metrics"
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_invalid_ai_prompt_create(self):
        """AI prompt starting with 'Create a' should be rejected."""
        is_valid, error = self.queue._validate_command(
            "Create a comprehensive analysis of human-AI collaboration patterns"
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_add_task_rejects_ai_prompt(self):
        """add_task should raise ValueError for AI prompts."""
        with pytest.raises(ValueError) as exc_info:
            self.queue.add_task(
                command="Analyze the bandwidth metrics and generate a report",
                task_type="research",
                description="Run bandwidth analysis",
            )
        assert "AI prompt" in str(exc_info.value)

    def test_add_task_accepts_shell_command(self):
        """add_task should accept valid shell commands."""
        task = self.queue.add_task(
            command="python -m cortex briefing",
            task_type="general",
            description="Generate morning briefing",
        )
        assert task.command == "python -m cortex briefing"

    def test_add_task_skip_validation(self):
        """add_task with skip_validation=True should allow AI prompts."""
        # This is an escape hatch - use with caution
        task = self.queue.add_task(
            command="Analyze this for me please",
            task_type="special",
            description="Special case",
            skip_validation=True,
        )
        assert task.command == "Analyze this for me please"


class TestRealWorldFailures:
    """Test cases from actual failed batch tasks."""

    def setup_method(self):
        """Create a batch queue with temp directory."""
        from intelligence.process_monitor.batch_queue import BatchTaskQueue

        self.tmpdir = tempfile.mkdtemp()
        self.queue = BatchTaskQueue(db_path=Path(self.tmpdir) / "test_queue.db")

    def test_context_compression_prompt(self):
        """Real failed task: context compression experiment."""
        is_valid, error = self.queue._validate_command(
            "Measure context compression ratio by comparing three format types "
            "(narrative, structured JSON, hybrid) across 10 coding scenarios. "
            "For each scenario, provide the same task using all three formats..."
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_trust_calibration_prompt(self):
        """Real failed task: trust calibration experiment."""
        is_valid, error = self.queue._validate_command(
            "Generate 20 predictions about code behavior with varying confidence "
            "levels (0.5-0.95). For each prediction, include: 1) The code snippet..."
        )
        assert not is_valid
        assert "AI prompt" in error

    def test_handoff_protocol_prompt(self):
        """Real failed task: handoff protocol experiment."""
        is_valid, error = self.queue._validate_command(
            "Design an optimal session handoff protocol based on context "
            "compression findings. Create 5 handoff templates that maximize "
            "context retention while minimizing token usage..."
        )
        assert not is_valid
        assert "AI prompt" in error
