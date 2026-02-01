"""
Prompt registry for loading and managing templates.
"""

from pathlib import Path
from typing import Dict, List, Optional

from cortex.prompts.base import PromptTemplate


class PromptRegistry:
    """Registry for loading and managing prompt templates.

    Loads templates from YAML files and provides access by name/version.
    Caches loaded templates for performance.
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize registry.

        Args:
            prompts_dir: Root directory for prompts (defaults to cortex/prompts/)
        """
        if prompts_dir is None:
            # Default to cortex/prompts/ directory
            cortex_root = Path(__file__).parent.parent
            prompts_dir = cortex_root / "prompts"

        self.prompts_dir = Path(prompts_dir)
        self._templates: Dict[str, Dict[str, PromptTemplate]] = {}
        self._load_all_templates()

    def _load_all_templates(self) -> None:
        """Load all YAML templates from versions/ directory."""
        versions_dir = self.prompts_dir / "versions"

        if not versions_dir.exists():
            return

        # Load all version directories
        for version_dir in versions_dir.iterdir():
            if not version_dir.is_dir():
                continue

            version = version_dir.name  # e.g., "v1"

            # Load all YAML files in this version
            for yaml_file in version_dir.glob("*.yaml"):
                try:
                    template = PromptTemplate.from_yaml(yaml_file)

                    # Store by name and version
                    if template.name not in self._templates:
                        self._templates[template.name] = {}

                    self._templates[template.name][version] = template

                except Exception as e:
                    # Log error but continue loading
                    print(f"Warning: Failed to load {yaml_file}: {e}")
                    continue

    def get_prompt(
        self, name: str, version: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """Get a prompt template by name and optional version.

        Args:
            name: Prompt name
            version: Specific version to load (e.g., "v1"), or None for latest

        Returns:
            PromptTemplate or None if not found
        """
        if name not in self._templates:
            return None

        versions = self._templates[name]

        if version is not None:
            return versions.get(version)

        # Return latest version (highest version number)
        if not versions:
            return None

        # Sort versions (v1, v2, v3, etc.)
        sorted_versions = sorted(versions.keys(), key=lambda v: int(v[1:]))
        latest_version = sorted_versions[-1]
        return versions[latest_version]

    def list_prompts(self) -> List[Dict[str, any]]:
        """List all available prompts with versions.

        Returns:
            List of dicts with prompt metadata
        """
        prompts = []

        for name, versions in self._templates.items():
            for version, template in versions.items():
                prompts.append(
                    {
                        "name": name,
                        "version": version,
                        "semantic_version": template.version,
                        "description": template.description,
                        "variables": template.variables,
                        "usage_count": template.metadata.get("usage_count", 0),
                        "avg_quality_score": template.metadata.get(
                            "avg_quality_score", None
                        ),
                    }
                )

        return prompts

    def reload(self) -> None:
        """Reload all templates from disk."""
        self._templates.clear()
        self._load_all_templates()

    def register_template(self, template: PromptTemplate, version: str) -> None:
        """Register a template programmatically.

        Args:
            template: PromptTemplate to register
            version: Version identifier (e.g., "v1")
        """
        if template.name not in self._templates:
            self._templates[template.name] = {}

        self._templates[template.name][version] = template

    def get_versions(self, name: str) -> List[str]:
        """Get all available versions for a prompt.

        Args:
            name: Prompt name

        Returns:
            List of version strings (e.g., ["v1", "v2"])
        """
        if name not in self._templates:
            return []

        return sorted(self._templates[name].keys(), key=lambda v: int(v[1:]))


# Global registry instance (singleton pattern)
_global_registry: Optional[PromptRegistry] = None


def get_registry() -> PromptRegistry:
    """Get the global prompt registry (singleton).

    Returns:
        PromptRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = PromptRegistry()
    return _global_registry
