"""Tests for the orchestration pipeline: intake -> router -> dispatch -> collect."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from cortex.supervisor.agents import (
    AGENT_REGISTRY,
    AgentProfile,
    get_agent_by_name,
    get_agent_for_task,
    list_agents,
)
from cortex.supervisor.models import WorkItem, WorkItemPriority, TaskTarget


# ---------------------------------------------------------------------------
# Local helpers — lightweight router/dispatch/collector stubs for pipeline tests
# These mirror the expected interfaces without importing unwritten modules.
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


@dataclass
class ModelSelection:
    model_tier: ModelTier
    complexity_score: float
    reason: str


@dataclass
class DispatchResult:
    work_item_id: str
    success: bool
    model_used: str
    output: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    duration_seconds: float = 0.0


def compute_complexity(item: WorkItem) -> float:
    """Score 0-1 based on token count, priority, file count, and task type."""
    score = 0.0

    # Token contribution (up to 0.3)
    score += min(item.estimated_tokens / 100_000, 0.3)

    # Priority contribution (up to 0.3)
    priority_weights = {
        WorkItemPriority.CRITICAL: 0.3,
        WorkItemPriority.HIGH: 0.2,
        WorkItemPriority.MEDIUM: 0.1,
        WorkItemPriority.LOW: 0.0,
    }
    score += priority_weights.get(item.priority, 0.1)

    # File count contribution (up to 0.2)
    score += min(len(item.files) / 20, 0.2)

    # Task type contribution (up to 0.2)
    complex_types = {"architecture", "design", "implement", "spec"}
    simple_types = {"classify", "triage", "categorize", "tag"}
    if item.task_type in complex_types:
        score += 0.2
    elif item.task_type in simple_types:
        score += 0.0
    else:
        score += 0.1

    return min(score, 1.0)


def select_model(complexity: float) -> ModelSelection:
    """Route to model tier based on complexity score."""
    if complexity >= 0.6:
        return ModelSelection(ModelTier.OPUS, complexity, "High complexity")
    elif complexity >= 0.3:
        return ModelSelection(ModelTier.SONNET, complexity, "Medium complexity")
    else:
        return ModelSelection(ModelTier.HAIKU, complexity, "Low complexity")


def collect_results(results: List[DispatchResult]) -> Dict[str, Any]:
    """Summarize a batch of dispatch results."""
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    total_tokens = sum(r.tokens_used for r in results)
    return {
        "total": len(results),
        "successes": len(successes),
        "failures": len(failures),
        "total_tokens": total_tokens,
        "failed_ids": [r.work_item_id for r in failures],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_work_item() -> WorkItem:
    return WorkItem(
        id="wi-001",
        source="cli",
        task_type="classify",
        description="Triage incoming issue",
        priority=WorkItemPriority.LOW,
        estimated_tokens=500,
        files=[],
    )


@pytest.fixture
def medium_work_item() -> WorkItem:
    return WorkItem(
        id="wi-002",
        source="cli",
        task_type="test",
        description="Write integration tests for auth module",
        priority=WorkItemPriority.MEDIUM,
        estimated_tokens=15_000,
        files=["src/auth.py", "tests/test_auth.py"],
    )


@pytest.fixture
def complex_work_item() -> WorkItem:
    return WorkItem(
        id="wi-003",
        source="cli",
        task_type="architecture",
        description="Design event-driven pipeline for real-time ingestion",
        priority=WorkItemPriority.CRITICAL,
        estimated_tokens=80_000,
        files=[f"src/module_{i}.py" for i in range(15)],
    )


@pytest.fixture
def success_dispatch() -> DispatchResult:
    return DispatchResult(
        work_item_id="wi-001",
        success=True,
        model_used="haiku",
        output='{"category": "bug"}',
        tokens_used=350,
        duration_seconds=1.2,
    )


@pytest.fixture
def failure_dispatch() -> DispatchResult:
    return DispatchResult(
        work_item_id="wi-099",
        success=False,
        model_used="sonnet",
        error="Rate limit exceeded",
        tokens_used=0,
        duration_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkItemCreation:
    def test_work_item_creation_from_cli(self, simple_work_item: WorkItem) -> None:
        assert simple_work_item.id == "wi-001"
        assert simple_work_item.source == "cli"
        assert simple_work_item.task_type == "classify"
        assert simple_work_item.priority == WorkItemPriority.LOW
        assert isinstance(simple_work_item.created_at, datetime)

    def test_work_item_priority_scoring(self) -> None:
        critical = WorkItem(
            id="c",
            source="s",
            task_type="fix",
            description="d",
            priority=WorkItemPriority.CRITICAL,
        )
        low = WorkItem(
            id="l",
            source="s",
            task_type="fix",
            description="d",
            priority=WorkItemPriority.LOW,
        )
        assert compute_complexity(critical) > compute_complexity(low)


class TestModelRouter:
    def test_model_router_selects_opus_for_complex(
        self,
        complex_work_item: WorkItem,
    ) -> None:
        score = compute_complexity(complex_work_item)
        selection = select_model(score)
        assert selection.model_tier == ModelTier.OPUS

    def test_model_router_selects_haiku_for_simple(
        self,
        simple_work_item: WorkItem,
    ) -> None:
        score = compute_complexity(simple_work_item)
        selection = select_model(score)
        assert selection.model_tier == ModelTier.HAIKU

    def test_model_router_selects_sonnet_for_medium(
        self,
        medium_work_item: WorkItem,
    ) -> None:
        score = compute_complexity(medium_work_item)
        selection = select_model(score)
        assert selection.model_tier == ModelTier.SONNET


class TestComplexityScoring:
    def test_complexity_scoring_high_tokens(self) -> None:
        item = WorkItem(
            id="t",
            source="s",
            task_type="review",
            description="d",
            estimated_tokens=200_000,
        )
        score = compute_complexity(item)
        # 0.3 (tokens capped) + 0.1 (medium priority) + 0.0 (no files) + 0.1 (review=other)
        assert score == pytest.approx(0.5, abs=0.05)

    def test_complexity_scoring_architecture_type(self) -> None:
        item = WorkItem(
            id="a",
            source="s",
            task_type="architecture",
            description="d",
            priority=WorkItemPriority.HIGH,
        )
        score = compute_complexity(item)
        # 0.0 (tokens) + 0.2 (high priority) + 0.0 (no files) + 0.2 (architecture)
        assert score == pytest.approx(0.4, abs=0.05)

    def test_complexity_scoring_low_priority(self, simple_work_item: WorkItem) -> None:
        score = compute_complexity(simple_work_item)
        # 500/100000 ~ 0.005 + 0.0 (low) + 0.0 (no files) + 0.0 (classify=simple)
        assert score < 0.1


class TestDispatch:
    def test_dispatch_result_success(self, success_dispatch: DispatchResult) -> None:
        assert success_dispatch.success is True
        assert success_dispatch.model_used == "haiku"
        assert success_dispatch.tokens_used == 350
        assert success_dispatch.error is None

    def test_dispatch_result_failure(self, failure_dispatch: DispatchResult) -> None:
        assert failure_dispatch.success is False
        assert failure_dispatch.error == "Rate limit exceeded"
        assert failure_dispatch.tokens_used == 0


class TestCollector:
    def test_collector_batch_summary(
        self,
        success_dispatch: DispatchResult,
        failure_dispatch: DispatchResult,
    ) -> None:
        summary = collect_results([success_dispatch, failure_dispatch])
        assert summary["total"] == 2
        assert summary["successes"] == 1
        assert summary["failures"] == 1
        assert summary["total_tokens"] == 350
        assert summary["failed_ids"] == ["wi-099"]

    def test_collector_outcome_recording(
        self,
        success_dispatch: DispatchResult,
        tmp_path,
    ) -> None:
        outcome_file = tmp_path / "outcomes.jsonl"
        record = {
            "work_item_id": success_dispatch.work_item_id,
            "model_used": success_dispatch.model_used,
            "success": success_dispatch.success,
            "tokens_used": success_dispatch.tokens_used,
        }
        outcome_file.write_text(json.dumps(record) + "\n")

        loaded = json.loads(outcome_file.read_text().strip())
        assert loaded["work_item_id"] == "wi-001"
        assert loaded["success"] is True
        assert loaded["tokens_used"] == 350


class TestAgentRegistry:
    def test_agent_registry_lookup(self) -> None:
        agent = get_agent_by_name("architect")
        assert agent is not None
        assert agent.name == "architect"
        assert agent.preferred_model_tier == "opus"

    def test_agent_task_type_matching(self) -> None:
        agent = get_agent_for_task("review")
        assert agent is not None
        assert agent.name == "code_reviewer"
        assert agent.can_handle("review") is True
        assert agent.can_handle("architecture") is False


class TestFullPipeline:
    def test_full_pipeline_mock(self, complex_work_item: WorkItem) -> None:
        """Mock API call, test full intake -> route -> dispatch -> collect flow."""
        # Step 1: Intake — work item exists
        assert complex_work_item.id == "wi-003"

        # Step 2: Route — select model
        score = compute_complexity(complex_work_item)
        assert 0.0 <= score <= 1.0
        selection = select_model(score)
        assert selection.model_tier == ModelTier.OPUS

        # Step 3: Agent selection
        agent = get_agent_for_task(complex_work_item.task_type)
        assert agent is not None
        assert agent.name == "architect"

        # Step 4: Build prompt
        prompt = agent.build_system_prompt(
            project="vortex",
            context="Multi-source weather pipeline.",
        )
        assert "vortex" in prompt
        assert "Multi-source weather pipeline." in prompt

        # Step 5: Dispatch (mocked API)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Design approved.")]
        mock_response.usage.input_tokens = 5000
        mock_response.usage.output_tokens = 2000

        with patch("anthropic.Anthropic") as mock_client_cls:
            client = mock_client_cls.return_value
            client.messages.create.return_value = mock_response

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=prompt,
                messages=[{"role": "user", "content": complex_work_item.description}],
            )

            result = DispatchResult(
                work_item_id=complex_work_item.id,
                success=True,
                model_used=selection.model_tier.value,
                output=response.content[0].text,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                duration_seconds=2.5,
            )

        # Step 6: Collect
        summary = collect_results([result])
        assert summary["total"] == 1
        assert summary["successes"] == 1
        assert summary["failures"] == 0
        assert summary["total_tokens"] == 7000
        assert result.output == "Design approved."
