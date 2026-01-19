#!/usr/bin/env python3
"""
CLI Integration Test Suite for Phase 1 Deep Mode
Tests all new CLI commands: deep, quick, auto, config
"""

import subprocess
import sys

def run_command(cmd, expect_success=True):
    """Run a CLI command and return result"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30
    )

    if expect_success:
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            print(f"   stderr: {result.stderr}")
            return False, result

    return True, result


def test_cli_help():
    """Test 1: CLI help includes deep mode commands"""
    print("\n" + "="*60)
    print("TEST 1: CLI Help")
    print("="*60)

    success, result = run_command("python cli.py --help")

    if not success:
        return False

    # Check for deep mode section
    if "Deep Mode" in result.stdout:
        print("✅ Help includes 'Deep Mode' section")
    else:
        print("❌ Help missing 'Deep Mode' section")
        return False

    # Check for commands
    commands = ["cortex deep", "cortex quick", "cortex auto", "cortex config"]
    for cmd in commands:
        if cmd in result.stdout:
            print(f"✅ Help includes '{cmd}'")
        else:
            print(f"❌ Help missing '{cmd}'")
            return False

    return True


def test_config_show():
    """Test 2: Config --show command"""
    print("\n" + "="*60)
    print("TEST 2: Config --show")
    print("="*60)

    success, result = run_command("python cli.py config --show")

    if not success:
        return False

    # Check output contains expected elements
    expected = ["Default Mode:", "Deep Mode Config:", "Fast Mode Config:", "Git days:"]
    for item in expected:
        if item in result.stdout:
            print(f"✅ Output contains '{item}'")
        else:
            print(f"❌ Output missing '{item}'")
            return False

    return True


def test_deep_command():
    """Test 3: Deep analysis command"""
    print("\n" + "="*60)
    print("TEST 3: Deep Analysis")
    print("="*60)

    success, result = run_command("python cli.py deep cortex")

    if not success:
        return False

    # Check output contains expected elements
    expected = ["Deep Intelligence", "Git Analysis", "Warnings", "Recommendations"]
    for item in expected:
        if item in result.stdout:
            print(f"✅ Output contains '{item}'")
        else:
            print(f"❌ Output missing '{item}'")
            return False

    # Check for health score format (e.g., "80/100")
    if "/100" in result.stdout:
        print("✅ Output includes health score (X/100 format)")
    else:
        print("❌ Output missing health score")
        return False

    print("✅ Deep command executed successfully")
    return True


def test_deep_json():
    """Test 4: Deep analysis with JSON output"""
    print("\n" + "="*60)
    print("TEST 4: Deep Analysis --json")
    print("="*60)

    success, result = run_command("python cli.py deep cortex --json")

    if not success:
        return False

    # Check it's valid JSON by parsing
    try:
        import json
        data = json.loads(result.stdout)

        # Check required keys
        required_keys = ["timestamp", "project", "mode", "health", "git", "quality"]
        for key in required_keys:
            if key in data:
                print(f"✅ JSON contains '{key}'")
            else:
                print(f"❌ JSON missing '{key}'")
                return False

        print(f"✅ Valid JSON output ({len(result.stdout)} bytes)")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False


def test_quick_command():
    """Test 5: Quick mode command (expects fallback message)"""
    print("\n" + "="*60)
    print("TEST 5: Quick Mode (Fallback)")
    print("="*60)

    # Quick mode expected to fail gracefully with suggestion
    success, result = run_command("python cli.py quick cortex", expect_success=False)

    # Check for expected fallback message
    if "not yet fully implemented" in result.stdout or "Suggestion" in result.stdout:
        print("✅ Quick mode shows expected fallback message")
        return True
    else:
        print("❌ Quick mode missing fallback message")
        return False


def test_auto_command():
    """Test 6: Auto mode command"""
    print("\n" + "="*60)
    print("TEST 6: Auto Mode")
    print("="*60)

    success, result = run_command("python cli.py auto cortex")

    if not success:
        return False

    # Auto should select deep mode and show analysis
    if "Deep Intelligence" in result.stdout or "Health" in result.stdout:
        print("✅ Auto mode selected deep and ran successfully")
        return True
    else:
        print("❌ Auto mode didn't produce expected output")
        return False


def main():
    """Run all CLI integration tests"""
    print("\n" + "#"*60)
    print("# PHASE 1 CLI INTEGRATION TEST SUITE")
    print("#"*60)

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
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' raised exception: {e}")
            results[name] = False

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED - CLI INTEGRATION COMPLETE")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("⚠️  SOME TESTS FAILED - See details above")
        print("="*60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
