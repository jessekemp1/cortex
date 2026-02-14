#!/usr/bin/env python3
"""
Counterfactual Learning Ledger

Tracks recommended action vs chosen action and estimates missed value
when recommendations are not followed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CounterfactualEntry:
    timestamp: str
    recommendation_id: str
    project: str
    recommended_action: str
    chosen_action: str
    expected_value: float
    actual_value: float | None = None
    confidence: float = 0.0
    rationale: str = ""


class CounterfactualLedger:
    """JSONL-backed ledger with lightweight summary/estimation helpers."""

    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".cortex" / "counterfactuals.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_entry(self, entry: CounterfactualEntry) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry)) + "\n")

    def record(
        self,
        recommendation_id: str,
        project: str,
        recommended_action: str,
        chosen_action: str,
        expected_value: float,
        actual_value: float | None = None,
        confidence: float = 0.0,
        rationale: str = "",
    ) -> CounterfactualEntry:
        entry = CounterfactualEntry(
            timestamp=datetime.now().isoformat(),
            recommendation_id=recommendation_id,
            project=project,
            recommended_action=recommended_action,
            chosen_action=chosen_action,
            expected_value=expected_value,
            actual_value=actual_value,
            confidence=confidence,
            rationale=rationale,
        )
        self.log_entry(entry)
        return entry

    def load_entries(self) -> list[CounterfactualEntry]:
        if not self.path.exists():
            return []
        rows: list[CounterfactualEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                rows.append(CounterfactualEntry(**data))
        return rows

    @staticmethod
    def estimate_missed_value(entries: Iterable[CounterfactualEntry]) -> float:
        """
        Proxy estimate:
        - If recommendation not followed, expected value counts as opportunity.
        - If actual value exists, subtract it from expected to estimate miss.
        """
        missed_total = 0.0
        for entry in entries:
            if entry.recommended_action == entry.chosen_action:
                continue
            if entry.actual_value is None:
                missed_total += max(entry.expected_value, 0.0)
            else:
                missed_total += max(entry.expected_value - entry.actual_value, 0.0)
        return round(missed_total, 3)

    def summarize(self) -> dict:
        entries = self.load_entries()
        if not entries:
            return {
                "count": 0,
                "follow_rate": 0.0,
                "missed_value_estimate": 0.0,
            }

        followed = sum(1 for e in entries if e.recommended_action == e.chosen_action)
        follow_rate = followed / len(entries)
        missed = self.estimate_missed_value(entries)

        return {
            "count": len(entries),
            "follow_rate": round(follow_rate, 3),
            "missed_value_estimate": missed,
        }

