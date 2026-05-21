# Test Quality: Known Issues

Tracks weaknesses in the test suite. Items are removed once resolved.
`test_memory_roundtrip.py::test_known_issues_accuracy` enforces that the
"Resolved" claims below actually match code reality — if you mark something
resolved without fixing it, that test fails.

## Resolved

### `assert X in (True, False)` — RESOLVED 2026-05

Was: ~4 occurrences in `test_bridge_integration.py` asserting availability
flags were booleans. The pattern is trivially true and also accepts `0`/`1`.

Now: replaced with `assert isinstance(X, bool)` — rejects non-bool values,
which is the real invariant (the flags are set by try/except guards and must
never be `None`).

### `assert result is not None` as sole assertion — RESOLVED 2026-05

`test_known_issues_accuracy` scans every `test_integration_*.py` for test
functions whose only assertion is `assert X is not None`. The scan currently
reports zero — integration tests assert specific keys, types, or values.

## Standing policy

When adding new tests:

1. **Never** use `assert X is not None` as a sole assertion.
2. **Always** assert specific values: types, keys, ranges, or exact values.
3. For optional features (behind feature flags): use `@pytest.mark.skipif`.
4. For known-broken functionality: use `@pytest.mark.xfail(strict=True)` so
   the moment it's fixed, the suite tells you to remove the marker.
5. Memory-retrieval tests must include recall-accuracy assertions, not just
   "retrieval happened".

`test_assertion_quality.py` enforces a low trivial-assertion rate suite-wide.
See `tests/contract/` for the contract-test pattern (exact payload + response
shape, no weak assertions).
