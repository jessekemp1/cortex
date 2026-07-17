"""A4/A5: doctor --json + exit codes, and cortex reset.

- doctor --json emits valid JSON and its exit code reflects health (non-zero on
  any FAIL, 0 when healthy); --fix repairs a seeded broken state.
- reset wipes the isolated CORTEX_STATE_DIR with --force.

All tests force CORTEX_CLAUDE_BIN="" so no test path can touch the real
~/.claude.json via MCP registration.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cli.commands.v2_ops import cmd_doctor, cmd_reset


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("CORTEX_CLAUDE_BIN", "")  # force claude-not-installed path
    return tmp_path


def _spool(state_dir, decision_id="dec_seed1"):
    spool = state_dir / "spool"
    spool.mkdir(parents=True, exist_ok=True)
    (spool / f"decision-{decision_id}.json").write_text(
        json.dumps({"decision_id": decision_id, "decision": "seeded", "timestamp": "t"})
    )


def test_doctor_json_is_valid_and_has_schema(state_dir, capsys):
    with pytest.raises(SystemExit):
        cmd_doctor(SimpleNamespace(fix=False, json=True))
    payload = json.loads(capsys.readouterr().out)
    assert "checks" in payload and isinstance(payload["checks"], list)
    assert "all_pass" in payload
    assert set(payload["counts"]) == {"pass", "fail", "warn", "skip"}
    for c in payload["checks"]:
        assert set(c) == {"check", "status", "detail"}
        assert c["status"] in {"pass", "fail", "warn", "skip"}


def test_doctor_exit_nonzero_on_failure(state_dir):
    _spool(state_dir)  # a pending spool is a FAIL
    with pytest.raises(SystemExit) as exc:
        cmd_doctor(SimpleNamespace(fix=False, json=True))
    assert exc.value.code == 1


def test_doctor_exit_zero_when_healthy(state_dir):
    # No seeded failure; golden path (no key) must NOT fail doctor.
    with pytest.raises(SystemExit) as exc:
        cmd_doctor(SimpleNamespace(fix=False, json=True))
    assert exc.value.code == 0


def test_doctor_fix_repairs_broken_spool_and_exits_zero(state_dir, capsys):
    _spool(state_dir)
    with pytest.raises(SystemExit) as exc:
        cmd_doctor(SimpleNamespace(fix=True, json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_pass"] is True
    assert exc.value.code == 0
    # The stranded decision landed durably.
    decisions = (state_dir / "decisions.jsonl").read_text().splitlines()
    assert any(json.loads(d)["decision_id"] == "dec_seed1" for d in decisions)


def test_doctor_fix_creates_env_placeholder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CORTEX_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("CORTEX_CLAUDE_BIN", "")
    assert not (tmp_path / ".env").exists()
    with pytest.raises(SystemExit):
        cmd_doctor(SimpleNamespace(fix=True, json=True))
    assert (tmp_path / ".env").exists()


def test_doctor_api_key_missing_is_warn_not_fail(state_dir, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        cmd_doctor(SimpleNamespace(fix=False, json=True))
    payload = json.loads(capsys.readouterr().out)
    key_check = next(c for c in payload["checks"] if c["check"] == "ANTHROPIC_API_KEY set")
    assert key_check["status"] == "warn"
    assert exc.value.code == 0  # golden path: no key still healthy


def test_reset_force_wipes_state(state_dir, capsys):
    (state_dir / "logs").mkdir()
    (state_dir / "decisions.jsonl").write_text("x")
    cmd_reset(SimpleNamespace(yes=False, force=True))
    assert not state_dir.exists()
    assert "wiped" in capsys.readouterr().out.lower()


def test_reset_yes_alias(state_dir):
    (state_dir / "decisions.jsonl").write_text("x")
    cmd_reset(SimpleNamespace(yes=True, force=False))
    assert not state_dir.exists()
