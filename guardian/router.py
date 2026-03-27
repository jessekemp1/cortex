"""ProjectRouter — maps file paths to project ownership and rules."""

from __future__ import annotations
import os

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ProjectInfo:
    name: str
    display_name: str
    root: str  # relative to repo root
    test_dir: str
    rules: List[str] = field(default_factory=list)


# Fallback for files outside known projects
_REPO_ROOT_PROJECT = ProjectInfo(
    name="repo_root",
    display_name="Repository Root",
    root="",
    test_dir="",
    rules=[],
)


class ProjectRouter:
    """Maps absolute file paths to project ownership using prefix matching.

    Uses longest-prefix-wins so that nested project roots resolve correctly.
    """

    REPO_ROOT = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))

    PROJECTS = [
        ProjectInfo(
            name="vortex_backend",
            display_name="Vortex Backend",
            root="Vortex/backend",
            test_dir="Vortex/backend/tests",
            rules=[
                "GRIB fixtures required for integration tests",
                "lon must use _get_grid_indices() convention",
                "No NWP model should show >60 deg direction MAE",
            ],
        ),
        ProjectInfo(
            name="vortex_frontend",
            display_name="Vortex Frontend",
            root="Vortex/frontend",
            test_dir="Vortex/frontend/src",
            rules=[
                "Run tsc --noEmit before committing",
                "Mapbox token must not be committed",
            ],
        ),
        ProjectInfo(
            name="cortex",
            display_name="Cortex",
            root="cortex",
            test_dir="cortex/tests",
            rules=[
                "No files in automation-managed directories",
                "Bridge endpoint imports must be lazy (inside functions)",
            ],
        ),
        ProjectInfo(
            name="alpha_arena",
            display_name="Alpha Arena",
            root="alpha_arena",
            test_dir="alpha_arena/tests",
            rules=[
                "Circular import risk: model_competition <-> ensemble_analyzer",
                "Use ui/command_center.py, NOT ui/app.py",
            ],
        ),
        ProjectInfo(
            name="pupil",
            display_name="Pupil",
            root="pupil",
            test_dir="pupil/tests",
            rules=[],
        ),
    ]

    def resolve(self, file_path: str) -> ProjectInfo:
        """Resolve a file path to its owning project (longest prefix wins)."""
        try:
            rel = str(Path(file_path).relative_to(self.REPO_ROOT))
        except ValueError:
            return _REPO_ROOT_PROJECT

        best: Optional[ProjectInfo] = None
        best_len = 0
        for proj in self.PROJECTS:
            if not proj.root:
                continue
            if rel.startswith(proj.root + "/") or rel == proj.root:
                if len(proj.root) > best_len:
                    best = proj
                    best_len = len(proj.root)

        return best or _REPO_ROOT_PROJECT

    def get_project(self, name: str) -> Optional[ProjectInfo]:
        """Look up a project by name."""
        for proj in self.PROJECTS:
            if proj.name == name:
                return proj
        return None

    def get_rules(self, file_path: str) -> List[str]:
        """Get project-specific rules for a file path."""
        return self.resolve(file_path).rules
