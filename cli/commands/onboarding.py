"""Onboarding command: auto-detect projects, seed memory for immediate value."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


# Project detection signatures
LANG_SIGNATURES = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "typescript": ["tsconfig.json"],
    "javascript": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle"],
}

TEST_SIGNATURES = {
    "pytest": ["pytest.ini", "pyproject.toml", "conftest.py"],
    "jest": ["jest.config.js", "jest.config.ts"],
    "vitest": ["vitest.config.ts", "vitest.config.js"],
    "go-test": ["*_test.go"],
    "cargo-test": ["Cargo.toml"],
}


def _detect_projects(root: Path) -> List[Dict[str, Any]]:
    """Scan root for git repos and detect language/framework/tests."""
    projects = []

    # Look for git repos one level deep (avoid scanning node_modules, .venv, etc.)
    skip_dirs = {
        "node_modules",
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        ".claude",
        ".worktrees",
        "dist",
        "build",
        ".next",
        ".cache",
    }

    if not root.exists():
        return projects

    candidates = [root]  # Root itself may be a project
    try:
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and entry.name not in skip_dirs and not entry.name.startswith("."):
                candidates.append(entry)
    except PermissionError:
        pass

    for candidate in candidates:
        # Accept directories that are git repos OR have project signatures
        has_git = (candidate / ".git").exists()
        has_project_file = any(
            (candidate / sig).exists() for sigs in LANG_SIGNATURES.values() for sig in sigs
        )
        if not has_git and not has_project_file:
            continue

        project: Dict[str, Any] = {
            "name": candidate.name,
            "path": str(candidate),
            "languages": [],
            "test_framework": None,
            "has_ci": False,
        }

        # Detect languages
        for lang, signatures in LANG_SIGNATURES.items():
            for sig in signatures:
                if (candidate / sig).exists():
                    if lang not in project["languages"]:
                        project["languages"].append(lang)
                    break

        # Detect test framework
        for framework, signatures in TEST_SIGNATURES.items():
            for sig in signatures:
                if "*" in sig:
                    # Glob pattern — check if any match exists
                    if list(candidate.glob(sig)):
                        project["test_framework"] = framework
                        break
                elif (candidate / sig).exists():
                    project["test_framework"] = framework
                    break
            if project["test_framework"]:
                break

        # Detect CI
        ci_paths = [".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci"]
        project["has_ci"] = any((candidate / ci).exists() for ci in ci_paths)

        projects.append(project)

    return projects


def _get_recent_commits(project_path: str, limit: int = 20) -> List[Dict[str, str]]:
    """Get recent git commits for a project."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={limit}", "--format=%H|%s|%ai"],
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append(
                    {
                        "hash": parts[0][:8],
                        "message": parts[1],
                        "date": parts[2],
                    }
                )
        return commits
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _project_description(proj: Dict[str, Any]) -> str:
    """Build a human-readable project description."""
    langs = ", ".join(proj["languages"]) or "unknown"
    parts = [f"{proj['name']} — {langs} project"]
    if proj["test_framework"]:
        parts.append(f"with {proj['test_framework']}")
    if proj["has_ci"]:
        parts.append("(CI configured)")
    return " ".join(parts)


def _seed_working_memory(projects: List[Dict], commits_by_project: Dict[str, List]) -> int:
    """Seed working memory with project context and recent commits."""
    try:
        from cortex.intelligence.memory.tiered_memory import MemoryItem, WorkingMemory
    except ImportError:
        return _seed_file_memory(projects, commits_by_project)

    wm = WorkingMemory()
    count = 0
    now = datetime.now()

    # Seed project context
    for proj in projects:
        item = MemoryItem(
            id=f"onboard:project:{proj['name']}",
            content={
                "title": f"Project: {proj['name']}",
                "type": "project_context",
                "description": _project_description(proj),
                "project": proj["name"],
                "languages": proj["languages"],
                "test_framework": proj["test_framework"],
                "source": "onboarding",
            },
            created_at=now,
            last_accessed=now,
            access_count=1,
        )
        wm.add(item)
        count += 1

    # Seed recent work from commits
    for proj_name, commits in commits_by_project.items():
        if not commits:
            continue
        # Store a summary, not individual commits
        recent_msgs = [c["message"] for c in commits[:10]]
        item = MemoryItem(
            id=f"onboard:recent_work:{proj_name}",
            content={
                "title": f"Recent work in {proj_name}",
                "type": "episodic",
                "description": f"Last {len(recent_msgs)} commits: {'; '.join(recent_msgs[:5])}",
                "commits": commits[:10],
                "project": proj_name,
                "source": "onboarding",
            },
            created_at=now,
            last_accessed=now,
            access_count=1,
        )
        wm.add(item)
        count += 1

    return count


