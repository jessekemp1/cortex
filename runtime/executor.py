"""Main runtime executor service.

Provides the central execution engine for managing agents,
scheduling, and tracking execution history.
"""

import signal
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog
import uvicorn

from cortex.runtime.agents.base import BaseAgent
from cortex.runtime.agents.loader import DynamicAgentLoader
from cortex.runtime.batch.manager import BatchManager
from cortex.runtime.config import RuntimeConfig, get_config
from cortex.runtime.models import AgentResult, AgentStatus
from cortex.runtime.scheduler import TaskScheduler
from cortex.runtime.storage.history import ExecutionHistory

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


class RuntimeExecutor:
    """Central executor for managing agents.

    Provides:
    - Agent registration and execution
    - Scheduled execution via APScheduler
    - Webhook-triggered execution
    - Execution history tracking
    - Batch processing integration
    """

    def __init__(self, config: Optional[RuntimeConfig] = None):
        """Initialize the runtime executor.

        Args:
            config: Runtime configuration. If None, uses default config.
        """
        self.config = config or get_config()
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_status: Dict[str, AgentStatus] = {}
        self.scheduler = TaskScheduler(self)
        self.api_app = None
        self.history = ExecutionHistory()
        self.batch_manager = BatchManager()

        # Initialize Dynamic Loader
        try:
            self.dynamic_loader = DynamicAgentLoader()
        except Exception as e:
            logger.warning("dynamic_loader_init_failed", error=str(e))
            self.dynamic_loader = None

        # Success hooks (optional)
        self._success_hooks: List[Callable[[str, AgentResult], None]] = []

    def add_success_hook(self, hook: Callable[[str, AgentResult], None]):
        """Add a hook to be called on successful agent execution.

        Args:
            hook: Function taking (agent_id, result)
        """
        self._success_hooks.append(hook)

    def register_agent(
        self,
        agent: BaseAgent,
        schedule: Optional[str] = None,
        webhook_path: Optional[str] = None,
    ):
        """Register an agent with the executor.

        Args:
            agent: The agent instance to register
            schedule: Optional cron schedule (e.g., "0 8 * * *")
            webhook_path: Optional webhook path for event triggers
        """
        if not agent.validate():
            raise ValueError(f"Agent {agent.agent_id} failed validation")

        self.agents[agent.agent_id] = agent
        self.agent_status[agent.agent_id] = AgentStatus.IDLE

        # Register with scheduler if scheduled
        if schedule:
            self.scheduler.add_job(
                agent_id=agent.agent_id,
                schedule=schedule,
                func=lambda aid=agent.agent_id: self._execute_agent(aid),
            )
            logger.info(
                "agent_registered_scheduled",
                agent_id=agent.agent_id,
                schedule=schedule,
            )

        # Register webhook if event-triggered
        if webhook_path:
            normalized = webhook_path.lstrip("/")
            if normalized.startswith("webhooks/"):
                normalized = normalized[len("webhooks/"):]

            if self.api_app is None:
                from cortex.runtime.api import create_api_app

                self.api_app = create_api_app(self)
            self.api_app.add_webhook_handler(normalized, agent.agent_id)
            logger.info(
                "agent_registered_webhook",
                agent_id=agent.agent_id,
                webhook_path=normalized,
            )

    def _execute_agent(
        self, agent_id: str, context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Execute an agent.

        Args:
            agent_id: ID of the agent to execute
            context: Optional execution context

        Returns:
            AgentResult from the agent execution
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]
        self.agent_status[agent_id] = AgentStatus.RUNNING

        start_time = datetime.now()
        start_timestamp = time.time()

        try:
            result = agent.execute(context or {})
            end_time = datetime.now()
            duration = time.time() - start_timestamp

            self.agent_status[agent_id] = (
                AgentStatus.COMPLETED if result.success else AgentStatus.FAILED
            )

            # Record execution history
            self.history.record_execution(
                agent_id=agent_id,
                status=self.agent_status[agent_id].value,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                success=result.success,
                message=result.message,
                result_data=result.data,
                error_data={"error": result.message} if not result.success else None,
            )

            # Trigger success hooks
            if result.success:
                self._trigger_success_hooks(agent_id, result)

            return result

        except Exception as e:
            end_time = datetime.now()
            duration = time.time() - start_timestamp

            self.agent_status[agent_id] = AgentStatus.FAILED
            logger.error("agent_execution_error", agent_id=agent_id, error=str(e))

            # Record failed execution
            self.history.record_execution(
                agent_id=agent_id,
                status=AgentStatus.FAILED.value,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                success=False,
                message=str(e),
                error_data={"error": str(e), "exception_type": type(e).__name__},
            )

            raise

    def _trigger_success_hooks(self, agent_id: str, result: AgentResult):
        """Trigger hooks for successful execution."""
        for hook in self._success_hooks:
            try:
                hook(agent_id, result)
            except Exception as e:
                logger.error("success_hook_failed", error=str(e))

    def trigger_agent(
        self, agent_id: str, context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Manually trigger an agent.

        Args:
            agent_id: ID of the agent to trigger
            context: Optional execution context

        Returns:
            AgentResult from the agent execution
        """
        return self._execute_agent(agent_id, context)

    def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Get current status of an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Current AgentStatus
        """
        return self.agent_status.get(agent_id, AgentStatus.IDLE)

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents.

        Returns:
            List of agent info dicts
        """
        return [
            {
                "agent_id": agent_id,
                "name": agent.name,
                "description": agent.description,
                "status": self.agent_status.get(agent_id, AgentStatus.IDLE).value,
                "metadata": agent.get_metadata().model_dump(),
            }
            for agent_id, agent in self.agents.items()
        ]

    def _start_dynamic_loader(self):
        """Start the dynamic agent loader."""
        if not self.dynamic_loader:
            return

        # Run loading immediately
        self._reload_dynamic_agents()

        # Schedule periodic checks (every minute)
        self.scheduler.add_job(
            agent_id="system_dynamic_loader",
            schedule="*/1 * * * *",
            func=self._reload_dynamic_agents,
        )

    def _reload_dynamic_agents(self):
        """Reload dynamic agents from the drop zone."""
        if not self.dynamic_loader:
            return

        new_agents = self.dynamic_loader.load_agents()
        for agent in new_agents:
            if agent.agent_id not in self.agents:
                self.register_agent(agent)

                if hasattr(agent, "schedule") and agent.schedule:
                    self.scheduler.add_job(
                        agent_id=agent.agent_id,
                        schedule=agent.schedule,
                        func=lambda aid=agent.agent_id: self._execute_agent(aid),
                    )
                    logger.info(
                        "dynamic_agent_scheduled",
                        agent_id=agent.agent_id,
                        schedule=agent.schedule,
                    )

        if new_agents:
            logger.info("dynamic_agents_reloaded", count=len(new_agents))

    def _start_batch_system(self):
        """Start the batch processing system agents."""
        from cortex.runtime.agents.system.batch_agents import (
            BatchProcessorAgent,
            ResultHandlerAgent,
        )

        # Register and schedule processor (hourly)
        processor = BatchProcessorAgent(self)
        self.register_agent(processor, schedule="0 * * * *")

        # Register and schedule handler (every 15 mins)
        handler = ResultHandlerAgent(self)
        self.register_agent(handler, schedule="*/15 * * * *")

        logger.info("batch_system_started")

    def _register_builtin_agents(self):
        """Register built-in agents."""
        try:
            from cortex.runtime.agents.builtin.briefing import BriefingAgent

            briefing = BriefingAgent()
            self.register_agent(briefing, schedule="0 8 * * *")
            logger.info("builtin_agents_registered")
        except Exception as e:
            logger.warning("builtin_agents_registration_failed", error=str(e))

    def start(self, api_port: Optional[int] = None):
        """Start the executor service.

        Args:
            api_port: Port for the API server (default from config)
        """
        port = api_port or self.config.port

        # Create API app if not already created
        if self.api_app is None:
            from cortex.runtime.api import create_api_app

            self.api_app = create_api_app(self)

        # Start scheduler
        self.scheduler.start()

        # Start dynamic loader
        self._start_dynamic_loader()

        # Start batch system
        self._start_batch_system()

        # Register built-in agents
        self._register_builtin_agents()

        # Start API server (blocking)
        logger.info("api_server_starting", port=port)
        uvicorn.run(self.api_app, host=self.config.host, port=port)

    def shutdown(self):
        """Shutdown the executor gracefully."""
        self.scheduler.shutdown()
        logger.info("executor_shutdown")


def main():
    """Main entry point for running the executor."""
    config = get_config()
    executor = RuntimeExecutor(config)

    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received")
        executor.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        executor.start()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        executor.shutdown()


if __name__ == "__main__":
    main()
