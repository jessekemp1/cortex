"""
Tests for the prompt versioning system.

Tests cover:
- YAML template loading
- Variable substitution and validation
- Registry operations
- A/B testing assignment consistency
"""

import json
from pathlib import Path

import pytest
from cortex.prompts.ab_testing import ABTestManager, simple_ab_test
from cortex.prompts.base import PromptTemplate
from cortex.prompts.registry import PromptRegistry


class TestPromptTemplate:
    """Test PromptTemplate class."""

    def test_render_basic(self):
        """Test basic variable substitution."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name}, you are {age} years old.",
            variables=["name", "age"],
        )

        result = template.render(name="Alice", age=30)
        assert result == "Hello Alice, you are 30 years old."

    def test_render_missing_variable(self):
        """Test that missing variables raise ValueError."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name}!",
            variables=["name"],
        )

        with pytest.raises(ValueError, match="Missing required variables"):
            template.render()

    def test_validate_variables_success(self):
        """Test variable validation succeeds when correct."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name} and {friend}!",
            variables=["name", "friend"],
        )

        assert template.validate_variables() is True

    def test_validate_variables_missing_in_template(self):
        """Test validation fails when declared variable not in template."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name}!",
            variables=["name", "age"],  # age not in template
        )

        with pytest.raises(ValueError, match="Declared but not in template"):
            template.validate_variables()

    def test_validate_variables_undeclared(self):
        """Test validation fails when template has undeclared variable."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name} and {friend}!",
            variables=["name"],  # friend not declared
        )

        with pytest.raises(ValueError, match="In template but not declared"):
            template.validate_variables()

    def test_from_yaml(self, tmp_path):
        """Test loading template from YAML file."""
        yaml_content = """
name: test_prompt
version: "1.0.0"
description: "Test prompt"
template: "Hello {name}!"
variables:
  - name
metadata:
  author: "test"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        template = PromptTemplate.from_yaml(yaml_file)

        assert template.name == "test_prompt"
        assert template.version == "1.0.0"
        assert template.description == "Test prompt"
        assert "name" in template.variables
        assert template.metadata["author"] == "test"

    def test_from_yaml_missing_file(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            PromptTemplate.from_yaml(Path("/nonexistent/file.yaml"))

    def test_from_yaml_missing_required_field(self, tmp_path):
        """Test loading with missing required field raises error."""
        yaml_content = """
name: test_prompt
version: "1.0.0"
# Missing template and variables
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Missing required fields"):
            PromptTemplate.from_yaml(yaml_file)

    def test_to_yaml(self, tmp_path):
        """Test saving template to YAML."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            template="Hello {name}!",
            variables=["name"],
            description="Test template",
            metadata={"author": "test"},
        )

        yaml_file = tmp_path / "output.yaml"
        template.to_yaml(yaml_file)

        assert yaml_file.exists()

        # Load it back and verify
        loaded = PromptTemplate.from_yaml(yaml_file)
        assert loaded.name == template.name
        assert loaded.version == template.version
        assert loaded.template == template.template

    def test_compare_version(self):
        """Test version comparison."""
        template1 = PromptTemplate(name="test", version="1.0.0", template="", variables=[])
        template2 = PromptTemplate(name="test", version="1.0.1", template="", variables=[])
        template3 = PromptTemplate(name="test", version="2.0.0", template="", variables=[])

        assert template1.compare_version(template2) == -1  # 1.0.0 < 1.0.1
        assert template2.compare_version(template1) == 1  # 1.0.1 > 1.0.0
        assert template1.compare_version(template1) == 0  # 1.0.0 == 1.0.0
        assert template1.compare_version(template3) == -1  # 1.0.0 < 2.0.0

    def test_compare_version_different_prompts(self):
        """Test comparing versions of different prompts raises error."""
        template1 = PromptTemplate(name="test1", version="1.0.0", template="", variables=[])
        template2 = PromptTemplate(name="test2", version="1.0.0", template="", variables=[])

        with pytest.raises(ValueError, match="Cannot compare versions"):
            template1.compare_version(template2)

    def test_record_usage(self):
        """Test usage recording."""
        template = PromptTemplate(name="test", version="1.0.0", template="", variables=[])

        assert template.metadata.get("usage_count", 0) == 0

        template.record_usage()
        assert template.metadata["usage_count"] == 1
        assert "last_used" in template.metadata

        template.record_usage()
        assert template.metadata["usage_count"] == 2

    def test_record_quality_score(self):
        """Test quality score recording."""
        template = PromptTemplate(name="test", version="1.0.0", template="", variables=[])

        template.record_quality_score(0.8)
        template.record_quality_score(0.9)
        template.record_quality_score(0.7)

        assert len(template.metadata["quality_scores"]) == 3
        assert template.metadata["avg_quality_score"] == pytest.approx(0.8)


