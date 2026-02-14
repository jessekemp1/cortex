"""
Phase 1 metric contracts for Human-AI bandwidth tracking.

Contract metrics:
- override_rate: corrections per prompt
- autonomy_level: actions completed without explicit confirmation
- novelty_score: heuristic 0-10 score for ideation signal density
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ContractSessionMetrics:
    """Per-session contract metrics snapshot."""

    timestamp: datetime
    session_id: str
    project: str
    source: str = "unknown"

    prompt_count: int = 0
    correction_count: int = 0
    confirmation_count: int = 0
    tool_count: int = 0
    brainstorm_signal_count: int = 0
    novelty_signal_count: int = 0

    override_rate: float = 0.0
    autonomy_level: float = 0.0
    novelty_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContractSessionMetrics":
        data = dict(data)
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ContractMetricsStore:
    """JSONL storage and aggregation for contract metrics."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".cortex" / "research" / "bandwidth"
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.storage_dir / "session_contracts.jsonl"

    def record(self, metrics: ContractSessionMetrics) -> None:
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(metrics.to_dict()) + "\n")

    def load_metrics(self, days: int = 7, project: Optional[str] = None) -> List[ContractSessionMetrics]:
        if not self.metrics_file.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        rows: List[ContractSessionMetrics] = []

        with open(self.metrics_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = ContractSessionMetrics.from_dict(json.loads(line))
                except Exception:
                    continue

                if item.timestamp < cutoff:
                    continue
                if project and item.project != project:
                    continue
                rows.append(item)

        return rows

    def aggregate(self, days: int = 7, project: Optional[str] = None) -> Dict[str, Any]:
        rows = self.load_metrics(days=days, project=project)
        if not rows:
            return {
                "sessions": 0,
                "override_rate": 0.0,
                "autonomy_level": 0.0,
                "novelty_score": 0.0,
                "project": project,
                "period_days": days,
            }

        n = len(rows)
        return {
            "sessions": n,
            "override_rate": round(sum(r.override_rate for r in rows) / n, 3),
            "autonomy_level": round(sum(r.autonomy_level for r in rows) / n, 3),
            "novelty_score": round(sum(r.novelty_score for r in rows) / n, 2),
            "project": project,
            "period_days": days,
        }
