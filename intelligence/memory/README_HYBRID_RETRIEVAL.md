# Hybrid Retrieval System - Usage Guide

## Overview

The hybrid retrieval system combines BM25 (keyword-based) and embedding (semantic) search for improved pattern retrieval. It's particularly effective at finding patterns using synonyms or different terminology.

## Quick Start

### Basic Usage (Default)

```python
from intelligence.memory.pattern_memory import PatternMemory

# Initialize with hybrid retrieval enabled (default)
memory = PatternMemory()

# Search for patterns
patterns = memory.get_relevant_patterns("async database connection", limit=5)

for pattern in patterns:
    print(f"{pattern.title} - {pattern.relevance_score:.3f}")
```

### Configuring Alpha (BM25 vs Embedding Weight)

```python
# Favor BM25 (keyword matching) - good for exact terminology
memory = PatternMemory(use_hybrid_retrieval=True, hybrid_alpha=0.3)

# Equal weight (recommended default)
memory = PatternMemory(use_hybrid_retrieval=True, hybrid_alpha=0.5)

# Favor embeddings (semantic matching) - good for synonyms
memory = PatternMemory(use_hybrid_retrieval=True, hybrid_alpha=0.7)
```

### Disable Hybrid Retrieval

```python
# Use BM25 only (backward compatible)
memory = PatternMemory(use_hybrid_retrieval=False)
```

## Advanced Usage

### Direct HybridRetriever Usage

```python
from intelligence.embeddings_client import EmbeddingsClient
from intelligence.memory.hybrid_retriever import HybridRetriever
from intelligence.memory.pattern_indexer import PatternIndexer

# Load patterns
indexer = PatternIndexer("/path/to/projects")
patterns = indexer.load_patterns()

# Initialize retriever
embeddings_client = EmbeddingsClient()
retriever = HybridRetriever(patterns, embeddings_client)

# Search with different alpha values
bm25_results = retriever.search("async database", limit=5, alpha=0.0)
hybrid_results = retriever.search("async database", limit=5, alpha=0.5)
semantic_results = retriever.search("async database", limit=5, alpha=1.0)
```

### Cache Management

```python
# Get stats (includes cache info)
stats = retriever.get_stats()
print(f"Embeddings cached: {stats['embeddings_cached']}")
print(f"Cache directory: {stats['cache_dir']}")

# Invalidate cache (force regeneration)
retriever.invalidate_cache()
```

## When to Use Different Alpha Values

### Alpha = 0.0 (BM25 Only)
**Use when**:
- Query uses exact technical terms from patterns
- Keyword matching is sufficient
- Speed is critical (fastest mode)

**Example queries**:
- "fix database connection pool"
- "implement API rate limiting"
- "refactor error handling"

### Alpha = 0.5 (Hybrid - Recommended)
**Use when**:
- General-purpose search
- Balance between keyword and semantic matching
- Not sure which approach will work best

**Example queries**:
- "database connection issues"
- "API performance problems"
- "error handling patterns"

### Alpha = 1.0 (Embeddings Only)
**Use when**:
- Query uses synonyms or different terminology
- Natural language queries
- Cross-domain pattern matching

**Example queries**:
- "asynchronous database operations" (async = asynchronous)
- "concurrent task processing" (concurrent = parallel = async)
- "slow query optimization" (slow = performance)

## Performance Characteristics

### Search Latency

| Mode | First Search | Cached | Notes |
|------|-------------|---------|-------|
| BM25 only | <0.01ms | <0.01ms | Fastest |
| Embedding only | ~100ms* | 0.05ms | *First load generates embeddings |
| Hybrid | ~100ms* | 0.05ms | *First load generates embeddings |

### Memory Usage

| Patterns | Memory | Cache Size |
|----------|--------|------------|
| 100 | ~60KB | ~60KB |
| 1,000 | ~600KB | ~600KB |
| 10,000 | ~6MB | ~6MB |

## Troubleshooting

### "Embeddings not available" Warning

**Cause**: EmbeddingsClient initialization failed

**Solution**: Check that `ANTHROPIC_API_KEY` is set (optional - falls back to hash-based embeddings)

### Slow First Search

**Cause**: Generating embeddings for all patterns

**Solution**: This only happens once. Subsequent searches use cached embeddings.

### Cache Not Loading

**Cause**: Pattern IDs changed (reindexing occurred)

**Solution**: This is expected. Cache is regenerated automatically.

## Examples

### Finding Patterns with Synonyms

```python
memory = PatternMemory(hybrid_alpha=0.7)  # Favor embeddings

# These should all find similar patterns
patterns1 = memory.get_relevant_patterns("async database")
patterns2 = memory.get_relevant_patterns("asynchronous database")
patterns3 = memory.get_relevant_patterns("concurrent database")

# All queries return similar patterns due to semantic matching
```

### Cross-Project Pattern Discovery

```python
memory = PatternMemory()

# Find patterns from other projects
similar_work = memory.find_similar_solutions(
    task="implement rate limiting",
    current_project="MyProject",
    limit=5
)

for work in similar_work:
    print(f"{work.project}: {work.title}")
    print(f"Relevance: {work.relevance_score:.2%}")
```

### Monitoring Retrieval Quality

```python
memory = PatternMemory()

# Get statistics
stats = memory.get_stats()

print(f"Total patterns: {stats['total_patterns']}")
print(f"Hybrid retrieval: {stats['hybrid_retrieval']}")
print(f"Alpha setting: {stats['hybrid_alpha']}")

if 'hybrid_stats' in stats:
    hybrid_stats = stats['hybrid_stats']
    print(f"Embeddings available: {hybrid_stats['embeddings_available']}")
    print(f"Embeddings cached: {hybrid_stats['embeddings_cached']}")
```

## Best Practices

1. **Use default settings** (hybrid_alpha=0.5) for general-purpose search
2. **Experiment with alpha** if results seem off:
   - Lower alpha if missing exact keyword matches
   - Raise alpha if missing synonym/conceptual matches
3. **Let cache warm up** - first search may be slow while generating embeddings
4. **Monitor stats** to ensure embeddings are cached and available
5. **Reindex periodically** to keep patterns fresh

## See Also

- Implementation: `intelligence/memory/hybrid_retriever.py`
- Tests: `tests/test_hybrid_retriever.py`
- Demo: `demo_hybrid_retrieval.py`
- PRD: `docs/AI_ENGINEERING_IMPROVEMENTS_PRD.md` (Improvement 1)
