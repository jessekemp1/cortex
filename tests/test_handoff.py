"""Tests for cortex/runtime/handoff.py and its integration with session_snapshot.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

CORTEX_ROOT = Path(__file__).resolve().parent.parent
if str(CORTEX_ROOT) not in sys.path:
    sys.path.insert(0, str(CORTEX_ROOT))

from runtime.handoff import (  # noqa: E402
    HANDOFF_FILENAME,
    HandoffFields,
    read_handoff,
    render_handoff_markdown,
    write_handoff,
)


@pytest.fixture
def workflow_dir(tmp_path: Path) -> Path:
    """Fresh .workflow/current/ for each test."""
    d = tmp_path / ".workflow" / "current"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def sample_fields() -> HandoffFields:
    return HandoffFields(
        done=["commit phase-1a", "verify snapshot freeze"],
        verified=["pytest tests/test_echelon_snapshot.py -q"],
        open_questions=["PE value-only vs value+bizeq?"],
        next_action="Write us_calibration.json with 50-state weights.",
        gate_command="pytest pupil/tests/test_echelon_snapshot.py -q",
        confidence=0.8,
    )


# ── Roundtrip and schema ─────────────────────────────────────────────


class TestRoundtrip:
    def test_roundtrip(self, workflow_dir: Path, sample_fields: HandoffFields):
        write_handoff(sample_fields, workflow_dir=workflow_dir)
        loaded = read_handoff(workflow_dir=workflow_dir)
        assert loaded is not None
        assert loaded.done == sample_fields.done
        assert loaded.verified == sample_fields.verified
        assert loaded.open_questions == sample_fields.open_questions
        assert loaded.next_action == sample_fields.next_action
        assert loaded.gate_command == sample_fields.gate_command
        assert loaded.confidence == sample_fields.confidence

    def test_missing_file_returns_none(self, workflow_dir: Path):
        assert read_handoff(workflow_dir=workflow_dir) is None

    def test_missing_directory_returns_none(self, tmp_path: Path):
        # Directory doesn't exist at all
        assert read_handoff(workflow_dir=tmp_path / "nope") is None

    def test_malformed_yaml_returns_none(self, workflow_dir: Path):
        (workflow_dir / HANDOFF_FILENAME).write_text("{: this is [not valid yaml")
        assert read_handoff(workflow_dir=workflow_dir) is None

    def test_yaml_root_not_mapping_returns_none(self, workflow_dir: Path):
        (workflow_dir / HANDOFF_FILENAME).write_text("- this is a list at root\n- not a map")
        assert read_handoff(workflow_dir=workflow_dir) is None

    def test_schema_violation_returns_none(self, workflow_dir: Path):
        (workflow_dir / HANDOFF_FILENAME).write_text("done: not a list\nnext_action: foo\n")
        assert read_handoff(workflow_dir=workflow_dir) is None

    def test_confidence_must_be_numeric(self, workflow_dir: Path):
        (workflow_dir / HANDOFF_FILENAME).write_text("confidence: true\n")
        # bool is not accepted as a confidence value
        assert read_handoff(workflow_dir=workflow_dir) is None

    def test_unknown_keys_preserved_on_read(self, workflow_dir: Path):
        (workflow_dir / HANDOFF_FILENAME).write_text(
            "done: []\nnext_action: foo\nfuture_field: extra\n"
        )
        loaded = read_handoff(workflow_dir=workflow_dir)
        assert loaded is not None
        assert loaded.next_action == "foo"


# ── Write behavior ──────────────────────────────────────────────────


class TestWriteBehavior:
    def test_confidence_clamped_high(self, workflow_dir: Path):
        fields = HandoffFields(confidence=1.5)
        assert fields.confidence == 1.0
        write_handoff(fields, workflow_dir=workflow_dir)
        loaded = read_handoff(workflow_dir=workflow_dir)
        assert loaded is not None
        assert loaded.confidence == 1.0

    def test_confidence_clamped_low(self, workflow_dir: Path):
        fields = HandoffFields(confidence=-0.5)
        assert fields.confidence == 0.0

    def test_auto_timestamp_and_branch_added(self, workflow_dir: Path, sample_fields):
        path = write_handoff(sample_fields, workflow_dir=workflow_dir)
        raw = yaml.safe_load(path.read_text())
        assert "_written_at" in raw
        assert "_branch" in raw
        # ISO-8601 format check
        assert "T" in raw["_written_at"]

    def test_write_creates_parent_directory(self, tmp_path: Path, sample_fields):
        deep = tmp_path / "nested" / ".workflow" / "current"
        # Parent does not exist yet
        assert not deep.exists()
        write_handoff(sample_fields, workflow_dir=deep)
        assert (deep / HANDOFF_FILENAME).exists()

    def test_atomic_write_no_temp_file_leftover(self, workflow_dir: Path, sample_fields):
        write_handoff(sample_fields, workflow_dir=workflow_dir)
        leftovers = list(workflow_dir.glob(".handoff_*"))
        assert leftovers == [], f"tempfile leaked: {leftovers}"

    def test_rewrite_replaces_previous(self, workflow_dir: Path):
        write_handoff(HandoffFields(next_action="first"), workflow_dir=workflow_dir)
        write_handoff(HandoffFields(next_action="second"), workflow_dir=workflow_dir)
        loaded = read_handoff(workflow_dir=workflow_dir)
        assert loaded is not None
        assert loaded.next_action == "second"


# ── Path resolution ─────────────────────────────────────────────────


class TestPathResolution:
    def test_env_override_takes_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_fields
    ):
        env_dir = tmp_path / "env_target"
        env_dir.mkdir()
        monkeypatch.setenv("CORTEX_WORKFLOW_DIR", str(env_dir))
        # No explicit workflow_dir → env wins
        path = write_handoff(sample_fields)
        assert path.parent == env_dir

    def test_cwd_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_fields
    ):
        monkeypatch.delenv("CORTEX_WORKFLOW_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        path = write_handoff(sample_fields)
        assert path.parent == tmp_path / ".workflow" / "current"

    def test_explicit_arg_beats_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_fields
    ):
        env_dir = tmp_path / "env_target"
        env_dir.mkdir()
        explicit = tmp_path / "explicit_target"
        explicit.mkdir()
        monkeypatch.setenv("CORTEX_WORKFLOW_DIR", str(env_dir))
        path = write_handoff(sample_fields, workflow_dir=explicit)
        assert path.parent == explicit


# ── Markdown rendering ──────────────────────────────────────────────


class TestMarkdownRendering:
    def test_renders_all_sections(self, sample_fields):
        md = render_handoff_markdown(sample_fields)
        assert "## Agent Handoff" in md
        assert "Confidence: 0.80" in md or "0.80" in md
        assert "commit phase-1a" in md
        assert "pytest tests/test_echelon_snapshot.py -q" in md
        assert "PE value-only vs value+bizeq?" in md
        assert "us_calibration.json" in md

    def test_renders_empty_lists_as_none(self):
        md = render_handoff_markdown(HandoffFields())
        assert "(none)" in md


# ── Integration with session_snapshot.py ────────────────────────────


class TestSessionSnapshotIntegration:
    def test_progress_md_includes_handoff_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_fields
    ):
        import session_snapshot

        progress = tmp_path / "progress.md"
        workflow_dir = tmp_path
        monkeypatch.setattr(session_snapshot, "WORKFLOW_PROGRESS", progress)
        monkeypatch.setattr(session_snapshot, "_WORKFLOW_DIR", workflow_dir)

        write_handoff(sample_fields, workflow_dir=workflow_dir)
        session_snapshot.write_progress_snapshot(reason="test")

        body = progress.read_text()
        assert "## Agent Handoff" in body
        assert "commit phase-1a" in body
        assert "us_calibration.json" in body

    def test_progress_md_without_handoff_no_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import session_snapshot

        progress = tmp_path / "progress.md"
        empty_workflow = tmp_path / "empty"
        empty_workflow.mkdir()
        monkeypatch.setattr(session_snapshot, "WORKFLOW_PROGRESS", progress)
        monkeypatch.setattr(session_snapshot, "_WORKFLOW_DIR", empty_workflow)

        # No handoff.yaml exists; daemon must still render progress.md.
        session_snapshot.write_progress_snapshot(reason="test")
        body = progress.read_text()
        assert "Session Handoff" in body
        assert "## Agent Handoff" not in body

    def test_progress_md_survives_malformed_handoff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        import session_snapshot

        progress = tmp_path / "progress.md"
        workflow_dir = tmp_path
        monkeypatch.setattr(session_snapshot, "WORKFLOW_PROGRESS", progress)
        monkeypatch.setattr(session_snapshot, "_WORKFLOW_DIR", workflow_dir)

        (workflow_dir / HANDOFF_FILENAME).write_text("{: malformed")
        # Daemon must not crash.
        session_snapshot.write_progress_snapshot(reason="test")
        body = progress.read_text()
        assert "Session Handoff" in body
        assert "## Agent Handoff" not in body
