#!/usr/bin/env python3
"""
Plugin Loader for Cortex Plugin System

Automatically discovers and loads plugins from the plugins directory.

Features:
- Auto-discovery of valid plugins
- Dynamic module loading
- Dependency checking
- Error handling for invalid plugins
- Caching for performance
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base import BasePlugin


class PluginLoader:
    """
    Discovers and loads plugins automatically.

    Scans cortex/plugins/ for directories containing:
    - PLUGIN.md (metadata + documentation)
    - plugin.py (implementation with BasePlugin subclass)

    Example:
        loader = PluginLoader()
        plugins = loader.load_all_plugins()

        status_plugin = loader.get_plugin("status")
        status_plugin.execute(["--quick"])
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Initialize plugin loader.

        Args:
            plugins_dir: Path to plugins directory (default: cortex/plugins/)
        """
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent

        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, BasePlugin] = {}
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}

    def discover_plugins(self) -> List[str]:
        """
        Discover all valid plugins in plugins directory.

        Returns:
            List of plugin names found

        A valid plugin must have:
        - Directory in cortex/plugins/
        - PLUGIN.md file
        - plugin.py file with BasePlugin subclass
        """
        discovered = []

        for item in self.plugins_dir.iterdir():
            if not item.is_dir():
                continue

            # Skip special directories
            if item.name.startswith("_") or item.name.startswith("."):
                continue

            # Skip __pycache__, tests, etc.
            if item.name in ["__pycache__", "tests"]:
                continue

            # Check for required files
            plugin_md = item / "PLUGIN.md"
            plugin_py = item / "plugin.py"

            if plugin_md.exists() and plugin_py.exists():
                discovered.append(item.name)

        return sorted(discovered)

    def load_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Load a plugin by name.

        Args:
            plugin_name: Name of plugin directory

        Returns:
            Loaded plugin instance or None if failed
        """
        # Check cache
        if plugin_name in self.plugins:
            return self.plugins[plugin_name]

        plugin_dir = self.plugins_dir / plugin_name
        plugin_py = plugin_dir / "plugin.py"

        if not plugin_py.exists():
            print(f"Warning: plugin.py not found for {plugin_name}", file=sys.stderr)
            return None

        try:
            # Dynamic import
            spec = importlib.util.spec_from_file_location(
                f"cortex.plugins.{plugin_name}.plugin",
                plugin_py
            )

            if spec is None or spec.loader is None:
                print(f"Warning: Could not load spec for {plugin_name}", file=sys.stderr)
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Find plugin class (subclass of BasePlugin, but not BasePlugin itself)
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr != BasePlugin
                ):
                    plugin_class = attr
                    break

            if plugin_class is None:
                print(f"Warning: No BasePlugin subclass found in {plugin_name}/plugin.py", file=sys.stderr)
                return None

            # Instantiate plugin
            plugin = plugin_class(plugin_dir)

            # Check dependencies
            missing = plugin.check_dependencies()
            if missing:
                print(f"Warning: Plugin '{plugin_name}' has missing dependencies:", file=sys.stderr)
                for dep in missing:
                    print(f"  - {dep}", file=sys.stderr)
                # Still load plugin, but note missing deps
                plugin.metadata.enabled = False

            # Cache
            self.plugins[plugin_name] = plugin
            self._plugin_classes[plugin_name] = plugin_class

            return plugin

        except Exception as e:
            print(f"Error loading plugin '{plugin_name}': {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return None

    def load_all_plugins(self, skip_disabled: bool = True) -> Dict[str, BasePlugin]:
        """
        Load all discovered plugins.

        Args:
            skip_disabled: Skip plugins with enabled=false in metadata

        Returns:
            Dict of plugin_name -> BasePlugin instance
        """
        discovered = self.discover_plugins()

        for plugin_name in discovered:
            plugin = self.load_plugin(plugin_name)

            if plugin:
                # Cache the plugin
                self.plugins[plugin_name] = plugin

        # Return filtered dict based on skip_disabled
        if skip_disabled:
            return {
                name: plugin
                for name, plugin in self.plugins.items()
                if plugin.metadata.enabled
            }
        else:
            return self.plugins

    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Get a loaded plugin by name.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin instance or None if not loaded
        """
        return self.plugins.get(plugin_name)

    def reload_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Reload a plugin (useful for development).

        Args:
            plugin_name: Plugin name

        Returns:
            Reloaded plugin instance or None if failed
        """
        # Remove from cache
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]

        if plugin_name in self._plugin_classes:
            del self._plugin_classes[plugin_name]

        # Reload
        return self.load_plugin(plugin_name)

    def list_plugins(self, include_disabled: bool = False) -> List[Dict[str, any]]:
        """
        List all loaded plugins with metadata.

        Args:
            include_disabled: Include disabled plugins

        Returns:
            List of plugin info dicts
        """
        result = []

        for name, plugin in self.plugins.items():
            if not include_disabled and not plugin.metadata.enabled:
                continue

            # Check dependencies
            missing_deps = plugin.check_dependencies()

            result.append({
                "name": name,
                "version": plugin.metadata.version,
                "description": plugin.metadata.description,
                "enabled": plugin.metadata.enabled,
                "missing_dependencies": missing_deps,
                "tags": plugin.metadata.tags,
            })

        return sorted(result, key=lambda x: x["name"])

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, any]]:
        """
        Get detailed info about a specific plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin info dict or None if not found
        """
        plugin = self.get_plugin(plugin_name)

        if not plugin:
            return None

        missing_deps = plugin.check_dependencies()

        return {
            "name": plugin.metadata.name,
            "version": plugin.metadata.version,
            "description": plugin.metadata.description,
            "author": plugin.metadata.author,
            "enabled": plugin.metadata.enabled,
            "tags": plugin.metadata.tags,
            "requires": plugin.metadata.requires,
            "missing_dependencies": missing_deps,
            "directory": str(plugin.plugin_dir),
            "homepage": plugin.metadata.homepage,
            "repository": plugin.metadata.repository,
            "license": plugin.metadata.license,
        }
