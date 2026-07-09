"""Append-only namespaced event store for Cortex private workloads."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from namespaces import ensure_namespace, validate_namespace


VALID_VISIBILITIES = {"private", "internal", "public"}


class EventWriteError(RuntimeError):
    """Raised when an event cannot be written."""


class EventReadError(RuntimeError):
    """Raised when events cannot be read."""


class InvalidVisibilityError(ValueError):
    """Raised when event visibility is invalid."""


class EventStore:
    """Simple append-only JSONL event store.

    This intentionally avoids optional Cortex subsystems. It is the boring
    reliability substrate KempOS can depend on first.
    """

    def __init__(self, config_dir: Path | str | None = None):
        self.config_dir = Path(config_dir).expanduser().resolve() if config_dir else None

    def _events_path(self, namespace: str) -> Path:
        ns_dir = ensure_namespace(namespace, config_dir=self.config_dir)
        return ns_dir / "events.jsonl"

    def append(
        self,
        namespace: str,
        event_type: str,
        payload: dict[str, Any],
        visibility: str = "private",
    ) -> dict[str, Any]:
        """Append one event and return the stored event envelope."""
        safe_namespace = validate_namespace(namespace)
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        if visibility not in VALID_VISIBILITIES:
            raise InvalidVisibilityError(
                f"visibility must be one of {sorted(VALID_VISIBILITIES)}"
            )

        event = {
            "id": f"evt_{uuid.uuid4().hex}",
            "namespace": safe_namespace,
            "type": event_type.strip(),
            "visibility": visibility,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        try:
            path = self._events_path(safe_namespace)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, sort_keys=True) + "\n")
        except OSError as exc:
            raise EventWriteError(f"Failed to append event: {exc}") from exc

        return event

    def list(
        self,
        namespace: str,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List events newest-first, optionally filtered by type."""
        safe_namespace = validate_namespace(namespace)
        if limit <= 0:
            return []

        path = self._events_path(safe_namespace)
        if not path.exists():
            return []

        events: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        # Deterministic skip for corrupt rows. Future pass can add
                        # structured warnings if needed.
                        continue
                    if event.get("namespace") != safe_namespace:
                        continue
                    if event_type is not None and event.get("type") != event_type:
                        continue
                    events.append(event)
        except OSError as exc:
            raise EventReadError(f"Failed to read events: {exc}") from exc

        return list(reversed(events))[:limit]

    def get(self, namespace: str, event_id: str) -> dict[str, Any] | None:
        """Return one event by id, or None."""
        for event in self.list(namespace=namespace, limit=100000):
            if event.get("id") == event_id:
                return event
        return None
