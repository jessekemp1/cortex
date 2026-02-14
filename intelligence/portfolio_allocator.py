#!/usr/bin/env python3
"""
Portfolio Allocator

Rebalances weekly attention (hours) across projects using weighted
risk/opportunity/strategic signals while enforcing caps and minimums.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectSignal:
    project: str
    risk: float
    opportunity: float
    strategic_alignment: float


@dataclass(frozen=True)
class Allocation:
    project: str
    hours: float
    share: float
    score: float


@dataclass(frozen=True)
class AllocationWeights:
    risk_weight: float = 0.4
    opportunity_weight: float = 0.4
    strategic_weight: float = 0.2


class PortfolioAllocator:
    """Deterministic allocator suitable for daily rebalance routines."""

    def __init__(self, weights: AllocationWeights | None = None):
        self.weights = weights or AllocationWeights()

    def _score(self, signal: ProjectSignal) -> float:
        return max(
            0.0,
            self.weights.risk_weight * signal.risk
            + self.weights.opportunity_weight * signal.opportunity
            + self.weights.strategic_weight * signal.strategic_alignment,
        )

    def allocate(
        self,
        signals: list[ProjectSignal],
        total_hours: float = 40.0,
        min_hours_per_project: float = 2.0,
        max_share_per_project: float = 0.5,
    ) -> list[Allocation]:
        if not signals:
            return []
        if total_hours <= 0:
            raise ValueError("total_hours must be positive")

        base_hours = min_hours_per_project * len(signals)
        if base_hours > total_hours:
            raise ValueError("total_hours too small for minimum allocation constraints")

        scores = {signal.project: self._score(signal) for signal in signals}
        score_total = sum(scores.values())
        variable_budget = total_hours - base_hours

        provisional: dict[str, float] = {
            signal.project: min_hours_per_project for signal in signals
        }

        if score_total > 0 and variable_budget > 0:
            for signal in signals:
                proportional = (scores[signal.project] / score_total) * variable_budget
                provisional[signal.project] += proportional

        # Apply hard cap and redistribute remainder.
        cap_hours = max_share_per_project * total_hours
        overflow = 0.0
        capped: dict[str, float] = {}
        for project, hours in provisional.items():
            if hours > cap_hours:
                overflow += hours - cap_hours
                capped[project] = cap_hours
            else:
                capped[project] = hours

        if overflow > 0:
            recipients = [p for p, h in capped.items() if h < cap_hours]
            if recipients:
                recipient_total_score = sum(scores[p] for p in recipients) or len(recipients)
                for project in recipients:
                    if recipient_total_score == len(recipients):
                        add = overflow / len(recipients)
                    else:
                        add = overflow * (scores[project] / recipient_total_score)
                    capped[project] = min(cap_hours, capped[project] + add)

        # Final normalization to eliminate floating drift.
        allocated_total = sum(capped.values())
        if allocated_total > 0:
            scale = total_hours / allocated_total
            for project in list(capped.keys()):
                capped[project] *= scale

        result = [
            Allocation(
                project=signal.project,
                hours=round(capped[signal.project], 3),
                share=round(capped[signal.project] / total_hours, 4),
                score=round(scores[signal.project], 4),
            )
            for signal in signals
        ]
        return sorted(result, key=lambda x: x.hours, reverse=True)

