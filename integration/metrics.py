"""Metrics tracking for recommendation quality"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class RecommendationMetrics:
    """Track metrics for recommendation quality"""

    def __init__(self, metrics_file: Path = None):
        """
        Initialize metrics tracker.

        Args:
            metrics_file: Path to metrics storage file
        """
        if metrics_file is None:
            metrics_file = Path.home() / ".cortex" / "recommendation_metrics.json"

        self.metrics_file = metrics_file
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_metrics()

    def _load_metrics(self):
        """Load metrics from file"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r") as f:
                    self.metrics = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.metrics = {"recommendations": [], "statistics": {}}
        else:
            self.metrics = {"recommendations": [], "statistics": {}}

    def _save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def record_recommendation(self, action_title: str, priority: str, scheduled: bool = False):
        """Record a recommendation"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_title": action_title,
            "priority": priority,
            "scheduled": scheduled,
        }
        self.metrics["recommendations"].append(entry)
        self._save_metrics()

    def get_statistics(self) -> Dict[str, Any]:
        """Get recommendation statistics"""
        recommendations = self.metrics.get("recommendations", [])

        if not recommendations:
            return {"total": 0, "scheduled": 0, "scheduled_rate": 0.0}

        scheduled = sum(1 for r in recommendations if r.get("scheduled", False))

        return {
            "total": len(recommendations),
            "scheduled": scheduled,
            "scheduled_rate": (scheduled / len(recommendations) if recommendations else 0.0),
        }
