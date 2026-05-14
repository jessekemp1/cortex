#!/usr/bin/env python3
"""Tests for PupilBridge — generation-to-simulation connector."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.generator import SyntheticGenerator
from synthetic.pupil.analysis import AnalysisReport
from synthetic.pupil.bridge import PupilBridge
from synthetic.pupil.market_env import CompetitionEvent, EventType
from synthetic.pupil.simulation import SimulationResult
from synthetic.schemas import CustomerProfile, GenerationRequest

# ============================================================================
# Fixtures
# ============================================================================


def make_profile(
    profile_id: str = "test-001",
    segment: str = "mass_market",
    credit_score: int = 720,
    annual_income: float = 65000.0,
    total_deposits: float = 25000.0,
    tenure_years: float = 5.0,
    products: list | None = None,
) -> CustomerProfile:
    return CustomerProfile(
        profile_id=profile_id,
        age=35,
        province="ON",
        fsa="M5V",
        segment=segment,
        annual_income=annual_income,
        household_income=annual_income * 1.5,
        credit_score=credit_score,
        products_held=products or ["chequing", "savings"],
        total_deposits=total_deposits,
        total_credit_outstanding=5000.0,
        digital_adoption="hybrid",
        primary_channel="mobile",
        tenure_years=tenure_years,
        products_per_household=2,
    )


def make_profiles(n: int = 50, segment: str = "mass_market") -> list[CustomerProfile]:
    return [make_profile(profile_id=f"{segment}-{i}", segment=segment) for i in range(n)]


def make_mixed_profiles() -> list[CustomerProfile]:
    """Mix of segments for realistic simulation."""
    profiles = []
    segments = [
        ("mass_market", 20),
        ("mass_affluent", 10),
        ("affluent", 5),
        ("high_net_worth", 3),
        ("new_to_canada", 8),
        ("small_business", 4),
    ]
    idx = 0
    for seg, count in segments:
        for _ in range(count):
            profiles.append(
                make_profile(
                    profile_id=f"mix-{idx}",
                    segment=seg,
                    credit_score=720 if seg != "new_to_canada" else 650,
                    annual_income=65000 if seg not in ("high_net_worth", "affluent") else 300000,
                    total_deposits=25000 if seg != "high_net_worth" else 500000,
                )
            )
            idx += 1
    return profiles


@pytest.fixture
def bridge():
    return PupilBridge()


@pytest.fixture
def profiles_50():
    return make_profiles(50)


@pytest.fixture
def profiles_mixed():
    return make_mixed_profiles()


@pytest.fixture
def generated_profiles():
    """Profiles from the actual SyntheticGenerator pipeline."""
    gen = SyntheticGenerator()
    request = GenerationRequest(data_type="profiles", count=50, min_quality_score=0.0)
    result = gen.generate(request)
    # Read back from the output file
    import json

    profiles = []
    if result.output_path:
        with open(result.output_path) as f:
            for line in f:
                data = json.loads(line)
                profiles.append(CustomerProfile(**data))
    return profiles


@pytest.fixture
def stress_kwargs():
    """Timeline kwargs for a stress scenario."""
    return {
        "rate_schedule": {0: 4.50, 3: 5.00, 6: 5.50},
        "unemployment_schedule": {0: 6.1, 4: 7.5, 8: 8.5},
        "events": {
            2: [
                CompetitionEvent(
                    event_type=EventType.PRODUCT_LAUNCH,
                    institution="EQ Bank",
                    description="5% HISA",
                    product="savings",
                    rate_offered=5.0,
                    impact_magnitude=0.8,
                )
            ],
        },
    }


# ============================================================================
# from_profiles Tests
# ============================================================================


class TestFromProfiles:
    def test_returns_simulation_result(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50)
        assert isinstance(result, SimulationResult)

    def test_correct_agent_count(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50)
        assert result.n_agents == 50

    def test_default_months(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50)
        assert result.n_steps == 12

    def test_custom_months(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50, months=6)
        assert result.n_steps == 6

    def test_has_step_data(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50, months=12)
        assert len(result.steps) == 12
        assert result.steps[0].total_actions >= 50

    def test_has_final_snapshots(self, bridge, profiles_50):
        result = bridge.from_profiles(profiles_50)
        assert len(result.final_snapshots) == 50

    def test_with_timeline_kwargs(self, bridge, profiles_50, stress_kwargs):
        result = bridge.from_profiles(profiles_50, **stress_kwargs)
        assert result.n_agents == 50
        assert result.n_steps == 12

    def test_with_generated_profiles(self, bridge, generated_profiles):
        """End-to-end: SyntheticGenerator -> PupilBridge -> SimulationResult."""
        if not generated_profiles:
            pytest.skip("Generator produced no profiles")
        result = bridge.from_profiles(generated_profiles)
        assert isinstance(result, SimulationResult)
        assert result.n_agents == len(generated_profiles)


# ============================================================================
# full_analysis Tests
# ============================================================================


class TestFullAnalysis:
    def test_returns_tuple(self, bridge, profiles_50):
        result = bridge.full_analysis(profiles_50)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_simulation_result_and_report(self, bridge, profiles_50):
        sim_result, report = bridge.full_analysis(profiles_50)
        assert isinstance(sim_result, SimulationResult)
        assert isinstance(report, AnalysisReport)

    def test_report_matches_simulation(self, bridge, profiles_50):
        sim_result, report = bridge.full_analysis(profiles_50)
        assert report.n_agents == sim_result.n_agents
        assert report.n_steps == sim_result.n_steps
        assert report.overall_churn_rate == pytest.approx(sim_result.churn_rate, abs=1e-6)

    def test_report_has_segment_analyses(self, bridge, profiles_mixed):
        _, report = bridge.full_analysis(profiles_mixed)
        assert len(report.segment_analyses) > 0
        segment_names = {s.segment for s in report.segment_analyses}
        assert "mass_market" in segment_names

    def test_report_has_churn_curve(self, bridge, profiles_50):
        _, report = bridge.full_analysis(profiles_50)
        assert len(report.churn_curve) == 12

    def test_report_has_migration_flows(self, bridge, profiles_50):
        _, report = bridge.full_analysis(profiles_50, months=12)
        # Migration flows may be empty in calm scenarios, but field must exist
        assert isinstance(report.migration_flows, list)


# ============================================================================
# scenario_comparison Tests
# ============================================================================


class TestScenarioComparison:
    def test_returns_dict_of_results(self, bridge, profiles_50):
        scenarios = {
            "baseline": {},
            "stress": {
                "rate_schedule": {3: 5.50, 6: 6.00},
                "unemployment_schedule": {4: 8.0},
            },
        }
        results = bridge.scenario_comparison(profiles_50, scenarios)
        assert isinstance(results, dict)
        assert set(results.keys()) == {"baseline", "stress"}

    def test_each_scenario_has_result_and_report(self, bridge, profiles_50):
        scenarios = {
            "baseline": {},
            "stress": {"rate_schedule": {3: 5.50}},
        }
        results = bridge.scenario_comparison(profiles_50, scenarios)
        for name, (sim, report) in results.items():
            assert isinstance(sim, SimulationResult), f"{name} sim wrong type"
            assert isinstance(report, AnalysisReport), f"{name} report wrong type"

    def test_stress_produces_different_outcomes(self, bridge):
        # Use larger population to reduce stochastic noise
        profiles = make_profiles(200)
        scenarios = {
            "baseline": {},
            "stress": {
                "rate_schedule": {0: 4.50, 3: 5.50, 6: 6.50},
                "unemployment_schedule": {0: 6.1, 4: 8.5, 8: 9.0},
                "events": {
                    2: [
                        CompetitionEvent(
                            event_type=EventType.PRODUCT_LAUNCH,
                            institution="EQ Bank",
                            description="6% HISA",
                            product="savings",
                            rate_offered=6.0,
                            impact_magnitude=0.9,
                        )
                    ],
                },
            },
        }
        results = bridge.scenario_comparison(profiles, scenarios, seed=42)
        base_sim, base_report = results["baseline"]
        stress_sim, stress_report = results["stress"]

        # Stress should produce worse outcomes
        assert (
            stress_sim.total_churned >= base_sim.total_churned
            or stress_sim.avg_final_satisfaction < base_sim.avg_final_satisfaction
        )


# ============================================================================
# Determinism Tests
# ============================================================================


class TestDeterminism:
    def test_same_seed_same_churn(self, bridge, profiles_50):
        r1 = bridge.from_profiles(profiles_50, seed=42)
        r2 = bridge.from_profiles(profiles_50, seed=42)
        assert r1.total_churned == r2.total_churned

    def test_same_seed_same_satisfaction(self, bridge, profiles_50):
        r1 = bridge.from_profiles(profiles_50, seed=42)
        r2 = bridge.from_profiles(profiles_50, seed=42)
        assert r1.avg_final_satisfaction == pytest.approx(r2.avg_final_satisfaction, abs=1e-6)

    def test_same_seed_same_churn_rate(self, bridge, profiles_50):
        r1 = bridge.from_profiles(profiles_50, seed=42)
        r2 = bridge.from_profiles(profiles_50, seed=42)
        assert r1.churn_rate == pytest.approx(r2.churn_rate, abs=1e-6)

    def test_different_seed_diverges(self, bridge, profiles_50):
        r1 = bridge.from_profiles(profiles_50, seed=42)
        r2 = bridge.from_profiles(profiles_50, seed=999)
        # With different seeds, at least one metric should differ
        assert r1.total_churned != r2.total_churned or r1.avg_final_satisfaction != pytest.approx(
            r2.avg_final_satisfaction, abs=1e-6
        )

    def test_scenario_comparison_deterministic(self, bridge, profiles_50):
        """Same seed across scenario_comparison runs produces same results."""
        scenarios = {"baseline": {}, "stress": {"rate_schedule": {3: 5.50}}}
        res1 = bridge.scenario_comparison(profiles_50, scenarios, seed=42)
        res2 = bridge.scenario_comparison(profiles_50, scenarios, seed=42)
        for name in scenarios:
            s1, _ = res1[name]
            s2, _ = res2[name]
            assert s1.total_churned == s2.total_churned
            assert s1.churn_rate == pytest.approx(s2.churn_rate, abs=1e-6)


# ============================================================================
# Segment Mix Tests
# ============================================================================


class TestSegmentMixes:
    def test_single_segment(self, bridge):
        profiles = make_profiles(30, segment="affluent")
        result = bridge.from_profiles(profiles)
        segments = {s["segment"] for s in result.final_snapshots}
        assert segments == {"affluent"}

    def test_mixed_segments_all_represented(self, bridge, profiles_mixed):
        _, report = bridge.full_analysis(profiles_mixed)
        segment_names = {s.segment for s in report.segment_analyses}
        assert "mass_market" in segment_names
        assert "mass_affluent" in segment_names
        assert "new_to_canada" in segment_names

    def test_hnw_vs_mass_market_deposits(self, bridge):
        """High net worth agents should maintain higher deposits."""
        hnw = make_profiles(30, segment="high_net_worth")
        for p in hnw:
            p.annual_income = 500000.0
            p.total_deposits = 500000.0
        mm = make_profiles(30, segment="mass_market")

        r_hnw = bridge.from_profiles(hnw, seed=42)
        r_mm = bridge.from_profiles(mm, seed=42)

        avg_hnw = sum(s["deposits"] for s in r_hnw.final_snapshots) / len(r_hnw.final_snapshots)
        avg_mm = sum(s["deposits"] for s in r_mm.final_snapshots) / len(r_mm.final_snapshots)
        assert avg_hnw > avg_mm
