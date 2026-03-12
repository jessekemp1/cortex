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
    dry_run: bool = False  # Log routing decisions without calling API
    watch_goals: bool = True  # Check GOALS.md for changes on every tick

    # Multi-provider routing (Phase 1)
    enable_multi_provider: bool = False  # Route to non-Anthropic providers
    providers_config_path: Path = field(
        default_factory=lambda: Path.home() / ".cortex" / "providers.yaml"
    )
    fallback_provider: str = "anthropic"  # Always-available fallback

    # Offline / local LLM support
    offline_mode: str = "auto"  # "auto" | "force_offline" | "force_online"
    offline_check_interval_seconds: int = 300  # Re-check connectivity every 5min
    local_model_quality_floor: float = 0.3  # Lower quality floor for local models

    # Distributed dispatch (Phase 3)
    enable_distributed: bool = False  # Enable worker API
    worker_api_port: int = 8766
    worker_api_auth_token: str = ""  # Required for distributed mode
    heartbeat_timeout_seconds: int = 90
    max_remote_workers: int = 10

    # Team orchestration (Phase 4)
    enable_teams: bool = False  # Enable team-of-teams decomposition
    enable_ai_quality_judge: bool = False  # Use AI judge for quality evaluation
    enable_routing_analytics: bool = True  # Cost/quality reporting

    # Approval gates (see cortex.supervisor.approval)
    approval_policy: str = "gate_high"  # "auto_all", "gate_high", "gate_all"
    approval_dir: Path = field(default_factory=lambda: Path.home() / ".cortex" / "approvals")

    # Overnight batch queue (50% cost savings via Anthropic Batch API)
    overnight_batch_enabled: bool = True  # Defer LOW-priority AI tasks to overnight
    overnight_start_hour: int = 2  # UTC hour to submit overnight batch (2 AM)
    overnight_end_hour: int = 6  # UTC hour after which overnight window closes
    overnight_queue_file: Path = field(
        default_factory=lambda: Path.home() / ".cortex" / "overnight_queue.json"
    )
    min_items_for_overnight_batch: int = 3  # Minimum items before submitting

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
