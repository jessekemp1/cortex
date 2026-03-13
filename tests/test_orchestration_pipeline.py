"""
Tests for the full orchestration pipeline (Phases 3-6).

Tests:
  - AgentDispatcher: prompt construction, timeout, concurrency
  - AgentProfile: registry, task matching, system prompts
  - ResultCollector: collection, summaries, persistence, outcomes
  - CortexSupervisor.orchestrate(): end-to-end pipeline wiring
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add cortex directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supervisor.agents import (
    AGENT_REGISTRY,
    get_agent_by_name,
    get_agent_for_task,
    list_agents,
)
from supervisor.collector import BatchSummary, ResultCollector, _tier_from_model_id
from supervisor.dispatch import AgentDispatcher, DispatchResult
from supervisor.dispatch import ModelSelection as DispatchModelSelection
from supervisor.models import WorkItem, WorkItemPriority


# ── Fixtures ──


def _mock_find_repos(self):
    return []


def _mock_analyze(self, repo_path):
    from ai_intelligence import ProjectActivity

    return ProjectActivity(
        name=repo_path.name if hasattr(repo_path, "name") else "mock",
        path=repo_path,
        status="active",
        commits_7d=1,
        commits_30d=5,
        files_changed_7d=2,
        uncommitted_changes=0,
    )


@pytest.fixture(autouse=True)
def _patch_slow_operations():
    """Patch slow operations for all tests in this module."""
    mock_pm = MagicMock()
    mock_pm.alert_generator.generate_alerts.return_value = []

    with (
        patch("ai_intelligence.ProjectScanner.find_git_repos", _mock_find_repos),
        patch("ai_intelligence.ProjectScanner.find_projects", _mock_find_repos),
        patch("ai_intelligence.ProjectScanner.analyze_project", _mock_analyze),
        patch("recommendation_engine.ProcessMonitor", return_value=mock_pm),
        patch(
            "recommendation_engine.RecommendationEngine._enrich_with_patterns",
            lambda self, recs: recs,
        ),
    ):
        yield


# ── Agent Profiles ──


class TestAgentProfiles:
    def test_registry_has_expected_agents(self):
        names = set(AGENT_REGISTRY.keys())
        assert "architect" in names
        assert "test_engineer" in names
        assert "researcher" in names
        assert "implementer" in names
        assert "classifier" in names

    def test_get_agent_for_task_test(self):
        agent = get_agent_for_task("test")
        assert agent is not None
        assert agent.name == "test_engineer"

    def test_get_agent_for_task_research(self):
        agent = get_agent_for_task("research")
        assert agent is not None
        assert agent.name == "researcher"

    def test_get_agent_for_task_unknown(self):
        agent = get_agent_for_task("underwater_basket_weaving")
        assert agent is None

    def test_get_agent_by_name(self):
        agent = get_agent_by_name("architect")
        assert agent is not None
        assert agent.preferred_model_tier == "opus"

    def test_list_agents(self):
        agents = list_agents()
        assert len(agents) == len(AGENT_REGISTRY)

    def test_agent_build_system_prompt(self):
        agent = get_agent_by_name("test_engineer")
        prompt = agent.build_system_prompt(project="vortex", context="Backend API tests")
        assert "vortex" in prompt
        assert "Backend API tests" in prompt

    def test_classifier_has_short_timeout(self):
        agent = get_agent_by_name("classifier")
        assert agent.timeout_seconds == 60

    def test_architect_prefers_opus(self):
        agent = get_agent_by_name("architect")
        assert agent.preferred_model_tier == "opus"


# ── AgentDispatcher ──


class TestAgentDispatcher:
    @pytest.fixture
    def dispatcher(self):
        test_key = "test-key-not-real"  # pragma: allowlist secret
        return AgentDispatcher(api_key=test_key, max_concurrent=2)

    @pytest.fixture
    def work_item(self):
        return WorkItem(
            id="wi_test123",
            source="test",
            task_type="test",
            description="Run unit tests for the auth module",
            project="vortex",
            files=["app/auth.py", "tests/test_auth.py"],
            metadata={"coverage_target": "90%"},
        )

    @pytest.fixture
    def model_selection(self):
        return DispatchModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="Test task -> sonnet",
            complexity_score=0.4,
            confidence=0.7,
        )

    def test_build_prompt_from_description(self, dispatcher, work_item):
        work_item.prompt = None
        work_item.command = None
        prompt = dispatcher._build_prompt(work_item)
        assert "Run unit tests" in prompt
        assert "app/auth.py" in prompt
        assert "coverage_target" in prompt

    def test_build_prompt_from_explicit_prompt(self, dispatcher, work_item):
        work_item.prompt = "Custom prompt text"
        prompt = dispatcher._build_prompt(work_item)
        assert "Custom prompt text" in prompt

    def test_build_prompt_from_command(self, dispatcher, work_item):
        work_item.prompt = None
        work_item.command = "pytest tests/ -v"
        prompt = dispatcher._build_prompt(work_item)
        assert "pytest tests/ -v" in prompt
        assert "Execute the following command" in prompt

    def test_build_system_prompt_default(self, dispatcher, work_item):
        work_item.system_prompt = None
        sys_prompt = dispatcher._build_system_prompt(work_item)
        # Agent profiles are used when task_type matches a registered agent
        assert "vortex" in sys_prompt
        # "test" task_type matches test_engineer agent profile
        assert "test" in sys_prompt.lower()

    def test_build_system_prompt_custom(self, dispatcher, work_item):
        work_item.system_prompt = "You are a specialized tester."
        sys_prompt = dispatcher._build_system_prompt(work_item)
        assert sys_prompt == "You are a specialized tester."

    @patch("cortex.supervisor.dispatch.ANTHROPIC_SDK_AVAILABLE", False)
    def test_dispatch_uses_direct_api_fallback(self, dispatcher, work_item, model_selection):
        """When Agent SDK unavailable, falls back to direct API."""
        with patch.object(dispatcher, "_run_dispatch", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Test output", 500)
            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is True
        assert result.output == "Test output"
        assert result.tokens_used == 500
        assert result.model_used == "claude-sonnet-4-6"

    @patch("cortex.supervisor.dispatch.ANTHROPIC_SDK_AVAILABLE", False)
    def test_dispatch_handles_api_error(self, dispatcher, work_item, model_selection):
        """API errors are caught and returned as failed results."""

        async def fail(*args, **kwargs):
            raise RuntimeError("API key invalid")

        with patch.object(dispatcher, "_run_dispatch", side_effect=fail):
            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is False
        assert "API key invalid" in result.error


# ── ResultCollector ──


class TestResultCollector:
    @pytest.fixture
    def collector(self, tmp_path):
        return ResultCollector(
            results_dir=tmp_path / "runs",
            outcomes_path=tmp_path / "outcomes.jsonl",
        )

    @pytest.fixture
    def success_result(self):
        return DispatchResult(
            work_item_id="wi_abc",
            success=True,
            output="All tests passed",
            model_used="claude-sonnet-4-6",
            tokens_used=1200,
            duration_seconds=3.5,
        )

    @pytest.fixture
    def failure_result(self):
        return DispatchResult(
            work_item_id="wi_def",
            success=False,
            output="",
            model_used="claude-haiku-4-5-20251001",
            tokens_used=200,
            duration_seconds=1.0,
            error="Rate limited",
        )

    def test_collect_single(self, collector, success_result):
        collector.collect(success_result)
        summary = collector.get_summary()
        assert summary.total == 1
        assert summary.succeeded == 1

    def test_collect_batch(self, collector, success_result, failure_result):
        summary = collector.collect_batch([success_result, failure_result])
        assert summary.total == 2
        assert summary.succeeded == 1
        assert summary.failed == 1
        assert summary.total_tokens == 1400
        assert "sonnet" in summary.model_breakdown
        assert "haiku" in summary.model_breakdown

    def test_persist(self, collector, success_result, failure_result):
        collector.collect(success_result)
        collector.collect(failure_result)
        run_dir = collector.persist()

        assert run_dir.exists()
        results_file = run_dir / "results.json"
        summary_file = run_dir / "summary.json"
        assert results_file.exists()
        assert summary_file.exists()

        results = json.loads(results_file.read_text())
        assert len(results) == 2

        summary = json.loads(summary_file.read_text())
        assert summary["total"] == 2

    def test_record_outcome(self, collector, success_result, tmp_path):
        collector.record_outcome(success_result, quality_score=0.95)
        outcomes_path = tmp_path / "outcomes.jsonl"
        assert outcomes_path.exists()

        lines = outcomes_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["work_item_id"] == "wi_abc"
        assert entry["model_tier"] == "sonnet"
        assert entry["success"] is True

    def test_record_outcome_includes_task_type(self, collector, tmp_path):
        """Collector must propagate task_type from DispatchResult to outcome records."""
        result = DispatchResult(
            work_item_id="wi_typed",
            success=True,
            output="Done",
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
            task_type="security",
        )
        collector.record_outcome(result, quality_score=0.85)
        outcomes_path = tmp_path / "outcomes.jsonl"
        entry = json.loads(outcomes_path.read_text().strip())
        assert entry["task_type"] == "security"

    def test_clear(self, collector, success_result):
        collector.collect(success_result)
        assert collector.get_summary().total == 1
        collector.clear()
        assert collector.get_summary().total == 0


class TestTierFromModelId:
    def test_opus(self):
        assert _tier_from_model_id("claude-opus-4-6") == "opus"

    def test_sonnet(self):
        assert _tier_from_model_id("claude-sonnet-4-6") == "sonnet"

    def test_haiku(self):
        assert _tier_from_model_id("claude-haiku-4-5-20251001") == "haiku"

    def test_unknown(self):
        assert _tier_from_model_id("gpt-4") == "unknown"


# ── Supervisor Orchestration Wiring (Phase 6) ──


class TestSupervisorOrchestrate:
    """Test the full pipeline: discover -> route -> dispatch -> collect."""

    @patch("cortex.supervisor.dispatch.ANTHROPIC_SDK_AVAILABLE", False)
    def test_orchestrate_with_work_items(self, tmp_path):
        """orchestrate() with explicit work items routes and dispatches them."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            approval_policy="auto_all",
            state_file=tmp_path / "state.json",
        )
        supervisor = CortexSupervisor(config=config)

        items = [
            WorkItem(
                id="wi_test1",
                source="test",
                task_type="test",
                description="Run tests",
                priority=WorkItemPriority.HIGH,
            ),
        ]

        mock_result = DispatchResult(
            work_item_id="wi_test1",
            success=True,
            output="Tests passed",
            model_used="claude-sonnet-4-6",
            tokens_used=800,
            duration_seconds=2.0,
        )

        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
        ):
            mock_dispatcher = MagicMock()
            mock_dispatcher.dispatch.return_value = mock_result
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=1,
                succeeded=1,
                failed=0,
                total_tokens=800,
                total_duration_seconds=2.0,
                model_breakdown={"sonnet": 1},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            result = supervisor.orchestrate(work_items=items)

        assert result["status"] == "completed"
        assert result["items_found"] == 1
        assert result["items_dispatched"] == 1

    def test_orchestrate_no_work(self):
        """orchestrate() with no discoverable work returns no_work status."""
        from supervisor.core import CortexSupervisor

        supervisor = CortexSupervisor()

        with patch.object(supervisor, "_discover_work", return_value=[]):
            result = supervisor.orchestrate()

        assert result["status"] == "no_work"

    def test_work_discovery_called_on_tick(self):
        """tick() calls _discover_work when work_discovery interval elapsed."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            work_discovery_interval_seconds=0,
            enable_work_discovery=True,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        mock_items = [
            WorkItem(
                id="wi_disc1",
                source="goals",
                task_type="feature",
                description="Implement dashboard",
            ),
        ]

        with (
            patch.object(supervisor, "_discover_work", return_value=mock_items),
            patch.object(
                supervisor,
                "_dispatch_work_items",
                return_value={
                    "queued": 1,
                    "dispatched": 1,
                    "succeeded": 1,
                    "failed": 0,
                    "errors": [],
                },
            ),
        ):
            result = supervisor.tick()

        assert result.work_discovered == 1
        assert len(result.work_items) == 1

    def test_work_discovery_skipped_when_disabled(self):
        """tick() skips work discovery when feature flag is off."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            enable_work_discovery=False,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        result = supervisor.tick()
        assert result.work_discovered == 0


