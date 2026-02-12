"""
Base classes for prompt template management.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class PromptTemplate:
    """Versioned prompt template with variable substitution.

    Attributes:
        name: Unique identifier for the prompt
        version: Semantic version (e.g., "1.0.0")
        template: Template string with {variable} placeholders
        variables: List of required variable names
        metadata: Additional metadata (author, created, metrics)
        description: Human-readable description
    """

    name: str
    version: str
    template: str
    variables: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def render(self, **kwargs) -> str:
        """Render template with provided variables.

        Args:
            **kwargs: Variable values to substitute

        Returns:
            Rendered template string

        Raises:
            ValueError: If required variables are missing
        """
        # Validate all required variables are provided
        missing = set(self.variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables for prompt '{self.name}': {missing}")

        # Perform substitution
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Variable {e} not found in template") from e

    def validate_variables(self) -> bool:
        """Validate that template contains all declared variables.

        Returns:
            True if valid, raises ValueError otherwise
        """
        # Extract variables from template
        template_vars = set(re.findall(r"\{(\w+)\}", self.template))

        # Check all declared variables exist in template
        declared = set(self.variables)
        if template_vars != declared:
            missing_in_template = declared - template_vars
            undeclared = template_vars - declared
            msg = []
            if missing_in_template:
                msg.append(f"Declared but not in template: {missing_in_template}")
            if undeclared:
                msg.append(f"In template but not declared: {undeclared}")
            raise ValueError("; ".join(msg))

        return True

    @classmethod
    def from_yaml(cls, path: Path) -> "PromptTemplate":
        """Load template from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            PromptTemplate instance

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ValueError: If YAML format is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Validate required fields
        required = ["name", "version", "template", "variables"]
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"Missing required fields in {path}: {missing}")

        return cls(
            name=data["name"],
            version=data["version"],
            template=data["template"],
            variables=data["variables"],
            metadata=data.get("metadata", {}),
            description=data.get("description", ""),
        )

    def to_yaml(self, path: Path) -> None:
        """Save template to YAML file.

        Args:
            path: Path to write YAML file
        """
        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "template": self.template,
            "variables": self.variables,
            "metadata": self.metadata,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def compare_version(self, other: "PromptTemplate") -> int:
        """Compare versions with another template.

        Args:
            other: Another PromptTemplate

        Returns:
            -1 if self < other, 0 if equal, 1 if self > other
        """
        if self.name != other.name:
            raise ValueError("Cannot compare versions of different prompts")

        # Parse semantic versions
        self_parts = [int(x) for x in self.version.split(".")]
        other_parts = [int(x) for x in other.version.split(".")]

        # Compare major.minor.patch
        for s, o in zip(self_parts, other_parts):
            if s < o:
                return -1
            elif s > o:
                return 1

        # Equal or one is longer
        if len(self_parts) < len(other_parts):
            return -1
        elif len(self_parts) > len(other_parts):
            return 1
        else:
            return 0

    def record_usage(self) -> None:
        """Record a usage of this template (updates metadata)."""
        if "usage_count" not in self.metadata:
            self.metadata["usage_count"] = 0
        self.metadata["usage_count"] += 1
        self.metadata["last_used"] = datetime.now().isoformat()

    def record_quality_score(self, score: float) -> None:
        """Record a quality score for this template.

        Args:
            score: Quality score (0.0 to 1.0)
        """
        if "quality_scores" not in self.metadata:
            self.metadata["quality_scores"] = []

        self.metadata["quality_scores"].append(
            {"score": score, "timestamp": datetime.now().isoformat()}
        )

        # Update average
        scores = [s["score"] for s in self.metadata["quality_scores"]]
        self.metadata["avg_quality_score"] = sum(scores) / len(scores)
