#!/usr/bin/env python3
"""
Pupil Bridge — Connects SyntheticGenerator output to Pupil simulation pipeline.

Provides a clean interface for feeding generated CustomerProfiles into
SimulationEngine and MarketAnalyzer without modifying either upstream module.

Architecture:
    SyntheticGenerator → profiles → PupilBridge
        → SimulationEngine.run(timeline) → SimulationResult
        → MarketAnalyzer.analyze(result) → AnalysisReport
"""

from typing import Any, Dict, List, Tuple

from .analysis import AnalysisReport, MarketAnalyzer
from .market_env import build_timeline
from .schemas import CustomerProfile
from .simulation import SimulationEngine, SimulationResult


class PupilBridge:
    """
    Connects SyntheticGenerator output to Pupil behavioral simulation.

    Usage:
        generator = SyntheticGenerator()
        result = generator.generate(GenerationRequest(data_type="profiles", count=100))
        profiles = ...  # extract profiles from result output

        bridge = PupilBridge()
        sim_result = bridge.from_profiles(profiles, months=12)
        sim_result, report = bridge.full_analysis(profiles, months=12)
    """

    def from_profiles(
        self,
        profiles: List[CustomerProfile],
        months: int = 12,
        seed: int = 42,
        **timeline_kwargs: Any,
    ) -> SimulationResult:
        """
        Run a Pupil simulation from generated profiles.

        Creates a SimulationEngine, generates agents from profiles,
        builds a timeline, and runs the simulation.

        Args:
            profiles: CustomerProfiles from SyntheticGenerator
            months: Number of months to simulate
            seed: Random seed for deterministic replay
            **timeline_kwargs: Passed to build_timeline (rate_schedule,
                events, unemployment_schedule, housing_schedule, etc.)

        Returns:
            SimulationResult with per-step and aggregate behavioral data
        """
        engine = SimulationEngine(seed=seed)
        engine.generate_agents(profiles, seed=seed)
        timeline = build_timeline(months=months, **timeline_kwargs)
        return engine.run(timeline)

    def full_analysis(
        self,
        profiles: List[CustomerProfile],
        months: int = 12,
        seed: int = 42,
        **timeline_kwargs: Any,
    ) -> Tuple[SimulationResult, AnalysisReport]:
        """
        Run simulation and market analysis from generated profiles.

        Args:
            profiles: CustomerProfiles from SyntheticGenerator
            months: Number of months to simulate
            seed: Random seed for deterministic replay
            **timeline_kwargs: Passed to build_timeline

        Returns:
            Tuple of (SimulationResult, AnalysisReport) for downstream use
        """
        sim_result = self.from_profiles(profiles, months=months, seed=seed, **timeline_kwargs)
        analyzer = MarketAnalyzer()
        report = analyzer.analyze(sim_result)
        return sim_result, report

    def scenario_comparison(
        self,
        profiles: List[CustomerProfile],
        scenarios: Dict[str, dict],
        months: int = 12,
        seed: int = 42,
    ) -> Dict[str, Tuple[SimulationResult, AnalysisReport]]:
        """
        Run multiple scenarios against the same profiles for comparison.

        Each scenario dict is passed as **kwargs to build_timeline,
        allowing rate schedules, events, and macro changes per scenario.

        Args:
            profiles: CustomerProfiles from SyntheticGenerator
            scenarios: {scenario_name: timeline_kwargs_dict}
            months: Number of months to simulate
            seed: Random seed (same seed across all scenarios for comparability)

        Returns:
            {scenario_name: (SimulationResult, AnalysisReport)}
        """
        results: Dict[str, Tuple[SimulationResult, AnalysisReport]] = {}

        for name, kwargs in scenarios.items():
            sim_result, report = self.full_analysis(profiles, months=months, seed=seed, **kwargs)
            results[name] = (sim_result, report)

        return results
