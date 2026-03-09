#!/usr/bin/env python3
"""
Frontier Scout Engine

Scans AI engineering frontier weekly and produces actionable intelligence
for the Cortex platform roadmap. Identifies high-impact integration
opportunities by scoring findings on Relevance × (6 - Effort).

Usage:
    scout = FrontierScout()
    report = scout.generate_report()
    scout.save_report(report)

Batch usage:
    python -m cortex.engines.frontier_scout
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FRONTIER_DIR = Path.home() / "Dev" / "cortex" / ".frontier"
GOALS_PATH = Path.home() / "Dev" / "GOALS.md"

# Categories to scan — each maps to search queries and Cortex subsystems
SCAN_CATEGORIES = {
    "frontier_models": {
        "label": "Frontier Model Releases & Capabilities",
        "queries": [
            "new AI model release this week",
            "frontier model benchmarks",
        ],
        "subsystems": ["routing", "conductor"],
        "key_files": [
            "cortex/conductor/router.py",
            "cortex/conductor/registry.py",
        ],
    },
    "agent_frameworks": {
        "label": "Agent Frameworks & Orchestration",
        "queries": [
            "AI agent framework update",
            "multi-agent orchestration",
            "agentic AI patterns",
        ],
        "subsystems": ["agents", "supervisor", "orchestration"],
        "key_files": [
            "cortex/supervisor/agents.py",
            "cortex/agent_factory.py",
            "cortex/batch/intelligent_orchestrator.py",
        ],
    },
    "protocols": {
        "label": "Protocol & Interoperability",
        "queries": [
            "MCP protocol update",
            "A2A protocol news",
            "AI agent interoperability",
        ],
        "subsystems": ["plugins", "integration"],
        "key_files": [
            "cortex/plugins/registry.py",
            "cortex/integration/feedback_loop.py",
        ],
    },
    "developer_tooling": {
        "label": "Developer Tooling & Infrastructure",
        "queries": [
            "AI coding tools update",
            "LLM evaluation framework",
            "agent deployment patterns",
        ],
        "subsystems": ["batch", "evaluation"],
        "key_files": [
            "cortex/intelligence/evaluation/quality_judge.py",
            "cortex/batch/flywheel_daemon.py",
        ],
    },
    "research_papers": {
        "label": "Research Papers",
        "queries": [
            "arxiv agent architecture",
            "LLM self-improvement research",
            "LLM memory systems research",
        ],
        "subsystems": ["memory", "learning"],
        "key_files": [
            "cortex/intelligence/memory/tiered_memory.py",
            "cortex/learning.py",
            "cortex/engines/interaction_learner.py",
        ],
    },
}


@dataclass
class Finding:
    """A single frontier finding."""

    title: str
    source_url: str
    category: str
    description: str
    relevance: int  # 1-5
    effort: int  # 1-5
    subsystem: str  # which cortex subsystem
    integration_path: str  # specific files/approach
    effort_hours: Optional[float] = None
    action: str = "MONITOR"  # INTEGRATE | EVALUATE | MONITOR

    @property
    def priority_score(self) -> int:
        return self.relevance * (6 - self.effort)

    @property
    def priority_tier(self) -> str:
        score = self.priority_score
        if score >= 12:
            return "HIGH"
        elif score >= 8:
            return "MEDIUM"
        return "LOW"


@dataclass
class ScoutReport:
    """Complete frontier scout report."""

    date: datetime = field(default_factory=datetime.now)
    findings: List[Finding] = field(default_factory=list)
    executive_summary: str = ""
    model_landscape: str = ""
    sprint_recommendations: List[str] = field(default_factory=list)

    @property
    def high_priority(self) -> List[Finding]:
        return [f for f in self.findings if f.priority_score >= 12]

    @property
    def medium_priority(self) -> List[Finding]:
        return [f for f in self.findings if 8 <= f.priority_score < 12]

    @property
    def low_priority(self) -> List[Finding]:
        return [f for f in self.findings if f.priority_score < 8]

    def to_markdown(self) -> str:
        """Render report as markdown."""
        lines = [
            f"# Cortex Frontier Scout — Week of {self.date.strftime('%Y-%m-%d')}",
            "",
            "## Executive Summary",
            self.executive_summary or "_No summary generated._",
            "",
        ]

        # HIGH priority
        if self.high_priority:
            lines.append("## HIGH Priority (Score ≥12)")
            lines.append("")
            for f in sorted(self.high_priority, key=lambda x: -x.priority_score):
                lines.extend(self._format_finding(f))
            lines.append("")

        # MEDIUM priority
        if self.medium_priority:
            lines.append("## MEDIUM Priority (Score 8-11)")
            lines.append("")
            for f in sorted(self.medium_priority, key=lambda x: -x.priority_score):
                lines.extend(self._format_finding(f, brief=True))
            lines.append("")

        # LOW priority
        if self.low_priority:
            lines.append("## LOW Priority / Watch List")
            lines.append("")
            for f in self.low_priority:
                lines.append(f"- [{f.title}]({f.source_url}) — {f.description[:80]}")
            lines.append("")

        # Sprint recommendations
        if self.sprint_recommendations:
            lines.append("## Recommended Sprint Items")
            lines.append("")
            for i, rec in enumerate(self.sprint_recommendations[:3], 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Model landscape
        if self.model_landscape:
            lines.append("## Model Landscape Update")
            lines.append(self.model_landscape)
            lines.append("")

        return "\n".join(lines)

    def _format_finding(self, f: Finding, brief: bool = False) -> List[str]:
        lines = [
            f"### {f.title} (Score: {f.priority_score})",
            f"- **What**: {f.description} — [source]({f.source_url})",
            f"- **Subsystem**: {f.subsystem}",
            f"- **Action**: {f.action}",
        ]
        if not brief:
            lines.append(f"- **Integration path**: {f.integration_path}")
            if f.effort_hours:
                lines.append(f"- **Effort**: {f.effort_hours}h")
        lines.append("")
        return lines

    def to_json(self) -> Dict[str, Any]:
        """Serialize for batch storage."""
        return {
            "date": self.date.isoformat(),
            "findings_count": len(self.findings),
            "high_count": len(self.high_priority),
            "medium_count": len(self.medium_priority),
            "low_count": len(self.low_priority),
            "executive_summary": self.executive_summary,
            "findings": [
                {
                    "title": f.title,
                    "source_url": f.source_url,
                    "category": f.category,
                    "priority_score": f.priority_score,
                    "priority_tier": f.priority_tier,
                    "subsystem": f.subsystem,
                    "action": f.action,
                }
                for f in self.findings
            ],
        }


class FrontierScout:
    """
    Frontier intelligence engine for Cortex.

    Designed to be invoked by:
    1. Claude Code slash command (/frontier-scout)
    2. Cortex batch system (research_batcher)
    3. Direct CLI (python -m cortex.engines.frontier_scout)
    """

    def __init__(self):
        self.frontier_dir = FRONTIER_DIR
        self.frontier_dir.mkdir(parents=True, exist_ok=True)
        self.reports_index = self.frontier_dir / "reports_index.json"

    def get_scan_categories(self) -> Dict[str, Any]:
        """Return scan categories for external callers (slash commands, batch)."""
        return SCAN_CATEGORIES

    def get_report_template(self) -> str:
        """Return the markdown template for report generation."""
        return ScoutReport().to_markdown()

    def save_report(self, content: str, date: Optional[datetime] = None) -> Path:
        """Save a generated report to the .frontier directory."""
        date = date or datetime.now()
        filename = f"scout_report_{date.strftime('%Y-%m-%d')}.md"
        report_path = self.frontier_dir / filename
        report_path.write_text(content)

        # Update index
        self._update_index(report_path, date)

        logger.info(f"Scout report saved: {report_path}")
        return report_path

    def get_latest_report(self) -> Optional[Path]:
        """Get the most recent scout report."""
        reports = sorted(self.frontier_dir.glob("scout_report_*.md"), reverse=True)
        return reports[0] if reports else None

    def get_report_history(self) -> List[Dict[str, Any]]:
        """Return list of past reports with metadata."""
        if self.reports_index.exists():
            return json.loads(self.reports_index.read_text())
        return []

    def should_run(self) -> bool:
        """Check if a scan is due (>6 days since last report)."""
        latest = self.get_latest_report()
        if not latest:
            return True
        try:
            date_str = latest.stem.replace("scout_report_", "")
            last_date = datetime.strptime(date_str, "%Y-%m-%d")
            days_since = (datetime.now() - last_date).days
            return days_since >= 6
        except ValueError:
            return True

    def _update_index(self, report_path: Path, date: datetime):
        """Append to reports index."""
        history = self.get_report_history()
        history.append(
            {
                "date": date.isoformat(),
                "path": str(report_path),
                "filename": report_path.name,
            }
        )
        # Keep last 52 entries (1 year)
        history = history[-52:]
        self.reports_index.write_text(json.dumps(history, indent=2))


def get_batch_prompt() -> str:
    """Return the full prompt for batch API submission."""
    return (FRONTIER_DIR / "SCOUT_TASK_PROMPT.md").read_text()


if __name__ == "__main__":
    scout = FrontierScout()
    if scout.should_run():
        print(f"Frontier scout due. Last report: {scout.get_latest_report()}")
        print(f"Categories: {list(SCAN_CATEGORIES.keys())}")
        print("Run via: /frontier-scout")
    else:
        latest = scout.get_latest_report()
        print(f"Scout not due. Latest: {latest}")
