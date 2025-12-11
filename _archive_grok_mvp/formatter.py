#!/usr/bin/env python3
"""
Converx Formatter - Formats strategist responses for display

Formats StrategistResponse objects into human-readable output.
"""

from typing import Optional
import json

try:
    from .orchestrator import StrategistResponse, Recommendation, ContextPrediction, SystemHealth
except ImportError:
    from orchestrator import StrategistResponse, Recommendation, ContextPrediction, SystemHealth


class ConverxFormatter:
    """Formats strategist responses."""

    @staticmethod
    def format_response(response: StrategistResponse, json_output: bool = False) -> str:
        """
        Format strategist response for display.

        Args:
            response: StrategistResponse to format
            json_output: If True, output JSON instead of formatted text

        Returns:
            Formatted string
        """
        if json_output:
            return ConverxFormatter._format_json(response)
        else:
            return ConverxFormatter._format_text(response)

    @staticmethod
    def _format_text(response: StrategistResponse) -> str:
        """Format as human-readable text."""
        lines = []

        # Header
        lines.append("╔══════════════════════════════════════════════════════╗")
        lines.append("║              CONVERX - STRATEGIC NEXT ACTION             ║")
        lines.append("╚══════════════════════════════════════════════════════╝")
        lines.append("")

        # Current State
        lines.append("📊 CURRENT STATE")
        lines.append("────────────────")
        state = response.current_state

        active = state.get("active_projects", 0)
        recent = state.get("recent_projects", 0)
        dormant = state.get("dormant_projects", 0)
        total = state.get("total_projects", 0)

        if total > 0:
            lines.append(f"Active Projects: {active} (3+ commits in 7d)")
            if recent > 0:
                lines.append(f"Recent Projects: {recent} (commits in 7d)")
            if dormant > 0:
                lines.append(f"Dormant Projects: {dormant} (only 30d commits)")
            lines.append(f"Total Projects: {total}")

        priority_a = state.get("priority_a_goals", 0)
        priority_b = state.get("priority_b_goals", 0)
        if priority_a > 0 or priority_b > 0:
            lines.append(f"Priority A Goals: {priority_a}")
            if priority_b > 0:
                lines.append(f"Priority B Goals: {priority_b}")

        pending = state.get("goals_pending", 0)
        in_progress = state.get("goals_in_progress", 0)
        if pending > 0 or in_progress > 0:
            lines.append(f"Goals: {in_progress} in progress, {pending} pending")

        blockers = state.get("blockers", [])
        if blockers:
            lines.append(f"Blockers: {len(blockers)}")
            for blocker in blockers[:3]:  # Show first 3
                lines.append(f"  • {blocker['project']}: {blocker['blocker']}")

        lines.append("")
        
        # System Health (Golden Spec: Dependency Transparency)
        lines.append("🔧 SYSTEM HEALTH")
        lines.append("────────────────")
        health = response.system_health
        status_icon = "✅" if health.all_active else "⚠️"
        lines.append(f"{status_icon} Integrations: {health.active_count}/4 active")
        
        if not health.all_active:
            missing = []
            if not health.project_scanner:
                missing.append("Project Scanner")
            if not health.goal_parser:
                missing.append("Goal Parser")
            if not health.recommendation_engine:
                missing.append("Recommendation Engine")
            if not health.context_intelligence:
                missing.append("Context Intelligence")
            
            if missing:
                lines.append(f"   Missing: {', '.join(missing)}")
                lines.append(f"   Note: System will work with reduced capability")
        
        lines.append("")
        lines.append("")

        # Next Action
        if response.next_action:
            lines.append("🎯 NEXT ACTION")
            lines.append("────────────────")
            lines.append(ConverxFormatter._format_recommendation(response.next_action, detailed=True))
            lines.append("")
        else:
            lines.append("🎯 NEXT ACTION")
            lines.append("────────────────")
            lines.append("No recommendations available.")
            lines.append("")
            lines.append("Try:")
            lines.append("  • Check ACTION_PLAN.md for goals")
            lines.append("  • Review project activity")
            lines.append("  • Run: python ai_intelligence.py --recommend")
            lines.append("")

        # Alternative Actions
        if response.alternative_actions:
            lines.append("────────────────────────────────────────────────────────────")
            lines.append("💡 ALTERNATIVE ACTIONS")
            lines.append("────────────────────────────────────────────────────────────")

            for i, rec in enumerate(response.alternative_actions, 2):
                lines.append(f"{i}. {ConverxFormatter._format_recommendation(rec, detailed=False)}")
                lines.append("")

        # Context Predictions
        if response.context_predictions:
            lines.append("────────────────────────────────────────────────────────────")
            lines.append("🔮 CONTEXT PREDICTIONS")
            lines.append("────────────────────────────────────────────────────────────")

            for pred in response.context_predictions[:3]:  # Show top 3
                confidence_icon = "🟢" if pred.confidence >= 0.8 else "🟡" if pred.confidence >= 0.6 else "⚪"
                lines.append(f"{confidence_icon} {pred.title} ({pred.confidence:.0%} confidence)")
                lines.append(f"   {pred.description}")
                lines.append(f"   Command: {pred.command}")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_recommendation(rec: Recommendation, detailed: bool = True) -> str:
        """Format a single recommendation with enhanced traceability."""
        priority_icon = "🔴" if rec.priority == "high" else "🟡" if rec.priority == "medium" else "⚪"
        priority_label = rec.priority.upper()

        lines = []

        if detailed:
            lines.append(f"[{priority_label}] {rec.title}")
            lines.append("")
            lines.append(f"Why: {rec.rationale}")
            lines.append("")
            
            # Enhanced Traceability (Golden Spec: Solution-Outcome Alignment)
            # Show decision factors if available
            if hasattr(rec, 'decision_factors') and rec.decision_factors:
                lines.append("Decision Factors:")
                for factor, weight in rec.decision_factors.items():
                    lines.append(f"  • {factor}: {weight:.0%}")
                lines.append("")
            else:
                # Fallback: Extract traceability from rationale
                # Show priority, impact, and confidence as decision factors
                lines.append("Decision Factors:")
                if rec.priority == "high":
                    lines.append(f"  • Priority: High (weight: 40%)")
                lines.append(f"  • Impact: {rec.estimated_impact} (weight: 30%)")
                lines.append(f"  • Confidence: {rec.confidence:.0%} (weight: 30%)")
                lines.append("")
            
            lines.append(f"Effort: {rec.estimated_effort}")
            lines.append(f"Impact: {rec.estimated_impact}")
            lines.append(f"Confidence: {rec.confidence:.0%}")
            lines.append("")

            if rec.description:
                # Extract next steps from description if present
                desc_lines = rec.description.split("\n")
                next_steps_started = False
                for line in desc_lines:
                    if "Next steps:" in line or "next steps:" in line.lower():
                        next_steps_started = True
                        lines.append("Next Steps:")
                    elif next_steps_started and line.strip().startswith("•"):
                        lines.append(f"  {line.strip()}")
                    elif next_steps_started and line.strip() and not line.strip().startswith("•"):
                        # End of next steps
                        break

            if rec.related_projects:
                lines.append(f"Related Projects: {', '.join(rec.related_projects)}")

            if rec.related_goals:
                lines.append(f"Related Goals: {', '.join(rec.related_goals)}")
        else:
            lines.append(f"{priority_icon} [{priority_label}] {rec.title}")
            lines.append(f"   {rec.rationale[:100]}..." if len(rec.rationale) > 100 else f"   {rec.rationale}")

        return "\n".join(lines)

    @staticmethod
    def _format_json(response: StrategistResponse) -> str:
        """Format as JSON."""
        data = {
            "current_state": response.current_state,
            "system_health": response.system_health.to_dict(),
            "next_action": ConverxFormatter._recommendation_to_dict(response.next_action) if response.next_action else None,
            "alternative_actions": [
                ConverxFormatter._recommendation_to_dict(rec) for rec in response.alternative_actions
            ],
            "context_predictions": [
                ConverxFormatter._context_prediction_to_dict(pred) for pred in response.context_predictions
            ]
        }
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def _recommendation_to_dict(rec: Recommendation) -> dict:
        """Convert Recommendation to dict."""
        return {
            "id": rec.id,
            "type": rec.type,
            "priority": rec.priority,
            "title": rec.title,
            "description": rec.description,
            "rationale": rec.rationale,
            "estimated_effort": rec.estimated_effort,
            "estimated_impact": rec.estimated_impact,
            "confidence": rec.confidence,
            "related_projects": rec.related_projects,
            "related_goals": rec.related_goals,
            "prerequisites": rec.prerequisites
        }

    @staticmethod
    def _context_prediction_to_dict(pred: ContextPrediction) -> dict:
        """Convert ContextPrediction to dict."""
        return {
            "context_type": pred.context_type,
            "title": pred.title,
            "description": pred.description,
            "confidence": pred.confidence,
            "rationale": pred.rationale,
            "command": pred.command
        }

