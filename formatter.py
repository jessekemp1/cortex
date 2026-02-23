#!/usr/bin/env python3
"""
Cortex Formatter - Formats strategist responses for display

Formats StrategistResponse objects into human-readable output.
"""

import json

try:
    from .orchestrator import SystemHealth  # noqa: F401
    from .orchestrator import ContextPrediction, Recommendation, StrategistResponse
except ImportError:
    from orchestrator import ContextPrediction, Recommendation, StrategistResponse


def make_clickable(text: str) -> str:
    """
    Ensure file paths are in a clickable format.
    Claude Code recognizes plain absolute paths as clickable.
    Just ensure paths are clean and not embedded in problematic contexts.
    """
    # For now, just return text as-is since Claude Code auto-detects paths
    # Paths like ~/Dev/file.md are already clickable
    return text


class CortexFormatter:
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
            return CortexFormatter._format_json(response)
        else:
            return CortexFormatter._format_text(response)

    @staticmethod
    def _format_text(response: StrategistResponse) -> str:
        """Format as human-readable text."""
        lines = []

        # Header
        lines.append("╔══════════════════════════════════════════════════════╗")
        lines.append("║              CORTEX - STRATEGIC NEXT ACTION             ║")
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
                lines.append("   Note: System will work with reduced capability")

        lines.append("")
        lines.append("")

        # Next Action
        if response.next_action:
            lines.append("🎯 NEXT ACTION")
            lines.append("────────────────")
            lines.append(
                CortexFormatter._format_recommendation(response.next_action, detailed=True)
            )
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

        # Command Workflow Suggestion
        if response.command_workflow and response.command_workflow.suggested_command:
            lines.append("────────────────────────────────────────────────────────────")
            lines.append("⚡ SUGGESTED WORKFLOW")
            lines.append("────────────────────────────────────────────────────────────")
            workflow = response.command_workflow
            lines.append(f"Start with: {workflow.suggested_command}")
            if workflow.full_workflow:
                lines.append(f"Full workflow: {workflow.full_workflow}")
            if workflow.rationale:
                lines.append(f"Rationale: {workflow.rationale}")
            if workflow.confidence > 0:
                conf_icon = (
                    "🟢"
                    if workflow.confidence >= 0.8
                    else "🟡" if workflow.confidence >= 0.6 else "⚪"
                )
                lines.append(f"Confidence: {conf_icon} {workflow.confidence:.0%}")
            lines.append("")

        # Alternative Actions
        if response.alternative_actions:
            lines.append("────────────────────────────────────────────────────────────")
            lines.append("💡 ALTERNATIVE ACTIONS")
            lines.append("────────────────────────────────────────────────────────────")

            for i, rec in enumerate(response.alternative_actions, 2):
                lines.append(f"{i}. {CortexFormatter._format_recommendation(rec, detailed=False)}")
                lines.append("")

        # Context Predictions
        if response.context_predictions:
            lines.append("────────────────────────────────────────────────────────────")
            lines.append("🔮 CONTEXT PREDICTIONS")
            lines.append("────────────────────────────────────────────────────────────")

            for pred in response.context_predictions[:3]:  # Show top 3
                confidence_icon = (
                    "🟢" if pred.confidence >= 0.8 else "🟡" if pred.confidence >= 0.6 else "⚪"
                )
                lines.append(f"{confidence_icon} {pred.title} ({pred.confidence:.0%} confidence)")
                lines.append(f"   {pred.description}")
                # Show file path on its own line for clickability
                if hasattr(pred, "file_path") and pred.file_path:
                    lines.append(f"   {pred.file_path}")
                lines.append("")

        # Make all file paths and URLs clickable
        return make_clickable("\n".join(lines))

    @staticmethod
    def _format_recommendation(rec: Recommendation, detailed: bool = True) -> str:
        """Format a single recommendation with enhanced traceability."""
        # Handle priority as int, enum, or string
        priority = rec.priority
        if isinstance(priority, int):
            priority_str = "high" if priority > 70 else "medium" if priority > 40 else "low"
        elif hasattr(priority, "value"):
            priority_str = priority.value.lower()
        else:
            priority_str = str(priority).lower()

        priority_icon = (
            "🔴" if priority_str == "high" else "🟡" if priority_str == "medium" else "⚪"
        )
        priority_label = priority_str.upper()

        # Get rationale/description before the if/else
        rationale = getattr(rec, "rationale", None) or getattr(rec, "description", "No details")

        # Handle confidence as enum or float
        conf = rec.confidence
        if hasattr(conf, "value"):
            conf_str = conf.value.upper()
        elif isinstance(conf, (int, float)):
            conf_str = f"{conf:.0%}"
        else:
            conf_str = str(conf)

        lines = []

        if detailed:
            lines.append(f"[{priority_label}] {rec.title}")
            lines.append("")
            lines.append(f"Why: {rationale}")
            lines.append("")

            # Enhanced Traceability (Golden Spec: Solution-Outcome Alignment)
            # Show decision factors if available
            if hasattr(rec, "decision_factors") and rec.decision_factors:
                lines.append("Decision Factors:")
                for factor, weight in rec.decision_factors.items():
                    lines.append(f"  • {factor}: {weight:.0%}")
                lines.append("")
            else:
                # Fallback: Show priority, impact, and confidence as decision factors
                lines.append("Decision Factors:")
                if priority_str == "high":
                    lines.append("  • Priority: High (weight: 40%)")
                lines.append(
                    f"  • Impact: {getattr(rec, 'estimated_impact', 'Unknown')} (weight: 30%)"
                )
                lines.append(f"  • Confidence: {conf_str} (weight: 30%)")
                lines.append("")

            lines.append(f"Effort: {getattr(rec, 'estimated_effort', 'Unknown')}")
            lines.append(f"Impact: {getattr(rec, 'estimated_impact', 'Unknown')}")
            lines.append(f"Confidence: {conf_str}")
            lines.append("")

            description = getattr(rec, "description", "")
            if description:
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

            related_projects = getattr(rec, "related_projects", None) or []
            if related_projects:
                lines.append(f"Related Projects: {', '.join(related_projects)}")

            related_goals = getattr(rec, "related_goals", None) or []
            if related_goals:
                lines.append(f"Related Goals: {', '.join(related_goals)}")
        else:
            lines.append(f"{priority_icon} [{priority_label}] {rec.title}")
            summary = rationale[:100] + "..." if len(rationale) > 100 else rationale
            lines.append(f"   {summary}")

        return "\n".join(lines)

    @staticmethod
    def _format_json(response: StrategistResponse) -> str:
        """Format as JSON."""
        data = {
            "current_state": response.current_state,
            "system_health": response.system_health.to_dict(),
            "next_action": (
                CortexFormatter._recommendation_to_dict(response.next_action)
                if response.next_action
                else None
            ),
            "alternative_actions": [
                CortexFormatter._recommendation_to_dict(rec) for rec in response.alternative_actions
            ],
            "context_predictions": [
                CortexFormatter._context_prediction_to_dict(pred)
                for pred in response.context_predictions
            ],
        }
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def _recommendation_to_dict(rec: Recommendation) -> dict:
        """Convert Recommendation to dict."""
        # Handle priority and confidence as enum or other types
        priority = rec.priority
        if isinstance(priority, int):
            priority_str = "high" if priority > 70 else "medium" if priority > 40 else "low"
        elif hasattr(priority, "value"):
            priority_str = priority.value
        else:
            priority_str = str(priority)

        conf = rec.confidence
        if hasattr(conf, "value"):
            conf_val = conf.value
        elif isinstance(conf, (int, float)):
            conf_val = conf
        else:
            conf_val = str(conf)

        rec_type = getattr(rec, "type", "unknown")
        if hasattr(rec_type, "value"):
            rec_type = rec_type.value

        return {
            "id": getattr(rec, "id", "unknown"),
            "type": rec_type,
            "priority": priority_str,
            "title": rec.title,
            "description": getattr(rec, "description", ""),
            "rationale": getattr(rec, "rationale", None) or getattr(rec, "description", ""),
            "estimated_effort": getattr(rec, "estimated_effort", None),
            "estimated_impact": getattr(rec, "estimated_impact", None),
            "confidence": conf_val,
            "related_projects": getattr(rec, "related_projects", []),
            "related_goals": getattr(rec, "related_goals", []),
            "prerequisites": getattr(rec, "prerequisites", []),
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
            "command": pred.command,
        }
