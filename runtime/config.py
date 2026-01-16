"""Runtime configuration management.

Provides unified configuration for the Cortex runtime engine,
replacing hardcoded paths with environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _get_default_root_dir() -> Path:
    """Get default root directory from environment or user home."""
    env_root = os.environ.get("CORTEX_ROOT_DIR")
    if env_root:
        return Path(env_root)
    # Default to ~/Dev if exists, otherwise home
    dev_dir = Path.home() / "Dev"
    return dev_dir if dev_dir.exists() else Path.home()


def _get_default_data_dir() -> Path:
    """Get default data directory."""
    env_data = os.environ.get("CORTEX_DATA_DIR")
    if env_data:
        return Path(env_data)
    return Path.home() / ".cortex" / "data"


@dataclass
class RuntimeConfig:
    """Configuration for the Cortex runtime engine."""

    # Server settings
    host: str = field(default_factory=lambda: os.getenv("CORTEX_RUNTIME_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("CORTEX_RUNTIME_PORT", "8000")))
    log_level: str = field(default_factory=lambda: os.getenv("CORTEX_LOG_LEVEL", "INFO"))

    # Scheduler settings
    timezone: str = field(
        default_factory=lambda: os.getenv("CORTEX_TIMEZONE", "America/Los_Angeles")
    )
    max_workers: int = field(default_factory=lambda: int(os.getenv("CORTEX_MAX_WORKERS", "10")))

    # Directory settings
    root_dir: Path = field(default_factory=_get_default_root_dir)
    data_dir: Path = field(default_factory=_get_default_data_dir)
    agents_dir: Path = field(default_factory=lambda: Path.home() / ".cortex" / "agents")

    def __post_init__(self):
        """Ensure directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    @property
    def execution_history_db(self) -> Path:
        """Path to execution history SQLite database."""
        return self.data_dir / "execution_history.db"

    @property
    def batch_queue_db(self) -> Path:
        """Path to batch queue SQLite database."""
        return self.data_dir / "batch_queue.db"

    @property
    def dynamic_agents_dir(self) -> Path:
        """Path to dynamic agent definitions (JSON)."""
        return self.agents_dir / "dynamic"


# Global default config instance
_default_config: RuntimeConfig | None = None


def get_config() -> RuntimeConfig:
    """Get or create the default runtime configuration."""
    global _default_config
    if _default_config is None:
        _default_config = RuntimeConfig()
    return _default_config
