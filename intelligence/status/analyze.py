#!/usr/bin/env python3
"""
Enhanced status analysis CLI - Present Cortex intelligence in readable format.

Includes:
- Semantic grouping of uncommitted changes
- Git hygiene checks (prevents mega-PRs)
- Actionable commit recommendations
"""

import sys
from pathlib import Path

# Add cortex to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from intelligence.status.git_hygiene import GitHygieneAnalyzer
from intelligence.status.git_status_analyzer import GitStatusAnalyzer


def format_hygiene_for_cli(report) -> str:
    """Format hygiene report as a compact CLI section."""
    status_icons = {"ok": "✅", "warning": "⚠️", "alert": "🔴", "critical": "🚨"}

    lines = [
        "",
        "🧹 GIT HYGIENE",
        "=" * 60,
        f"Status: {status_icons[report.overall_status]} {report.overall_status.upper()}",
        f"  • Uncommitted: {report.uncommitted_lines:,} lines / {report.uncommitted_files} files",
        f"  • Branch age: {report.branch_age_days:.1f} days",
        f"  • Commits ahead: {report.commits_ahead}",
    ]

    if report.alerts:
        lines.append("")
        for alert in report.alerts:
            icon = status_icons[alert.level]
            lines.append(f"{icon} {alert.message}")
            lines.append(f"   → {alert.recommendation}")

    return "\n".join(lines)


def format_for_cli(suggestions):
    """Format suggestions for terminal display."""
    output = []

    # Header
    total_files = sum(len(s.group.files) for s in suggestions)
    output.append("\n🧠 Cortex Status Intelligence")
    output.append(
        f"📊 Analyzed {total_files} uncommitted files → {len(suggestions)} suggested commits\n"
    )

    # Categorize suggestions
    ready_now = [s for s in suggestions if s.priority <= 2 and not s.blockers]
    needs_work = [s for s in suggestions if s.blockers]
    review_needed = [s for s in suggestions if s.priority >= 5 and not s.blockers]

    # Section 1: Ready to Commit
    if ready_now:
        output.append("✅ READY TO COMMIT NOW")
        output.append("=" * 60)
        for i, suggestion in enumerate(ready_now, 1):
            group = suggestion.group
            output.append(f"\n{i}. {group.suggested_message}")
            output.append(f"   📁 {len(group.files)} files | 💡 {suggestion.reasoning}")

            # Show sample files
            sample_files = group.files[:3]
            for f in sample_files:
                output.append(f"      • {f}")
            if len(group.files) > 3:
                output.append(f"      ... and {len(group.files) - 3} more")
        output.append("")

    # Section 2: Needs Work
    if needs_work:
        output.append("⚠️  NEEDS WORK BEFORE COMMIT")
        output.append("=" * 60)
        for i, suggestion in enumerate(needs_work, 1):
            group = suggestion.group
            output.append(f"\n{i}. {group.suggested_message}")
            output.append(f"   📁 {len(group.files)} files")
            for blocker in suggestion.blockers:
                output.append(f"   🚫 {blocker}")
        output.append("")

    # Section 3: Review Needed
    if review_needed:
        output.append("🔍 REVIEW RECOMMENDED")
        output.append("=" * 60)
        for i, suggestion in enumerate(review_needed, 1):
            group = suggestion.group
            output.append(f"\n{i}. {group.suggested_message}")
            output.append(f"   📁 {len(group.files)} files | 💡 {suggestion.reasoning}")
        output.append("")

    # Summary
    output.append("📝 RECOMMENDED ACTIONS")
    output.append("=" * 60)
    if ready_now:
        output.append(f"1. Commit {len(ready_now)} ready groups (low risk, high confidence)")
    if needs_work:
        output.append(f"2. Address {len(needs_work)} blockers")
    if review_needed:
        output.append(f"3. Manually review {len(review_needed)} uncertain groups")

    return "\n".join(output)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        repo_path = Path.cwd()
    else:
        repo_path = Path(sys.argv[1])

    # Find git root
    while repo_path != repo_path.parent:
        if (repo_path / ".git").exists():
            break
        repo_path = repo_path.parent
    else:
        print("❌ Not in a git repository")
        sys.exit(1)

    # Run hygiene check first (automated)
    try:
        hygiene_analyzer = GitHygieneAnalyzer(repo_path)
        hygiene_report = hygiene_analyzer.analyze()
        print(format_hygiene_for_cli(hygiene_report))
    except Exception as e:
        print(f"⚠️ Hygiene check failed: {e}")

    # Then run semantic grouping
    analyzer = GitStatusAnalyzer(repo_path)
    groups = analyzer.analyze_uncommitted_changes()
    suggestions = analyzer.suggest_commit_sequence(groups)

    print(format_for_cli(suggestions))


if __name__ == "__main__":
    main()
