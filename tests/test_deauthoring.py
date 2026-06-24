"""Regression tests for the P0 de-authoring work.

Ensures a second user pointing CORTEX_ROOT_DIR at their own workspace gets
projects discovered from *their* git repos — never the author's hardcoded
portfolio (cortex/vortex/alpha_arena/pupil) or ~/Dev.

See docs/P0_DEAUTHORING_PLAN.md.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import config

# Author project names + workspace markers that must NOT leak for a second user.
_AUTHOR_LEAKS = {"cortex", "vortex", "alpha_arena", "pupil", "kempion"}


def _git_init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)


@pytest.fixture()
def fake_workspace(tmp_path, monkeypatch):
    """A second user's workspace with two git repos under CORTEX_ROOT_DIR."""
    ws = tmp_path / "ws"
    _git_init(ws / "proj-a")
    _git_init(ws / "proj-b")
    # A non-git dir at the root should be ignored.
    (ws / "not-a-repo").mkdir()
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(ws))
    monkeypatch.delenv("CORTEX_DEV_ROOT", raising=False)
    return ws


def test_workspace_root_reads_cortex_root_dir(fake_workspace):
    assert config.workspace_root() == fake_workspace


def test_discover_projects_returns_only_user_repos(fake_workspace):
    names = sorted(p["name"] for p in config.discover_projects())
    assert names == ["proj-a", "proj-b"]
    assert not (_AUTHOR_LEAKS & set(names))


def test_discover_projects_depth_2(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    _git_init(ws / "group" / "nested-proj")
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(ws))
    projects = {p["name"]: p for p in config.discover_projects()}
    assert "nested-proj" in projects
    assert projects["nested-proj"]["rel"] == "group/nested-proj"


def test_discover_projects_missing_root(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(tmp_path / "does-not-exist"))
    assert config.discover_projects() == []


def test_discover_projects_root_is_a_file(tmp_path, monkeypatch):
    """A CORTEX_ROOT_DIR pointing at a FILE must return [] — not raise
    NotADirectoryError, which would 500 the /projects endpoint for a second
    user who misconfigures the env var."""
    f = tmp_path / "not-a-dir.txt"
    f.write_text("oops")
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(f))
    assert config.discover_projects() == []