# ── Quality Evaluator Tests ──


class TestQualityEvaluator:
    """Test QualityEvaluator heuristic scoring (replaces _estimate_quality)."""

    def _make_result(self, success=True, output=""):
        return DispatchResult(
            work_item_id="wi_test",
            success=success,
            output=output,
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
        )

    def _make_work_item(self, task_type="implement"):
        from unittest.mock import MagicMock

        wi = MagicMock()
        wi.task_type = task_type
        wi.description = "Fix the authentication module"
        return wi

    def _evaluate(self, result, task_type="implement"):
        from supervisor.core import _get_quality_evaluator

        return _get_quality_evaluator().evaluate_heuristic(
            self._make_work_item(task_type),
            result,
        )

    def test_failed_result_scores_zero(self):
        result = self._make_result(success=False, output="Error occurred")
        evaluation = self._evaluate(result)
        assert evaluation.overall_score == 0.0

    def test_short_output_scores_low(self):
        result = self._make_result(output="OK")
        evaluation = self._evaluate(result)
        assert evaluation.overall_score < 0.4

    def test_refusal_output_scores_low(self):
        result = self._make_result(
            output="I cannot complete this task. Please provide more context and clarification."
        )
        evaluation = self._evaluate(result)
        assert evaluation.overall_score < 0.5

    def test_structured_output_scores_high(self):
        output = """# Analysis Report

## Findings

```python
def fix_bug():
    return True
```

| Metric | Value |
|--------|-------|
| Tests  | 42    |
"""
        result = self._make_result(output=output)
        evaluation = self._evaluate(result)
        assert evaluation.overall_score >= 0.6

    def test_moderate_output_scores_medium(self):
        result = self._make_result(
            output="The authentication module has a race condition in the token refresh logic. "
            "When two requests arrive simultaneously, both attempt to refresh the token."
        )
        evaluation = self._evaluate(result)
        assert 0.3 <= evaluation.overall_score <= 0.8

    def test_output_with_one_structured_signal(self):
        result = self._make_result(output="Here is the fix:\n```python\nprint('hello')\n```")
        evaluation = self._evaluate(result)
        assert evaluation.overall_score >= 0.4


