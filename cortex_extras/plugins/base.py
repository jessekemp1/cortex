#!/usr/bin/env python3
"""
Base Plugin Class for Cortex Plugin System

All Cortex plugins must inherit from BasePlugin and implement:
1. execute() - Main plugin logic
2. PLUGIN.md - Self-documentation with metadata

Optional overrides:
- validate_args() - Custom argument validation
- setup() - One-time setup logic
- teardown() - Cleanup logic
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class PluginMetadata:
    """
    Plugin metadata from PLUGIN.md frontmatter.

    Parsed from YAML frontmatter in PLUGIN.md file.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: Optional[str] = None
    requires: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    # Additional metadata
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: Optional[str] = None


class BasePlugin(ABC):
    """
    Base class for all Cortex plugins.

    Plugins must:
    1. Have a PLUGIN.md file with YAML frontmatter
    2. Implement execute() method
    3. Handle their own dependencies
    4. Provide help() output from PLUGIN.md

    Example:
        class StatusPlugin(BasePlugin):
            def execute(self, args: List[str], **kwargs) -> int:
                # Implementation
                return 0
    """

    def __init__(self, plugin_dir: Path):
        """
        Initialize plugin from directory.

        Args:
            plugin_dir: Path to plugin directory containing PLUGIN.md
        """
        self.plugin_dir = plugin_dir
        self.metadata = self._load_metadata()
        self.plugin_md_content = self._load_plugin_md()

    def _load_metadata(self) -> PluginMetadata:
        """
        Load metadata from PLUGIN.md frontmatter.

        Returns:
            PluginMetadata parsed from YAML frontmatter

        Raises:
            FileNotFoundError: If PLUGIN.md doesn't exist
            ValueError: If frontmatter is invalid
        """
        plugin_md = self.plugin_dir / "PLUGIN.md"

        if not plugin_md.exists():
            raise FileNotFoundError(f"PLUGIN.md not found in {self.plugin_dir}")

        content = plugin_md.read_text()

        # Extract YAML frontmatter (between --- markers)
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)

        if not frontmatter_match:
            # No frontmatter, use defaults
            return PluginMetadata(name=self.plugin_dir.name)

        frontmatter_yaml = frontmatter_match.group(1)

        # Parse YAML
        if yaml is None:
            # Fallback: simple key-value parsing
            metadata_dict = self._parse_simple_yaml(frontmatter_yaml)
        else:
            metadata_dict = yaml.safe_load(frontmatter_yaml) or {}

        # Create PluginMetadata
        return PluginMetadata(
            name=metadata_dict.get("name", self.plugin_dir.name),
            version=metadata_dict.get("version", "1.0.0"),
            description=metadata_dict.get("description", ""),
            author=metadata_dict.get("author"),
            requires=metadata_dict.get("requires", {}),
            tags=metadata_dict.get("tags", []),
            enabled=metadata_dict.get("enabled", True),
            homepage=metadata_dict.get("homepage"),
            repository=metadata_dict.get("repository"),
            license=metadata_dict.get("license"),
        )

    def _parse_simple_yaml(self, yaml_str: str) -> Dict[str, Any]:
        """
        Simple YAML parser for when PyYAML isn't available.

        Only handles basic key: value pairs and lists.
        """
        result = {}
        current_key = None

        for line in yaml_str.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle list items
            if line.startswith("- "):
                if current_key and isinstance(result.get(current_key), list):
                    result[current_key].append(line[2:].strip())
                continue

            # Handle key: value
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Handle booleans
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                # Handle numbers
                elif value.isdigit():
                    value = int(value)
                # Handle lists
                elif value.startswith("[") and value.endswith("]"):
                    value = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
                    current_key = None
                # Handle empty (start of list)
                elif not value:
                    result[key] = []
                    current_key = key
                    continue

                result[key] = value
                current_key = None

        return result

    def _load_plugin_md(self) -> str:
        """
        Load full PLUGIN.md content (without frontmatter).

        Returns:
            PLUGIN.md content for help display
        """
        plugin_md = self.plugin_dir / "PLUGIN.md"

        if not plugin_md.exists():
            return ""

        content = plugin_md.read_text()

        # Remove frontmatter
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

        return content.strip()

    @abstractmethod
    def execute(self, args: List[str], **kwargs) -> int:
        """
        Execute plugin with arguments.

        Args:
            args: Command-line arguments (e.g., ["--quick", "--project", "vortex"])
            **kwargs: Additional context (e.g., current_dir, user, etc.)

        Returns:
            Exit code (0 = success, non-zero = error)

        Example:
            def execute(self, args: List[str], **kwargs) -> int:
                if "--help" in args:
                    print(self.help())
                    return 0

                # Plugin logic here
                return 0
        """
        pass

    def help(self) -> str:
        """
        Return help text from PLUGIN.md.

        Returns:
            Formatted help text
        """
        if not self.plugin_md_content:
            return f"No help available for {self.metadata.name}"

        return f"""# {self.metadata.name} (v{self.metadata.version})

{self.metadata.description}

{self.plugin_md_content}
"""

    def check_dependencies(self) -> List[str]:
        """
        Check if all dependencies are available.

        Returns:
            List of missing dependencies (empty = all OK)
        """
        missing = []
        requires = self.metadata.requires

        # Check Python version
        if "python" in requires:
            requires["python"]
            # Simple version check (e.g., ">=3.11")
            # This is basic - could be enhanced with packaging.version
            pass

        # Check required packages
        if "packages" in requires:
            packages = requires["packages"]
            if isinstance(packages, list):
                for package in packages:
                    try:
                        __import__(package)
                    except ImportError:
                        missing.append(f"python package: {package}")
            elif isinstance(packages, dict):
                for package, version in packages.items():
                    try:
                        __import__(package)
                    except ImportError:
                        missing.append(f"python package: {package} ({version})")

        # Check optional packages (just log, don't fail)
        if "optional" in requires:
            optional = requires["optional"]
            if isinstance(optional, dict):
                for package, purpose in optional.items():
                    try:
                        __import__(package)
                    except ImportError:
                        # Optional - just note it
                        pass

        return missing

    def validate_args(self, args: List[str]) -> bool:
        """
        Validate arguments before execution.

        Override this in subclasses for custom validation.

        Args:
            args: Command-line arguments

        Returns:
            True if valid, False otherwise
        """
        return True

    def setup(self) -> None:
        """
        One-time setup logic.

        Called before execute(). Override in subclasses if needed.
        """
        pass

    def teardown(self) -> None:
        """
        Cleanup logic.

        Called after execute(). Override in subclasses if needed.
        """
        pass

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<{self.__class__.__name__} name={self.metadata.name} version={self.metadata.version}>"
        )
