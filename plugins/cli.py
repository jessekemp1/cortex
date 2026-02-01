#!/usr/bin/env python3
"""
Plugin CLI - Command-line interface for plugin management

Provides /plugin commands for listing, info, enable, disable, and install.
"""

import sys
from pathlib import Path
from typing import Optional

# Handle both direct execution and module import
if __name__ == "__main__" or "cortex.plugins" not in sys.modules:
    # Add parent directory to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from cortex.plugins.loader import PluginLoader
    from cortex.plugins.registry import PluginRegistry
else:
    from .loader import PluginLoader
    from .registry import PluginRegistry


class PluginCLI:
    """
    CLI for plugin management.

    Handles:
    - /plugin list - Show all plugins
    - /plugin info <name> - Show plugin details
    - /plugin enable <name> - Enable plugin
    - /plugin disable <name> - Disable plugin
    - /plugin install <path> - Install external plugin
    """

    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Initialize plugin CLI.

        Args:
            plugins_dir: Path to plugins directory (default: cortex/plugins/)
        """
        if plugins_dir is None:
            # Auto-detect from current file location
            plugins_dir = Path(__file__).parent

        self.plugins_dir = plugins_dir
        self.loader = PluginLoader(plugins_dir)
        self.registry = PluginRegistry()

    def run(self, args: list[str]) -> int:
        """
        Run plugin CLI command.

        Args:
            args: Command-line arguments (e.g., ["list"], ["info", "status"])

        Returns:
            Exit code (0 = success)
        """
        if not args or args[0] in ["--help", "-h", "help"]:
            self._show_help()
            return 0

        command = args[0]
        command_args = args[1:]

        if command == "list":
            return self._list_plugins(command_args)
        elif command == "info":
            return self._info_plugin(command_args)
        elif command == "enable":
            return self._enable_plugin(command_args)
        elif command == "disable":
            return self._disable_plugin(command_args)
        elif command == "install":
            return self._install_plugin(command_args)
        else:
            print(f"❌ Unknown command: {command}", file=sys.stderr)
            print("Use '/plugin help' for usage", file=sys.stderr)
            return 1

    def _show_help(self) -> None:
        """Show help message."""
        print("""Plugin Management CLI

Usage:
  /plugin list [--all]              List all plugins
  /plugin info <name>               Show plugin details
  /plugin enable <name>             Enable a plugin
  /plugin disable <name>            Disable a plugin
  /plugin install <path>            Install external plugin
  /plugin help                      Show this help

Examples:
  /plugin list                      # Show enabled plugins
  /plugin list --all                # Show all plugins (including disabled)
  /plugin info status               # Show status plugin details
  /plugin disable briefing          # Disable briefing plugin
  /plugin enable briefing           # Re-enable briefing plugin
