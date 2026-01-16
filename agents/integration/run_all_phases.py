"""Run all integration phases sequentially"""

#!/usr/bin/env python3
import sys
from pathlib import Path

# Add paths
ROOT_DIR = Path(__file__).parent.parent.parent.parent
CORTEX_DIR = ROOT_DIR / "cortex"
LOCAL_ORCHESTRATOR_DIR = ROOT_DIR / "local-orchestrator"

sys.path.insert(0, str(CORTEX_DIR))
sys.path.insert(0, str(LOCAL_ORCHESTRATOR_DIR))

# Import using importlib to handle path issues
import importlib.util

# Import TeamCoordinator
team_coord_spec = importlib.util.spec_from_file_location(
    "team_coordinator", CORTEX_DIR / "agents" / "integration" / "team_coordinator.py"
)
team_coord_module = importlib.util.module_from_spec(team_coord_spec)
team_coord_spec.loader.exec_module(team_coord_module)
TeamCoordinator = team_coord_module.TeamCoordinator

# Import Phase2Agent
phase2_spec = importlib.util.spec_from_file_location(
    "phase2_agent", CORTEX_DIR / "agents" / "integration" / "phase2_agent.py"
)
phase2_module = importlib.util.module_from_spec(phase2_spec)
phase2_spec.loader.exec_module(phase2_module)
Phase2Agent = phase2_module.Phase2Agent

# Import Phase3Agent
phase3_spec = importlib.util.spec_from_file_location(
    "phase3_agent", CORTEX_DIR / "agents" / "integration" / "phase3_agent.py"
)
phase3_module = importlib.util.module_from_spec(phase3_spec)
phase3_spec.loader.exec_module(phase3_module)
Phase3Agent = phase3_module.Phase3Agent

# Import Phase1Agent from local-orchestrator
phase1_spec = importlib.util.spec_from_file_location(
    "phase1_agent",
    LOCAL_ORCHESTRATOR_DIR / "agents" / "integration" / "phase1_agent.py",
)
phase1_module = importlib.util.module_from_spec(phase1_spec)
phase1_spec.loader.exec_module(phase1_module)
Phase1Agent = phase1_module.Phase1Agent


def main():
    """Run all phases sequentially"""
    print("=" * 60)
    print("CORTEX-LOCAL-ORCHESTRATOR INTEGRATION")
    print("Running all phases sequentially")
    print("=" * 60)
    print()

    # Create coordinator
    coordinator = TeamCoordinator(root_dir=ROOT_DIR)

    # Register all phase agents
    coordinator.register_agent(Phase1Agent(root_dir=ROOT_DIR))
    coordinator.register_agent(Phase2Agent(root_dir=ROOT_DIR))
    coordinator.register_agent(Phase3Agent(root_dir=ROOT_DIR))

    # Execute all phases
    results = coordinator.execute_all_phases()

    # Print results
    print()
    print("=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Overall Status: {results['overall_status']}")
    print(f"Phases Completed: {results['phases_completed']}/{results['total_phases']}")
    print(f"Phases Failed: {results['phases_failed']}")
    print()

    for phase_result in results["execution_log"]:
        status_icon = "✓" if phase_result["success"] else "✗"
        print(f"{status_icon} Phase {phase_result['phase']}: {phase_result['phase_name']}")
        print(f"   Status: {phase_result['message']}")
        if phase_result.get("errors"):
            print(f"   Errors: {len(phase_result['errors'])}")
        print()

    # Exit with appropriate code
    if results["overall_status"] == "completed":
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
