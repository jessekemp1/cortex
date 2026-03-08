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
        assert "execution agent" in sys_prompt
        assert "test" in sys_prompt
        assert "vortex" in sys_prompt

    def test_build_system_prompt_custom(self, dispatcher, work_item):
        work_item.system_prompt = "You are a specialized tester."
        sys_prompt = dispatcher._build_system_prompt(work_item)
        assert sys_prompt == "You are a specialized tester."

    @patch("cortex.supervisor.dispatch.AGENT_SDK_AVAILABLE", False)
    def test_dispatch_uses_direct_api_fallback(self, dispatcher, work_item, model_selection):
        """When Agent SDK unavailable, falls back to direct API."""
        with patch.object(dispatcher, "_run_direct", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ("Test output", 500)
            result = dispatcher.dispatch(work_item, model_selection)

        assert result.success is True
        assert result.output == "Test output"
        assert result.tokens_used == 500
        assert result.model_used == "claude-sonnet-4-6"

    @patch("cortex.supervisor.dispatch.AGENT_SDK_AVAILABLE", False)
    def test_dispatch_handles_api_error(self, dispatcher, work_item, model_selection):
        """API errors are caught and returned as failed results."""

        async def fail(*args, **kwargs):
            raise RuntimeError("API key invalid")

        with patch.object(dispatcher, "_run_direct", side_effect=fail):
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

    @patch("cortex.supervisor.dispatch.AGENT_SDK_AVAILABLE", False)
    def test_orchestrate_with_work_items(self):
        """orchestrate() with explicit work items routes and dispatches them."""
        from supervisor.core import CortexSupervisor

        supervisor = CortexSupervisor()

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
            patch.object(supervisor, "_dispatch_work_items", return_value=1),
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
