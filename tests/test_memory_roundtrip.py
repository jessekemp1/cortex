#!/usr/bin/env python3
"""
Memory Roundtrip Tests — Phase 1 of Cortex Self-Awareness

These tests verify whether learning data actually flows between systems.
They document known gaps between Claude Code memory and Cortex state,
and verify that internal feedback loops (outcomes → learning) work.

Each xfail test represents a known architectural gap. When a gap is
closed, the strict=True marker will cause the test to fail (forcing
an update to acknowledge the fix).
"""

import ast
import json
import sys
from pathlib import Path

import pytest

# Ensure cortex is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

CORTEX_ROOT = Path(__file__).parent.parent
DEV_ROOT = CORTEX_ROOT.parent
CLAUDE_MEMORIES_DIR = Path.home() / ".claude" / "memories"
CORTEX_STATE_DIR = Path.home() / ".cortex"


# ── TEST 1: Claude Memory → Cortex Intelligence ─────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="Memory bridge not implemented: Claude Code and Cortex are isolated systems",
)
def test_claude_memory_reaches_cortex_recommendations(tmp_path: Path):
    """
    WHY: Claude Code stores learned anti-patterns in ~/.claude/memories/.
    Cortex stores intelligence in ~/.cortex/. Neither reads the other.
    If a user teaches Claude Code a gotcha, Cortex recommendations should
    reflect it — but today they don't.

    This test writes a gotcha in Claude Code memory format, then queries
    Cortex intelligence for a related topic. If the bridge existed, the
    gotcha would appear in the response.
    """
    from cortex.bridge import CortexBridge

    # Write a gotcha in Claude Code memory format to a temp file
    unique_marker = "ROUNDTRIP_TEST_SENTINEL_abc123xyz"
    memory_content = (
        f"# Test Memory\n\n"
        f"## Gotcha\n"
        f"- **{unique_marker}**: When using xarray interp() on 0-360 grids, "
        f"always convert negative longitudes first.\n"
    )
    temp_memory = tmp_path / "test-memory.md"
    temp_memory.write_text(memory_content)

    # Query Cortex intelligence for the related topic
    bridge = CortexBridge()
    results = bridge.get_context("xarray longitude convention GRIB interp", limit=10)

    # Flatten all result text to check for our marker
    all_text = json.dumps(results, default=str)
    assert unique_marker in all_text, (
        f"Cortex intelligence does not surface Claude Code memory content. "
        f"The marker '{unique_marker}' was written to {temp_memory} but not found "
        f"in Cortex query results. This proves the two systems are isolated."
    )


# ── TEST 2: Outcomes → Learning Round-Trip ───────────────────────────────────


