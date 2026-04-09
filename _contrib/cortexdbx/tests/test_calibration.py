"""Tests for calibration engine."""

from cortexdbx.calibration.engine import CalibrationEngine, CalibrationState
from cortexdbx.synthetic.generator import SyntheticDataGenerator


def test_calibration_state_confidence_no_evidence():
    state = CalibrationState(alpha=1.0, beta=1.0, success_count=0, failure_count=0, partial_count=0)
    assert state.confidence == 0.5
    assert state.evidence_count == 0


def test_calibration_state_confidence_after_success():
    state = CalibrationState(alpha=2.0, beta=1.0, success_count=1, failure_count=0, partial_count=0)
    assert state.confidence == 2.0 / 3.0


def test_calibration_engine_update_success():
    engine = CalibrationEngine(prior_alpha=1.0, prior_beta=1.0)
    state = engine.update("ctx_1", "strat_1", "SUCCESS")
    assert state.success_count == 1
    assert state.failure_count == 0
    assert state.confidence > 0.5


def test_calibration_engine_update_failure():
    engine = CalibrationEngine(prior_alpha=1.0, prior_beta=1.0)
    state = engine.update("ctx_1", "strat_1", "FAILURE")
    assert state.success_count == 0
    assert state.failure_count == 1
    assert state.confidence < 0.5


def test_calibration_engine_update_partial():
    engine = CalibrationEngine(prior_alpha=1.0, prior_beta=1.0)
    engine.update("ctx_1", "strat_1", "PARTIAL")
    state = engine.get_state("ctx_1", "strat_1")
    assert state.partial_count == 1
    assert state.alpha == 1.5
    assert state.beta == 1.5


def test_calibration_engine_get_confidence_no_data():
    engine = CalibrationEngine()
    conf, explanation = engine.get_confidence("ctx_x", "strat_x")
    assert conf == 0.5
    assert "No historical data" in explanation


def test_calibration_engine_ingest_outcomes():
    engine = CalibrationEngine()
    outcomes = [
        {"context_id": "c1", "strategy_id": "s1", "result": "SUCCESS"},
        {"context_id": "c1", "strategy_id": "s1", "result": "FAILURE"},
        {"context_id": "c1", "strategy_id": "s1", "result": "SUCCESS"},
    ]
    count = engine.ingest_outcomes(outcomes)
    assert count == 3
    conf, _ = engine.get_confidence("c1", "s1")
    assert 0.4 < conf < 0.7


def test_calibration_engine_evaluate_against_ground_truth():
    gen = SyntheticDataGenerator("fraud_investigation", seed=42)
    data = list(gen.generate_dataset(200))
    ground_truth = gen.get_ground_truth()

    engine = CalibrationEngine()
    outcomes = [
        {
            "context_id": r["context"]["context_id"],
            "strategy_id": r["strategy"]["strategy_id"],
            "result": r["outcome"]["result"],
        }
        for r in data
    ]
    engine.ingest_outcomes(outcomes)

    metrics = engine.evaluate_calibration(ground_truth)
    assert "error" not in metrics or metrics.get("num_evaluated", 0) > 0
    if metrics.get("num_evaluated", 0) > 0:
        assert "brier_score" in metrics
        assert "mean_absolute_error" in metrics
        assert 0 <= metrics["brier_score"] <= 1
        assert 0 <= metrics["mean_absolute_error"] <= 1


def test_calibration_get_top_strategies():
    engine = CalibrationEngine()
    engine.update("ctx_1", "strat_high", "SUCCESS")
    engine.update("ctx_1", "strat_high", "SUCCESS")
    engine.update("ctx_1", "strat_low", "FAILURE")
    engine.update("ctx_1", "strat_low", "FAILURE")

    top = engine.get_top_strategies("ctx_1", min_confidence=0.0, limit=5)
    assert len(top) == 2
    assert top[0][1] >= top[1][1]
    assert top[0][0] == "strat_high"
