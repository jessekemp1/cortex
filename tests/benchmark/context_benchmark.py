"""
Context Optimization Benchmark.

Measures real impact of lost-in-the-middle reordering and deduplication
using realistic Cortex preamble data (CLAUDE.md, GOALS.md, session context).
"""

from dataclasses import dataclass
from typing import List

import sys
from pathlib import Path

# Ensure cortex root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from intelligence.context_optimizer import (
    CategoryType,
    ContextItem,
    ContextOptimizer,
    OptimizationMetrics,
)


@dataclass
class BenchmarkResult:
    """Full benchmark result."""

    metrics: OptimizationMetrics
    items_before: int
    items_after: int
    duplicate_pairs_found: int


class ContextBenchmark:
    """Measure real context optimization impact with realistic data."""

    def build_realistic_context(self) -> List[ContextItem]:
        """Build context items mimicking real Cortex preamble (CLAUDE.md, GOALS.md, session data)."""
        items = [
            # System instructions (high importance)
            ContextItem(
                content="You are an AI assistant for a software engineering monorepo. "
                "Follow the project conventions. Use type hints. Run tests before committing.",
                importance=1.0,
                category=CategoryType.INSTRUCTION,
                source="CLAUDE.md",
            ),
            ContextItem(
                content="Recommend with options: When presenting choices, give 2-3 options "
                "with (Recommended) marked. Reserve questions for destructive operations.",
                importance=0.95,
                category=CategoryType.INSTRUCTION,
                source="CLAUDE.md",
            ),
            ContextItem(
                content="Anti-patterns: Never force push to main. Never commit without tests. "
                "Never mock DB in integration tests. Never use permissive assertions.",
                importance=0.9,
                category=CategoryType.INSTRUCTION,
                source="CLAUDE.md",
            ),
            # Project goals (high importance)
            ContextItem(
                content="Active goals: Vortex V4 stability, Cortex OSS launch, "
                "Alpha Arena cold start on $5K paper account.",
                importance=0.85,
                category=CategoryType.DATA,
                source="GOALS.md",
            ),
            ContextItem(
                content="Vortex Backend: 2835+ tests. PRODUCTION :8000. V4 shipped. "
                "HRRR EMOS auto-fit LIVE. Competition: 295K pairs.",
                importance=0.8,
                category=CategoryType.DATA,
                source="GOALS.md",
            ),
            # Examples (medium-high importance)
            ContextItem(
                content="Example: To run Vortex tests use pytest Vortex/backend/tests/ -v. "
                "For Alpha Arena use pytest alpha_arena/tests/ -v.",
                importance=0.75,
                category=CategoryType.EXAMPLE,
                source="CLAUDE.md",
            ),
            ContextItem(
                content="Example: Database session import uses from app.database.connection "
                "import db_connection then db_connection.get_session().",
                importance=0.7,
                category=CategoryType.EXAMPLE,
                source="CLAUDE.md",
            ),
            # Session context (medium importance)
            ContextItem(
                content="Last session worked on GRIB parallel loading optimization. "
                "Reduced forecast latency from 15s to 4s with ThreadPoolExecutor(3).",
                importance=0.65,
                category=CategoryType.HISTORY,
                source="session",
            ),
            ContextItem(
                content="Previous session deployed SQLite WAL mode for production cache. "
                "Resolved concurrent read/write contention under load.",
                importance=0.55,
                category=CategoryType.HISTORY,
                source="session",
            ),
            ContextItem(
                content="Session decision: Examined Engineer v1.1 verified with 13/13 checks. "
                "Three gaps found and resolved.",
                importance=0.5,
                category=CategoryType.HISTORY,
                source="session",
            ),
            # Retrieved patterns (medium importance)
            ContextItem(
                content="Pattern: Vortex ensemble selects winning model PER FIELD based on "
                "last 6 hours of competition. Does NOT simply average.",
                importance=0.7,
                category=CategoryType.DATA,
                source="retrieved",
            ),
            ContextItem(
                content="Pattern: GRIB longitude convention - ds.interp() does NOT auto-convert. "
                "Must pass coordinates in grid native convention (0-360).",
                importance=0.65,
                category=CategoryType.DATA,
                source="retrieved",
            ),
            # Lower-priority context
            ContextItem(
                content="Ship log 2026-03-07: Vortex V2 shipped to production worktree. "
                "3 test fixes. Production at main HEAD.",
                importance=0.35,
                category=CategoryType.HISTORY,
                source="MEMORY.md",
            ),
            ContextItem(
                content="Ship log 2026-03-08: Orchestration V2 complete. Supervisor CLI, "
                "MCP server rewired, dead phase agents deleted.",
                importance=0.4,
                category=CategoryType.HISTORY,
                source="MEMORY.md",
            ),
            ContextItem(
                content="Known gotcha: kempion-research-site is a git submodule. "
                "Build uses tsc -b which is stricter than tsc --noEmit.",
                importance=0.3,
                category=CategoryType.DATA,
                source="MEMORY.md",
            ),
            ContextItem(
                content="Known gotcha: Monorepo local_ci.sh covers 7 projects. "
                "Runs on pre-push via scripts/safety/local_ci.sh.",
                importance=0.25,
                category=CategoryType.DATA,
                source="MEMORY.md",
            ),
            # Duplicate/overlapping items (realistic: same info from different sources)
            ContextItem(
                content="Active goals: Vortex V4 stability, Cortex OSS launch, "
                "Alpha Arena cold start on $5K paper account.",
                importance=0.6,
                category=CategoryType.DATA,
                source="session_context",
            ),
            ContextItem(
                content="Anti-patterns: Never force push to main. Never commit without tests. "
                "Never mock DB in integration tests. Never use permissive assertions.",
                importance=0.7,
                category=CategoryType.DATA,
                source="retrieved",
            ),
            ContextItem(
                content="Vortex Backend: 2835+ tests. PRODUCTION :8000. V4 shipped. "
                "HRRR EMOS auto-fit LIVE. Competition: 295K pairs. Stratified ensemble enabled.",
                importance=0.6,
                category=CategoryType.HISTORY,
                source="session_context",
            ),
            ContextItem(
                content="Pattern: GRIB longitude convention - ds.interp() does NOT auto-convert. "
                "Must pass coordinates in grid native convention (0-360).",
                importance=0.5,
                category=CategoryType.HISTORY,
                source="session_patterns",
            ),
        ]
        return items

    def run_benchmark(self) -> BenchmarkResult:
        """Run full benchmark: measure dedup + position quality + generate report."""
        items = self.build_realistic_context()
        items_before = len(items)

        optimizer = ContextOptimizer()

        # Deduplicate first
        deduped, tokens_saved = optimizer.deduplicate(items)

        # Count duplicate pairs removed
        duplicate_pairs_found = items_before - len(deduped)

        # Optimize ordering
        optimized = optimizer.optimize_context(deduped)

        # Measure
        metrics = optimizer.measure_optimization(items, optimized)

        return BenchmarkResult(
            metrics=metrics,
            items_before=items_before,
            items_after=len(optimized),
            duplicate_pairs_found=duplicate_pairs_found,
        )

    def format_report(self, result: BenchmarkResult) -> str:
        """Human-readable report with measured percentages."""
        m = result.metrics
        lines = [
            "=== Context Optimization Benchmark Report ===",
            "",
            f"Items before dedup:       {result.items_before}",
            f"Items after dedup:        {result.items_after}",
            f"Duplicates removed:       {result.duplicate_pairs_found}",
            "",
            f"Tokens before:            {m.total_tokens_before}",
            f"Tokens after:             {m.total_tokens_after}",
            f"Dedup savings:            {m.dedup_savings_pct:.1f}%",
            "",
            f"Position Quality Score:   {m.position_quality_score:.2f}",
            f"Items in optimal position: {m.items_in_optimal_position}/{m.total_items}",
            "",
            "=== End Report ===",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    benchmark = ContextBenchmark()
    result = benchmark.run_benchmark()
    print(benchmark.format_report(result))