""")

    def _list_plugins(self, args: list[str]) -> int:
        """
        List all plugins.

        Args:
            args: Command arguments

        Returns:
            Exit code
        """
        show_all = "--all" in args or "-a" in args

        # Load all plugins
        all_plugins = self.loader.load_all_plugins(skip_disabled=False)

        # Register all plugins
        for plugin in all_plugins.values():
            self.registry.register(plugin)

        # Get enabled/disabled lists
        enabled = self.registry.get_enabled_plugins()
        disabled = self.registry.get_disabled_plugins()

        if not all_plugins:
            print("No plugins found")
            return 0

        # Show enabled plugins
        print(f"📦 Available Plugins ({len(all_plugins)} total)")
        print("═" * 60)
        print()

        if enabled:
            print(f"✓ Enabled ({len(enabled)}):")
            print("─" * 40)
            for name in sorted(enabled):
                if name in all_plugins:
                    plugin = all_plugins[name]
                    desc = plugin.metadata.description[:50]
                    tags = ", ".join(plugin.metadata.tags[:3])
                    print(f"  {name:12s} v{plugin.metadata.version:6s} - {desc}")
                    if tags:
                        print(f"              Tags: {tags}")
            print()

        if disabled and show_all:
            print(f"✗ Disabled ({len(disabled)}):")
            print("─" * 40)
            for name in sorted(disabled):
                if name in all_plugins:
                    plugin = all_plugins[name]
                    desc = plugin.metadata.description[:50]
                    print(f"  {name:12s} v{plugin.metadata.version:6s} - {desc}")
            print()

        if disabled and not show_all:
            print(f"💡 {len(disabled)} disabled plugin(s). Use '/plugin list --all' to see them.")
            print()

        return 0

    def _info_plugin(self, args: list[str]) -> int:
        """
        Show plugin info.

        Args:
            args: Command arguments (plugin name)

        Returns:
            Exit code
        """
        if not args:
            print("❌ Plugin name required", file=sys.stderr)
            print("Usage: /plugin info <name>", file=sys.stderr)
            return 1

        plugin_name = args[0]

        # Load plugin
        plugin = self.loader.load_plugin(plugin_name)
        if not plugin:
            print(f"❌ Plugin '{plugin_name}' not found", file=sys.stderr)
            return 1

        # Register and get info
        self.registry.register(plugin)
        info = self.registry.get_plugin_info(plugin_name)

        if not info:
            print(f"❌ Could not get info for '{plugin_name}'", file=sys.stderr)
            return 1

        # Display info
        print(f"📦 Plugin: {info['name']} (v{info['version']})")
        print("═" * 60)
        print()
        print(f"Description: {info['description']}")
        print(f"Author:      {info.get('author', 'Unknown')}")
        print(f"Status:      {'✓ Enabled' if info['enabled'] else '✗ Disabled'}")
        print()

        if info.get('tags'):
            print(f"Tags:        {', '.join(info['tags'])}")
            print()

        if info.get('requires'):
            print("Requirements:")
            requires = info['requires']
            if 'python' in requires:
                print(f"  Python:    {requires['python']}")
            if 'packages' in requires:
                packages = requires['packages']
                if isinstance(packages, list):
                    print(f"  Packages:  {', '.join(packages)}")
                elif isinstance(packages, dict):
                    for pkg, ver in packages.items():
                        print(f"  - {pkg}: {ver}")
            print()

        if info.get('homepage'):
            print(f"Homepage:    {info['homepage']}")
        if info.get('repository'):
            print(f"Repository:  {info['repository']}")
        if info.get('license'):
            print(f"License:     {info['license']}")

        print()
        print("Run '/plugin help' or '/<name> --help' for usage")

        return 0

    def _enable_plugin(self, args: list[str]) -> int:
        """
        Enable a plugin.

        Args:
            args: Command arguments (plugin name)

        Returns:
            Exit code
        """
        if not args:
            print("❌ Plugin name required", file=sys.stderr)
            print("Usage: /plugin enable <name>", file=sys.stderr)
            return 1

        plugin_name = args[0]

        # Load plugin to verify it exists
        plugin = self.loader.load_plugin(plugin_name)
        if not plugin:
            print(f"❌ Plugin '{plugin_name}' not found", file=sys.stderr)
            return 1

        # Register and enable
        self.registry.register(plugin)
        self.registry.enable(plugin_name)

        print(f"✓ Plugin '{plugin_name}' enabled")
        print(f"  Run '/{plugin_name}' to use it")

        return 0

    def _disable_plugin(self, args: list[str]) -> int:
        """
        Disable a plugin.

        Args:
            args: Command arguments (plugin name)

        Returns:
            Exit code
        """
        if not args:
            print("❌ Plugin name required", file=sys.stderr)
            print("Usage: /plugin disable <name>", file=sys.stderr)
            return 1

        plugin_name = args[0]

        # Load plugin to verify it exists
        plugin = self.loader.load_plugin(plugin_name)
        if not plugin:
            print(f"❌ Plugin '{plugin_name}' not found", file=sys.stderr)
            return 1

        # Register and disable
        self.registry.register(plugin)
        self.registry.disable(plugin_name)

        print(f"✓ Plugin '{plugin_name}' disabled")
        print(f"  Use '/plugin enable {plugin_name}' to re-enable")

        return 0

    def _install_plugin(self, args: list[str]) -> int:
        """
        Install external plugin.

        Args:
            args: Command arguments (path to plugin)

        Returns:
            Exit code
        """
        if not args:
            print("❌ Plugin path required", file=sys.stderr)
            print("Usage: /plugin install <path>", file=sys.stderr)
            return 1

        plugin_path = Path(args[0])

        if not plugin_path.exists():
            print(f"❌ Path not found: {plugin_path}", file=sys.stderr)
            return 1

        if not plugin_path.is_dir():
            print(f"❌ Path is not a directory: {plugin_path}", file=sys.stderr)
            return 1

        # Check for required files
        plugin_md = plugin_path / "PLUGIN.md"
        plugin_py = plugin_path / "plugin.py"

        if not plugin_md.exists():
            print(f"❌ PLUGIN.md not found in {plugin_path}", file=sys.stderr)
            return 1

        if not plugin_py.exists():
            print(f"❌ plugin.py not found in {plugin_path}", file=sys.stderr)
            return 1

        # Copy to plugins directory
        import shutil
        dest_path = self.plugins_dir / plugin_path.name

        if dest_path.exists():
            print(f"⚠️  Plugin '{plugin_path.name}' already exists", file=sys.stderr)
            print("   Remove it first or use a different name", file=sys.stderr)
            return 1

        try:
            shutil.copytree(plugin_path, dest_path)
            print(f"✓ Plugin '{plugin_path.name}' installed successfully")
            print(f"  Location: {dest_path}")
            print(f"  Run '/plugin info {plugin_path.name}' for details")
            return 0
        except Exception as e:
            print(f"❌ Installation failed: {e}", file=sys.stderr)
            return 1


def main():
    """Main entry point for CLI."""
    cli = PluginCLI()
    sys.exit(cli.run(sys.argv[1:]))


if __name__ == "__main__":
    main()
