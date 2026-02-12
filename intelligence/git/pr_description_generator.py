#!/usr/bin/env python3
"""
Cortex V1: PR Description Generator

Analyzes git log main..HEAD to categorize commits, detect affected
projects from file paths, and generate structured PR descriptions.

Called by: modified /pr command (Phase 3)
"""

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class PRDescription:
    title: str
    summary_bullets: list[str]
    projects_affected: list[str]
    commit_categories: dict[str, list[str]]
    test_plan: list[str]
    deployment_notes: list[str]
    stats: dict[str, int]


PROJECT_MAP = {
    "Vortex/VortexV2": "VortexV2",
    "Vortex/VortexV3": "VortexV3",
    "Vortex/Winfield": "Winfield",
    "cortex": "Cortex",
    "alpha_arena": "Alpha Arena",
}

COMMIT_CATEGORIES = {
    "Features": ["feat"],
    "Bug Fixes": ["fix"],
    "Refactoring": ["refactor"],
    "Tests": ["test"],
    "Documentation": ["docs"],
    "Chores": ["chore", "data", "ci", "build"],
}


def get_commits(base: str = "main") -> list[dict]:
    try:
        result = subprocess.run(
            ["git", "log", f"{base}..HEAD", "--format=%H|%s", "--no-merges"],
            capture_output=True, text=True, timeout=10,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            if "|" in line:
                sha, message = line.split("|", 1)
                commits.append({"sha": sha.strip(), "message": message.strip()})
        return commits
    except Exception:
        return []


def get_changed_files(base: str = "main") -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except Exception:
        return []


def get_diff_stats(base: str = "main") -> dict[str, int]:
    try:
        result = subprocess.run(
            ["git", "diff", "--shortstat", f"{base}...HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        text = result.stdout.strip()
        stats = {"files_changed": 0, "insertions": 0, "deletions": 0}
        if not text:
            return stats
        for part in text.split(","):
            part = part.strip()
            num = int(re.search(r"\d+", part).group())
            if "file" in part:
                stats["files_changed"] = num
            elif "insertion" in part:
                stats["insertions"] = num
            elif "deletion" in part:
                stats["deletions"] = num
        return stats
    except Exception:
        return {"files_changed": 0, "insertions": 0, "deletions": 0}


def detect_projects(files: list[str]) -> list[str]:
    projects = set()
    for f in files:
        for prefix, name in PROJECT_MAP.items():
            if f.startswith(prefix):
                projects.add(name)
                break
        else:
            if f.startswith(".claude/") or f.startswith("cortex/"):
                projects.add("Cortex")
            elif not f.startswith("."):
                projects.add("Root")
    return sorted(projects)


def categorize_commits(commits: list[dict]) -> dict[str, list[str]]:
    categories = defaultdict(list)
    for commit in commits:
        msg = commit["message"]
        matched = False
        for category, prefixes in COMMIT_CATEGORIES.items():
            for prefix in prefixes:
                if msg.startswith(f"{prefix}(") or msg.startswith(f"{prefix}:"):
                    categories[category].append(msg)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            categories["Other"].append(msg)
    return dict(categories)


def generate_title(commits: list[dict], projects: list[str]) -> str:
    if len(commits) == 1:
        return commits[0]["message"][:70]
    categories = categorize_commits(commits)
    dominant = max(categories, key=lambda k: len(categories[k]))
    if len(projects) == 1:
        scope = projects[0].lower()
    elif len(projects) <= 3:
        scope = ", ".join(p.lower() for p in projects)
    else:
        scope = f"{len(projects)} projects"
    prefix_map = {"Features": "feat", "Bug Fixes": "fix", "Refactoring": "refactor",
                  "Tests": "test", "Documentation": "docs", "Chores": "chore"}
    prefix = prefix_map.get(dominant, "chore")
    return f"{prefix}: {dominant} across {scope} ({len(commits)} commits)"[:70]


def generate_summary(categories: dict[str, list[str]], projects: list[str]) -> list[str]:
    bullets = []
    for category, messages in sorted(categories.items(), key=lambda x: -len(x[1])):
        if len(messages) == 1:
            bullets.append(f"**{category}**: {messages[0]}")
        else:
            bullets.append(f"**{category}**: {len(messages)} changes")
    if projects:
        bullets.append(f"**Projects affected**: {', '.join(projects)}")
    return bullets


def generate_test_plan(projects: list[str], files: list[str]) -> list[str]:
    plan = []
    test_commands = {
        "VortexV2": "pytest Vortex/VortexV2/tests/ -v",
        "VortexV3": "cd Vortex/VortexV3 && npm test",
        "Winfield": "pytest Vortex/Winfield/tests/ -v",
        "Cortex": "pytest cortex/tests/ -v",
        "Alpha Arena": "pytest alpha_arena/tests/ -v",
    }
    for project in projects:
        if project in test_commands:
            plan.append(f"Run `{test_commands[project]}`")
    has_test_files = any("test" in f.lower() for f in files)
    if has_test_files:
        plan.append("New/updated test files included")
    else:
        plan.append("Manual testing completed for changed functionality")
    return plan


def generate_deployment_notes(projects: list[str]) -> list[str]:
    notes = []
    if "VortexV2" in projects:
        notes.append("VortexV2: Validate on staging (:9000) before production (:8000)")
    if "Cortex" in projects:
        notes.append("Cortex: Dashboard on :8502 — verify after deploy")
    if "VortexV3" in projects:
        notes.append("VortexV3: Build with `npm run build`, verify bundle size")
    return notes


def generate(base: str = "main") -> PRDescription:
    commits = get_commits(base)
    files = get_changed_files(base)
    stats = get_diff_stats(base)
    projects = detect_projects(files)
    categories = categorize_commits(commits)
    return PRDescription(
        title=generate_title(commits, projects),
        summary_bullets=generate_summary(categories, projects),
        projects_affected=projects,
        commit_categories=categories,
        test_plan=generate_test_plan(projects, files),
        deployment_notes=generate_deployment_notes(projects),
        stats=stats,
    )


def format_pr_body(desc: PRDescription) -> str:
    sections = ["## Summary"]
    for bullet in desc.summary_bullets:
        sections.append(f"- {bullet}")
    if desc.commit_categories:
        sections.append("\n## Changes")
        for category, messages in desc.commit_categories.items():
            sections.append(f"\n### {category}")
            for msg in messages[:5]:
                sections.append(f"- {msg}")
            if len(messages) > 5:
                sections.append(f"- ...and {len(messages) - 5} more")
    sections.append("\n## Test Plan")
    for item in desc.test_plan:
        sections.append(f"- [ ] {item}")
    if desc.deployment_notes:
        sections.append("\n## Deployment Notes")
        for note in desc.deployment_notes:
            sections.append(f"- {note}")
    s = desc.stats
    sections.append(f"\n**Stats**: {s['files_changed']} files changed, +{s['insertions']} -{s['deletions']}")
    sections.append("\n\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)")
    return "\n".join(sections)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cortex V1 PR Description Generator")
    parser.add_argument("--base", default="main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    desc = generate(args.base)
    if args.json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(desc), indent=2))
    else:
        print(f"Title: {desc.title}")
        print(f"\n{format_pr_body(desc)}")


if __name__ == "__main__":
    main()
