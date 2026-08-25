"""Regression tests: project health must measure the project's OWN repo.

The workspace root (~/dbx-dev) is one repo among many, not a monorepo that
contains the others. PortfolioMemory nevertheless analyzed
`CORTEX_ROOT_DIR` at every call site and reported those numbers under each
project's name, so five projects returned an identical 57/100 while their
own repos differed (cortex was 2 commits / 1 uncommitted against the root's
14 / 18). These tests pin the shape of the fix: distinct repos produce
distinct numbers, an unresolvable project is reported rather than scored,
and a dormant repo is not an at-risk one.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from portfolio_memory import PortfolioMemory, _resolve_repo_path


def _git(path: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(path),
        check=True,
        capture_output=True,
        env={**os.environ, **(env or {})},
    )


def _repo(path: Path, commits: int = 1, days_ago: int = 0) -> Path:
    """A real git repo with `commits` commits dated `days_ago` in the past.

    Backdating needs GIT_COMMITTER_DATE, not just --date: `git log --since`
    filters on the COMMITTER date, so a commit with only its author date moved
    back still counts as today's activity.
    """
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    # An explicit ISO timestamp, not "N days ago": this git rejects the relative
    # form outright ("fatal: invalid date format: 0 days ago").
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    for i in range(commits):
        (path / f"f{i}.txt").write_text(str(i))
        _git(path, "add", f"f{i}.txt")
        # --no-verify: the machine's global pre-commit hooks (secret scanning)
        # otherwise run on every fixture commit and dominate the runtime.
        _git(
            path,
            "commit",
            "-q",
            "--no-verify",
            "-m",
            f"c{i}",
            "--date",
            when,
            env={"GIT_COMMITTER_DATE": when},
        )
    return path


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Root repo plus two sub-repos with deliberately different activity."""
    ws = tmp_path / "ws"
    # The root is itself a repo and the busiest one — the old code reported
    # these numbers for every project.
    _repo(ws, commits=6)
    _repo(ws / "proj-a", commits=2)
    _repo(ws / "proj-b", commits=1)
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(ws))
    monkeypatch.delenv("CORTEX_DEV_ROOT", raising=False)
    return ws


@pytest.fixture()
def index(tmp_path):
    """A portfolio index dir; write_index(...) seeds project_index.json."""
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    def write_index(names: list[str]) -> Path:
        (portfolio / "project_index.json").write_text(
            json.dumps({"meta": {}, "projects": {n: {"path": ""} for n in names}})
        )
        return portfolio

    return write_index


def test_resolves_each_project_to_its_own_repo(workspace):
    assert _resolve_repo_path("proj-a") == workspace / "proj-a"
    assert _resolve_repo_path("proj-b") == workspace / "proj-b"


@pytest.mark.usefixtures("workspace")
def test_unresolvable_project_returns_none_not_the_root():
    """The old fallback silently substituted the workspace root."""
    assert _resolve_repo_path("no-such-project") is None


@pytest.mark.usefixtures("workspace")
def test_index_recorded_path_wins_over_discovery(tmp_path):
    elsewhere = _repo(tmp_path / "elsewhere")
    resolved = _resolve_repo_path("proj-a", {"proj-a": {"path": str(elsewhere)}})
    assert resolved == elsewhere


def test_index_path_ignored_when_not_a_repo(workspace, tmp_path):
    """A stale recorded path must fall through to discovery, not win."""
    plain = tmp_path / "plain-dir"
    plain.mkdir()
    resolved = _resolve_repo_path("proj-a", {"proj-a": {"path": str(plain)}})
    assert resolved == workspace / "proj-a"


def test_project_health_reports_its_own_commit_count(workspace, index):
    pm = PortfolioMemory(portfolio_path=index(["proj-a", "proj-b"]))

    a = pm.get_project_health("proj-a", days=7)
    b = pm.get_project_health("proj-b", days=7)

    assert a["commits_7d"] == 2, a
    assert b["commits_7d"] == 1, b
    # The root repo has 6 commits; neither project may report them.
    assert a["commits_7d"] != 6 and b["commits_7d"] != 6
    assert a["repo_path"] == str(workspace / "proj-a")


@pytest.mark.usefixtures("workspace")
def test_project_health_errors_when_no_repo_resolves(index):
    pm = PortfolioMemory(portfolio_path=index(["ghost"]))
    result = pm.get_project_health("ghost", days=7)
    assert "error" in result
    assert "no repo resolved" in result["error"].lower()
    # Must NOT invent a score.
    assert "score" not in result


