#!/usr/bin/env python3
"""
Cortex V2 Prime Activation Script

This script activates and tests all V2 Prime components:
- Engine A: Context Absorber
- Engine B: Synthesis Core (Context Graph)
- Engine C: Action Broker
- IAP Handler

Usage:
    python activate_v2.py           # Full activation
    python activate_v2.py --test    # Run tests only
    python activate_v2.py --import  # Import portfolio data only
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Ensure we can import cortex modules
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def print_header(title: str):
    print()
    print("+" + "=" * 58 + "+")
    print(f"|{title:^58}|")
    print("+" + "=" * 58 + "+")
    print()


def print_status(name: str, success: bool, message: str = ""):
    icon = "[OK]" if success else "[--]"
    msg = f": {message}" if message else ""
    print(f"  {icon} {name}{msg}")


def test_engines():
    """Test all V2 Prime engines."""
    print_header("V2 PRIME ENGINE TEST")
    
    results = {"passed": 0, "failed": 0}
    
    # Test Bridge initialization
    try:
        from cortex.bridge import CortexBridge
        bridge = CortexBridge()
        status = bridge.get_v2_status()
        
        print_status("Bridge initialization", True)
        print_status("V2 Prime available", status.get("v2_available", False))
        
        if status.get("v2_available"):
            results["passed"] += 1
        else:
            results["failed"] += 1
            
    except Exception as e:
        print_status("Bridge initialization", False, str(e))
        results["failed"] += 1
        return results
    
    # Test Engine A: Absorber
    try:
        if bridge.absorber:
            print_status("Engine A: Absorber", True, "Initialized")
            results["passed"] += 1
        else:
            print_status("Engine A: Absorber", False, "Not available")
            results["failed"] += 1
    except Exception as e:
        print_status("Engine A: Absorber", False, str(e))
        results["failed"] += 1
    
    # Test Engine B: Synthesis Core
    try:
        if bridge.synthesis:
            stats = bridge.get_graph_stats()
            node_count = stats.get("total_nodes", 0)
            print_status("Engine B: Synthesis", True, f"{node_count} nodes in graph")
            results["passed"] += 1
        else:
            print_status("Engine B: Synthesis", False, "Not available")
            results["failed"] += 1
    except Exception as e:
        print_status("Engine B: Synthesis", False, str(e))
        results["failed"] += 1
    
    # Test Engine C: Broker
    try:
        if bridge.broker:
            broker_status = bridge.get_broker_status()
            pending = broker_status.get("pending_count", 0)
            print_status("Engine C: Broker", True, f"{pending} pending interventions")
            results["passed"] += 1
        else:
            print_status("Engine C: Broker", False, "Not available")
            results["failed"] += 1
    except Exception as e:
        print_status("Engine C: Broker", False, str(e))
        results["failed"] += 1
    
    # Test IAP Handler
    try:
        if bridge.iap:
            print_status("IAP Handler", True, "Ready for agent communication")
            results["passed"] += 1
        else:
            print_status("IAP Handler", False, "Not available")
            results["failed"] += 1
    except Exception as e:
        print_status("IAP Handler", False, str(e))
        results["failed"] += 1
    
    # Test Graph operations
    try:
        result = bridge.add_graph_node("lesson", "test_lesson", {"description": "Activation test"})
        if result.get("success"):
            print_status("Graph add node", True, result.get("node_id"))
            results["passed"] += 1
        else:
            print_status("Graph add node", False, result.get("error"))
            results["failed"] += 1
    except Exception as e:
        print_status("Graph add node", False, str(e))
        results["failed"] += 1
    
    # Test Intervention creation
    try:
        intervention = bridge.broker.trigger_learning_insight(
            insight_type="activation_test",
            insight="V2 Prime activation completed successfully",
            data={"timestamp": datetime.now().isoformat()},
        )
        print_status("Intervention creation", True, f"ID: {intervention.id}")
        results["passed"] += 1
    except Exception as e:
        print_status("Intervention creation", False, str(e))
        results["failed"] += 1
    
    return results


def import_portfolio():
    """Import existing portfolio data into the context graph."""
    print_header("PORTFOLIO IMPORT")
    
    from cortex.bridge import CortexBridge
    bridge = CortexBridge()
    
    if not bridge.synthesis:
        print("[FAIL] V2 Prime Synthesis Core not available")
        return False
    
    portfolio_path = Path.home() / ".claude" / "portfolio"
    print(f"Source: {portfolio_path}")
    print()
    
    result = bridge.synthesis.import_portfolio_data(portfolio_path)
    
    print("Imported:")
    total = 0
    for category, count in result.items():
        print(f"  {category}: {count}")
        total += count
    
    print()
    print(f"Total entities imported: {total}")
    
    # Show updated stats
    stats = bridge.get_graph_stats()
    print()
    print(f"Graph now has {stats.get('total_nodes', 0)} nodes and {stats.get('total_edges', 0)} edges")
    
    return total > 0


def start_absorber():
    """Start the Context Absorber with default sources."""
    print_header("STARTING CONTEXT ABSORBER")
    
    from cortex.bridge import CortexBridge
    from cortex.engines.absorber import FileWatcher, ShellListener, IDEBridge
    
    bridge = CortexBridge()
    
    if not bridge.absorber:
        print("[FAIL] V2 Prime Absorber not available")
        return False
    
    # Register sources
    root_dir = bridge.root_dir
    
    try:
        # FileWatcher
        watcher = FileWatcher([root_dir])
        bridge.absorber.register_source(watcher)
        print_status("FileWatcher", True, str(root_dir))
    except Exception as e:
        print_status("FileWatcher", False, str(e))
    
    try:
        # ShellListener
        listener = ShellListener()
        bridge.absorber.register_source(listener)
        print_status("ShellListener", True, str(listener.history_file))
    except Exception as e:
        print_status("ShellListener", False, str(e))
    
    try:
        # IDEBridge
        ide = IDEBridge()
        bridge.absorber.register_source(ide)
        print_status("IDEBridge", True, "Ready for MCP signals")
    except Exception as e:
        print_status("IDEBridge", False, str(e))
    
    # Start all sources
    print()
    print("Starting sources...")
    bridge.absorber.start_all()
    
    status = bridge.absorber.get_status()
    running = sum(1 for s in status.get("sources", []) if s.get("running"))
    total = len(status.get("sources", []))
    
    print()
    print(f"[OK] Absorber running with {running}/{total} sources")
    
    return True


def full_activation():
    """Perform full V2 Prime activation."""
    print_header("CORTEX V2 PRIME ACTIVATION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Test engines
    test_results = test_engines()
    
    if test_results["failed"] > 0:
        print()
        print(f"[WARN] {test_results['failed']} tests failed, but continuing...")
    
    # Step 2: Import portfolio data
    import_portfolio()
    
    # Step 3: Final status
    print_header("ACTIVATION COMPLETE")
    
    from cortex.bridge import CortexBridge
    bridge = CortexBridge()
    status = bridge.get_v2_status()
    
    print("V2 Prime Status:")
    print(f"  Engines: {3 if status.get('v2_available') else 0}/3 active")
    print(f"  IAP: {'Ready' if status.get('iap') else 'Unavailable'}")
    
    graph_stats = status.get("graph_stats", {})
    print(f"  Graph: {graph_stats.get('total_nodes', 0)} nodes")
    
    broker_status = status.get("broker_status", {})
    print(f"  Interventions: {broker_status.get('pending_count', 0)} pending")
    
    print()
    print("Next steps:")
    print("  1. Run 'cortex v2 status' to check status")
    print("  2. Run 'cortex graph query --type project' to view projects")
    print("  3. Run 'cortex interventions list' to view pending actions")
    print("  4. MCP tools are ready for agent integration")
    print()
    
    return test_results["failed"] == 0


def main():
    parser = argparse.ArgumentParser(description="Cortex V2 Prime Activation")
    parser.add_argument("--test", action="store_true", help="Run tests only")
    parser.add_argument("--import", dest="import_only", action="store_true", help="Import portfolio data only")
    parser.add_argument("--start", action="store_true", help="Start absorber only")
    
    args = parser.parse_args()
    
    if args.test:
        results = test_engines()
        print()
        print(f"Results: {results['passed']} passed, {results['failed']} failed")
        sys.exit(0 if results["failed"] == 0 else 1)
    
    if args.import_only:
        success = import_portfolio()
        sys.exit(0 if success else 1)
    
    if args.start:
        success = start_absorber()
        sys.exit(0 if success else 1)
    
    # Full activation
    success = full_activation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