# ── Routing Integration Tests ──


class TestRoutingIntegration:
    """Test that task types from intake correctly route to expected model tiers."""

    def test_architecture_routes_to_opus(self):
        from supervisor.intake import _infer_task_type
        from supervisor.router import ModelRouter

        task_type = _infer_task_type("Redesign the authentication architecture")
        assert task_type == "architecture"

        router = ModelRouter(outcomes_path=Path("/dev/null"))
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type=task_type,
            description="Redesign the authentication architecture",
            priority=WorkItemPriority.HIGH,
        )
        selection = router.select_model(item)
        assert selection.model_tier == "opus"

    def test_security_routes_to_opus(self):
        from supervisor.intake import _infer_task_type
        from supervisor.router import ModelRouter

        task_type = _infer_task_type("Audit security vulnerabilities in API endpoints")
        assert task_type == "security"

        router = ModelRouter(outcomes_path=Path("/dev/null"))
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type=task_type,
            description="Audit security vulnerabilities",
            priority=WorkItemPriority.HIGH,
        )
        selection = router.select_model(item)
        assert selection.model_tier == "opus"

    def test_classify_routes_to_haiku(self):
        from supervisor.intake import _infer_task_type
        from supervisor.router import ModelRouter

        task_type = _infer_task_type("Classify and triage incoming support tickets")
        assert task_type == "classify"

        router = ModelRouter(outcomes_path=Path("/dev/null"))
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type=task_type,
            description="Classify and triage incoming support tickets",
            priority=WorkItemPriority.LOW,
        )
        selection = router.select_model(item)
        assert selection.model_tier == "haiku"

    def test_test_routes_to_sonnet(self):
        from supervisor.intake import _infer_task_type
        from supervisor.router import ModelRouter

        task_type = _infer_task_type("Write unit tests for the payment module")
        assert task_type == "test"

        router = ModelRouter(outcomes_path=Path("/dev/null"))
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type=task_type,
            description="Write unit tests for the payment module",
            priority=WorkItemPriority.MEDIUM,
        )
        selection = router.select_model(item)
        assert selection.model_tier == "sonnet"

    def test_agent_profile_used_in_dispatch(self):
        """Dispatcher uses agent profiles for system prompts when available."""
        dispatcher = AgentDispatcher()
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type="test",
            description="Write tests",
            project="vortex",
        )
        prompt = dispatcher._build_system_prompt(item)
        # Should use test_engineer agent profile, not generic
        assert "test engineer" in prompt.lower()
        assert "vortex" in prompt

    def test_generic_task_type_gets_fallback_prompt(self):
        """Unmatched task types get the generic system prompt."""
        dispatcher = AgentDispatcher()
        item = WorkItem(
            id="wi_test",
            source="test",
            task_type="unknown_type",
            description="Do something unusual",
        )
        prompt = dispatcher._build_system_prompt(item)
        assert "execution agent" in prompt


