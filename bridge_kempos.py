"""Bridge mixin for explicit Cortex reliability contracts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from capabilities import CapabilityRegistry
from events import EventStore
from health import doctor_namespace
from recommendations_store import RecommendationStore


class KempOSContractsMixin:
    """Expose namespace/event/capability contracts through CortexBridge.

    The methods are generic despite the name: KempOS is the reference workload,
    not a special case in the storage layer.
    """

    def _contract_config_dir(self):
        config = getattr(self, "config", None)
        return getattr(config, "config_dir", None)

    def capabilities(self) -> dict[str, dict]:
        return CapabilityRegistry(config_dir=self._contract_config_dir()).list()

    def require_capability(self, name: str) -> dict:
        return CapabilityRegistry(config_dir=self._contract_config_dir()).require(name).to_dict()

    def append_event(
        self,
        namespace: str,
        event_type: str,
        payload: dict[str, Any],
        visibility: str = "private",
    ) -> dict[str, Any]:
        return EventStore(config_dir=self._contract_config_dir()).append(
            namespace=namespace,
            event_type=event_type,
            payload=payload,
            visibility=visibility,
        )

    def list_events(
        self,
        namespace: str,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return EventStore(config_dir=self._contract_config_dir()).list(
            namespace=namespace,
            event_type=event_type,
            limit=limit,
        )

    def doctor_namespace(self, namespace: str) -> dict[str, Any]:
        return doctor_namespace(namespace, config_dir=self._contract_config_dir())

    def inject_recommendation(
        self,
        title: str,
        rationale: str,
        priority: str = "medium",
        type: str = "ai_suggestion",
        effort: str = "Unknown",
        related_project: str = "",
        namespace: str = "default",
        visibility: str = "private",
    ) -> bool:
        """Inject recommendation with namespace-aware storage.

        For namespace='default', preserve the legacy external_recommendations.json
        behavior closely. For any other namespace, store under
        ~/.cortex/namespaces/<namespace>/recommendations.json.
        """
        if namespace != "default":
            try:
                RecommendationStore(config_dir=self._contract_config_dir()).add(
                    namespace=namespace,
                    title=title,
                    rationale=rationale,
                    priority=priority,
                    type=type,
                    effort=effort,
                    related_project=related_project,
                    visibility=visibility,
                )
                return True
            except Exception:
                return False

        rec_data = {
            "id": f"bridge_{datetime.now().timestamp()}",
            "title": title,
            "type": type,
            "priority": priority,
            "rationale": rationale,
            "estimated_effort": effort,
            "estimated_impact": priority,
            "confidence": 0.95,
            "related_projects": [related_project] if related_project else [],
            "description": f"Injected via Cortex Bridge.\nRationale: {rationale}",
            "created_at": datetime.now().isoformat(),
            "source": "CortexBridge",
            "namespace": namespace,
            "visibility": visibility,
        }

        if (self.root_dir / "bridge.py").exists():
            external_file = self.root_dir / "external_recommendations.json"
        else:
            external_file = self.root_dir / "cortex" / "external_recommendations.json"

        try:
            current_recs = []
            if external_file.exists():
                content = external_file.read_text()
                if content.strip():
                    try:
                        current_recs = json.loads(content)
                    except json.JSONDecodeError:
                        current_recs = []

            current_recs.append(rec_data)
            external_file.write_text(json.dumps(current_recs, indent=2))
            return True
        except Exception:
            return False
