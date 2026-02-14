#!/usr/bin/env python3
"""
Compounding Memory Distiller

Compresses outcome and counterfactual logs into reusable strategy primitives.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DistilledMemory:
    key: str
    confidence: float
    evidence_count: int
    summary: str
    tags: tuple[str, ...]


class MemoryDistiller:
    """Weekly distillation helper for high-signal strategy memory."""

    def __init__(
        self,
        outcomes_path: Path | None = None,
        counterfactual_path: Path | None = None,
    ):
        self.outcomes_path = outcomes_path or (Path.home() / ".cortex" / "outcomes.jsonl")
        self.counterfactual_path = counterfactual_path or (Path.home() / ".cortex" / "counterfactuals.jsonl")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def distill(self) -> dict[str, Any]:
        outcomes = self._load_jsonl(self.outcomes_path)
        counterfactuals = self._load_jsonl(self.counterfactual_path)

        if not outcomes and not counterfactuals:
            return {"memories": [], "totals": {"outcomes": 0, "counterfactuals": 0}}

        by_type = Counter()
        success_by_type = defaultdict(lambda: {"success": 0, "total": 0})
        for row in outcomes:
            rec_type = row.get("recommendation_type", "unknown")
            by_type[rec_type] += 1
            success_by_type[rec_type]["total"] += 1
            if row.get("outcome") == "success":
                success_by_type[rec_type]["success"] += 1

        mismatches = sum(
            1
            for row in counterfactuals
            if row.get("recommended_action") != row.get("chosen_action")
        )

        memories: list[DistilledMemory] = []
        for rec_type, count in by_type.most_common(5):
            stats = success_by_type[rec_type]
            confidence = stats["success"] / stats["total"] if stats["total"] else 0.0
            summary = (
                f"{rec_type}: success={stats['success']}/{stats['total']} "
                f"({confidence:.2f}), occurrences={count}"
            )
            memories.append(
                DistilledMemory(
                    key=f"pattern:{rec_type}",
                    confidence=round(confidence, 3),
                    evidence_count=count,
                    summary=summary,
                    tags=("pattern", "outcome"),
                )
            )

        if counterfactuals:
            mismatch_rate = mismatches / len(counterfactuals)
            memories.append(
                DistilledMemory(
                    key="counterfactual:follow_alignment",
                    confidence=round(1.0 - mismatch_rate, 3),
                    evidence_count=len(counterfactuals),
                    summary=(
                        f"follow_alignment={1.0 - mismatch_rate:.2f}, "
                        f"mismatches={mismatches}/{len(counterfactuals)}"
                    ),
                    tags=("counterfactual", "strategy"),
                )
            )

        return {
            "memories": [memory.__dict__ for memory in memories],
            "totals": {
                "outcomes": len(outcomes),
                "counterfactuals": len(counterfactuals),
            },
        }

