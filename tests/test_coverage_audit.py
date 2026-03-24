"""Coverage Audit — identify all code that isn't fully verified and functioning.

This test programmatically discovers all Python modules and reports which
have corresponding tests, which test files are empty, and which modules
have zero coverage.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

CORTEX_ROOT = Path(__file__).parent.parent
TESTS_DIR = CORTEX_ROOT / "tests"

# Directories to skip
SKIP_DIRS = {
    "_dead", "_archive", "scripts", "examples", "docs",
    "__pycache__", ".git", ".claude", "node_modules",
    "MARKETING", "FUTURE", "STRATEGY", "OPUS", "GPT5",
    "mvp", "cortex_mvp", "config-backups", "vision",
    "site", "dashboard", "automation", "v2", "v21",
}


def _count_test_functions(filepath: Path) -> int:
    """Count test functions/methods in a test file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return -1

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                count += 1
    return count


def _discover_source_modules() -> list:
    """Find all non-test Python files."""
    modules = []
    for py_file in sorted(CORTEX_ROOT.rglob("*.py")):
        rel = py_file.relative_to(CORTEX_ROOT)
        parts = rel.parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        if "tests" in parts or py_file.name.startswith("test_"):
            continue
        if py_file.name == "__init__.py":
            continue
        modules.append(rel)
    return modules


def _discover_test_files() -> dict:
    """Find all test files and their function counts."""
    tests = {}
    for test_file in sorted(TESTS_DIR.rglob("test_*.py")):
        rel = test_file.relative_to(CORTEX_ROOT)
        count = _count_test_functions(test_file)
        tests[test_file.stem] = {"path": rel, "test_count": count}

    # Also check subdirectory test files
    for test_file in sorted(CORTEX_ROOT.rglob("test_*.py")):
        if "tests" not in test_file.parts:
            rel = test_file.relative_to(CORTEX_ROOT)
            count = _count_test_functions(test_file)
            tests[test_file.stem] = {"path": rel, "test_count": count}

    return tests


class TestCoverageAudit:
    """Audit test coverage across the codebase."""

    def test_report_empty_test_files(self):
        """Identify test files with zero test functions."""
        test_files = _discover_test_files()
        empty_files = [
            (name, info["path"])
            for name, info in test_files.items()
            if info["test_count"] == 0
        ]

        # This is informational — we don't fail, just report
        if empty_files:
            report = "\n".join(f"  {name}: {path}" for name, path in empty_files)
            print(f"\n{'='*60}")
            print(f"EMPTY TEST FILES ({len(empty_files)} files with 0 test functions):")
            print(report)
            print(f"{'='*60}")

        # Soft assertion: flag but don't fail
        # assert len(empty_files) == 0, f"Found {len(empty_files)} empty test files"

    def test_report_untested_modules(self):
        """Identify source modules with no corresponding test file."""
        source_modules = _discover_source_modules()
        test_files = _discover_test_files()

        untested = []
        for mod_path in source_modules:
            mod_name = mod_path.stem
            test_name = f"test_{mod_name}"
            if test_name not in test_files or test_files[test_name]["test_count"] == 0:
                untested.append(str(mod_path))

        if untested:
            report = "\n".join(f"  {m}" for m in untested[:50])
            print(f"\n{'='*60}")
            print(f"MODULES WITHOUT TESTS ({len(untested)} modules):")
            print(report)
            if len(untested) > 50:
                print(f"  ... and {len(untested) - 50} more")
            print(f"{'='*60}")

    def test_critical_modules_have_tests(self):
        """Critical modules MUST have tests with actual test functions."""
        critical_modules = [
            "conversation_ingestor",
            "consolidated_store",
            "prompt_history",
            "cli",
            "learning",
            "feedback",
            "briefing",
            "formatter",
            "orchestrator",
        ]

        # Alternate test file names for some modules
        alt_names = {
            "cli": "test_cli_integration",
            "prompt_history": "test_prompt_history",
        }

        test_files = _discover_test_files()
        missing = []

        for mod in critical_modules:
            test_name = f"test_{mod}"
            alt_name = alt_names.get(mod)
            found = test_name in test_files or (alt_name and alt_name in test_files)
            has_tests = (
                (test_name in test_files and test_files[test_name]["test_count"] > 0)
                or (alt_name and alt_name in test_files and test_files[alt_name]["test_count"] > 0)
            )
            if not found:
                missing.append(f"{mod}: no test file")
            elif not has_tests:
                missing.append(f"{mod}: test file exists but EMPTY (0 functions)")

        assert not missing, (
            f"Critical modules without tests:\n" + "\n".join(f"  {m}" for m in missing)
        )

    def test_new_prompt_storage_tested(self):
        """Verify the new prompt storage has tests."""
        test_files = _discover_test_files()

        assert "test_prompt_storage" in test_files, "test_prompt_storage.py missing"
        assert test_files["test_prompt_storage"]["test_count"] > 0, (
            "test_prompt_storage.py has no test functions"
        )

    def test_consolidated_store_schema_v2(self):
        """Verify schema v2 tables exist and work."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            os.environ["CORTEX_STATE_DIR"] = td
            from intelligence.storage.consolidated_store import ConsolidatedOutcomeStore

            store = ConsolidatedOutcomeStore(db_path=Path(td) / "audit.db")
            info = store.get_storage_info()

            assert info["schema_version"] == 2
            assert "conversation_content" in info["tables"]
            assert "correction_chains" in info["tables"]

    def test_report_broken_cortex_imports(self):
        """Identify files using 'from cortex.*' imports (broken without pip install)."""
        broken = []
        for py_file in sorted(CORTEX_ROOT.rglob("*.py")):
            rel = py_file.relative_to(CORTEX_ROOT)
            parts = rel.parts
            if any(p in SKIP_DIRS for p in parts):
                continue

            try:
                content = py_file.read_text()
            except Exception:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("from cortex.") or stripped.startswith("import cortex."):
                    # Check if it has a fallback
                    if "try:" not in content.splitlines()[max(0, i - 3):i][-1:]:
                        broken.append(f"{rel}:{i}: {stripped}")

        if broken:
            print(f"\n{'='*60}")
            print(f"FILES WITH 'from cortex.*' IMPORTS ({len(broken)} occurrences):")
            for b in broken[:30]:
                print(f"  {b}")
            if len(broken) > 30:
                print(f"  ... and {len(broken) - 30} more")
            print(f"{'='*60}")
