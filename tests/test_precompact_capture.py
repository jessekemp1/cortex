"""Tests for cortex/hooks/precompact_capture.py."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

CORTEX_ROOT = Path(__file__).resolve().parent.parent
if str(CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT))
if str(CORTEX_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT.parent))

HOOK_SCRIPT = CORTEX_ROOT / "hooks" / "precompact_capture.py"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Initialized git repo with one commit on branch 'test-branch'.

    Commit signing is disabled for this throwaway repo — the environment
    may have a global signing hook that fails in sandboxes, and the
    precompact hook only inspects the output of ``git log --oneline -1``,
    which doesn't care whether the commit is signed.
    """
    subprocess.run(["git", "init", "-q", "-b", "test-branch"], cwd=tmp_path, check=True)
    # Local config — affects this throwaway repo only.
    for k, v in [
        ("user.email", "t@t"),
        ("user.name", "t"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
    ]:
        subprocess.run(["git", "config", k, v], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("a")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init commit"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


@pytest.fixture
def workflow_dir(git_repo: Path) -> Path:
    d = git_repo / ".workflow" / "current"
    d.mkdir(parents=True)
    return d


def _load_hook():
    """Import precompact_capture without running its top-level logging setup twice."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cortex_precompact_test", HOOK_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Fallback generation ─────────────────────────────────────────────


class TestFallbackGeneration:
    def test_writes_fallback_when_handoff_missing(
        self, git_repo: Path, workflow_dir: Path
    ):
        hook = _load_hook()
        hook_input = {
            "session_id": "test-session",
            "hook_event_name": "PreCompact",
            "trigger": "manual",
            "cwd": str(git_repo),
        }
        rc = hook.run(hook_input)
        assert rc == 0

        handoff_path = workflow_dir / "handoff.yaml"
        assert handoff_path.exists()

        data = yaml.safe_load(handoff_path.read_text())
        assert data["confidence"] == 0.2  # fallback marker
        assert "init commit" in (data["done"][0] if data["done"] else "")
        assert data["gate_command"] == "git status --short"
        assert data["_branch"] == "test-branch"

    def test_fallback_captures_uncommitted_changes(
        self, git_repo: Path, workflow_dir: Path
    ):
        (git_repo / "dirty.txt").write_text("uncommitted")
        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "auto",
                "cwd": str(git_repo),
            }
        )
        data = yaml.safe_load((workflow_dir / "handoff.yaml").read_text())
        assert any("uncommitted" in q or "dirty.txt" in q for q in data["open_questions"])

    def test_fallback_has_low_confidence(self, git_repo: Path, workflow_dir: Path):
        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )
        data = yaml.safe_load((workflow_dir / "handoff.yaml").read_text())
        # Fallback handoff is machine-generated; must signal low trust
        assert data["confidence"] <= 0.3


# ── Fresh-handoff detection ─────────────────────────────────────────


class TestFreshHandoffDetection:
    def test_fresh_handoff_is_preserved(
        self, git_repo: Path, workflow_dir: Path
    ):
        """If the agent wrote a handoff recently, the hook must not overwrite it."""
        from runtime.handoff import HandoffFields, write_handoff

        agent_fields = HandoffFields(
            done=["agent-written step 1", "agent-written step 2"],
            verified=["pytest passed"],
            open_questions=[],
            next_action="agent-authored next action",
            gate_command="pytest -q",
            confidence=0.9,
        )
        write_handoff(agent_fields, workflow_dir=workflow_dir)

        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )

        data = yaml.safe_load((workflow_dir / "handoff.yaml").read_text())
        # Must be the agent's content, not the fallback
        assert data["confidence"] == 0.9
        assert data["next_action"] == "agent-authored next action"
        assert data["gate_command"] == "pytest -q"

    def test_stale_handoff_is_overwritten(
        self, git_repo: Path, workflow_dir: Path
    ):
        """A handoff older than _FRESH_HANDOFF_WINDOW is treated as stale."""
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        (workflow_dir / "handoff.yaml").write_text(
            yaml.safe_dump(
                {
                    "done": ["stale content"],
                    "verified": [],
                    "open_questions": [],
                    "next_action": "stale action",
                    "gate_command": "stale",
                    "confidence": 0.9,
                    "_written_at": stale_ts,
                    "_branch": "old-branch",
                }
            )
        )

        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )

        data = yaml.safe_load((workflow_dir / "handoff.yaml").read_text())
        # Fallback replaced the stale handoff
        assert data["confidence"] == 0.2
        assert data["next_action"] != "stale action"

    def test_handoff_without_timestamp_treated_as_stale(
        self, git_repo: Path, workflow_dir: Path
    ):
        """Handoff missing _written_at cannot be verified fresh; overwrite."""
        (workflow_dir / "handoff.yaml").write_text(
            "done: []\nnext_action: no timestamp\nconfidence: 0.5\n"
        )
        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )
        data = yaml.safe_load((workflow_dir / "handoff.yaml").read_text())
        assert data["confidence"] == 0.2


# ── Resilience ──────────────────────────────────────────────────────


class TestResilience:
    def test_never_blocks_on_missing_stdin(self, tmp_path: Path):
        """Running the hook with empty stdin exits 0."""
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="",
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_never_blocks_on_malformed_json(self, tmp_path: Path):
        """Malformed stdin JSON exits 0 with a warning, not a crash."""
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input="{this is not json",
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_never_blocks_outside_git_repo(self, tmp_path: Path):
        """Hook runs in a directory that isn't a git repo — still exits 0."""
        hook = _load_hook()
        rc = hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(tmp_path),
            }
        )
        assert rc == 0

    def test_env_workflow_dir_respected(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """CORTEX_WORKFLOW_DIR env var redirects where the handoff lands."""
        alt_dir = tmp_path / "alt_workflow"
        alt_dir.mkdir()
        monkeypatch.setenv("CORTEX_WORKFLOW_DIR", str(alt_dir))

        hook = _load_hook()
        hook.run(
            {
                "session_id": "s",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )
        assert (alt_dir / "handoff.yaml").exists()
        # Default location should NOT have received the write
        assert not (git_repo / ".workflow" / "current" / "handoff.yaml").exists()


# ── CLI entry point ─────────────────────────────────────────────────


class TestCLIEntry:
    def test_end_to_end_via_subprocess(self, git_repo: Path, workflow_dir: Path):
        """Full CLI invocation: JSON in → exit 0 → handoff.yaml written."""
        payload = json.dumps(
            {
                "session_id": "cli-test",
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "cwd": str(git_repo),
            }
        )
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=git_repo,
            timeout=10,
        )
        assert proc.returncode == 0
        assert (workflow_dir / "handoff.yaml").exists()


# ── Hook config registration ────────────────────────────────────────


class TestHookConfig:
    def test_precompact_registered_in_hooks_config(self):
        """interaction_hooks_config.json must wire the PreCompact script."""
        cfg = json.loads(
            (CORTEX_ROOT / "hooks" / "interaction_hooks_config.json").read_text()
        )
        assert "PreCompact" in cfg["hooks"]
        entry = cfg["hooks"]["PreCompact"][0]["hooks"][0]
        assert "precompact_capture.py" in entry["command"]
        assert entry.get("timeout", 0) > 0