# ── Phase 2: Tool-Use Dispatch Loop Tests ──


class TestToolExecution:
    """Tests for tool execution in the dispatch loop."""

    @pytest.fixture
    def dispatcher(self):
        test_key = "test-key-not-real"  # pragma: allowlist secret
        return AgentDispatcher(api_key=test_key, max_concurrent=2)

    def test_tool_execution_read_file(self, dispatcher, tmp_path):
        """read_file tool reads a file and returns contents."""
        test_file = tmp_path / "hello.py"
        test_file.write_text("print('hello world')")

        result = dispatcher._execute_tool("read_file", {"path": str(test_file)}, str(tmp_path))
        assert "print('hello world')" in result

    def test_tool_execution_path_traversal_blocked(self, dispatcher, tmp_path):
        """read_file blocks path traversal attacks."""
        result = dispatcher._execute_tool("read_file", {"path": "../../etc/passwd"}, str(tmp_path))
        assert "error" in result.lower() or "denied" in result.lower()

    def test_tool_execution_read_file_not_found(self, dispatcher, tmp_path):
        """read_file returns error for missing files."""
        result = dispatcher._execute_tool(
            "read_file", {"path": str(tmp_path / "nonexistent.py")}, str(tmp_path)
        )
        assert "error" in result.lower() or "not found" in result.lower()

    def test_tool_execution_search_code(self, dispatcher, tmp_path):
        """search_code finds pattern matches in files."""
        (tmp_path / "a.py").write_text("def hello():\n    return 'world'")
        (tmp_path / "b.py").write_text("x = 42")

        result = dispatcher._execute_tool(
            "search_code", {"pattern": "hello", "path": str(tmp_path)}, str(tmp_path)
        )
        assert "hello" in result
        assert "a.py" in result

    def test_tool_execution_list_files(self, dispatcher, tmp_path):
        """list_files returns matching file paths."""
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        (tmp_path / "c.txt").write_text("z")

        result = dispatcher._execute_tool(
            "list_files", {"pattern": "*.py", "path": str(tmp_path)}, str(tmp_path)
        )
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    def test_tool_execution_unknown_tool(self, dispatcher, tmp_path):
        """Unknown tools return an error message."""
        result = dispatcher._execute_tool("delete_everything", {}, str(tmp_path))
        assert "unknown" in result.lower() or "error" in result.lower()

    def test_tool_execution_search_path_traversal_blocked(self, dispatcher, tmp_path):
        """search_code blocks path traversal."""
        result = dispatcher._execute_tool(
            "search_code", {"pattern": "secret", "path": "/etc"}, str(tmp_path)
        )
        assert "error" in result.lower() or "denied" in result.lower()


