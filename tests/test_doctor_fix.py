"""cortex doctor: spool reporting and --fix flush."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cli.commands.v2_ops import cmd_doctor


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    # Force the "claude CLI not installed" path so doctor --fix never touches
    # the real ~/.claude.json during tests (empty string == not available).
    monkeypatch.setenv("CORTEX_CLAUDE_BIN", "")
    return tmp_path


def _spool_entry(state_dir, decision_id="dec_stranded1"):
    spool = state_dir / "spool"
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"decision-{decision_id}.json").write_text(
        json.dumps({"decision_id": decision_id, "decision": "stranded", "timestamp": "t"})
    )


def test_doctor_reports_pending_spool(state_dir, capsys):
    _spool_entry(state_dir)
    with pytest.raises(SystemExit) as exc:
        cmd_doctor(SimpleNamespace(fix=False))
    out = capsys.readouterr().out
    assert "decision spool empty" in out
    assert "1 pending" in out
    assert exc.value.code == 1  # pending spool fails doctor


def test_doctor_fix_flushes_spool(state_dir, capsys):
    _spool_entry(state_dir)
    with pytest.raises(SystemExit):
        cmd_doctor(SimpleNamespace(fix=True))
    out = capsys.readouterr().out
    assert "spool flush: 1 flushed" in out

    decisions = (state_dir / "decisions.jsonl").read_text().splitlines()
    assert json.loads(decisions[0])["decision_id"] == "dec_stranded1"
    assert not list((state_dir / "spool").glob("decision-*.json"))

    # Second run: nothing left to flush, spool check passes.
    with pytest.raises(SystemExit):
        cmd_doctor(SimpleNamespace(fix=True))
    out = capsys.readouterr().out
    assert "spool flush: 0 flushed" in out
    assert "[PASS] decision spool empty" in out
