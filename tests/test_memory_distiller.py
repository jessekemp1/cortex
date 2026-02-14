#!/usr/bin/env python3
"""Tests for compounding memory distiller."""

import json
from pathlib import Path

from intelligence.memory_distiller import MemoryDistiller


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_distills_patterns_and_counterfactual_alignment(tmp_path: Path):
    outcomes = tmp_path / "outcomes.jsonl"
    counterfactuals = tmp_path / "counterfactuals.jsonl"

    _write_jsonl(
        outcomes,
        [
            {"recommendation_type": "goal_progress", "outcome": "success"},
            {"recommendation_type": "goal_progress", "outcome": "failed"},
            {"recommendation_type": "investigation", "outcome": "success"},
        ],
    )
    _write_jsonl(
        counterfactuals,
        [
            {"recommended_action": "queue_now", "chosen_action": "queue_now"},
            {"recommended_action": "queue_now", "chosen_action": "skip"},
        ],
    )

    distiller = MemoryDistiller(outcomes_path=outcomes, counterfactual_path=counterfactuals)
    result = distiller.distill()

    assert result["totals"]["outcomes"] == 3
    assert result["totals"]["counterfactuals"] == 2
    assert len(result["memories"]) >= 2

