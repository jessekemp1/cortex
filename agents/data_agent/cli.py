"""
Cortex Data Agent CLI - Project health analysis interface

Provides beautiful terminal output for project health metrics
"""

import sys
from typing import Optional

from .analyzers.project_analyzer import ProjectAnalyzer


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


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
    print(
        f"  Average Health: {get_score_color(stats['average_health'])}{stats['average_health']}/100{Colors.END}"
    )
    print(
        f"  Projects with Concerns: {Colors.RED if stats['projects_with_concerns'] > 0 else Colors.GREEN}{stats['projects_with_concerns']}{Colors.END}"
    )
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

    print(
        f"{Colors.BOLD}Health Score: {score_color}{health['total_score']}/100{Colors.END} {assessment_emoji} {health['assessment'].upper()}"
    )
    print("\nScore Breakdown:")
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
        print("  Top Contributors:")
        for author, count in sorted(commits["authors"].items(), key=lambda x: x[1], reverse=True)[
            :3
        ]:
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

    print(
        f"{'Health Score:':<20} {get_score_color(proj1_health)}{proj1_health:>3}/100{Colors.END} {health_winner}  vs  {get_score_color(proj2_health)}{proj2_health:>3}/100{Colors.END} {health_winner2}"
    )

    # Commits
    proj1_commits = comp[proj1]["commits"]
    proj2_commits = comp[proj2]["commits"]
    commits_winner = "🏆" if winner["activity"] == proj1 else ""
    commits_winner2 = "🏆" if winner["activity"] == proj2 else ""

    print(
        f"{'Commits:':<20} {proj1_commits:>7} {commits_winner}  vs  {proj2_commits:>7} {commits_winner2}"
    )

    # Trend
    proj1_trend = comp[proj1]["trend"]
    proj2_trend = comp[proj2]["trend"]

    print(
        f"{'Trend:':<20} {get_trend_emoji(proj1_trend)} {proj1_trend:<10}  vs  {get_trend_emoji(proj2_trend)} {proj2_trend:<10}"
    )

    # Uncommitted
    proj1_uncommitted = comp[proj1]["uncommitted"]
    proj2_uncommitted = comp[proj2]["uncommitted"]
    clean_winner = "✨" if winner["cleanliness"] == proj1 else ""
    clean_winner2 = "✨" if winner["cleanliness"] == proj2 else ""

    print(
        f"{'Uncommitted:':<20} {proj1_uncommitted:>7} {clean_winner}  vs  {proj2_uncommitted:>7} {clean_winner2}"
    )

    print()


def display_project_trends(project_name: str):
    """Display comprehensive health trends for a project"""
    analyzer = ProjectAnalyzer()

    try:
        trends = analyzer.get_project_health_trends(project_name)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    print("=" * 60)
    print(f"📈 {Colors.BOLD}{project_name} - Health Trends Analysis{Colors.END}")
    print("=" * 60)
    print()

    # Overall trend
    history = trends["history"]
    overall_trend = history["overall_trend"]
    trend_emoji = get_trend_emoji(overall_trend)
    trend_color = (
        Colors.GREEN
        if overall_trend == "improving"
        else (Colors.RED if overall_trend == "declining" else Colors.YELLOW)
    )
    print(
        f"{Colors.BOLD}Overall Trend:{Colors.END} {trend_color}{trend_emoji} {overall_trend.upper()}{Colors.END}"
    )
    print()

    # Multi-period health scores
    print(f"{Colors.BOLD}Health Score by Period:{Colors.END}")
    print(f"{'Period':<12} {'Score':<12} {'Commits':<12} {'Trend':<15} {'Uncommitted'}")
    print("-" * 70)

    periods = history["periods"]
    for period_key in sorted(periods.keys(), key=lambda x: int(x[:-1])):
        period = periods[period_key]
        score = period["health_score"]
        score_color = get_score_color(score)
        trend_emoji = get_trend_emoji(period["trend"])

        print(
            f"{period_key:<12} {score_color}{score}/100{Colors.END:<12} "
            f"{period['commits']:<12} {trend_emoji} {period['trend']:<12} "
            f"{period['uncommitted']}"
        )

    print()

    # Insights
    if trends["insights"]:
        print(f"{Colors.BOLD}Insights:{Colors.END}")
        for insight in trends["insights"]:
            icon = (
                "⚠️ "
                if insight["type"] == "warning"
                else "✅ " if insight["type"] == "success" else "ℹ️  "
            )
            color = (
                Colors.YELLOW
                if insight["type"] == "warning"
                else Colors.GREEN if insight["type"] == "success" else Colors.BLUE
            )
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

    print("=" * 60)