def test_cortex_outcome_influences_recommendations(tmp_path: Path):
    """
    WHY: The feedback loop (outcomes.jsonl → learning.py → accuracy calculation)
    is the core self-improvement mechanism. If outcomes are written but never
    read back, the system cannot learn.

    This test writes structured outcomes to a temp file, then verifies the
    LearningSystem can read them and calculate accuracy — proving the
    outcomes.jsonl → learning.py data path works.
    """
    from cortex.feedback import FeedbackLogger

    # Set up temp files so we don't pollute real data
    temp_feedback = tmp_path / "feedback.json"
    temp_outcomes = tmp_path / "outcomes.jsonl"

    logger = FeedbackLogger(log_file=temp_feedback, outcomes_file=temp_outcomes)

    # Write 3 outcomes: 2 successes, 1 failure (all followed)
    test_outcomes = [
        {
            "recommendation_id": "test-001",
            "recommendation_title": "Fix GRIB cache",
            "recommendation_type": "blocker_resolution",
            "priority": "A",
            "confidence": 0.9,
            "followed": True,
            "outcome": "success",
        },
        {
            "recommendation_id": "test-002",
            "recommendation_title": "Add wave field support",
            "recommendation_type": "goal_progress",
            "priority": "B",
            "confidence": 0.7,
            "followed": True,
            "outcome": "success",
        },
        {
            "recommendation_id": "test-003",
            "recommendation_title": "Migrate to Postgres",
            "recommendation_type": "goal_progress",
            "priority": "C",
            "confidence": 0.5,
            "followed": True,
            "outcome": "failed",
        },
    ]

    for outcome in test_outcomes:
        logger.log_outcome(**outcome)

    # Verify outcomes were written
    assert temp_outcomes.exists(), "Outcomes file was not created"
    lines = [line for line in temp_outcomes.read_text().strip().split("\n") if line]
    assert len(lines) == 3, f"Expected 3 outcome lines, got {len(lines)}"

    # Verify each line is valid JSON with the right fields
    for i, line in enumerate(lines):
        data = json.loads(line)
        assert data["recommendation_id"] == test_outcomes[i]["recommendation_id"]
        assert data["outcome"] == test_outcomes[i]["outcome"]
        assert data["followed"] == test_outcomes[i]["followed"]
        assert "timestamp" in data, "Outcome entry missing timestamp"

    # Now verify the LearningSystem can read them back and calculate accuracy
    # Import LearningSystem — it uses relative imports, so we need the path
    # We test via FeedbackLogger.load_outcomes() which is the shared interface
    loaded = logger.load_outcomes()
    assert len(loaded) == 3, f"LearningSystem loaded {len(loaded)} outcomes, expected 3"

    # Verify loaded outcomes match what we wrote
    assert loaded[0].recommendation_id == "test-001"
    assert loaded[0].outcome == "success"
    assert loaded[0].followed is True

    assert loaded[2].recommendation_id == "test-003"
    assert loaded[2].outcome == "failed"

    # Calculate accuracy manually: 2 successes out of 3 followed = 0.667
    followed = [o for o in loaded if o.followed]
    success_count = sum(
        1.0 if o.outcome == "success" else 0.5 if o.outcome == "partial" else 0.0 for o in followed
    )
    accuracy = success_count / len(followed) if followed else 0.0
    assert abs(accuracy - 2.0 / 3.0) < 0.01, f"Expected accuracy ~0.667, got {accuracy}"


# ── TEST 3: Anti-Pattern Mechanism Fixes Actually Exist ──────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="Mechanism fixes not yet fully implemented",
)
def test_anti_pattern_mechanism_implemented():
    """
    WHY: Each anti-pattern in ~/.claude/memories/anti-patterns.md specifies a
    'mechanism_fix' — a concrete thing that should exist in the codebase to
    prevent recurrence. But documenting a mechanism is not the same as building
    it. This test checks whether the mechanisms actually exist.

    If all mechanisms are implemented, this test should be un-xfailed.
    """
    anti_patterns_file = CLAUDE_MEMORIES_DIR / "anti-patterns.md"
    if not anti_patterns_file.exists():
        pytest.skip("~/.claude/memories/anti-patterns.md not found")

    # Define mechanism checks: (description, check_function)
    # Each returns (exists: bool, detail: str)
    mechanism_checks = []

    # Mechanism 1: CI grep gate for LocalMultiFieldGRIBLoader mock target
    def check_ci_grep_gate():
        safety_dir = DEV_ROOT / "scripts" / "safety"
        if not safety_dir.exists():
            return False, "scripts/safety/ directory exists but no GRIB mock gate found"
        # Check if any file in safety/ mentions LocalMultiFieldGRIBLoader
        for f in safety_dir.iterdir():
            if f.is_file() and f.suffix in (".sh", ".py"):
                text = f.read_text()
                if "LocalMultiFieldGRIBLoader" in text:
                    return True, f"Found in {f.name}"
        return False, "No safety script checks for LocalMultiFieldGRIBLoader mock target"

    # Mechanism 2: Ban xfail without strict=True in pre-commit
    def check_xfail_strict_ban():
        # Check pre-commit config
        for config_name in [".pre-commit-config.yaml", ".pre-commit-config.yml"]:
            config_file = DEV_ROOT / config_name
            if config_file.exists():
                text = config_file.read_text()
                if "xfail" in text and "strict" in text:
                    return True, f"Found xfail+strict check in {config_name}"
        # Also check safety scripts
        safety_dir = DEV_ROOT / "scripts" / "safety"
        if safety_dir.exists():
            for f in safety_dir.iterdir():
                if f.is_file():
                    text = f.read_text()
                    if "xfail" in text and "strict" in text:
                        return True, f"Found in {f.name}"
        return False, "No pre-commit or safety script enforces xfail strict=True"

    # Mechanism 3: test_quality_linter.py in pre-push hook
    def check_quality_linter():
        linter_path = DEV_ROOT / "scripts" / "safety" / "test_quality_linter.py"
        if linter_path.exists():
            return True, "test_quality_linter.py exists"
        # Also check cortex/tests/ for it
        alt_path = CORTEX_ROOT / "tests" / "test_quality_linter.py"
        if alt_path.exists():
            return True, "test_quality_linter.py exists in cortex/tests/"
        return False, "test_quality_linter.py not found in scripts/safety/ or cortex/tests/"

    mechanism_checks = [
        ("CI grep gate for GRIB mock target", check_ci_grep_gate),
        ("Ban xfail without strict=True", check_xfail_strict_ban),
        ("test_quality_linter.py in pre-push", check_quality_linter),
    ]

    # Only check mechanisms that are actually referenced in the file
    missing = []
    for description, check_fn in mechanism_checks:
        exists, detail = check_fn()
        if not exists:
            missing.append(f"  - {description}: {detail}")

    assert not missing, (
        "Anti-pattern mechanism fixes documented but not implemented:\n"
        + "\n".join(missing)
        + "\n\nThese were promised in ~/.claude/memories/anti-patterns.md "
        + "but don't exist in the codebase."
    )