def _seed_file_memory(projects: List[Dict], commits_by_project: Dict[str, List]) -> int:
    """Fallback: seed via FileMemoryBackend if TieredMemory unavailable."""
    try:
        from cortex.intelligence.memory.backend_adapter import FileMemoryBackend
    except ImportError:
        return 0

    backend = FileMemoryBackend()
    now = datetime.now().isoformat()

    backend.store(
        "onboard_projects",
        {
            "projects": projects,
            "discovered_at": now,
        },
        namespace="onboarding",
    )

    for proj_name, commits in commits_by_project.items():
        if commits:
            backend.store(
                f"recent_work_{proj_name}",
                {
                    "project": proj_name,
                    "commits": commits[:10],
                    "seeded_at": now,
                },
                namespace="onboarding",
            )

    return len(projects) + sum(1 for c in commits_by_project.values() if c)


def _seed_custom_gotcha(gotcha_text: str) -> bool:
    """Store a user-provided gotcha as an anti-pattern."""
    try:
        from cortex.intelligence.memory.backend_adapter import FileMemoryBackend
    except ImportError:
        return False

    backend = FileMemoryBackend()
    backend.store_anti_pattern(
        {
            "id": f"user:gotcha:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": gotcha_text[:80],
            "description": gotcha_text,
            "category": "user_provided",
            "source": "onboarding",
            "created_at": datetime.now().isoformat(),
            "confidence": 0.9,
        }
    )
    return True


def cmd_onboard(args):
    """Interactive onboarding — auto-detect projects and seed memory."""
    from state_paths import get_cortex_dir

    cortex_dir = get_cortex_dir()
    root = Path(
        getattr(args, "root", "")
        or os.environ.get("CORTEX_ROOT_DIR", "")
        or str(Path.home() / "Dev")
    )

    if not root.exists():
        print(f"Root directory not found: {root}", file=sys.stderr)
        print("Set with: cortex onboard --root ~/your/projects", file=sys.stderr)
        sys.exit(1)

    print("Cortex Onboarding")
    print(f"{'=' * 40}\n")

    # Phase 1: Auto-detect
    print(f"Scanning {root} for projects...")
    projects = _detect_projects(root)

    if not projects:
        print(f"  No git repos found in {root}.")
        print("  Make sure your project root is correct.\n")
    else:
        print(f"  Found {len(projects)} project(s):\n")
        for p in projects:
            langs = ", ".join(p["languages"]) if p["languages"] else "?"
            test = p["test_framework"] or "none detected"
            ci = " + CI" if p["has_ci"] else ""
            print(f"    {p['name']:20s}  {langs:15s}  tests: {test}{ci}")
        print()

    # Phase 2: Git history
    print("Reading recent git history...")
    commits_by_project: Dict[str, List] = {}
    total_commits = 0
    for p in projects:
        commits = _get_recent_commits(p["path"])
        commits_by_project[p["name"]] = commits
        total_commits += len(commits)
    print(f"  {total_commits} recent commits across {len(projects)} project(s).\n")

    # Phase 3: Seed memory
    print("Seeding memory...")
    mem_count = _seed_working_memory(projects, commits_by_project)
    print(f"  {mem_count} memory entries created.\n")

    # Phase 4: Seed anti-patterns
    try:
        from cortex.intelligence.memory.seed_patterns import get_seed_patterns

        seeds = get_seed_patterns()
        print(f"  {len(seeds)} anti-pattern seeds loaded (built-in).\n")
    except ImportError:
        seeds = []
        print("  Seed patterns unavailable (import error).\n")

    # Phase 5: Optional user input (2 questions max)
    if sys.stdin.isatty() and not getattr(args, "non_interactive", False):
        gotcha = input("Any gotcha Cortex should know about? (Enter to skip): ").strip()
        if gotcha:
            if _seed_custom_gotcha(gotcha):
                print("  Stored as anti-pattern.\n")
            else:
                print("  Could not store (memory backend unavailable).\n")

        workflow_note = input("Anything about your workflow to remember? (Enter to skip): ").strip()
        if workflow_note:
            try:
                from cortex.intelligence.memory.backend_adapter import FileMemoryBackend

                backend = FileMemoryBackend()
                backend.store(
                    "workflow_note",
                    {
                        "note": workflow_note,
                        "source": "onboarding",
                        "created_at": datetime.now().isoformat(),
                    },
                    namespace="onboarding",
                )
                print("  Stored workflow note.\n")
            except ImportError:
                print("  Could not store (memory backend unavailable).\n")

    # Phase 6: Summary
    print(f"{'=' * 40}")
    print("Onboarding complete.")
    print(f"  Projects:   {len(projects)}")
    print(f"  Memories:   {mem_count}")
    print(f"  Seeds:      {len(seeds)} anti-patterns")
    print(f"  Data dir:   {cortex_dir}")
    print()
    print("Next steps:")
    print("  cortex status       — see your context")
    print("  cortex briefing     — daily intelligence briefing")
    print("  cortex doctor       — verify system health")
