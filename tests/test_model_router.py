"""Tests for the model complexity router."""

from __future__ import annotations

import json
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Phase 2: Tests for route() API with TASK_MODEL_MAP + complexity overrides
# ---------------------------------------------------------------------------

from cortex.supervisor.router import (
    ModelAssignment,
    ModelRouter as ActualModelRouter,
)


def _make_phase2_item(
    task_type: str = "research",
    description: str = "A moderate-length description for testing",
    priority: WorkItemPriority = WorkItemPriority.MEDIUM,
    tokens: int = 5_000,
    files: int = 2,
) -> WorkItem:
    return WorkItem(
        id="p2-test",
        source="test",
        task_type=task_type,
        description=description,
        priority=priority,
        estimated_tokens=tokens,
        files=[f"f{i}.py" for i in range(files)],
    )


@pytest.fixture
def phase2_router(tmp_path: Path) -> ActualModelRouter:
    """Router with no outcomes file (clean state)."""
    return ActualModelRouter(outcomes_path=tmp_path / "nonexistent.jsonl")


@pytest.fixture
def phase2_router_with_outcomes(tmp_path: Path) -> ActualModelRouter:
    """Router pre-loaded with outcome stats for testing adjustment logic.

    Safety valve requires >=10 outcomes and at least 1 failure before downgrade.
    """
    outcomes_file = tmp_path / "outcomes.jsonl"
    records = []
    # sonnet on "implement" fails a lot (2/12 = 17% success -> should escalate)
    for i in range(12):
        records.append(
            {
                "work_item_id": f"w-impl-{i}",
                "model_tier": "sonnet",
                "task_type": "implement",
                "success": i < 2,  # first 2 succeed, rest fail
                "quality_score": 0.8 if i < 2 else 0.1,
                "timestamp": "2026-01-01T00:00:00",
            }
        )
    # opus on "planning" succeeds almost always (11/12 = 92%, 1 failure)
    for i in range(12):
        records.append(
            {
                "work_item_id": f"w-plan-{i}",
                "model_tier": "opus",
                "task_type": "planning",
                "success": i != 11,  # last one fails
                "quality_score": 0.95 if i != 11 else 0.2,
                "timestamp": "2026-01-01T00:00:00",
            }
        )
    outcomes_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return ActualModelRouter(outcomes_path=outcomes_file)