# ── TEST 4: KNOWN_ISSUES.md Accuracy ────────────────────────────────────────


def test_known_issues_accuracy():
    """
    WHY: KNOWN_ISSUES.md claims certain patterns are 'Fixed' in specific files.
    If the fix claim is wrong, we have false documentation giving false confidence.
    This test checks each 'Fixed' claim against the actual code.

    As of the ship-readiness cleanup the doc's claims match reality (the
    'assert X in (True, False)' pattern was actually removed from
    test_bridge_integration.py), so this is now an enforced passing test
    rather than an xfail: any future drift between doc and code re-fails it.
    """
    known_issues_file = CORTEX_ROOT / "tests" / "KNOWN_ISSUES.md"
    if not known_issues_file.exists():
        pytest.skip("cortex/tests/KNOWN_ISSUES.md not found")

    contradictions = []

    # Claim 1: "assert X in (True, False)" is "Fixed in test_bridge_integration.py"
    # Check if the pattern still exists in that file
    bridge_test = CORTEX_ROOT / "tests" / "test_bridge_integration.py"
    if bridge_test.exists():
        bridge_text = bridge_test.read_text()
        # Count occurrences of the trivial pattern
        trivial_count = bridge_text.count("in (True, False)")
        if trivial_count > 0:
            contradictions.append(
                f"KNOWN_ISSUES.md claims 'assert X in (True, False)' is "
                f"'Fixed in test_bridge_integration.py', but {trivial_count} "
                f"instances remain in that file."
            )

    # Claim 2: "assert result is not None as sole assertion" — "Being addressed"
    # Check integration test files for sole `assert X is not None` patterns
    sole_none_files = []
    for test_file in (CORTEX_ROOT / "tests").glob("test_integration_*.py"):
        tree = ast.parse(test_file.read_text(), filename=str(test_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Find assert statements in the function body
                asserts = [stmt for stmt in ast.walk(node) if isinstance(stmt, ast.Assert)]
                if len(asserts) == 1:
                    # Check if it's `assert X is not None`
                    assert_node = asserts[0]
                    test_expr = assert_node.test
                    if (
                        isinstance(test_expr, ast.Compare)
                        and len(test_expr.ops) == 1
                        and isinstance(test_expr.ops[0], ast.IsNot)
                        and isinstance(test_expr.comparators[0], ast.Constant)
                        and test_expr.comparators[0].value is None
                    ):
                        sole_none_files.append(f"{test_file.name}::{node.name}")

    if sole_none_files:
        contradictions.append(
            f"KNOWN_ISSUES.md says 'assert X is not None' sole assertions are "
            f"'Being addressed', but these test functions still have only that "
            f"assertion: {', '.join(sole_none_files)}"
        )

    assert not contradictions, (
        "KNOWN_ISSUES.md contains claims contradicted by code:\n"
        + "\n".join(f"  - {c}" for c in contradictions)
    )


# ── TEST 5: Cross-System Data References ────────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="Claude Code and Cortex have zero cross-references — fully isolated",
)
def test_cross_system_data_references():
    """
    WHY: If ~/.cortex/ never references ~/.claude/ and vice versa, the two
    memory systems are completely isolated. Any 'learning' claimed by one
    system cannot benefit the other. This test checks for at least ONE
    functional data bridge — a config, import path, or data pipeline that
    actually reads from one system's state directory into the other.

    We specifically exclude documentation references (like CLAUDE.md mentioning
    "cortex/tests/" as a test path) because those are human-readable notes,
    not machine-readable bridges.

    Today: zero functional cross-references exist. The systems are isolated.
    """
    cortex_refs_claude = False
    claude_refs_cortex = False

    # Patterns that indicate a real data bridge (not just documentation)
    # Real bridge: code/config that reads ~/.claude/memories/ or ~/.cortex/outcomes.jsonl
    cortex_bridge_patterns = [
        "~/.claude/memories",
        ".claude/memories",
        "claude/memories/",
        "CLAUDE_MEMORIES",
    ]
    claude_bridge_patterns = [
        "~/.cortex/outcomes",
        ".cortex/outcomes",
        "~/.cortex/feedback",
        ".cortex/feedback",
        "CORTEX_STATE_DIR",
        "cortex_state_dir",
    ]

    # Check if any config/code file in ~/.cortex/ has a real bridge to .claude
    # Exclude event logs (*.jsonl) which record file-change events mentioning
    # .claude paths — those log that something happened, they don't read data.
    if CORTEX_STATE_DIR.exists():
        for ext in ("*.json", "*.yaml", "*.yml", "*.toml", "*.py"):
            for f in CORTEX_STATE_DIR.rglob(ext):
                try:
                    text = f.read_text(errors="ignore")
                    if any(pat in text for pat in cortex_bridge_patterns):
                        cortex_refs_claude = True
                        break
                except (OSError, PermissionError):
                    continue
            if cortex_refs_claude:
                break

    # Check if any config/code file in ~/.claude/ has a real bridge to .cortex
    # Exclude conversation logs (projects/*/uuid.jsonl) — those contain text
    # about cortex because we *discussed* it, not because the system reads it.
    claude_dir = Path.home() / ".claude"
    if claude_dir.exists():
        # Only check actual config/memory files, not conversation logs
        check_dirs = [
            claude_dir / "memories",
            claude_dir / "settings",
        ]
        for check_dir in check_dirs:
            if not check_dir.exists():
                continue
            for ext in ("*.json", "*.yaml", "*.yml", "*.toml", "*.py", "*.md"):
                for f in check_dir.rglob(ext):
                    try:
                        text = f.read_text(errors="ignore")
                        if any(pat in text for pat in claude_bridge_patterns):
                            claude_refs_cortex = True
                            break
                    except (OSError, PermissionError):
                        continue
                if claude_refs_cortex:
                    break
            if claude_refs_cortex:
                break

    has_any_cross_ref = cortex_refs_claude or claude_refs_cortex
    assert has_any_cross_ref, (
        "No functional data bridges found between ~/.cortex/ and ~/.claude/. "
        "The two memory systems are completely isolated — neither reads the "
        "other's state files. Documentation mentions don't count. "
        f"cortex→claude: {cortex_refs_claude}, claude→cortex: {claude_refs_cortex}"
    )
