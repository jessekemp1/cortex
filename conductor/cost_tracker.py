#!/usr/bin/env python3
"""
Cost tracking and budget enforcement for the Cortex Conductor.

Tracks per-provider spending via an append-only JSONL log,
enforces configurable daily budgets, and calculates savings
versus Anthropic-only routing.

State directory: ~/.cortex/conductor/
Cost log: ~/.cortex/conductor/costs.jsonl
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Anthropic baseline pricing: (input_cost_per_mtok, output_cost_per_mtok)
# Used by get_savings_report() to calculate what each call WOULD have cost.
ANTHROPIC_BASELINE: Dict[str, tuple[float, float]] = {
    "classification": (1.0, 5.0),  # haiku
    "code_review": (3.0, 15.0),  # sonnet
    "long_context": (3.0, 15.0),  # sonnet
    "research": (3.0, 15.0),  # sonnet
    "quick_qa": (1.0, 5.0),  # haiku
    "pattern_learning": (0.50, 2.50),  # haiku batch
    "documentation": (1.0, 5.0),  # haiku
    "test_generation": (3.0, 15.0),  # sonnet
    "security_audit": (15.0, 75.0),  # opus
    "architecture": (15.0, 75.0),  # opus
    "interactive_coding": (3.0, 15.0),  # sonnet
}

# Default baseline for unknown use cases — sonnet pricing as a reasonable mid-tier
DEFAULT_BASELINE: tuple[float, float] = (3.0, 15.0)


class CostTracker:
    """Track per-provider spending and enforce budgets.

    All cost records are persisted to an append-only JSONL file.
    Thread-safe: concurrent record() calls are serialized via lock.
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        daily_budget: float = 20.0,
    ):
        self.state_dir = state_dir or Path.home() / ".cortex" / "conductor"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.costs_file = self.state_dir / "costs.jsonl"
        self.daily_budget = daily_budget
        self._lock = threading.Lock()

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        use_case: str = "",
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Record a completed API call.

        Appends a JSON line to the costs file with a UTC timestamp.
        Returns the recorded entry for confirmation/logging.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "use_case": use_case,
            "latency_ms": latency_ms,
        }

        with self._lock:
            with open(self.costs_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        # Feed usage to subscription optimizer if available
        try:
            from batch.subscription_optimizer import SubscriptionOptimizer

            sub_opt = SubscriptionOptimizer()
            sub_opt.record_usage(
                provider=provider,
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                is_batch="batch" in use_case.lower() if use_case else False,
                model_tier=model.split("-")[0] if model else "sonnet",
            )
        except (ImportError, Exception):
            pass  # Subscription tracking is optional

        return entry

    def _load_entries(self, date_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load entries from the JSONL file, optionally filtered by date.

        Args:
            date_filter: ISO date string (YYYY-MM-DD) to filter by. If None,
                         returns all entries.

        Returns:
            List of cost entry dicts matching the filter.
        """
        entries: List[Dict[str, Any]] = []

        if not self.costs_file.exists():
            return entries

        with self._lock:
            with open(self.costs_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if date_filter is not None:
                        ts = entry.get("timestamp", "")
                        if not ts.startswith(date_filter):
                            continue

                    entries.append(entry)

        return entries

    def get_daily_spend(self, date: Optional[str] = None) -> Dict[str, float]:
        """Get spending by provider for a date (default: today).

        Args:
            date: ISO date string (YYYY-MM-DD). Defaults to today UTC.

        Returns:
            Dict mapping provider name to total spend, plus a "total" key.
            Example: {"groq": 0.05, "xai": 1.20, "anthropic": 15.00, "total": 16.25}
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        entries = self._load_entries(date_filter=date)

        spend: Dict[str, float] = {}
        total = 0.0

        for entry in entries:
            provider = entry.get("provider", "unknown")
            cost = entry.get("cost_usd", 0.0)
            spend[provider] = spend.get(provider, 0.0) + cost
            total += cost

        spend["total"] = round(total, 6)
        # Round individual provider totals too
        for key in spend:
            spend[key] = round(spend[key], 6)

        return spend

    def get_budget_remaining(self) -> float:
        """Get remaining daily budget in USD for today."""
        spend = self.get_daily_spend()
        remaining = self.daily_budget - spend.get("total", 0.0)
        return round(max(0.0, remaining), 6)

    def check_budget(self, estimated_cost: float) -> bool:
        """Check if estimated cost fits within remaining daily budget.

        Args:
            estimated_cost: The projected cost in USD for the next call.

        Returns:
            True if the call can proceed within budget, False otherwise.
        """
        remaining = self.get_budget_remaining()
        return estimated_cost <= remaining

    def get_monthly_summary(self) -> Dict[str, Any]:
        """Get monthly spending breakdown by provider and use case.

        Returns a dict with:
        - by_provider: {provider: total_spend}
        - by_use_case: {use_case: total_spend}
        - by_day: {date: total_spend}
        - total_calls: int
        - total_spend: float
        - current_month: str (YYYY-MM)
        """
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        entries = self._load_entries()

        # Filter to current month
        month_entries = [e for e in entries if e.get("timestamp", "").startswith(current_month)]

        by_provider: Dict[str, float] = {}
        by_use_case: Dict[str, float] = {}
        by_day: Dict[str, float] = {}
        total_spend = 0.0

        for entry in month_entries:
            cost = entry.get("cost_usd", 0.0)
            total_spend += cost

            provider = entry.get("provider", "unknown")
            by_provider[provider] = by_provider.get(provider, 0.0) + cost

            use_case = entry.get("use_case", "untagged")
            if use_case:
                by_use_case[use_case] = by_use_case.get(use_case, 0.0) + cost

            ts = entry.get("timestamp", "")
            day = ts[:10] if len(ts) >= 10 else "unknown"
            by_day[day] = by_day.get(day, 0.0) + cost

        # Round everything
        for d in (by_provider, by_use_case, by_day):
            for key in d:
                d[key] = round(d[key], 6)

        return {
            "current_month": current_month,
            "total_calls": len(month_entries),
            "total_spend": round(total_spend, 6),
            "by_provider": by_provider,
            "by_use_case": by_use_case,
            "by_day": by_day,
        }

    def get_savings_report(self) -> Dict[str, Any]:
        """Calculate savings vs Anthropic-only routing.

        For each recorded call, calculates what it WOULD have cost
        on the equivalent Anthropic model (haiku, sonnet, or opus
        depending on use case). Compares to actual cost.

        Returns:
        - actual_spend: float (what we actually paid)
        - anthropic_equivalent: float (what Anthropic-only would have cost)
        - savings_usd: float (anthropic_equivalent - actual_spend)
        - savings_pct: float (savings as percentage, 0-100)
        - by_use_case: dict with per-use-case breakdown
        - total_calls: int
        """
        entries = self._load_entries()

        actual_total = 0.0
        anthropic_total = 0.0
        by_use_case: Dict[str, Dict[str, float]] = {}
        total_calls = len(entries)

        for entry in entries:
            cost = entry.get("cost_usd", 0.0)
            actual_total += cost

            use_case = entry.get("use_case", "")
            input_tokens = entry.get("input_tokens", 0)
            output_tokens = entry.get("output_tokens", 0)

            # Calculate Anthropic equivalent cost
            baseline = ANTHROPIC_BASELINE.get(use_case, DEFAULT_BASELINE)
            anthro_cost = (input_tokens * baseline[0] + output_tokens * baseline[1]) / 1_000_000

            anthropic_total += anthro_cost

            # Accumulate per-use-case stats
            uc_key = use_case if use_case else "untagged"
            if uc_key not in by_use_case:
                by_use_case[uc_key] = {
                    "actual": 0.0,
                    "anthropic_equivalent": 0.0,
                    "calls": 0,
                }
            by_use_case[uc_key]["actual"] += cost
            by_use_case[uc_key]["anthropic_equivalent"] += anthro_cost
            by_use_case[uc_key]["calls"] += 1

        # Round per-use-case values
        for uc_key in by_use_case:
            uc = by_use_case[uc_key]
            uc["actual"] = round(uc["actual"], 6)
            uc["anthropic_equivalent"] = round(uc["anthropic_equivalent"], 6)
            savings = uc["anthropic_equivalent"] - uc["actual"]
            uc["savings_usd"] = round(savings, 6)
            uc["savings_pct"] = (
                round(savings / uc["anthropic_equivalent"] * 100, 2)
                if uc["anthropic_equivalent"] > 0
                else 0.0
            )

        savings_usd = anthropic_total - actual_total
        savings_pct = round(savings_usd / anthropic_total * 100, 2) if anthropic_total > 0 else 0.0

        return {
            "actual_spend": round(actual_total, 6),
            "anthropic_equivalent": round(anthropic_total, 6),
            "savings_usd": round(savings_usd, 6),
            "savings_pct": savings_pct,
            "total_calls": total_calls,
            "by_use_case": by_use_case,
        }
