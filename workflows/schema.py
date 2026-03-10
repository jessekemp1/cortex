"""
Workflow schema — Pydantic models for YAML workflow definitions.

Inspired by OpenClaw's Lobster but adapted for Cortex's supervisor model:
- Steps can be `shell` (subprocess) or `ai` (routed through Conductor)
- Conditions reference previous step results via `steps.<id>.success`
- Context threading passes one step's output as the next step's input

Example YAML:
    name: validate-and-deploy
    project: vortex
    steps:
      - id: test
        type: shell
        command: "pytest Vortex/backend/tests/ -v --tb=short"
        timeout: 300
      - id: deploy
        type: shell
        command: "python -m cortex.scripts.deploy_vortex"
        condition: "steps.test.success"
      - id: summarize
        type: ai
        model: sonnet
        prompt: "Summarize the test and deploy results."
        context_from: [test, deploy]
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class StepType(str, Enum):
    SHELL = "shell"
    AI = "ai"


class OnFailure(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"
    RETRY = "retry"


class Trigger(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    ON_EVENT = "on_event"


class Step(BaseModel):
    """A single workflow step."""

    id: str
    type: StepType
    description: str = ""

    # Shell step fields
    command: Optional[str] = None

    # AI step fields
    model: Optional[str] = None  # opus, sonnet, haiku
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None

    # Flow control
    condition: Optional[str] = None  # e.g. "steps.test.success"
    context_from: List[str] = Field(default_factory=list)  # step IDs whose output feeds this step
    on_failure: OnFailure = OnFailure.STOP
    retry_count: int = 0  # only used when on_failure == RETRY
    timeout: int = 120  # seconds


class Workflow(BaseModel):
    """A complete workflow definition loaded from YAML."""

    name: str
    description: str = ""
    project: Optional[str] = None
    trigger: str = "manual"  # "manual", "schedule: 0 3 * * *", "on_event: tests_pass"
    priority: str = "medium"

    steps: List[Step]

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, steps: List[Step]) -> List[Step]:
        ids = set()
        for step in steps:
            if step.id in ids:
                raise ValueError(f"Duplicate step ID: {step.id}")
            ids.add(step.id)

            if step.type == StepType.SHELL and not step.command:
                raise ValueError(f"Shell step '{step.id}' requires 'command'")
            if step.type == StepType.AI and not step.prompt:
                raise ValueError(f"AI step '{step.id}' requires 'prompt'")

            for ref in step.context_from:
                if ref not in ids:
                    raise ValueError(
                        f"Step '{step.id}' references '{ref}' in context_from, "
                        f"but it hasn't been defined yet (steps are sequential)"
                    )
            if step.condition:
                _validate_condition_refs(step.condition, ids)

        return steps

    @classmethod
    def from_yaml(cls, path: Path) -> Workflow:
        """Load a workflow from a YAML file."""
        data = yaml.safe_load(path.read_text())
        return cls(**data)

    @classmethod
    def from_yaml_string(cls, content: str) -> Workflow:
        """Load a workflow from a YAML string."""
        data = yaml.safe_load(content)
        return cls(**data)


def _validate_condition_refs(condition: str, known_ids: set[str]) -> None:
    """Validate that condition references only known step IDs."""
    # Parse "steps.<id>.success" or "steps.<id>.exit_code == 0"
    import re

    refs = re.findall(r"steps\.(\w+)\.", condition)
    for ref in refs:
        if ref not in known_ids:
            raise ValueError(
                f"Condition references unknown step '{ref}'. Known: {sorted(known_ids)}"
            )
