"""Team coordinator for managing sequential execution of agent teams"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import base coordination agent
sys.path.insert(0, str(Path(__file__).parent))
from base_coordination_agent import BaseCoordinationAgent


class TeamCoordinator:
    """Coordinates sequential execution of agent teams"""

    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize team coordinator.

        Args:
            root_dir: Root directory of the workspace
        """
        self.root_dir = root_dir or Path("/Users/jesse.kemp/Dev")
        self.agents: List[BaseCoordinationAgent] = []
        self.execution_log: List[Dict[str, Any]] = []

    def register_agent(self, agent: BaseCoordinationAgent):
        """Register an agent team"""
        self.agents.append(agent)
        # Sort by phase number
        self.agents.sort(key=lambda a: a.phase_number)

    def execute_all_phases(self) -> Dict[str, Any]:
        """
        Execute all registered phases sequentially.

        Returns:
            Dictionary with execution results
        """
        results = {
            "total_phases": len(self.agents),
            "phases_completed": 0,
            "phases_failed": 0,
            "execution_log": [],
            "overall_status": "pending",
        }

        for agent in self.agents:
            phase_result = self._execute_phase(agent)
            results["execution_log"].append(phase_result)

            if phase_result["success"]:
                results["phases_completed"] += 1
            else:
                results["phases_failed"] += 1
                # Stop on first failure (sequential execution)
                results["overall_status"] = "failed"
                results["failed_at_phase"] = agent.phase_number
                break

        if results["phases_completed"] == results["total_phases"]:
            results["overall_status"] = "completed"
        elif (
            results["phases_failed"] == 0 and results["phases_completed"] < results["total_phases"]
        ):
            results["overall_status"] = "in_progress"

        return results

    def _execute_phase(self, agent: BaseCoordinationAgent) -> Dict[str, Any]:
        """Execute a single phase"""
        phase_result = {
            "phase": agent.phase_number,
            "phase_name": agent.phase_name,
            "success": False,
            "message": "",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "errors": [],
        }

        try:
            # Check dependencies
            if not agent.check_dependencies():
                phase_result["success"] = False
                phase_result["message"] = f"Dependencies not met for Phase {agent.phase_number}"
                phase_result["errors"].append(phase_result["message"])
                return phase_result

            # Start phase
            agent.start_phase()

            # Execute phase
            result = agent.execute_phase()

            # Record result
            phase_result["success"] = result.success
            phase_result["message"] = result.message
            phase_result["data"] = result.data
            phase_result["end_time"] = datetime.now().isoformat()

            # Mark phase complete if successful
            if result.success:
                agent.complete_phase(True, result.message)
            else:
                agent.complete_phase(False, result.message)
                phase_result["errors"].extend(agent.progress.get("errors", []))

        except Exception as e:
            phase_result["success"] = False
            phase_result["message"] = f"Exception during phase execution: {str(e)}"
            phase_result["errors"].append(str(e))
            phase_result["end_time"] = datetime.now().isoformat()
            agent.complete_phase(False, phase_result["message"])

        return phase_result

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all phases"""
        status = {"total_phases": len(self.agents), "phases": []}

        for agent in self.agents:
            phase_status = {
                "phase": agent.phase_number,
                "phase_name": agent.phase_name,
                "progress": agent.report_progress(),
                "dependencies_met": agent.check_dependencies(),
            }
            status["phases"].append(phase_status)

        return status
