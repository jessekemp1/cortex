"""Tests for the rollover policy prompt loader and runtime hint."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

CORTEX_ROOT = Path(__file__).resolve().parent.parent
if str(CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT))


def _load_rollover_policy():
    """Import rollover_policy without going through prompts/__init__.py.

    The prompts package __init__ eagerly imports ab_testing which pulls in
    cortex.state_paths — too many deps for a focused unit test. This helper
    loads the module directly via importlib.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cortex_rollover_policy_test",
        CORTEX_ROOT / "prompts" / "rollover_policy.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_interaction_hint():
    """Extract get_contextual_hint + pattern list without executing the
    heavyweight imports at the top of interaction_capture.py.

    Both the module-level constant and the function must be compiled into
    one AST module so the function closes over the constant at exec time.
    """
    import ast

    src = (CORTEX_ROOT / "hooks" / "interaction_capture.py").read_text()
    tree = ast.parse(src)
    keep: list = []
    for node in tree.body:
        # The pattern tuple uses an annotated assignment (tuple[str, ...])
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_SELF_ROTATE_PATTERNS":
                keep.append(node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "_SELF_ROTATE_PATTERNS":
                keep.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "get_contextual_hint":
            keep.append(node)

    combined = ast.Module(body=keep, type_ignores=[])
    ast.fix_missing_locations(combined)
    ns: dict = {}
    exec(compile(combined, "interaction_capture_slice", "exec"), ns)
    return ns["get_contextual_hint"]


class TestRolloverPolicyLoader:
    def test_loads_from_claude_md(self):
        mod = _load_rollover_policy()
        assert "Cortex Agent Operating Policy" in mod.ROLLOVER_POLICY_TEXT, (
            "Policy should load from repo-root CLAUDE.md"
        )

    def test_full_policy_mentions_rollover_commands(self):
        mod = _load_rollover_policy()
        assert "/compact" in mod.ROLLOVER_POLICY_TEXT
        assert "/clear" in mod.ROLLOVER_POLICY_TEXT
        assert "fresh session" in mod.ROLLOVER_POLICY_TEXT

    def test_full_policy_mentions_handoff_yaml(self):
        mod = _load_rollover_policy()
        assert "handoff.yaml" in mod.ROLLOVER_POLICY_TEXT, (
            "Policy should direct agents to handoff.yaml, not progress.md"
        )

    def test_short_policy_fits_haiku_budget(self):
        mod = _load_rollover_policy()
        assert len(mod.ROLLOVER_POLICY_SHORT) < 500, (
            "Short policy must stay compact for haiku-tier prompts"
        )
        assert "/compact" in mod.ROLLOVER_POLICY_SHORT
        assert "/clear" in mod.ROLLOVER_POLICY_SHORT

    def test_fallback_when_claude_md_missing(self, tmp_path, monkeypatch):
        """If CLAUDE.md is unreadable, loader falls back to the inline string."""
        import importlib.util

        # Create a policy module whose _CLAUDE_MD points to a non-existent path
        policy_src = (CORTEX_ROOT / "prompts" / "rollover_policy.py").read_text()
        rewritten = policy_src.replace(
            'Path(__file__).resolve().parent.parent / "CLAUDE.md"',
            'Path("/nonexistent/CLAUDE.md")',
        )
        test_path = tmp_path / "rollover_policy.py"
        test_path.write_text(rewritten)

        spec = importlib.util.spec_from_file_location("fallback_test", test_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Fallback text should still contain the core policy signals
        assert "/compact" in mod.ROLLOVER_POLICY_TEXT
        assert "/clear" in mod.ROLLOVER_POLICY_TEXT
        assert "handoff.yaml" in mod.ROLLOVER_POLICY_TEXT


class TestContextualHint:
    @pytest.fixture
    def hint(self):
        return _load_interaction_hint()

    @pytest.mark.parametrize(
        "prompt,expect_hint",
        [
            ("go", False),
            ("", False),
            ("write the failing test", False),
            ("/clear please", True),
            ("recommend /compact or fresh session", True),
            ("Context at 90% now", True),
            ("Context is tight.", True),
            ("checkpointing before the next step", True),
            ("start a new session and /implement", True),
            ("open a new session for the next phase", True),
        ],
    )
    def test_pattern_detection(self, hint, prompt, expect_hint):
        out = hint({"prompt": prompt})
        assert bool(out) == expect_hint, f"Prompt {prompt!r} detection mismatch"

    def test_hint_body_references_claude_md(self, hint):
        out = hint({"prompt": "/clear now"})
        assert "CLAUDE.md" in out
        assert "handoff.yaml" in out

    def test_empty_hook_input(self, hint):
        assert hint({}) == ""

    def test_case_insensitive_matching(self, hint):
        assert hint({"prompt": "CONTEXT AT 85%"}) != ""
        assert hint({"prompt": "/CLEAR"}) != ""
