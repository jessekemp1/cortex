# Paper: Portfolio Allocator

## Abstract
Portfolio Allocator rebalances attention daily across projects by weighted risk, opportunity, and strategic alignment under strict cap/min constraints.

## Problem
Static time allocation causes strategic drift and underfunds emerging high-leverage work.

## Method
- Score projects from normalized signals.
- Allocate constrained attention budget with cap and minimum floors.
- Rebalance daily.

## Engineering Status
- Implemented: `cortex/intelligence/portfolio_allocator.py`
- Tested: `cortex/tests/test_portfolio_allocator.py`

## Evaluation Plan
- Compare fixed-split baseline vs allocator for 10 weeks.
- Metrics: throughput, goal alignment, blocker response latency.

## Risks
- Signal quality drift; mitigated by freshness gates and override policy.
