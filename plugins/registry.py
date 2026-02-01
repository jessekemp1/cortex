#!/usr/bin/env python3
"""
Plugin Registry for Cortex Plugin System

Manages plugin metadata, enable/disable state, and persistence.

Features:
- Plugin state persistence (JSON)
- Enable/disable plugins
- Plugin metadata management
- Version tracking
- Dependency resolution
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from .base import BasePlugin, PluginMetadata


class PluginRegistry:
    """
    Manages plugin metadata and enable/disable state.

    Persists plugin state to ~/.cortex/plugins/registry.json

    Example:
        registry = PluginRegistry()
        registry.register(plugin)
        registry.disable("briefing")
        registry.is_enabled("briefing")  # False
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """
        Initialize plugin registry.

        Args:
            registry_path: Path to registry file (default: ~/.cortex/plugins/registry.json)
        """
        if registry_path is None:
            cortex_dir = Path.home() / ".cortex" / "plugins"
            cortex_dir.mkdir(parents=True, exist_ok=True)
            registry_path = cortex_dir / "registry.json"

        self.registry_path = registry_path
        self.plugins: Dict[str, PluginMetadata] = {}
        self._state: Dict[str, Dict] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load plugin state from registry file."""
        if not self.registry_path.exists():
            self._state = {}
            return

        try:
            with open(self.registry_path, "r") as f:
                self._state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load registry from {self.registry_path}: {e}", file=sys.stderr)
            self._state = {}

    def _save_state(self) -> None:
        """Save plugin state to registry file."""
        try:
            with open(self.registry_path, "w") as f:
                json.dump(self._state, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save registry to {self.registry_path}: {e}", file=sys.stderr)

    def register(self, plugin: BasePlugin) -> None:
        """
        Register a plugin with the registry.

        Args:
            plugin: Plugin instance to register
        """
        name = plugin.metadata.name
        self.plugins[name] = plugin.metadata

        # Initialize state if not exists
        if name not in self._state:
            self._state[name] = {
                "enabled": plugin.metadata.enabled,
                "version": plugin.metadata.version,
                "installed_at": None,  # Could track installation time
            }

        # Update version if changed
        if self._state[name]["version"] != plugin.metadata.version:
            self._state[name]["version"] = plugin.metadata.version

        self._save_state()

    def unregister(self, plugin_name: str) -> None:
        """
        Unregister a plugin from the registry.

        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]

        if plugin_name in self._state:
            del self._state[plugin_name]
            self._save_state()

    def is_enabled(self, plugin_name: str) -> bool:
        """
        Check if a plugin is enabled.

        Args:
            plugin_name: Plugin name

        Returns:
            True if enabled, False otherwise
        """
        if plugin_name not in self._state:
            return True  # Default to enabled if not in state

        return self._state[plugin_name].get("enabled", True)

    def enable(self, plugin_name: str) -> bool:
        """
        Enable a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            True if successful, False if plugin not found
        """
        if plugin_name not in self._state:
            # Plugin not registered yet
            self._state[plugin_name] = {"enabled": True, "version": "unknown"}

        self._state[plugin_name]["enabled"] = True
        self._save_state()
        return True

    def disable(self, plugin_name: str) -> bool:
        """
        Disable a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            True if successful, False if plugin not found
        """
        if plugin_name not in self._state:
            # Plugin not registered yet
            self._state[plugin_name] = {"enabled": False, "version": "unknown"}

        self._state[plugin_name]["enabled"] = False
        self._save_state()
        return True

    def get_enabled_plugins(self) -> List[str]:
        """
        Get list of enabled plugin names.

        Returns:
            List of enabled plugin names
        """
        return [
            name
            for name in self.plugins.keys()
            if self.is_enabled(name)
        ]

    def get_disabled_plugins(self) -> List[str]:
        """
        Get list of disabled plugin names.

        Returns:
            List of disabled plugin names
        """
        return [
            name
            for name in self.plugins.keys()
            if not self.is_enabled(name)
        ]

    def get_all_plugins(self) -> List[str]:
        """
        Get list of all registered plugin names.

        Returns:
            List of all plugin names
        """
        return list(self.plugins.keys())

    def get_metadata(self, plugin_name: str) -> Optional[PluginMetadata]:
        """
        Get metadata for a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            PluginMetadata or None if not found
        """
        return self.plugins.get(plugin_name)

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict]:
        """
        Get full info for a plugin (metadata + state).

        Args:
            plugin_name: Plugin name

        Returns:
            Dict with plugin info or None if not found
        """
        if plugin_name not in self.plugins:
            return None

        metadata = self.plugins[plugin_name]
        state = self._state.get(plugin_name, {"enabled": True})

        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "tags": metadata.tags,
            "requires": metadata.requires,
            "enabled": state.get("enabled", True),
            "homepage": metadata.homepage,
            "repository": metadata.repository,
            "license": metadata.license,
        }

    def check_dependencies(self, plugin_name: str) -> List[str]:
        """
        Check if plugin dependencies are satisfied.

        Args:
            plugin_name: Plugin name

        Returns:
            List of missing dependencies (empty = all OK)
        """
        if plugin_name not in self.plugins:
            return [f"Plugin '{plugin_name}' not found"]

        metadata = self.plugins[plugin_name]
        missing = []

        # Check Python version
        if "python" in metadata.requires:
            # Basic version check (could be enhanced)
            pass

        # Check required packages
        if "packages" in metadata.requires:
            packages = metadata.requires["packages"]
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

        return missing

    def find_by_tag(self, tag: str) -> List[str]:
        """
        Find plugins by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of plugin names with the tag
        """
        return [
            name
            for name, metadata in self.plugins.items()
            if tag in metadata.tags
        ]

    def get_stats(self) -> Dict:
        """
        Get registry statistics.

        Returns:
            Dict with stats (total, enabled, disabled, by tag)
        """
        enabled = self.get_enabled_plugins()
        disabled = self.get_disabled_plugins()

        # Count by tag
        tags_count: Dict[str, int] = {}
        for metadata in self.plugins.values():
            for tag in metadata.tags:
                tags_count[tag] = tags_count.get(tag, 0) + 1

        return {
            "total": len(self.plugins),
            "enabled": len(enabled),
            "disabled": len(disabled),
            "tags": tags_count,
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return f"<PluginRegistry total={stats['total']} enabled={stats['enabled']} disabled={stats['disabled']}>"
