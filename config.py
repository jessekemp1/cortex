import os
from dataclasses import dataclass, field
from pathlib import Path

from security import (
    check_and_warn_permissions,
    secure_create_directory,
    secure_create_file,
)


def workspace_root() -> Path:
    """Projects workspace root (the dir that CONTAINS your git repos).

    Resolved from CORTEX_ROOT_DIR (preferred), falling back to the legacy
    CORTEX_DEV_ROOT, then ~/Dev. This is the *projects* root used for project
    discovery and git scanning — NOT the Cortex state dir (~/.cortex), which
    holds databases, logs, and prompts.
    """
    root = (
        os.environ.get("CORTEX_ROOT_DIR")
        or os.environ.get("CORTEX_DEV_ROOT")
        or str(Path.home() / "Dev")
    )
    return Path(root).expanduser()


def discover_projects(root: Path | None = None, depth: int = 2) -> list[dict]:
    """Discover projects under the workspace root.

    A project = a git repo found under the workspace root (depth-limited):
    depth 1 (root/<proj>) and depth 2 (root/<group>/<proj>). Returns a list of
    {"name", "path", "rel"} dicts, deduped by project name.
    """
    root = root or workspace_root()
    found: dict[str, dict] = {}
    # is_dir() (not exists()): a misconfigured CORTEX_ROOT_DIR pointing at a FILE
    # "exists" but would raise NotADirectoryError on iterdir() below.
    if not root.is_dir():
        return []
    # depth 1 (root/<proj>) and depth 2 (root/<group>/<proj>)
    for d in sorted(root.iterdir()):
        try:
            if (d / ".git").exists():
                found[d.name] = {"name": d.name, "path": str(d), "rel": d.name}
            elif d.is_dir() and depth >= 2:
                for sub in sorted(d.iterdir()):
                    if (sub / ".git").exists():
                        found[sub.name] = {
                            "name": sub.name,
                            "path": str(sub),
                            "rel": f"{d.name}/{sub.name}",
                        }
        except (PermissionError, OSError):
            continue
    return list(found.values())


@dataclass
class CortexConfig:
    # Default to cwd; override via CORTEX_ROOT_DIR env var or ~/.cortex/config.yaml root_dir
    root_dir: Path = field(default_factory=lambda: Path.cwd())
    config_dir: Path = field(default_factory=lambda: Path.home() / ".cortex")
    learning_enabled: bool = True
    default_limit: int = 3
    json_output: bool = False

    # Phase 1 Feature Flags
    prompt_versioning_enabled: bool = True  # Use versioned prompt templates
    data_quality_enabled: bool = True  # Track data quality metrics
    defensive_prompting_enabled: bool = True  # Apply input/output validation

    # Advanced options
    quality_weighting_enabled: bool = True  # Use quality scores in learning
    prompt_version: str = "v1"  # Default prompt version to use

    # AI Engineering Module Flags (Week 2)
    tiered_memory_enabled: bool = True  # Use three-tier memory system
    context_optimizer_enabled: bool = True  # Apply context optimization for LLM prompts
    hybrid_retrieval_enabled: bool = True  # Use hybrid BM25+embedding retrieval
    implicit_feedback_enabled: bool = True  # Track implicit user feedback signals

    # Synthetic Data Engine
    synthetic_enabled: bool = True  # Enable synthetic FinServ data generation


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
            if "prompt_versioning_enabled" in data:
                config.prompt_versioning_enabled = data["prompt_versioning_enabled"]
            if "data_quality_enabled" in data:
                config.data_quality_enabled = data["data_quality_enabled"]
            if "defensive_prompting_enabled" in data:
                config.defensive_prompting_enabled = data["defensive_prompting_enabled"]
            if "quality_weighting_enabled" in data:
                config.quality_weighting_enabled = data["quality_weighting_enabled"]
            if "prompt_version" in data:
                config.prompt_version = data["prompt_version"]
            # AI Engineering Module Flags
            if "tiered_memory_enabled" in data:
                config.tiered_memory_enabled = data["tiered_memory_enabled"]
            if "context_optimizer_enabled" in data:
                config.context_optimizer_enabled = data["context_optimizer_enabled"]
            if "hybrid_retrieval_enabled" in data:
                config.hybrid_retrieval_enabled = data["hybrid_retrieval_enabled"]
            if "implicit_feedback_enabled" in data:
                config.implicit_feedback_enabled = data["implicit_feedback_enabled"]
        except ImportError:
            # YAML optional - config will use defaults
            pass

    # Environment overrides with validation
    if os.environ.get("CORTEX_ROOT_DIR"):
        proposed_root = Path(os.environ["CORTEX_ROOT_DIR"]).expanduser().resolve()
        if proposed_root.exists() and proposed_root.is_dir():
            config.root_dir = proposed_root
        else:
            print(
                f"Warning: Invalid CORTEX_ROOT_DIR: {os.environ['CORTEX_ROOT_DIR']}, using default"
            )

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
# root_dir: ~/my-projects  # Override default (cwd). Can also use CORTEX_ROOT_DIR env var.
learning_enabled: true
default_limit: 3

# Phase 1 Features (Advanced Intelligence)
prompt_versioning_enabled: true  # Use versioned prompt templates
data_quality_enabled: true       # Track data quality metrics
defensive_prompting_enabled: true # Apply input/output validation
quality_weighting_enabled: true  # Use quality scores in learning
prompt_version: v1               # Default prompt version
""",
            )
        except ImportError:
            # YAML optional - config will use defaults
            pass
