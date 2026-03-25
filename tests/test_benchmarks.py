"""Tests for the routing benchmark (Phase 5).

Tests:
  - Benchmark tasks are well-defined
  - Benchmark runs against router
  - Report generation
  - Accuracy calculation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.supervisor.benchmarks import (
    BENCHMARK_TASKS,
    BenchmarkResult,
    RoutingBenchmark,
)
from cortex.supervisor.router import ModelRouter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBenchmarkTasks:
    def test_has_tasks(self) -> None:
        assert len(BENCHMARK_TASKS) == 10

    def test_all_tiers_covered(self) -> None:
        tiers = {t.expected_tier for t in BENCHMARK_TASKS}
        assert "haiku" in tiers
        assert "sonnet" in tiers
        assert "opus" in tiers

    def test_all_tasks_have_description(self) -> None:
        for task in BENCHMARK_TASKS:
            assert len(task.description) > 10

    def test_all_tasks_have_type(self) -> None:
        for task in BENCHMARK_TASKS:
            assert task.task_type


class TestRoutingBenchmark:
    def test_run_produces_results(self, tmp_path: Path) -> None:
        router = ModelRouter(outcomes_path=tmp_path / "outcomes.jsonl")
        benchmark = RoutingBenchmark()
        results = benchmark.run(router)
        assert len(results) == 10

    def test_all_results_have_fields(self, tmp_path: Path) -> None:
        router = ModelRouter(outcomes_path=tmp_path / "outcomes.jsonl")
        benchmark = RoutingBenchmark()
        results = benchmark.run(router)
        for r in results:
            assert r.routed_tier in ("haiku", "sonnet", "opus")
            assert isinstance(r.correct, bool)
            assert r.complexity_score >= 0.0

    def test_report_generation(self, tmp_path: Path) -> None:
        router = ModelRouter(outcomes_path=tmp_path / "outcomes.jsonl")
        benchmark = RoutingBenchmark()
        results = benchmark.run(router)
        report = benchmark.report(results)
        assert "Routing Benchmark Results" in report
        assert "Accuracy" in report

    def test_some_correct_routing(self, tmp_path: Path) -> None:
        """At least some tasks should route to the expected tier."""
        router = ModelRouter(outcomes_path=tmp_path / "outcomes.jsonl")
        benchmark = RoutingBenchmark()
        results = benchmark.run(router)
        correct = sum(1 for r in results if r.correct)
        # Should get at least 3/10 right (haiku tasks are easy to route)
        assert correct >= 3
