#!/usr/bin/env python3
"""
Pre-Mortem Forecasting

Generates likely failure narratives for initiatives and proposes mitigation tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Initiative:
    name: str
    complexity: float  # 0-1
    dependency_risk: float  # 0-1
    deadline_pressure: float  # 0-1
    context: str = ""


@dataclass(frozen=True)
class FailureNarrative:
    initiative: str
    risk_score: float
    narrative: str
    mitigations: tuple[str, ...]


class PreMortemEngine:
    """Deterministic pre-mortem generator suitable for queue pre-work."""

    def _score(self, initiative: Initiative) -> float:
        return round(
            0.4 * initiative.complexity
            + 0.35 * initiative.dependency_risk
            + 0.25 * initiative.deadline_pressure,
            3,
        )

    def generate(self, initiatives: Iterable[Initiative]) -> list[FailureNarrative]:
        narratives: list[FailureNarrative] = []
        for item in initiatives:
            score = self._score(item)
            narrative = (
                f"{item.name} may miss expected outcomes due to "
                f"complexity/dependency/deadline coupling (risk={score})."
            )
            mitigations = (
                "Run targeted dependency validation before implementation.",
                "Create rollback path and test it before rollout.",
                "Queue focused review for highest-risk module.",
            )
            narratives.append(
                FailureNarrative(
                    initiative=item.name,
                    risk_score=score,
                    narrative=narrative,
                    mitigations=mitigations,
                )
            )
        return sorted(narratives, key=lambda n: n.risk_score, reverse=True)

    def route_mitigations(self, narratives: Iterable[FailureNarrative]) -> list[dict]:
        """
        Convert narratives into queue-ready mitigation actions.
        """
        actions: list[dict] = []
        for narrative in narratives:
            priority = "high" if narrative.risk_score >= 0.7 else "normal"
            for mitigation in narrative.mitigations:
                actions.append(
                    {
                        "initiative": narrative.initiative,
                        "priority": priority,
                        "task_type": "research",
                        "action": mitigation,
                        "context": f"pre-mortem:risk={narrative.risk_score}",
                    }
                )
        return actions

