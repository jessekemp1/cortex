import datetime
from pathlib import Path
from typing import Optional


class SpecGenerator:
    """Generates Golden Spec skeletons based on user intent."""

    GOLDEN_SPEC_TEMPLATE = """# GOLDEN SPEC: {project_name}

**Date**: {date}
**Status**: Draft
**Intent**: {intent}

---

## 1. Deep Understanding (The "Why")

**Core Problem**: {intent}

*Tip: Use the 5 Whys to dig deeper. Why is this a problem? Why now?*

### Context & Background
- [ ] What is the current state?
- [ ] Who are the stakeholders?

---

## 2. Outcome Definition (The "What")

**Target Outcome**:

*Tip: Describe the end state as if it has already happened. Be specific and measurable.*

### Success Metrics
- [ ] Metric 1:
- [ ] Metric 2:

---

## 3. Outcome Validation (The "Check")

- [ ] Is this the right problem to solve?
- [ ] Does this outcome actually solve the problem?
- [ ] Is it feasible?

---

## 4. Solution Design (The "How")

**Proposed Solution**:

*Tip: Brainstorm 3 options before picking one.*

### Architecture
- Component A:
- Component B:

---

## 5. Solution-Outcome Alignment

- [ ] Does this solution achieve the Target Outcome?
- [ ] Are there any side effects?

---

## 6. Implementation Planning (The "When")

### Tasks
- [ ] T1:
- [ ] T2:

### Resources
- Required:

---

## 7. Success Verification (The "Proof")

- [ ] How will we verify Metric 1?
- [ ] How will we verify Metric 2?

---

**Next Step**: Run `cortex check` to validate this spec.
"""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir

    def generate(
        self, intent: str, project_name: str, target_dir: Optional[Path] = None
    ) -> Path:
        """
        Generate a GOLDEN_SPEC.md file.

        Args:
            intent: The user's intended goal.
            project_name: Name of the project.
            target_dir: Directory to write the spec to (defaults to root/project_name or cwd).

        Returns:
            Path to the created file.
        """
        if target_dir is None:
            # Default to current working directory if not specified
            target_dir = Path.cwd()

        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        content = self.GOLDEN_SPEC_TEMPLATE.format(
            project_name=project_name,
            date=datetime.date.today().isoformat(),
            intent=intent,
        )

        # Determine filename
        # If project_name is generic or empty, use GOLDEN_SPEC.md
        # If project_name is specific, use PROJECT_NAME_SPEC.md
        filename = "GOLDEN_SPEC.md"
        file_path = target_dir / filename

        if file_path.exists():
            # Don't overwrite, append timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = target_dir / f"GOLDEN_SPEC_{timestamp}.md"

        file_path.write_text(content)
        return file_path
