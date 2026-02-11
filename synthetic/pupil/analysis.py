#!/usr/bin/env python3
"""
Market Analyzer — Intelligence extraction from Pupil simulation results.

Transforms raw simulation data into actionable market intelligence:
- Churn analysis by segment, tenure, and satisfaction
- Migration flows between lifecycle states
- Product adoption/switching patterns
- Deposit sensitivity to rate changes
- Risk emergence detection

Architecture:
    SimulationResult → MarketAnalyzer.analyze() → AnalysisReport
    → SegmentAnalysis[] + MigrationFlow[] + summary metrics
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .persona import Action, ActionType
from .simulation import SimulationResult


@dataclass
class MigrationFlow:
    """State transition flow between two lifecycle states."""
    from_state: str
    to_state: str
    count: int
    pct_of_total: float  # Percentage of all agents

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_state,
            "to": self.to_state,
            "count": self.count,
            "pct_of_total": round(self.pct_of_total, 4),
        }


@dataclass
class SegmentAnalysis:
    """Analysis results for a single customer segment."""
    segment: str
    n_agents: int
    churn_count: int
    churn_rate: float
    avg_satisfaction: float
    avg_products: float
    avg_deposits: float
    adoption_count: int
    switch_count: int
    at_risk_count: int
    top_adopted_products: List[Tuple[str, int]] = field(default_factory=list)
    top_switch_targets: List[Tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment": self.segment,
            "n_agents": self.n_agents,
            "churn_count": self.churn_count,
            "churn_rate": round(self.churn_rate, 4),
            "avg_satisfaction": round(self.avg_satisfaction, 4),
            "avg_products": round(self.avg_products, 2),
            "avg_deposits": round(self.avg_deposits, 2),
            "adoption_count": self.adoption_count,
            "switch_count": self.switch_count,
            "at_risk_count": self.at_risk_count,
            "top_adopted_products": [
                {"product": p, "count": c} for p, c in self.top_adopted_products
            ],
            "top_switch_targets": [
                {"institution": i, "count": c} for i, c in self.top_switch_targets
            ],
        }


@dataclass
class AnalysisReport:
    """Complete analysis report from a simulation."""
    n_agents: int
    n_steps: int
    overall_churn_rate: float
    avg_final_satisfaction: float
    segment_analyses: List[SegmentAnalysis]
    migration_flows: List[MigrationFlow]
    churn_curve: List[Dict[str, Any]]  # [{step, cumulative_churn, churn_rate}]
    deposit_trajectory: List[Dict[str, Any]]  # [{step, total_deposits, avg_deposits}]
    risk_timeline: List[Dict[str, Any]]  # [{step, at_risk_count, at_risk_pct}]
    action_summary: Dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        top_churn = max(self.segment_analyses, key=lambda s: s.churn_rate)
        safest = min(self.segment_analyses, key=lambda s: s.churn_rate)
        return (
            f"Analysis: {self.n_agents} agents × {self.n_steps} months\n"
            f"  Overall churn: {self.overall_churn_rate:.1%}\n"
            f"  Avg satisfaction: {self.avg_final_satisfaction:.3f}\n"
            f"  Highest churn: {top_churn.segment} ({top_churn.churn_rate:.1%})\n"
            f"  Lowest churn: {safest.segment} ({safest.churn_rate:.1%})\n"
            f"  Migration flows: {len(self.migration_flows)}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_agents": self.n_agents,
            "n_steps": self.n_steps,
            "overall_churn_rate": round(self.overall_churn_rate, 4),
            "avg_final_satisfaction": round(self.avg_final_satisfaction, 4),
            "segments": [s.to_dict() for s in self.segment_analyses],
            "migration_flows": [m.to_dict() for m in self.migration_flows],
            "churn_curve": self.churn_curve,
            "deposit_trajectory": self.deposit_trajectory,
            "risk_timeline": self.risk_timeline,
            "action_summary": self.action_summary,
        }


class MarketAnalyzer:
    """
    Extracts market intelligence from Pupil simulation results.

    Produces segment-level analysis, migration flows, time-series
    metrics, and actionable summaries for banking strategy teams.
    """

    def analyze(self, result: SimulationResult) -> AnalysisReport:
        """
        Run full analysis on simulation results.

        Args:
            result: SimulationResult from SimulationEngine.run()

        Returns:
            AnalysisReport with segment, migration, and time-series analysis
        """
        segment_analyses = self._analyze_segments(result)
        migration_flows = self._compute_migration_flows(result)
        churn_curve = self._build_churn_curve(result)
        deposit_trajectory = self._build_deposit_trajectory(result)
        risk_timeline = self._build_risk_timeline(result)
        action_summary = self._summarize_actions(result)

        return AnalysisReport(
            n_agents=result.n_agents,
            n_steps=result.n_steps,
            overall_churn_rate=result.churn_rate,
            avg_final_satisfaction=result.avg_final_satisfaction,
            segment_analyses=segment_analyses,
            migration_flows=migration_flows,
            churn_curve=churn_curve,
            deposit_trajectory=deposit_trajectory,
            risk_timeline=risk_timeline,
            action_summary=action_summary,
        )

    def _analyze_segments(self, result: SimulationResult) -> List[SegmentAnalysis]:
        """Analyze results by customer segment."""
        # Group final snapshots by segment
        by_segment: Dict[str, List[Dict]] = defaultdict(list)
        for snap in result.final_snapshots:
            by_segment[snap["segment"]].append(snap)

        # Group actions by agent → segment
        agent_segments: Dict[str, str] = {}
        for snap in result.final_snapshots:
            agent_segments[snap["agent_id"]] = snap["segment"]

        # Count actions per segment
        segment_actions: Dict[str, List[Action]] = defaultdict(list)
        for action in result.all_actions:
            seg = agent_segments.get(action.agent_id, "unknown")
            segment_actions[seg].append(action)

        analyses = []
        for segment, snapshots in sorted(by_segment.items()):
            n = len(snapshots)
            churned = sum(1 for s in snapshots if s["state"] == "churned")
            at_risk = sum(1 for s in snapshots if s["state"] == "at_risk")
            active_sats = [s["satisfaction"] for s in snapshots if s["state"] != "churned"]

            actions = segment_actions.get(segment, [])
            adoptions = [a for a in actions if a.action_type == ActionType.ADOPT_PRODUCT]
            switches = [a for a in actions if a.action_type == ActionType.SWITCH_TO_COMPETITOR]

            # Top adopted products
            product_counts = Counter(a.product for a in adoptions if a.product)
            top_products = product_counts.most_common(5)

            # Top switch targets
            target_counts = Counter(a.target for a in switches if a.target)
            top_targets = target_counts.most_common(5)

            analyses.append(SegmentAnalysis(
                segment=segment,
                n_agents=n,
                churn_count=churned,
                churn_rate=churned / n if n > 0 else 0.0,
                avg_satisfaction=sum(active_sats) / len(active_sats) if active_sats else 0.0,
                avg_products=sum(s["product_count"] for s in snapshots) / n if n > 0 else 0.0,
                avg_deposits=sum(s["deposits"] for s in snapshots) / n if n > 0 else 0.0,
                adoption_count=len(adoptions),
                switch_count=len(switches),
                at_risk_count=at_risk,
                top_adopted_products=top_products,
                top_switch_targets=top_targets,
            ))

        return analyses

    def _compute_migration_flows(self, result: SimulationResult) -> List[MigrationFlow]:
        """Compute state transition flows across the simulation."""
        if len(result.steps) < 2:
            return []

        # Track state at each step per agent
        transitions = Counter()
        for i in range(1, len(result.steps)):
            prev_snaps = {s["agent_id"]: s["state"] for s in result.steps[i - 1].snapshots}
            curr_snaps = {s["agent_id"]: s["state"] for s in result.steps[i].snapshots}

            for agent_id, curr_state in curr_snaps.items():
                prev_state = prev_snaps.get(agent_id, curr_state)
                if prev_state != curr_state:
                    transitions[(prev_state, curr_state)] += 1

        flows = []
        for (from_s, to_s), count in transitions.most_common():
            flows.append(MigrationFlow(
                from_state=from_s,
                to_state=to_s,
                count=count,
                pct_of_total=count / result.n_agents if result.n_agents > 0 else 0.0,
            ))

        return flows

    def _build_churn_curve(self, result: SimulationResult) -> List[Dict[str, Any]]:
        """Build cumulative churn curve over time."""
        curve = []
        cumulative = 0
        for step_result in result.steps:
            cumulative += step_result.churn_count
            curve.append({
                "step": step_result.step,
                "date_label": step_result.date_label,
                "monthly_churn": step_result.churn_count,
                "cumulative_churn": cumulative,
                "churn_rate": cumulative / result.n_agents if result.n_agents > 0 else 0.0,
            })
        return curve

    def _build_deposit_trajectory(self, result: SimulationResult) -> List[Dict[str, Any]]:
        """Build deposit trajectory over time."""
        trajectory = []
        for step_result in result.steps:
            active_deposits = [
                s["deposits"] for s in step_result.snapshots
                if s["state"] != "churned"
            ]
            total = sum(active_deposits)
            avg = total / len(active_deposits) if active_deposits else 0.0
            trajectory.append({
                "step": step_result.step,
                "date_label": step_result.date_label,
                "total_deposits": round(total, 2),
                "avg_deposits": round(avg, 2),
                "n_active": len(active_deposits),
            })
        return trajectory

    def _build_risk_timeline(self, result: SimulationResult) -> List[Dict[str, Any]]:
        """Build at-risk population timeline."""
        timeline = []
        for step_result in result.steps:
            non_churned = sum(
                1 for s in step_result.snapshots if s["state"] != "churned"
            )
            timeline.append({
                "step": step_result.step,
                "date_label": step_result.date_label,
                "at_risk_count": step_result.n_at_risk,
                "at_risk_pct": (
                    step_result.n_at_risk / non_churned
                    if non_churned > 0 else 0.0
                ),
            })
        return timeline

    def _summarize_actions(self, result: SimulationResult) -> Dict[str, int]:
        """Count all action types across the simulation."""
        counts: Dict[str, int] = Counter()
        for action in result.all_actions:
            counts[action.action_type.value] += 1
        return dict(counts)
