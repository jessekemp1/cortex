"""
Cortex Data Agent CLI - Project health analysis interface

Provides beautiful terminal output for project health metrics
"""

import sys
from pathlib import Path
from datetime import datetime
import json

from .analyzers.project_analyzer import ProjectAnalyzer


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


def get_score_color(score: float) -> str:
    """Get color based on score"""
    if score >= 80:
        return Colors.GREEN
    elif score >= 60:
        return Colors.CYAN
    elif score >= 40:
        return Colors.YELLOW
    else:
        return Colors.RED


def get_trend_emoji(trend: str) -> str:
    """Get emoji for trend"""
    if trend == "increasing":
        return "📈"
    elif trend == "decreasing":
        return "📉"
    elif trend == "stable":
        return "➡️"
    else:
        return "❓"


def get_assessment_emoji(assessment: str) -> str:
    """Get emoji for assessment"""
    if assessment == "excellent":
        return "🌟"
    elif assessment == "good":
        return "✅"
    elif assessment == "fair":
        return "⚠️"
    else:
        return "🔴"


def display_portfolio_summary(days: int = 7):
    """Display beautiful portfolio summary"""
    analyzer = ProjectAnalyzer()
    summary = analyzer.get_portfolio_summary(days)

    print_header(f"📊 Portfolio Health Summary ({days} days)")

    stats = summary["portfolio_stats"]
    print(f"{Colors.BOLD}Portfolio Overview:{Colors.END}")
    print(f"  Total Projects: {stats['total_projects']}")
    print(f"  Total Commits: {stats['total_commits']}")
    print(f"  Average Health: {get_score_color(stats['average_health'])}{stats['average_health']}/100{Colors.END}")
    print(f"  Projects with Concerns: {Colors.RED if stats['projects_with_concerns'] > 0 else Colors.GREEN}{stats['projects_with_concerns']}{Colors.END}")
    print(f"  Star Projects: {Colors.GREEN}{stats['star_projects']}{Colors.END}")

    if summary["rankings"]:
        print(f"\n{Colors.BOLD}Project Rankings:{Colors.END}")
        print(f"{'Rank':<6} {'Project':<20} {'Score':<10} {'Commits':<10} {'Trend':<12} {'Status'}")
        print("-" * 70)

        for i, project in enumerate(summary["rankings"], 1):
            score_color = get_score_color(project["score"])
            trend_emoji = get_trend_emoji(project["trend"])
            assessment_emoji = get_assessment_emoji(project["assessment"])

            print(
                f"{i:<6} "
                f"{project['project']:<20} "
                f"{score_color}{project['score']:>3}/100{Colors.END}   "
                f"{project['commits']:>4}       "
                f"{trend_emoji} {project['trend']:<10} "
                f"{assessment_emoji} {project['assessment']}"
            )

    if summary["stars"]:
        print(f"\n{Colors.BOLD}{Colors.GREEN}🌟 Star Projects:{Colors.END}")
        for star in summary["stars"]:
            print(f"  • {star['project']} - {star['score']}/100 ({star['commits']} commits)")

    if summary["concerns"]:
        print(f"\n{Colors.BOLD}{Colors.RED}⚠️  Projects Needing Attention:{Colors.END}")
        for concern in summary["concerns"]:
            reason = []
            if concern["score"] < 40:
                reason.append("low health")
            if concern["trend"] == "decreasing":
                reason.append("decreasing activity")
            print(f"  • {concern['project']} - {concern['score']}/100 ({', '.join(reason)})")

    print()


