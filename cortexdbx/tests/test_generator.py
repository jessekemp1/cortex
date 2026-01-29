"""Tests for synthetic data generator."""

import pytest
from cortexdbx.synthetic.generator import (
    SyntheticDataGenerator,
    DOMAIN_CONFIGS,
    generate_all_domains,
)


def test_domain_configs_has_six_domains():
    assert len(DOMAIN_CONFIGS) == 6
    assert "fraud_investigation" in DOMAIN_CONFIGS
    assert "clinical_trial" in DOMAIN_CONFIGS
    assert "maintenance" in DOMAIN_CONFIGS
    assert "marketing_campaign" in DOMAIN_CONFIGS
    assert "security_incident" in DOMAIN_CONFIGS
    assert "supply_chain" in DOMAIN_CONFIGS


def test_generator_requires_valid_domain():
    with pytest.raises(ValueError, match="Unknown domain"):
        SyntheticDataGenerator("invalid_domain")


def test_generator_produces_context_with_required_fields():
    gen = SyntheticDataGenerator("fraud_investigation", seed=42)
    data = list(gen.generate_dataset(5))
    assert len(data) == 5
    for record in data:
        ctx = record["context"]
        assert "context_id" in ctx
        assert "context_hash" in ctx
        assert "domain" in ctx
        assert ctx["domain"] == "fraud_investigation"
        assert "factors" in ctx
        assert len(ctx["factors"]) == len(DOMAIN_CONFIGS["fraud_investigation"].context_factors)


def test_generator_produces_outcome_with_required_fields():
    gen = SyntheticDataGenerator("clinical_trial", seed=123)
    data = list(gen.generate_dataset(10))
    for record in data:
        outcome = record["outcome"]
        assert "outcome_id" in outcome
        assert "context_id" in outcome
        assert "strategy_id" in outcome
        assert outcome["result"] in ("SUCCESS", "FAILURE", "PARTIAL")
        assert "evidence" in outcome
        assert "created_at" in outcome


def test_generator_ground_truth_matches_strategies():
    gen = SyntheticDataGenerator("maintenance", seed=1)
    gt = gen.get_ground_truth()
    assert len(gt) == len(DOMAIN_CONFIGS["maintenance"].strategy_types)
    for sid, rate in gt.items():
        assert 0 <= rate <= 1
        assert sid.startswith("strategy_maintenance_")


def test_generator_reproducible_with_same_seed():
    gen1 = SyntheticDataGenerator("supply_chain", seed=99)
    data1 = list(gen1.generate_dataset(20))
    gen2 = SyntheticDataGenerator("supply_chain", seed=99)
    data2 = list(gen2.generate_dataset(20))
    assert len(data1) == len(data2) == 20
    results1 = [r["outcome"]["result"] for r in data1]
    results2 = [r["outcome"]["result"] for r in data2]
    assert results1 == results2
    strategies1 = [r["outcome"]["strategy_id"] for r in data1]
    strategies2 = [r["outcome"]["strategy_id"] for r in data2]
    assert strategies1 == strategies2


def test_generate_all_domains():
    all_data = generate_all_domains(outcomes_per_domain=50)
    assert len(all_data) == 6
    for domain, payload in all_data.items():
        assert "outcomes" in payload
        assert "ground_truth" in payload
        assert "strategies" in payload
        assert len(payload["outcomes"]) == 50
        assert len(payload["ground_truth"]) > 0
        assert len(payload["strategies"]) > 0


def test_generator_large_dataset():
    gen = SyntheticDataGenerator("security_incident", seed=0)
    data = list(gen.generate_dataset(500))
    assert len(data) == 500
    results = [r["outcome"]["result"] for r in data]
    assert "SUCCESS" in results
    assert "FAILURE" in results
    assert "PARTIAL" in results
