# Troubleshooting Guide

**Common issues and solutions**

This guide helps you resolve common issues with Cortex.

---

## Common Issues

### "ModuleNotFoundError: No module named 'cortex'"

**Cause**: Cortex not installed or Python path incorrect

**Solution**:
```bash
# Install cortex
cd /Users/jesse.kemp/Dev/cortex
pip install -e .

# Or add to Python path
export PYTHONPATH="/Users/jesse.kemp/Dev/cortex:$PYTHONPATH"
```

---

### "Portfolio memory not available"

**Cause**: PortfolioMemory module not initialized

**Solution**:
```bash
# Initialize portfolio memory
python3 -c "from portfolio_memory import PortfolioMemory; PortfolioMemory()"

# Check data directory exists
ls -la ~/.claude/portfolio/
```

---

### "No projects found"

**Cause**: No projects in workspace or portfolio not indexed

**Solution**:
```bash
# Check workspace root
echo $CORTEX_ROOT  # or check config.yaml

# Verify projects exist
ls /Users/jesse.kemp/Dev/

# Projects should have .git directories or .claude/project.yaml files
```

---

### "Spec search returns no results"

**Cause**: Specs not indexed yet

**Solution**:
```bash
# Index specs
python bridge.py index-spec /path/to/spec.md --project ProjectName

# Or index entire project (programmatic)
python3 -c "
from intelligence.spec_knowledge_base import SpecKnowledgeBase
kb = SpecKnowledgeBase()
count = kb.index_project('/path/to/project', 'ProjectName')
print(f'Indexed {count} specs')
"
```

---

### "ANTHROPIC_API_KEY not set"

**Cause**: API key not configured (only needed for embeddings)

**Solution**:
```bash
# Set environment variable
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Or use without embeddings (metadata-only mode)
# Spec knowledge base will use hash-based search instead
```

---

### "chromadb not available"

**Cause**: ChromaDB not installed (optional dependency)

**Solution**:
```bash
# Install chromadb (optional)
pip install chromadb

# Or use without chromadb (hash-based search)
# Spec knowledge base will fall back to hash-based similarity
```

---

### "Session context slow (>500ms)"

**Cause**: Git operations variable based on repo size

**Solution**:
- Acceptable for v1.0, optimize in Month 1
- Use caching (default: 1 hour)
- Consider smaller git repositories

---

### "Permission denied" when accessing ~/.claude/

**Cause**: Insufficient permissions

**Solution**:
```bash
# Fix permissions
chmod -R 755 ~/.claude/

# Or run with appropriate permissions
```

---

### "JSON file corrupted"

**Cause**: Manual editing error

**Solution**:
```bash
# Validate JSON
python3 -m json.tool ~/.claude/portfolio/project_index.json

# Restore from backup if needed
cp ~/cortex_backups/cortex_YYYYMMDD.tar.gz ~/restore/
cd ~/restore/
tar -xzf cortex_YYYYMMDD.tar.gz
```

---

### "Metrics not recording"

**Cause**: Forgot to call tracker methods

**Solution**:
```python
# Track metrics after completing tasks
from metrics_tracker import MetricsTracker

tracker = MetricsTracker()
tracker.record_velocity(
    task="Implemented feature X",
    time_without_cortex=60,
    time_with_cortex=20,
    project="yourproject"
)
```

See [Best Practices](user_guide/best_practices.md) for workflow tips.

---

## Error Messages

### "Portfolio memory not available"

**Meaning**: PortfolioMemory module not initialized

**Solution**: Initialize portfolio memory (see above)

---

### "Project 'X' not found"

**Meaning**: Project not in portfolio

**Solution**: Register project in portfolio memory

---

### "SpecKnowledgeBase not available"

**Meaning**: Spec KB not initialized (chromadb missing)

**Solution**: Install chromadb or use without spec search

---

### "Session Manager not available"

**Meaning**: SessionManager not initialized

**Solution**: Check initialization in bridge.py

---

### "No session context available"

**Meaning**: No git repository detected

**Solution**: Run from git repository directory

---

## Debugging Tips

### Enable Debug Logging

```bash
# Enable debug logging
export CORTEX_DEBUG=1

# Run with verbose output
cortex status --verbose
```

### Check Installation

```bash
# Check Python version
python3 --version  # Should be 3.9+

# Check installed packages
pip list | grep cortex

# Check data directories
ls -la ~/.claude/
```

### Verify Dependencies

```bash
# Check core dependencies
python3 -c "import structlog, yaml, dotenv; print('Core dependencies OK')"

# Check optional dependencies
python3 -c "import chromadb; print('ChromaDB available')" 2>/dev/null || echo "ChromaDB not installed (optional)"
```

---

## Performance Issues

### Slow Operations

**If operations are slow**:
1. Check cache settings
2. Verify data directory permissions
3. Check disk space
4. Review performance benchmarks

### Memory Issues

**If memory usage is high**:
1. Check cache size limits
2. Clean old data
3. Review data structures

---

## Getting Help

### Check Documentation

1. [Installation Guide](INSTALLATION.md)
2. [User Guide](user_guide/getting_started.md)
3. [API Documentation](API.md)

### Report Issues

1. Check existing issues
2. Create new issue with:
   - Error message
   - Steps to reproduce
   - Environment details
   - Expected vs actual behavior

---

## References

- [Installation Guide](INSTALLATION.md)
- [User Guide](user_guide/getting_started.md)
- [API Documentation](API.md)
- [Best Practices](user_guide/best_practices.md)

---

**Version**: 1.0  
**Last Updated**: 2025-12-24

