import json
import re


class AgentFactory:
    """Generates Agent Configurations from high-level intent."""

    @staticmethod
    def create_team_config(intent: str, team_id: str = None) -> str:
        """
        Generate a JSON configuration for an agent team based on intent.

        Args:
            intent: The high-level goal (e.g. "Research Windfield")
            team_id: Optional ID for the team/agent

        Returns:
            JSON string configuration
        """
        if not team_id:
            # Generate ID from intent
            clean_intent = re.sub(r"[^a-zA-Z0-9]", "_", intent.lower())
            team_id = f"team_{clean_intent[:30]}"

        # For now, we create a single "Team Leader" agent that represents the team.
        # In the future, this could generate multiple YAMLs.

        # Simple template for a generic "Task Agent"
        config = {
            "id": team_id,
            "name": f"Agent Team: {intent}",
            "description": f"Team dedicated to: {intent}",
            "schedule": "0 8 * * *",  # Default to daily at 8am
            "script": AgentFactory._generate_script(intent),
        }

        return json.dumps(config, indent=2)

    @staticmethod
    def _generate_script(intent: str) -> str:
        """Generate the Python script for the agent."""
        # In a real implementation, this might use an LLM to generate code.
        # For now, we use a template that prints the intent.

        return f'''
import structlog
logger = structlog.get_logger()

def run(context):
    """
    Auto-generated agent script for: {intent}
    """
    logger.info("dynamic_agent_start", intent="{intent}")
    print(f"[{intent}] Agent Team Executing...")

    # 1. Access Context
    last_run = context.get("last_run")

    # 2. Perform Work (Simulation)
    # TODO: Connect to real tool execution here
    print(f"[{intent}] Analyzing workspace...")
    print(f"[{intent}] Generating report...")

    logger.info("dynamic_agent_complete", intent="{intent}")

    return {{
        "status": "success",
        "message": "Executed work for: {intent}",
        "data": {{ "intent": "{intent}", "artifacts": [] }}
    }}
'''
