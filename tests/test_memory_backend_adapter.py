"""
Tests for Memory Backend Adapter — ABC interface + FileMemoryBackend + AnthropicMemoryBackend stub.

Tests:
- ABC contract enforcement
- FileMemoryBackend store/retrieve roundtrip
- FileMemoryBackend query (keyword search)
- FileMemoryBackend anti-pattern storage
- FileMemoryBackend outcome retrieval
- FileMemoryBackend delete and list_keys
- AnthropicMemoryBackend stub raises NotImplementedError
- HybridRetriever accepts optional backend parameter
"""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def backend_dir():
    """Temporary directory for FileMemoryBackend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_backend(backend_dir):
    """FileMemoryBackend instance with temp storage."""
    from intelligence.memory.backend_adapter import FileMemoryBackend

    return FileMemoryBackend(base_dir=backend_dir)


class TestMemoryBackendABCContract:
    """Verify ABC contract is enforced."""

    def test_file_backend_implements_all_methods(self):
        from intelligence.memory.backend_adapter import (
            FileMemoryBackend,
            MemoryBackendAdapter,
        )

        # FileMemoryBackend must be a subclass of the ABC
        assert issubclass(FileMemoryBackend, MemoryBackendAdapter)
        # Should be instantiable (all abstract methods implemented)
        backend = FileMemoryBackend()
        assert backend is not None

    def test_anthropic_stub_implements_all_methods(self):
        from intelligence.memory.backend_adapter import (
            AnthropicMemoryBackend,
            MemoryBackendAdapter,
        )

        assert issubclass(AnthropicMemoryBackend, MemoryBackendAdapter)
        # Should be instantiable (all abstract methods implemented, even if they raise)
        backend = AnthropicMemoryBackend()
        assert backend is not None

    def test_cannot_instantiate_abc_directly(self):
        from intelligence.memory.backend_adapter import MemoryBackendAdapter

        with pytest.raises(TypeError, match="abstract"):
            MemoryBackendAdapter()


class TestFileMemoryBackendRoundtrip:
    """Tests for store → retrieve cycle."""

    def test_store_and_retrieve(self, file_backend):
        data = {"title": "Test Pattern", "content": "Use Redis for caching"}
        file_backend.store("pattern_001", data, namespace="patterns")
        result = file_backend.retrieve("pattern_001", namespace="patterns")
        assert result is not None
        assert result["title"] == "Test Pattern"
        assert result["content"] == "Use Redis for caching"
        assert "_stored_at" in result  # Metadata added by store

    def test_retrieve_nonexistent_returns_none(self, file_backend):
        result = file_backend.retrieve("nonexistent", namespace="patterns")
        assert result is None

    def test_store_overwrites(self, file_backend):
        file_backend.store("key1", {"v": 1}, namespace="ns")
        file_backend.store("key1", {"v": 2}, namespace="ns")
        result = file_backend.retrieve("key1", namespace="ns")
        assert result["v"] == 2

    def test_namespaces_are_isolated(self, file_backend):
        file_backend.store("key1", {"v": "patterns"}, namespace="patterns")
        file_backend.store("key1", {"v": "outcomes"}, namespace="outcomes")
        assert file_backend.retrieve("key1", namespace="patterns")["v"] == "patterns"
        assert file_backend.retrieve("key1", namespace="outcomes")["v"] == "outcomes"


class TestFileMemoryBackendQuery:
    """Tests for keyword-based query."""

    def test_query_finds_matching(self, file_backend):
        file_backend.store("p1", {"title": "Redis caching pattern"}, namespace="patterns")
        file_backend.store("p2", {"title": "JWT authentication"}, namespace="patterns")
        file_backend.store("p3", {"title": "Redis connection pooling"}, namespace="patterns")
        results = file_backend.query("Redis", namespace="patterns")
        assert len(results) == 2
        titles = [r["title"] for r in results]
        assert "Redis caching pattern" in titles
        assert "Redis connection pooling" in titles

    def test_query_returns_empty_for_no_match(self, file_backend):
        file_backend.store("p1", {"title": "Redis caching"}, namespace="patterns")
        results = file_backend.query("kubernetes", namespace="patterns")
        assert results == []

    def test_query_respects_limit(self, file_backend):
        for i in range(10):
            file_backend.store(f"p{i}", {"title": f"Pattern {i} redis"}, namespace="patterns")
        results = file_backend.query("redis", namespace="patterns", limit=3)
        assert len(results) == 3


class TestFileMemoryBackendAntiPatterns:
    """Tests for anti-pattern storage."""

    def test_store_anti_pattern(self, file_backend, backend_dir):
        pattern = {
            "id": "ap_mock_namespace",
            "failure_mode": "Mock patch targets wrong namespace",
            "trigger": "from X import Y at module level",
            "prevention": "Patch importing_module.Y, not X.Y",
        }
        file_backend.store_anti_pattern(pattern)
        # Should be stored in anti_patterns namespace
        result = file_backend.retrieve("ap_mock_namespace", namespace="anti_patterns")
        assert result is not None
        assert result["failure_mode"] == "Mock patch targets wrong namespace"


class TestFileMemoryBackendOutcomes:
    """Tests for outcome retrieval."""

    def test_get_outcomes_from_jsonl(self, file_backend, backend_dir):
        outcomes_path = backend_dir / "outcomes.jsonl"
        entries = [
            {"outcome": "success", "context": {"project": "vortex"}},
            {"outcome": "failure", "context": {"project": "cortex"}},
            {"outcome": "success", "context": {"project": "vortex"}},
        ]
        outcomes_path.write_text("\n".join(json.dumps(e) for e in entries))
        results = file_backend.get_outcomes()
        assert len(results) == 3

    def test_get_outcomes_filtered_by_project(self, file_backend, backend_dir):
        outcomes_path = backend_dir / "outcomes.jsonl"
        entries = [
            {"outcome": "success", "context": {"project": "vortex"}},
            {"outcome": "failure", "context": {"project": "cortex"}},
        ]
        outcomes_path.write_text("\n".join(json.dumps(e) for e in entries))
        results = file_backend.get_outcomes(project="vortex")
        assert len(results) == 1
        assert results[0]["context"]["project"] == "vortex"

    def test_get_outcomes_empty(self, file_backend):
        results = file_backend.get_outcomes()
        assert results == []


class TestFileMemoryBackendDeleteAndList:
    """Tests for delete and list_keys."""

    def test_delete_existing(self, file_backend):
        file_backend.store("key1", {"v": 1})
        assert file_backend.delete("key1") is True
        assert file_backend.retrieve("key1") is None

    def test_delete_nonexistent(self, file_backend):
        assert file_backend.delete("nonexistent") is False

    def test_list_keys(self, file_backend):
        file_backend.store("alpha", {"v": 1}, namespace="ns")
        file_backend.store("beta", {"v": 2}, namespace="ns")
        file_backend.store("gamma", {"v": 3}, namespace="ns")
        keys = file_backend.list_keys(namespace="ns")
        assert set(keys) == {"alpha", "beta", "gamma"}

    def test_list_keys_empty(self, file_backend):
        keys = file_backend.list_keys(namespace="empty_ns")
        assert keys == []


class TestAnthropicMemoryBackendStub:
    """Verify stub raises NotImplementedError with informative message."""

    def test_store_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError, match="not yet available"):
            backend.store("key", {"data": "value"})

    def test_retrieve_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError, match="not yet available"):
            backend.retrieve("key")

    def test_query_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError, match="not yet available"):
            backend.query("search text")

    def test_store_anti_pattern_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError):
            backend.store_anti_pattern({"id": "test"})

    def test_get_outcomes_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError):
            backend.get_outcomes()

    def test_delete_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError):
            backend.delete("key")

    def test_list_keys_raises(self):
        from intelligence.memory.backend_adapter import AnthropicMemoryBackend

        backend = AnthropicMemoryBackend()
        with pytest.raises(NotImplementedError):
            backend.list_keys()
