"""Health checks for Cortex namespaced private state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capabilities import CapabilityRegistry
from events import EventStore
from namespaces import ensure_namespace, validate_namespace


def _check(name: str, status: str, detail: str | None = None) -> dict[str, str | None]:
    return {"name": name, "status": status, "detail": detail}


def _path_inside(path: Path, root: Path) -> bool:
    path = path.resolve()
    root = root.resolve()
    return path == root or root in path.parents


def doctor_namespace(namespace: str, config_dir: Path | str | None = None) -> dict[str, Any]:
    """Validate basic namespaced Cortex storage reliability.

    This is filesystem-only in Pass 1. It should run without API keys,
    scheduler, MCP, vector DBs, or optional intelligence modules.
    """
    checks: list[dict[str, str | None]] = []
    recommendations: list[str] = []

    try:
        safe_namespace = validate_namespace(namespace)
        checks.append(_check("namespace.validate", "pass"))
    except Exception as exc:
        return {
            "namespace": namespace,
            "status": "unhealthy",
            "checks": [_check("namespace.validate", "fail", str(exc))],
            "recommendations": ["Use a lowercase safe namespace like kempos."],
        }

    try:
        ns_dir = ensure_namespace(safe_namespace, config_dir=config_dir)
        checks.append(_check("namespace.ensure", "pass", str(ns_dir)))
    except Exception as exc:
        checks.append(_check("namespace.ensure", "fail", str(exc)))
        return {
            "namespace": safe_namespace,
            "status": "unhealthy",
            "checks": checks,
            "recommendations": ["Fix Cortex config directory permissions."],
        }

    # Make sure private namespace state is not accidentally under the repo cwd.
    try:
        cwd = Path.cwd().resolve()
        if _path_inside(ns_dir, cwd):
            checks.append(_check("namespace.private_path", "fail", str(ns_dir)))
            recommendations.append("Namespace state is inside repo working tree; move config_dir outside repo.")
        else:
            checks.append(_check("namespace.private_path", "pass", str(ns_dir)))
    except Exception as exc:
        checks.append(_check("namespace.private_path", "warn", str(exc)))

    store = EventStore(config_dir=config_dir)
    event_id = None
    try:
        event = store.append(
            namespace=safe_namespace,
            event_type="doctor_check",
            payload={"check": "write_read"},
            visibility="private",
        )
        event_id = event["id"]
        checks.append(_check("events.write", "pass", event_id))
    except Exception as exc:
        checks.append(_check("events.write", "fail", str(exc)))

    if event_id:
        try:
            readback = store.get(safe_namespace, event_id)
            if readback:
                checks.append(_check("events.read", "pass", event_id))
            else:
                checks.append(_check("events.read", "fail", "event not found after write"))
        except Exception as exc:
            checks.append(_check("events.read", "fail", str(exc)))

    try:
        registry = CapabilityRegistry(config_dir=config_dir)
        capability_report = registry.list()
        checks.append(_check("capabilities.list", "pass"))
    except Exception as exc:
        capability_report = {}
        checks.append(_check("capabilities.list", "fail", str(exc)))

    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    if failed:
        status = "unhealthy"
    elif warned:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "namespace": safe_namespace,
        "status": status,
        "checks": checks,
        "capabilities": capability_report,
        "recommendations": recommendations,
    }