@pytest.mark.usefixtures("workspace")
def test_portfolio_summary_scores_projects_independently(index):
    pm = PortfolioMemory(portfolio_path=index(["proj-a", "proj-b"]))
    summary = pm.get_portfolio_health_summary(days=7)

    projects = summary["projects"]
    assert {"proj-a", "proj-b"} <= set(projects)
    assert projects["proj-a"]["commits"] == 2
    assert projects["proj-b"]["commits"] == 1
    # The defect was every project sharing one identical metric set.
    assert projects["proj-a"]["commits"] != projects["proj-b"]["commits"]
    assert projects["proj-a"]["repo_path"] != projects["proj-b"]["repo_path"]


@pytest.mark.usefixtures("workspace")
def test_portfolio_summary_aggregates_over_real_repos(index):
    pm = PortfolioMemory(portfolio_path=index(["proj-a", "proj-b"]))
    summary = pm.get_portfolio_health_summary(days=7)

    # root(6) + proj-a(2) + proj-b(1) — a real sum, not one repo's count.
    assert summary["overall"]["commits"] == 9
    assert summary["overall"]["active_projects"] == 3
    assert "error" not in summary


@pytest.mark.usefixtures("workspace")
def test_stale_index_entry_is_reported_not_scored(index):
    """The ~/Dev-era names (Vortex/backend, alpha_arena, pupil) land here."""
    pm = PortfolioMemory(portfolio_path=index(["proj-a", "alpha_arena", "pupil"]))
    summary = pm.get_portfolio_health_summary(days=7)

    unresolved = summary["aggregate"]["unresolved_projects"]
    assert sorted(unresolved) == ["alpha_arena", "pupil"]
    # They get no fabricated score and no alert-path membership.
    assert "alpha_arena" not in summary["projects"]
    for bucket in ("healthy_projects", "at_risk_projects", "critical_projects"):
        assert "alpha_arena" not in summary["aggregate"][bucket]


def test_dormant_repo_is_inactive_not_critical(tmp_path, monkeypatch, index):
    """No commits in the window means no health signal to decline."""
    ws = tmp_path / "ws2"
    _repo(ws, commits=3)
    _repo(ws / "dormant", commits=1, days_ago=400)
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(ws))

    pm = PortfolioMemory(portfolio_path=index(["dormant"]))
    summary = pm.get_portfolio_health_summary(days=7)

    agg = summary["aggregate"]
    assert "dormant" in agg["inactive_projects"]
    assert "dormant" not in agg["critical_projects"]
    assert "dormant" not in agg["at_risk_projects"]
    # Still measured and visible, just not alerted on.
    assert summary["projects"]["dormant"]["commits"] == 0


@pytest.mark.usefixtures("workspace")
def test_refresh_index_records_real_paths(workspace, index):
    pm = PortfolioMemory(portfolio_path=index(["proj-a"]))
    result = pm.refresh_index()

    assert "proj-b" in result["added"]
    assert "proj-a" in result["updated"]

    written = json.loads((pm.index_file).read_text())
    assert written["projects"]["proj-a"]["path"] == str(workspace / "proj-a")
    assert written["meta"]["total_projects"] == len(written["projects"])


@pytest.mark.usefixtures("workspace")
def test_refresh_index_retires_without_discarding(index):
    portfolio = index(["proj-a", "alpha_arena"])
    # Give the stale entry a curated payload that must survive.
    path = portfolio / "project_index.json"
    data = json.loads(path.read_text())
    data["projects"]["alpha_arena"]["tech_stack"] = ["Python"]
    path.write_text(json.dumps(data))

    pm = PortfolioMemory(portfolio_path=portfolio)
    result = pm.refresh_index()

    assert result["retired"] == ["alpha_arena"]
    written = json.loads(path.read_text())
    assert "alpha_arena" not in written["projects"]
    # Retired, not deleted — the analysis is still readable.
    assert written["retired_projects"]["alpha_arena"]["tech_stack"] == ["Python"]
    assert "retired_at" in written["retired_projects"]["alpha_arena"]


@pytest.mark.usefixtures("workspace")
def test_refresh_index_is_idempotent(index):
    pm = PortfolioMemory(portfolio_path=index(["proj-a"]))
    pm.refresh_index()
    first = json.loads(pm.index_file.read_text())["projects"]

    second_run = pm.refresh_index()
    second = json.loads(pm.index_file.read_text())["projects"]

    assert second_run["added"] == []
    assert sorted(first) == sorted(second)


def test_summary_errors_when_nothing_can_be_measured(tmp_path, monkeypatch, index):
    """A health-data outage must surface as `error`, which recommendations.py
    checks so it can report the outage instead of reading a zero as real."""
    empty = tmp_path / "empty-ws"
    empty.mkdir()
    monkeypatch.setenv("CORTEX_ROOT_DIR", str(empty))

    pm = PortfolioMemory(portfolio_path=index(["ghost"]))
    summary = pm.get_portfolio_health_summary(days=7)
    assert "error" in summary
