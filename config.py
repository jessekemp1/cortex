import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CortexConfig:
    root_dir: Path = field(default_factory=lambda: Path("/Users/jesse.kemp/Dev"))
    config_dir: Path = field(default_factory=lambda: Path.home() / ".cortex")
    learning_enabled: bool = True
    default_limit: int = 3
    json_output: bool = False


def load_config() -> CortexConfig:
    config = CortexConfig()
    config_file = config.config_dir / "config.yaml"

    if config_file.exists():
        try:
            import yaml

            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
            if "root_dir" in data:
                config.root_dir = Path(data["root_dir"])
            if "learning_enabled" in data:
                config.learning_enabled = data["learning_enabled"]
        except ImportError:
            # YAML optional - config will use defaults
            pass

    # Environment overrides
    if os.environ.get("CORTEX_ROOT_DIR"):
        config.root_dir = Path(os.environ["CORTEX_ROOT_DIR"])

    return config


def create_default_config():
    config_dir = Path.home() / ".cortex"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.yaml"

    if not config_file.exists():
        try:
            import yaml

            config_file.write_text(
                """# Cortex Configuration
root_dir: /Users/jesse.kemp/Dev
learning_enabled: true
default_limit: 3
"""
            )
        except ImportError:
            # YAML optional - config will use defaults
            pass