class TestToolUseDispatchLoop:
    """Tests for the multi-turn tool-use dispatch loop."""

    @pytest.fixture
    def dispatcher(self):
        test_key = "test-key-not-real"  # pragma: allowlist secret
        return AgentDispatcher(api_key=test_key, max_concurrent=2)

    @pytest.fixture
    def work_item(self):
        return WorkItem(
            id="wi_tool_test",
            source="test",
            task_type="research",
            description="Analyze the router module",
            project="cortex",
        )

    @pytest.fixture
    def model_selection(self):
        return DispatchModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="Research task -> sonnet",
            complexity_score=0.5,
            confidence=0.7,
        )

    def _make_text_response(self, text, input_tokens=100, output_tokens=50):
        """Create a mock response with only text blocks."""
        mock_resp = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = text
        mock_resp.content = [text_block]
        mock_resp.usage = MagicMock()
        mock_resp.usage.input_tokens = input_tokens
        mock_resp.usage.output_tokens = output_tokens
        return mock_resp

    def _make_tool_use_response(
        self, tool_name, tool_input, tool_id="tool_1", input_tokens=100, output_tokens=50
    ):
        """Create a mock response with a tool_use block."""
        mock_resp = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = tool_name
        tool_block.input = tool_input
        tool_block.id = tool_id
        mock_resp.content = [tool_block]
        mock_resp.usage = MagicMock()
        mock_resp.usage.input_tokens = input_tokens
        mock_resp.usage.output_tokens = output_tokens
        return mock_resp

    def test_dispatch_no_tools_single_shot(self, dispatcher, work_item, model_selection):
        """Single-shot dispatch (no tool use) still works — backward compatible."""
        text_resp = self._make_text_response("Analysis complete: router is healthy")

        with patch.object(dispatcher, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = text_resp
            mock_client_fn.return_value = mock_client

            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is True
        assert "router is healthy" in result.output
        assert result.tokens_used == 150  # 100 + 50
        # Only one API call (no tool loop)
        assert mock_client.messages.create.call_count == 1

    def test_dispatch_with_tool_use_read_file(
        self, dispatcher, work_item, model_selection, tmp_path
    ):
        """Tool-use loop: model requests read_file, gets result, then responds."""
        # Turn 1: model requests read_file
        tool_resp = self._make_tool_use_response(
            "read_file", {"path": str(tmp_path / "test.py")}, "tool_read_1"
        )
        # Turn 2: model responds with text
        text_resp = self._make_text_response("The file contains a test function", 200, 100)

        # Create the file for tool to read
        (tmp_path / "test.py").write_text("def test_foo(): pass")

        with patch.object(dispatcher, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [tool_resp, text_resp]
            mock_client_fn.return_value = mock_client

            # Need to set project_root for tool execution
            work_item.metadata["project_root"] = str(tmp_path)
            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is True
        assert "test function" in result.output
        # Two API calls: initial + after tool result
        assert mock_client.messages.create.call_count == 2
        # Tokens sum both turns
        assert result.tokens_used == 150 + 300  # (100+50) + (200+100)

    def test_dispatch_max_turns_exceeded(self, dispatcher, work_item, model_selection):
        """Dispatch stops after max_turns even if model keeps requesting tools."""
        # Always return tool_use (infinite loop scenario)
        tool_resp = self._make_tool_use_response("list_files", {"pattern": "*.py"}, "tool_inf")

        with patch.object(dispatcher, "_get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = tool_resp
            mock_client_fn.return_value = mock_client

            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is True
        # Should have stopped at max_turns (10)
        assert mock_client.messages.create.call_count == 10
        assert "max turns" in result.output.lower() or result.output != ""


# ── Phase 2: Work Deduplication Tests ──


class TestWorkDeduplication:
    """Tests for work item dedup tracking across ticks."""

    def _make_supervisor(self, tmp_path):
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            enable_work_discovery=True,
            enable_ai_batching=True,
            enable_self_healing=False,
            work_discovery_interval_seconds=0,  # Always discover
            approval_policy="auto_all",
            state_file=tmp_path / "state.json",
        )
        supervisor = CortexSupervisor(config=config)
        return supervisor

    def test_dispatched_items_not_rediscovered(self, tmp_path):
        """Items dispatched in tick 1 are skipped in tick 2."""
        supervisor = self._make_supervisor(tmp_path)

        item = WorkItem(
            id="wi_dup1",
            source="goals",
            task_type="test",
            description="Run unit tests for auth",
            priority=WorkItemPriority.HIGH,
        )

        mock_result = DispatchResult(
            work_item_id="wi_dup1",
            success=True,
            output="Tests passed",
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
        )

        with (
            patch.object(supervisor, "_discover_work", return_value=[item]),
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
        ):
            mock_dispatcher = MagicMock()
            mock_dispatcher.dispatch.return_value = mock_result
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=1,
                succeeded=1,
                failed=0,
                total_tokens=100,
                total_duration_seconds=1.0,
                model_breakdown={"sonnet": 1},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            # Tick 1: should dispatch
            result1 = supervisor.tick()
            assert result1.ai_tasks_dispatched == 1

            # Tick 2: same item rediscovered — should be skipped
            result2 = supervisor.tick()
            assert result2.ai_tasks_dispatched == 0

    def test_similar_descriptions_deduped(self, tmp_path):
        """Items with similar descriptions are treated as duplicates."""
        supervisor = self._make_supervisor(tmp_path)

        item1 = WorkItem(
            id="wi_sim1",
            source="goals",
            task_type="test",
            description="Run unit tests for auth module",
        )
        item2 = WorkItem(
            id="wi_sim2",
            source="goals",
            task_type="test",
            description="Run unit tests for authentication module",
        )

        mock_result = DispatchResult(
            work_item_id="wi_sim1",
            success=True,
            output="OK",
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
        )

        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
        ):
            mock_dispatcher = MagicMock()
            mock_dispatcher.dispatch.return_value = mock_result
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=1,
                succeeded=1,
                failed=0,
                total_tokens=100,
                total_duration_seconds=1.0,
                model_breakdown={"sonnet": 1},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            # Tick 1: dispatch item1
            with patch.object(supervisor, "_discover_work", return_value=[item1]):
                supervisor.tick()

            # Tick 2: discover item2 (similar description) — should be skipped
            with patch.object(supervisor, "_discover_work", return_value=[item2]):
                result = supervisor.tick()

            assert result.ai_tasks_dispatched == 0

    def test_different_items_not_blocked(self, tmp_path):
        """Different work items are dispatched normally."""
        supervisor = self._make_supervisor(tmp_path)

        item1 = WorkItem(
            id="wi_diff1",
            source="goals",
            task_type="test",
            description="Run unit tests",
        )
        item2 = WorkItem(
            id="wi_diff2",
            source="goals",
            task_type="deploy",
            description="Deploy to production environment",
        )

        mock_result1 = DispatchResult(
            work_item_id="wi_diff1",
            success=True,
            output="OK",
            model_used="claude-sonnet-4-6",
            tokens_used=100,
            duration_seconds=1.0,
        )
        mock_result2 = DispatchResult(
            work_item_id="wi_diff2",
            success=True,
            output="Deployed",
            model_used="claude-haiku-4-5-20251001",
            tokens_used=50,
            duration_seconds=0.5,
        )

        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
        ):
            mock_dispatcher = MagicMock()
            mock_dispatcher.dispatch.side_effect = [mock_result1, mock_result2]
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=1,
                succeeded=1,
                failed=0,
                total_tokens=100,
                total_duration_seconds=1.0,
                model_breakdown={"sonnet": 1},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            with patch.object(supervisor, "_discover_work", return_value=[item1]):
                supervisor.tick()

            with patch.object(supervisor, "_discover_work", return_value=[item2]):
                result = supervisor.tick()

            # item2 is different — should dispatch
            assert result.ai_tasks_dispatched == 1


