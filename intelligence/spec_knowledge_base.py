"""Spec Knowledge Base - Semantic similarity search over indexed specs."""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from .models import SimilarWork


def _connect(db_path) -> "sqlite3.Connection":
    """Open the shared store with WAL + busy_timeout.

    Multiple processes share these databases (MCP servers per Claude session,
    the CLI, and the bridge daemon). WAL allows concurrent readers during a
    write; busy_timeout makes a second writer wait up to 5s instead of
    failing immediately with 'database is locked'.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


logger = logging.getLogger(__name__)


class SpecKnowledgeBase:
    """Index and search specs using embeddings + SQLite."""

    def __init__(self, storage_path: Optional[Path] = None):
        # Resolve at call time to honor test-harness HOME monkeypatching.
        if storage_path is None:
            storage_path = Path.home() / ".claude" / "specs"
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb not available - run: pip install chromadb")

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=str(storage_path / "embeddings"))
        self.collection = self.chroma_client.get_or_create_collection(
            name="specs", metadata={"hnsw:space": "cosine"}
        )

        # Initialize SQLite for metadata
        self.metadata_db = storage_path / "learnings.db"
        self._init_metadata_db()

        # Initialize embeddings client (lazy)
        self._embeddings_client = None

        # Embedding cache to avoid regenerating for unchanged content
        self._embedding_cache: Dict[str, List[float]] = {}
        self._cache_file = storage_path / "embedding_cache.json"
        self._load_embedding_cache()

    def _init_metadata_db(self):
        """Initialize SQLite database for spec metadata."""
        conn = _connect(self.metadata_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS specs (
                spec_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                project TEXT NOT NULL,
                domain TEXT,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                key_concepts TEXT
            )
        """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project ON specs(project)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain ON specs(domain)")
        conn.commit()
        conn.close()

    def _get_embeddings_client(self):
        """Lazy initialize embeddings client."""
        if self._embeddings_client is None:
            try:
                from .embeddings_client import EmbeddingsClient

                self._embeddings_client = EmbeddingsClient()
                logger.info("EmbeddingsClient initialized successfully")
            except (ImportError, ValueError, Exception) as e:
                logger.warning(f"EmbeddingsClient not available: {e}. Using hash-based fallback.")
                self._embeddings_client = None
        return self._embeddings_client

    def _load_embedding_cache(self):
        """Load embedding cache from disk."""
        if self._cache_file.exists():
            try:
                cache_data = json.loads(self._cache_file.read_text())
                self._embedding_cache = {k: v for k, v in cache_data.items()}
                logger.debug(f"Loaded {len(self._embedding_cache)} cached embeddings")
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")
                self._embedding_cache = {}

    def _save_embedding_cache(self):
        """Save embedding cache to disk."""
        try:
            self._cache_file.write_text(json.dumps(self._embedding_cache))
            logger.debug(f"Saved {len(self._embedding_cache)} cached embeddings")
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")

    def _generate_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding using Anthropic API or hash-based fallback with caching.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings for unchanged content

        Returns:
            Embedding vector
        """
        # Check cache first
        if use_cache:
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            if content_hash in self._embedding_cache:
                logger.debug(f"Using cached embedding for content hash: {content_hash[:8]}")
                return self._embedding_cache[content_hash]

        # Try to use real embeddings client
        embeddings_client = self._get_embeddings_client()
        if embeddings_client:
            try:
                embedding = embeddings_client.generate_embedding(text)
                # Cache the embedding
                if use_cache:
                    content_hash = hashlib.sha256(text.encode()).hexdigest()
                    self._embedding_cache[content_hash] = embedding
                    # Save cache periodically (every 10 new embeddings)
                    if len(self._embedding_cache) % 10 == 0:
                        self._save_embedding_cache()
                return embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding via API: {e}. Using fallback.")

        # Fallback to hash-based embedding
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i : i + 4]
            value = int.from_bytes(chunk, byteorder="big")
            normalized = (value / (2**32)) * 2 - 1
            embedding.append(normalized)

        # Pad to 768 dimensions
        while len(embedding) < 768:
            embedding.extend(embedding[: min(768 - len(embedding), len(embedding))])

        embedding = embedding[:768]

        # Cache hash-based embedding too
        if use_cache:
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            self._embedding_cache[content_hash] = embedding

        return embedding

    def index_spec(self, spec_path: Path, metadata: Dict[str, Any]) -> str:
        """Index a spec with embeddings and metadata."""
        if not spec_path.exists():
            raise FileNotFoundError(f"Spec not found: {spec_path}")

        content = spec_path.read_text()
        title = spec_path.stem.replace("_", " ").title()
        word_count = len(content.split())

        # Generate embedding
        embedding = self._generate_embedding(content)

        # Create spec ID
        spec_id = (
            f"{metadata['project']}_{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
        )

        # Store in ChromaDB
        self.collection.add(
            ids=[spec_id],
            embeddings=[embedding],
            documents=[content[:1000]],  # Store summary
            metadatas=[
                {
                    "project": metadata["project"],
                    "domain": metadata.get("domain", "general"),
                    "title": title,
                    "path": str(spec_path),
                }
            ],
        )

        # Store metadata in SQLite
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        now = datetime.now().isoformat()

        conn = _connect(self.metadata_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO specs
            (spec_id, title, project, domain, file_path, created_at, indexed_at, content_hash, word_count, key_concepts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                spec_id,
                title,
                metadata["project"],
                metadata.get("domain", "general"),
                str(spec_path),
                now,
                now,
                content_hash,
                word_count,
                json.dumps([]),  # Empty key concepts for now
            ),
        )
        conn.commit()
        conn.close()

        # Save embedding cache after indexing
        self._save_embedding_cache()

        return spec_id

    def index_text(
        self, text: str, title: str, project: str, domain: str = "general", doc_id: str = ""
    ) -> str:
        """Index arbitrary text content (no file required)."""
        word_count = len(text.split())
        embedding = self._generate_embedding(text)

        spec_id = (
            doc_id
            or f"{project}_{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        self.collection.upsert(
            ids=[spec_id],
            embeddings=[embedding],
            documents=[text[:1000]],
            metadatas=[{"project": project, "domain": domain, "title": title, "path": ""}],
        )

        content_hash = hashlib.sha256(text.encode()).hexdigest()
        now = datetime.now().isoformat()
        conn = _connect(self.metadata_db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """INSERT OR REPLACE INTO specs
               (spec_id, title, project, domain, file_path, created_at, indexed_at, content_hash, word_count, key_concepts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                spec_id,
                title,
                project,
                domain,
                "",
                now,
                now,
                content_hash,
                word_count,
                json.dumps([]),
            ),
        )
        conn.commit()
        conn.close()
        self._save_embedding_cache()
        return spec_id

    def find_similar(
        self,
        query_text: str,
        k: int = 5,
        project_filter: Optional[str] = None,
        use_hybrid_search: bool = True,
    ) -> List[SimilarWork]:
        """
        Find similar specs using embedding similarity with optional hybrid search.

        Args:
            query_text: Query text to search for
            k: Number of results to return
            project_filter: Optional project filter
            use_hybrid_search: Whether to use hybrid search (embeddings + metadata)

        Returns:
            List of SimilarWork objects ranked by relevance
        """
        query_embedding = self._generate_embedding(query_text, use_cache=False)

        # Query ChromaDB with embeddings
        where_filter = {"project": project_filter} if project_filter else None

        # Increase n_results for hybrid search to allow re-ranking
        n_results = k * 2 if use_hybrid_search else k

        results = self.collection.query(
            query_embeddings=[query_embedding], n_results=n_results, where=where_filter
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        # Build SimilarWork objects with hybrid scoring
        similar_work = []
        conn = _connect(self.metadata_db)
        cursor = conn.cursor()

        # Extract keywords from query for metadata matching
        query_keywords = set(query_text.lower().split())

        for i, spec_id in enumerate(results["ids"][0]):
            cursor.execute("SELECT * FROM specs WHERE spec_id = ?", (spec_id,))
            row = cursor.fetchone()

            if row:
                # row: spec_id, title, project, domain, file_path, created_at, indexed_at, content_hash, word_count, key_concepts
                key_concepts = json.loads(row[9]) if row[9] else []

                # Base similarity from embedding distance
                embedding_similarity = 1.0 - results["distances"][0][i]

                # Hybrid search: combine embedding similarity with metadata matching
                if use_hybrid_search:
                    # Boost if title matches query keywords
                    title_lower = row[1].lower()
                    title_matches = sum(1 for kw in query_keywords if kw in title_lower)
                    title_boost = min(title_matches * 0.1, 0.2)

                    # Boost if domain matches
                    domain_boost = 0.0
                    if row[3] and any(kw in row[3].lower() for kw in query_keywords):
                        domain_boost = 0.1

                    # Boost if project matches (if no filter)
                    project_boost = 0.0
                    if not project_filter and row[2]:
                        project_boost = 0.05

                    # Combine scores
                    final_similarity = min(
                        embedding_similarity + title_boost + domain_boost + project_boost,
                        1.0,
                    )
                else:
                    final_similarity = embedding_similarity

                similar_work.append(
                    SimilarWork(
                        id=row[0],
                        title=row[1],
                        type="spec",
                        similarity_score=final_similarity,
                        project=row[2],
                        summary=(results["documents"][0][i][:500] if results["documents"] else ""),
                        key_patterns=key_concepts[:5],  # First 5 concepts as patterns
                        lessons_learned=[],
                        reference_path=row[4],
                    )
                )

        conn.close()

        # Re-rank by final similarity score and return top k
        similar_work.sort(key=lambda x: x.similarity_score, reverse=True)
        return similar_work[:k]

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        conn = _connect(self.metadata_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT project), SUM(word_count) FROM specs")
        total, projects, words = cursor.fetchone()

        conn.close()

        return {
            "total_specs": total or 0,
            "total_projects": projects or 0,
            "total_words": words or 0,
            "storage_path": str(self.storage_path),
            "collection_count": self.collection.count(),
        }
