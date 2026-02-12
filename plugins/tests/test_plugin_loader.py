#!/usr/bin/env python3
"""
Unit tests for Cortex Plugin System

Tests:
- BasePlugin class functionality
- PluginLoader discovery and loading
- PluginRegistry state management
- PLUGIN.md parsing
- Dependency checking
"""

import tempfile
from pathlib import Path
from typing import List

import pytest
from cortex.plugins.base import BasePlugin, PluginMetadata
from cortex.plugins.loader import PluginLoader
from cortex.plugins.registry import PluginRegistry


# Test Plugin Implementation (renamed to avoid pytest collection warning)
class DummyPlugin(BasePlugin):
    """Simple dummy plugin for unit tests."""

    def execute(self, args: List[str], **kwargs) -> int:
        """Execute dummy plugin."""
        return 0


class FailingDummyPlugin(BasePlugin):
    """Plugin that fails execution."""

    def execute(self, args: List[str], **kwargs) -> int:
        """Execute and fail."""
        raise RuntimeError("Test failure")


# Fixtures
@pytest.fixture
def temp_plugin_dir():
    """Create temporary plugin directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_plugin_md():
    """Sample PLUGIN.md content."""
    return """---
name: test_plugin
version: 1.0.0
description: Test plugin for unit tests
author: Test Author
requires:
  python: ">=3.11"
  packages:
    - pytest
tags: [test, core]
enabled: true
---

# Test Plugin

This is a test plugin for unit tests.

## Usage

```bash
/test_plugin
```
"""


@pytest.fixture
def sample_plugin_py():
    """Sample plugin.py content."""
    return """from typing import List
from cortex.plugins.base import BasePlugin

class SamplePlugin(BasePlugin):
    def execute(self, args: List[str], **kwargs) -> int:
        return 0
"""


@pytest.fixture
def create_test_plugin(temp_plugin_dir, sample_plugin_md, sample_plugin_py):
    """Create a valid test plugin."""
    plugin_dir = temp_plugin_dir / "test_plugin"
    plugin_dir.mkdir()

    # Write PLUGIN.md
    (plugin_dir / "PLUGIN.md").write_text(sample_plugin_md)

    # Write plugin.py
    (plugin_dir / "plugin.py").write_text(sample_plugin_py)

    return plugin_dir


# Test PluginMetadata
class TestPluginMetadata:
    """Test PluginMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata with defaults."""
        metadata = PluginMetadata(name="test")
        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert metadata.enabled is True
        assert metadata.tags == []
        assert metadata.requires == {}

    def test_metadata_with_values(self):
        """Test creating metadata with values."""
        metadata = PluginMetadata(
            name="test",
            version="2.0.0",
            description="Test plugin",
            author="Author",
            requires={"python": ">=3.11"},
            tags=["core"],
            enabled=False,
        )
        assert metadata.name == "test"
        assert metadata.version == "2.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.author == "Author"
        assert metadata.requires == {"python": ">=3.11"}
        assert metadata.tags == ["core"]
        assert metadata.enabled is False


# Test BasePlugin
class TestBasePlugin:
    """Test BasePlugin class."""

    def test_plugin_initialization(self, create_test_plugin):
        """Test plugin can be initialized."""
        plugin = DummyPlugin(create_test_plugin.parent / "test_plugin")
        assert plugin.metadata.name == "test_plugin"
        assert plugin.metadata.version == "1.0.0"

    def test_plugin_metadata_loading(self, create_test_plugin):
        """Test metadata loading from PLUGIN.md."""
        plugin = DummyPlugin(create_test_plugin.parent / "test_plugin")
        assert plugin.metadata.description == "Test plugin for unit tests"
        assert plugin.metadata.author == "Test Author"
        assert "test" in plugin.metadata.tags
        assert "core" in plugin.metadata.tags

    def test_plugin_help(self, create_test_plugin):
        """Test help() returns PLUGIN.md content."""
        plugin = DummyPlugin(create_test_plugin.parent / "test_plugin")
        help_text = plugin.help()
        assert "test_plugin" in help_text
        assert "1.0.0" in help_text
        assert "Test Plugin" in help_text

    def test_plugin_execute(self, create_test_plugin):
        """Test execute() can be called."""
        plugin = DummyPlugin(create_test_plugin.parent / "test_plugin")
        result = plugin.execute([])
        assert result == 0

    def test_plugin_dependency_check(self, create_test_plugin):
        """Test dependency checking."""
        plugin = DummyPlugin(create_test_plugin.parent / "test_plugin")
        missing = plugin.check_dependencies()
        # pytest should be installed
        assert len(missing) == 0

    def test_missing_plugin_md(self, temp_plugin_dir):
        """Test plugin without PLUGIN.md fails gracefully."""
        plugin_dir = temp_plugin_dir / "invalid_plugin"
        plugin_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            DummyPlugin(plugin_dir)

    def test_no_frontmatter(self, temp_plugin_dir):
        """Test PLUGIN.md without frontmatter uses defaults."""
        plugin_dir = temp_plugin_dir / "no_frontmatter"
        plugin_dir.mkdir()

        (plugin_dir / "PLUGIN.md").write_text("# Plugin\n\nNo frontmatter here.")

        plugin = DummyPlugin(plugin_dir)
        assert plugin.metadata.name == "no_frontmatter"
        assert plugin.metadata.version == "1.0.0"


# Test PluginLoader
class TestPluginLoader:
    """Test PluginLoader class."""

    def test_loader_initialization(self, temp_plugin_dir):
        """Test loader can be initialized."""
        loader = PluginLoader(temp_plugin_dir)
        assert loader.plugins_dir == temp_plugin_dir
        assert loader.plugins == {}

    def test_discover_plugins(self, create_test_plugin):
        """Test plugin discovery."""
        loader = PluginLoader(create_test_plugin.parent)
        discovered = loader.discover_plugins()
        assert "test_plugin" in discovered

    def test_discover_skips_invalid(self, temp_plugin_dir):
        """Test discovery skips invalid plugins."""
        # Create directory without PLUGIN.md
        invalid_dir = temp_plugin_dir / "invalid"
        invalid_dir.mkdir()
        (invalid_dir / "plugin.py").write_text("# Empty")

        # Create directory starting with _
        template_dir = temp_plugin_dir / "_template"
        template_dir.mkdir()

        loader = PluginLoader(temp_plugin_dir)
        discovered = loader.discover_plugins()
        assert "invalid" not in discovered
        assert "_template" not in discovered

    def test_load_plugin(self, create_test_plugin):
        """Test loading a single plugin."""
        loader = PluginLoader(create_test_plugin.parent)
        plugin = loader.load_plugin("test_plugin")

        assert plugin is not None
        assert plugin.metadata.name == "test_plugin"
        assert isinstance(plugin, BasePlugin)

    def test_load_plugin_caching(self, create_test_plugin):
        """Test plugin loading caches results."""
        loader = PluginLoader(create_test_plugin.parent)
        plugin1 = loader.load_plugin("test_plugin")
        plugin2 = loader.load_plugin("test_plugin")

        assert plugin1 is plugin2  # Same instance (cached)

    def test_load_all_plugins(self, temp_plugin_dir, sample_plugin_md, sample_plugin_py):
        """Test loading all plugins."""
        # Create multiple plugins
        for i in range(3):
            plugin_dir = temp_plugin_dir / f"plugin_{i}"
            plugin_dir.mkdir()
            (plugin_dir / "PLUGIN.md").write_text(
                sample_plugin_md.replace("test_plugin", f"plugin_{i}")
            )
            (plugin_dir / "plugin.py").write_text(sample_plugin_py)

        loader = PluginLoader(temp_plugin_dir)
        plugins = loader.load_all_plugins()

        assert len(plugins) == 3
        assert "plugin_0" in plugins
        assert "plugin_1" in plugins
        assert "plugin_2" in plugins

    def test_load_disabled_plugin(self, temp_plugin_dir):
        """Test skip_disabled parameter."""
        # Create disabled plugin
        plugin_dir = temp_plugin_dir / "disabled_plugin"
        plugin_dir.mkdir()

        disabled_md = """---
