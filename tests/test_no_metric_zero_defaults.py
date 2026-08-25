"""Guard: no metric may be read with a numeric default on the briefing path.

`.get("commits", 0)` and `.get("score", 100)` are the idiom that let a failed
lookup reach a threshold comparison. One invented a MEDIUM "No commits in
analysis period" alert that ran for a month against a live workspace; the other
silently suppressed a HIGH health alert. Both are unrecoverable at the read site,
because by then absent and measured are the same value.

Read metrics through metric_result.is_available / require instead, or index the
producer's dict directly so a shape change raises.

Parsed with `ast`, not regex over lines: the modules being guarded quote the
banned idiom verbatim in their own comments and docstrings explaining it, and a
line-based matcher flags those.

ALLOWLIST is empty on purpose. If a case is genuinely legitimate, add it with a
comment arguing why, so the exception gets reviewed rather than assumed.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

GUARDED_FILES = ["portfolio_memory.py", "recommendations.py", "mcp_handlers.py"]

METRICS = {"commits", "score", "count", "total", "uncommitted", "total_score"}

ALLOWLIST: set[tuple[str, int]] = set()


def _offenders(source: str, filename: str) -> list[str]:
    """(file:line) for every `<x>.get("<metric>", <number>)` in real code."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        if len(node.args) != 2:
            continue
        key, default = node.args
        if not (isinstance(key, ast.Constant) and key.value in METRICS):
            continue
        # Only a numeric default is dangerous: it survives a threshold compare.
        if isinstance(default, ast.Constant) and isinstance(default.value, (int, float)):
            if isinstance(default.value, bool):
                continue
            if (filename, node.lineno) in ALLOWLIST:
                continue
            found.append(f"{filename}:{node.lineno}: .get(\"{key.value}\", {default.value})")
    return found


def test_no_metric_read_uses_a_numeric_default():
    offenders = []
    for name in GUARDED_FILES:
        path = REPO / name
        if path.exists():
            offenders += _offenders(path.read_text(), name)

    assert not offenders, (
        "Metric read with a numeric default — use metric_result.is_available/require "
        "or index the producer dict so a missing key raises:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_actually_matches_the_old_idiom():
    """A guard that cannot fail is not a guard."""
    assert _offenders('if overall.get("commits", 0) == 0: pass', "x.py")
    assert _offenders("x = overall.get('score', 100)", "x.py")
    assert _offenders('y = dep_health.get("total_score", 100)', "x.py")


def test_the_guard_ignores_safe_and_non_code_forms():
    # Non-numeric defaults are fine: no threshold acts on them.
    assert not _offenders('n = cfg.get("name", "unknown")', "x.py")
    assert not _offenders('c = d.get("concerns", [])', "x.py")
    # No default at all is the safe form.
    assert not _offenders('v = overall.get("commits")', "x.py")
    # A non-metric key with a numeric default is out of scope.
    assert not _offenders('r = cfg.get("retries", 3)', "x.py")
    # Comments and docstrings quoting the idiom must not trip it.
    assert not _offenders('"""explains overall.get("commits", 0) here"""', "x.py")
    assert not _offenders('# overall.get("commits", 0) was the bug', "x.py")
