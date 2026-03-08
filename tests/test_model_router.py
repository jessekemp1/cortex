"""Tests for the model complexity router."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from cortex.supervisor.models import WorkItem, WorkItemPriority


# ---------------------------------------------------------------------------
# Router implementation under test
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


MODEL_ID_MAP: Dict[ModelTier, str] = {
    ModelTier.OPUS: "claude-opus-4-20250514",
    ModelTier.SONNET: "claude-sonnet-4-20250514",
    ModelTier.HAIKU: "claude-haiku-3-20250414",
}


@dataclass
class ModelSelection:
    model_tier: ModelTier
    model_id: str
    complexity_score: float
    reason: str


@dataclass
class OutcomeRecord:
    work_item_id: str
    model_tier: str
    success: bool
    tokens_used: int


class ModelRouter:
    """Complexity-based model router with historical outcome tracking."""

    OPUS_THRESHOLD = 0.6
    SONNET_THRESHOLD = 0.3

    COMPLEX_TASK_TYPES = {"architecture", "design", "implement", "spec"}
    SIMPLE_TASK_TYPES = {"classify", "triage", "categorize", "tag"}

    def __init__(self, outcomes_path: Optional[Path] = None) -> None:
        self.outcomes_path = outcomes_path
        self.history: List[OutcomeRecord] = []
        if outcomes_path and outcomes_path.exists():
            self._load_outcomes()

    def _load_outcomes(self) -> None:
        assert self.outcomes_path is not None
        for line in self.outcomes_path.read_text().strip().splitlines():
            data = json.loads(line)
            self.history.append(OutcomeRecord(**data))

    def compute_complexity(self, item: WorkItem) -> float:
        """Score 0-1 based on tokens, priority, files, and task type."""
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
        if item.task_type in self.COMPLEX_TASK_TYPES:
            score += 0.2
        elif item.task_type in self.SIMPLE_TASK_TYPES:
            score += 0.0
        else:
            score += 0.1

        return min(score, 1.0)

    def select_model(self, item: WorkItem) -> ModelSelection:
        """Route a work item to the appropriate model tier."""
        complexity = self.compute_complexity(item)

        if complexity >= self.OPUS_THRESHOLD:
            tier = ModelTier.OPUS
            reason = "High complexity"
        elif complexity >= self.SONNET_THRESHOLD:
            tier = ModelTier.SONNET
            reason = "Medium complexity"
        else:
            tier = ModelTier.HAIKU
            reason = "Low complexity"

        return ModelSelection(
            model_tier=tier,
            model_id=MODEL_ID_MAP[tier],
            complexity_score=complexity,
            reason=reason,
        )

    def record_outcome(self, record: OutcomeRecord) -> None:
        """Append an outcome to history and persist to disk."""
        self.history.append(record)
        if self.outcomes_path:
            with self.outcomes_path.open("a") as f:
                f.write(json.dumps(record.__dict__) + "\n")

    def historical_performance(self, model_tier: str) -> Dict[str, Any]:
        """Return success rate and token stats for a model tier."""
        tier_records = [r for r in self.history if r.model_tier == model_tier]
        if not tier_records:
            return {"count": 0, "success_rate": 0.0, "avg_tokens": 0.0}

        successes = sum(1 for r in tier_records if r.success)
        total_tokens = sum(r.tokens_used for r in tier_records)
        return {
            "count": len(tier_records),
            "success_rate": successes / len(tier_records),
            "avg_tokens": total_tokens / len(tier_records),
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter()


@pytest.fixture
def router_with_outcomes(tmp_path: Path) -> ModelRouter:
    outcomes_file = tmp_path / "outcomes.jsonl"
    records = [
        {"work_item_id": "w1", "model_tier": "opus", "success": True, "tokens_used": 8000},
        {"work_item_id": "w2", "model_tier": "opus", "success": True, "tokens_used": 6000},
        {"work_item_id": "w3", "model_tier": "sonnet", "success": False, "tokens_used": 3000},
        {"work_item_id": "w4", "model_tier": "haiku", "success": True, "tokens_used": 500},
    ]
    outcomes_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return ModelRouter(outcomes_path=outcomes_file)


def _make_item(
    task_type: str = "review",
    priority: WorkItemPriority = WorkItemPriority.MEDIUM,
    tokens: int = 0,
    files: int = 0,
) -> WorkItem:
    return WorkItem(
        id="test",
        source="test",
        task_type=task_type,
        description="test item",
        priority=priority,
        estimated_tokens=tokens,
        files=[f"f{i}.py" for i in range(files)],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComplexityScoring:
    def test_complexity_score_ranges(self, router: ModelRouter) -> None:
        """All scores must be in [0, 1]."""
        items = [
            _make_item(task_type="classify", priority=WorkItemPriority.LOW, tokens=0),
            _make_item(
                task_type="architecture",
                priority=WorkItemPriority.CRITICAL,
                tokens=200_000,
                files=30,
            ),
            _make_item(
                task_type="review", priority=WorkItemPriority.MEDIUM, tokens=10_000, files=5
            ),
        ]
        for item in items:
            score = router.compute_complexity(item)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {item.task_type}"

    def test_high_token_count_increases_complexity(self, router: ModelRouter) -> None:
        low_tokens = _make_item(tokens=1_000)
        high_tokens = _make_item(tokens=90_000)
        assert router.compute_complexity(high_tokens) > router.compute_complexity(low_tokens)

    def test_critical_priority_increases_complexity(self, router: ModelRouter) -> None:
        low = _make_item(priority=WorkItemPriority.LOW)
        critical = _make_item(priority=WorkItemPriority.CRITICAL)
        assert router.compute_complexity(critical) > router.compute_complexity(low)

    def test_many_files_increases_complexity(self, router: ModelRouter) -> None:
        few = _make_item(files=1)
        many = _make_item(files=18)
        assert router.compute_complexity(many) > router.compute_complexity(few)


class TestModelSelection:
    def test_opus_selection_threshold(self, router: ModelRouter) -> None:
        """Items with complexity >= 0.6 route to opus."""
        item = _make_item(
            task_type="architecture",
            priority=WorkItemPriority.CRITICAL,
            tokens=50_000,
            files=10,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.OPUS
        assert selection.complexity_score >= 0.6

    def test_sonnet_selection_threshold(self, router: ModelRouter) -> None:
        """Items with complexity in [0.3, 0.6) route to sonnet."""
        item = _make_item(
            task_type="test",
            priority=WorkItemPriority.MEDIUM,
            tokens=15_000,
            files=3,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.SONNET
        assert 0.3 <= selection.complexity_score < 0.6

    def test_haiku_selection_threshold(self, router: ModelRouter) -> None:
        """Items with complexity < 0.3 route to haiku."""
        item = _make_item(
            task_type="classify",
            priority=WorkItemPriority.LOW,
            tokens=200,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.HAIKU
        assert selection.complexity_score < 0.3

    def test_architecture_task_routes_to_opus(self, router: ModelRouter) -> None:
        item = _make_item(
            task_type="architecture",
            priority=WorkItemPriority.HIGH,
            tokens=40_000,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.OPUS

    def test_classification_task_routes_to_haiku(self, router: ModelRouter) -> None:
        item = _make_item(
            task_type="classify",
            priority=WorkItemPriority.LOW,
            tokens=100,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.HAIKU

    def test_test_task_routes_to_sonnet(self, router: ModelRouter) -> None:
        item = _make_item(
            task_type="test",
            priority=WorkItemPriority.MEDIUM,
            tokens=10_000,
            files=2,
        )
        selection = router.select_model(item)
        assert selection.model_tier == ModelTier.SONNET

    def test_model_id_mapping_correct(self, router: ModelRouter) -> None:
        for tier, model_id in MODEL_ID_MAP.items():
            assert "claude" in model_id
            assert tier.value in model_id


class TestOutcomeTracking:
    def test_outcome_recording_creates_jsonl(self, tmp_path: Path) -> None:
        outcomes_file = tmp_path / "outcomes.jsonl"
        router = ModelRouter(outcomes_path=outcomes_file)

        record = OutcomeRecord(
            work_item_id="w-test",
            model_tier="sonnet",
            success=True,
            tokens_used=4500,
        )
        router.record_outcome(record)

        assert outcomes_file.exists()
        lines = outcomes_file.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["work_item_id"] == "w-test"
        assert data["success"] is True
        assert data["tokens_used"] == 4500

    def test_outcome_loading_on_init(self, router_with_outcomes: ModelRouter) -> None:
        assert len(router_with_outcomes.history) == 4
        opus_records = [r for r in router_with_outcomes.history if r.model_tier == "opus"]
        assert len(opus_records) == 2

    def test_historical_performance_empty(self, router: ModelRouter) -> None:
        perf = router.historical_performance("opus")
        assert perf["count"] == 0
        assert perf["success_rate"] == 0.0
        assert perf["avg_tokens"] == 0.0

    def test_historical_performance_with_data(
        self,
        router_with_outcomes: ModelRouter,
    ) -> None:
        opus_perf = router_with_outcomes.historical_performance("opus")
        assert opus_perf["count"] == 2
        assert opus_perf["success_rate"] == 1.0
        assert opus_perf["avg_tokens"] == 7000.0

        sonnet_perf = router_with_outcomes.historical_performance("sonnet")
        assert sonnet_perf["count"] == 1
        assert sonnet_perf["success_rate"] == 0.0
        assert sonnet_perf["avg_tokens"] == 3000.0
