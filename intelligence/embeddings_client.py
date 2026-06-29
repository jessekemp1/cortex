"""Embeddings client for Cortex.

Default backend: sklearn HashingVectorizer (768-dim, no deps, no fitting) — keeps
the base install light. Optional higher-quality semantic backends are used
automatically WHEN PRESENT, with graceful fallback to hashing:

  * Ollama (recommended local addon): install `ollama` + `ollama pull nomic-embed-text`.
    Detected over local HTTP (adds NO Python dependency to cortex). Real semantic
    embeddings, offline, free.
  * Voyage API: set VOYAGE_API_KEY (+ `pip install voyageai`).

Precedence: Voyage (if key) > Ollama (if reachable) > HashingVectorizer.
Select explicitly with CORTEX_EMBED_BACKEND = auto|voyage|ollama|local (default auto).
"""

import json
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional

from sklearn.feature_extraction.text import HashingVectorizer

logger = logging.getLogger(__name__)

# Shared hashing vectorizer (no fitting required — hashing trick)
_VECTORIZER = HashingVectorizer(
    analyzer="word", ngram_range=(1, 3), n_features=768,
    norm="l2", alternate_sign=False, lowercase=True,
)

EMBEDDING_DIM = 768  # hashing/voyage default; Ollama reports its model's native dim


class EmbeddingsClient:
    """Embeddings with an optional, auto-detected local semantic backend (Ollama)."""

    def __init__(self, api_key: Optional[str] = None):
        self._voyage_client = None
        self._ollama: Optional[tuple] = None  # (host, model)
        self._nomic = False  # nomic-embed-text needs search_query/search_document prefixes
        self._dim = EMBEDDING_DIM
        backend = os.getenv("CORTEX_EMBED_BACKEND", "auto").lower()

        voyage_key = api_key or os.getenv("VOYAGE_API_KEY")
        if voyage_key and backend in ("auto", "voyage"):
            try:
                import voyageai  # type: ignore

                self._voyage_client = voyageai.Client(api_key=voyage_key)
                logger.info("Using Voyage AI embeddings (voyage-3-lite)")
            except ImportError:
                logger.debug("voyageai not installed — skipping Voyage backend")

        # Optional local addon: Ollama (auto-detected; no python dependency).
        if not self._voyage_client and backend in ("auto", "ollama"):
            host = os.getenv("CORTEX_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            model = os.getenv("CORTEX_OLLAMA_EMBED_MODEL", "nomic-embed-text")
            dim = self._probe_ollama(host, model)
            if dim:
                self._ollama = (host, model)
                self._dim = dim
                # nomic-embed-text REQUIRES asymmetric task prefixes; without
                # them retrieval quality drops sharply.
                self._nomic = model.startswith("nomic")
                logger.info(f"Using Ollama embeddings ({model}, {dim}-dim) at {host}")
            elif backend == "ollama":
                logger.warning("CORTEX_EMBED_BACKEND=ollama but Ollama is unreachable or the "
                               "model isn't pulled — falling back to local hashing")

        if not self._voyage_client and not self._ollama:
            logger.debug("Using local HashingVectorizer embeddings (768-dim)")

    # ---- Ollama helpers (stdlib HTTP; no dependency added to cortex) ----
    @staticmethod
    def _ollama_embed(host: str, model: str, text: str, timeout: float = 30.0) -> Optional[List[float]]:
        """Embed one text via Ollama. Tries /api/embed (new) then /api/embeddings (old)."""
        for path, payload, key in (
            ("/api/embed", {"model": model, "input": text}, "embeddings"),
            ("/api/embeddings", {"model": model, "prompt": text}, "embedding"),
        ):
            try:
                req = urllib.request.Request(
                    host + path, data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read())
                v = data.get(key)
                if key == "embeddings" and v:  # /api/embed returns a list of vectors
                    v = v[0]
                if v:
                    return v
            except Exception:
                continue
        return None

    def _probe_ollama(self, host: str, model: str) -> Optional[int]:
        """Return embedding dim if Ollama + model are usable, else None."""
        v = self._ollama_embed(host, model, "ping", timeout=5.0)
        return len(v) if v else None

    def generate_embedding(self, text: str, model: str = "") -> List[float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        if len(text) > 8000:
            text = text[:8000]

        if self._ollama:
            host, ollama_model = self._ollama
            # single-text path is the query side (hybrid_retriever embeds the query here)
            q = f"search_query: {text}" if self._nomic else text
            v = self._ollama_embed(host, ollama_model, q)
            if v:
                return v
            logger.warning("Ollama embedding failed — falling back to local hashing")
        if self._voyage_client:
            try:
                vec = self._voyage_client.embed([text], model="voyage-3-lite").embeddings[0]
                if len(vec) < EMBEDDING_DIM:
                    vec = vec + [0.0] * (EMBEDDING_DIM - len(vec))
                return vec[:EMBEDDING_DIM]
            except Exception as e:
                logger.warning(f"Voyage embedding failed: {e} — falling back to local")

        return _VECTORIZER.transform([text]).toarray()[0].tolist()

    def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100, max_retries: int = 3
    ) -> List[List[float]]:
        if not texts:
            return []

        if self._ollama:
            host, ollama_model = self._ollama
            out: List[List[float]] = []
            for t in texts:
                t = t[:8000] if t and t.strip() else " "
                # batch path is the document side (pattern corpus)
                doc = f"search_document: {t}" if self._nomic else t
                v = self._ollama_embed(host, ollama_model, doc)
                out.append(v if v else _VECTORIZER.transform([t]).toarray()[0].tolist())
            return out

        if self._voyage_client:
            results: List[List[float]] = []
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
                            results.extend(_VECTORIZER.transform(batch).toarray().tolist())
            return results

        valid_texts = [t[:8000] if t and t.strip() else " " for t in texts]
        return _VECTORIZER.transform(valid_texts).toarray().tolist()

    def get_embedding_dimension(self) -> int:
        return self._dim

    def is_api_available(self) -> bool:
        """True if a real semantic backend (Voyage or Ollama) is active."""
        return self._voyage_client is not None or self._ollama is not None

    def get_embedding_info(self) -> Dict[str, Any]:
        if self._voyage_client:
            backend = "voyage-3-lite"
        elif self._ollama:
            backend = f"ollama:{self._ollama[1]}"
        else:
            backend = "sklearn-hashing-ngram"
        return {
            "backend": backend,
            "api_available": self.is_api_available(),
            "dimension": self._dim,
            "requires_api_key": self._voyage_client is not None,
        }