def display_project_detail(project_name: str, days: int = 7):
    """Display detailed project analysis"""
    analyzer = ProjectAnalyzer()
    data = analyzer.analyze_project(project_name, days)

    if not data:
        print(f"{Colors.RED}Project '{project_name}' not found{Colors.END}")
        print(f"Available projects: {', '.join(analyzer.projects.keys())}")
        return

    if "error" in data:
        print(f"{Colors.RED}Error analyzing project: {data['error']}{Colors.END}")
        return

    print_header(f"📁 {data['project']} - Project Health Analysis")

    # Health Score
    health = data["health"]
    score_color = get_score_color(health["total_score"])
    assessment_emoji = get_assessment_emoji(health["assessment"])

    print(f"{Colors.BOLD}Health Score: {score_color}{health['total_score']}/100{Colors.END} {assessment_emoji} {health['assessment'].upper()}")
    print(f"\nScore Breakdown:")
    print(f"  Activity:      {health['breakdown']['activity']}/40")
    print(f"  Trend:         {health['breakdown']['trend']}/25")
    print(f"  Cleanliness:   {health['breakdown']['cleanliness']}/25")
    print(f"  Diversity:     {health['breakdown']['diversity']}/10")

    # Commits
    commits = data["commits"]
    trend_emoji = get_trend_emoji(commits["trend"])

    print(f"\n{Colors.BOLD}Commit Activity ({days} days):{Colors.END}")
    print(f"  Total Commits: {commits['count']}")
    print(f"  Trend: {trend_emoji} {commits['trend']}")
    print(f"  Contributors: {len(commits['authors'])}")

    if commits["authors"]:
        print(f"  Top Contributors:")
        for author, count in sorted(commits["authors"].items(), key=lambda x: x[1], reverse=True)[:3]:
            print(f"    - {author}: {count} commits")

    # Uncommitted changes
    uncommitted = data["uncommitted"]
    if uncommitted["has_changes"]:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️  Uncommitted Changes:{Colors.END}")
        print(f"  Total: {uncommitted['total']}")
        if uncommitted["modified"]:
            print(f"  Modified: {len(uncommitted['modified'])}")
        if uncommitted["added"]:
            print(f"  Added: {len(uncommitted['added'])}")
        if uncommitted["untracked"]:
            print(f"  Untracked: {len(uncommitted['untracked'])}")
    else:
        print(f"\n{Colors.GREEN}✅ Repository Clean{Colors.END}")

    # Branches
    branches = data["branches"]
    print(f"\n{Colors.BOLD}Repository Info:{Colors.END}")
    print(f"  Current Branch: {branches['current']}")
    print(f"  Total Branches: {branches['total_local']}")

    # Top changed files
    if commits["files_changed"]:
        print(f"\n{Colors.BOLD}Most Active Files:{Colors.END}")
        for filename, count in list(commits["files_changed"].items())[:5]:
            # Shorten path if too long
            display_name = filename if len(filename) < 50 else "..." + filename[-47:]
            print(f"  {count:>3}x {display_name}")

    print()


def display_comparison(proj1: str, proj2: str, days: int = 7):
    """Display project comparison"""
    analyzer = ProjectAnalyzer()
    comparison = analyzer.compare_projects(proj1, proj2, days)

    if "error" in comparison:
        print(f"{Colors.RED}{comparison['error']}{Colors.END}")
        if "available" in comparison:
            print(f"Available: {', '.join(comparison['available'])}")
        return

    print_header(f"⚖️  {proj1} vs {proj2}")

    comp = comparison["comparison"]
    winner = comparison["winner"]

    print(f"{Colors.BOLD}Metric Comparison:{Colors.END}\n")

    # Health Score
    proj1_health = comp[proj1]["health_score"]
    proj2_health = comp[proj2]["health_score"]
    health_winner = "🏆" if winner["health"] == proj1 else ""
    health_winner2 = "🏆" if winner["health"] == proj2 else ""

    print(f"{'Health Score:':<20} {get_score_color(proj1_health)}{proj1_health:>3}/100{Colors.END} {health_winner}  vs  {get_score_color(proj2_health)}{proj2_health:>3}/100{Colors.END} {health_winner2}")

    # Commits
    proj1_commits = comp[proj1]["commits"]
    proj2_commits = comp[proj2]["commits"]
    commits_winner = "🏆" if winner["activity"] == proj1 else ""
    commits_winner2 = "🏆" if winner["activity"] == proj2 else ""

    print(f"{'Commits:':<20} {proj1_commits:>7} {commits_winner}  vs  {proj2_commits:>7} {commits_winner2}")

    # Trend
    proj1_trend = comp[proj1]["trend"]
    proj2_trend = comp[proj2]["trend"]

    print(f"{'Trend:':<20} {get_trend_emoji(proj1_trend)} {proj1_trend:<10}  vs  {get_trend_emoji(proj2_trend)} {proj2_trend:<10}")

    # Uncommitted
    proj1_uncommitted = comp[proj1]["uncommitted"]
    proj2_uncommitted = comp[proj2]["uncommitted"]
    clean_winner = "✨" if winner["cleanliness"] == proj1 else ""
    clean_winner2 = "✨" if winner["cleanliness"] == proj2 else ""

    print(f"{'Uncommitted:':<20} {proj1_uncommitted:>7} {clean_winner}  vs  {proj2_uncommitted:>7} {clean_winner2}")

    print()


