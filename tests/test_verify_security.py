"""Live verification of all security controls — not a unit test but a smoke test.

Run with: python -m pytest tests/test_verify_security.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ============================================================================
# 1. Workflow condition evaluator — malicious inputs must be rejected
# ============================================================================

class TestConditionEvaluatorSecurity:
    """Verify eval() replacement blocks all code injection attempts."""

    @pytest.fixture
    def steps(self):
        return {
            "build": {"success": True, "exit_code": 0, "output": "ok"},
            "test": {"success": True, "exit_code": 0, "output": "pass"},
        }

    def _eval(self, condition, steps):
        from workflows.runner import WorkflowRunner
        return WorkflowRunner._safe_eval_condition(condition, steps)

    @pytest.mark.parametrize("attack", [
        '__import__("os").system("rm -rf /")',
        'eval("1+1")',
        'exec("import os")',
        'steps.build.__class__.__bases__',
        'lambda: True',
        '().__class__.__subclasses__()',
        'steps.build.success; import os',
        'True or __import__("os")',
        'steps.build.success and __import__("subprocess")',
        '1; exec("print(1)")',
        'steps["build"]["success"]',  # dict access not supported
    ])
    def test_malicious_condition_rejected(self, attack, steps):
        assert self._eval(attack, steps) is False

    def test_valid_truthy_allowed(self, steps):
        assert self._eval("steps.build.success", steps) is True

    def test_valid_equality_allowed(self, steps):
        assert self._eval("steps.build.exit_code == 0", steps) is True

    def test_valid_inequality_allowed(self, steps):
        assert self._eval("steps.test.success != False", steps) is True

    def test_valid_false_condition(self, steps):
        assert self._eval("steps.build.exit_code == 1", steps) is False


# ============================================================================
# 2. Dynamic agent AST validation — dangerous constructs must be blocked
# ============================================================================

class TestDynamicAgentSecurity:
    """Verify exec() sandbox blocks dangerous agent scripts."""

    @pytest.fixture(autouse=True)
    def _mock_deps(self):
        """Stub runtime dependencies so we can import the loader directly."""
        import importlib

        stubs = {}
        needed = [
            "structlog",
            "cortex", "cortex.runtime", "cortex.runtime.agents",
            "cortex.runtime.agents.base", "cortex.runtime.config",
            "cortex.runtime.models",
        ]
        for mod in needed:
            if mod not in sys.modules:
                m = MagicMock()
                # Give AgentMetadata a real-looking return
                if mod == "cortex.runtime.agents.base":
                    m.AgentMetadata = MagicMock

                    def _base_init(self, agent_id, name, description, **kw):
                        self.agent_id = agent_id
                        self.name = name
                        self.description = description

                    m.BaseAgent = type("BaseAgent", (), {
                        "__init__": _base_init,
                    })
                stubs[mod] = m
                sys.modules[mod] = m

        yield

        for mod in stubs:
            sys.modules.pop(mod, None)

    def _load_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "runtime.agents.loader",
            Path(__file__).parent.parent / "runtime" / "agents" / "loader.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _make_agent(self, code):
        mod = self._load_module()
        return mod.DynamicAgent(
            agent_id="test", name="test", description="test", script_code=code,
        )

    @pytest.mark.parametrize("name,code", [
        ("exec call", 'exec("import os")\ndef run(ctx): return {}'),
        ("eval call", 'def run(ctx): return eval("1+1")'),
        ("compile call", 'compile("x", "<s>", "exec")\ndef run(ctx): return {}'),
        ("dunder access", 'def run(ctx): return ctx.__class__.__bases__'),
        ("os import", 'import os\ndef run(ctx): return os.listdir(".")'),
        ("subprocess import", 'import subprocess\ndef run(ctx): return {}'),
        ("sys import", 'import sys\ndef run(ctx): return {}'),
        ("socket import", 'import socket\ndef run(ctx): return {}'),
    ])
    def test_dangerous_script_blocked(self, name, code):
        mod = self._load_module()
        with pytest.raises(mod.SecurityError):
            mod.DynamicAgent(
                agent_id="test", name="test", description="test", script_code=code,
            )

    @pytest.mark.parametrize("name,code", [
        ("json import", 'import json\ndef run(ctx): return {"ok": True}'),
        ("math import", 'import math\ndef run(ctx): return {"pi": math.pi}'),
        ("re import", 'import re\ndef run(ctx): return {"m": bool(re.match("a", "abc"))}'),
        ("no imports", 'def run(ctx): return {"result": len(ctx)}'),
    ])
    def test_safe_script_allowed(self, name, code):
        agent = self._make_agent(code)
        assert agent._compiled_run is not None


# ============================================================================
# 3. API auth enforcement — every protected endpoint must reject bad tokens
# ============================================================================

class TestAPIAuthEnforcement:
    """Verify bearer token auth works across all endpoint categories."""

    @pytest.fixture(autouse=True)
    def _setup_api(self, monkeypatch):
        """Import the API app with mocked bridge deps and a known API key."""
        pytest.importorskip("fastapi")
        monkeypatch.setenv("CORTEX_API_KEY", "test-secret-key-12345")

        # Temporarily inject stubs, import app, then restore
        needed = [
            "cortex", "cortex.bridge", "cortex.orchestration",
            "cortex.orchestration.anomaly_detector",
            "cortex.orchestration.database",
            "cortex.batch", "cortex.batch.batch_client",
            "cortex.batch.queue_manager",
        ]
        saved = {}
        for mod in needed:
            saved[mod] = sys.modules.get(mod)
            if mod not in sys.modules:
                sys.modules[mod] = MagicMock()

        from api.bridge_endpoint import app
        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        self.auth = {"Authorization": "Bearer test-secret-key-12345"}
        self.bad_auth = {"Authorization": "Bearer wrong-token"}

        yield

        # Restore sys.modules
        for mod, original in saved.items():
            if original is None:
                sys.modules.pop(mod, None)
            else:
                sys.modules[mod] = original

    # Health endpoints — no auth required
    @pytest.mark.parametrize("path", ["/", "/health", "/service-health"])
    def test_health_endpoints_open(self, path):
        r = self.client.get(path)
        assert r.status_code == 200

    # Protected endpoints — 401 without token
    @pytest.mark.parametrize("path", ["/status", "/batches", "/queue", "/recommendations"])
    def test_protected_requires_auth(self, path):
        r = self.client.get(path)
        assert r.status_code == 401

    # Wrong token — 401
    def test_wrong_token_rejected(self):
        r = self.client.get("/status", headers=self.bad_auth)
        assert r.status_code == 401

    # Correct token — not 401 (may 500 from mocked bridge, but auth passed)
    def test_correct_token_accepted(self):
        r = self.client.get("/status", headers=self.auth)
        assert r.status_code != 401

    # Input validation — limit bounds
    def test_limit_zero_rejected(self):
        r = self.client.get("/recommendations", params={"limit": 0}, headers=self.auth)
        assert r.status_code == 422

    def test_limit_too_large_rejected(self):
        r = self.client.get("/recommendations", params={"limit": 9999}, headers=self.auth)
        assert r.status_code == 422

    # Graph filter validation
    def test_unknown_filter_key_rejected(self):
        r = self.client.get(
            "/graph/query",
            params={"node_type": "spec", "filters": '{"evil_key": 1}'},
            headers=self.auth,
        )
        assert r.status_code == 422
        assert "evil_key" in r.json()["detail"]

    def test_invalid_json_filter_rejected(self):
        r = self.client.get(
            "/graph/query",
            params={"node_type": "spec", "filters": "not json"},
            headers=self.auth,
        )
        assert r.status_code == 422

    # Pydantic model validation
    def test_bad_priority_rejected(self):
        r = self.client.post(
            "/queue",
            json={"title": "test", "description": "test", "priority": "INVALID"},
            headers=self.auth,
        )
        assert r.status_code == 422

    def test_empty_title_rejected(self):
        r = self.client.post(
            "/queue",
            json={"title": "", "description": "test"},
            headers=self.auth,
        )
        assert r.status_code == 422

    def test_oversized_content_rejected(self):
        r = self.client.post(
            "/intelligence/query",
            json={"request": "x" * 10001},
            headers=self.auth,
        )
        assert r.status_code == 422


# ============================================================================
# 4. Shell=False verification — confirm no shell=True remains
# ============================================================================

class TestNoShellTrue:
    """Verify no production code uses shell=True."""

    def test_no_shell_true_in_production_code(self):
        """Scan all Python files for shell=True, excluding tests and scripts."""
        import ast

        root = Path(__file__).parent.parent
        skip_dirs = {"tests", "_dead", "_archive", "scripts", "docs", "examples",
                      "__pycache__", ".git", "cortexdbx", "reports"}

        violations = []
        for py_file in root.rglob("*.py"):
            rel = py_file.relative_to(root)
            if any(p in skip_dirs for p in rel.parts):
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.keyword):
                    if node.arg == "shell" and isinstance(node.value, ast.Constant):
                        if node.value.value is True:
                            violations.append(f"{rel}:{node.lineno}")

        assert violations == [], (
            f"Found shell=True in production code:\n" +
            "\n".join(f"  {v}" for v in violations)
        )

    def test_no_pickle_in_production_code(self):
        """Verify no pickle.load() in production code."""
        root = Path(__file__).parent.parent
        skip_dirs = {"tests", "_dead", "_archive", "scripts", "docs", "__pycache__", ".git"}

        violations = []
        for py_file in root.rglob("*.py"):
            rel = py_file.relative_to(root)
            if any(p in skip_dirs for p in rel.parts):
                continue
            content = py_file.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if "pickle.load" in line and not line.strip().startswith("#"):
                    violations.append(f"{rel}:{i}: {line.strip()}")

        assert violations == [], (
            f"Found pickle.load() in production code:\n" +
            "\n".join(f"  {v}" for v in violations)
        )

    def test_no_bare_eval_in_production_code(self):
        """Verify no eval() calls in production code (except noqa-marked)."""
        import ast

        root = Path(__file__).parent.parent
        skip_dirs = {"tests", "_dead", "_archive", "scripts", "docs", "__pycache__", ".git"}

        violations = []
        for py_file in root.rglob("*.py"):
            rel = py_file.relative_to(root)
            if any(p in skip_dirs for p in rel.parts):
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "eval":
                        violations.append(f"{rel}:{node.lineno}")

        assert violations == [], (
            f"Found eval() in production code:\n" +
            "\n".join(f"  {v}" for v in violations)
        )
