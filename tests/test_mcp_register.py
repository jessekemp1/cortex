"""A3: MCP auto-registration with graceful fallback.

The registration path must never fail the setup when the `claude` CLI is
absent — it prints the exact manual copy-paste block and exits 0. These tests
force CORTEX_CLAUDE_BIN="" so they never touch the real ~/.claude.json.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import setup_ops
from cli.commands.v2_ops import cmd_mcp_register


@pytest.fixture(autouse=True)
def no_claude(monkeypatch):
    monkeypatch.setenv("CORTEX_CLAUDE_BIN", "")  # claude not installed


def test_claude_bin_override_empty_is_none():
    assert setup_ops.claude_bin() is None


def test_registration_entry_shape():
    entry = setup_ops.mcp_registration_entry("user")
    assert entry["name"] == "cortex"
    assert entry["scope"] == "user"
    assert entry["manual"].startswith("claude mcp add cortex -s user")


def test_mcp_is_registered_reports_unavailable_without_cli():
    status = setup_ops.mcp_is_registered()
    assert status["available"] is False
    assert status["registered"] is False


def test_register_mcp_returns_manual_block_without_cli():
    result = setup_ops.register_mcp()
    assert result["ok"] is False
    assert result["action"] == "manual"
    assert "claude mcp add cortex" in result["manual"]


def test_cmd_mcp_register_prints_manual_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cmd_mcp_register(SimpleNamespace(scope="user", yes=True))
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "claude mcp add cortex" in out


def test_unregister_mcp_graceful_without_cli():
    result = setup_ops.unregister_mcp()
    assert result["ok"] is False
    assert "not installed" in result["detail"]
