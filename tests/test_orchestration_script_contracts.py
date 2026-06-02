"""Contract tests for maintainer orchestration scripts.

These scripts are part of an internal maintenance toolchain that hasn't been
published in the public OSS repo. The tests skip when the scripts aren't
present so that:
  - In the local monorepo (scripts present), the contracts are enforced.
  - In the public repo (scripts absent), the tests skip cleanly instead of
    failing — preserving the 100% pass rate target for external testers.

Re-enable by shipping the scripts under scripts/ at the repo root.
"""

import pytest
import subprocess
from pathlib import Path

pytestmark = pytest.mark.integration

# Test files live at <repo>/tests/, so parents[1] is the repo root.
ROOT = Path(__file__).resolve().parents[1]

_AUDIT_SCRIPT = ROOT / "scripts/orchestration-audit.sh"
_MACRO_SCRIPT = ROOT / "scripts/codex/macro-test.sh"
_LAUNCHD_SCRIPT = ROOT / "scripts/launchd-services.sh"


def _read(path: str) -> str:
    return (ROOT / path).read_text()


@pytest.mark.skipif(
    not (_AUDIT_SCRIPT.exists() and _MACRO_SCRIPT.exists() and _LAUNCHD_SCRIPT.exists()),
    reason="orchestration scripts not present in this checkout (internal toolchain)",
)
def test_shell_scripts_are_syntax_valid() -> None:
    scripts = [
        "scripts/orchestration-audit.sh",
        "scripts/codex/macro-test.sh",
        "scripts/launchd-services.sh",
    ]
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(ROOT / script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script} failed bash -n: {result.stderr}"


@pytest.mark.skipif(not _AUDIT_SCRIPT.exists(), reason="orchestration-audit.sh not present")
def test_audit_enforces_semantic_http_checks() -> None:
    body = _read("scripts/orchestration-audit.sh")
    assert "check_http_expect" in body
    assert "check_http_any_expect" in body
    assert "com.jessekemp.cortex-site-3001" in body
    assert "com.jessekemp.cortex-bridge-8765" in body


@pytest.mark.skipif(not _MACRO_SCRIPT.exists(), reason="macro-test.sh not present")
def test_macro_test_uses_strict_probe_contract() -> None:
    body = _read("scripts/codex/macro-test.sh")
    assert 'code="$(curl' in body
    assert "probe_any" in body
    assert 'expect="${2:-}"' in body
