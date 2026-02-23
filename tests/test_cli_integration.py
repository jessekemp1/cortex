#!/usr/bin/env python3
"""
CLI Integration Test Suite for Phase 1 Deep Mode
Tests all new CLI commands: deep, quick, auto, config
"""

import subprocess
import sys
from pathlib import Path

import pytest


CORTEX_DIR = str(Path(__file__).parent.parent)
ROOT_DIR = str(Path(__file__).parent.parent.parent)
CLI_SCRIPT = str(Path(CORTEX_DIR) / "cli.py")


def run_command(cmd, expect_success=True):
    """Run a CLI command and return result.

    Uses absolute path to cli.py with PYTHONPATH set to cortex/ so
    module imports (intelligence.*, bridge, etc.) resolve correctly.
    """
    # Replace bare "python cli.py" with absolute path + explicit --root
    cmd = cmd.replace("python cli.py", f"{sys.executable} {CLI_SCRIPT} --root {ROOT_DIR}")
    import os

    env = {**os.environ, "PYTHONPATH": CORTEX_DIR}
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=30, env=env
    )

    if expect_success:
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            print(f"   stderr: {result.stderr}")
            return False, result

    return True, result



def test_cli_help():
    """Test 1: CLI help includes deep mode commands"""
    print("\n" + "=" * 60)
    print("TEST 1: CLI Help")
    print("=" * 60)

    success, result = run_command("python cli.py --help")

    assert success, "CLI help command failed"

    # Check for deep mode section
    assert "Deep Mode" in result.stdout, "Help missing 'Deep Mode' section"
    print("✅ Help includes 'Deep Mode' section")

    # Check for commands
    commands = ["cortex deep", "cortex quick", "cortex auto", "cortex config"]
    for cmd in commands:
        assert cmd in result.stdout, f"Help missing '{cmd}'"
        print(f"✅ Help includes '{cmd}'")



def test_config_show():
    """Test 2: Config --show command"""
    print("\n" + "=" * 60)
    print("TEST 2: Config --show")
    print("=" * 60)

    success, result = run_command("python cli.py config --show")
    assert success, "Config --show command failed"

    # Check output contains expected elements
    expected = ["Default Mode:", "Deep Mode Config:", "Fast Mode Config:", "Git days:"]
    for item in expected:
        assert item in result.stdout, f"Output missing '{item}'"
        print(f"✅ Output contains '{item}'")



def test_deep_command():
    """Test 3: Deep analysis command"""
    print("\n" + "=" * 60)
    print("TEST 3: Deep Analysis")
    print("=" * 60)

    success, result = run_command("python cli.py deep cortex")
    assert success, "Deep command failed"

    # Check output contains expected elements (format updated 2026-02)
    expected = ["Deep Intelligence", "Git Analysis", "Code Quality"]
    for item in expected:
        assert item in result.stdout, f"Output missing '{item}'"
        print(f"✅ Output contains '{item}'")

    # Check for health score format (e.g., "80/100")
    assert "/100" in result.stdout, "Output missing health score"
    print("✅ Output includes health score (X/100 format)")
    print("✅ Deep command executed successfully")



def test_deep_json():
    """Test 4: Deep analysis with JSON output"""
    print("\n" + "=" * 60)
    print("TEST 4: Deep Analysis --json")
    print("=" * 60)

    success, result = run_command("python cli.py deep cortex --json")
    assert success, "Deep --json command failed"

    # Check it's valid JSON by parsing
    import json

    data = json.loads(result.stdout)

    # Check required keys
    required_keys = ["timestamp", "project", "mode", "health", "git", "quality"]
    for key in required_keys:
        assert key in data, f"JSON missing '{key}'"
        print(f"✅ JSON contains '{key}'")

    print(f"✅ Valid JSON output ({len(result.stdout)} bytes)")



def test_quick_command():
    """Test 5: Quick mode command (expects fallback message)"""
    print("\n" + "=" * 60)
    print("TEST 5: Quick Mode (Fallback)")
    print("=" * 60)

    # Quick mode expected to fail gracefully with suggestion
    success, result = run_command("python cli.py quick cortex", expect_success=False)

    # Check for expected fallback message
    assert (
        "not yet fully implemented" in result.stdout or "Suggestion" in result.stdout
    ), "Quick mode missing fallback message"
    print("✅ Quick mode shows expected fallback message")



def test_auto_command():
    """Test 6: Auto mode command"""
    print("\n" + "=" * 60)
    print("TEST 6: Auto Mode")
    print("=" * 60)

    success, result = run_command("python cli.py auto cortex")
    assert success, "Auto command failed"

    # Auto should select deep mode and show analysis
    assert (
        "Deep Intelligence" in result.stdout or "Health" in result.stdout
    ), "Auto mode didn't produce expected output"
    print("✅ Auto mode selected deep and ran successfully")


def main():
    """Run all CLI integration tests"""
    print("\n" + "#" * 60)
    print("# PHASE 1 CLI INTEGRATION TEST SUITE")
    print("#" * 60)

    tests = [
        ("CLI Help", test_cli_help),
        ("Config Show", test_config_show),
        ("Deep Command", test_deep_command),
        ("Deep JSON", test_deep_json),
        ("Quick Fallback", test_quick_command),
        ("Auto Command", test_auto_command),
    ]

    results = {}
    for name, test_func in tests:
        try:
            test_func()
            results[name] = True
        except Exception as e:
            print(f"\n❌ Test '{name}' failed: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED - CLI INTEGRATION COMPLETE")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("⚠️  SOME TESTS FAILED - See details above")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