# ── Phase 3: Shell Routing Tests ──


class TestShellRouting:
    """Tests for routing work items with commands to shell executor."""

    def test_work_item_with_command_routes_to_shell(self, tmp_path):
        """WorkItems with command field route to shell queue, not AI."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            enable_work_discovery=False,
            enable_ai_batching=True,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        item = WorkItem(
            id="wi_shell1",
            source="goals",
            task_type="test",
            description="Run pytest",
            command="pytest tests/ -v",
            priority=WorkItemPriority.HIGH,
        )

        supervisor._pending_work_items = [item]

        # Mock the AI dispatcher — should NOT be called for shell items
        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
            patch.object(supervisor.shell_queue, "add_task") as mock_add_task,
        ):
            mock_dispatcher = MagicMock()
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=0,
                succeeded=0,
                failed=0,
                total_tokens=0,
                total_duration_seconds=0,
                model_breakdown={},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            supervisor._dispatch_work_items()

        # Shell queue should have received the task
        mock_add_task.assert_called_once()
        call_kwargs = mock_add_task.call_args
        # Check it was called with the right command
        assert "pytest tests/ -v" in str(call_kwargs)
        # AI dispatcher should NOT have been called
        mock_dispatcher.dispatch.assert_not_called()

    def test_work_item_without_command_routes_to_ai(self, tmp_path):
        """WorkItems without command field route to AI dispatcher."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            enable_work_discovery=False,
            enable_ai_batching=True,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        item = WorkItem(
            id="wi_ai1",
            source="goals",
            task_type="research",
            description="Analyze the authentication module",
            priority=WorkItemPriority.MEDIUM,
        )

        supervisor._pending_work_items = [item]

        mock_result = DispatchResult(
            work_item_id="wi_ai1",
            success=True,
            output="Analysis done",
            model_used="claude-sonnet-4-6",
            tokens_used=500,
            duration_seconds=2.0,
        )

        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
            patch.object(supervisor.shell_queue, "add_task") as mock_add_task,
        ):
            mock_dispatcher = MagicMock()
            mock_dispatcher.dispatch.return_value = mock_result
            mock_get_disp.return_value = mock_dispatcher

            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=1,
                succeeded=1,
                failed=0,
                total_tokens=500,
                total_duration_seconds=2.0,
                model_breakdown={"sonnet": 1},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            summary = supervisor._dispatch_work_items()

        # AI dispatcher should have been called
        mock_dispatcher.dispatch.assert_called_once()
        # Shell queue should NOT have been used
        mock_add_task.assert_not_called()
        assert summary["dispatched"] == 1

    def test_shell_routed_task_has_correct_metadata(self, tmp_path):
        """Shell-routed tasks carry work_item_id in metadata."""
        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        config = SupervisorConfig(
            enable_work_discovery=False,
            enable_ai_batching=True,
            enable_self_healing=False,
        )
        supervisor = CortexSupervisor(config=config)

        item = WorkItem(
            id="wi_meta1",
            source="goals",
            task_type="deploy",
            description="Deploy app",
            command="./deploy.sh",
            priority=WorkItemPriority.HIGH,
        )

        supervisor._pending_work_items = [item]

        with (
            patch.object(supervisor, "_get_dispatcher") as mock_get_disp,
            patch.object(supervisor, "_get_collector") as mock_get_coll,
            patch.object(supervisor.shell_queue, "add_task") as mock_add_task,
        ):
            mock_get_disp.return_value = MagicMock()
            mock_collector = MagicMock()
            mock_collector.get_summary.return_value = BatchSummary(
                total=0,
                succeeded=0,
                failed=0,
                total_tokens=0,
                total_duration_seconds=0,
                model_breakdown={},
                errors=[],
            )
            mock_get_coll.return_value = mock_collector

            supervisor._dispatch_work_items()

        mock_add_task.assert_called_once()
        call_kwargs = mock_add_task.call_args
        assert "work_item_id" in str(call_kwargs)


# ── Phase 4: Dry-Run Mode Tests ──


class TestDryRunMode:
    """Tests for dry-run mode that skips API calls."""

    def test_dry_run_does_not_call_api(self):
        """Dispatcher with dry_run=True returns synthetic result without API call."""
        dispatcher = AgentDispatcher(dry_run=True)

        item = WorkItem(
            id="wi_dry1",
            source="test",
            task_type="research",
            description="Analyze something",
        )
        selection = DispatchModelSelection(
            model_tier="sonnet",
            model_id="claude-sonnet-4-6",
            reasoning="test",
            complexity_score=0.5,
            confidence=0.7,
        )

        with patch.object(dispatcher, "_get_client") as mock_client_fn:
            result = dispatcher.dispatch(item, selection)

        # Client should never have been created
        mock_client_fn.assert_not_called()
        assert result.success is True
        assert "[DRY RUN]" in result.output
        assert result.tokens_used == 0

    def test_dry_run_flag_in_config(self):
        """SupervisorConfig has dry_run flag."""
        from supervisor.config import SupervisorConfig

        config = SupervisorConfig(dry_run=True)
        assert config.dry_run is True

        default = SupervisorConfig()
        assert default.dry_run is False


# ── Phase 5: GOALS.md File Watcher Tests ──


