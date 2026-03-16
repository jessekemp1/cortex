"""
Routing benchmark — standardized test suite for evaluating routing accuracy.

10 tasks spanning all complexity levels. Run each against the router and
compare prediction vs expected tier. Optionally run against all available
models to compare quality/cost/latency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cortex.supervisor.models import WorkItem, WorkItemPriority

log = logging.getLogger(__name__)


@dataclass
class BenchmarkTask:
    """A standardized benchmark task."""

    description: str
    task_type: str
    expected_tier: str  # "haiku" | "sonnet" | "opus"
    files: List[str] = field(default_factory=list)
    priority: WorkItemPriority = WorkItemPriority.MEDIUM
    estimated_tokens: int = 5000


@dataclass
class BenchmarkResult:
    """Result of running a benchmark task."""

    task: BenchmarkTask
    routed_tier: str
    routed_model: str
    routed_provider: str = "anthropic"
    correct: bool = False  # routed_tier matches expected_tier
    complexity_score: float = 0.0
    quality_score: Optional[float] = None  # If actually dispatched
    cost_usd: Optional[float] = None
    latency_seconds: Optional[float] = None


BENCHMARK_TASKS: List[BenchmarkTask] = [
    BenchmarkTask(
        description="Find all TODO comments in the project",
        task_type="classify",
        expected_tier="haiku",
        estimated_tokens=1000,
        priority=WorkItemPriority.LOW,
    ),
    BenchmarkTask(
        description="List files modified in the last commit",
        task_type="classify",
        expected_tier="haiku",
        estimated_tokens=500,
        priority=WorkItemPriority.LOW,
    ),
    BenchmarkTask(
        description="Fix the off-by-one error in pagination logic",
        task_type="fix",
        expected_tier="sonnet",
        files=["app/api/pagination.py"],
        estimated_tokens=5000,
    ),
    BenchmarkTask(
        description="Write unit tests for the authentication middleware",
        task_type="test",
        expected_tier="sonnet",
        files=["app/middleware/auth.py", "tests/test_auth.py"],
        estimated_tokens=8000,
    ),
    BenchmarkTask(
        description="Research best practices for rate limiting in FastAPI",
        task_type="research",
        expected_tier="sonnet",
        estimated_tokens=10000,
    ),
    BenchmarkTask(
        description="Implement a retry mechanism with exponential backoff for API calls",
        task_type="implement",
        expected_tier="sonnet",
        files=["app/core/http_client.py"],
        estimated_tokens=8000,
    ),
    BenchmarkTask(
        description="Review the database migration for potential data loss",
        task_type="review",
        expected_tier="sonnet",
        files=["migrations/002_add_indexes.py"],
        estimated_tokens=5000,
    ),
    BenchmarkTask(
        description="Design the authentication middleware architecture for multi-tenant support",
        task_type="architecture",
        expected_tier="opus",
        files=["app/middleware/", "app/models/tenant.py", "app/core/auth/"],
        estimated_tokens=50000,
        priority=WorkItemPriority.HIGH,
    ),
    BenchmarkTask(
        description="Refactor the entire event processing pipeline from synchronous to async",
        task_type="refactor",
        expected_tier="opus",
        files=[f"app/events/handler_{i}.py" for i in range(10)],
        estimated_tokens=80000,
        priority=WorkItemPriority.HIGH,
    ),
    BenchmarkTask(
        description="Conduct a security audit of the API endpoints and authentication flow",
        task_type="security",
        expected_tier="opus",
        files=["app/api/", "app/middleware/auth.py", "app/core/crypto.py"],
        estimated_tokens=60000,
        priority=WorkItemPriority.CRITICAL,
    ),
]


class RoutingBenchmark:
    """Run the benchmark suite against a router."""

    def run(
        self,
        router: Any,
        registry: Any = None,
    ) -> List[BenchmarkResult]:
        """Run all benchmark tasks through the router.

        Args:
            router: ModelRouter instance
            registry: Optional ProviderRegistry for multi-provider routing

        Returns:
            List of BenchmarkResult (one per task)
        """
        results = []

        for task in BENCHMARK_TASKS:
            work_item = WorkItem(
                id=f"bench-{task.task_type}-{len(results)}",
                source="benchmark",
                task_type=task.task_type,
                description=task.description,
                priority=task.priority,
                estimated_tokens=task.estimated_tokens,
                files=task.files,
            )

            if hasattr(router, "route_advanced"):
                selection = router.route_advanced(work_item)
            elif registry and hasattr(router, "select_model_with_provider"):
                selection = router.select_model_with_provider(work_item, registry)
            else:
                selection = router.select_model(work_item)

            result = BenchmarkResult(
                task=task,
                routed_tier=selection.model_tier,
                routed_model=selection.model_id,
                routed_provider=getattr(selection, "provider", "anthropic"),
                correct=selection.model_tier == task.expected_tier,
                complexity_score=selection.complexity_score,
            )
            results.append(result)

        return results

    def report(self, results: List[BenchmarkResult]) -> str:
        """Generate an ASCII report of benchmark results."""
        total = len(results)
        correct = sum(1 for r in results if r.correct)
        accuracy = correct / total * 100 if total > 0 else 0

        lines = [
            "┌─────────────────────────────────────────────────────────────┐",
            "│              Routing Benchmark Results                      │",
            "├───────────────────┬──────────┬──────────┬──────────┬───────┤",
            "│ Task Type         │ Expected │ Routed   │ Provider │  OK   │",
            "├───────────────────┼──────────┼──────────┼──────────┼───────┤",
        ]

        for r in results:
            ok = "✓" if r.correct else "✗"
            lines.append(
                f"│ {r.task.task_type:<17} │ {r.task.expected_tier:<8} │ "
                f"{r.routed_tier:<8} │ {r.routed_provider:<8} │  {ok}    │"
            )

        lines.extend(
            [
                "├───────────────────┴──────────┴──────────┴──────────┴───────┤",
                f"│ Accuracy: {correct}/{total} ({accuracy:.0f}%)                                     │",
                "└─────────────────────────────────────────────────────────────┘",
            ]
        )

        return "\n".join(lines)
