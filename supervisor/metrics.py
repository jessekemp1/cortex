"""
Orchestration metrics — real-time dispatch tracking.

In-memory counters for the current session. Persisted to disk
periodically for dashboard consumption.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)


class OrchestrationMetrics:
    """Real-time metrics for monitoring dispatch activity."""

    def __init__(self) -> None:
        self._dispatches_today: int = 0
        self._cost_today: float = 0.0
        self._tokens_today: int = 0
        self._by_provider: Dict[str, int] = defaultdict(int)
        self._by_model: Dict[str, int] = defaultdict(int)
        self._by_tier: Dict[str, int] = defaultdict(int)
        self._quality_scores: list[float] = []
        self._last_reset: datetime = datetime.now(tz=timezone.utc)

    def record_dispatch(
        self,
        provider: str,
        model: str,
        tier: str,
        cost: float,
        tokens: int,
        latency: float,
        quality: float,
    ) -> None:
        """Record a completed dispatch."""
        self._dispatches_today += 1
        self._cost_today += cost
        self._tokens_today += tokens
        self._by_provider[provider] += 1
        self._by_model[model] += 1
        self._by_tier[tier] += 1
        if quality > 0:
            self._quality_scores.append(quality)

    def get_dashboard(self) -> Dict[str, Any]:
        """Get current metrics for display."""
        avg_quality = (
            sum(self._quality_scores) / len(self._quality_scores) if self._quality_scores else 0.0
        )

        return {
            "dispatches_today": self._dispatches_today,
            "cost_today_usd": round(self._cost_today, 4),
            "tokens_today": self._tokens_today,
            "avg_quality": round(avg_quality, 3),
            "by_provider": dict(self._by_provider),
            "by_model": dict(self._by_model),
            "by_tier": dict(self._by_tier),
            "since": self._last_reset.isoformat(),
        }

    def reset(self) -> None:
        """Reset daily counters."""
        self._dispatches_today = 0
        self._cost_today = 0.0
        self._tokens_today = 0
        self._by_provider.clear()
        self._by_model.clear()
        self._by_tier.clear()
        self._quality_scores.clear()
        self._last_reset = datetime.now(tz=timezone.utc)

    def persist(self, path: Path | None = None) -> None:
        """Write current metrics to disk."""
        path = path or Path.home() / ".cortex" / "orchestration" / "metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.get_dashboard(), indent=2) + "\n")
