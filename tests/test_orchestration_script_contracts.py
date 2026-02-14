from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text()


def test_shell_scripts_are_syntax_valid() -> None:
    scripts = [
        "scripts/orchestration-audit.sh",
        "scripts/codex/macro-test.sh",
        "scripts/launchd-services.sh",
    ]
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(ROOT / script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script} failed bash -n: {result.stderr}"


def test_audit_enforces_semantic_http_checks() -> None:
    body = _read("scripts/orchestration-audit.sh")
    assert "check_http_expect" in body
    assert "check_http_any_expect" in body
    assert "com.jessekemp.cortex-site-3001" in body
    assert "com.jessekemp.cortex-bridge-8765" in body


def test_macro_test_uses_strict_probe_contract() -> None:
    body = _read("scripts/codex/macro-test.sh")
    assert 'code="$(curl' in body
    assert "probe_any" in body
    assert "winfield-health" in body
    assert 'expect="${2:-}"' in body
