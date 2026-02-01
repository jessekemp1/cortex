"""
Cortex Plugin System

Self-documenting, extensible plugin architecture for Cortex commands.

Features:
- Automatic plugin discovery
- PLUGIN.md format for self-documentation
- Dependency checking
- Enable/disable functionality
- External plugin installation

Usage:
    from cortex.plugins import PluginLoader

    loader = PluginLoader()
    loader.load_all_plugins()

    plugin = loader.get_plugin("status")
    plugin.execute(["--quick"])
"""

from .base import BasePlugin, PluginMetadata
from .loader import PluginLoader
from .registry import PluginRegistry

__all__ = [
    "BasePlugin",
    "PluginMetadata",
    "PluginLoader",
    "PluginRegistry",
]

__version__ = "1.0.0"
