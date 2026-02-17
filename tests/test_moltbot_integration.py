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
import subprocess
import sys
import time
from pathlib import Path

import requests

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
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "healthy":
                print_success(f"Health check passed: {data}")
                return True
        print_error(f"Health check failed: {resp.status_code}")
        return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False


def test_status():
    """Test status endpoint."""
    print_test("Testing /status endpoint...")
    try:
        resp = requests.get(f"{API_BASE}/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_success(f"Status: {json.dumps(data, indent=2)}")
            return True
        print_error(f"Status check failed: {resp.status_code}")
        return False
    except Exception as e:
        print_error(f"Status check error: {e}")
        return False


def test_intelligence_query():
    """Test intelligence query endpoint."""
    print_test("Testing /intelligence/query endpoint...")
    try:
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

        if resp.status_code == 200:
            data = resp.json()
            print_success("Intelligence query succeeded")
            print(f"  Response keys: {list(data.keys())}")
            if "error" in data:
                print_warning(f"  Query returned error: {data['error']}")
                return False
            return True
        print_error(f"Intelligence query failed: {resp.status_code}")
        return False
    except Exception as e:
        print_error(f"Intelligence query error: {e}")
        return False


def test_anomalies():
    """Test anomaly detection endpoint."""
    print_test("Testing /anomalies endpoint...")
    try:
        resp = requests.get(f"{API_BASE}/anomalies", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            count = data.get("count", 0)
            print_success(f"Anomaly detection works - found {count} anomalies")
            if count > 0:
                print("  Sample anomaly:")
                sample = data["anomalies"][0]
                print(f"    Type: {sample.get('type')}")
                print(f"    Severity: {sample.get('severity')}")
                print(f"    Title: {sample.get('title')}")
            return True
        print_error(f"Anomaly check failed: {resp.status_code}")
        return False
    except Exception as e:
        print_error(f"Anomaly check error: {e}")
        return False


def test_recommendations():
    """Test recommendations endpoint."""
    print_test("Testing /intelligence/recommendations endpoint...")
    try:
        resp = requests.get(
            f"{API_BASE}/intelligence/recommendations",
            params={"limit": 3},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            print_success("Recommendations endpoint works")
            print(f"  Response keys: {list(data.keys())}")
            return True
        print_error(f"Recommendations failed: {resp.status_code}")
        return False
    except Exception as e:
        print_error(f"Recommendations error: {e}")
        return False


def test_moltbot_skills():
    """Test Moltbot skills."""
    print_test("Checking Moltbot skills...")

    skills_dir = Path.home() / "clawd" / "skills"

    # Check cortex-query skill
    cortex_query = skills_dir / "cortex-query" / "SKILL.md"
    if cortex_query.exists():
        print_success(f"cortex-query skill exists: {cortex_query}")
    else:
        print_error(f"cortex-query skill not found: {cortex_query}")
        return False

    # Check cortex-notify skill
    cortex_notify = skills_dir / "cortex-notify" / "SKILL.md"
    if cortex_notify.exists():
        print_success(f"cortex-notify skill exists: {cortex_notify}")
    else:
        print_error(f"cortex-notify skill not found: {cortex_notify}")
        return False

    return True


def test_skill_command():
    """Test a sample skill command (curl from skill)."""
    print_test("Testing skill command (curl health check)...")
    try:
        result = subprocess.run(
            ["curl", "-s", f"{API_BASE}/health"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("status") == "healthy":
                print_success("Skill command works - curl successfully queried API")
                return True
        print_error("Skill command failed")
        return False
    except Exception as e:
        print_error(f"Skill command error: {e}")
        return False


def main():
    """Run all tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Moltbot-Cortex Integration Test Suite{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    results = {}

    try:
        # Start API
        if not start_api():
            print_error("Failed to start API. Aborting tests.")
            return 1

        time.sleep(2)  # Give API time to initialize

        # Run tests
        results["health"] = test_health()
        print()

        results["status"] = test_status()
        print()

        results["intelligence"] = test_intelligence_query()
        print()

        results["anomalies"] = test_anomalies()
        print()

        results["recommendations"] = test_recommendations()
        print()

        results["skills"] = test_moltbot_skills()
        print()

        results["skill_command"] = test_skill_command()
        print()

    finally:
        # Always stop API
        stop_api()

    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Test Results Summary{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {test_name:20s} {status}")

    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
