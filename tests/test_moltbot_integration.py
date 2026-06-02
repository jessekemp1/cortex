#!/usr/bin/env python3
"""
Test script for Moltbot-Cortex integration.

Tests:
1. Cortex Bridge API starts and responds
2. Health and status endpoints work
3. Intelligence queries work
4. Anomaly detection works
5. Moltbot skills can query Cortex

Usage:
    python cortex/test_moltbot_integration.py
"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


def _bridge_running() -> bool:
    """Quick TCP probe — is the Cortex Bridge listening on 127.0.0.1:8765?"""
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.5):
            return True
    except OSError:
        return False


# These tests require a running Cortex Bridge (port 8765). Skip when it's
# not up — brilliant testers running `pytest` cold won't have it.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _bridge_running(),
        reason="Cortex Bridge not running on 127.0.0.1:8765 (start with `python -m api.bridge_endpoint`)",
    ),
]

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

API_BASE = "http://127.0.0.1:8765"
API_PROCESS = None


def print_test(msg):
    """Print test message."""
    print(f"{BLUE}► {msg}{RESET}")


def print_success(msg):
    """Print success message."""
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg):
    """Print error message."""
    print(f"{RED}✗ {msg}{RESET}")


def print_warning(msg):
    """Print warning message."""
    print(f"{YELLOW}⚠ {msg}{RESET}")


def start_api():
    """Start Cortex Bridge API."""
    global API_PROCESS
    print_test("Starting Cortex Bridge API...")

    try:
        API_PROCESS = subprocess.Popen(
            [sys.executable, "-m", "cortex.api.bridge_endpoint"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent.parent,
        )

        # Wait for API to be ready
        for i in range(30):
            try:
                resp = requests.get(f"{API_BASE}/health", timeout=1)
                if resp.status_code == 200:
                    print_success("Cortex Bridge API started")
                    return True
            except requests.exceptions.RequestException:
                time.sleep(0.5)

        print_error("API failed to start within 15 seconds")
        return False

    except Exception as e:
        print_error(f"Failed to start API: {e}")
        return False


def stop_api():
    """Stop Cortex Bridge API."""
    global API_PROCESS
    if API_PROCESS:
        print_test("Stopping Cortex Bridge API...")
        API_PROCESS.terminate()
        API_PROCESS.wait(timeout=5)
        print_success("API stopped")


def test_health():
    """Test health endpoint."""
    print_test("Testing /health endpoint...")
    resp = requests.get(f"{API_BASE}/health", timeout=5)
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    data = resp.json()
    assert data.get("status") == "healthy", f"Unexpected status: {data.get('status')}"
    print_success(f"Health check passed: {data}")


def test_status():
    """Test status endpoint."""
    print_test("Testing /status endpoint...")
    resp = requests.get(f"{API_BASE}/status", timeout=5)
    assert resp.status_code == 200, f"Status check failed: {resp.status_code}"
    data = resp.json()
    print_success(f"Status: {json.dumps(data, indent=2)}")


def test_intelligence_query():
    """Test intelligence query endpoint."""
    print_test("Testing /intelligence/query endpoint...")
    payload = {
        "request": "test query for integration",
        "project": "cortex",
        "query_type": "spec",
        "use_cache": False,
    }
    resp = requests.post(
        f"{API_BASE}/intelligence/query",
        json=payload,
        timeout=30,
    )
    assert resp.status_code == 200, f"Intelligence query failed: {resp.status_code}"
    data = resp.json()
    print_success("Intelligence query succeeded")
    print(f"  Response keys: {list(data.keys())}")
    assert "error" not in data, f"Query returned error: {data['error']}"


def test_anomalies():
    """Test anomaly detection endpoint."""
    print_test("Testing /anomalies endpoint...")
    resp = requests.get(f"{API_BASE}/anomalies", timeout=5)
    assert resp.status_code == 200, f"Anomaly check failed: {resp.status_code}"
    data = resp.json()
    count = data.get("count", 0)
    print_success(f"Anomaly detection works - found {count} anomalies")
    if count > 0:
        print("  Sample anomaly:")
        sample = data["anomalies"][0]
        print(f"    Type: {sample.get('type')}")
        print(f"    Severity: {sample.get('severity')}")
        print(f"    Title: {sample.get('title')}")


def test_recommendations():
    """Test recommendations endpoint."""
    print_test("Testing /intelligence/recommendations endpoint...")
    resp = requests.get(
        f"{API_BASE}/intelligence/recommendations",
        params={"limit": 3},
        timeout=10,
    )
    assert resp.status_code == 200, f"Recommendations failed: {resp.status_code}"
    data = resp.json()
    print_success("Recommendations endpoint works")
    print(f"  Response keys: {list(data.keys())}")


@pytest.mark.xfail(reason="Legacy ~/clawd/skills/ directory no longer exists")
def test_moltbot_skills():
    """Test Moltbot skills."""
    print_test("Checking Moltbot skills...")

    skills_dir = Path.home() / "clawd" / "skills"

    # Check cortex-query skill
    cortex_query = skills_dir / "cortex-query" / "SKILL.md"
    assert cortex_query.exists(), f"cortex-query skill not found: {cortex_query}"
    print_success(f"cortex-query skill exists: {cortex_query}")

    # Check cortex-notify skill
    cortex_notify = skills_dir / "cortex-notify" / "SKILL.md"
    assert cortex_notify.exists(), f"cortex-notify skill not found: {cortex_notify}"
    print_success(f"cortex-notify skill exists: {cortex_notify}")


def test_skill_command():
    """Test a sample skill command (curl from skill)."""
    print_test("Testing skill command (curl health check)...")
    result = subprocess.run(
        ["curl", "-s", f"{API_BASE}/health"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, "curl command failed"
    data = json.loads(result.stdout)
    assert data.get("status") == "healthy", f"Unexpected status: {data.get('status')}"
    print_success("Skill command works - curl successfully queried API")


def main():
    """Run all tests."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Moltbot-Cortex Integration Test Suite{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

    results = {}

    try:
        # Start API
        if not start_api():
            print_error("Failed to start API. Aborting tests.")
            return 1

        time.sleep(2)  # Give API time to initialize

        # Run tests
        for name, func in [
            ("health", test_health),
            ("status", test_status),
            ("intelligence", test_intelligence_query),
            ("anomalies", test_anomalies),
            ("recommendations", test_recommendations),
            ("skills", test_moltbot_skills),
            ("skill_command", test_skill_command),
        ]:
            try:
                func()
                results[name] = True
            except Exception as e:
                print_error(f"{name} failed: {e}")
                results[name] = False
            print()

    finally:
        # Always stop API
        stop_api()

    # Summary
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}Test Results Summary{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {test_name:20s} {status}")

    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
