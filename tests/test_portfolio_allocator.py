#!/usr/bin/env python3
"""Tests for portfolio attention allocator."""

from intelligence.portfolio_allocator import PortfolioAllocator, ProjectSignal


def test_allocate_respects_total_and_cap():
    allocator = PortfolioAllocator()
    signals = [
        ProjectSignal("vortex", risk=0.8, opportunity=0.9, strategic_alignment=0.9),
        ProjectSignal("cortex", risk=0.6, opportunity=0.8, strategic_alignment=0.8),
        ProjectSignal("alpha_arena", risk=0.4, opportunity=0.5, strategic_alignment=0.5),
    ]

    allocations = allocator.allocate(
        signals,
        total_hours=40,
        min_hours_per_project=2,
        max_share_per_project=0.5,
    )

    total = sum(item.hours for item in allocations)
    assert round(total, 2) == 40.00
    assert all(item.share <= 0.5 for item in allocations)
    assert allocations[0].project in {"vortex", "cortex"}


def test_allocate_raises_when_minimums_exceed_budget():
    allocator = PortfolioAllocator()
    signals = [
        ProjectSignal("vortex", risk=0.7, opportunity=0.7, strategic_alignment=0.7),
        ProjectSignal("cortex", risk=0.7, opportunity=0.7, strategic_alignment=0.7),
    ]

    try:
        allocator.allocate(signals, total_hours=3, min_hours_per_project=2)
        assert False, "expected ValueError"
    except ValueError:
        assert True

