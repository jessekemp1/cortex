#!/usr/bin/env python3
"""Tests for bridge.py hybrid retriever wiring.

Verifies that the bridge constructs HybridRetriever instances with
embeddings_client properly wired, so that embeddings_available is True
when an embeddings backend is present. The test intentionally FAILS
before the fix is applied — the failure is the deliverable that proves
the bug exists.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.hybrid_retriever import HybridRetriever


@pytest.fixture
def mock_embeddings_client():
    """Create mock embeddings client that reports api_available=True."""
    client = Mock(spec=EmbeddingsClient)
    client.get_embedding_dimension.return_value = 768

    def generate_embedding(text):
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i : i + 4]
            value = int.from_bytes(chunk, byteorder="big")
            normalized = (value / (2**32)) * 2 - 1
            embedding.append(normalized)
        while len(embedding) < 768:
            embedding.extend(embedding[: min(768 - len(embedding), len(embedding))])
        return embedding[:768]

    def generate_embeddings_batch(texts, batch_size=100):
        return [generate_embedding(text) for text in texts]

    client.generate_embedding.side_effect = generate_embedding
    client.generate_embeddings_batch.side_effect = generate_embeddings_batch
    client.get_embedding_info.return_value = {
        'backend': 'ollama',
        'api_available': True,
        'dimension': 768,
        'requires_api_key': False,
    }

    return client


@pytest.fixture
def sample_patterns():
    """Create minimal sample patterns for testing."""
    from intelligence.memory.pattern_indexer import Pattern
    from datetime import datetime

    return [
        Pattern(
            id="test:pattern1",
            project="test_project",
            commit_hash="abc123",
            commit_date=datetime.now(),
            title="Test Pattern",
            description="A test pattern for retriever wiring",
            files_changed=["test.py"],
            keywords={"test", "pattern"},
            pattern_type="test",
        ),
    ]


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestBridgeRetrievalWiring:
    """Tests for HybridRetriever construction wiring in bridge.py context."""

    def test_bridge_passes_embeddings_client_at_every_call_site(self):
        """bridge.py must pass an embeddings_client wherever it builds a retriever.

        This asserts against the REAL source of bridge.py rather than
        re-constructing retrievers by hand, so it fails if the fix is ever
        reverted. An earlier version of this test built its own buggy and fixed
        retrievers side by side; that documented the mechanism but passed with
        the fix stashed, making it useless as a regression guard.

        The bug it guards: bridge.py called
        ``HybridRetriever(patterns=pm.patterns)`` with no embeddings_client, so
        ``embeddings_available`` was False and every MCP ``cortex_intelligence``
        query silently degraded to BM25 keyword-only.
        """
        import inspect

        import bridge as bridge_mod

        src = inspect.getsource(bridge_mod)

        # The keyword-only form is the bug signature: passing `patterns=` as a
        # kwarg with nothing after it means no client was supplied.
        unwired = src.count("HybridRetriever(patterns=")
        assert unwired == 0, (
            f"{unwired} HybridRetriever call site(s) in bridge.py omit "
            "embeddings_client — MCP recall silently degrades to keyword-only"
        )

        # And a client must actually be constructed for those call sites to use.
        assert "EmbeddingsClient" in src, (
            "bridge.py must import and construct EmbeddingsClient to pass into "
            "HybridRetriever"
        )

    def test_retriever_without_client_has_no_semantic_search(self, sample_patterns):
        """Document the underlying mechanism the wiring bug exploited.

        Kept separate from the regression guard above: this pins the
        HybridRetriever contract (no client ⇒ no semantic path), which is
        legitimate behaviour, not a bug.
        """
        retriever = HybridRetriever(patterns=sample_patterns)
        assert retriever.embeddings_available is False
        assert retriever.pattern_embeddings is None

    def test_bridge_construction_path_loads_decision_patterns(
        self, sample_patterns, temp_cache_dir
    ):
        """
        Verify that the construction path used by bridge.py
        (intelligence.memory.hybrid_retriever._load_decision_patterns())
        correctly loads patterns from the live store and that they can be
        indexed into a HybridRetriever.

        Skip if api_available is False AND backend is hashing (no embeddings backend
        in the environment, which is OK for CI without ollama).
        """
        from intelligence.embeddings_client import EmbeddingsClient
        from intelligence.memory.hybrid_retriever import _load_decision_patterns

        # Check if embeddings backend is available
        try:
            client = EmbeddingsClient()
            info = client.get_embedding_info()
            api_available = info.get("api_available", False)
            backend = info.get("backend", "")

            # Skip if no real backend (environment issue, not a code bug)
            if not api_available and "hashing" in backend:
                pytest.skip(
                    f"No embeddings backend available (backend={backend}, "
                    "api_available=False) — CI without ollama is OK"
                )
        except Exception:
            pytest.skip("Could not probe embeddings backend")

        # Load patterns the way bridge.py does
        decision_patterns = _load_decision_patterns()

        # If we got here, embeddings should be available
        # (or skip already happened above)
        if decision_patterns:
            # Decision patterns were loaded; they should be indexable
            assert isinstance(decision_patterns, list)
            for pattern in decision_patterns:
                assert hasattr(pattern, "id")

            # Construct retriever with decision patterns and real embeddings client
            # This is what bridge.py SHOULD do (not what it currently does)
            retriever = HybridRetriever(
                patterns=decision_patterns,
                embeddings_client=client,
                cache_dir=temp_cache_dir,
            )

            # Assert embeddings are properly wired
            assert retriever.embeddings_available is True

    def test_semantic_query_surfaces_recent_decision(self):
        """
        Query for "what did we conclude about views needing serverless"
        with project='interac' should return decision id containing
        dec_ee472609ffe9 in the top 3 (if present in local store).

        Skips if that decision isn't in the store (portable across environments).
        """
        from intelligence.memory.hybrid_retriever import _load_decision_patterns, HybridRetriever

        # Load decisions from the live store
        decision_patterns = _load_decision_patterns()

        # Check if the specific decision is present
        target_id = "decision:dec_ee472609ffe9"
        target_present = any(p.id == target_id for p in decision_patterns)

        if not target_present:
            pytest.skip(
                f"Target decision {target_id} not in local store "
                "(portable test across environments)"
            )

        # Construct retriever with decision patterns
        from intelligence.embeddings_client import EmbeddingsClient

        client = EmbeddingsClient()
        info = client.get_embedding_info()
        api_available = info.get("api_available", False)
        backend = info.get("backend", "")

        if not api_available and "hashing" in backend:
            pytest.skip(
                f"No embeddings backend available for semantic ranking "
                "(backend={backend}, api_available=False)"
            )

        retriever = HybridRetriever(patterns=decision_patterns, embeddings_client=client)

        # Query for serverless + views + Interac context
        results = retriever.search(
            "what did we conclude about views needing serverless",
            limit=3,
            alpha=1.0,  # Semantic search only
            project="interac",
        )

        # Assert the target decision surfaces in top 3
        result_ids = [p.id for p, _ in results]
        assert target_id in result_ids, (
            f"Expected {target_id} in top 3 results for interac project, "
            f"got: {result_ids}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
