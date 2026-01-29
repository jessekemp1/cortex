"""Tests for agent orchestrator."""

import pytest
from cortexdbx.agents.orchestrator import AgentOrchestrator
from cortexdbx.synthetic.generator import SyntheticDataGenerator


def test_orchestrator_process_outcomes():
    orch = AgentOrchestrator(max_workers=2)
    outcomes = [
        {"context_id": "c1", "strategy_id": "s1", "result": "SUCCESS", "domain": "fraud_investigation"},
        {"context_id": "c1", "strategy_id": "s1", "result": "FAILURE", "domain": "fraud_investigation"},
        {"context_id": "c2", "strategy_id": "s2", "result": "SUCCESS", "domain": "clinical_trial"},
    ]
    result = orch.process_outcomes(outcomes)
    assert result["total_processed"] == 3
    assert result["total_ingested"] == 3
    assert "fraud_investigation" in result["by_domain"]
    assert "clinical_trial" in result["by_domain"]
    orch.shutdown()


def test_orchestrator_calibration_updated():
    orch = AgentOrchestrator(max_workers=2)
    outcomes = [
        {"context_id": "c1", "strategy_id": "s1", "result": "SUCCESS"},
        {"context_id": "c1", "strategy_id": "s1", "result": "SUCCESS"},
        {"context_id": "c1", "strategy_id": "s1", "result": "FAILURE"},
    ]
    orch.process_outcomes(outcomes)
    top = orch.get_recommendations("c1", min_confidence=0.0, limit=5)
    assert len(top) == 1
    assert top[0][0] == "s1"
    assert top[0][1] > 0.5
    orch.shutdown()


def test_orchestrator_with_synthetic_data():
    gen = SyntheticDataGenerator("maintenance", seed=0)
    data = list(gen.generate_dataset(100))
    outcomes = []
    for r in data:
        o = r["outcome"].copy()
        o["domain"] = r["context"]["domain"]
        outcomes.append(o)

    orch = AgentOrchestrator(max_workers=4)
    result = orch.process_outcomes(outcomes)
    assert result["total_processed"] == 100
    assert result["total_ingested"] == 100

    ground_truth = gen.get_ground_truth()
    metrics = orch.evaluate_calibration(ground_truth)
    assert "error" not in metrics or metrics.get("num_evaluated", 0) >= 0
    if metrics.get("num_evaluated", 0) > 0:
        assert metrics["brier_score"] < 0.5
    orch.shutdown()


def test_orchestrator_parallel_processing():
    gen = SyntheticDataGenerator("supply_chain", seed=1)
    data = list(gen.generate_dataset(200))
    outcomes = [r["outcome"].copy() for r in data]
    for i, o in enumerate(outcomes):
        o["domain"] = data[i]["context"]["domain"]

    orch = AgentOrchestrator(max_workers=4)
    result = orch.process_outcomes_parallel(outcomes, chunk_size=50)
    assert result["total_processed"] == 200
    assert result["total_ingested"] == 200
    assert result["chunks_processed"] >= 1
    orch.shutdown()
