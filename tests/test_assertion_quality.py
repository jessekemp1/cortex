#!/usr/bin/env python3
"""
Assertion Quality Meta-Tests — Phase 1 of Cortex Self-Awareness

These tests scan the test suite itself, checking whether tests actually
test anything. A test that only asserts `isinstance(x, list)` or
`assert x is not None` proves nothing about correctness.

These are the enforcement mechanism for the anti-pattern documented in
~/.claude/memories/anti-patterns.md under "[Testing] Counting Test
Passes Without Measuring Test Quality".

Expected state today: FAIL. These tests document the gap between
"1,111 tests pass" and "1,111 tests prove something."
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Ensure cortex is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

CORTEX_TESTS_DIR = Path(__file__).parent


def _parse_test_functions(filepath: Path) -> List[ast.FunctionDef]:
    """Parse a Python file and return all test function AST nodes."""
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return []

    test_funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            test_funcs.append(node)
    return test_funcs


def _is_trivial_assertion(assert_node: ast.Assert) -> bool:
    """
    Classify an assertion as trivial if it only checks:
    - isinstance(x, SomeType)
    - x is not None (as sole assertion)
    - x in (True, False)
    - assert X (bare truthy check on a name/attribute, not a comparison)

    Returns True if the assertion is trivial.
    """
    test_expr = assert_node.test

    # Pattern: assert isinstance(x, Type)
    if isinstance(test_expr, ast.Call):
        if isinstance(test_expr.func, ast.Name) and test_expr.func.id == "isinstance":
            return True

    # Pattern: assert X is not None
    if isinstance(test_expr, ast.Compare):
        if (
            len(test_expr.ops) == 1
            and isinstance(test_expr.ops[0], ast.IsNot)
            and len(test_expr.comparators) == 1
            and isinstance(test_expr.comparators[0], ast.Constant)
            and test_expr.comparators[0].value is None
        ):
            return True

    # Pattern: assert X in (True, False)
    if isinstance(test_expr, ast.Compare):
        if (
            len(test_expr.ops) == 1
            and isinstance(test_expr.ops[0], ast.In)
            and len(test_expr.comparators) == 1
            and isinstance(test_expr.comparators[0], ast.Tuple)
        ):
            elts = test_expr.comparators[0].elts
            if (
                len(elts) == 2
                and all(isinstance(e, ast.Constant) for e in elts)
                and {e.value for e in elts} == {True, False}
            ):
                return True

    return False


def _classify_test_function(
    func: ast.FunctionDef,
) -> Tuple[int, int, bool]:
    """
    Classify a test function's assertions.

    Returns:
        (total_asserts, trivial_asserts, is_pass_only)
    """
    # Collect all assert statements in the function
    asserts = []
    has_pass_only = False

    # Check for pass-only body (after docstrings and if-guards)
    meaningful_stmts = []
    for stmt in func.body:
        # Skip docstrings
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        # Skip `if` guards that contain only pytest.skip
        if isinstance(stmt, ast.If):
            # If the body is just pytest.skip or pass, it's a guard
            continue
        meaningful_stmts.append(stmt)

    # Check if the only meaningful statement is `pass`
    if len(meaningful_stmts) == 1 and isinstance(meaningful_stmts[0], ast.Pass):
        has_pass_only = True
    elif len(meaningful_stmts) == 0:
        has_pass_only = True

    # Walk the entire function body for assert statements
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            asserts.append(node)

    trivial_count = sum(1 for a in asserts if _is_trivial_assertion(a))
    return len(asserts), trivial_count, has_pass_only


# ── TEST 1: No Trivial-Only Test Files ───────────────────────────────────────


def test_no_trivial_only_test_files():
    """
    WHY: A test file where >50% of test functions have ONLY trivial assertions
    gives false confidence. It inflates the test count without proving behavior.

    Trivial assertions: isinstance(), `is not None` (sole), `in (True, False)`.
    Behavioral assertions: specific values, key presence, method return checks.

    Today: FAILS for test_integration_learning.py (~85% trivial).
    """
    violations = []

    for test_file in sorted(CORTEX_TESTS_DIR.glob("test_*.py")):
        # Skip this file (meta-tests) and the roundtrip tests
        if test_file.name in (
            "test_assertion_quality.py",
            "test_memory_roundtrip.py",
        ):
            continue

        funcs = _parse_test_functions(test_file)
        if not funcs:
            continue

        trivial_only_count = 0
        for func in funcs:
            total_asserts, trivial_asserts, is_pass_only = _classify_test_function(func)

            # A function is "trivial-only" if ALL its assertions are trivial
            # or it has no assertions at all (just pass)
            if is_pass_only:
                trivial_only_count += 1
            elif total_asserts > 0 and trivial_asserts == total_asserts:
                trivial_only_count += 1

        trivial_ratio = trivial_only_count / len(funcs) if funcs else 0.0

        if trivial_ratio > 0.50:
            violations.append(
                f"  {test_file.name}: {trivial_only_count}/{len(funcs)} "
                f"({trivial_ratio:.0%}) test functions are trivial-only"
            )

    assert not violations, (
        "Test files with >50% trivial-only test functions:\n"
        + "\n".join(violations)
        + "\n\nThese files inflate test counts without proving behavior. "
        + "Replace trivial assertions with specific behavioral checks."
    )


# ── TEST 2: Integration Tests Have Behavioral Calls ──────────────────────────


def test_integration_tests_have_behavioral_calls():
    """
    WHY: Integration tests should exercise actual system behavior — calling
    methods like .get_context(), .learn(), .dispatch(), .query(). A test
    that only imports a class and checks `is not None` is not an integration
    test; it's an import test.

    Today: FAILS for test_integration_learning.py and
    test_integration_local_orchestrator.py.
    """
    # Behavioral method calls we expect to see in real integration tests
    behavioral_methods = {
        "get_context",
        "learn",
        "dispatch",
        "query",
        "get_learning_metrics",
        "calculate_recommendation_accuracy",
        "get_outcome_patterns",
        "log_outcome",
        "load_outcomes",
        "get_recommendations",
        "generate",
        "process",
        "execute",
        "run",
        "analyze",
        "evaluate",
        "predict",
        "search",
        "retrieve",
        "orchestrate",
        # Integration health/availability checks
        "is_available",
        "get_status",
        "check",
        "validate",
        "connect",
        # Domain-specific behavioral methods
        "recommend",
        "generate_alerts",
        "get_project_health",
        "get_active_alerts",
        "analyze_coverage_trend",
        "analyze_violation_trend",
    }

    violations = []

    # CLI integration tests shell out via subprocess — different integration pattern
    skip_files = {"test_cli_integration.py", "test_integration_simple.py"}

    for test_file in sorted(CORTEX_TESTS_DIR.glob("test_*integration*.py")):
        if test_file.name in skip_files:
            continue
        funcs = _parse_test_functions(test_file)
        if not funcs:
            continue

        has_behavioral_call = False
        for func in funcs:
            # Walk the function AST looking for method calls
            for node in ast.walk(func):
                if isinstance(node, ast.Call):
                    # Check for obj.method() calls
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in behavioral_methods:
                            has_behavioral_call = True
                            break
                    # Check for bare function calls like dispatch()
                    elif isinstance(node.func, ast.Name):
                        if node.func.id in behavioral_methods:
                            has_behavioral_call = True
                            break
            if has_behavioral_call:
                break

        if not has_behavioral_call:
            violations.append(
                f"  {test_file.name}: no test function calls a behavioral method "
                f"(expected at least one of: {', '.join(sorted(behavioral_methods)[:8])}...)"
            )

    assert not violations, (
        "Integration test files with no behavioral method calls:\n"
        + "\n".join(violations)
        + "\n\nThese files only test imports/instantiation, not integration behavior."
    )


# ── TEST 3: No Empty Test Bodies ─────────────────────────────────────────────


def test_no_empty_test_bodies():
    """
    WHY: A test function with zero assertions proves nothing. This includes
    both literal `pass`-only bodies AND functions that do setup + conditional
    guards but never assert anything (e.g., `if AVAILABLE: pass`).

    These are placeholders that get counted as passing tests, giving false
    confidence in test coverage.

    Today: FAILS for 2 functions in test_bridge_integration.py where the
    body is `bridge = CortexBridge(); if FLAG: pass` with no assertions.
    """
    assertionless_tests = []

    for test_file in sorted(CORTEX_TESTS_DIR.glob("test_*.py")):
        # Skip meta-test files
        if test_file.name in (
            "test_assertion_quality.py",
            "test_memory_roundtrip.py",
            "test_coverage_audit.py",  # informational audit — reports, not asserts
            "test_import_health.py",   # uses pytest.skip/xfail/raise as assertions
        ):
            continue

        funcs = _parse_test_functions(test_file)
        for func in funcs:
            # Count all assert statements anywhere in the function
            # (including inside if-blocks)
            assert_count = sum(1 for node in ast.walk(func) if isinstance(node, ast.Assert))
            # Also check for pytest.raises, pytest.warns (context managers that assert)
            has_pytest_assert = False
            for node in ast.walk(func):
                if isinstance(node, ast.Attribute) and node.attr in ("raises", "warns"):
                    has_pytest_assert = True
                    break

            if assert_count == 0 and not has_pytest_assert:
                assertionless_tests.append(f"  {test_file.name}::{func.name}")

    assert not assertionless_tests, (
        "Test functions with zero assertions:\n"
        + "\n".join(assertionless_tests)
        + "\n\nThese are placeholders, not tests. They pass without proving "
        + "anything. Either add meaningful assertions or delete them."
    )
