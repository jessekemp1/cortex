"""A2: install.sh --yes is non-interactive and needs no API key.

Runs the real install.sh in a FAKE HOME with stdin closed and the network/OS
side effects stubbed out (reuse the test venv, skip pip/npm/launchd, force the
claude CLI absent). Asserts it completes without hanging and without prompting.

Skipped unless CORTEX_TEST_VENV points at a usable prebuilt venv — the install
needs a real cortex install to run `cortex init/onboard/doctor`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"

# The venv the installer should reuse. Default to a sibling .venv; tests in CI
# override via CORTEX_TEST_VENV.
TEST_VENV = os.environ.get("CORTEX_TEST_VENV") or str(REPO_ROOT / ".venv")


pytestmark = pytest.mark.skipif(
    not Path(TEST_VENV, "bin", "python").exists(),
    reason="no usable venv for install.sh (set CORTEX_TEST_VENV)",
)


def test_install_yes_is_noninteractive_and_keyless(tmp_path):
    fake_home = tmp_path / "home"
    state = tmp_path / "state"
    projects = tmp_path / "projects"
    fake_home.mkdir()
    projects.mkdir()

    env = {
        **os.environ,
        "HOME": str(fake_home),
        "CORTEX_STATE_DIR": str(state),
        "CORTEX_ROOT_DIR": str(projects),
        "CORTEX_VENV": TEST_VENV,
        "CORTEX_SKIP_PIP": "1",
        "CORTEX_SKIP_LAUNCHD": "1",
        "CORTEX_SKIP_SITE": "1",
        "CORTEX_CLAUDE_BIN": "",  # force claude-not-installed (manual block)
    }
    env.pop("ANTHROPIC_API_KEY", None)  # golden path: no key

    proc = subprocess.run(
        ["bash", str(INSTALL_SH), "--yes"],
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,  # any prompt would hang → timeout → fail
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert proc.returncode == 0, f"install --yes failed:\n{proc.stdout}\n{proc.stderr}"
    out = proc.stdout
    # It reached the epilogue (did not hang mid-way).
    assert "NEXT — 3 STEPS" in out or "Install complete" in out
    # It skipped the key rather than prompting for it.
    assert "Skipping API key" in out
    # doctor --fix ran and the golden path is healthy without a key.
    assert "All checks passed." in out
    # State was actually initialized in the isolated dir.
    assert (state / "config.yaml").exists()


def test_bridge_agent_script_skips_gracefully(tmp_path):
    """install_bridge_agent.sh must no-op cleanly when launchd is skipped."""
    script = REPO_ROOT / "scripts" / "install_bridge_agent.sh"
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "CORTEX_STATE_DIR": str(tmp_path / "state"),
        "CORTEX_SKIP_LAUNCHD": "1",
    }
    proc = subprocess.run(
        ["bash", str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "skipping launch agent" in proc.stdout.lower()
