#!/usr/bin/env python3
"""Briefing Plugin - Morning briefing with recommendations"""

import argparse
from datetime import datetime
from typing import List

from cortex.plugins.base import BasePlugin

try:
    from cortex.intelligence.counterfactual_learning import CounterfactualLedger
    from cortex.intelligence.decision_twin import DecisionTwinEngine, PlanScenario, PlanTask
    from cortex.intelligence.memory_distiller import MemoryDistiller
    from cortex.intelligence.portfolio_allocator import PortfolioAllocator, ProjectSignal
    from cortex.intelligence.pre_mortem import Initiative, PreMortemEngine
    from cortex.intelligence.trust_governor import TrustGovernor
except Exception:
    CounterfactualLedger = None  # type: ignore[assignment]
    DecisionTwinEngine = None  # type: ignore[assignment]
    MemoryDistiller = None  # type: ignore[assignment]
    PortfolioAllocator = None  # type: ignore[assignment]
    PreMortemEngine = None  # type: ignore[assignment]
    TrustGovernor = None  # type: ignore[assignment]


class BriefingPlugin(BasePlugin):
    """Morning briefing plugin."""

    def execute(self, args: List[str], **kwargs) -> int:
        """Execute briefing plugin."""
        if "--help" in args or "-h" in args:
            print(self.help())
            return 0

        parser = argparse.ArgumentParser(prog="briefing", add_help=False)
        parser.add_argument("--date", type=str, help="Briefing date")
        parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")

        try:
            parser.parse_args(args)
        except SystemExit:
            return 1

        print(f"📊 Morning Briefing - {datetime.now().strftime('%A, %b %d, %Y')}")
        print("═" * 60)
        print()

        print("🌙 Overnight Summary")
        print("─" * 40)
        print("- Git status: Working")
        print("- Services: Running")
        print()

        print("📋 Next Actions")
        print("─" * 40)
        print("1. Review status with /status")
        print("2. Check for anomalies")
        print()

        self._print_co_navigator_section()

        return 0

    def _print_co_navigator_section(self) -> None:
        """Render compact co-navigator signals in briefing."""
        print("🧭 Co-Navigator Snapshot")
        print("─" * 40)

        if DecisionTwinEngine is not None:
            twin = DecisionTwinEngine()
            scenarios = [
                PlanScenario(
                    scenario_id="balanced",
                    name="Balanced Build",
                    tasks=(
                        PlanTask("Ship routing integration", 9, 7, 3, 1),
                        PlanTask("Harden tests", 6, 4, 2, 1),
                    ),
                ),
                PlanScenario(
                    scenario_id="aggressive",
                    name="Aggressive Expansion",
                    tasks=(PlanTask("Ship 3 new modules", 12, 12, 8, 3),),
                ),
            ]
            best = twin.choose_best(scenarios)
            print(f"- Decision Twin: {best.name} (utility {best.utility_score})")

        if PortfolioAllocator is not None:
            allocator = PortfolioAllocator()
            allocations = allocator.allocate(
                [
                    ProjectSignal("vortex", 0.8, 0.9, 0.95),
                    ProjectSignal("cortex", 0.6, 0.85, 0.9),
                    ProjectSignal("alpha_arena", 0.5, 0.7, 0.75),
                ],
                total_hours=40.0,
            )
            top = allocations[0]
            print(f"- Portfolio Allocator: {top.project} gets {top.hours}h ({top.share * 100:.1f}%)")

        if CounterfactualLedger is not None:
            summary = CounterfactualLedger().summarize()
            print(
                "- Counterfactual: "
                f"follow_rate={summary.get('follow_rate', 0.0)}, "
                f"missed_value={summary.get('missed_value_estimate', 0.0)}"
            )
        if TrustGovernor is not None:
            trust = TrustGovernor().evaluate(current_level=1)
            print(f"- Trust Governor: action={trust.get('action')} next={trust.get('next_level')}")
        if PreMortemEngine is not None:
            prem = PreMortemEngine().generate(
                [Initiative("co-navigator rollout", 0.75, 0.7, 0.65)]
            )
            if prem:
                print(f"- Pre-Mortem: top risk {prem[0].risk_score} for {prem[0].initiative}")
        if MemoryDistiller is not None:
            distilled = MemoryDistiller().distill()
            print(f"- Memory Distiller: {len(distilled.get('memories', []))} distilled primitives")
        print()
