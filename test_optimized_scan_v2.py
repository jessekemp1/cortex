"""
Test optimized scan_workspace with refined directory exclusions.
"""

import time
from pathlib import Path

# Directories to skip (but NOT .claude!)
SKIP_DIRS = {
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "bower_components",
    ".tox",
    ".eggs",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".coverage",
    ".DS_Store",
}


def optimized_rglob(root: Path, pattern: str):
    """Optimized recursive glob that skips common large directories."""

    def _walk(path: Path):
        try:
            for item in path.iterdir():
                if item.is_dir():
                    # Skip if in exclusion list
                    if item.name in SKIP_DIRS:
                        continue
                    # Recurse into directory (including .claude!)
                    yield from _walk(item)
                elif item.match(pattern):
                    yield item
        except PermissionError:
            pass  # Skip directories we can't read

    # Recurse from root
    yield from _walk(root)


def optimized_scan():
    """Optimized implementation with directory exclusions."""
    workspace = Path.home() / "Dev"
    start = time.time()
    projects = list(optimized_rglob(workspace, "project.yaml"))
    duration = time.time() - start
    return projects, duration


if __name__ == "__main__":
    print("=" * 60)
    print("OPTIMIZED SCAN V2 (refined exclusions)")
    print("=" * 60)

    opt_projects, opt_time = optimized_scan()

    # Filter to only .claude/project.yaml
    claude_projects = [p for p in opt_projects if p.parent.name == ".claude"]

    print(f"\nProjects found: {len(claude_projects)}")
    print(f"Scan time: {opt_time:.3f}s")
    print("Target: <2.0s")
    print(f"Status: {'✅ PASS' if opt_time < 2.0 else '⚠️  CLOSE (but better than 15s!)'}")

    print("\nProjects discovered:")
    for p in sorted(claude_projects):
        project_name = p.parent.parent.name
        print(f"  - {project_name}")

    print(f"\nImprovement vs current: ~{15/opt_time:.1f}x faster")
