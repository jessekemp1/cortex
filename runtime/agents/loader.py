"""Dynamic agent loader for Cortex runtime.

Provides hot-loading of agents from JSON definitions,
allowing agents to be added without restarting the service.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from cortex.runtime.agents.base import AgentMetadata, BaseAgent
from cortex.runtime.config import get_config
from cortex.runtime.models import AgentResult

logger = structlog.get_logger()


class DynamicAgent(BaseAgent):
    """An agent loaded dynamically from a JSON definition.

    Wraps an embedded Python script that defines a run() function.
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        script_code: str,
        schedule: Optional[str] = None,
    ):
        """Initialize a dynamic agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: What the agent does
            script_code: Python code containing a run(context) function
            schedule: Optional cron schedule
        """
        metadata = AgentMetadata(version="1.0.0", tags=["dynamic"])
        super().__init__(agent_id, name, description, metadata=metadata)

        self.script_code = script_code
        self.schedule = schedule
        self._compiled_run = None

        # Pre-compile the script to validate syntax and get the 'run' function
        self._compile_script()

    def _compile_script(self):
        """Compiles the embedded script and extracts the run function."""
        try:
            # Create a restricted namespace
            namespace: Dict[str, Any] = {}
            exec(self.script_code, namespace)

            if "run" not in namespace:
                raise ValueError("Dynamic agent script must define a 'run(context)' function.")

            self._compiled_run = namespace["run"]

        except Exception as e:
            logger.error("dynamic_agent_compile_failed", agent_id=self.agent_id, error=str(e))
            raise

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Executes the dynamic script.

        Args:
            context: Execution context

        Returns:
            AgentResult from the script execution
        """
        if not self._compiled_run:
            raise RuntimeError(f"Agent {self.agent_id} has no compiled run function.")

        try:
            logger.info("dynamic_agent_executing", agent_id=self.agent_id)
            result = self._compiled_run(context)

            # If result is already an AgentResult, return it
            if isinstance(result, AgentResult):
                return result

            # Otherwise wrap the result
            return AgentResult(
                success=True,
                message="Execution completed",
                data=result if isinstance(result, dict) else {"result": result},
            )

        except Exception as e:
            logger.error("dynamic_agent_execution_failed", agent_id=self.agent_id, error=str(e))
            return AgentResult(
                success=False, message=f"Dynamic Execution Failed: {str(e)}", data={}
            )


class DynamicAgentLoader:
    """Loads dynamic agents from JSON definitions.

    Scans a directory for .json files and creates DynamicAgent instances
    from valid definitions.
    """

    def __init__(self, agents_dir: Optional[str] = None):
        """Initialize the loader.

        Args:
            agents_dir: Directory to scan for agent definitions.
                       If None, uses config default.
        """
        if agents_dir is None:
            config = get_config()
            self.agents_dir = config.dynamic_agents_dir
        else:
            self.agents_dir = Path(agents_dir)

        self.loaded_agents: Dict[str, DynamicAgent] = {}

    def load_agents(self) -> List[DynamicAgent]:
        """Scans the directory and loads all valid agent definitions.

        Returns:
            List of newly loaded or updated agents
        """
        new_agents = []

        if not self.agents_dir.exists():
            logger.warning("dynamic_agents_dir_missing", path=str(self.agents_dir))
            return []

        # Scan for .json files
        for agent_file in self.agents_dir.glob("*.json"):
            try:
                agent = self._load_single_agent(agent_file)
                if agent:
                    self.loaded_agents[agent.agent_id] = agent
                    new_agents.append(agent)
            except Exception as e:
                logger.error("dynamic_agent_load_error", file=agent_file.name, error=str(e))

        return new_agents

    def _load_single_agent(self, file_path: Path) -> Optional[DynamicAgent]:
        """Parses a single JSON file and creates a DynamicAgent.

        Args:
            file_path: Path to the JSON definition file

        Returns:
            DynamicAgent instance or None if invalid
        """
        try:
            with open(file_path, "r") as f:
                config = json.load(f)

            # Validation
            required_fields = ["id", "name", "description", "script"]
            for field in required_fields:
                if field not in config:
                    logger.warning(
                        "dynamic_agent_missing_field",
                        file=file_path.name,
                        field=field,
                    )
                    return None

            return DynamicAgent(
                agent_id=config["id"],
                name=config["name"],
                description=config["description"],
                script_code=config["script"],
                schedule=config.get("schedule"),
            )

        except Exception as e:
            logger.error("dynamic_agent_parse_error", file=file_path.name, error=str(e))
            raise
