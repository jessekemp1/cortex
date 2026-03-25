"""Tests for core.py QualityEvaluator wiring.

Verifies that _estimate_quality() was replaced with QualityEvaluator
and the dispatch loop records multi-dimensional quality scores.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from cortex.supervisor.core import _get_quality_evaluator
from cortex.supervisor.quality_evaluator import QualityEvaluation, QualityEvaluator


class TestQualityEvaluatorWiring:
    def test_get_quality_evaluator_returns_instance(self) -> None:
        evaluator = _get_quality_evaluator()
        assert isinstance(evaluator, QualityEvaluator)

    def test_get_quality_evaluator_is_singleton(self) -> None:
        e1 = _get_quality_evaluator()
        e2 = _get_quality_evaluator()
        assert e1 is e2

    def test_evaluator_produces_quality_evaluation(self) -> None:
        evaluator = _get_quality_evaluator()
        work_item = MagicMock()
        work_item.task_type = "implement"
        work_item.description = "Add authentication middleware"

        result = MagicMock()
        result.success = True
        result.output = (
            "```python\ndef auth_middleware():\n    pass\n```\n\nThis implements JWT auth."
        )

        evaluation = evaluator.evaluate_heuristic(work_item, result)
        assert isinstance(evaluation, QualityEvaluation)
        assert 0.0 <= evaluation.overall_score <= 1.0
        assert "success" in evaluation.dimensions
        assert "structure" in evaluation.dimensions
        assert evaluation.evaluator == "heuristic"

    def test_failed_result_gets_zero(self) -> None:
        evaluator = _get_quality_evaluator()
        work_item = MagicMock()
        result = MagicMock()
        result.success = False

        evaluation = evaluator.evaluate_heuristic(work_item, result)
        assert evaluation.overall_score == 0.0

    def test_estimate_quality_removed(self) -> None:
        """Verify _estimate_quality is no longer importable from core."""
        import cortex.supervisor.core as core_module

        assert not hasattr(core_module, "_estimate_quality")


class TestTeamOrchestratorWiring:
    def test_team_orchestrator_disabled_by_default(self) -> None:
        """When enable_teams=False, _get_team_orchestrator returns None."""
        from cortex.supervisor.config import SupervisorConfig
        from cortex.supervisor.core import CortexSupervisor

        config = SupervisorConfig(enable_teams=False, enable_self_healing=False)
        supervisor = CortexSupervisor(config=config)
        assert supervisor._get_team_orchestrator() is None

    def test_team_orchestrator_enabled(self) -> None:
        """When enable_teams=True, returns a TeamOrchestrator."""
        from cortex.supervisor.config import SupervisorConfig
        from cortex.supervisor.core import CortexSupervisor
        from cortex.supervisor.teams import TeamOrchestrator

        config = SupervisorConfig(enable_teams=True, enable_self_healing=False)
        supervisor = CortexSupervisor(config=config)
        orchestrator = supervisor._get_team_orchestrator()
        assert isinstance(orchestrator, TeamOrchestrator)


class TestMetricsWiring:
    def test_metrics_initialized(self) -> None:
        from cortex.supervisor.config import SupervisorConfig
        from cortex.supervisor.core import CortexSupervisor
        from cortex.supervisor.metrics import OrchestrationMetrics

        config = SupervisorConfig(enable_self_healing=False)
        supervisor = CortexSupervisor(config=config)
        assert isinstance(supervisor._metrics, OrchestrationMetrics)
