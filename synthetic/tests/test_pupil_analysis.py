#!/usr/bin/env python3
"""Tests for Pupil MarketAnalyzer — intelligence extraction from simulation results."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from synthetic.schemas import CustomerProfile
from synthetic.pupil.market_env import (
    CompetitionEvent,
    EventType,
    build_timeline,
)
from synthetic.pupil.simulation import SimulationEngine
from synthetic.pupil.analysis import (
    AnalysisReport,
    MarketAnalyzer,
)


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


@pytest.fixture
def mixed_simulation_result():
    """Run a mixed-segment simulation and return the result."""
    profiles = []
    idx = 0
    for seg, count, income, deposits, credit in [
        ("mass_market", 30, 65000, 25000, 720),
        ("mass_affluent", 15, 110000, 80000, 760),
        ("affluent", 8, 250000, 200000, 790),
        ("high_net_worth", 4, 600000, 500000, 810),
        ("new_to_canada", 12, 45000, 5000, 650),
        ("small_business", 6, 85000, 40000, 700),
    ]:
        for _ in range(count):
            profiles.append(make_profile(
                profile_id=f"mix-{idx}",
                segment=seg,
                credit_score=credit,
                annual_income=income,
                total_deposits=deposits,
            ))
            idx += 1

    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(months=12)
    return engine.run(timeline)


@pytest.fixture
def stress_simulation_result():
    """Run a stress scenario for richer analysis."""
    profiles = []
    for i in range(60):
        seg = "mass_market" if i < 30 else "new_to_canada"
        profiles.append(make_profile(
            profile_id=f"stress-{i}",
            segment=seg,
            credit_score=680 if seg == "mass_market" else 620,
            total_deposits=20000 if seg == "mass_market" else 5000,
        ))

    engine = SimulationEngine(seed=42)
    engine.generate_agents(profiles)
    timeline = build_timeline(
        months=12,
        rate_schedule={0: 4.50, 3: 5.25, 6: 5.75},
        unemployment_schedule={0: 6.1, 4: 8.0, 8: 9.0},
        events={
            2: [CompetitionEvent(
                event_type=EventType.PRODUCT_LAUNCH,
                institution="EQ Bank",
                description="High-yield HISA",
                product="savings",
                rate_offered=5.5,
                impact_magnitude=0.9,
            )],
        },
    )
    return engine.run(timeline)


@pytest.fixture
def analyzer():
    return MarketAnalyzer()


# ============================================================================
# MarketAnalyzer Tests
# ============================================================================


class TestAnalyze:
    def test_returns_analysis_report(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert isinstance(report, AnalysisReport)

    def test_report_counts_match(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert report.n_agents == mixed_simulation_result.n_agents
        assert report.n_steps == mixed_simulation_result.n_steps

    def test_overall_churn_rate(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert 0.0 <= report.overall_churn_rate <= 1.0
        assert report.overall_churn_rate == pytest.approx(
            mixed_simulation_result.churn_rate, abs=1e-6
        )

    def test_has_segment_analyses(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert len(report.segment_analyses) > 0
        segments = {sa.segment for sa in report.segment_analyses}
        assert "mass_market" in segments
        assert "new_to_canada" in segments


class TestSegmentAnalysis:
    def test_segment_agent_counts(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        total = sum(sa.n_agents for sa in report.segment_analyses)
        assert total == mixed_simulation_result.n_agents

    def test_churn_rates_per_segment(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for sa in report.segment_analyses:
            assert 0.0 <= sa.churn_rate <= 1.0
            if sa.n_agents > 0:
                assert sa.churn_count <= sa.n_agents

    def test_satisfaction_per_segment(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for sa in report.segment_analyses:
            assert 0.0 <= sa.avg_satisfaction <= 1.0

    def test_products_per_segment(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for sa in report.segment_analyses:
            assert sa.avg_products >= 0

    def test_segment_to_dict(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for sa in report.segment_analyses:
            d = sa.to_dict()
            assert "segment" in d
            assert "churn_rate" in d
            assert "avg_satisfaction" in d
            assert "top_adopted_products" in d


class TestMigrationFlows:
    def test_flows_computed(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert isinstance(report.migration_flows, list)

    def test_flows_have_valid_states(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        valid_states = {"active", "at_risk", "churned", "dormant", "onboarding"}
        for flow in report.migration_flows:
            assert flow.from_state in valid_states, f"Invalid from_state: {flow.from_state}"
            assert flow.to_state in valid_states, f"Invalid to_state: {flow.to_state}"
            assert flow.from_state != flow.to_state

    def test_flows_have_counts(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for flow in report.migration_flows:
            assert flow.count > 0
            assert 0.0 < flow.pct_of_total <= 1.0

    def test_flow_to_dict(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        if report.migration_flows:
            d = report.migration_flows[0].to_dict()
            assert "from" in d
            assert "to" in d
            assert "count" in d

    def test_stress_produces_active_to_at_risk(self, analyzer, stress_simulation_result):
        """Stress scenario should produce active→at_risk transitions."""
        report = analyzer.analyze(stress_simulation_result)
        active_to_risk = [
            f for f in report.migration_flows
            if f.from_state == "active" and f.to_state == "at_risk"
        ]
        # Under stress, agents should move to at_risk
        assert len(active_to_risk) > 0 or report.overall_churn_rate > 0.1


class TestChurnCurve:
    def test_churn_curve_length(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert len(report.churn_curve) == mixed_simulation_result.n_steps

    def test_churn_curve_monotonic(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for i in range(1, len(report.churn_curve)):
            assert (
                report.churn_curve[i]["cumulative_churn"]
                >= report.churn_curve[i - 1]["cumulative_churn"]
            )

    def test_churn_curve_has_date_labels(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for entry in report.churn_curve:
            assert "date_label" in entry
            assert "monthly_churn" in entry
            assert "cumulative_churn" in entry
            assert "churn_rate" in entry


class TestDepositTrajectory:
    def test_trajectory_length(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert len(report.deposit_trajectory) == mixed_simulation_result.n_steps

    def test_trajectory_fields(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for entry in report.deposit_trajectory:
            assert "total_deposits" in entry
            assert "avg_deposits" in entry
            assert "n_active" in entry
            assert entry["total_deposits"] >= 0
            assert entry["avg_deposits"] >= 0

    def test_active_count_decreasing_or_stable(self, analyzer, mixed_simulation_result):
        """Active count should decrease or stay same as agents churn."""
        report = analyzer.analyze(mixed_simulation_result)
        for i in range(1, len(report.deposit_trajectory)):
            assert (
                report.deposit_trajectory[i]["n_active"]
                <= report.deposit_trajectory[0]["n_active"]
            )


class TestRiskTimeline:
    def test_risk_timeline_length(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert len(report.risk_timeline) == mixed_simulation_result.n_steps

    def test_risk_timeline_fields(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        for entry in report.risk_timeline:
            assert "at_risk_count" in entry
            assert "at_risk_pct" in entry
            assert entry["at_risk_count"] >= 0
            assert 0.0 <= entry["at_risk_pct"] <= 1.0

    def test_stress_increases_risk(self, analyzer, stress_simulation_result):
        report = analyzer.analyze(stress_simulation_result)
        # Under stress, at_risk should appear at some point
        max_at_risk = max(e["at_risk_count"] for e in report.risk_timeline)
        assert max_at_risk > 0 or report.overall_churn_rate > 0.1


class TestActionSummary:
    def test_action_summary_has_counts(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        assert isinstance(report.action_summary, dict)
        assert "hold" in report.action_summary  # At minimum, holds exist
        total = sum(report.action_summary.values())
        assert total == len(mixed_simulation_result.all_actions)

    def test_stress_has_diverse_actions(self, analyzer, stress_simulation_result):
        report = analyzer.analyze(stress_simulation_result)
        # Stress should produce more than just holds
        action_types = set(report.action_summary.keys())
        assert len(action_types) >= 2


class TestAnalysisReportSerialization:
    def test_summary_string(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        summary = report.summary()
        assert "agents" in summary
        assert "months" in summary
        assert "churn" in summary.lower()
        assert "satisfaction" in summary.lower()

    def test_to_dict_complete(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        d = report.to_dict()
        assert "n_agents" in d
        assert "segments" in d
        assert "migration_flows" in d
        assert "churn_curve" in d
        assert "deposit_trajectory" in d
        assert "risk_timeline" in d
        assert "action_summary" in d


class TestAnalysisConsistency:
    def test_segment_churn_sums_to_total(self, analyzer, mixed_simulation_result):
        report = analyzer.analyze(mixed_simulation_result)
        segment_churned = sum(sa.churn_count for sa in report.segment_analyses)
        final_churned = sum(
            1 for s in mixed_simulation_result.final_snapshots
            if s["state"] == "churned"
        )
        assert segment_churned == final_churned

    def test_deterministic_analysis(self, analyzer):
        """Same simulation → same analysis."""
        profiles = [make_profile(profile_id=f"det-{i}") for i in range(30)]
        timeline = build_timeline(months=6)

        e1 = SimulationEngine(seed=42)
        e1.generate_agents(profiles)
        r1 = e1.run(timeline)
        a1 = analyzer.analyze(r1)

        e2 = SimulationEngine(seed=42)
        e2.generate_agents(profiles)
        r2 = e2.run(timeline)
        a2 = analyzer.analyze(r2)

        assert a1.overall_churn_rate == pytest.approx(a2.overall_churn_rate, abs=1e-6)
        assert len(a1.segment_analyses) == len(a2.segment_analyses)


class TestModuleImports:
    """Verify the __init__.py exports work correctly."""

    def test_import_all_from_pupil(self):
        from synthetic.pupil import (
            MarketAnalyzer,
            PersonaAgent,
            SimulationEngine,
        )
        assert SimulationEngine is not None
        assert MarketAnalyzer is not None
        assert PersonaAgent is not None

    def test_pupil_version(self):
        from synthetic.pupil import __version__
        assert __version__ == "0.1.0"
