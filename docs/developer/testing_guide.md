# Testing Guide

**How to write and run tests for Cortex**

This guide explains how to write, run, and maintain tests for Cortex.

---

## Running Tests

### Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_portfolio_memory.py -v

# Run specific test
pytest tests/test_portfolio_memory.py::test_get_stats -v

# Run with coverage
pytest tests/ --cov=cortex --cov-report=html
```

### Enterprise-Grade Tests

```bash
# Run enterprise-grade assessment
python test_enterprise_grade.py

# Expected: 15/15 tests pass (100%)
```

### E2E Tests

```bash
# Run E2E validation
python e2e_validation.py

# Expected: 9/9 tests pass
```

---

## Writing Tests

### Test Structure

```python
"""Test module for PortfolioMemory."""

import pytest
from cortex.portfolio_memory import PortfolioMemory


class TestPortfolioMemory:
    """Test suite for PortfolioMemory."""
    
    def test_get_stats(self):
        """Test get_stats method."""
        pm = PortfolioMemory()
        stats = pm.get_stats()
        
        assert "total_projects" in stats
        assert isinstance(stats["total_projects"], int)
        assert stats["total_projects"] >= 0
    
    def test_get_stats_with_health(self):
        """Test get_stats with health included."""
        pm = PortfolioMemory()
        stats = pm.get_stats(include_health=True)
        
        assert "health" in stats
        assert "healthy_count" in stats["health"]
```

### Test Naming

- **Test files**: `test_<module>.py`
- **Test classes**: `Test<ClassName>`
- **Test methods**: `test_<method_name>`

### Assertions

**Use descriptive assertions**:

```python
# Good
assert stats["total_projects"] >= 0, "Total projects should be non-negative"

# Better
assert "total_projects" in stats, "Stats should include total_projects"
assert isinstance(stats["total_projects"], int), "total_projects should be int"
```

---

## Mocking Strategies

### Mock External Dependencies

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency."""
    with patch('cortex.portfolio_memory.Path') as mock_path:
        mock_path.return_value.exists.return_value = True
        # Test code
```

### Mock File Operations

```python
from unittest.mock import mock_open, patch

def test_file_operations():
    """Test file operations with mock."""
    with patch("builtins.open", mock_open(read_data='{"key": "value"}')):
        # Test code
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest tests/ --cov=cortex
      - run: python test_enterprise_grade.py
```

---

## Test Best Practices

### 1. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Clean up after tests

### 2. Test Coverage

- Aim for >80% coverage
- Test error cases
- Test edge cases

### 3. Test Performance

- Keep tests fast (<1s each)
- Use mocks for slow operations
- Run tests in parallel when possible

---

## Next Steps

- [Developer Setup](setup.md) - Development environment
- [Test Results](../tests/TEST_RESULTS.md) - Test results
- [Contributing Guide](../CONTRIBUTING.md) - Contribution guidelines

---

**Version**: 1.0  
**Last Updated**: 2025-12-24

