#!/usr/bin/env python3
"""
Switch Tracker — measures real context-switching costs across projects.

Replaces hardcoded token estimates with measured data from actual switches.
Stores switch cost records in ~/.cortex/metrics/switch_costs.json.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAX_RECORDS = 500
SWITCH_COSTS_FILE = Path.home() / ".cortex" / "metrics" / "switch_costs.json"


@dataclass
class SwitchStats:
    total_switches: int
    avg_with_cortex: int
    avg_without_cortex: int
    savings_per_switch: int
    enough_data: bool


class SwitchTracker:
    """Tracks and measures project-switching token costs."""

    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or SWITCH_COSTS_FILE

    def _load_records(self) -> list[dict]:
        if not self.storage_path.exists():
            return []
        try:
            data = json.loads(self.storage_path.read_text())
            return data.get("records", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_records(self, records: list[dict]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps({"records": records}, indent=2))

    def record_switch(
        self,
        from_project: str,
        to_project: str,
        preamble_tokens: int,
        context_tokens: int,
    ) -> None:
        """Append a switch cost record.

        Args:
            from_project: Project switched away from.
            to_project: Project switched to.
            preamble_tokens: Actual tokens injected with Cortex context.
            context_tokens: Estimated baseline tokens without Cortex filtering.
        """
        records = self._load_records()
        records.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_project": from_project,
                "to_project": to_project,
                "preamble_tokens": preamble_tokens,
                "context_tokens": context_tokens,
            }
        )
        # Keep only the most recent records
        if len(records) > MAX_RECORDS:
            records = records[-MAX_RECORDS:]
        self._save_records(records)

    def get_stats(self) -> SwitchStats:
        """Compute aggregate stats from recorded switches."""
        records = self._load_records()
        total = len(records)

        if total == 0:
            return SwitchStats(
                total_switches=0,
                avg_with_cortex=0,
                avg_without_cortex=0,
                savings_per_switch=0,
                enough_data=False,
            )

        avg_with = sum(r["preamble_tokens"] for r in records) // total
        avg_without = sum(r["context_tokens"] for r in records) // total

        return SwitchStats(
            total_switches=total,
            avg_with_cortex=avg_with,
            avg_without_cortex=avg_without,
            savings_per_switch=avg_without - avg_with,
            enough_data=total >= 10,
        )
