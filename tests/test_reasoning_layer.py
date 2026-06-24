"""Tests for cortex.intelligence.reasoning — V2 Reasoning Layer."""

import json
from pathlib import Path
from unittest.mock import MagicMock


from cortex.intelligence.reasoning import ReasoningLayer, classify_query


class TestClassifyQuery:
    def test_tier1_direct_lookup(self):
        assert classify_query("what is the gotcha for HRRR") == 1
        assert classify_query("show me the latest outcomes") == 1
        assert classify_query("get all patterns for vortex") == 1
        assert classify_query("list recent decisions") == 1
        assert classify_query("find the config for cortex") == 1

    def test_tier2_pattern_question(self):
        assert classify_query("what patterns repeat") == 2
        assert classify_query("how does the ensemble work") == 2
        assert classify_query("tell me about the batch pipeline") == 2

    def test_tier3_abstract_strategic(self):
        assert classify_query("what is Cortex missing") == 3
        assert classify_query("should we refactor the bridge") == 3
        assert classify_query("assess the risk of this change") == 3
        assert classify_query("what if we remove the signal bus") == 3
        assert classify_query("compare haiku vs sonnet for routing") == 3
        assert classify_query("why does the ensemble fail here") == 3
        assert classify_query("evaluate the strategy for V2") == 3


class TestReasoningLayerTier1:
    def test_reason_tier1_no_llm(self):
        """Tier 1 returns formatted dict without any API call."""
        mock_client = MagicMock()
        layer = ReasoningLayer(anthropic_client=mock_client)
        context = {"related_patterns": [{"title": "HRRR Lambert", "score": 0.9}]}

        result = layer.reason("what is the gotcha for HRRR", context, tier=1)

        assert result["tier"] == 1
        assert result["cost"] == 0.0
        assert result["analysis"] == "Direct retrieval results"
        assert result["evidence"] == [{"title": "HRRR Lambert", "score": 0.9}]
        assert result["recommended_actions"] == []
        assert result["confidence"] == 0.6
        mock_client.messages.create.assert_not_called()


class TestReasoningLayerTier2:
    def test_reason_tier2_with_mock(self):
        """Tier 2 calls Haiku and returns structured response."""
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [
            MagicMock(
                text=json.dumps(
                    {
                        "analysis": "Pattern detected in HRRR failures",
                        "evidence": ["Lambert projection mismatch"],
                        "recommended_actions": ["Use _find_nearest_lambert"],
                        "confidence": 0.85,
                    }
                )
            )
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        layer = ReasoningLayer(anthropic_client=mock_client)
        # Use tmp path for cost tracking to avoid polluting real metrics
        layer.COSTS_PATH = Path("/tmp/test_reasoning_costs.jsonl")
        layer.COSTS_PATH.unlink(missing_ok=True)

        result = layer.reason("what patterns repeat in HRRR", {}, tier=2)

        assert result["tier"] == 2
        assert result["analysis"] == "Pattern detected in HRRR failures"
        assert result["confidence"] == 0.85
        assert "Lambert projection mismatch" in result["evidence"]
        assert result["cost"] > 0
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-haiku-4-5"

        # Cleanup
        layer.COSTS_PATH.unlink(missing_ok=True)


class TestBudgetExceeded:
    def test_budget_exceeded_falls_back(self, tmp_path):
        """After writing budget-exceeding costs, all queries return Tier 1."""
        costs_path = tmp_path / "reasoning_costs.jsonl"
        # Write $1.00 of cost for today — exceeds $0.50 default
        from datetime import date

        record = {"date": date.today().isoformat(), "cost": 1.00}
        costs_path.write_text(json.dumps(record) + "\n")

        mock_client = MagicMock()
        layer = ReasoningLayer(anthropic_client=mock_client)
        layer.COSTS_PATH = costs_path

        result = layer.reason("assess the risk of V2 rollout", {}, tier=3)

        assert result["tier"] == 3  # Preserves requested tier
        assert result["fallback_reason"] == "budget_exceeded"
        assert result["cost"] == 0.0
        mock_client.messages.create.assert_not_called()

    def test_budget_not_exceeded_allows_llm(self, tmp_path):
        """Under budget, Tier 3 proceeds to LLM."""
        costs_path = tmp_path / "reasoning_costs.jsonl"
        from datetime import date

        record = {"date": date.today().isoformat(), "cost": 0.01}
        costs_path.write_text(json.dumps(record) + "\n")

        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [
            MagicMock(
                text='{"analysis":"ok","evidence":[],"recommended_actions":[],"confidence":0.7}'
            )
        ]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        layer = ReasoningLayer(anthropic_client=mock_client)
        layer.COSTS_PATH = costs_path

        result = layer.reason("assess the risk", {}, tier=3)

        assert result["tier"] == 3
        mock_client.messages.create.assert_called_once()


class TestReasoningFailure:
    def test_reason_failure_returns_direct(self):
        """Exception in LLM call returns Tier 1 result, never raises."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API down")

        layer = ReasoningLayer(anthropic_client=mock_client)

        result = layer.reason("assess risk", {}, tier=3)

        assert result["tier"] == 3  # Preserves requested tier
        assert result["fallback_reason"] == "llm_fallback"
        assert result["cost"] == 0.0
        assert result["analysis"] == "Direct retrieval results"
