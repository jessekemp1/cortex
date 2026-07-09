"""Namespaced recommendation storage for Cortex private workloads."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from namespaces import ensure_namespace, validate_namespace


class RecommendationWriteError(RuntimeError):
    """Raised when a recommendation cannot be written."""


class RecommendationStore:
    """Simple JSON-backed namespaced recommendation store."""

    def __init__(self, config_dir: Path | str | None = None):
        self.config_dir = Path(config_dir).expanduser().resolve() if config_dir else None

    def _path(self, namespace: str) -> Path:
        ns_dir = ensure_namespace(namespace, config_dir=self.config_dir)
        return ns_dir / "recommendations.json"

    def add(
        self,
        namespace: str,
        title: str,
        rationale: str,
        priority: str = "medium",
        type: str = "ai_suggestion",
        effort: str = "Unknown",
        related_project: str = "",
        visibility: str = "private",
    ) -> dict[str, Any]:
        safe_namespace = validate_namespace(namespace)
        rec = {
            "id": f"rec_{uuid.uuid4().hex}",
            "namespace": safe_namespace,
            "visibility": visibility,
            "title": title,
            "type": type,
            "priority": priority,
            "rationale": rationale,
            "estimated_effort": effort,
            "estimated_impact": priority,
            "confidence": 0.95,
            "related_projects": [related_project] if related_project else [],
            "description": f"Injected via Cortex Bridge.\nRationale: {rationale}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "CortexBridge",
        }

        path = self._path(safe_namespace)
        try:
            current: list[dict[str, Any]] = []
            if path.exists() and path.read_text(encoding="utf-8").strip():
                current = json.loads(path.read_text(encoding="utf-8"))
            current.append(rec)
            path.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        except (OSError, json.JSONDecodeError) as exc:
            raise RecommendationWriteError(f"Failed to write recommendation: {exc}") from exc

        return rec

    def list(self, namespace: str) -> list[dict[str, Any]]:
        safe_namespace = validate_namespace(namespace)
        path = self._path(safe_namespace)
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                return []
            items = json.loads(text)
        except (OSError, json.JSONDecodeError):
            return []
        return [item for item in items if item.get("namespace") == safe_namespace]
