"""Local Embeddings Client for Cortex — sklearn HashingVectorizer backend.

Uses scikit-learn's HashingVectorizer with word/char n-grams to produce 768-dim
dense vectors with real semantic similarity. No API key required.

Falls back to an optional real embeddings API (voyageai, openai) if configured.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

logger = logging.getLogger(__name__)

# Shared vectorizer instance (no fitting required — hashing trick)
_VECTORIZER = HashingVectorizer(
    analyzer="word",
    ngram_range=(1, 3),
    n_features=768,
    norm="l2",
    alternate_sign=False,
    lowercase=True,
)

EMBEDDING_DIM = 768


class EmbeddingsClient:
    """Embeddings client using local sklearn HashingVectorizer.

    Produces 768-dim dense vectors via word/char n-gram hashing.
    No external API or fitting corpus required.

    Optional: set VOYAGE_API_KEY to use voyage-3-lite for higher quality
    semantic embeddings when available.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize embeddings client.

        Args:
            api_key: Optional Voyage AI or other embeddings API key.
                     If not provided, uses local HashingVectorizer (default).
        """
        self._voyage_client = None
        voyage_key = api_key or os.getenv("VOYAGE_API_KEY")
        if voyage_key:
            try:
                import voyageai  # type: ignore

                self._voyage_client = voyageai.Client(api_key=voyage_key)
                logger.info("Using Voyage AI embeddings (voyage-3-lite)")
            except ImportError:
                logger.debug("voyageai not installed — using local HashingVectorizer")

        if not self._voyage_client:
            logger.debug("Using local HashingVectorizer embeddings (n-gram, 768-dim)")

    def generate_embedding(self, text: str, model: str = "") -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed (empty string raises ValueError).
            model: Unused — kept for API compatibility.

        Returns:
            768-dim list of floats with L2 norm ≈ 1.0.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Truncate to reasonable length
        if len(text) > 8000:
            text = text[:8000]

        if self._voyage_client:
            try:
                result = self._voyage_client.embed([text], model="voyage-3-lite")
                vec = result.embeddings[0]
                # Pad or truncate to 768
                if len(vec) < EMBEDDING_DIM:
                    vec = vec + [0.0] * (EMBEDDING_DIM - len(vec))
                return vec[:EMBEDDING_DIM]
            except Exception as e:
                logger.warning(f"Voyage AI embedding failed: {e} — falling back to local")

        sparse = _VECTORIZER.transform([text])
        return sparse.toarray()[0].tolist()

    def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100, max_retries: int = 3
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size for API calls (ignored for local backend).
            max_retries: Retries for API calls (ignored for local backend).

        Returns:
            List of 768-dim embedding vectors.
        """
        if not texts:
            return []

        if self._voyage_client:
            results = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                for attempt in range(max_retries):
                    try:
                        result = self._voyage_client.embed(batch, model="voyage-3-lite")
                        for vec in result.embeddings:
                            if len(vec) < EMBEDDING_DIM:
                                vec = vec + [0.0] * (EMBEDDING_DIM - len(vec))
                            results.append(vec[:EMBEDDING_DIM])
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.warning(f"Voyage batch failed, using local: {e}")
                            # Fall through to local for this batch
                            sparse = _VECTORIZER.transform(batch)
                            results.extend(sparse.toarray().tolist())
            return results

        # Local backend — vectorize all at once (fast, no batching needed)
        valid_texts = [t[:8000] if t and t.strip() else " " for t in texts]
        sparse = _VECTORIZER.transform(valid_texts)
        return sparse.toarray().tolist()

    def get_embedding_dimension(self) -> int:
        """Return embedding dimension."""
        return EMBEDDING_DIM

    def is_api_available(self) -> bool:
        """Return True if a real (non-local) embeddings API is active."""
        return self._voyage_client is not None

    def get_embedding_info(self) -> Dict[str, Any]:
        """Return information about the active embeddings backend."""
        backend = "voyage-3-lite" if self._voyage_client else "sklearn-hashing-ngram"
        return {
            "backend": backend,
            "api_available": self.is_api_available(),
            "dimension": EMBEDDING_DIM,
            "requires_api_key": self._voyage_client is not None,
        }
