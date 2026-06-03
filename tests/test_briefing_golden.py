"""Golden-file harness for briefing formatters.

This test is the safety net for the planned `briefing.py` split (see
docs/AUDIT_FINDINGS.md). It captures the byte-for-byte output of the three
public formatters — `format_briefing`, `format_compact`, `format_statusline`
— against a deterministic `BriefingData` fixture. Any refactor that
preserves behavior must keep these tests green; any refactor that changes
behavior must regenerate the goldens and explain the diff in the PR.

The fixture is constructed in-test (no disk reads, no env reads, no
network), so the goldens are reproducible on any machine and in CI.

Regenerating the goldens (intentional output changes only):

    UPDATE_GOLDENS=1 pytest tests/test_briefing_golden.py

This writes new files under tests/fixtures/briefing_golden/. Inspect the
diffs before committing.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from briefing import (
    BriefingData,
    format_briefing,
    format_compact,
    format_statusline,
)


# format_compact reads the CWD's git state via detect_resume_context() and
# detect_stale_items(). For a pure golden capture, neutralize those reads —
# we want to test the formatter, not the environment it happens to run in.
# (This patch is also what tests/test_compact_briefing.py uses, so the
# golden output here will match what that test exercises.)
@pytest.fixture(autouse=True)
def _isolate_briefing_environment():
    with (
        patch("briefing.detect_resume_context", return_value=None),
        patch("briefing.detect_stale_items", return_value=[]),
    ):
        yield


GOLDEN_DIR = Path(__file__).parent / "fixtures" / "briefing_golden"


def _make_fixture_briefing() -> BriefingData:
    """A deterministic BriefingData for golden capture.

    Pinned timestamp + no optional intelligence fields → output is a pure
    function of the formatter code. If the formatter starts pulling from
    disk or the network, this test will catch the leak (the output will
    vary across runs).
    """
    return BriefingData(
        active_projects=["alpha", "beta", "gamma"],
        recent_commits_24h=7,
        total_commits_7d=42,
        # NOTE: format_briefing reads blocker['blocker'] (not 'title'). Schema
        # discovered via the harness on first run — a free finding from the
        # golden-file approach. If the schema is ever cleaned up, regenerate.
        blockers=[
            {"project": "alpha", "blocker": "auth refactor", "severity": "high"},
            {"project": "beta", "blocker": "deploy pipeline", "severity": "medium"},
        ],
        priority_actions=[
            {
                "title": "Ship outcome_linker idempotency",
                "project": "alpha",
                "priority": "HIGH",
                "rationale": "Phase 1 deliverable; blocks downstream learning loop.",
            },
            {
                "title": "Wire MCP contract tests",
                "project": "beta",
                "priority": "NORMAL",
                "rationale": "15 of 18 MCP tools currently lack contract tests.",
            },
        ],
        patterns=[
            "deepseek/deepseek-chat now primary for research routes (was xai/grok-3-fast)",
            "qwen-turbo now primary for long_context (was xai/grok-3-fast)",
        ],
        waiting_on=["external review of API key pre-flight"],
        generated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        period="24h",
    )


def _normalize(text: str) -> str:
    """Strip non-deterministic surface details from formatter output.

    Even with a pinned generated_at, formatters may inject the current
    wall-clock date in headers. Normalize those so the golden compare is
    stable across runs.
    """
    # Strip "Mon Jan 01" style date headers
    text = re.sub(
        r"[A-Z][a-z]+ \d{1,2},? \d{4}",
        "<DATE>",
        text,
    )
    # Strip ISO timestamps
    text = re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]?\d{0,2}:?\d{0,2}",
        "<ISO>",
        text,
    )
    # Strip "Generated: ..." / "as of ..." floats
    text = re.sub(r"as of [^\n]+", "as of <DATE>", text)
    return text


def _load_golden(name: str, actual: str) -> tuple[str, str]:
    """Return (expected, actual_normalized) for assertion.

    Side effects:
      - When UPDATE_GOLDENS=1, writes the golden and pytest.skips (won't
        return; tests reuse the skip semantics).
      - When the golden doesn't exist yet, pytest.skips with a hint.

    Otherwise returns the (expected, actual_normalized) pair so the caller
    can `assert expected == actual` directly. That keeps the assertion in
    the test body where static quality scanners expect to find it.
    """
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path = GOLDEN_DIR / f"{name}.txt"

    actual_normalized = _normalize(actual)

    if os.environ.get("UPDATE_GOLDENS") == "1":
        golden_path.write_text(actual_normalized)
        pytest.skip(f"Updated golden file: {golden_path}")

    if not golden_path.exists():
        pytest.skip(
            f"Golden file does not exist yet: {golden_path}\n"
            f"Generate with: UPDATE_GOLDENS=1 pytest {__file__}"
        )

    return golden_path.read_text(), actual_normalized


def _diff(expected: str, actual: str, name: str) -> str:
    """Format a unified diff for golden-mismatch failure messages."""
    import difflib

    diff = "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"tests/fixtures/briefing_golden/{name}.txt",
            tofile="actual",
            lineterm="",
        )
    )
    return (
        f"Output drift in {name} formatter.\n"
        f"If this is intentional, regenerate with:\n"
        f"  UPDATE_GOLDENS=1 pytest tests/test_briefing_golden.py::test_{name}_golden\n"
        f"--- diff ---\n{diff}"
    )


def test_format_briefing_golden():
    """format_briefing output is byte-stable on the fixture (modulo timestamps)."""
    briefing = _make_fixture_briefing()
    output = format_briefing(briefing, use_color=False)
    expected, actual = _load_golden("format_briefing", output)
    assert actual == expected, _diff(expected, actual, "format_briefing")


def test_format_compact_golden():
    """format_compact output is byte-stable on the fixture (modulo timestamps)."""
    briefing = _make_fixture_briefing()
    output = format_compact(briefing, use_color=False)
    expected, actual = _load_golden("format_compact", output)
    assert actual == expected, _diff(expected, actual, "format_compact")


def test_format_statusline_golden():
    """format_statusline output is byte-stable on the fixture (modulo timestamps)."""
    briefing = _make_fixture_briefing()
    output = format_statusline(briefing, use_color=False)
    expected, actual = _load_golden("format_statusline", output)
    assert actual == expected, _diff(expected, actual, "format_statusline")


def test_fixture_is_deterministic():
    """The fixture itself produces identical output across two calls.

    If this test fails, the formatters read non-deterministic state
    (env, disk, network) — a refactor blocker.
    """
    briefing_1 = _make_fixture_briefing()
    briefing_2 = _make_fixture_briefing()

    out_1 = _normalize(format_compact(briefing_1, use_color=False))
    out_2 = _normalize(format_compact(briefing_2, use_color=False))

    assert out_1 == out_2, (
        "format_compact output is NOT deterministic on a fixed fixture. "
        "This blocks any briefing.py refactor — the formatters are reading "
        "non-fixture state. Identify and isolate the leak before splitting."
    )