def display_dependency_analysis(project_name: str):
    """Display dependency analysis for a project"""
    analyzer = ProjectAnalyzer()

    try:
        analysis = analyzer.get_dependency_analysis(project_name)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    print("=" * 60)
    print(f"📦 {Colors.BOLD}{project_name} - Dependency Analysis{Colors.END}")
    print("=" * 60)
    print()

    print(f"{Colors.BOLD}Summary:{Colors.END}")
    print(f"  Files Analyzed: {analysis['files_analyzed']}")
    print(f"  Files with Errors: {analysis['files_with_errors']}")
    print()

    # Import types
    import_types = analysis.get("imports_by_type", {})
    if import_types:
        print(f"{Colors.BOLD}Import Types:{Colors.END}")
        for imp_type, count in sorted(import_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {imp_type:15} {count:>4}")
        print()

    # External dependencies
    external = analysis.get("external_deps", [])
    if external:
        print(f"{Colors.BOLD}External Dependencies ({len(external)}):{Colors.END}")
        for dep in sorted(external)[:10]:
            print(f"  • {dep}")
        if len(external) > 10:
            print(f"  ... and {len(external) - 10} more")
        print()

    print("=" * 60)


def display_dependency_health(project_name: str):
    """Display dependency health score"""
    analyzer = ProjectAnalyzer()

    try:
        health = analyzer.get_dependency_health(project_name)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    print("=" * 60)
    print(f"💊 {Colors.BOLD}{project_name} - Dependency Health{Colors.END}")
    print("=" * 60)
    print()

    # Health score
    score = health["total_score"]
    score_color = get_score_color(score)
    assessment_emoji = get_assessment_emoji(health["assessment"])

    print(
        f"{Colors.BOLD}Health Score: {score_color}{score}/100{Colors.END} {assessment_emoji} {health['assessment'].upper()}"
    )
    print()

    # Breakdown
    print(f"{Colors.BOLD}Score Breakdown:{Colors.END}")
    breakdown = health["breakdown"]
    for component, points in breakdown.items():
        component_name = component.replace("_", " ").title()
        print(f"  {component_name:20} {points}/25")
    print()

    # Concerns
    if health.get("concerns"):
        print(f"{Colors.BOLD}{Colors.YELLOW}⚠️  Concerns:{Colors.END}")
        for concern in health["concerns"]:
            print(f"  • {concern}")
        print()

    # Recommendations
    if health.get("recommendations"):
        print(f"{Colors.BOLD}Recommendations:{Colors.END}")
        for rec in health["recommendations"]:
            priority_color = Colors.RED if rec["priority"] == "high" else Colors.YELLOW
            print(f"  {priority_color}[{rec['priority'].upper()}]{Colors.END} {rec['action']}")
            print(f"    → {rec['details']}")
        print()

    print("=" * 60)


def display_circular_dependencies(project_name: str):
    """Display circular dependency analysis"""
    analyzer = ProjectAnalyzer()

    try:
        circular = analyzer.find_circular_dependencies(project_name)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    print("=" * 60)
    print(f"🔄 {Colors.BOLD}{project_name} - Circular Dependencies{Colors.END}")
    print("=" * 60)
    print()

    if circular["has_cycles"]:
        severity = circular["severity"]
        severity_color = Colors.RED if severity == "major" else Colors.YELLOW

        print(
            f"{Colors.BOLD}Status:{Colors.END} {severity_color}Found {circular['cycle_count']} circular dependencies ({severity}){Colors.END}"
        )
        print()

        print(f"{Colors.BOLD}Cycles:{Colors.END}")
        for i, cycle in enumerate(circular["cycles"], 1):
            print(f"\n  Cycle {i}:")
            for module in cycle:
                print(f"    → {module}")
    else:
        print(f"{Colors.GREEN}✅ No circular dependencies found{Colors.END}")

    print()
    print("=" * 60)


def display_package_comparison(project_name: str):
    """Display comparison of declared vs actual dependencies"""
    analyzer = ProjectAnalyzer()

    try:
        project_path = analyzer.projects.get(project_name)
        if not project_path:
            print(f"{Colors.RED}Error: Project '{project_name}' not found{Colors.END}")
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            return

        from .analyzers.dependency_mapper import DependencyMapper

        mapper = DependencyMapper(project_path)
        comparison = mapper.compare_declared_vs_actual()

        print("=" * 60)
        print(f"📦 {Colors.BOLD}{project_name} - Declared vs Actual Dependencies{Colors.END}")
        print("=" * 60)
        print()

        # Summary
        print(f"{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Declared: {comparison['declared_count']}")
        print(f"  Actually Used: {comparison['actual_count']}")
        print(f"  Matches: {Colors.GREEN}{comparison['match_count']}{Colors.END}")
        print(f"  Unused Declared: {Colors.YELLOW}{comparison['unused_count']}{Colors.END}")
        print(f"  Undeclared: {Colors.RED}{comparison['undeclared_count']}{Colors.END}")
        print()

        # Package files found
        if comparison.get("package_files"):
            print(f"{Colors.BOLD}Package Files Found:{Colors.END}")
            for file in comparison["package_files"]:
                print(f"  • {file}")
            print()

        # Unused declared dependencies
        if comparison["unused_declared"]:
            print(
                f"{Colors.BOLD}{Colors.YELLOW}⚠️  Unused Declared Dependencies ({len(comparison['unused_declared'])}):{Colors.END}"
            )
            for pkg in sorted(comparison["unused_declared"])[:10]:
                print(f"  • {pkg}")
            if len(comparison["unused_declared"]) > 10:
                print(f"  ... and {len(comparison['unused_declared']) - 10} more")
            print()

        # Undeclared dependencies
        if comparison["undeclared"]:
            print(
                f"{Colors.BOLD}{Colors.RED}⚠️  Undeclared Dependencies ({len(comparison['undeclared'])}):{Colors.END}"
            )
            for pkg in sorted(comparison["undeclared"])[:10]:
                print(f"  • {pkg}")
            if len(comparison["undeclared"]) > 10:
                print(f"  ... and {len(comparison['undeclared']) - 10} more")
            print()

        print("=" * 60)

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return


def display_portfolio_dependencies(project_filter: Optional[str] = None):
    """Display portfolio-wide dependency analysis"""
    analyzer = ProjectAnalyzer()

    try:
        portfolio = analyzer.analyze_portfolio_dependencies(project_filter=project_filter)

        print("=" * 60)
        if project_filter:
            print(f"🔗 {Colors.BOLD}Portfolio Dependencies - {project_filter} Focus{Colors.END}")
        else:
            print(f"🔗 {Colors.BOLD}Portfolio Dependencies - All Projects{Colors.END}")
        print("=" * 60)
        print()

        # Projects analyzed
        print(
            f"{Colors.BOLD}Projects Analyzed ({len(portfolio['projects_analyzed'])}):{Colors.END}"
        )
        for proj in portfolio["projects_analyzed"]:
            deps = portfolio["project_dependencies"].get(proj, {})
            ext_count = deps.get("external_count", 0)
            print(f"  • {proj} ({ext_count} external deps)")
        print()

        # Cross-project dependencies
        if portfolio["cross_project_graph"]:
            print(f"{Colors.BOLD}Cross-Project Dependencies:{Colors.END}")
            for proj, deps in portfolio["cross_project_graph"].items():
                print(f"  {proj} → {', '.join(deps)}")
            print()

        # Coupling analysis
        if portfolio["coupling_analysis"]:
            print(f"{Colors.BOLD}Coupling Analysis:{Colors.END}")
            print(f"{'Project':<20} {'Outgoing':<12} {'Incoming':<12} {'Bidirectional':<15}")
            print("-" * 60)
            for proj, coupling in sorted(portfolio["coupling_analysis"].items()):
                outgoing = coupling["outgoing"]
                incoming = coupling["incoming"]
                bidirectional = coupling["bidirectional"]

                # Color based on coupling level
                if outgoing + incoming > 3:
                    color = Colors.RED
                elif outgoing + incoming > 1:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN

                print(
                    f"{proj:<20} {color}{outgoing:<12}{Colors.END} {incoming:<12} {bidirectional:<15}"
                )
            print()

        # Shared dependencies
        if portfolio["shared_dependencies"]:
            print(
                f"{Colors.BOLD}Shared Dependencies ({len(portfolio['shared_dependencies'])}):{Colors.END}"
            )
            for dep, projects in list(portfolio["shared_dependencies"].items())[:10]:
                print(f"  • {dep} (used by: {', '.join(projects)})")
            if len(portfolio["shared_dependencies"]) > 10:
                print(f"  ... and {len(portfolio['shared_dependencies']) - 10} more")
            print()

        # Recommendations
        if portfolio["recommendations"]:
            print(f"{Colors.BOLD}Recommendations:{Colors.END}")
            for rec in portfolio["recommendations"]:
                priority_color = Colors.RED if rec["priority"] == "high" else Colors.YELLOW
                print(f"  {priority_color}[{rec['priority'].upper()}]{Colors.END} {rec['action']}")
                print(f"    → {rec['details']}")
            print()

        print("=" * 60)

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return


def display_dependency_graph(project_name: str, format: str = "ascii"):
    """Display dependency graph in specified format"""
    analyzer = ProjectAnalyzer()

    try:
        project_path = analyzer.projects.get(project_name)
        if not project_path:
            print(f"{Colors.RED}Error: Project '{project_name}' not found{Colors.END}")
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            return

        from .analyzers.dependency_mapper import DependencyMapper

        mapper = DependencyMapper(project_path)

        if format == "dot":
            graph = mapper.export_to_dot()
            print(graph)
        elif format == "mermaid":
            graph = mapper.export_to_mermaid()
            print(graph)
        elif format == "ascii":
            tree = mapper.generate_ascii_tree()
            print("=" * 60)
            print(f"🌳 {Colors.BOLD}{project_name} - Dependency Tree{Colors.END}")
            print("=" * 60)
            print()
            print(tree)
            print()
            print("=" * 60)
        else:
            print(
                f"{Colors.RED}Error: Unknown format '{format}'. Use: ascii, dot, or mermaid{Colors.END}"
            )

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")
        return


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
        print("  deps <name>              - Dependency analysis for project")
        print("  deps-health <name>       - Dependency health score")
        print("  deps-circular <name>     - Find circular dependencies")
        print("  deps-graph <name> [format] - Dependency graph (ascii|dot|mermaid)")
        print("  deps-package <name>        - Show package file dependencies")
        print("  deps-compare <name>        - Compare declared vs actual dependencies")
        print("  deps-portfolio [project]   - Portfolio-wide dependency analysis")
        print("\nExamples:")
        print("  python -m cortex.agents.data_agent.cli summary")
        print("  python -m cortex.agents.data_agent.cli summary 30")
        print("  python -m cortex.agents.data_agent.cli project Dev 7")
        print("  python -m cortex.agents.data_agent.cli deps cortex")
        print("  python -m cortex.agents.data_agent.cli deps-health cortex")
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

    elif command == "deps":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        display_dependency_analysis(project_name)

    elif command == "deps-health":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        display_dependency_health(project_name)

    elif command == "deps-circular":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        display_circular_dependencies(project_name)

    elif command == "deps-graph":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        format_type = sys.argv[3] if len(sys.argv) > 3 else "ascii"
        display_dependency_graph(project_name, format_type)

    elif command == "deps-package":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        from .analyzers.package_parser import PackageParser
        from .analyzers.project_analyzer import ProjectAnalyzer

        analyzer = ProjectAnalyzer()
        project_path = analyzer.projects.get(project_name)
        if project_path:
            parser = PackageParser(project_path)
            result = parser.get_all_declared_dependencies()
            print("=" * 60)
            print(f"📦 {Colors.BOLD}{project_name} - Package Files{Colors.END}")
            print("=" * 60)
            print()
            if result["by_file"]:
                for file_type, file_data in result["by_file"].items():
                    print(f"{Colors.BOLD}{file_type}:{Colors.END}")
                    if file_data.get("packages"):
                        print(f"  Packages ({len(file_data['packages'])}):")
                        for pkg in file_data["packages"][:10]:
                            name = pkg.get("name", "?")
                            version = pkg.get("version_spec", "")
                            print(f"    • {name} {version}")
                        if len(file_data["packages"]) > 10:
                            print(f"    ... and {len(file_data['packages']) - 10} more")
                    if file_data.get("dev_packages"):
                        print(f"  Dev Packages ({len(file_data['dev_packages'])}):")
                        for pkg in file_data["dev_packages"][:5]:
                            name = pkg.get("name", "?")
                            print(f"    • {name}")
                    print()
            else:
                print("  No package files found")
            print("=" * 60)
        else:
            print(f"{Colors.RED}Error: Project '{project_name}' not found{Colors.END}")

    elif command == "deps-compare":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}Error: project name required{Colors.END}")
            analyzer = ProjectAnalyzer()
            print(f"Available: {', '.join(analyzer.projects.keys())}")
            sys.exit(1)
        project_name = sys.argv[2]
        display_package_comparison(project_name)

    elif command == "deps-portfolio":
        project_filter = sys.argv[2] if len(sys.argv) > 2 else None
        display_portfolio_dependencies(project_filter)

    else:
        print(f"{Colors.RED}Unknown command: {command}{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
