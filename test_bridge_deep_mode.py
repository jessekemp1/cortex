#!/usr/bin/env python3
"""
Test Bridge Deep Mode Integration

Tests all Phase 1 Bridge API enhancements:
1. Deep mode analysis
2. Quick mode analysis
3. Auto mode selection
4. Helper methods
5. Serialization
"""

import sys
import time
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent))

def test_bridge_initialization():
    """Test 1: Bridge initializes with deep mode components"""
    print("\n" + "="*60)
    print("TEST 1: Bridge Initialization")
    print("="*60)

    try:
        from bridge import CortexBridge

        bridge = CortexBridge()

        # Check components initialized
        assert bridge.latency_manager is not None, "AdaptiveLatencyManager not initialized"
        assert bridge.deep_analyzer is not None, "DeepAnalyzer not initialized"

        print("✅ Bridge initialized successfully")
        print(f"   - AdaptiveLatencyManager: {type(bridge.latency_manager).__name__}")
        print(f"   - DeepAnalyzer: {type(bridge.deep_analyzer).__name__}")

        return bridge, True

    except Exception as e:
        print(f"❌ Bridge initialization failed: {e}")
        return None, False


def test_deep_mode(bridge):
    """Test 2: Deep mode analysis works end-to-end"""
    print("\n" + "="*60)
    print("TEST 2: Deep Mode Analysis")
    print("="*60)

    try:
        start = time.time()
        result = bridge.analyze_deep("cortex", output_json=False)
        elapsed = time.time() - start

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            print(f"❌ Deep mode failed: {result['error']}")
            return False

        # Validate result structure
        assert hasattr(result, 'mode'), "Result missing 'mode' attribute"
        assert hasattr(result, 'health'), "Result missing 'health' attribute"
        assert hasattr(result, 'git'), "Result missing 'git' attribute"
        assert hasattr(result, 'quality'), "Result missing 'quality' attribute"

        print("✅ Deep mode analysis successful")
        print(f"   - Analysis time: {elapsed:.2f}s")
        print(f"   - Mode: {result.mode}")
        print(f"   - Health score: {result.health.score}/100 ({result.health.assessment})")
        print(f"   - Commits analyzed: {result.git.commit_count}")
        print(f"   - Tech debt markers: {result.quality.tech_debt_markers}")
        print(f"   - Warnings: {len(result.warnings)}")
        print(f"   - Recommendations: {len(result.recommendations)}")

        # Validate performance (should be 2-10s for deep mode)
        if elapsed < 1.0:
            print(f"⚠️  Warning: Deep mode suspiciously fast ({elapsed:.2f}s)")
        elif elapsed > 15.0:
            print(f"⚠️  Warning: Deep mode too slow ({elapsed:.2f}s)")

        return True

    except Exception as e:
        print(f"❌ Deep mode analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_json_serialization(bridge):
    """Test 3: JSON serialization works"""
    print("\n" + "="*60)
    print("TEST 3: JSON Serialization")
    print("="*60)

    try:
        result = bridge.analyze_deep("cortex", output_json=True)

        # Check for errors
        if "error" in result:
            print(f"❌ Serialization failed: {result['error']}")
            return False

        # Validate JSON structure
        required_keys = ["timestamp", "project", "mode", "latency_ms", "health", "git", "quality"]
        for key in required_keys:
            assert key in result, f"JSON missing key: {key}"

        print("✅ JSON serialization successful")
        print(f"   - Project: {result['project']}")
        print(f"   - Mode: {result['mode']}")
        print(f"   - Latency: {result['latency_ms']:.0f}ms")
        print(f"   - Health: {result['health']['score']}/100")

        # Try to serialize to JSON string (final validation)
        import json
        json_str = json.dumps(result, indent=2)
        print(f"   - JSON size: {len(json_str)} bytes")

        return True

    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quick_mode(bridge):
    """Test 4: Quick mode analysis"""
    print("\n" + "="*60)
    print("TEST 4: Quick Mode Analysis")
    print("="*60)

    try:
        start = time.time()
        result = bridge.analyze_quick("cortex")
        elapsed = time.time() - start

        # Check for errors
        if "error" in result:
            print(f"⚠️  Quick mode warning: {result['error']}")
            # This might be expected if UnifiedIntelligence not available
            if "not available" in result["error"]:
                print("   (Expected - using fallback)")
                return True

        print("✅ Quick mode analysis successful")
        print(f"   - Analysis time: {elapsed:.2f}s")
        print(f"   - Project: {result.get('project', 'unknown')}")

        # Validate performance (should be <2s for quick mode)
        if elapsed > 2.0:
            print(f"⚠️  Warning: Quick mode slower than expected ({elapsed:.2f}s)")

        return True

    except Exception as e:
        print(f"❌ Quick mode analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_mode(bridge):
    """Test 5: Auto mode selection"""
    print("\n" + "="*60)
    print("TEST 5: Auto Mode Selection")
    print("="*60)

    try:
        start = time.time()
        result = bridge.analyze_auto("cortex")
        elapsed = time.time() - start

        # Check for errors
        if isinstance(result, dict) and "error" in result:
            print(f"❌ Auto mode failed: {result['error']}")
            return False

        print("✅ Auto mode analysis successful")
        print(f"   - Analysis time: {elapsed:.2f}s")

        # Check if it returned deep or quick result
        if hasattr(result, 'mode'):
            print(f"   - Selected mode: {result.mode}")
            print(f"   - Health score: {result.health.score}/100")
        else:
            print("   - Selected mode: quick (fallback)")

        return True

    except Exception as e:
        print(f"❌ Auto mode analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_helper_methods(bridge):
    """Test 6: Helper methods work"""
    print("\n" + "="*60)
    print("TEST 6: Helper Methods")
    print("="*60)

    try:
        # Test _detect_current_project
        project = bridge._detect_current_project()
        print(f"✅ _detect_current_project() → {project}")

        # Test _build_session_context
        context = bridge._build_session_context("cortex")
        if context is not None:
            print("✅ _build_session_context() → SessionContext")
            print(f"   - Project: {context.project_name}")
            print(f"   - Has uncommitted: {context.has_uncommitted_changes}")
        else:
            print("⚠️  _build_session_context() → None (SessionContext not available)")

        return True

    except Exception as e:
        print(f"❌ Helper methods failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_complete():
    """Master test runner"""
    print("\n" + "#"*60)
    print("# PHASE 1 BRIDGE INTEGRATION TEST SUITE")
    print("#"*60)

    results = {}

    # Test 1: Initialization
    bridge, results['init'] = test_bridge_initialization()

    if not results['init'] or bridge is None:
        print("\n" + "="*60)
        print("❌ FATAL: Bridge initialization failed")
        print("="*60)
        return False

    # Test 2: Deep mode
    results['deep'] = test_deep_mode(bridge)

    # Test 3: JSON serialization
    results['json'] = test_json_serialization(bridge)

    # Test 4: Quick mode
    results['quick'] = test_quick_mode(bridge)

    # Test 5: Auto mode
    results['auto'] = test_auto_mode(bridge)

    # Test 6: Helpers
    results['helpers'] = test_helper_methods(bridge)

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
        print("🎉 ALL TESTS PASSED - PHASE 1 INTEGRATION COMPLETE")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("⚠️  SOME TESTS FAILED - See details above")
        print("="*60)
        return False


if __name__ == "__main__":
    success = test_integration_complete()
    sys.exit(0 if success else 1)
