"""
Routing analytics — cost/quality reports for briefing commands.

Reads from model_outcomes.jsonl to generate:
  - Cost by provider, model, task type
  - Savings vs Anthropic-only baseline
  - Quality by model with trend direction
  - Routing accuracy (cheaper model vs opus quality match)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)

_DEFAULT_OUTCOMES_PATH = Path.home() / ".cortex" / "orchestration" / "model_outcomes.jsonl"

# Anthropic costs for baseline comparison
_ANTHROPIC_COSTS = {
    "opus": {"input": 15.0, "output": 75.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 0.25, "output": 1.25},
}


class RoutingAnalytics:
    """Cost/quality reports for multi-provider routing."""

    def __init__(self, outcomes_path: Path | None = None) -> None:
        self._outcomes_path = outcomes_path or _DEFAULT_OUTCOMES_PATH

    def cost_report(self, days: int = 7) -> Dict[str, Any]:
        """Cost breakdown by provider, model, and task type.

        Returns:
            {
                "period_days": 7,
                "total_cost_usd": 1.23,
                "total_dispatches": 45,
                "by_provider": {"anthropic": {"cost": 0.90, "count": 20}, ...},
                "by_tier": {"opus": {"cost": 0.50, "count": 5}, ...},
                "by_task_type": {"research": {"cost": 0.30, "count": 10}, ...},
                "anthropic_only_baseline_usd": 5.67,
                "savings_usd": 4.44,
                "savings_pct": 78.3,
            }
        """
        records = self._load_recent(days)
        if not records:
            return {"period_days": days, "total_cost_usd": 0, "total_dispatches": 0}

        by_provider: Dict[str, Dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        by_tier: Dict[str, Dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        by_task_type: Dict[str, Dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        total_cost = 0.0
        baseline_cost = 0.0

        for r in records:
            cost = r.get("cost_usd", 0.0) or 0.0
            provider = r.get("provider", "anthropic")
            tier = r.get("model_tier", "unknown")
            task_type = r.get("task_type", "unknown")
            tokens = r.get("tokens_used", 0) or 0

            total_cost += cost
            by_provider[provider]["cost"] += cost
            by_provider[provider]["count"] += 1
            by_tier[tier]["cost"] += cost
            by_tier[tier]["count"] += 1
            by_task_type[task_type]["cost"] += cost
            by_task_type[task_type]["count"] += 1

            # Anthropic baseline: what would this have cost on Anthropic?
            tier_costs = _ANTHROPIC_COSTS.get(tier, _ANTHROPIC_COSTS["sonnet"])
            avg_cost_per_token = (tier_costs["input"] + tier_costs["output"]) / 2 / 1_000_000
            baseline_cost += tokens * avg_cost_per_token

        savings = baseline_cost - total_cost
        savings_pct = (savings / baseline_cost * 100) if baseline_cost > 0 else 0

        return {
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_dispatches": len(records),
            "by_provider": dict(by_provider),
            "by_tier": dict(by_tier),
            "by_task_type": dict(by_task_type),
            "anthropic_only_baseline_usd": round(baseline_cost, 4),
            "savings_usd": round(savings, 4),
            "savings_pct": round(savings_pct, 1),
        }

    def quality_report(self, days: int = 7) -> Dict[str, Any]:
        """Quality breakdown by model with trend direction.

        Returns:
            {
                "by_model": {
                    "claude-sonnet-4-6": {"avg_quality": 0.75, "count": 20, "trend": "stable"},
                    "deepseek-chat": {"avg_quality": 0.68, "count": 15, "trend": "improving"},
                },
            }
        """
        records = self._load_recent(days)
        if not records:
            return {"by_model": {}}

        # Group quality scores by model
        model_scores: Dict[str, List[float]] = defaultdict(list)
        for r in records:
            model = r.get("model_id", "unknown")
            quality = r.get("quality_score")
            if quality is not None:
                model_scores[model].append(quality)

        by_model = {}
        for model, scores in model_scores.items():
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            # Trend: compare first half to second half
            mid = len(scores) // 2
            if mid > 0:
                first_half_avg = sum(scores[:mid]) / mid
                second_half_avg = sum(scores[mid:]) / (len(scores) - mid)
                diff = second_half_avg - first_half_avg
                if diff > 0.05:
                    trend = "improving"
                elif diff < -0.05:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            by_model[model] = {
                "avg_quality": round(avg, 3),
                "count": len(scores),
                "trend": trend,
            }

        return {"by_model": by_model}

    def routing_accuracy(self, days: int = 7) -> Dict[str, Any]:
        """How often did a cheaper model match opus-tier quality?

        Returns:
            {
                "cheaper_model_adequate_pct": 85.0,
                "escalation_rate_pct": 5.0,
                "avg_quality_by_tier": {"haiku": 0.5, "sonnet": 0.7, "opus": 0.9},
            }
        """
        records = self._load_recent(days)
        if not records:
            return {}

        tier_qualities: Dict[str, List[float]] = defaultdict(list)
        total_non_opus = 0
        adequate_non_opus = 0  # quality >= 0.6

        for r in records:
            tier = r.get("model_tier", "unknown")
            quality = r.get("quality_score")
            if quality is not None:
                tier_qualities[tier].append(quality)
                if tier != "opus":
                    total_non_opus += 1
                    if quality >= 0.6:
                        adequate_non_opus += 1

        avg_by_tier = {
            tier: round(sum(scores) / len(scores), 3)
            for tier, scores in tier_qualities.items()
            if scores
        }

        return {
            "cheaper_model_adequate_pct": (
                round(adequate_non_opus / total_non_opus * 100, 1) if total_non_opus > 0 else 0
            ),
            "total_dispatches": len(records),
            "avg_quality_by_tier": avg_by_tier,
        }

    def baseline_comparison(self, days: int = 7) -> Dict[str, Any]:
        """Compare A/B baseline (Anthropic-only) vs optimized multi-provider.

        Segments outcome records by is_baseline flag and compares average
        quality and success rate. This is the key signal for whether
        cheaper providers are degrading output quality.

        Returns:
            {
                "baseline": {"count": 5, "avg_quality": 0.82, "success_rate": 0.95},
                "optimized": {"count": 45, "avg_quality": 0.78, "success_rate": 0.92},
                "quality_delta": -0.04,  # negative = baseline wins
                "verdict": "acceptable",  # "acceptable" | "degraded" | "insufficient_data"
            }
        """
        records = self._load_recent(days)
        if not records:
            return {"verdict": "insufficient_data"}

        baseline_q: List[float] = []
        baseline_s: List[bool] = []
        optimized_q: List[float] = []
        optimized_s: List[bool] = []

        for r in records:
            is_bl = r.get("is_baseline", False)
            quality = r.get("quality_score")
            success = r.get("success", False)

            if is_bl:
                baseline_s.append(success)
                if quality is not None:
                    baseline_q.append(quality)
            else:
                optimized_s.append(success)
                if quality is not None:
                    optimized_q.append(quality)

        if len(baseline_q) < 3 or len(optimized_q) < 3:
            return {
                "verdict": "insufficient_data",
                "baseline_count": len(baseline_q),
                "optimized_count": len(optimized_q),
            }

        bl_avg = sum(baseline_q) / len(baseline_q)
        opt_avg = sum(optimized_q) / len(optimized_q)
        delta = opt_avg - bl_avg

        # Verdict: degraded if optimized is >10% worse than baseline
        if delta < -0.10:
            verdict = "degraded"
        else:
            verdict = "acceptable"

        return {
            "baseline": {
                "count": len(baseline_s),
                "avg_quality": round(bl_avg, 3),
                "success_rate": round(sum(baseline_s) / len(baseline_s), 3) if baseline_s else 0,
            },
            "optimized": {
                "count": len(optimized_s),
                "avg_quality": round(opt_avg, 3),
                "success_rate": round(sum(optimized_s) / len(optimized_s), 3) if optimized_s else 0,
            },
            "quality_delta": round(delta, 3),
            "verdict": verdict,
        }

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_recent(self, days: int) -> List[Dict[str, Any]]:
        """Load outcome records from the last N days."""
        if not self._outcomes_path.exists():
            return []

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        records = []

        try:
            for line in self._outcomes_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ts = data.get("timestamp", "")
                    if ts:
                        try:
                            record_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if record_time.tzinfo is None:
                                record_time = record_time.replace(tzinfo=timezone.utc)
                            if record_time >= cutoff:
                                records.append(data)
                        except (ValueError, TypeError):
                            records.append(data)  # Include if timestamp unparseable
                    else:
                        records.append(data)
                except json.JSONDecodeError:
                    continue
        except OSError as exc:
            log.error("Failed to read outcomes: %s", exc)

        return records