def display_project_trends(project_name: str):
    """Display comprehensive health trends for a project"""
    analyzer = ProjectAnalyzer()

    try:
        trends = analyzer.get_project_health_trends(project_name)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    print("="*60)
    print(f"📈 {Colors.BOLD}{project_name} - Health Trends Analysis{Colors.END}")
    print("="*60)
    print()

    # Overall trend
    history = trends["history"]
    overall_trend = history["overall_trend"]
    trend_emoji = get_trend_emoji(overall_trend)
    trend_color = Colors.GREEN if overall_trend == "improving" else (Colors.RED if overall_trend == "declining" else Colors.YELLOW)
    print(f"{Colors.BOLD}Overall Trend:{Colors.END} {trend_color}{trend_emoji} {overall_trend.upper()}{Colors.END}")
    print()

    # Multi-period health scores
    print(f"{Colors.BOLD}Health Score by Period:{Colors.END}")
    print(f"{'Period':<12} {'Score':<12} {'Commits':<12} {'Trend':<15} {'Uncommitted'}")
    print("-"*70)

    periods = history["periods"]
    for period_key in sorted(periods.keys(), key=lambda x: int(x[:-1])):
        period = periods[period_key]
        score = period["health_score"]
        score_color = get_score_color(score)
        trend_emoji = get_trend_emoji(period["trend"])

        print(f"{period_key:<12} {score_color}{score}/100{Colors.END:<12} "
              f"{period['commits']:<12} {trend_emoji} {period['trend']:<12} "
              f"{period['uncommitted']}")

    print()

    # Insights
    if trends["insights"]:
        print(f"{Colors.BOLD}Insights:{Colors.END}")
        for insight in trends["insights"]:
            icon = "⚠️ " if insight["type"] == "warning" else "✅ " if insight["type"] == "success" else "ℹ️  "
            color = Colors.YELLOW if insight["type"] == "warning" else Colors.GREEN if insight["type"] == "success" else Colors.BLUE
            print(f"  {icon}{color}{insight['message']}{Colors.END}")
        print()

    # Recommendations
    if trends["recommendations"]:
        print(f"{Colors.BOLD}Recommendations:{Colors.END}")
        for rec in trends["recommendations"]:
            priority_color = Colors.RED if rec["priority"] == "high" else Colors.YELLOW
            print(f"  {priority_color}[{rec['priority'].upper()}]{Colors.END} {rec['action']}")
            print(f"    → {rec['details']}")
        print()

    print("="*60)


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print(f"{Colors.BOLD}Cortex Data Agent - Project Health Analysis{Colors.END}\n")
        print("Usage:")
        print("  python -m cortex.agents.data_agent.cli <command> [args]")
        print("\nCommands:")
        print("  summary [days]           - Portfolio summary (default: 7 days)")
        print("  project <name> [days]    - Detailed project analysis")
        print("  compare <proj1> <proj2>  - Compare two projects")
        print("  trends <name>            - Health trends for project (multi-period)")
        print("\nExamples:")
        print("  python -m cortex.agents.data_agent.cli summary")
        print("  python -m cortex.agents.data_agent.cli summary 30")
        print("  python -m cortex.agents.data_agent.cli project Dev 7")
        sys.exit(1)

    command = sys.argv[1]

    if command == "summary":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        display_portfolio_summary(days)

    elif command == "project":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        display_project_detail(project_name, days)

    elif command == "compare":
        if len(sys.argv) < 4:
            print(f"{Colors.RED}Error: two project names required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        proj1 = sys.argv[2]
        proj2 = sys.argv[3]
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 7
        display_comparison(proj1, proj2, days)

    elif command == "trends":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        display_project_trends(project_name)

    else:
        print(f"{Colors.RED}Unknown command: {command}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