name: disabled_plugin
version: 1.0.0
enabled: false
---
# Disabled Plugin
"""
        (plugin_dir / "PLUGIN.md").write_text(disabled_md)
        (plugin_dir / "plugin.py").write_text("""
from typing import List
from cortex.plugins.base import BasePlugin

class DisabledPlugin(BasePlugin):
    def execute(self, args: List[str], **kwargs) -> int:
        return 0
""")

        loader = PluginLoader(temp_plugin_dir)
        plugins = loader.load_all_plugins(skip_disabled=True)

        assert "disabled_plugin" not in plugins

        # Load with skip_disabled=False
        plugins_all = loader.load_all_plugins(skip_disabled=False)
        assert "disabled_plugin" in plugins_all

    def test_get_plugin(self, create_test_plugin):
        """Test get_plugin() method."""
        loader = PluginLoader(create_test_plugin.parent)
        loader.load_plugin("test_plugin")

        plugin = loader.get_plugin("test_plugin")
        assert plugin is not None
        assert plugin.metadata.name == "test_plugin"

        # Get non-existent plugin
        missing = loader.get_plugin("nonexistent")
        assert missing is None

    def test_reload_plugin(self, create_test_plugin):
        """Test reloading a plugin."""
        loader = PluginLoader(create_test_plugin.parent)
        plugin1 = loader.load_plugin("test_plugin")

        # Reload
        plugin2 = loader.reload_plugin("test_plugin")

        assert plugin2 is not None
        # Should be different instance (reloaded)
        assert plugin1 is not plugin2

    def test_list_plugins(self, create_test_plugin):
        """Test list_plugins() returns metadata."""
        loader = PluginLoader(create_test_plugin.parent)
        loader.load_all_plugins()

        plugin_list = loader.list_plugins()
        assert len(plugin_list) == 1
        assert plugin_list[0]["name"] == "test_plugin"
        assert plugin_list[0]["version"] == "1.0.0"
        assert plugin_list[0]["enabled"] is True

    def test_get_plugin_info(self, create_test_plugin):
        """Test get_plugin_info() returns detailed info."""
        loader = PluginLoader(create_test_plugin.parent)
        loader.load_all_plugins()

        info = loader.get_plugin_info("test_plugin")
        assert info is not None
        assert info["name"] == "test_plugin"
        assert info["version"] == "1.0.0"
        assert info["author"] == "Test Author"
        assert "test" in info["tags"]


# Test PluginRegistry
class TestPluginRegistry:
    """Test PluginRegistry class."""

    def test_registry_initialization(self, temp_plugin_dir):
        """Test registry can be initialized."""
        registry_path = temp_plugin_dir / "registry.json"
        registry = PluginRegistry(registry_path)
        assert registry.registry_path == registry_path
        assert registry.plugins == {}

    def test_register_plugin(self, create_test_plugin, temp_plugin_dir):
        """Test registering a plugin."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")

        registry.register(plugin)
        assert "test_plugin" in registry.plugins
        assert registry.is_enabled("test_plugin") is True

    def test_enable_disable(self, create_test_plugin, temp_plugin_dir):
        """Test enabling and disabling plugins."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)

        # Disable
        registry.disable("test_plugin")
        assert registry.is_enabled("test_plugin") is False

        # Enable
        registry.enable("test_plugin")
        assert registry.is_enabled("test_plugin") is True

    def test_state_persistence(self, create_test_plugin, temp_plugin_dir):
        """Test state persists across registry instances."""
        registry_path = temp_plugin_dir / "registry.json"
        plugin = DummyPlugin(create_test_plugin)

        # First registry
        registry1 = PluginRegistry(registry_path)
        registry1.register(plugin)
        registry1.disable("test_plugin")

        # Second registry (reload from file)
        registry2 = PluginRegistry(registry_path)
        registry2.register(plugin)
        assert registry2.is_enabled("test_plugin") is False

    def test_get_enabled_plugins(self, create_test_plugin, temp_plugin_dir):
        """Test getting enabled plugins."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)

        enabled = registry.get_enabled_plugins()
        assert "test_plugin" in enabled

        registry.disable("test_plugin")
        enabled = registry.get_enabled_plugins()
        assert "test_plugin" not in enabled

    def test_get_disabled_plugins(self, create_test_plugin, temp_plugin_dir):
        """Test getting disabled plugins."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)
        registry.disable("test_plugin")

        disabled = registry.get_disabled_plugins()
        assert "test_plugin" in disabled

    def test_get_plugin_info(self, create_test_plugin, temp_plugin_dir):
        """Test getting plugin info."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)

        info = registry.get_plugin_info("test_plugin")
        assert info is not None
        assert info["name"] == "test_plugin"
        assert info["version"] == "1.0.0"
        assert info["enabled"] is True

    def test_find_by_tag(self, create_test_plugin, temp_plugin_dir):
        """Test finding plugins by tag."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)

        core_plugins = registry.find_by_tag("core")
        assert "test_plugin" in core_plugins

        test_plugins = registry.find_by_tag("test")
        assert "test_plugin" in test_plugins

    def test_get_stats(self, create_test_plugin, temp_plugin_dir):
        """Test getting registry statistics."""
        plugin = DummyPlugin(create_test_plugin)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")
        registry.register(plugin)

        stats = registry.get_stats()
        assert stats["total"] == 1
        assert stats["enabled"] == 1
        assert stats["disabled"] == 0
        assert "test" in stats["tags"]
        assert stats["tags"]["test"] == 1


# Integration Tests
class TestPluginIntegration:
    """Integration tests for plugin system."""

    def test_full_workflow(self, temp_plugin_dir, sample_plugin_md, sample_plugin_py):
        """Test complete plugin workflow."""
        # Create plugin
        plugin_dir = temp_plugin_dir / "workflow_test"
        plugin_dir.mkdir()
        (plugin_dir / "PLUGIN.md").write_text(
            sample_plugin_md.replace("test_plugin", "workflow_test")
        )
        (plugin_dir / "plugin.py").write_text(sample_plugin_py)

        # Initialize loader and registry
        loader = PluginLoader(temp_plugin_dir)
        registry = PluginRegistry(temp_plugin_dir / "registry.json")

        # Discover and load
        discovered = loader.discover_plugins()
        assert "workflow_test" in discovered

        plugins = loader.load_all_plugins()
        assert "workflow_test" in plugins

        # Register
        plugin = plugins["workflow_test"]
        registry.register(plugin)

        # Check enabled
        assert registry.is_enabled("workflow_test") is True

        # Execute
        result = plugin.execute([])
        assert result == 0

        # Disable
        registry.disable("workflow_test")
        assert registry.is_enabled("workflow_test") is False

        # Re-enable
        registry.enable("workflow_test")
        assert registry.is_enabled("workflow_test") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
