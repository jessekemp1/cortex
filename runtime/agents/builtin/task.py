"""Scheduled Task Agent - Simple function wrapper.

Provides a simple way to wrap arbitrary functions as agents
for scheduled execution.
"""

import time
from typing import Any, Callable, Dict

from cortex.runtime.agents.base import BaseAgent
from cortex.runtime.models import AgentResult


class TaskAgent(BaseAgent):
    """Agent that wraps a simple task function.

    Useful for converting existing functions into scheduled agents.

    Example:
        def my_task(context):
            return {"result": "done"}

        agent = TaskAgent(
            agent_id="my_task",
            name="My Task",
            description="Does something useful",
            task_func=my_task
        )
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        task_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        **kwargs,
    ):
        """Initialize the task agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: What the task does
            task_func: Function to execute (receives context, returns dict)
            **kwargs: Additional BaseAgent parameters
        """
        super().__init__(agent_id, name, description, **kwargs)
        self.task_func = task_func

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute the wrapped task function.

        Args:
            context: Execution context

        Returns:
            AgentResult with task output
        """
        start_time = time.time()

        try:
            result_data = self.task_func(context)
            execution_time = time.time() - start_time

            return AgentResult(
                success=True,
                message="Task completed successfully",
                data=result_data,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return AgentResult(
                success=False,
                message=f"Task failed: {str(e)}",
                data={"error": str(e)},
                execution_time=execution_time,
            )
