#!/usr/bin/env python3
"""
Cortex Portfolio Analyzer

Comprehensive portfolio analysis using all intelligence sources:
- Portfolio Memory (projects, patterns, lessons)
- Session Manager (current context, recent work)
- Spec Knowledge Base (documentation, specifications)
- Metrics Tracker (performance data)

Generates actionable recommendations based on cross-project intelligence.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from metrics_tracker import MetricsTracker
from portfolio_memory import PortfolioMemory
from session_manager import SessionManager
from spec_knowledge_base import SpecKnowledgeBase


class PortfolioAnalyzer:
    """Comprehensive portfolio analysis and recommendations"""

    def __init__(self):
        self.pm = PortfolioMemory()
        self.sm = SessionManager()
        self.kb = SpecKnowledgeBase()
        self.metrics = MetricsTracker()

    def analyze(self) -> Dict[str, Any]:
        """Run comprehensive portfolio analysis"""
        print("=" * 70)
        print("CORTEX PORTFOLIO ANALYZER")
        print("Unified Intelligence Analysis Across All Projects")
        print("=" * 70)

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "current_context": {},
            "project_analysis": {},
            "pattern_insights": {},
            "lesson_insights": {},
            "spec_coverage": {},
            "metrics_analysis": {},
            "recommendations": [],
            "action_plan": [],
        }

        # 1. Current Context
        print("\n📍 ANALYZING CURRENT CONTEXT...")
        analysis["current_context"] = self._analyze_current_context()

        # 2. Portfolio Overview
        print("\n📊 ANALYZING PORTFOLIO...")
        analysis["summary"] = self._analyze_portfolio_summary()

        # 3. Project Deep Dive
        print("\n🔍 ANALYZING INDIVIDUAL PROJECTS...")
        analysis["project_analysis"] = self._analyze_projects()

        # 4. Pattern Analysis
        print("\n🔄 ANALYZING PATTERNS...")
        analysis["pattern_insights"] = self._analyze_patterns()

        # 5. Lesson Analysis
        print("\n💡 ANALYZING LESSONS LEARNED...")
        analysis["lesson_insights"] = self._analyze_lessons()

        # 6. Spec Coverage
        print("\n📚 ANALYZING SPEC COVERAGE...")
        analysis["spec_coverage"] = self._analyze_spec_coverage()

        # 7. Metrics Analysis
        print("\n📈 ANALYZING PERFORMANCE METRICS...")
        analysis["metrics_analysis"] = self._analyze_metrics()

        # 8. Generate Recommendations
        print("\n🎯 GENERATING RECOMMENDATIONS...")
        analysis["recommendations"] = self._generate_recommendations(analysis)

        # 9. Create Action Plan
        print("\n📋 CREATING ACTION PLAN...")
        analysis["action_plan"] = self._create_action_plan(analysis)

        return analysis

    def _analyze_current_context(self) -> Dict[str, Any]:
        """Analyze current session context"""
        context_json = self.sm.get_context(format="structured")
        context = json.loads(context_json)

        return {
            "current_project": context.get("project", {}).get("name", "Unknown"),
            "git_branch": context.get("git", {}).get("branch", "Unknown"),
            "recent_commits": len(context.get("git", {}).get("recent_commits", [])),
            "current_focus": context.get("focus", "Unknown"),
            "active_goals": context.get("goals", []),
        }

    def _analyze_portfolio_summary(self) -> Dict[str, Any]:
        """Analyze overall portfolio"""
        stats = self.pm.get_stats()

        return {
            "total_projects": stats["total_projects"],
            "tier1_projects": stats["by_priority"]["tier1"],
            "tier2_projects": stats["by_priority"]["tier2"],
            "tier3_projects": stats["by_priority"]["tier3"],
            "active_projects": stats["active_projects"],
            "total_technologies": len(stats["top_technologies"]),
            "top_5_technologies": dict(list(stats["top_technologies"].items())[:5]),
            "cross_project_patterns": len(stats["top_patterns"]),
        }

    def _analyze_projects(self) -> Dict[str, Any]:
        """Analyze each project individually"""
        # Load project index
        index_file = Path.home() / ".claude" / "portfolio" / "project_index.json"
        with open(index_file, "r") as f:
            data = json.load(f)

        projects = data.get("projects", {})

        project_analysis = {}
        for name, proj in projects.items():
            # Count specs for this project
            spec_count = sum(1 for s in self.kb.specs.values() if s["project"] == name)

            project_analysis[name] = {
                "priority": proj.get("priority", "unknown"),
                "domain": proj.get("domain", "unknown"),
                "status": proj.get("status", "unknown"),
                "tech_stack_size": len(proj.get("tech_stack", [])),
                "primary_technologies": proj.get("tech_stack", [])[:3],
                "spec_count": spec_count,
                "has_documentation": spec_count > 0,
                "key_features": len(proj.get("key_features", [])),
            }

        return project_analysis

    def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze documented patterns"""
        patterns_file = Path.home() / ".claude" / "portfolio" / "patterns.json"
        with open(patterns_file, "r") as f:
            patterns = json.load(f)

        if not patterns:
            return {
                "total_patterns": 0,
                "by_category": {},
                "by_project": {},
                "avg_success_rate": 0,
                "reusable_patterns": [],
            }

        # Analyze by category
        by_category = defaultdict(int)
        by_project = defaultdict(list)
        success_rates = []

        for pattern in patterns:
            category = pattern.get("category", "uncategorized")
            by_category[category] += 1

            for project in pattern.get("projects", []):
                by_project[project].append(pattern.get("name"))

            # Extract success rate if available
            success_rate = pattern.get("success_rate", "")
            if isinstance(success_rate, str) and "%" in success_rate:
                try:
                    rate = float(success_rate.replace("%", ""))
                    success_rates.append(rate)
                except:
                    pass

        avg_success = sum(success_rates) / len(success_rates) if success_rates else 0

        # Find reusable patterns (used in multiple projects)
        reusable = []
        for pattern in patterns:
            if len(pattern.get("projects", [])) > 1:
                reusable.append(
                    {
                        "name": pattern.get("name"),
                        "projects": pattern.get("projects", []),
                        "category": pattern.get("category"),
                    }
                )

        return {
            "total_patterns": len(patterns),
            "by_category": dict(by_category),
            "by_project": {k: len(v) for k, v in by_project.items()},
            "avg_success_rate": round(avg_success, 1),
            "reusable_patterns": reusable,
        }

    def _analyze_lessons(self) -> Dict[str, Any]:
        """Analyze lessons learned"""
        lessons_file = Path.home() / ".claude" / "portfolio" / "lessons.json"
        with open(lessons_file, "r") as f:
            lessons = json.load(f)

        if not lessons:
            return {
                "total_lessons": 0,
                "by_category": {},
                "cross_project_lessons": [],
                "high_impact_lessons": [],
            }

        # Analyze by category
        by_category = defaultdict(int)
        cross_project = []

        for lesson in lessons:
            category = lesson.get("category", "uncategorized")
            by_category[category] += 1

            # Cross-project lessons
            projects = lesson.get("projects", [])
            if len(projects) > 1:
                cross_project.append(
                    {
                        "title": lesson.get("title"),
                        "category": category,
                        "projects": projects,
                    }
                )

        return {
            "total_lessons": len(lessons),
            "by_category": dict(by_category),
            "cross_project_lessons": cross_project,
            "categories": list(by_category.keys()),
        }

    def _analyze_spec_coverage(self) -> Dict[str, Any]:
        """Analyze spec documentation coverage"""
        total_specs = self.kb.count()
        projects_with_specs = self.kb.list_projects()

        # Get project list
        index_file = Path.home() / ".claude" / "portfolio" / "project_index.json"
        with open(index_file, "r") as f:
            data = json.load(f)
        total_projects = len(data.get("projects", {}))

        # Count specs per project
        specs_by_project = {}
        for project in projects_with_specs:
            count = sum(1 for s in self.kb.specs.values() if s["project"] == project)
            specs_by_project[project] = count

        # Find projects without specs
        all_project_names = set(data.get("projects", {}).keys())
        documented_projects = set(projects_with_specs)
        undocumented_projects = all_project_names - documented_projects

        coverage_pct = (
            (len(documented_projects) / total_projects * 100) if total_projects > 0 else 0
        )

        return {
            "total_specs": total_specs,
            "projects_with_specs": len(projects_with_specs),
            "total_projects": total_projects,
            "coverage_percentage": round(coverage_pct, 1),
            "specs_by_project": specs_by_project,
            "undocumented_projects": list(undocumented_projects),
        }

    def _analyze_metrics(self) -> Dict[str, Any]:
        """Analyze performance metrics"""
        dashboard = self.metrics.get_dashboard(days=30)

        return {
            "velocity": {
                "tasks_completed": dashboard["velocity"]["total_tasks"],
                "hours_saved": dashboard["velocity"]["total_savings_hours"],
                "avg_improvement": dashboard["velocity"]["avg_improvement_pct"],
            },
            "mistakes": {
                "total": dashboard["mistakes"]["total_mistakes"],
                "prevented": dashboard["mistakes"]["prevented"],
                "prevention_rate": dashboard["mistakes"]["prevention_rate"],
                "hours_saved": dashboard["mistakes"]["time_saved_hours"],
            },
            "roi": {
                "investment_hours": dashboard["roi"]["total_investment_hours"],
                "benefit_hours": dashboard["roi"]["total_benefit_hours"],
                "net_savings_hours": dashboard["roi"]["net_savings_hours"],
                "roi_ratio": dashboard["roi"]["roi_ratio"],
                "break_even": dashboard["roi"]["break_even"],
            },
        }

    def _generate_recommendations(self, analysis: Dict) -> List[Dict]:
        """Generate actionable recommendations"""
        recommendations = []

        # 1. Documentation gaps
        if analysis["spec_coverage"]["undocumented_projects"]:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Documentation",
                    "title": "Document Undocumented Projects",
                    "issue": f"{len(analysis['spec_coverage']['undocumented_projects'])} projects lack specifications",
                    "impact": "Cannot leverage spec search for these projects",
                    "action": f"Create markdown documentation for: {', '.join(analysis['spec_coverage']['undocumented_projects'])}",
                    "estimated_time": f"{len(analysis['spec_coverage']['undocumented_projects']) * 30} minutes",
                }
            )

        # 2. Pattern reuse opportunities
        pattern_count = analysis["pattern_insights"]["total_patterns"]
        if pattern_count < 10:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Knowledge Capture",
                    "title": "Document More Patterns",
                    "issue": f"Only {pattern_count} patterns documented",
                    "impact": "Missing opportunities for cross-project reuse",
                    "action": "Review recent work and document 5-10 successful patterns",
                    "estimated_time": "60-90 minutes",
                }
            )

        # 3. Lesson extraction
        lesson_count = analysis["lesson_insights"]["total_lessons"]
        if lesson_count < 10:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Knowledge Capture",
                    "title": "Document More Lessons",
                    "issue": f"Only {lesson_count} lessons documented",
                    "impact": "Higher risk of repeating mistakes",
                    "action": "Review past mistakes and document prevention strategies",
                    "estimated_time": "45-60 minutes",
                }
            )

        # 4. Metrics tracking
        if analysis["metrics_analysis"]["velocity"]["tasks_completed"] < 5:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Metrics",
                    "title": "Increase Metrics Tracking",
                    "issue": "Insufficient velocity data to measure ROI",
                    "impact": "Cannot demonstrate system value",
                    "action": "Record time estimates for next 5-10 tasks",
                    "estimated_time": "5 minutes per task",
                }
            )

        # 5. Tech stack consolidation
        tech_count = analysis["summary"]["total_technologies"]
        if tech_count > 15:
            recommendations.append(
                {
                    "priority": "LOW",
                    "category": "Architecture",
                    "title": "Consider Tech Stack Consolidation",
                    "issue": f"{tech_count} different technologies across portfolio",
                    "impact": "Higher context switching costs",
                    "action": "Evaluate if some technologies can be consolidated",
                    "estimated_time": "2-4 hours analysis",
                }
            )

        # 6. Cross-project pattern sharing
        reusable = len(analysis["pattern_insights"]["reusable_patterns"])
        if reusable > 0:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Optimization",
                    "title": "Leverage Cross-Project Patterns",
                    "issue": f"{reusable} patterns applicable to multiple projects",
                    "impact": "Faster development through reuse",
                    "action": f"Apply reusable patterns: {', '.join(p['name'] for p in analysis['pattern_insights']['reusable_patterns'][:3])}",
                    "estimated_time": "15-30 minutes per application",
                }
            )

        # 7. Current focus optimization
        current_focus = analysis["current_context"]["current_focus"]
        if current_focus == "Feature development":
            # Check if there are relevant patterns
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Current Work",
                    "title": "Search Patterns Before Implementing",
                    "issue": "Currently in feature development mode",
                    "impact": "May reinvent existing solutions",
                    "action": "Search spec KB and patterns before writing new code",
                    "estimated_time": "5 minutes per feature",
                }
            )

        # 8. Spec search utilization
        if analysis["spec_coverage"]["total_specs"] > 20:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Productivity",
                    "title": "Leverage Spec Knowledge Base",
                    "issue": f"{analysis['spec_coverage']['total_specs']} specs available",
                    "impact": "Faster implementation through reference",
                    "action": "Use 'python3 bridge.py intelligence similar-work' before coding",
                    "estimated_time": "2-5 minutes per search",
                }
            )

        # 9. ROI validation
        if not analysis["metrics_analysis"]["roi"]["break_even"]:
            recommendations.append(
                {
                    "priority": "CRITICAL",
                    "category": "Validation",
                    "title": "Demonstrate ROI",
                    "issue": "System hasn't broken even yet",
                    "impact": "Cannot justify continued investment",
                    "action": "Track next 5 tasks with detailed time measurements",
                    "estimated_time": "Ongoing",
                }
            )

        # 10. Integration opportunities
        tier1_projects = analysis["summary"]["tier1_projects"]
        if tier1_projects >= 2:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Integration",
                    "title": "Consider Project Integrations",
                    "issue": f"{tier1_projects} tier-1 projects could be integrated",
                    "impact": "Automated pattern extraction and calibration",
                    "action": "Build VortexV2 and Alpha Arena integrations (Agents 6-7)",
                    "estimated_time": "30-40 minutes",
                }
            )

        return recommendations

    def _create_action_plan(self, analysis: Dict) -> List[Dict]:
        """Create prioritized action plan"""
        recommendations = analysis["recommendations"]

        # Group by priority
        critical = [r for r in recommendations if r["priority"] == "CRITICAL"]
        high = [r for r in recommendations if r["priority"] == "HIGH"]
        medium = [r for r in recommendations if r["priority"] == "MEDIUM"]
        low = [r for r in recommendations if r["priority"] == "LOW"]

        action_plan = []

        # Today (Critical + Top 2 High)
        today_actions = critical + high[:2]
        if today_actions:
            action_plan.append(
                {
                    "timeframe": "TODAY",
                    "actions": [
                        {
                            "title": a["title"],
                            "action": a["action"],
                            "time": a["estimated_time"],
                        }
                        for a in today_actions
                    ],
                }
            )

        # This Week (Remaining High + Top 3 Medium)
        week_actions = high[2:] + medium[:3]
        if week_actions:
            action_plan.append(
                {
                    "timeframe": "THIS WEEK",
                    "actions": [
                        {
                            "title": a["title"],
                            "action": a["action"],
                            "time": a["estimated_time"],
                        }
                        for a in week_actions
                    ],
                }
            )

        # This Month (Remaining Medium + Low)
        month_actions = medium[3:] + low
        if month_actions:
            action_plan.append(
                {
                    "timeframe": "THIS MONTH",
                    "actions": [
                        {
                            "title": a["title"],
                            "action": a["action"],
                            "time": a["estimated_time"],
                        }
                        for a in month_actions
                    ],
                }
            )

        return action_plan

    def print_report(self, analysis: Dict):
        """Print formatted analysis report"""
        print("\n" + "=" * 70)
        print("CORTEX PORTFOLIO ANALYSIS REPORT")
        print(f"Generated: {analysis['timestamp']}")
        print("=" * 70)

        # Current Context
        print("\n📍 CURRENT CONTEXT")
        print("-" * 70)
        ctx = analysis["current_context"]
        print(f"Project: {ctx['current_project']}")
        print(f"Branch: {ctx['git_branch']}")
        print(f"Recent Commits: {ctx['recent_commits']}")
        print(f"Focus: {ctx['current_focus']}")
        if ctx["active_goals"]:
            print(f"Goals: {', '.join(ctx['active_goals'])}")

        # Portfolio Summary
        print("\n📊 PORTFOLIO SUMMARY")
        print("-" * 70)
        summary = analysis["summary"]
        print(f"Total Projects: {summary['total_projects']}")
        print(f"  Tier 1 (Critical): {summary['tier1_projects']}")
        print(f"  Tier 2 (Important): {summary['tier2_projects']}")
        print(f"  Tier 3 (Nice-to-have): {summary['tier3_projects']}")
        print(f"Active Projects: {summary['active_projects']}")
        print(f"Technologies: {summary['total_technologies']}")
        print(f"Top 5 Tech: {', '.join(summary['top_5_technologies'].keys())}")

        # Project Breakdown
        print("\n🔍 PROJECT ANALYSIS")
        print("-" * 70)
        for name, proj in analysis["project_analysis"].items():
            print(f"\n{name} ({proj['priority']}, {proj['status']})")
            print(f"  Domain: {proj['domain']}")
            print(f"  Tech Stack: {', '.join(proj['primary_technologies'])}")
            print(
                f"  Specs: {proj['spec_count']} {'✅' if proj['has_documentation'] else '⚠️ MISSING'}"
            )
            print(f"  Features: {proj['key_features']}")

        # Patterns
        print("\n🔄 PATTERN INSIGHTS")
        print("-" * 70)
        patterns = analysis["pattern_insights"]
        print(f"Total Patterns: {patterns['total_patterns']}")
        print(f"Avg Success Rate: {patterns['avg_success_rate']}%")
        if patterns["by_category"]:
            print(f"By Category: {patterns['by_category']}")
        if patterns["reusable_patterns"]:
            print(f"\nReusable Patterns ({len(patterns['reusable_patterns'])}):")
            for p in patterns["reusable_patterns"]:
                print(f"  • {p['name']} → {', '.join(p['projects'])}")

        # Lessons
        print("\n💡 LESSON INSIGHTS")
        print("-" * 70)
        lessons = analysis["lesson_insights"]
        print(f"Total Lessons: {lessons['total_lessons']}")
        if lessons["by_category"]:
            print(f"By Category: {lessons['by_category']}")
        if lessons["cross_project_lessons"]:
            print(f"\nCross-Project Lessons ({len(lessons['cross_project_lessons'])}):")
            for l in lessons["cross_project_lessons"]:
                print(f"  • {l['title']} → {', '.join(l['projects'])}")

        # Spec Coverage
        print("\n📚 SPEC COVERAGE")
        print("-" * 70)
        specs = analysis["spec_coverage"]
        print(f"Total Specs: {specs['total_specs']}")
        print(
            f"Coverage: {specs['coverage_percentage']}% ({specs['projects_with_specs']}/{specs['total_projects']} projects)"
        )
        if specs["specs_by_project"]:
            print("\nBy Project:")
            for proj, count in specs["specs_by_project"].items():
                print(f"  • {proj}: {count} specs")
        if specs["undocumented_projects"]:
            print(f"\n⚠️  Undocumented: {', '.join(specs['undocumented_projects'])}")

        # Metrics
        print("\n📈 PERFORMANCE METRICS")
        print("-" * 70)
        metrics = analysis["metrics_analysis"]
        print("Velocity:")
        print(f"  Tasks: {metrics['velocity']['tasks_completed']}")
        print(f"  Hours Saved: {metrics['velocity']['hours_saved']}")
        print(f"  Avg Improvement: {metrics['velocity']['avg_improvement']}%")
        print("\nMistake Prevention:")
        print(f"  Total: {metrics['mistakes']['total']}")
        print(
            f"  Prevented: {metrics['mistakes']['prevented']} ({metrics['mistakes']['prevention_rate']}%)"
        )
        print(f"  Hours Saved: {metrics['mistakes']['hours_saved']}")
        print("\nROI:")
        print(f"  Investment: {metrics['roi']['investment_hours']} hours")
        print(f"  Benefits: {metrics['roi']['benefit_hours']} hours")
        print(f"  Net: {metrics['roi']['net_savings_hours']} hours")
        print(f"  Ratio: {metrics['roi']['roi_ratio']}x")
        print(f"  Break-even: {'✅ YES' if metrics['roi']['break_even'] else '❌ NOT YET'}")

        # Recommendations
        print("\n🎯 RECOMMENDATIONS")
        print("-" * 70)
        for i, rec in enumerate(analysis["recommendations"], 1):
            priority_icon = {
                "CRITICAL": "🔴",
                "HIGH": "🟠",
                "MEDIUM": "🟡",
                "LOW": "🟢",
            }.get(rec["priority"], "⚪")

            print(f"\n{i}. {priority_icon} {rec['title']} [{rec['priority']}]")
            print(f"   Category: {rec['category']}")
            print(f"   Issue: {rec['issue']}")
            print(f"   Impact: {rec['impact']}")
            print(f"   Action: {rec['action']}")
            print(f"   Time: {rec['estimated_time']}")

        # Action Plan
        print("\n📋 ACTION PLAN")
        print("-" * 70)
        for phase in analysis["action_plan"]:
            print(f"\n{phase['timeframe']}:")
            for action in phase["actions"]:
                print(f"  ☐ {action['title']}")
                print(f"     {action['action']}")
                print(f"     Est. time: {action['time']}")

        print("\n" + "=" * 70)
        print("END OF REPORT")
        print("=" * 70)


def main():
    """Run portfolio analysis"""
    analyzer = PortfolioAnalyzer()
    analysis = analyzer.analyze()

    # Print formatted report
    analyzer.print_report(analysis)

    # Save to file
    output_file = Path.home() / "Dev" / "cortex" / "portfolio_analysis.json"
    with open(output_file, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"\n💾 Full analysis saved to: {output_file}")
    print("\nUse this analysis to guide your next development priorities!")


if __name__ == "__main__":
    main()