class TestGoalsWatcher:
    """Tests for stat-based GOALS.md mtime watcher."""

    @pytest.fixture(autouse=True)
    def _isolate_env(self):
        """Save and restore CORTEX_ROOT_DIR to avoid leaking into other tests."""
        import os

        orig = os.environ.get("CORTEX_ROOT_DIR")
        yield
        if orig is None:
            os.environ.pop("CORTEX_ROOT_DIR", None)
        else:
            os.environ["CORTEX_ROOT_DIR"] = orig

    def _make_supervisor(self, goals_dir):
        """Create a supervisor with CORTEX_ROOT_DIR pointing at goals_dir."""
        import os

        from supervisor.config import SupervisorConfig
        from supervisor.core import CortexSupervisor

        os.environ["CORTEX_ROOT_DIR"] = str(goals_dir)
        config = SupervisorConfig(
            enable_work_discovery=True,
            enable_ai_batching=False,
            enable_self_healing=False,
            watch_goals=True,
            work_discovery_interval_seconds=9999,  # Never trigger by interval
            state_file=goals_dir / "supervisor_state.json",
        )
        return CortexSupervisor(config=config)

    def test_goals_first_check_returns_false(self, tmp_path):
        """Initial mtime=0 should NOT trigger (avoids startup storm)."""
        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\n- Ship it\n")

        supervisor = self._make_supervisor(tmp_path)
        assert supervisor._goals_mtime == 0.0
        assert supervisor._goals_file_changed() is False
        # mtime should now be set (no longer 0)
        assert supervisor._goals_mtime > 0

    def test_goals_change_triggers_discovery(self, tmp_path):
        """Modify a GOALS.md file, verify _goals_file_changed() returns True."""
        import time as _time

        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\n- Ship it\n")

        supervisor = self._make_supervisor(tmp_path)
        # First call initializes
        supervisor._goals_file_changed()

        # Modify the file (ensure mtime advances)
        _time.sleep(0.05)
        goals.write_text("# Goals\n- Ship it\n- New goal\n")

        assert supervisor._goals_file_changed() is True

    def test_goals_no_change_returns_false(self, tmp_path):
        """Call twice without modifying — second call returns False."""
        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\n- Ship it\n")

        supervisor = self._make_supervisor(tmp_path)
        # Initialize
        supervisor._goals_file_changed()
        # No change
        assert supervisor._goals_file_changed() is False

    def test_goals_missing_file_returns_false(self, tmp_path):
        """Nonexistent GOALS.md returns False."""
        # Point at a dir with no GOALS.md
        supervisor = self._make_supervisor(tmp_path)
        assert supervisor._goals_file_changed() is False

    def test_should_run_work_discovery_with_goals_change(self, tmp_path):
        """_should_run_work_discovery() returns True when goals changed, even if interval not elapsed."""
        import time as _time

        goals = tmp_path / "GOALS.md"
        goals.write_text("# Goals\n- Ship it\n")

        supervisor = self._make_supervisor(tmp_path)
        # Initialize the mtime
        supervisor._goals_file_changed()
        # Set last discovery to now so interval hasn't elapsed
        from datetime import datetime

        supervisor._last_work_discovery = datetime.now()  # noqa: DTZ005

        # Without goals change, should NOT trigger (interval is 9999s)
        assert supervisor._should_run_work_discovery() is False

        # Modify GOALS.md
        _time.sleep(0.05)
        goals.write_text("# Goals\n- Ship it\n- New priority\n")

        # Now should trigger via goals change
        assert supervisor._should_run_work_discovery() is True


# ── Batch API tests ──


