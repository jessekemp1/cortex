#!/usr/bin/env python3
"""
Market Environment — Simulated market conditions for Pupil agent simulations.

Defines the world that agents observe and react to at each time step.
Supports event injection for scenario testing (rate changes, competition,
macro shocks).

Data sources for defaults:
- Bank of Canada overnight rate: 4.50% (Jan 2026)
- StatsCan unemployment: 6.1% (Dec 2025)
- StatsCan CPI: 2.8% YoY (Dec 2025)
- CREA housing price index: +2.3% YoY (Q4 2025)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EventType(str, Enum):
    """Types of market events agents can respond to."""
    RATE_CHANGE = "rate_change"
    PRODUCT_LAUNCH = "product_launch"
    FEE_CHANGE = "fee_change"
    MARKETING_CAMPAIGN = "campaign"
    MACRO_SHOCK = "macro_shock"
    REGULATORY = "regulatory"


@dataclass
class CompetitionEvent:
    """A competitive or market event that agents respond to."""
    event_type: EventType
    institution: str
    description: str
    product: Optional[str] = None
    rate_offered: Optional[float] = None
    target_segment: Optional[str] = None
    impact_magnitude: float = 0.5  # 0.0-1.0

    def affects_segment(self, segment: str) -> bool:
        """Check if this event targets a specific segment."""
        if self.target_segment is None:
            return True
        return self.target_segment == segment


@dataclass
class MarketEnvironment:
    """Market conditions for a single time step (month)."""
    month: int          # 1-12
    year: int           # e.g., 2026
    step: int           # Simulation step number (0-indexed)

    # Macro indicators
    boc_overnight_rate: float = 4.50
    unemployment_rate: float = 6.1
    cpi_yoy: float = 2.8
    housing_price_yoy: float = 2.3
    gdp_growth: float = 1.5

    # Banking market rates (derived from BoC)
    avg_savings_rate: float = 3.50
    avg_mortgage_rate_5yr: float = 5.20
    avg_gic_rate_1yr: float = 4.00

    # Events this month
    events: List[CompetitionEvent] = field(default_factory=list)

    @property
    def date_label(self) -> str:
        """Human-readable date label."""
        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        return f"{months[self.month - 1]} {self.year}"

    def rate_delta_from(self, baseline_rate: float) -> float:
        """Calculate rate change from a baseline."""
        return self.boc_overnight_rate - baseline_rate


def build_timeline(
    months: int = 12,
    start_year: int = 2026,
    start_month: int = 1,
    base_rate: float = 4.50,
    base_unemployment: float = 6.1,
    base_housing_yoy: float = 2.3,
    rate_schedule: Optional[Dict[int, float]] = None,
    unemployment_schedule: Optional[Dict[int, float]] = None,
    housing_schedule: Optional[Dict[int, float]] = None,
    events: Optional[Dict[int, List[CompetitionEvent]]] = None,
) -> List[MarketEnvironment]:
    """
    Build a timeline of market environments for simulation.

    Args:
        months: Number of months to simulate
        start_year: Starting year
        start_month: Starting month (1-12)
        base_rate: Initial BoC overnight rate
        base_unemployment: Initial unemployment rate
        base_housing_yoy: Initial housing price YoY change
        rate_schedule: {step: new_rate} for rate changes at specific steps
        unemployment_schedule: {step: new_rate} for unemployment changes
        housing_schedule: {step: new_yoy} for housing price changes
        events: {step: [CompetitionEvent, ...]} for event injection

    Returns:
        List of MarketEnvironment, one per month
    """
    rate_schedule = rate_schedule or {}
    unemployment_schedule = unemployment_schedule or {}
    housing_schedule = housing_schedule or {}
    events = events or {}

    timeline = []
    current_rate = base_rate
    current_unemployment = base_unemployment
    current_housing = base_housing_yoy

    for step in range(months):
        m = ((start_month - 1 + step) % 12) + 1
        y = start_year + (start_month - 1 + step) // 12

        if step in rate_schedule:
            current_rate = rate_schedule[step]
        if step in unemployment_schedule:
            current_unemployment = unemployment_schedule[step]
        if step in housing_schedule:
            current_housing = housing_schedule[step]

        # Derive market rates from BoC overnight rate
        avg_mortgage = current_rate + 0.70
        avg_savings = max(0.0, current_rate - 1.00)
        avg_gic = max(0.0, current_rate - 0.50)

        env = MarketEnvironment(
            month=m,
            year=y,
            step=step,
            boc_overnight_rate=current_rate,
            unemployment_rate=current_unemployment,
            housing_price_yoy=current_housing,
            avg_savings_rate=avg_savings,
            avg_mortgage_rate_5yr=avg_mortgage,
            avg_gic_rate_1yr=avg_gic,
            events=events.get(step, []),
        )
        timeline.append(env)

    return timeline
