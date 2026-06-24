"""
Learning Telemetry - Pipeline stage tracking and ASCII visualization.

Records pipeline stage events and renders pipeline run visualizations
for `cortex learn --pipeline`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_STAGE_LOG = Path.home() / ".cortex" / "pipeline" / "stage_log.jsonl"


@dataclass
class StageEvent:
    """A single pipeline stage event."""

    run_id: str
    name: str
    status: str  # pending, running, complete, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    items_in: int = 0
    items_out: int = 0
    duration_s: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineRun:
    """A grouped set of stages forming one pipeline run."""

    run_id: str
    stages: List[StageEvent] = field(default_factory=list)
    started_at: Optional[str] = None
    total_items: int = 0

    @property
    def age_label(self) -> str:
        """Human-readable age like '2m ago' or '1h ago'."""
        if not self.started_at:
            return "unknown"
        try:
            started = datetime.fromisoformat(self.started_at)
            delta = datetime.now() - started
            seconds = int(delta.total_seconds())
            if seconds < 60:
                return f"{seconds}s ago"
            elif seconds < 3600:
                return f"{seconds // 60}m ago"
            elif seconds < 86400:
                return f"{seconds // 3600}h ago"
            else:
                return f"{seconds // 86400}d ago"
        except Exception:
            return "unknown"


class LearningTelemetry:
    """Records and visualizes learning pipeline telemetry."""

    STAGE_ORDER = ["capture", "extract", "store", "index"]

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or DEFAULT_STAGE_LOG

    def record_stage(self, event: StageEvent) -> None:
        """Append a stage event to the JSONL log."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Telemetry write failed (non-fatal): {e}")

    def get_recent_runs(self, limit: int = 5) -> List[PipelineRun]:
        """Read the log and group stages into pipeline runs."""
        if not self.log_path.exists():
            return []

        events_by_run: Dict[str, List[StageEvent]] = {}
        try:
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        run_id = data.get("run_id", "unknown")
                        event = StageEvent(
                            run_id=run_id,
                            name=data.get("name", "unknown"),
                            status=data.get("status", "unknown"),
                            started_at=data.get("started_at"),
                            completed_at=data.get("completed_at"),
                            items_in=data.get("items_in", 0),
                            items_out=data.get("items_out", 0),
                            duration_s=data.get("duration_s", 0.0),
                            metadata=data.get("metadata", {}),
                        )
                        events_by_run.setdefault(run_id, []).append(event)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception as e:
            logger.warning(f"Failed to read stage log: {e}")
            return []

        runs = []
        for run_id, events in events_by_run.items():
            # Use only the latest event per stage name (complete/failed overrides running)
            latest_by_name: Dict[str, StageEvent] = {}
            for ev in events:
                existing = latest_by_name.get(ev.name)
                if existing is None or ev.status in ("complete", "failed"):
                    latest_by_name[ev.name] = ev

            stages = sorted(
                latest_by_name.values(),
                key=lambda s: self.STAGE_ORDER.index(s.name) if s.name in self.STAGE_ORDER else 99,
            )

            started_at = None
            for s in stages:
                if s.started_at:
                    started_at = s.started_at
                    break

            total_items = stages[0].items_in if stages else 0

            runs.append(
                PipelineRun(
                    run_id=run_id,
                    stages=stages,
                    started_at=started_at,
                    total_items=total_items,
                )
            )

        # Sort by started_at descending, take limit
        runs.sort(key=lambda r: r.started_at or "", reverse=True)
        return runs[:limit]

    def format_pipeline_ascii(self, runs: List[PipelineRun]) -> str:
        """Render ASCII visualization of pipeline runs."""
        if not runs:
            return "No pipeline runs recorded. The learning pipeline has not executed yet."

        lines = []
        count = len(runs)
        lines.append(f"LEARNING PIPELINE — Last {count} run{'s' if count != 1 else ''}")
        lines.append("━" * 50)

        for run in runs:
            items_label = f"{run.total_items} interactions processed"
            lines.append("")
            lines.append(f"Run #{run.run_id} ({run.age_label}) — {items_label}")

            if not run.stages:
                lines.append("  (no stages recorded)")
                continue

            # Stage name row with arrows
            stage_names = []
            for s in run.stages:
                tag = s.name.upper()
                if s.status == "failed":
                    tag = f"{tag}!"
                stage_names.append(f"[{tag}]")
            lines.append("  " + "──▶".join(stage_names))

            # Items row
            item_parts = []
            for s in run.stages:
                in_label = f"{s.items_in} in" if s.items_in else ""
                out_label = f"{s.items_out} out" if s.items_out else ""
                part = ", ".join(filter(None, [in_label, out_label]))
                item_parts.append(part if part else "-")
            lines.append(
                "  "
                + "   ".join(f"{p:^{len(stage_names[i]) + 2}}" for i, p in enumerate(item_parts))
            )

            # Duration row
            dur_parts = []
            for s in run.stages:
                if s.duration_s > 0:
                    dur_parts.append(f"{s.duration_s:.1f}s")
                else:
                    dur_parts.append("-")
            lines.append(
                "  "
                + "   ".join(f"{p:^{len(stage_names[i]) + 2}}" for i, p in enumerate(dur_parts))
            )

        lines.append("")
        return "\n".join(lines)