class TestBatchDispatch:
    """Tests for AgentDispatcher.submit_batch() and retrieve_batch()."""

    def _make_items(self, count=3):
        """Create test (WorkItem, ModelAssignment) tuples."""
        from supervisor.router import ModelAssignment

        items = []
        for i in range(count):
            wi = WorkItem(
                id=f"batch-item-{i}",
                source="test",
                task_type="research",
                description=f"Research task {i}",
                prompt=f"Analyze topic {i}",
                project="cortex",
            )
            ms = ModelAssignment(
                model="sonnet",
                confidence=0.8,
                rationale="batch test",
            )
            items.append((wi, ms))
        return items

    def test_submit_batch_creates_correct_requests(self, tmp_path):
        """submit_batch() builds correct Anthropic request format."""
        mock_client = MagicMock()
        mock_batch = MagicMock()
        mock_batch.id = "msgbatch_test_123"
        mock_client.messages.batches.create.return_value = mock_batch

        dispatcher = AgentDispatcher(api_key="test-key", dry_run=False)

        with (
            patch.object(dispatcher, "_get_client", return_value=mock_client),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            items = self._make_items(3)
            batch_id = dispatcher.submit_batch(items)

        assert batch_id == "msgbatch_test_123"

        # Verify the request structure passed to the API
        call_kwargs = mock_client.messages.batches.create.call_args
        requests = call_kwargs.kwargs.get("requests") or call_kwargs[1].get("requests")
        assert len(requests) == 3

        req0 = requests[0]
        assert req0["custom_id"] == "batch-item-0"
        assert req0["params"]["model"] == "claude-sonnet-4-6"
        assert req0["params"]["max_tokens"] == 4096
        assert req0["params"]["messages"][0]["role"] == "user"
        assert "Analyze topic 0" in req0["params"]["messages"][0]["content"]

    def test_submit_batch_persists_metadata(self, tmp_path):
        """submit_batch() saves batch metadata to disk."""
        import json

        mock_client = MagicMock()
        mock_batch = MagicMock()
        mock_batch.id = "msgbatch_persist_456"
        mock_client.messages.batches.create.return_value = mock_batch

        dispatcher = AgentDispatcher(api_key="test-key", dry_run=False)

        with (
            patch.object(dispatcher, "_get_client", return_value=mock_client),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            items = self._make_items(2)
            dispatcher.submit_batch(items)

        meta_file = tmp_path / ".cortex" / "orchestration" / "batches" / "msgbatch_persist_456.json"
        assert meta_file.exists()

        meta = json.loads(meta_file.read_text())
        assert meta["batch_id"] == "msgbatch_persist_456"
        assert meta["request_count"] == 2
        assert len(meta["items"]) == 2
        assert meta["items"][0]["work_item_id"] == "batch-item-0"
        assert meta["items"][0]["model_id"] == "sonnet"

    def test_submit_batch_empty_raises(self):
        """submit_batch() with empty list raises ValueError."""
        dispatcher = AgentDispatcher(api_key="test-key")
        with pytest.raises(ValueError, match="at least one item"):
            dispatcher.submit_batch([])

    def test_retrieve_batch_processes_results(self, tmp_path):
        """retrieve_batch() converts API results into DispatchResults."""
        import json

        # Set up metadata on disk
        meta_dir = tmp_path / ".cortex" / "orchestration" / "batches"
        meta_dir.mkdir(parents=True)
        meta = {
            "batch_id": "msgbatch_ret_789",
            "items": [
                {
                    "work_item_id": "item-0",
                    "task_type": "research",
                    "model_id": "claude-sonnet-4-20250514",
                    "model_tier": "sonnet",
                },
                {
                    "work_item_id": "item-1",
                    "task_type": "analysis",
                    "model_id": "claude-sonnet-4-20250514",
                    "model_tier": "sonnet",
                },
                {
                    "work_item_id": "item-2",
                    "task_type": "test",
                    "model_id": "claude-sonnet-4-20250514",
                    "model_tier": "sonnet",
                },
            ],
        }
        (meta_dir / "msgbatch_ret_789.json").write_text(json.dumps(meta))

        # Mock client
        mock_client = MagicMock()
        mock_batch_obj = MagicMock()
        mock_batch_obj.processing_status = "ended"
        mock_client.messages.batches.retrieve.return_value = mock_batch_obj

        # Build mock results
        def _make_result(cid, succeeded=True):
            r = MagicMock()
            r.custom_id = cid
            if succeeded:
                r.result.type = "succeeded"
                text_block = MagicMock()
                text_block.type = "text"
                text_block.text = f"Result for {cid}"
                r.result.message.content = [text_block]
                r.result.message.usage.input_tokens = 100
                r.result.message.usage.output_tokens = 200
            else:
                r.result.type = "errored"
            return r

        mock_client.messages.batches.results.return_value = [
            _make_result("item-0", True),
            _make_result("item-1", True),
            _make_result("item-2", False),
        ]

        dispatcher = AgentDispatcher(api_key="test-key", dry_run=False)

        with (
            patch.object(dispatcher, "_get_client", return_value=mock_client),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            results = dispatcher.retrieve_batch("msgbatch_ret_789")

        assert len(results) == 3
        assert results[0].success is True
        assert results[0].work_item_id == "item-0"
        assert results[0].tokens_used == 300
        assert "Result for item-0" in results[0].output
        assert results[0].task_type == "research"

        assert results[2].success is False
        assert "errored" in results[2].error

    def test_retrieve_batch_in_progress_returns_empty(self):
        """retrieve_batch() returns empty list if batch not ended."""
        mock_client = MagicMock()
        mock_batch_obj = MagicMock()
        mock_batch_obj.processing_status = "in_progress"
        mock_client.messages.batches.retrieve.return_value = mock_batch_obj

        dispatcher = AgentDispatcher(api_key="test-key", dry_run=False)

        with patch.object(dispatcher, "_get_client", return_value=mock_client):
            results = dispatcher.retrieve_batch("msgbatch_pending")

        assert results == []

    def test_retrieve_batch_records_outcomes(self, tmp_path):
        """retrieve_batch() calls router.record_outcome for each result."""
        import json

        meta_dir = tmp_path / ".cortex" / "orchestration" / "batches"
        meta_dir.mkdir(parents=True)
        meta = {
            "batch_id": "msgbatch_learn",
            "items": [
                {
                    "work_item_id": "learn-0",
                    "task_type": "research",
                    "model_id": "claude-sonnet-4-20250514",
                    "model_tier": "sonnet",
                },
            ],
        }
        (meta_dir / "msgbatch_learn.json").write_text(json.dumps(meta))

        mock_client = MagicMock()
        mock_batch_obj = MagicMock()
        mock_batch_obj.processing_status = "ended"
        mock_client.messages.batches.retrieve.return_value = mock_batch_obj

        r = MagicMock()
        r.custom_id = "learn-0"
        r.result.type = "succeeded"
        tb = MagicMock()
        tb.type = "text"
        tb.text = "done"
        r.result.message.content = [tb]
        r.result.message.usage.input_tokens = 50
        r.result.message.usage.output_tokens = 100
        mock_client.messages.batches.results.return_value = [r]

        mock_router = MagicMock()
        dispatcher = AgentDispatcher(api_key="test-key", dry_run=False)

        with (
            patch.object(dispatcher, "_get_client", return_value=mock_client),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            dispatcher.retrieve_batch("msgbatch_learn", router=mock_router)

        assert mock_router.record_outcome.call_count == 1
        call_kwargs = mock_router.record_outcome.call_args[1]
        assert call_kwargs["work_item_id"] == "learn-0"
        assert call_kwargs["model_tier"] == "sonnet"
        assert call_kwargs["success"] is True
        assert call_kwargs["task_type"] == "research"
