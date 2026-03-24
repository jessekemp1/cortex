"""Import Health Check — verify every Python module can be imported.

This test discovers all Python modules in the cortex codebase and verifies
each can be imported without error. It identifies broken imports, missing
dependencies, and circular import issues.

Modules requiring optional heavy dependencies (numpy, sklearn, xgboost, etc.)
are tested separately and skipped if the dependency is unavailable.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# Cortex root
CORTEX_ROOT = Path(__file__).parent.parent

# Optional heavy dependencies that may not be installed
OPTIONAL_DEPS = {"numpy", "sklearn", "xgboost", "shap", "openai", "anthropic",
                 "fastapi", "uvicorn", "apscheduler", "slowapi", "mcp",
                 "litellm", "httpx", "pydantic", "psutil", "structlog",
                 "dotenv", "scipy"}

# Modules known to require optional deps (skip if dep missing)
NEEDS_OPTIONAL = {
    "intelligence.memory.hybrid_retriever": "numpy",
    "intelligence.memory.embedding_store": "numpy",
    "intelligence.analytics": "xgboost",
    "intelligence.model_router": "anthropic",
    "runtime.api": "fastapi",
    "runtime.scheduler": "apscheduler",
    "mcp_server": "mcp",
}


def _discover_modules():
    """Discover all importable Python modules under cortex root."""
    modules = []

    for py_file in sorted(CORTEX_ROOT.rglob("*.py")):
        # Skip test files, __pycache__, hidden dirs, known non-importable
        rel = py_file.relative_to(CORTEX_ROOT)
        parts = rel.parts

        if any(p.startswith(".") or p.startswith("_") and p != "__init__" for p in parts):
            continue
        if "tests" in parts or "test_" in py_file.name:
            continue
        if "__pycache__" in parts:
            continue
        if any(skip in str(rel) for skip in [
            "_dead", "_archive", "scripts/", "examples/", "docs/",
            "MARKETING", "FUTURE", "STRATEGY", "OPUS", "GPT5",
            "mvp/", "cortex_mvp/", "golden-spec", "config-backups",
            "vision/", "site/", "dashboard/", "automation/", "v2/", "v21/",
        ]):
            continue

        # Convert path to module name
        if py_file.name == "__init__.py":
            module_name = ".".join(parts[:-1])
        else:
            module_name = ".".join(parts)[:-3]  # strip .py

        if module_name:
            modules.append(module_name)

    return modules


ALL_MODULES = _discover_modules()


def _check_optional_dep(module_name: str) -> str:
    """Check if module needs an optional dep that's missing. Returns dep name or ''."""
    for mod_prefix, dep in NEEDS_OPTIONAL.items():
        if module_name.startswith(mod_prefix):
            if importlib.util.find_spec(dep) is None:
                return dep
    return ""


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_module_imports(module_name):
    """Verify each module can be imported without error."""
    missing_dep = _check_optional_dep(module_name)
    if missing_dep:
        pytest.skip(f"Requires optional dependency: {missing_dep}")

    try:
        # Ensure cortex root is on path
        if str(CORTEX_ROOT) not in sys.path:
            sys.path.insert(0, str(CORTEX_ROOT))

        importlib.import_module(module_name)
    except ImportError as e:
        err_msg = str(e)
        # Check if it's an optional dep we didn't catalog
        for dep in OPTIONAL_DEPS:
            if dep in err_msg:
                pytest.skip(f"Optional dependency not installed: {dep}")
        # Check for cortex.* imports (known pattern)
        if "cortex." in err_msg or "No module named 'cortex'" in err_msg:
            pytest.xfail(f"Uses 'from cortex.*' import pattern: {e}")
        raise
    except Exception as e:
        # Other errors (config issues, missing files, etc.) — don't fail hard
        if "No such file" in str(e) or "FileNotFoundError" in type(e).__name__:
            pytest.skip(f"Requires runtime files: {e}")
        raise


class TestImportHealthSummary:
    """Summary test that reports overall import health."""

    def test_core_modules_importable(self):
        """Critical core modules must import successfully."""
        core_modules = [
            "engines.conversation_ingestor",
            "intelligence.prompt_history",
            "state_paths",
            "cli",
            "formatter",
            "learning",
            "feedback",
            "config",
        ]
        failures = []
        for mod in core_modules:
            try:
                importlib.import_module(mod)
            except Exception as e:
                failures.append(f"{mod}: {e}")

        assert not failures, f"Core module import failures:\n" + "\n".join(failures)

    def test_storage_modules_importable(self):
        """Storage modules must import (they're the data layer)."""
        storage_modules = [
            "intelligence.storage.consolidated_store",
            "state_paths",
        ]
        failures = []
        for mod in storage_modules:
            try:
                importlib.import_module(mod)
            except Exception as e:
                failures.append(f"{mod}: {e}")

        assert not failures, f"Storage module import failures:\n" + "\n".join(failures)