class TestPromptRegistry:
    """Test PromptRegistry class."""

    def test_init_default_dir(self):
        """Test registry initializes with default directory."""
        registry = PromptRegistry()
        assert registry.prompts_dir.exists()

    def test_init_custom_dir(self, tmp_path):
        """Test registry initializes with custom directory."""
        registry = PromptRegistry(prompts_dir=tmp_path)
        assert registry.prompts_dir == tmp_path

    def test_load_templates_from_real_prompts(self):
        """Test loading actual v1 templates from cortex/prompts/versions/v1/."""
        registry = PromptRegistry()

        # Should load briefing, recommendation, etc.
        templates = registry.list_prompts()
        assert len(templates) > 0

        # Check briefing template exists
        briefing = registry.get_prompt("briefing_generation")
        if briefing:  # May not exist in all environments
            assert briefing.name == "briefing_generation"
            assert "date" in briefing.variables

    def test_get_prompt_by_name(self, tmp_path):
        """Test getting prompt by name."""
        # Create test template
        versions_dir = tmp_path / "versions" / "v1"
        versions_dir.mkdir(parents=True)

        yaml_content = """
name: test_prompt
version: "1.0.0"
template: "Test {var}"
variables:
  - var
"""
        (versions_dir / "test.yaml").write_text(yaml_content)

        registry = PromptRegistry(prompts_dir=tmp_path)
        template = registry.get_prompt("test_prompt")

        assert template is not None
        assert template.name == "test_prompt"

    def test_get_prompt_specific_version(self, tmp_path):
        """Test getting specific version of a prompt."""
        # Create v1
        v1_dir = tmp_path / "versions" / "v1"
        v1_dir.mkdir(parents=True)
        (v1_dir / "test.yaml").write_text("""
name: test_prompt
version: "1.0.0"
template: "V1 {var}"
variables:
  - var
""")

        # Create v2
        v2_dir = tmp_path / "versions" / "v2"
        v2_dir.mkdir(parents=True)
        (v2_dir / "test.yaml").write_text("""
name: test_prompt
version: "2.0.0"
template: "V2 {var}"
variables:
  - var
""")

        registry = PromptRegistry(prompts_dir=tmp_path)

        v1_template = registry.get_prompt("test_prompt", version="v1")
        v2_template = registry.get_prompt("test_prompt", version="v2")

        assert v1_template.template == "V1 {var}"
        assert v2_template.template == "V2 {var}"

    def test_get_prompt_latest_version(self, tmp_path):
        """Test getting latest version when no version specified."""
        # Create multiple versions
        for v in ["v1", "v2", "v3"]:
            v_dir = tmp_path / "versions" / v
            v_dir.mkdir(parents=True)
            (v_dir / "test.yaml").write_text(f"""
name: test_prompt
version: "{v[1:]}.0.0"
template: "{v} {{var}}"
variables:
  - var
""")

        registry = PromptRegistry(prompts_dir=tmp_path)
        template = registry.get_prompt("test_prompt")  # No version specified

        assert template.template == "v3 {var}"  # Should get v3 (latest)

    def test_list_prompts(self, tmp_path):
        """Test listing all prompts."""
        v1_dir = tmp_path / "versions" / "v1"
        v1_dir.mkdir(parents=True)

        for name in ["prompt1", "prompt2"]:
            (v1_dir / f"{name}.yaml").write_text(f"""
name: {name}
version: "1.0.0"
description: "Test {name}"
template: "Test"
variables: []
""")

        registry = PromptRegistry(prompts_dir=tmp_path)
        prompts = registry.list_prompts()

        assert len(prompts) == 2
        names = [p["name"] for p in prompts]
        assert "prompt1" in names
        assert "prompt2" in names

    def test_reload(self, tmp_path):
        """Test reloading templates from disk."""
        v1_dir = tmp_path / "versions" / "v1"
        v1_dir.mkdir(parents=True)

        # Create initial template
        (v1_dir / "test.yaml").write_text("""
name: test_prompt
version: "1.0.0"
template: "Original"
variables: []
""")

        registry = PromptRegistry(prompts_dir=tmp_path)
        assert registry.get_prompt("test_prompt").template == "Original"

        # Modify template on disk
        (v1_dir / "test.yaml").write_text("""
name: test_prompt
version: "1.0.0"
template: "Modified"
variables: []
""")

        registry.reload()
        assert registry.get_prompt("test_prompt").template == "Modified"

    def test_register_template(self):
        """Test programmatic template registration."""
        registry = PromptRegistry()

        template = PromptTemplate(
            name="dynamic_template",
            version="1.0.0",
            template="Dynamic {var}",
            variables=["var"],
        )

        registry.register_template(template, version="v1")

        retrieved = registry.get_prompt("dynamic_template")
        assert retrieved.name == "dynamic_template"
        assert retrieved.template == "Dynamic {var}"

    def test_get_versions(self, tmp_path):
        """Test getting all versions of a prompt."""
        for v in ["v1", "v2", "v3"]:
            v_dir = tmp_path / "versions" / v
            v_dir.mkdir(parents=True)
            (v_dir / "test.yaml").write_text(f"""
name: test_prompt
version: "{v[1:]}.0.0"
template: "Test"
variables: []
""")

        registry = PromptRegistry(prompts_dir=tmp_path)
        versions = registry.get_versions("test_prompt")

        assert versions == ["v1", "v2", "v3"]


