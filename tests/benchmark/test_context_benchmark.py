"""
Tests for Context Optimization Benchmark.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.benchmark.context_benchmark import ContextBenchmark


class TestContextBenchmark:
    """Test the benchmark itself produces valid, reproducible results."""

    def test_benchmark_produces_reproducible_results(self):
        """Run benchmark twice — position quality score should be identical."""
        benchmark = ContextBenchmark()

        result1 = benchmark.run_benchmark()
        result2 = benchmark.run_benchmark()

        assert result1.metrics.position_quality_score == result2.metrics.position_quality_score
        assert result1.metrics.total_items == result2.metrics.total_items
        assert result1.metrics.dedup_savings_pct == result2.metrics.dedup_savings_pct

    def test_realistic_context_has_duplicates(self):
        """The test data actually contains overlapping items that get deduplicated."""
        benchmark = ContextBenchmark()
        result = benchmark.run_benchmark()

        assert result.duplicate_pairs_found > 0
        assert result.items_after < result.items_before

    def test_report_format(self):
        """Report contains required sections and measured percentages."""
        benchmark = ContextBenchmark()
        result = benchmark.run_benchmark()
        report = benchmark.format_report(result)

        assert "Position Quality Score:" in report
        assert "Dedup savings:" in report
        assert "%" in report
        assert "Items before dedup:" in report
        assert "Items after dedup:" in report
