"""Contract tests for the beta CLI surface gating (Workstream D).

Pins the beta behavior:
  - Without CORTEX_EXPERIMENTAL, only the visible allowlist appears in --help,
    and an experimental command refuses to run with the EXACT message + exit 2
    (never a traceback or argparse "invalid choice"/"required arguments").
  - `cortex <experimental> --help` still renders (parseable-but-unrunnable).
  - Visible commands still work.
  - With CORTEX_EXPERIMENTAL=1 the full surface is restored and runnable.

These shell out to `python -m cli`, which is fast for the paths exercised here
(help + the gate short-circuit), unlike the heavy analysis commands.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The exact message the beta contract requires, parameterized by command.
EXPECTED_MSG = (
    "'cortex {cmd}' is experimental in this beta. "
    "Enable with CORTEX_EXPERIMENTAL=1 (unsupported)."
)

# A representative slice of experimental commands: a plain one, one with a
# required positional (would otherwise trip argparse), and a grouped one.
EXPERIMENTAL_SAMPLES = ["sessions", "draft", "graph", "schedule", "v2a-batch"]

# Commands that must stay on the default surface.
VISIBLE_SAMPLES = ["config", "intelligence", "recall", "doctor", "briefing"]


def _run(args, experimental=False, tmp_home=None):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    # Isolate cortex state so no test touches the live ~/.cortex.
    if tmp_home is not None:
        env["HOME"] = str(tmp_home)
        env["CORTEX_ROOT_DIR"] = str(tmp_home)
    if experimental:
        env["CORTEX_EXPERIMENTAL"] = "1"
    else:
        env.pop("CORTEX_EXPERIMENTAL", None)
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
        env=env,
    )


@pytest.fixture()
def home(tmp_path):
    return tmp_path


@pytest.mark.parametrize("cmd", EXPERIMENTAL_SAMPLES)
def test_experimental_command_refuses_with_exact_message(cmd, home):
    """Experimental command → exit 2 + EXACT message, no traceback/usage dump."""
    res = _run([cmd], tmp_home=home)
    assert res.returncode == 2, (
        f"{cmd!r} expected exit 2, got {res.returncode}. stderr={res.stderr!r}"
    )
    # Exact message (single line), on stderr.
    assert res.stderr.strip() == EXPECTED_MSG.format(cmd=cmd), (
        f"{cmd!r} wrong message: {res.stderr!r}"
    )
    # Never an argparse error or a Python traceback.
    assert "invalid choice" not in res.stderr
    assert "Traceback" not in res.stderr
    assert "the following arguments are required" not in res.stderr


def test_experimental_command_help_still_renders(home):
    """`cortex <exp> --help` stays exit 0 — parseable-but-unrunnable."""
    res = _run(["schedule", "--help"], tmp_home=home)
    assert res.returncode == 0, res.stderr
    assert "schedule" in (res.stdout + res.stderr).lower()
    # The gate message must NOT fire on the --help path.
    assert "experimental in this beta" not in res.stderr


def test_experimental_hidden_from_help(home):
    """Experimental commands do not appear in the default --help listing."""
    res = _run(["--help"], tmp_home=home)
    assert res.returncode == 0, res.stderr
    help_text = res.stdout
    for cmd in EXPERIMENTAL_SAMPLES:
        # Each hidden command should not have its own help line. Guard against
        # a false match by looking for the command as a standalone token at the
        # start of a stripped help line.
        lines = [ln.strip() for ln in help_text.splitlines()]
        assert not any(ln.split()[:1] == [cmd] for ln in lines if ln), (
            f"{cmd!r} leaked into default --help:\n{help_text}"
        )


@pytest.mark.parametrize("cmd", VISIBLE_SAMPLES)
def test_visible_command_in_help(cmd, home):
    """Visible allowlist commands appear in the default --help listing."""
    res = _run(["--help"], tmp_home=home)
    assert res.returncode == 0, res.stderr
    assert cmd in res.stdout, f"{cmd!r} missing from default --help:\n{res.stdout}"


def test_visible_command_runs(home):
    """A visible command still executes (not gated)."""
    res = _run(["config", "--show"], tmp_home=home)
    assert res.returncode == 0, res.stderr
    assert "experimental in this beta" not in res.stderr


def test_experimental_flag_restores_and_runs(home):
    """CORTEX_EXPERIMENTAL=1: experimental commands are visible and not gated."""
    help_res = _run(["--help"], experimental=True, tmp_home=home)
    assert help_res.returncode == 0, help_res.stderr
    for cmd in EXPERIMENTAL_SAMPLES:
        assert cmd in help_res.stdout, f"{cmd!r} missing from experimental --help"

    # A gated-by-default command now reaches its own handler (no gate message),
    # regardless of that handler's own exit code in this isolated env.
    run_res = _run(["batch-api-status"], experimental=True, tmp_home=home)
    assert "experimental in this beta" not in run_res.stderr
    assert run_res.returncode == 0, run_res.stderr


def test_unknown_command_is_not_our_message(home):
    """A genuinely unknown command gets argparse's own error, not our gate."""
    res = _run(["definitelynotacommand"], tmp_home=home)
    assert res.returncode == 2
    assert "experimental in this beta" not in res.stderr
