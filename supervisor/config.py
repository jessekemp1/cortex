"""
Supervisor configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SupervisorConfig:
    """Configuration for the Cortex Supervisor."""

    # Timing
    tick_interval_seconds: int = 30  # Main loop interval
    health_check_interval_seconds: int = 60  # How often to check for stuck tasks
    work_discovery_interval_seconds: int = 300  # How often to discover new work
    ai_batch_grouping_window_minutes: int = 15  # Group AI tasks before submission

    # Capacity
    max_concurrent_shell_tasks: int = 3  # Parallel shell executions
    max_ai_batch_size: int = 50  # Max tasks per AI batch submission

    # Health
    stale_task_hours: int = 4  # Mark RUNNING tasks as stuck after this
    max_retries: int = 3  # Max auto-retries for failed tasks

    # Paths
    pid_file: Path = field(default_factory=lambda: Path.home() / ".cortex" / "supervisor.pid")
    log_file: Path = field(
        default_factory=lambda: Path.home() / ".cortex" / "logs" / "supervisor.log"
    )
    state_file: Path = field(
        default_factory=lambda: Path.home() / ".cortex" / "supervisor_state.json"
    )

    # Feature flags
    enable_work_discovery: bool = True  # Proactively find work from sources
    enable_ai_batching: bool = True  # Group AI tasks for batch submission
    enable_self_healing: bool = True  # Auto-detect and retry stuck tasks

    def __post_init__(self):
        """Ensure directories exist."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "SupervisorConfig":
        """Create config from environment variables."""
        import os

        return cls(
            tick_interval_seconds=int(os.getenv("CORTEX_SUPERVISOR_TICK_INTERVAL", "30")),
            health_check_interval_seconds=int(os.getenv("CORTEX_SUPERVISOR_HEALTH_INTERVAL", "60")),
            work_discovery_interval_seconds=int(
                os.getenv("CORTEX_SUPERVISOR_DISCOVERY_INTERVAL", "300")
            ),
            max_concurrent_shell_tasks=int(os.getenv("CORTEX_SUPERVISOR_MAX_CONCURRENT", "3")),
            stale_task_hours=int(os.getenv("CORTEX_SUPERVISOR_STALE_HOURS", "4")),
        )
