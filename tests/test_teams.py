"""Tests for team orchestration (Phase 4).

Tests:
  - Team registry and lookup
  - should_use_team decision matrix
  - Budget enforcement (hard stop)
  - DAG execution with dependencies
  - Cascade skip on failure
  - Decomposition max 5 sub-tasks
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import List

import pytest

from cortex.supervisor.teams import (
    BudgetTracker,
    TeamOrchestrator,
    TeamTask,
    TEAM_REGISTRY,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class MockWorkItem:
    id: str = "test-item"
    task_type: str = "architecture"
    description: str = "Design a new authentication system"
    estimated_tokens: int = 80000
    files: List[str] = field(default_factory=lambda: [f"f{i}.py" for i in range(12)])


@pytest.fixture
def orchestrator() -> TeamOrchestrator:
    return TeamOrchestrator(enabled=True)


@pytest.fixture
def disabled_orchestrator() -> TeamOrchestrator:
    return TeamOrchestrator(enabled=False)


# ---------------------------------------------------------------------------
# Tests: Team registry
# ---------------------------------------------------------------------------


class TestTeamRegistry:
    def test_registry_has_teams(self) -> None:
        assert "research" in TEAM_REGISTRY
        assert "implementation" in TEAM_REGISTRY
        assert "architecture" in TEAM_REGISTRY

    def test_team_definition_fields(self) -> None:
        arch = TEAM_REGISTRY["architecture"]
        assert arch.lead_agent == "architect"
        assert arch.token_budget > 0
        assert arch.cost_budget_usd > 0

    def test_get_team(self, orchestrator: TeamOrchestrator) -> None:
        team = orchestrator.get_team("architecture")
        assert team is not None
        assert team.name == "architecture"

    def test_get_unknown_team(self, orchestrator: TeamOrchestrator) -> None:
        assert orchestrator.get_team("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests: should_use_team
# ---------------------------------------------------------------------------


class TestShouldUseTeam:
    def test_disabled_returns_none(self, disabled_orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem()
        assert disabled_orchestrator.should_use_team(item, complexity_score=0.9) is None

    def test_architecture_high_complexity(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="architecture", estimated_tokens=80000)
        result = orchestrator.should_use_team(item, complexity_score=0.8)
        assert result == "architecture"

    def test_low_complexity_no_team(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="architecture", estimated_tokens=80000)
        result = orchestrator.should_use_team(item, complexity_score=0.3)
        assert result is None

    def test_small_tokens_no_team(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="architecture", estimated_tokens=5000)
        result = orchestrator.should_use_team(item, complexity_score=0.9)
        assert result is None

    def test_classify_never_uses_team(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="classify", estimated_tokens=100000)
        result = orchestrator.should_use_team(item, complexity_score=0.9)
        assert result is None

    def test_docs_never_uses_team(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="docs", estimated_tokens=100000)
        result = orchestrator.should_use_team(item, complexity_score=0.9)
        assert result is None

    def test_research_eligible(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem(task_type="research", estimated_tokens=60000)
        result = orchestrator.should_use_team(item, complexity_score=0.75)
        assert result == "research"


# ---------------------------------------------------------------------------
# Tests: Budget tracker
# ---------------------------------------------------------------------------


class TestBudgetTracker:
    def test_can_afford_within_budget(self) -> None:
        budget = BudgetTracker(token_limit=100000, cost_limit_usd=5.0)
        assert budget.can_afford(50000)

    def test_cannot_afford_over_budget(self) -> None:
        budget = BudgetTracker(token_limit=100000, cost_limit_usd=5.0)
        budget.record_spend(90000, 4.0)
        assert not budget.can_afford(20000)

    def test_cost_limit_enforced(self) -> None:
        budget = BudgetTracker(token_limit=1000000, cost_limit_usd=1.0)
        budget.record_spend(1000, 1.1)
        assert not budget.can_afford(100)

    def test_remaining(self) -> None:
        budget = BudgetTracker(token_limit=100000, cost_limit_usd=5.0)
        budget.record_spend(30000, 1.5)
        assert budget.remaining_tokens == 70000
        assert abs(budget.remaining_usd - 3.5) < 0.01

    def test_budget_exhausted(self) -> None:
        budget = BudgetTracker(token_limit=100, cost_limit_usd=0.01)
        budget.record_spend(100, 0.01)
        assert budget.budget_exhausted


# ---------------------------------------------------------------------------
# Tests: Team execution
# ---------------------------------------------------------------------------


class TestTeamExecution:
    def test_execute_with_unknown_team(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem()
        result = asyncio.run(orchestrator.execute_with_team(item, "nonexistent_team"))
        assert not result.success
        assert "Unknown team" in result.error

    def test_execute_produces_sub_results(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem()
        result = asyncio.run(orchestrator.execute_with_team(item, "architecture"))
        assert len(result.sub_results) > 0
        assert result.total_tokens > 0

    def test_execute_budget_tracking(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem()
        result = asyncio.run(orchestrator.execute_with_team(item, "architecture"))
        assert result.budget_remaining_tokens >= 0
        assert result.budget_remaining_usd >= 0

    def test_synthesized_output_not_empty(self, orchestrator: TeamOrchestrator) -> None:
        item = MockWorkItem()
        result = asyncio.run(orchestrator.execute_with_team(item, "architecture"))
        assert result.synthesized_output


# ---------------------------------------------------------------------------
# Tests: DAG execution
# ---------------------------------------------------------------------------


class TestDAGExecution:
    def test_cascade_skip_on_failure(self, orchestrator: TeamOrchestrator) -> None:
        """If a task fails, all dependents should be skipped."""
        sub_tasks = [
            TeamTask(
                parent_id="p",
                sub_task_id="t0",
                description="first",
                task_type="research",
                sequence=0,
            ),
            TeamTask(
                parent_id="p",
                sub_task_id="t1",
                description="second",
                task_type="implement",
                sequence=1,
                depends_on=[0],
            ),
            TeamTask(
                parent_id="p",
                sub_task_id="t2",
                description="third",
                task_type="review",
                sequence=2,
                depends_on=[1],
            ),
        ]

        async def failing_dispatch(task):
            if task.sequence == 0:
                return {
                    "success": False,
                    "error": "deliberate_failure",
                    "tokens_used": 100,
                    "cost_usd": 0,
                }
            return {"success": True, "output": "ok", "tokens_used": 100, "cost_usd": 0}

        budget = BudgetTracker(token_limit=500000, cost_limit_usd=5.0)
        results = asyncio.run(orchestrator._execute_dag(sub_tasks, budget, failing_dispatch))

        assert not results[0]["success"]
        assert "dependency_failed" in results[1].get("error", "")
        assert "dependency_failed" in results[2].get("error", "")


# ---------------------------------------------------------------------------
# Tests: Opus-lead decomposition
# ---------------------------------------------------------------------------


class TestDecompositionValidation:
    """Test _validate_decomposition without needing LLM calls."""

    def test_valid_decomposition(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        raw = [
            {
                "description": "Search for existing auth patterns in codebase files",
                "task_type": "research",
                "required_tier": "haiku",
                "depends_on": [],
                "estimated_tokens": 2000,
                "files": ["auth.py"],
                "rationale": "Simple search",
            },
            {
                "description": "Implement JWT middleware based on research findings above",
                "task_type": "implement",
                "required_tier": "sonnet",
                "depends_on": [0],
                "estimated_tokens": 8000,
                "files": ["middleware.py"],
                "rationale": "Needs implementation skill",
            },
            {
                "description": "Write integration tests for the new JWT middleware",
                "task_type": "test",
                "required_tier": "sonnet",
                "depends_on": [1],
                "estimated_tokens": 5000,
                "files": ["test_auth.py"],
                "rationale": "Standard test writing",
            },
        ]
        tasks = orch._validate_decomposition(raw, "test-parent")
        assert len(tasks) == 3
        assert tasks[0].required_tier == "haiku"
        assert tasks[1].required_tier == "sonnet"
        assert tasks[1].depends_on == [0]
        assert tasks[0].files == ["auth.py"]
        assert tasks[0].rationale == "Simple search"

    def test_rejects_non_array(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        with pytest.raises(ValueError, match="JSON array"):
            orch._validate_decomposition({"not": "an array"}, "p")

    def test_rejects_single_task(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        with pytest.raises(ValueError, match="2\\+"):
            orch._validate_decomposition(
                [
                    {
                        "description": "only one task here that is long enough",
                        "task_type": "implement",
                        "required_tier": "sonnet",
                    }
                ],
                "p",
            )

    def test_rejects_short_description(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        with pytest.raises(ValueError, match="empty/short"):
            orch._validate_decomposition(
                [
                    {"description": "too short", "task_type": "research"},
                    {"description": "also short", "task_type": "implement"},
                ],
                "p",
            )

    def test_rejects_forward_dependency(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        with pytest.raises(ValueError, match="invalid dependency"):
            orch._validate_decomposition(
                [
                    {
                        "description": "First task needs to be long enough for validation",
                        "task_type": "research",
                        "depends_on": [1],
                    },
                    {
                        "description": "Second task also needs to be long enough for validation",
                        "task_type": "implement",
                    },
                ],
                "p",
            )

    def test_truncates_to_five(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        raw = [
            {
                "description": f"Sub-task number {i} with enough description text here",
                "task_type": "research",
                "depends_on": [],
            }
            for i in range(8)
        ]
        tasks = orch._validate_decomposition(raw, "p")
        assert len(tasks) == 5

    def test_normalizes_unknown_tier(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        raw = [
            {
                "description": "First task with unknown tier that defaults to sonnet",
                "task_type": "research",
                "required_tier": "gpt4",
            },
            {
                "description": "Second task with no tier specified at all defaults sonnet",
                "task_type": "implement",
            },
        ]
        tasks = orch._validate_decomposition(raw, "p")
        assert tasks[0].required_tier == "sonnet"
        assert tasks[1].required_tier == "sonnet"

    def test_limits_opus_subtasks(self) -> None:
        """Only 1 sub-task allowed at opus tier. Others downgraded to sonnet."""
        orch = TeamOrchestrator(enabled=True)
        raw = [
            {
                "description": "First opus sub-task that requires deep reasoning here",
                "task_type": "research",
                "required_tier": "opus",
                "depends_on": [],
            },
            {
                "description": "Second opus sub-task that should be downgraded to sonnet",
                "task_type": "implement",
                "required_tier": "opus",
                "depends_on": [],
            },
            {
                "description": "Third opus sub-task that should also be downgraded here",
                "task_type": "review",
                "required_tier": "opus",
                "depends_on": [],
            },
        ]
        tasks = orch._validate_decomposition(raw, "p")
        opus_count = sum(1 for t in tasks if t.required_tier == "opus")
        assert opus_count == 1
        assert tasks[0].required_tier == "opus"
        assert tasks[1].required_tier == "sonnet"  # Downgraded

    def test_normalizes_unknown_task_type(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        raw = [
            {
                "description": "First task with a completely invalid task type string",
                "task_type": "quantum_compute",
                "depends_on": [],
            },
            {
                "description": "Second task with another invalid type that defaults",
                "task_type": "teleport",
                "depends_on": [],
            },
        ]
        tasks = orch._validate_decomposition(raw, "p")
        assert tasks[0].task_type == "implement"
        assert tasks[1].task_type == "implement"


class TestDecomposeFallback:
    """Test that decomposition falls back correctly."""

    def test_no_dispatcher_uses_default(self) -> None:
        orch = TeamOrchestrator(enabled=True, dispatcher=None)
        from cortex.supervisor.teams import TEAM_REGISTRY

        team = TEAM_REGISTRY["architecture"]
        budget = BudgetTracker(token_limit=500000, cost_limit_usd=5.0)
        tasks = asyncio.run(orch._decompose(MockWorkItem(), team, budget))
        assert len(tasks) == 3  # Default: research → implement → review
        assert tasks[0].task_type == "research"

    def test_tight_budget_uses_default(self) -> None:
        orch = TeamOrchestrator(enabled=True, dispatcher="fake")
        from cortex.supervisor.teams import TEAM_REGISTRY

        team = TEAM_REGISTRY["architecture"]
        budget = BudgetTracker(token_limit=1000, cost_limit_usd=5.0)  # Can't afford 5K
        tasks = asyncio.run(orch._decompose(MockWorkItem(), team, budget))
        assert len(tasks) == 3  # Default fallback


class TestSynthesisFallback:
    """Test synthesis fallback when no dispatcher available."""

    def test_no_dispatcher_uses_concat(self) -> None:
        orch = TeamOrchestrator(enabled=True, dispatcher=None)
        from cortex.supervisor.teams import TEAM_REGISTRY

        team = TEAM_REGISTRY["architecture"]
        budget = BudgetTracker(token_limit=500000, cost_limit_usd=5.0)
        sub_tasks = [
            TeamTask(
                parent_id="p",
                sub_task_id="t0",
                description="first",
                task_type="research",
                sequence=0,
            ),
        ]
        sub_results = [{"success": True, "output": "Found auth patterns"}]
        result = asyncio.run(orch._synthesize(MockWorkItem(), sub_tasks, sub_results, team, budget))
        assert "Found auth patterns" in result
        assert "✓" in result

    def test_failed_subtask_in_fallback(self) -> None:
        orch = TeamOrchestrator(enabled=True, dispatcher=None)
        from cortex.supervisor.teams import TEAM_REGISTRY

        team = TEAM_REGISTRY["architecture"]
        budget = BudgetTracker(token_limit=500000, cost_limit_usd=5.0)
        sub_tasks = [
            TeamTask(
                parent_id="p",
                sub_task_id="t0",
                description="first",
                task_type="research",
                sequence=0,
            ),
        ]
        sub_results = [{"success": False, "error": "timeout"}]
        result = asyncio.run(orch._synthesize(MockWorkItem(), sub_tasks, sub_results, team, budget))
        assert "✗" in result
        assert "timeout" in result


class TestResultFormatting:
    """Test _format_results_for_synthesis."""

    def test_caps_output_at_4000_chars(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        sub_tasks = [
            TeamTask(
                parent_id="p",
                sub_task_id="t0",
                description="first task here",
                task_type="research",
                sequence=0,
                required_tier="haiku",
            ),
        ]
        # Output longer than 4000 chars
        sub_results = [{"success": True, "output": "x" * 10000}]
        formatted = orch._format_results_for_synthesis(sub_tasks, sub_results)
        # The raw output in the formatted string should be capped
        assert len(formatted) < 5000  # 4000 chars + metadata overhead

    def test_includes_tier_in_format(self) -> None:
        orch = TeamOrchestrator(enabled=True)
        sub_tasks = [
            TeamTask(
                parent_id="p",
                sub_task_id="t0",
                description="first task",
                task_type="research",
                sequence=0,
                required_tier="haiku",
            ),
        ]
        sub_results = [{"success": True, "output": "some result"}]
        formatted = orch._format_results_for_synthesis(sub_tasks, sub_results)
        assert "haiku" in formatted
        assert "research" in formatted
        assert "SUCCESS" in formatted


class TestTeamTaskFields:
    """Test new fields on TeamTask."""

    def test_files_field_default(self) -> None:
        task = TeamTask(
            parent_id="p", sub_task_id="t", description="d", task_type="research", sequence=0
        )
        assert task.files == []

    def test_rationale_field(self) -> None:
        task = TeamTask(
            parent_id="p",
            sub_task_id="t",
            description="d",
            task_type="research",
            sequence=0,
            rationale="Simple search, haiku sufficient",
        )
        assert "haiku" in task.rationale

    def test_dispatcher_param(self) -> None:
        """TeamOrchestrator accepts dispatcher parameter."""
        orch = TeamOrchestrator(enabled=True, dispatcher="mock_dispatcher")
        assert orch._dispatcher == "mock_dispatcher"