class TestABTesting:
    """Test A/B testing framework."""

    def test_get_variant_consistent(self):
        """Test that same user always gets same variant."""
        manager = ABTestManager()

        variant1 = manager.get_variant("test_prompt", "user123", {"v1": 0.5, "v2": 0.5})
        variant2 = manager.get_variant("test_prompt", "user123", {"v1": 0.5, "v2": 0.5})

        assert variant1 == variant2  # Consistent assignment

    def test_get_variant_different_users(self):
        """Test that different users can get different variants."""
        manager = ABTestManager()

        # Try many users - should get both variants
        variants = set()
        for i in range(100):
            variant = manager.get_variant("test_prompt", f"user{i}", {"v1": 0.5, "v2": 0.5})
            variants.add(variant)

        # With 100 users, should see both variants
        assert len(variants) == 2
        assert "v1" in variants
        assert "v2" in variants

    def test_get_variant_weighted(self):
        """Test weighted variant distribution."""
        manager = ABTestManager()

        # Test many assignments
        v1_count = 0
        v2_count = 0

        for i in range(1000):
            variant = manager.get_variant("test_prompt", f"user{i}", {"v1": 0.8, "v2": 0.2})
            if variant == "v1":
                v1_count += 1
            else:
                v2_count += 1

        # Should be roughly 80/20 split (allow some variance)
        v1_ratio = v1_count / 1000
        assert 0.75 < v1_ratio < 0.85

    def test_get_variant_invalid_weights(self):
        """Test that invalid weights raise error."""
        manager = ABTestManager()

        with pytest.raises(ValueError, match="must sum to 1.0"):
            manager.get_variant("test_prompt", "user123", {"v1": 0.6, "v2": 0.6})

    def test_get_variant_logs_assignment(self, tmp_path):
        """Test that assignments are logged."""
        manager = ABTestManager(log_dir=tmp_path)

        manager.get_variant("test_prompt", "user123", {"v1": 0.5, "v2": 0.5})

        assignments_file = tmp_path / "assignments.jsonl"
        assert assignments_file.exists()

        with open(assignments_file) as f:
            assignment = json.loads(f.readline())

        assert assignment["prompt_name"] == "test_prompt"
        assert assignment["user_id"] == "user123"
        assert assignment["variant"] in ["v1", "v2"]

    def test_get_assignment_stats(self, tmp_path):
        """Test getting assignment statistics."""
        manager = ABTestManager(log_dir=tmp_path)

        # Create some assignments
        for i in range(100):
            manager.get_variant("test_prompt", f"user{i}", {"v1": 0.5, "v2": 0.5})

        stats = manager.get_assignment_stats("test_prompt")

        assert stats["total"] == 100
        assert "v1" in stats["variants"]
        assert "v2" in stats["variants"]
        assert stats["variants"]["v1"]["count"] + stats["variants"]["v2"]["count"] == 100

    def test_simple_ab_test(self):
        """Test simple A/B test helper function."""
        variant = simple_ab_test("test_prompt", "user123", control="v1", treatment="v2")
        assert variant in ["v1", "v2"]

        # Should be consistent
        variant2 = simple_ab_test("test_prompt", "user123", control="v1", treatment="v2")
        assert variant == variant2


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_load_render_template(self):
        """Test loading a real template and rendering it."""
        registry = PromptRegistry()

        # Try to load briefing template (if it exists)
        template = registry.get_prompt("briefing_generation")

        if template:
            # Render with sample data
            result = template.render(
                date="2026-02-01",
                portfolio_pulse="3 active projects",
                active_goals="Complete Phase 1",
                recent_activity="10 commits in last 24h",
            )

            assert "2026-02-01" in result
            assert "3 active projects" in result

    def test_ab_test_with_registry(self, tmp_path):
        """Test A/B testing with registry templates."""
        # Create two versions of a template
        for v in ["v1", "v2"]:
            v_dir = tmp_path / "versions" / v
            v_dir.mkdir(parents=True)
            (v_dir / "test.yaml").write_text(f"""
name: test_prompt
version: "{v[1:]}.0.0"
template: "{v} template {{var}}"
variables:
  - var
""")

        registry = PromptRegistry(prompts_dir=tmp_path)
        manager = ABTestManager()

        # Get variant for user
        variant = manager.get_variant("test_prompt", "user123", {"v1": 0.5, "v2": 0.5})

        # Load corresponding template
        template = registry.get_prompt("test_prompt", version=variant)

        # Render it
        result = template.render(var="test")

        assert variant in result  # Should contain "v1" or "v2"
        assert "test" in result
