"""
End-to-end test: full CortexDBx learning loop (generate, ingest, calibrate, recommend).

Validates MVP success criteria locally before Databricks deployment.
"""

from cortexdbx.agents.orchestrator import AgentOrchestrator
from cortexdbx.sdk.client import CortexDBxClient
from cortexdbx.synthetic.generator import SyntheticDataGenerator


def test_e2e_learning_loop_orchestrator():
    """
    Full learning loop via AgentOrchestrator: generate -> ingest -> calibrate -> recommend.

    Success criteria: Brier < 0.25, num_evaluated >= 1, at least one recommendation
    for a seen context with confidence in [0, 1].
    """
    domain = "fraud_investigation"
    num_outcomes = 800
    seed = 42

    # 1. Generate dataset
    generator = SyntheticDataGenerator(domain, seed=seed)
    data = list(generator.generate_dataset(num_outcomes))
    assert len(data) >= num_outcomes

    # 2. Build outcomes list (context_id, strategy_id, result, domain)
    outcomes = []
    for r in data:
        o = {
            "context_id": r["context"]["context_id"],
            "strategy_id": r["strategy"]["strategy_id"],
            "result": r["outcome"]["result"],
            "domain": r["context"]["domain"],
        }
        outcomes.append(o)

    # 3. Ingest via orchestrator
    orchestrator = AgentOrchestrator(max_workers=2)
    result = orchestrator.process_outcomes(outcomes)
    assert result["total_processed"] == len(outcomes)
    assert result["total_ingested"] == len(outcomes)

    # 4. Ground truth and calibration evaluation
    ground_truth = generator.get_ground_truth()
    metrics = orchestrator.evaluate_calibration(ground_truth)
    assert "error" not in metrics or metrics.get("num_evaluated", 0) > 0
    assert metrics.get("num_evaluated", 0) >= 1, "At least one strategy should have enough evidence"
    if metrics.get("brier_score") is not None:
        assert metrics["brier_score"] < 0.25, (
            f"Brier score {metrics['brier_score']} should be < 0.25"
        )

    # 5. Recommendations for a known context from the dataset
    sample_context_id = data[0]["context"]["context_id"]
    recs = orchestrator.get_recommendations(sample_context_id, min_confidence=0.5, limit=10)
    assert len(recs) >= 1, "Should have at least one recommendation for a seen context"
    for strategy_id, confidence in recs:
        assert 0 <= confidence <= 1, f"Confidence {confidence} should be in [0, 1]"

    orchestrator.shutdown()


def test_e2e_learning_loop_sdk_local():
    """
    Full learning loop via CortexDBxClient (local backend): log outcomes -> recommend.

    Validates SDK path: log_outcome in a loop, then recommend and assert non-empty
    and sane confidence.
    """
    client = CortexDBxClient()
    domain = "clinical_trial"
    num_outcomes = 300
    seed = 123

    generator = SyntheticDataGenerator(domain, seed=seed)
    data = list(generator.generate_dataset(num_outcomes))
    assert len(data) >= num_outcomes

    # Log outcomes via SDK (context dict, strategy name, result)
    for r in data:
        ctx = {f["key"]: f["value"] for f in r["context"]["factors"]}
        ctx["domain"] = r["context"]["domain"]
        client.log_outcome(
            context=ctx,
            strategy=r["strategy"]["name"],
            result=r["outcome"]["result"],
            evidence={"source": "e2e_test"},
        )

    # Use same context factors as one of the records to get recommendations
    sample = data[0]
    ctx = {f["key"]: f["value"] for f in sample["context"]["factors"]}
    ctx["domain"] = sample["context"]["domain"]

    recs = client.recommend(ctx, min_confidence=0.3, limit=5)
    assert len(recs) >= 1, "SDK should return at least one recommendation after logging"
    for rec in recs:
        assert "confidence" in rec
        assert 0 <= rec["confidence"] <= 1
        assert "strategy_name" in rec or "strategy_id" in rec
