# ~/Dev/cortex/spec_knowledge_base.py

import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

class SpecKnowledgeBase:
    """
    Indexed specification knowledge base with semantic search

    Features:
    - Index all markdown specs across projects
    - Semantic similarity search (hash-based, upgradable to embeddings)
    - Version tracking
    - Related spec discovery
    """

    def __init__(self, storage_path: str = "~/.claude/specs"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.index_path = self.storage_path / "index.json"
        self.specs = self._load_index()

    def _load_index(self) -> Dict:
        """Load spec index from disk"""
        if self.index_path.exists():
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {}

    def _save_index(self):
        """Save spec index to disk"""
        with open(self.index_path, 'w') as f:
            json.dump(self.specs, f, indent=2, default=str)

    def index_spec(
        self,
        spec_path: str,
        project: str,
        force: bool = False
    ) -> bool:
        """
        Index a single spec file

        Args:
            spec_path: Path to spec markdown file
            project: Project name
            force: Re-index even if already indexed

        Returns:
            True if indexed, False if skipped
        """
        path = Path(spec_path)

        if not path.exists():
            return False

        # Generate spec ID
        spec_id = self._generate_spec_id(spec_path, project)

        # Skip if already indexed (unless force)
        if not force and spec_id in self.specs:
            # Check if file modified
            current_mtime = path.stat().st_mtime
            if self.specs[spec_id]['mtime'] >= current_mtime:
                return False

        # Read spec content
        with open(path, 'r') as f:
            content = f.read()

        # Extract metadata
        metadata = self._extract_metadata(content)

        # Generate content hash for similarity
        content_hash = self._hash_content(content)

        # Store spec
        self.specs[spec_id] = {
            'id': spec_id,
            'path': str(path),
            'project': project,
            'name': path.stem,
            'content': content,
            'metadata': metadata,
            'content_hash': content_hash,
            'mtime': path.stat().st_mtime,
            'indexed_at': datetime.now().isoformat()
        }

        self._save_index()
        return True

    def index_project(self, project_path: str, project_name: str = None) -> int:
        """
        Index all specs in a project

        Args:
            project_path: Path to project root
            project_name: Project name (default: directory name)

        Returns:
            Number of specs indexed
        """
        path = Path(project_path)
        project_name = project_name or path.name

        # Find all markdown files
        spec_files = list(path.rglob("*.md"))

        indexed_count = 0
        for spec_file in spec_files:
            if self.index_spec(str(spec_file), project_name):
                indexed_count += 1

        return indexed_count

    def search(
        self,
        query: str,
        project: str = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for similar specs

        Args:
            query: Search query
            project: Filter by project (optional)
            limit: Max results

        Returns:
            List of matching specs with similarity scores
        """
        # Generate query hash
        query_hash = self._hash_content(query)

        # Calculate similarity to all specs
        results = []
        for spec in self.specs.values():
            # Filter by project if specified
            if project and spec['project'] != project:
                continue

            # Calculate similarity (simple hash-based for now)
            similarity = self._calculate_similarity(query_hash, spec['content_hash'])

            results.append({
                'spec_id': spec['id'],
                'spec_name': spec['name'],
                'project': spec['project'],
                'similarity': similarity,
                'path': spec['path'],
                'summary': self._extract_summary(spec['content'])
            })

        # Sort by similarity
        results.sort(key=lambda x: x['similarity'], reverse=True)

        return results[:limit]

    def get_spec(self, spec_id: str) -> Optional[Dict]:
        """Get spec by ID"""
        return self.specs.get(spec_id)

    def count(self) -> int:
        """Get total number of indexed specs"""
        return len(self.specs)

    def list_projects(self) -> List[str]:
        """List all projects with indexed specs"""
        projects = set(spec['project'] for spec in self.specs.values())
        return sorted(projects)

    # === Helper Methods ===

    def _generate_spec_id(self, spec_path: str, project: str) -> str:
        """Generate unique spec ID"""
        path = Path(spec_path)
        return f"{project}:{path.stem}"

    def _hash_content(self, content: str) -> str:
        """Generate content hash for similarity"""
        # Simple word-based hash (upgrade to embeddings later)
        words = content.lower().split()
        # Use 3-grams for better matching
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
        combined = '|'.join(sorted(set(trigrams)))
        return hashlib.md5(combined.encode()).hexdigest()

    def _calculate_similarity(self, hash1: str, hash2: str) -> float:
        """
        Calculate similarity between content hashes

        NOTE: This is a placeholder. Upgrade to embeddings for better similarity.
        """
        # Simple hash match (0 or 1)
        # In production, use cosine similarity of embeddings
        if hash1 == hash2:
            return 1.0
        else:
            # Hamming distance of hashes (rough approximation)
            distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
            return 1.0 - (distance / len(hash1))

    def _extract_metadata(self, content: str) -> Dict:
        """Extract metadata from spec content"""
        metadata = {}

        # Look for common metadata patterns
        lines = content.split('\n')

        for line in lines[:20]:  # Check first 20 lines
            if line.startswith('**Status**:'):
                metadata['status'] = line.split(':', 1)[1].strip()
            elif line.startswith('**Priority**:'):
                metadata['priority'] = line.split(':', 1)[1].strip()
            elif line.startswith('**Domain**:'):
                metadata['domain'] = line.split(':', 1)[1].strip()

        return metadata

    def _extract_summary(self, content: str, max_length: int = 200) -> str:
        """Extract summary from spec content"""
        # Find first paragraph after title
        lines = content.split('\n')

        in_paragraph = False
        summary_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip title lines
            if stripped.startswith('#'):
                continue

            # Start collecting after first non-empty line
            if stripped:
                summary_lines.append(stripped)

            # Stop after first paragraph
            if len(summary_lines) > 0 and not stripped:
                break

        summary = ' '.join(summary_lines)

        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary
