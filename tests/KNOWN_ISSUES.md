# Test Quality: Known Issues

This document tracks known weaknesses in the test suite. All items here are
actively being fixed. PRs improving test quality are welcome.

## Weak Assertion Patterns

### `assert X in (True, False)`

**Where**: ~87 occurrences across 24 files, primarily in `test_bridge_integration.py`
and `test_phase1_integration.py`.

**What it tests**: Only that a variable is a boolean. Mathematically always true.

**Example**:
```python
# Before (proves nothing)
assert TIERED_MEMORY_AVAILABLE in (True, False)

# After (tests actual behavior)
assert TIERED_MEMORY_AVAILABLE is True
# or: skip the test if unavailable
@pytest.mark.skipif(not TIERED_MEMORY_AVAILABLE, reason="tiered memory not installed")
def test_tiered_memory_stores_and_retrieves():
    ...
```

**Status**: Fixed in `test_bridge_integration.py` and `test_tiered_memory.py`.
Remaining files tracked at: https://github.com/jessekemp1/cortex/issues (post-launch)

---

### `assert result is not None` as sole assertion

**Where**: ~30 occurrences across integration and unit tests.

**What it tests**: That a function returned *something*. Does not verify correctness.

**Example**:
```python
# Before (proves nothing useful)
result = bridge.get_context("task", project="my-project")
assert result is not None

# After (tests actual content)
result = bridge.get_context("task", project="my-project")
assert isinstance(result, dict)
assert "similar_work" in result
assert "recommendations" in result
```

**Status**: Being addressed test-by-test. Priority on high-value integration tests.

---

## Import Path Dependencies

Several test files rely on `sys.path` manipulation in `conftest.py` rather than
proper package imports. This works with `pip install -e .` but may fail in
some CI environments if paths are not set correctly.

**Mitigation**: Always run tests from the repo root after `pip install -e .`.

```bash
pip install -e .
pytest tests/ -v
```

---

## Tests Referencing Moved Files

After the v1.0 OSS restructuring (Feb 2026), some tests may reference files
that were moved to `scripts/internal/` or `examples/`. If you see an import
error for a file that no longer exists at the root, check those directories.

---

## Contributing Better Tests

When adding new tests:

1. **Never** use `assert X is not None` as a sole assertion.
2. **Always** assert specific values: types, keys, ranges, or exact values.
3. For optional features (behind feature flags): use `@pytest.mark.skipif`.
4. For known-broken functionality: use `@pytest.mark.xfail(reason="...")`.
5. Memory retrieval tests must include recall accuracy assertions (not just
   "retrieval happened").

See `tests/test_tiered_memory.py` for examples of well-structured tests.
