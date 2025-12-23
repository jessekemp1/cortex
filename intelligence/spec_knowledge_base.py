"""Spec Knowledge Base - Semantic similarity search over indexed specs."""

import hashlib
import json
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


class SpecKnowledgeBase:
    """Index and search specs using embeddings + SQLite."""

    def __init__(self, storage_path: Path = Path.home() / ".claude" / "specs"):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb not available - run: pip install chromadb")

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=str(storage_path / "embeddings"))
        self.collection = self.chroma_client.get_or_create_collection(
            name="specs",
            metadata={"hnsw:space": "cosine"}
        )

        # Initialize SQLite for metadata
        self.metadata_db = storage_path / "learnings.db"
        self._init_metadata_db()

    def _init_metadata_db(self):
        """Initialize SQLite database for spec metadata."""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        cursor.execute("""
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
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_project ON specs(project)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain ON specs(domain)")
        conn.commit()
        conn.close()

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate hash-based pseudo-embedding (fallback until real embeddings available)."""
        # Simple hash-based embedding as placeholder
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()

        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i:i+4]
            value = int.from_bytes(chunk, byteorder='big')
            normalized = (value / (2**32)) * 2 - 1
            embedding.append(normalized)

        # Pad to 768 dimensions
        while len(embedding) < 768:
            embedding.extend(embedding[:min(768 - len(embedding), len(embedding))])

        return embedding[:768]

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
        spec_id = f"{metadata['project']}_{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

        # Store in ChromaDB
        self.collection.add(
            ids=[spec_id],
            embeddings=[embedding],
            documents=[content[:1000]],  # Store summary
            metadatas=[{
                "project": metadata["project"],
                "domain": metadata.get("domain", "general"),
                "title": title,
                "path": str(spec_path)
            }]
        )

        # Store metadata in SQLite
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO specs
            (spec_id, title, project, domain, file_path, created_at, indexed_at, content_hash, word_count, key_concepts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            spec_id,
            title,
            metadata["project"],
            metadata.get("domain", "general"),
            str(spec_path),
            now,
            now,
            content_hash,
            word_count,
            json.dumps([])  # Empty key concepts for now
        ))
        conn.commit()
        conn.close()

        return spec_id

    def find_similar(self, query_text: str, k: int = 5,
                    project_filter: Optional[str] = None) -> List[SimilarWork]:
        """Find similar specs using embedding similarity."""
        query_embedding = self._generate_embedding(query_text)

        # Query ChromaDB
        where_filter = {"project": project_filter} if project_filter else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        # Build SimilarWork objects
        similar_work = []
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        for i, spec_id in enumerate(results["ids"][0]):
            cursor.execute("SELECT * FROM specs WHERE spec_id = ?", (spec_id,))
            row = cursor.fetchone()

            if row:
                # row: spec_id, title, project, domain, file_path, created_at, indexed_at, content_hash, word_count, key_concepts
                key_concepts = json.loads(row[9]) if row[9] else []
                similar_work.append(SimilarWork(
                    id=row[0],
                    title=row[1],
                    type="spec",
                    similarity_score=1.0 - results["distances"][0][i],  # Convert distance to similarity
                    project=row[2],
                    summary=results["documents"][0][i][:500] if results["documents"] else "",
                    key_patterns=key_concepts[:5],  # First 5 concepts as patterns
                    lessons_learned=[],
                    reference_path=row[4]
                ))

        conn.close()
        return similar_work

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT project), SUM(word_count) FROM specs")
        total, projects, words = cursor.fetchone()

        conn.close()

        return {
            "total_specs": total or 0,
            "total_projects": projects or 0,
            "total_words": words or 0,
            "storage_path": str(self.storage_path),
            "collection_count": self.collection.count()
        }
