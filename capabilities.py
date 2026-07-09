"""Explicit Cortex capability registry.

This module makes degraded/missing behavior visible to callers instead of
requiring them to infer it from optional imports or silent fallbacks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from events import EventStore
from namespaces import ensure_namespace

CapabilityState = Literal["available", "degraded", "missing"]


@dataclass(frozen=True)
class CapabilityStatus:
    name: str
    status: CapabilityState
    reason: str | None = None
    fallback: str | None = None
    checked_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class CapabilityRegistry:
    """Small explicit registry for reliability contracts.

    Pass 1 is intentionally conservative: filesystem-backed namespace/events
    are available; optional higher-order systems are degraded or missing until
    specific contracts are implemented.
    """

    def __init__(self, config_dir: Path | str | None = None):
        self.config_dir = Path(config_dir).expanduser().resolve() if config_dir else None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _available(self, name: str, reason: str | None = None) -> CapabilityStatus:
        return CapabilityStatus(name=name, status="available", reason=reason, checked_at=self._now())

    def _degraded(self, name: str, reason: str, fallback: str | None = None) -> CapabilityStatus:
        return CapabilityStatus(
            name=name,
            status="degraded",
            reason=reason,
            fallback=fallback,
            checked_at=self._now(),
        )

    def _missing(self, name: str, reason: str) -> CapabilityStatus:
        return CapabilityStatus(name=name, status="missing", reason=reason, checked_at=self._now())

    def _events_available(self, capability_name: str) -> CapabilityStatus:
        try:
            ensure_namespace("healthcheck", config_dir=self.config_dir)
            store = EventStore(config_dir=self.config_dir)
            event = store.append(
                namespace="healthcheck",
                event_type="capability_check",
                payload={"capability": capability_name},
            )
            if store.get("healthcheck", event["id"]):
                return self._available(capability_name, "filesystem event store write/read ok")
            return self._degraded(capability_name, "event write succeeded but readback failed")
        except Exception as exc:  # pragma: no cover - exact failure platform-dependent
            return self._missing(capability_name, str(exc))

    def get(self, name: str) -> CapabilityStatus:
        if name in {"events.write", "events.read", "namespace.isolation", "health.doctor"}:
            if name == "namespace.isolation":
                try:
                    ensure_namespace("healthcheck", config_dir=self.config_dir)
                    return self._available(name, "namespaced private state directory available")
                except Exception as exc:
                    return self._missing(name, str(exc))
            if name == "health.doctor":
                return self._available(name, "doctor_namespace is filesystem-backed")
            return self._events_available(name)

        if name == "recommendations.inject":
            return self._degraded(name, "namespaced recommendation contract pending Pass 2", "events.write")
        if name in {"memory.read", "memory.write"}:
            return self._degraded(name, "optional memory subsystem not part of Pass 1 contract", "events.jsonl")
        if name in {"scheduler.status", "scheduler.run"}:
            return self._missing(name, "scheduler contract deferred to later phase")

        return self._missing(name, "unknown capability")

    def list(self) -> dict[str, dict]:
        names = [
            "memory.read",
            "memory.write",
            "events.read",
            "events.write",
            "recommendations.inject",
            "scheduler.status",
            "scheduler.run",
            "health.doctor",
            "namespace.isolation",
        ]
        return {name: self.get(name).to_dict() for name in names}

    def require(self, name: str) -> CapabilityStatus:
        status = self.get(name)
        if status.status == "missing":
            raise RuntimeError(f"Required capability missing: {name} ({status.reason})")
        return status
