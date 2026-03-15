"""
Memory Backend Adapter — ABC interface for pluggable memory storage.

Enables future backend swap (file → Anthropic native → Mem0) while
preserving intelligence layers (anti-patterns, outcome learning, goal pipeline).

Current backends:
  - FileMemoryBackend: Wraps current file+SQLite storage (default)
  - AnthropicMemoryBackend: Stub for Anthropic native memory API (not yet available)

Usage:
    backend = FileMemoryBackend(base_dir=Path.home() / ".cortex")
    backend.store("key", {"data": "value"}, namespace="patterns")
    result = backend.retrieve("key", namespace="patterns")
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryBackendAdapter(ABC):
    """Abstract base class for memory storage backends.

    All Cortex memory operations route through this interface.
    Implementations must handle: store, retrieve, query, anti-patterns, outcomes.
    """

    @abstractmethod
    def store(self, key: str, data: Dict[str, Any], namespace: str = "default") -> None:
        """Store a memory entry.

        Args:
            key: Unique identifier for this memory.
            data: Serializable dict of memory content.
            namespace: Logical grouping (e.g., "patterns", "anti_patterns", "outcomes").
        """

    @abstractmethod
    def retrieve(self, key: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        """Retrieve a single memory entry by key.

        Returns None if not found.
        """

    @abstractmethod
    def query(self, text: str, namespace: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """Query memories by text similarity/keyword match.

        Args:
            text: Search query.
            namespace: Namespace to search within.
            limit: Maximum results.

        Returns:
            List of matching memory entries, ordered by relevance.
        """

    @abstractmethod
    def store_anti_pattern(self, pattern: Dict[str, Any]) -> None:
        """Store an anti-pattern (failure mode + trigger + prevention).

        Anti-patterns are a core Cortex primitive and get special treatment
        in retrieval (higher boost, trigger matching).
        """

    @abstractmethod
    def get_outcomes(self, project: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve outcome records for feedback loop.

        Args:
            project: Optional project filter.
            limit: Maximum results.

        Returns:
            List of outcome entries (success/failure + context).
        """

    @abstractmethod
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a memory entry. Returns True if found and deleted."""

    @abstractmethod
    def list_keys(self, namespace: str = "default") -> List[str]:
        """List all keys in a namespace."""


class FileMemoryBackend(MemoryBackendAdapter):
    """File-based memory backend — wraps current file+SQLite storage.

    This is the default backend that preserves all current Cortex behavior.
    Data is stored as JSON files organized by namespace under base_dir.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path.home() / ".cortex")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _namespace_dir(self, namespace: str) -> Path:
        d = self.base_dir / "memory" / namespace
        d.mkdir(parents=True, exist_ok=True)
        return d

    def store(self, key: str, data: Dict[str, Any], namespace: str = "default") -> None:
        path = self._namespace_dir(namespace) / f"{key}.json"
        data["_stored_at"] = datetime.now(tz=timezone.utc).isoformat()
        path.write_text(json.dumps(data, indent=2, default=str))
        logger.debug("Stored memory: %s/%s", namespace, key)

    def retrieve(self, key: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        path = self._namespace_dir(namespace) / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to retrieve %s/%s: %s", namespace, key, e)
            return None

    def query(self, text: str, namespace: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """Simple keyword-based query over stored memories."""
        ns_dir = self._namespace_dir(namespace)
        text_lower = text.lower()
        text_words = set(text_lower.split())

        results: List[tuple] = []
        for path in ns_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                content_str = json.dumps(data).lower()
                # Score by keyword overlap
                score = sum(1 for w in text_words if w in content_str)
                if score > 0:
                    results.append((score, data))
            except (json.JSONDecodeError, OSError):
                continue

        results.sort(key=lambda x: x[0], reverse=True)
        return [data for _, data in results[:limit]]

    def store_anti_pattern(self, pattern: Dict[str, Any]) -> None:
        key = pattern.get("id", f"ap_{hash(str(pattern)) & 0xFFFFFFFF:08x}")
        self.store(key, pattern, namespace="anti_patterns")

    def get_outcomes(self, project: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        outcomes_path = self.base_dir / "outcomes.jsonl"
        if not outcomes_path.exists():
            return []

        results = []
        for line in outcomes_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if project:
                    entry_project = entry.get("context", {}).get("project", "")
                    if entry_project != project:
                        continue
                results.append(entry)
            except (json.JSONDecodeError, TypeError):
                continue

        return results[-limit:]

    def delete(self, key: str, namespace: str = "default") -> bool:
        path = self._namespace_dir(namespace) / f"{key}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self, namespace: str = "default") -> List[str]:
        ns_dir = self._namespace_dir(namespace)
        return [p.stem for p in ns_dir.glob("*.json")]


class AnthropicMemoryBackend(MemoryBackendAdapter):
    """Stub for Anthropic native memory API.

    Anthropic's "free memory" (memories.anthropic.com) is currently user-facing,
    not a developer API. This stub exists so the ABC interface is proven with
    two implementations. Full adapter waits for confirmed API surface.

    CRA monitors Anthropic memory API status weekly via threat_monitors.
    """

    def store(self, key: str, data: Dict[str, Any], namespace: str = "default") -> None:
        raise NotImplementedError(
            "Anthropic memory API not yet available as a developer API. "
            "Monitor via CRA source 'anthropic_native_memory' for updates."
        )

    def retrieve(self, key: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")

    def query(self, text: str, namespace: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")

    def store_anti_pattern(self, pattern: Dict[str, Any]) -> None:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")

    def get_outcomes(self, project: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")

    def delete(self, key: str, namespace: str = "default") -> bool:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")

    def list_keys(self, namespace: str = "default") -> List[str]:
        raise NotImplementedError("Anthropic memory API not yet available as a developer API.")
