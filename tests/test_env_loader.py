"""A1: .env loading — a key saved by install.sh must reach the process.

Proves the two contract properties:
  1. A key in $CORTEX_STATE_DIR/.env becomes visible via os.environ WITHOUT a
     shell export.
  2. A real environment variable ALWAYS wins over the .env-file value.
"""

from __future__ import annotations

import importlib

import env_loader


def test_env_file_key_visible_without_shell_export(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-fromfile\nCORTEX_DEMO_VAR=hi\n")
    monkeypatch.setenv("CORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CORTEX_DEMO_VAR", raising=False)

    importlib.reload(env_loader)
    applied = env_loader.load_env()

    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fromfile"
    assert os.environ["CORTEX_DEMO_VAR"] == "hi"
    assert "ANTHROPIC_API_KEY" in applied


def test_real_env_var_wins_over_file(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-fromfile\n")
    monkeypatch.setenv("CORTEX_STATE_DIR", str(state))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-REAL")

    importlib.reload(env_loader)
    env_loader.load_env()

    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-REAL"


def test_state_env_precedes_repo_env(tmp_path, monkeypatch):
    """The state-dir .env (canonical secret store) wins over a repo-local .env."""
    state = tmp_path / "state"
    state.mkdir()
    (state / ".env").write_text("CORTEX_PRECEDENCE=state\n")
    monkeypatch.setenv("CORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("CORTEX_PRECEDENCE", raising=False)

    importlib.reload(env_loader)
    # Point the repo-root .env lookup at a value that must LOSE.
    monkeypatch.setattr(env_loader, "_repo_root", lambda: tmp_path / "repo")
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / ".env").write_text("CORTEX_PRECEDENCE=repo\n")

    env_loader.load_env()

    import os

    assert os.environ["CORTEX_PRECEDENCE"] == "state"


def test_parity_reports_missing_when_loader_not_run(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / ".env").write_text("CORTEX_ONLY_IN_FILE=xyz\n")
    monkeypatch.setenv("CORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("CORTEX_ONLY_IN_FILE", raising=False)

    importlib.reload(env_loader)
    par = env_loader.env_dotenv_parity()
    assert par["ok"] is False
    assert "CORTEX_ONLY_IN_FILE" in par["missing"]

    # After loading, parity is restored.
    env_loader.load_env()
    par2 = env_loader.env_dotenv_parity()
    assert par2["ok"] is True
    assert "CORTEX_ONLY_IN_FILE" not in par2["missing"]
