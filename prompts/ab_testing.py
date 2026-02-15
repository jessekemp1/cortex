"""
A/B testing framework for prompt variants.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from cortex.state_paths import get_cortex_dir


@dataclass
class ExperimentAssignment:
    """Record of an A/B test assignment.

    Attributes:
        prompt_name: Name of the prompt being tested
        user_id: Identifier for the user
        variant: Which variant was assigned (e.g., "v1", "v2")
        assigned_at: When assignment was made
        metadata: Additional experiment metadata
    """

    prompt_name: str
    user_id: str
    variant: str
    assigned_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, any] = field(default_factory=dict)


class ABTestManager:
    """Manages A/B testing for prompt templates.

    Uses consistent hash-based assignment to ensure users always
    get the same variant for a given experiment.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize A/B test manager.

        Args:
            log_dir: Directory to log assignments (defaults to ~/.cortex/ab_tests/)
        """
        if log_dir is None:
            log_dir = get_cortex_dir() / "ab_tests"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.assignments_file = self.log_dir / "assignments.jsonl"

    def get_variant(
        self,
        prompt_name: str,
        user_id: str,
        variants: Dict[str, float],
        experiment_id: Optional[str] = None,
    ) -> str:
        """Get assigned variant for a user in an A/B test.

        Uses consistent hashing to ensure same user always gets same variant.

        Args:
            prompt_name: Name of the prompt
            user_id: User identifier (can be session ID, username, etc.)
            variants: Dict of variant -> weight (e.g., {"v1": 0.5, "v2": 0.5})
            experiment_id: Optional experiment identifier for tracking

        Returns:
            Variant identifier (e.g., "v1")

        Example:
            >>> manager = ABTestManager()
            >>> variant = manager.get_variant(
            ...     "briefing",
            ...     "user123",
            ...     {"v1": 0.5, "v2": 0.5}
            ... )
            >>> print(variant)  # "v1" or "v2"
        """
        # Validate weights sum to 1.0
        total_weight = sum(variants.values())
        if not (0.99 <= total_weight <= 1.01):  # Allow small floating point error
            raise ValueError(f"Variant weights must sum to 1.0, got {total_weight}")

        # Create consistent hash from prompt + user
        hash_input = f"{prompt_name}:{user_id}"
        if experiment_id:
            hash_input = f"{experiment_id}:{hash_input}"

        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()
        # Convert to 0-1 range
        hash_float = int(hash_value[:16], 16) / (2**64)

        # Assign variant based on hash
        cumulative = 0.0
        assigned_variant = None

        sorted_variants = sorted(variants.items())  # Consistent ordering
        for variant, weight in sorted_variants:
            cumulative += weight
            if hash_float <= cumulative:
                assigned_variant = variant
                break

        # Fallback to first variant (shouldn't happen)
        if assigned_variant is None:
            assigned_variant = sorted_variants[0][0]

        # Log assignment
        self._log_assignment(
            prompt_name,
            user_id,
            assigned_variant,
            experiment_id=experiment_id,
            variants=variants,
        )

        return assigned_variant

    def _log_assignment(
        self,
        prompt_name: str,
        user_id: str,
        variant: str,
        experiment_id: Optional[str] = None,
        variants: Optional[Dict[str, float]] = None,
    ) -> None:
        """Log an assignment to the assignments file.

        Args:
            prompt_name: Name of the prompt
            user_id: User identifier
            variant: Assigned variant
            experiment_id: Optional experiment ID
            variants: Optional variant weights for reference
        """
        assignment = ExperimentAssignment(
            prompt_name=prompt_name,
            user_id=user_id,
            variant=variant,
            metadata={
                "experiment_id": experiment_id,
                "variants": variants,
            },
        )

        # Append to JSONL file
        with open(self.assignments_file, "a") as f:
            f.write(json.dumps(assignment.__dict__) + "\n")

    def get_assignment_stats(
        self, prompt_name: str, experiment_id: Optional[str] = None
    ) -> Dict[str, any]:
        """Get statistics for an A/B test.

        Args:
            prompt_name: Name of the prompt
            experiment_id: Optional experiment ID to filter

        Returns:
            Dict with variant counts and percentages
        """
        if not self.assignments_file.exists():
            return {"total": 0, "variants": {}}

        variant_counts: Dict[str, int] = {}
        total = 0

        with open(self.assignments_file) as f:
            for line in f:
                assignment_data = json.loads(line)

                # Filter by prompt name and optionally experiment ID
                if assignment_data["prompt_name"] != prompt_name:
                    continue

                if (
                    experiment_id
                    and assignment_data["metadata"].get("experiment_id") != experiment_id
                ):
                    continue

                variant = assignment_data["variant"]
                variant_counts[variant] = variant_counts.get(variant, 0) + 1
                total += 1

        # Calculate percentages
        variant_stats = {}
        for variant, count in variant_counts.items():
            variant_stats[variant] = {
                "count": count,
                "percentage": (count / total * 100) if total > 0 else 0,
            }

        return {"total": total, "variants": variant_stats}


def simple_ab_test(prompt_name: str, user_id: str, control: str, treatment: str) -> str:
    """Simple 50/50 A/B test helper.

    Args:
        prompt_name: Name of prompt
        user_id: User identifier
        control: Control variant ID (e.g., "v1")
        treatment: Treatment variant ID (e.g., "v2")

    Returns:
        Assigned variant (control or treatment)
    """
    manager = ABTestManager()
    return manager.get_variant(
        prompt_name=prompt_name,
        user_id=user_id,
        variants={control: 0.5, treatment: 0.5},
    )
