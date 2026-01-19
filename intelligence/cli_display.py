#!/usr/bin/env python3
"""
CLI Display Formatters for Deep Intelligence

Provides rich, actionable terminal output for Cortex deep mode analysis.
Follows depth-first design: actionable information first, progressive disclosure.
"""

from typing import Dict, Any, List


# ANSI Color Codes
class Colors:
    """Terminal color codes for rich output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Status colors
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

    # Background colors
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_GREEN = "\033[42m"


def format_health_score(score: int, assessment: str) -> str:
    """Format health score with color-coded visual"""
    if score >= 80:
        color = Colors.GREEN
        emoji = "✅"
    elif score >= 60:
        color = Colors.YELLOW
        emoji = "⚠️"
    else:
        color = Colors.RED
        emoji = "❌"

    # Progress bar (20 chars)
    filled = int(score / 5)  # 100/5 = 20 chars
    bar = "█" * filled + "░" * (20 - filled)

    return f"{emoji} {color}{Colors.BOLD}{score}/100{Colors.RESET} {color}{bar}{Colors.RESET} ({assessment})"


def format_git_summary(git_data: Dict[str, Any]) -> str:
    """Format git analysis summary"""
    lines = []

    commit_count = git_data.get('commit_count', 0)
    days_analyzed = git_data.get('days_analyzed', 0)
    uncommitted_count = git_data.get('uncommitted_count', 0)
    branch = git_data.get('branch', 'unknown')

    lines.append(f"{Colors.BOLD}Git Analysis:{Colors.RESET}")
    lines.append(f"  Branch: {Colors.CYAN}{branch}{Colors.RESET}")
    lines.append(f"  Commits analyzed: {Colors.BOLD}{commit_count}{Colors.RESET} ({days_analyzed} days)")

    if uncommitted_count > 0:
        lines.append(f"  Uncommitted files: {Colors.YELLOW}{uncommitted_count}{Colors.RESET}")
    else:
        lines.append(f"  Uncommitted files: {Colors.GREEN}0{Colors.RESET} (clean)")

    return "\n".join(lines)


def format_quality_metrics(quality_data: Dict[str, Any]) -> str:
    """Format code quality metrics"""
    lines = []

    tech_debt = quality_data.get('tech_debt_markers', 0)
    test_coverage = quality_data.get('test_coverage_pct', None)
    complexity = quality_data.get('avg_complexity', None)

    lines.append(f"{Colors.BOLD}Code Quality:{Colors.RESET}")

    # Tech debt markers
    if tech_debt > 100:
        color = Colors.RED
    elif tech_debt > 50:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN
    lines.append(f"  Tech debt markers: {color}{tech_debt}{Colors.RESET}")

    # Test coverage (if available)
    if test_coverage is not None:
        if test_coverage >= 80:
            color = Colors.GREEN
        elif test_coverage >= 60:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        lines.append(f"  Test coverage: {color}{test_coverage:.1f}%{Colors.RESET}")

    # Complexity (if available)
    if complexity is not None:
        if complexity <= 5:
            color = Colors.GREEN
        elif complexity <= 10:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        lines.append(f"  Avg complexity: {color}{complexity:.1f}{Colors.RESET}")

    return "\n".join(lines)


def format_warnings(warnings: List) -> str:
    """Format warnings with severity indicators"""
    if not warnings:
        return f"{Colors.GREEN}✓ No warnings detected{Colors.RESET}"

    lines = [f"{Colors.BOLD}⚠️  Warnings ({len(warnings)}):{Colors.RESET}"]

    for i, warning in enumerate(warnings, 1):
        # Handle both string and dict warnings
        if isinstance(warning, str):
            # Simple string warning
            lines.append(f"  🟡 {Colors.YELLOW}[WARNING]{Colors.RESET} {warning}")
        else:
            # Dict warning with metadata
            severity = warning.get('severity', 'medium')
            message = warning.get('message', 'Unknown warning')
            category = warning.get('category', 'general')

            # Severity color
            if severity == 'critical':
                color = Colors.RED
                emoji = "🔴"
            elif severity == 'high':
                color = Colors.YELLOW
                emoji = "🟡"
            else:
                color = Colors.BLUE
                emoji = "🔵"

            lines.append(f"  {emoji} {color}[{severity.upper()}]{Colors.RESET} {message}")
            lines.append(f"     {Colors.DIM}Category: {category}{Colors.RESET}")

    return "\n".join(lines)


def format_recommendations(recommendations: List[Dict[str, Any]]) -> str:
    """Format actionable recommendations"""
    if not recommendations:
        return f"{Colors.DIM}No recommendations at this time{Colors.RESET}"

    lines = [f"{Colors.BOLD}💡 Recommendations ({len(recommendations)}):{Colors.RESET}"]

    for i, rec in enumerate(recommendations, 1):
        # Handle both 'action'/'title' keys
        action = rec.get('action') or rec.get('title', 'Unknown action')
        rationale = rec.get('rationale', '')
        priority = rec.get('priority', 'medium')

        # Priority indicator
        if priority == 'high':
            color = Colors.RED
            emoji = "🔥"
        elif priority == 'medium':
            color = Colors.YELLOW
            emoji = "⭐"
        else:
            color = Colors.BLUE
            emoji = "💭"

        lines.append(f"  {emoji} {color}[{priority.upper()}]{Colors.RESET} {action}")
        if rationale:
            lines.append(f"     {Colors.DIM}{rationale}{Colors.RESET}")

    return "\n".join(lines)


def format_deep_intelligence_compact(result: Any) -> str:
    """
    Format deep intelligence in compact mode (default)

    Shows: Health, Key Metrics, Top Warnings, Top Recommendations
    """
    lines = []

    # Header
    project = getattr(result, 'project', 'unknown')
    mode = getattr(result, 'mode', 'deep')
    latency_ms = getattr(result, 'latency_ms', 0)

    lines.append("")
    lines.append(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{Colors.CYAN}Cortex Deep Intelligence: {project}{Colors.RESET}")
    lines.append(f"{Colors.DIM}Mode: {mode} | Analysis time: {latency_ms/1000:.2f}s{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    lines.append("")

    # Health Score (prominent)
    health = getattr(result, 'health', None)
    if health:
        score = getattr(health, 'score', 0)
        assessment = getattr(health, 'assessment', 'unknown')
        lines.append(format_health_score(score, assessment))
        lines.append("")

    # Git Summary
    git = getattr(result, 'git', None)
    if git:
        git_dict = git.__dict__ if hasattr(git, '__dict__') else git
        lines.append(format_git_summary(git_dict))
        lines.append("")

    # Quality Metrics
    quality = getattr(result, 'quality', None)
    if quality:
        quality_dict = quality.__dict__ if hasattr(quality, '__dict__') else quality
        lines.append(format_quality_metrics(quality_dict))
        lines.append("")

    # Warnings (top 3 in compact mode)
    warnings = getattr(result, 'warnings', [])
    if warnings:
        lines.append(format_warnings(warnings[:3]))
        if len(warnings) > 3:
            lines.append(f"{Colors.DIM}  ... and {len(warnings) - 3} more (use --verbose to see all){Colors.RESET}")
        lines.append("")

    # Recommendations (top 3 in compact mode)
    recommendations = getattr(result, 'recommendations', [])
    if recommendations:
        lines.append(format_recommendations(recommendations[:3]))
        if len(recommendations) > 3:
            lines.append(f"{Colors.DIM}  ... and {len(recommendations) - 3} more (use --verbose to see all){Colors.RESET}")
        lines.append("")

    # Footer
    lines.append(f"{Colors.DIM}{'─'*60}{Colors.RESET}")
    lines.append(f"{Colors.DIM}Tip: Use 'cortex deep --verbose' for full details{Colors.RESET}")
    lines.append("")

    return "\n".join(lines)


def format_deep_intelligence_verbose(result: Any) -> str:
    """
    Format deep intelligence in verbose mode

    Shows: Everything in compact mode + all warnings + all recommendations + specs
    """
    lines = []

    # Start with compact version
    compact = format_deep_intelligence_compact(result)
    lines.append(compact)

    # Add verbose-only sections
    lines.append(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}Extended Analysis{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    lines.append("")

    # All warnings
    warnings = getattr(result, 'warnings', [])
    if len(warnings) > 3:
        lines.append(f"{Colors.BOLD}All Warnings ({len(warnings)}):{Colors.RESET}")
        lines.append(format_warnings(warnings))
        lines.append("")

    # All recommendations
    recommendations = getattr(result, 'recommendations', [])
    if len(recommendations) > 3:
        lines.append(f"{Colors.BOLD}All Recommendations ({len(recommendations)}):{Colors.RESET}")
        lines.append(format_recommendations(recommendations))
        lines.append("")

    # Spec matches (if available)
    specs = getattr(result, 'specs', None)
    if specs:
        spec_count = len(specs) if isinstance(specs, list) else 0
        if spec_count > 0:
            lines.append(f"{Colors.BOLD}Specification Matches ({spec_count}):{Colors.RESET}")
            for spec in specs[:5]:  # Top 5
                title = spec.get('title', 'Unknown')
                relevance = spec.get('relevance_score', 0)
                lines.append(f"  • {title} (relevance: {relevance:.2f})")
            if spec_count > 5:
                lines.append(f"{Colors.DIM}  ... and {spec_count - 5} more{Colors.RESET}")
            lines.append("")

    return "\n".join(lines)


def format_quick_intelligence(result: Dict[str, Any]) -> str:
    """Format quick mode intelligence (minimal output)"""
    lines = []

    project = result.get('project', 'unknown')

    lines.append("")
    lines.append(f"{Colors.BOLD}Cortex Quick Intelligence: {project}{Colors.RESET}")
    lines.append(f"{Colors.DIM}{'─'*60}{Colors.RESET}")
    lines.append("")

    # Quick mode shows minimal context
    lines.append(f"{Colors.GREEN}✓{Colors.RESET} Quick analysis complete")
    lines.append(f"{Colors.DIM}(Use 'cortex deep' for comprehensive analysis){Colors.RESET}")
    lines.append("")

    return "\n".join(lines)


def format_mode_info(mode: str, config: Dict[str, Any]) -> str:
    """Format mode selection information"""
    lines = []

    lines.append("")
    lines.append(f"{Colors.BOLD}Selected Mode: {mode.upper()}{Colors.RESET}")
    lines.append(f"{Colors.DIM}{'─'*60}{Colors.RESET}")

    if mode == "deep":
        lines.append(f"{Colors.CYAN}Deep Mode{Colors.RESET} - Comprehensive portfolio intelligence")
        lines.append(f"  • Git history: {config.get('git_days', 90)} days")
        lines.append(f"  • Spec search: {'✓' if config.get('spec_search_enabled') else '✗'}")
        lines.append(f"  • Pattern matching: {'semantic' if config.get('pattern_semantic') else 'keyword'}")
        lines.append(f"  • Expected latency: ~{config.get('expected_latency_ms', 5000)/1000:.1f}s")
    elif mode == "fast":
        lines.append(f"{Colors.GREEN}Fast Mode{Colors.RESET} - Minimal analysis for quick context")
        lines.append(f"  • Git history: {config.get('git_days', 7)} days")
        lines.append("  • Spec search: ✗")
        lines.append(f"  • Expected latency: ~{config.get('expected_latency_ms', 500)/1000:.1f}s")
    elif mode == "auto":
        lines.append(f"{Colors.YELLOW}Auto Mode{Colors.RESET} - Adaptive based on context")
        lines.append("  • Intelligently selects between fast and deep")
        lines.append("  • Learns from your preferences")

    lines.append("")
    return "\n".join(lines)


# Main display functions for CLI
def display_deep_intelligence(result: Any, verbose: bool = False, json_output: bool = False) -> None:
    """Main display function for deep intelligence"""
    if json_output:
        import json
        # Result should already be serialized dict if json_output=True was passed to analyze_deep
        print(json.dumps(result, indent=2))
    elif verbose:
        print(format_deep_intelligence_verbose(result))
    else:
        print(format_deep_intelligence_compact(result))


def display_quick_intelligence(result: Dict[str, Any]) -> None:
    """Main display function for quick intelligence"""
    print(format_quick_intelligence(result))


def display_error(error_msg: str, details: str = None) -> None:
    """Display error message with optional details"""
    print(f"\n{Colors.RED}{Colors.BOLD}❌ Error:{Colors.RESET} {error_msg}\n")
    if details:
        print(f"{Colors.DIM}{details}{Colors.RESET}\n")