class TestPhase2Route:
    """Tests for the Phase 2 route() API."""

    def test_planning_routes_to_opus(self, phase2_router: ActualModelRouter) -> None:
        item = _make_phase2_item(task_type="planning")
        result = phase2_router.route(item)
        assert result.model == "opus"

    def test_implement_routes_to_sonnet(self, phase2_router: ActualModelRouter) -> None:
        item = _make_phase2_item(task_type="implement")
        result = phase2_router.route(item)
        assert result.model == "sonnet"

    def test_classify_routes_to_haiku(self, phase2_router: ActualModelRouter) -> None:
        item = _make_phase2_item(task_type="classify")
        result = phase2_router.route(item)
        assert result.model == "haiku"

    def test_unknown_task_defaults_to_sonnet(self, phase2_router: ActualModelRouter) -> None:
        item = _make_phase2_item(task_type="unknown_task_xyz")
        result = phase2_router.route(item)
        assert result.model == "sonnet"

    def test_simple_complexity_overrides_to_haiku(self, phase2_router: ActualModelRouter) -> None:
        """A 'planning' task that is clearly simple should override to haiku."""
        item = _make_phase2_item(
            task_type="planning",  # normally opus
            description="fix typo in readme",  # simple keyword
            priority=WorkItemPriority.LOW,
            files=0,
        )
        result = phase2_router.route(item)
        assert result.model == "haiku"
        assert "Complexity override" in result.rationale
        assert "simple" in result.rationale

    def test_complex_complexity_overrides_to_opus(self, phase2_router: ActualModelRouter) -> None:
        """A 'classify' task that is clearly complex should override to opus."""
        item = _make_phase2_item(
            task_type="classify",  # normally haiku
            description=(
                "migrate the entire classification pipeline from legacy system "
                + " ".join(f"word{i}" for i in range(120))
            ),
            priority=WorkItemPriority.CRITICAL,
            files=10,
        )
        result = phase2_router.route(item)
        assert result.model == "opus"
        assert "Complexity override" in result.rationale
        assert "complex" in result.rationale

    def test_moderate_complexity_uses_task_map(self, phase2_router: ActualModelRouter) -> None:
        """Moderate complexity should not override — uses TASK_MODEL_MAP."""
        item = _make_phase2_item(
            task_type="review",  # maps to sonnet in TASK_MODEL_MAP
            description="review the pull request changes for correctness",
            priority=WorkItemPriority.MEDIUM,
            files=3,
        )
        result = phase2_router.route(item)
        # Should use task map (review → sonnet), not a complexity override
        assert result.model == "sonnet"
        assert "Complexity override" not in result.rationale

    def test_outcome_adjustment_escalates(
        self, phase2_router_with_outcomes: ActualModelRouter
    ) -> None:
        """When sonnet has <40% success on 'implement', escalate to opus."""
        item = _make_phase2_item(task_type="implement")
        result = phase2_router_with_outcomes.route(item)
        assert result.model == "opus"
        assert "Escalated" in result.rationale

    def test_outcome_adjustment_downgrades(
        self, phase2_router_with_outcomes: ActualModelRouter
    ) -> None:
        """When opus has >90% success on 'planning', downgrade to sonnet."""
        item = _make_phase2_item(task_type="planning")
        result = phase2_router_with_outcomes.route(item)
        assert result.model == "sonnet"
        assert "Downgraded" in result.rationale

    def test_missing_outcomes_file_graceful(self, tmp_path: Path) -> None:
        """Router should not crash when outcomes file doesn't exist."""
        router = ActualModelRouter(outcomes_path=tmp_path / "does_not_exist" / "outcomes.jsonl")
        item = _make_phase2_item(task_type="test")
        result = router.route(item)
        assert result.model == "sonnet"
        assert result.confidence > 0.0

    def test_update_from_outcome_records(self, tmp_path: Path) -> None:
        """update_from_outcome should persist and update in-memory stats."""
        outcomes_file = tmp_path / "outcomes.jsonl"
        router = ActualModelRouter(outcomes_path=outcomes_file)

        # Record several outcomes
        for i in range(5):
            router.update_from_outcome("test", "sonnet", success=True)

        # Verify file was written
        assert outcomes_file.exists()
        lines = outcomes_file.read_text().strip().splitlines()
        assert len(lines) == 5

        # Verify in-memory stats updated
        stats = router._outcome_stats.get("test", {}).get("sonnet", {})
        assert stats["total"] == 5
        assert stats["success"] == 5

    def test_route_returns_model_assignment(self, phase2_router: ActualModelRouter) -> None:
        """route() must return a ModelAssignment with correct fields."""
        item = _make_phase2_item(task_type="research")
        result = phase2_router.route(item)
        assert isinstance(result, ModelAssignment)
        assert result.model in ("opus", "sonnet", "haiku")
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.rationale, str)
        assert len(result.rationale) > 0

    def test_safety_valve_no_downgrade_on_100pct_success(self, tmp_path: Path) -> None:
        """100% success with no failures = no real signal -> never downgrade."""
        outcomes_file = tmp_path / "all_success.jsonl"
        records = []
        # 15 records, all success (above min_outcomes=10 threshold)
        for i in range(15):
            records.append(
                {
                    "work_item_id": f"w-plan-{i}",
                    "model_tier": "opus",
                    "task_type": "planning",
                    "success": True,
                    "quality_score": 1.0,
                    "timestamp": "2026-01-01T00:00:00",
                }
            )
        outcomes_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        router = ActualModelRouter(outcomes_path=outcomes_file)

        item = _make_phase2_item(task_type="planning")
        result = router.route(item)
        # Must NOT downgrade: 100% success = no learning signal (safety valve)
        assert result.model == "opus"
        assert "Downgraded" not in result.rationale

    def test_safety_valve_requires_min_outcomes(self, tmp_path: Path) -> None:
        """Fewer than 10 outcomes -> no adjustment, use base model."""
        outcomes_file = tmp_path / "few.jsonl"
        records = []
        # Only 5 records (below min_outcomes=10)
        for i in range(5):
            records.append(
                {
                    "work_item_id": f"w-impl-{i}",
                    "model_tier": "sonnet",
                    "task_type": "implement",
                    "success": i < 1,
                    "quality_score": 0.8 if i < 1 else 0.1,
                    "timestamp": "2026-01-01T00:00:00",
                }
            )
        outcomes_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        router = ActualModelRouter(outcomes_path=outcomes_file)

        item = _make_phase2_item(task_type="implement")
        result = router.route(item)
        # Should use base model (sonnet) due to insufficient data
        assert result.model == "sonnet"
        assert "insufficient" in result.rationale.lower()
