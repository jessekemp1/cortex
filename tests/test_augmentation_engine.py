#!/usr/bin/env python3
"""
Tests for AugmentationEngine

Covers: AugmentedIdea structure, confidence calculation, offline bridge,
graph pass, prior outcomes pass, counter-arguments, and JSONL persistence.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortex.engines.augmentation_engine import AugmentationEngine, AugmentedIdea


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """AugmentationEngine with isolated JSONL log."""
    monkeypatch.setattr(
        "cortex.engines.augmentation_engine.AUGMENTATIONS_PATH",
        tmp_path / "augmentations.jsonl",
    )
    return AugmentationEngine()


@pytest.fixture
def offline_engine(tmp_path, monkeypatch):
    """Engine where bridge is unreachable (expected behaviour in CI)."""
    monkeypatch.setattr(
        "cortex.engines.augmentation_engine.AUGMENTATIONS_PATH",
        tmp_path / "augmentations.jsonl",
    )
    return AugmentationEngine(bridge_url="http://127.0.0.1:19999")  # No server


# ─── AugmentedIdea dataclass ─────────────────────────────────


def test_augmented_idea_to_dict():
    idea = AugmentedIdea(
        original="add caching",
        project="vortex",
        refined="add caching. (Relates to pattern: cache invalidation)",
        related_patterns=["cache invalidation"],
        prior_outcomes=[],
        counter_arguments=["Cache invalidation adds complexity."],
        confidence=0.5,
        augmentation_id="aug_abc123",
    )
    d = idea.to_dict()
    assert d["original"] == "add caching"
    assert d["project"] == "vortex"
    assert isinstance(d["timestamp"], str)
    assert "T" in d["timestamp"]  # ISO format


def test_augmented_idea_has_all_fields():
    idea = AugmentedIdea(
        original="test",
        project="cortex",
        refined="test.",
        related_patterns=[],
        prior_outcomes=[],
        counter_arguments=[],
        confidence=0.1,
        augmentation_id="aug_xyz",
    )
    assert idea.augmentation_id == "aug_xyz"
    assert idea.phase == "build"  # default


# ─── augment method ──────────────────────────────────────────


def test_augment_returns_augmented_idea(offline_engine):
    result = offline_engine.augment("add caching to forecast API", "vortex")
    assert isinstance(result, AugmentedIdea)


def test_augment_preserves_original(offline_engine):
    result = offline_engine.augment("my idea text", "cortex", "design")
    assert result.original == "my idea text"
    assert result.project == "cortex"
    assert result.phase == "design"


def test_augment_produces_refined_string(offline_engine):
    result = offline_engine.augment("refactor ensemble selector", "vortex")
    assert isinstance(result.refined, str)
    assert len(result.refined) >= len("refactor ensemble selector")


def test_augment_counter_arguments_nonempty(offline_engine):
    result = offline_engine.augment("add new endpoint for weather", "vortex")
    assert len(result.counter_arguments) >= 1
    assert all(isinstance(c, str) for c in result.counter_arguments)


def test_augment_related_patterns_list(offline_engine):
    result = offline_engine.augment("implement caching layer", "pupil")
    assert isinstance(result.related_patterns, list)


def test_augment_confidence_in_range(offline_engine):
    result = offline_engine.augment("improve test coverage", "cortex")
    assert 0.0 <= result.confidence <= 1.0


def test_augment_unique_ids(offline_engine):
    r1 = offline_engine.augment("idea one", "vortex")
    r2 = offline_engine.augment("idea two", "cortex")
    assert r1.augmentation_id != r2.augmentation_id


# ─── Offline bridge behaviour ────────────────────────────────


def test_augment_bridge_offline_returns_result(offline_engine):
    """Should succeed even when bridge is unreachable."""
    result = offline_engine.augment("design auth flow", "pupil")
    assert isinstance(result, AugmentedIdea)
    assert result.confidence >= 0.1  # Baseline confidence always present


def test_bridge_query_empty_when_offline(offline_engine):
    data = offline_engine._query_bridge("test query")
    assert data == {}


# ─── Counter-arguments ───────────────────────────────────────


def test_counter_args_for_caching_idea(offline_engine):
    result = offline_engine.augment("add Redis caching to reduce latency", "vortex")
    combined = " ".join(result.counter_arguments).lower()
    assert "cache" in combined or "complex" in combined or "stale" in combined


def test_counter_args_for_refactor(offline_engine):
    result = offline_engine.augment("refactor the data pipeline", "cortex")
    combined = " ".join(result.counter_arguments).lower()
    assert "refactor" in combined or "test" in combined or "risk" in combined


# ─── Persistence ─────────────────────────────────────────────


def test_augmentation_persisted_to_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "augmentations.jsonl"
    monkeypatch.setattr(
        "cortex.engines.augmentation_engine.AUGMENTATIONS_PATH",
        log_path,
    )
    eng = AugmentationEngine(bridge_url="http://127.0.0.1:19999")
    eng.augment("build new feature", "vortex")

    assert log_path.exists()
    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["original"] == "build new feature"
    assert record["project"] == "vortex"


def test_multiple_augmentations_appended(tmp_path, monkeypatch):
    log_path = tmp_path / "augmentations.jsonl"
    monkeypatch.setattr(
        "cortex.engines.augmentation_engine.AUGMENTATIONS_PATH",
        log_path,
    )
    eng = AugmentationEngine(bridge_url="http://127.0.0.1:19999")
    eng.augment("idea A", "vortex")
    eng.augment("idea B", "cortex")
    eng.augment("idea C", "pupil")

    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 3


# ─── Confidence calculation ──────────────────────────────────


def test_confidence_baseline_always_present():
    eng = AugmentationEngine()
    score = eng._calculate_confidence([], [], {})
    assert score == 0.1  # Baseline alone


def test_confidence_increases_with_patterns():
    eng = AugmentationEngine()
    score_0 = eng._calculate_confidence([], [], {})
    score_2 = eng._calculate_confidence(["pat1", "pat2"], [], {})
    assert score_2 > score_0


def test_confidence_capped_at_1():
    eng = AugmentationEngine()
    score = eng._calculate_confidence(["p"] * 10, ["o"] * 10, {"patterns": ["x"]})
    assert score <= 1.0
