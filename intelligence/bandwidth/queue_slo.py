"""Queue SLO monitoring for interaction ingest/drain health."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def check_queue_slo(
    queue_file: Path = Path.home() / ".cortex" / "interaction_queue.jsonl",
    processing_file: Path = Path.home() / ".cortex" / "interaction_queue.processing.jsonl",
    backlog_warn: int = 5000,
    backlog_crit: int = 20000,
) -> Dict[str, Any]:
    backlog = _count_lines(queue_file)
    processing = _count_lines(processing_file)
    total = backlog + processing

    if total >= backlog_crit:
        status = "critical"
    elif total >= backlog_warn:
        status = "warning"
    else:
        status = "healthy"

    alerts = []
    if status == "warning":
        alerts.append("Queue backlog above warning threshold")
    elif status == "critical":
        alerts.append("Queue backlog above critical threshold")

    return {
        "timestamp": datetime.now().isoformat(),
        "queue_lines": backlog,
        "processing_lines": processing,
        "total_lines": total,
        "status": status,
        "alerts": alerts,
        "thresholds": {
            "warning": backlog_warn,
            "critical": backlog_crit,
        },
    }
