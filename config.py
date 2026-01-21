import os
from dataclasses import dataclass, field
from pathlib import Path
from security import check_and_warn_permissions, secure_create_file, secure_create_directory


@dataclass
class CortexConfig:
    root_dir: Path = field(default_factory=lambda: Path(os.path.expanduser("~/Dev")))
    config_dir: Path = field(default_factory=lambda: Path.home() / ".cortex")
    learning_enabled: bool = True
    default_limit: int = 3
    json_output: bool = False


def load_config() -> CortexConfig:
    config = CortexConfig()
    config_file = config.config_dir / "config.yaml"

    if config_file.exists():
        # SECURITY: Check config file permissions and warn if insecure
        check_and_warn_permissions(config_file, is_directory=False, fix=False)

        try:
            import yaml

            with open(config_file) as f:
                data = yaml.safe_load(f) or {}
            if "root_dir" in data:
                # SECURITY: Validate path to prevent traversal attacks
                proposed_root = Path(data["root_dir"]).expanduser().resolve()
                # Ensure path exists and is a directory
                if proposed_root.exists() and proposed_root.is_dir():
                    config.root_dir = proposed_root
                else:
                    print(f"Warning: Invalid root_dir in config: {data['root_dir']}, using default")
            if "learning_enabled" in data:
                config.learning_enabled = data["learning_enabled"]
        except ImportError:
            # YAML optional - config will use defaults
            pass

    # Environment overrides with validation
    if os.environ.get("CORTEX_ROOT_DIR"):
        proposed_root = Path(os.environ["CORTEX_ROOT_DIR"]).expanduser().resolve()
        if proposed_root.exists() and proposed_root.is_dir():
            config.root_dir = proposed_root
        else:
            print(f"Warning: Invalid CORTEX_ROOT_DIR: {os.environ['CORTEX_ROOT_DIR']}, using default")

    return config


def create_default_config():
    config_dir = Path.home() / ".cortex"

    # SECURITY: Create directory with secure permissions (700)
    secure_create_directory(config_dir)

    config_file = config_dir / "config.yaml"

    if not config_file.exists():
        try:
            import yaml  # noqa: F401

            # SECURITY: Create config file with secure permissions (600)
            secure_create_file(
                config_file,
                content="""# Cortex Configuration
root_dir: ~/Dev  # Or use ${HOME}/Dev for portability
learning_enabled: true
default_limit: 3
"""
            )
        except ImportError:
            # YAML optional - config will use defaults
            pass
