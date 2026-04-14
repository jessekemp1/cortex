"""
Cortex V2 Reasoning Layer — tiered LLM synthesis over retrieved context.

Tier 1: Direct lookup (no LLM, $0)
Tier 2: Pattern question (Haiku, ~$0.001)
Tier 3: Abstract/strategic (Sonnet, ~$0.01)

Budget-capped at $0.50/day via CORTEX_REASONING_BUDGET env var.
All failures fall back to Tier 1 formatted results — never raises.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional


def classify_query(query: str) -> int:
    """Keyword heuristic. Tier 1=direct lookup, Tier 2=pattern, Tier 3=abstract/strategic."""
    q = query.lower()
    direct_patterns = ["what is the", "show me", "get ", "list ", "find "]
    if any(q.startswith(p) for p in direct_patterns):
        return 1
    abstract_signals = [
        "missing",
        "should",
        "strategy",
        "risk",
        "trajectory",
        "what if",
        "compare",
        "assess",
        "evaluate",
        "why",
    ]
    if any(s in q for s in abstract_signals):
        return 3
    return 2


# Per-1K-token costs (input, output) — used for budget tracking
_MODEL_COSTS = {
    "claude-haiku-4-5": (0.0008, 0.004),
    "claude-sonnet-4-5-20250514": (0.003, 0.015),
}


class ReasoningLayer:
    """Tiered LLM synthesis over retrieved context."""

    BUDGET_ENV = "CORTEX_REASONING_BUDGET"
    DEFAULT_BUDGET = 0.50  # $/day
    COSTS_PATH = Path.home() / ".cortex" / "metrics" / "reasoning_costs.jsonl"

    _SYSTEM_PROMPT = (
        "You are Cortex, an intelligence layer for a developer's projects. "
        "Given the user's query and retrieved context, produce a structured JSON response with: "
        '"analysis" (1-3 sentence synthesis), '
        '"evidence" (list of supporting facts from context), '
        '"recommended_actions" (list of concrete next steps), '
        '"confidence" (float 0-1). '
        "Return ONLY valid JSON, no markdown fences."
    )

    def __init__(self, anthropic_client: Optional[Any] = None):
        self.client = anthropic_client

    def _get_client(self) -> Any:
        """Lazy-init Anthropic client from env if not injected."""
        if self.client is not None:
            return self.client
        try:
            import anthropic

            self.client = anthropic.Anthropic()
            return self.client
        except Exception:
            return None

    def reason(self, query: str, retrieved_context: dict, tier: int) -> dict:
        """Route query to appropriate reasoning tier."""
        if tier == 1:
            return self._format_direct(retrieved_context)
        if self._budget_exceeded():
            return self._format_direct(retrieved_context)
        model = "claude-haiku-4-5" if tier == 2 else "claude-sonnet-4-5-20250514"
        try:
            return self._reason_with_llm(query, retrieved_context, model, tier)
        except Exception:
            return self._format_direct(retrieved_context)

    def _format_direct(self, context: dict) -> dict:
        """Tier 1: format retrieved results without LLM."""
        return {
            "analysis": "Direct retrieval results",
            "evidence": context.get("related_patterns", []),
            "recommended_actions": [],
            "confidence": 0.6,
            "tier": 1,
            "cost": 0.0,
        }

    def _reason_with_llm(self, query: str, context: dict, model: str, tier: int) -> dict:
        """Tier 2-3: structured LLM synthesis."""
        client = self._get_client()
        if client is None:
            return self._format_direct(context)

        user_msg = (
            f"Query: {query}\n\nRetrieved context:\n{json.dumps(context, default=str)[:3000]}"
        )

        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=self._SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        # Track cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self._track_cost(input_tokens, output_tokens, model)

        # Parse structured response
        raw = response.content[0].text
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"analysis": raw, "evidence": [], "recommended_actions": [], "confidence": 0.5}

        return {
            "analysis": parsed.get("analysis", raw[:500]),
            "evidence": parsed.get("evidence", []),
            "recommended_actions": parsed.get("recommended_actions", []),
            "confidence": parsed.get("confidence", 0.5),
            "tier": tier,
            "cost": cost,
        }

    def _budget_exceeded(self) -> bool:
        """Check if daily reasoning budget is exceeded."""
        budget = float(os.getenv(self.BUDGET_ENV, str(self.DEFAULT_BUDGET)))
        today = date.today().isoformat()
        total = 0.0
        if not self.COSTS_PATH.exists():
            return False
        try:
            for line in self.COSTS_PATH.read_text().strip().split("\n"):
                if not line:
                    continue
                record = json.loads(line)
                if record.get("date") == today:
                    total += record.get("cost", 0.0)
        except Exception:
            return False
        return total >= budget

    def _track_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Append cost record to COSTS_PATH. Returns cost in dollars."""
        in_rate, out_rate = _MODEL_COSTS.get(model, (0.003, 0.015))
        cost = (input_tokens / 1000 * in_rate) + (output_tokens / 1000 * out_rate)
        record = {
            "date": date.today().isoformat(),
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
        }
        try:
            self.COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.COSTS_PATH, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
        return cost
