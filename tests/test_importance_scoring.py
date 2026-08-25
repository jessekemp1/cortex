#!/usr/bin/env python3
"""Tests for the decision-store importance heuristic (P1 curation).

Pure, deterministic scoring — no model call, no I/O. A thin/template decision
must score below IMPORTANCE_FLOOR so recall can down-weight it; a rich decision
(context + alternatives + rationale) must score above it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.memory.importance import _importance_score, IMPORTANCE_FLOOR


def test_empty_decision_scores_low():
    # No context, no rationale, template-ish text → noise.
    score = _importance_score("test integration", "", "", "")
    assert score < IMPORTANCE_FLOOR


def test_template_test_row_scores_low():
    # The exact class of junk flooding the store (test_integration_001 etc.).
    score = _importance_score("Test data quality integration", "", "", "")
    assert score < IMPORTANCE_FLOOR


def test_rich_decision_scores_high():
    score = _importance_score(
        decision="Scope Slack draft untag-durability to auto-tagging-off to match the calibrated GDoc",
        context="Clio DC follow-up; the draft stated untag durability unconditionally but docs say auto-tagging-on re-tags live matches",
        alternatives="Leave unconditional wording; run full /calibrate skill twice instead of a focused pass",
        rationale="Durability only holds with auto-tagging off; conditioning it keeps the guarantee true and matches PM docs",
    )
    assert score >= IMPORTANCE_FLOOR


def test_deterministic():
    a = _importance_score("some decision text here that is reasonably long", "ctx", "alts", "why")
    b = _importance_score("some decision text here that is reasonably long", "ctx", "alts", "why")
    assert a == b


def test_score_bounds():
    # Always within 1..10 regardless of input.
    for args in [("", "", "", ""), ("x" * 5000, "y" * 5000, "z" * 5000, "w" * 5000)]:
        s = _importance_score(*args)
        assert 1 <= s <= 10


def test_short_decision_penalized():
    # Very short decision text with no supporting fields is low-signal.
    assert _importance_score("did the thing", "", "", "") < IMPORTANCE_FLOOR


def test_floor_env_override(monkeypatch):
    # IMPORTANCE_FLOOR is env-overridable; re-import picks it up.
    import importlib
    import intelligence.memory.importance as imp
    monkeypatch.setenv("CORTEX_IMPORTANCE_FLOOR", "5")
    importlib.reload(imp)
    try:
        assert imp.IMPORTANCE_FLOOR == 5
    finally:
        monkeypatch.delenv("CORTEX_IMPORTANCE_FLOOR", raising=False)
        importlib.reload(imp)
