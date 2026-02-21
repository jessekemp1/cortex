import os
#!/usr/bin/env python3
"""
Prompt Learning Loop - Closes the loop between what you ask for and what Cortex recommends.

This module integrates prompt history analysis into Cortex's learning system to:
1. Adjust recommendation priorities based on what you actually ask about
2. Predict your next needs based on conversation patterns
3. Optimize tool/workflow suggestions based on your actual usage
4. Auto-tune confidence scores based on prompt-to-outcome correlation

This creates a self-improving system where Cortex gets smarter the more you use it.
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add cortex root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.prompt_history import (
    PrioritySignal,
    PromptHistoryAnalyzer,
    PromptPattern,
    WorkflowPattern,
)

try:
    from learning import LearningSystem
except ImportError:
    # LearningSystem is optional
    LearningSystem = None


@dataclass
class PromptBasedRecommendation:
    """A recommendation generated from prompt history analysis."""

    type: str  # "next_action", "workflow", "context", "priority_shift"
    content: str
    confidence: float  # 0-1
    based_on: List[str]  # What patterns/signals this is based on
    projects: List[str]
    urgency: float  # 0-1


class PromptLearningLoop:
    """Integrates prompt history into Cortex learning loops."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))

        self.root_dir = root_dir
        self.analyzer = PromptHistoryAnalyzer()
        self.learning_system = LearningSystem() if LearningSystem else None

        # Cache directory for learning data
        self.cache_dir = Path.home() / ".cortex" / "prompt_learning"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def analyze_and_learn(self, days_back: int = 30) -> Dict[str, Any]:
        """Analyze prompt history and update learning system.

        This is the main entry point for the learning loop.

        Args:
            days_back: How many days of history to analyze

        Returns:
            Dictionary with analysis results and recommendations
        """
        print(f"Analyzing {days_back} days of conversation history...")

        # Step 1: Extract sessions
        sessions = self.analyzer.extract_sessions(days_back=days_back)
        print(f"  Found {len(sessions)} sessions")

        if not sessions:
            return {"error": "No sessions found"}

        # Step 2: Analyze patterns
        patterns = self.analyzer.analyze_prompt_patterns(sessions)
        priorities = self.analyzer.analyze_priorities(sessions, lookback_days=7)
        workflows = self.analyzer.detect_workflows(sessions)

        print(f"  Detected {len(patterns)} patterns")
        print(f"  Identified {len(priorities)} priorities")
        print(f"  Found {len(workflows)} workflows")

        # Step 3: Save analysis
        self.analyzer.save_analysis(patterns, priorities, workflows)

        # Step 4: Generate recommendations
        recommendations = self._generate_recommendations(patterns, priorities, workflows)

        # Step 5: Update learning weights
        self._update_learning_weights(patterns, priorities)

        # Step 6: Save learning state
        self._save_learning_state(
            {
                "timestamp": datetime.now().isoformat(),
                "patterns_count": len(patterns),
                "priorities_count": len(priorities),
                "workflows_count": len(workflows),
                "recommendations_count": len(recommendations),
            }
        )

        return {
            "sessions_analyzed": len(sessions),
            "patterns": [p.to_dict() for p in patterns[:10]],  # Top 10
            "priorities": [p.to_dict() for p in priorities],
            "workflows": [w.to_dict() for w in workflows[:5]],  # Top 5
            "recommendations": [self._recommendation_to_dict(r) for r in recommendations],
        }

    def _generate_recommendations(
        self,
        patterns: List[PromptPattern],
        priorities: List[PrioritySignal],
        workflows: List[WorkflowPattern],
    ) -> List[PromptBasedRecommendation]:
        """Generate actionable recommendations from analyzed patterns."""
        recommendations = []

        # 1. Priority-based recommendations
        for priority in priorities[:3]:  # Top 3 priorities
            if priority.strength > 0.15:  # Significant priority
                rec = PromptBasedRecommendation(
                    type="priority_shift",
                    content=f"Focus on {priority.category} work - this is {priority.strength:.0%} of your recent activity and {priority.trend}",
                    confidence=priority.strength,
                    based_on=[f"{len(priority.evidence)} recent prompts"],
                    projects=list(priority.projects_affected),
                    urgency=0.7 if priority.trend == "increasing" else 0.5,
                )
                recommendations.append(rec)

        # 2. Pattern-based next actions
        for pattern in patterns[:5]:  # Top 5 patterns
            # If a pattern is frequent and recent, suggest continuing it
            recency_hours = (datetime.now() - pattern.recent_activity).total_seconds() / 3600

            if recency_hours < 24:  # Active in last 24 hours
                rec = PromptBasedRecommendation(
                    type="next_action",
                    content=f"Continue work on: {pattern.topic}",
                    confidence=min(pattern.frequency / 10, 0.9),  # Cap at 0.9
                    based_on=[
                        f"{pattern.frequency} sessions",
                        f"Last active {recency_hours:.0f}h ago",
                    ],
                    projects=list(pattern.projects),
                    urgency=pattern.urgency_score,
                )
                recommendations.append(rec)

        # 3. Workflow suggestions
        for workflow in workflows[:3]:  # Top 3 workflows
            # Suggest next step in workflow based on pattern
            if workflow.success_rate > 0.6:  # Only suggest successful workflows
                rec = PromptBasedRecommendation(
                    type="workflow",
                    content=f"Consider following your typical workflow: {workflow.name}",
                    confidence=workflow.success_rate,
                    based_on=[
                        f"{workflow.frequency} times used",
                        f"{workflow.success_rate:.0%} success rate",
                    ],
                    projects=[],
                    urgency=0.5,
                )
                recommendations.append(rec)

        # 4. Context-based suggestions
        # Look for patterns that haven't been active recently but were frequent
        for pattern in patterns:
            recency_days = (datetime.now() - pattern.recent_activity).days

            if pattern.frequency >= 5 and recency_days > 7:  # Frequent but dormant
                rec = PromptBasedRecommendation(
                    type="context",
                    content=f"You haven't worked on '{pattern.topic}' in {recency_days} days - was this intentional?",
                    confidence=0.6,
                    based_on=[f"{pattern.frequency} sessions", f"Last: {recency_days}d ago"],
                    projects=list(pattern.projects),
                    urgency=0.3,
                )
                recommendations.append(rec)

        # Sort by urgency * confidence
        recommendations.sort(key=lambda r: r.urgency * r.confidence, reverse=True)

        return recommendations

    def _update_learning_weights(
        self, patterns: List[PromptPattern], priorities: List[PrioritySignal]
    ) -> None:
        """Update learning system weights based on prompt patterns.

        This adjusts Cortex's recommendation confidence based on what you actually ask for.
        """
        # Load existing learning config
        try:
            from learning_config import LearningConfig

            LearningConfig()
        except ImportError:
            # If learning_config doesn't exist yet, we'll create basic adjustments
            pass

        # Calculate category weights from priorities
        category_weights = {}
        total_strength = sum(p.strength for p in priorities)

        if total_strength > 0:
            for priority in priorities:
                # Weight = 0.5 to 1.5 based on priority strength
                weight = 0.5 + (priority.strength / total_strength)
                category_weights[priority.category] = weight

        # Save weights for future use
        weights_file = self.cache_dir / "category_weights.json"
        with open(weights_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "weights": category_weights,
                    "priorities": [p.to_dict() for p in priorities],
                },
                f,
                indent=2,
            )

        print(f"  Updated learning weights: {weights_file}")

    def get_next_action_prediction(self, current_context: Dict[str, Any]) -> Optional[str]:
        """Predict what you'll work on next based on patterns.

        Args:
            current_context: Dictionary with:
                - cwd: Current working directory
                - recent_files: Recently edited files
                - time_of_day: Current time
                - last_prompt: Last prompt sent

        Returns:
            Predicted next action or None
        """
        # Load cached analysis
        analysis = self.analyzer.load_analysis()
        if not analysis:
            return None

        # Simple prediction: Most frequent pattern in same project
        cwd = current_context.get("cwd", "")
        project = self._extract_project(cwd)

        if not project:
            return None

        # Find patterns for this project
        project_patterns = [
            p
            for p in analysis["patterns"]
            if project.lower() in [proj.lower() for proj in p["projects"]]
        ]

        if not project_patterns:
            return None

        # Get most frequent recent pattern
        top_pattern = project_patterns[0]

        return f"Based on your patterns, you'll likely work on: {top_pattern['topic']}"

    def get_optimized_recommendation(
        self, recommendation_type: str, base_confidence: float, context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """Optimize a recommendation's confidence based on prompt history.

        This is called by other Cortex systems to adjust their recommendations
        based on what you actually ask for.

        Args:
            recommendation_type: Type of recommendation
            base_confidence: Base confidence score
            context: Context dictionary

        Returns:
            (adjusted_confidence, explanation)
        """
        # Load weights
        weights_file = self.cache_dir / "category_weights.json"
        if not weights_file.exists():
            return base_confidence, "No prompt history data yet"

        with open(weights_file, "r") as f:
            data = json.load(f)

        weights = data.get("weights", {})

        # Find matching weight
        weight = weights.get(recommendation_type, 1.0)

        # Adjust confidence
        adjusted = min(1.0, base_confidence * weight)

        # Explanation
        if weight > 1.0:
            explanation = f"Boosted by {(weight-1)*100:.0f}% based on your recent focus"
        elif weight < 1.0:
            explanation = f"Reduced by {(1-weight)*100:.0f}% - not a current priority"
        else:
            explanation = "No adjustment based on prompt history"

        return adjusted, explanation

    def correlate_prompts_with_outcomes(self) -> Dict[str, Any]:
        """Correlate prompt patterns with session outcomes to identify what works.

        This analyzes which types of prompts lead to successful sessions vs failures.

        Returns:
            Dictionary with correlation insights
        """
        # Extract sessions with outcomes
        sessions = self.analyzer.extract_sessions(days_back=30)

        # Track success/failure by prompt category
        category_outcomes = {}

        for session in sessions:
            success = self.analyzer._session_completed_successfully(session)

            for prompt_data in session["prompts"]:
                prompt = prompt_data["text"]
                categories = self.analyzer._categorize_prompt(prompt)

                for category in categories:
                    if category not in category_outcomes:
                        category_outcomes[category] = {"success": 0, "failure": 0}

                    if success:
                        category_outcomes[category]["success"] += 1
                    else:
                        category_outcomes[category]["failure"] += 1

        # Calculate success rates
        correlations = {}
        for category, outcomes in category_outcomes.items():
            total = outcomes["success"] + outcomes["failure"]
            success_rate = outcomes["success"] / total if total > 0 else 0

            correlations[category] = {
                "success_rate": success_rate,
                "total_sessions": total,
                "successes": outcomes["success"],
                "failures": outcomes["failure"],
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "correlations": correlations,
            "insights": self._generate_correlation_insights(correlations),
        }

    def _generate_correlation_insights(self, correlations: Dict[str, Any]) -> List[str]:
        """Generate insights from prompt-outcome correlations."""
        insights = []

        for category, data in correlations.items():
            if data["total_sessions"] < 3:  # Need sufficient data
                continue

            success_rate = data["success_rate"]

            if success_rate > 0.8:
                insights.append(
                    f"✓ {category.capitalize()} prompts have high success rate ({success_rate:.0%}) - keep using this approach"
                )
            elif success_rate < 0.4:
                insights.append(
                    f"⚠ {category.capitalize()} prompts have low success rate ({success_rate:.0%}) - consider changing approach"
                )

        return insights

    def _recommendation_to_dict(self, rec: PromptBasedRecommendation) -> Dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "type": rec.type,
            "content": rec.content,
            "confidence": rec.confidence,
            "based_on": rec.based_on,
            "projects": rec.projects,
            "urgency": rec.urgency,
        }

    def _extract_project(self, cwd: str) -> Optional[str]:
        """Extract project name from path."""
        if not cwd:
            return None

        parts = Path(cwd).parts
        for part in reversed(parts):
            if part.startswith(".") or "session" in part.lower():
                continue
            if part and len(part) > 2:
                return part

        return None

    def _save_learning_state(self, state: Dict[str, Any]) -> None:
        """Save learning state for tracking."""
        state_file = self.cache_dir / "learning_state.jsonl"

        with open(state_file, "a") as f:
            f.write(json.dumps(state) + "\n")


def main():
    """CLI for prompt learning loop."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python prompt_learning.py <command> [args]")
        print("\nCommands:")
        print("  learn [days]         - Run learning loop (default: 30 days)")
        print("  recommendations      - Show current recommendations")
        print("  correlations         - Show prompt-outcome correlations")
        print("  weights              - Show current category weights")
        return

    command = sys.argv[1]
    loop = PromptLearningLoop()

    if command == "learn":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

        result = loop.analyze_and_learn(days_back=days)

        if "error" in result:
            print(f"\n⚠️  {result['error']}")
            print("\nThis is normal if:")
            print("  • You haven't used Claude Code much yet")
            print("  • Your sessions are in a different location")
            print("  • This is your first time running the analysis")
            print("\nNext steps:")
            print("  • Keep using Claude Code for a week")
            print("  • Run /prompt-learn again")
            print("  • The system will learn from your conversations")
            return

        print("\n=== LEARNING RESULTS ===")
        print(f"Sessions analyzed: {result['sessions_analyzed']}")

        if result.get("priorities"):
            print("\nTop priorities:")
            for priority in result["priorities"][:5]:
                print(
                    f"  - {priority['category']}: {priority['strength']:.0%} ({priority['trend']})"
                )

        if result.get("recommendations"):
            print("\nRecommendations:")
            for rec in result["recommendations"][:5]:
                print(f"  [{rec['confidence']:.0%}] {rec['content']}")

    elif command == "recommendations":
        analysis = loop.analyzer.load_analysis()
        if not analysis:
            print("No analysis found. Run 'learn' first.")
            return

        # Reconstruct patterns and priorities

        # This is simplified - in practice you'd reconstruct full objects
        print("\n=== CURRENT RECOMMENDATIONS ===")
        print("(Run 'learn' to generate fresh recommendations)")

    elif command == "correlations":
        correlations = loop.correlate_prompts_with_outcomes()

        print("\n=== PROMPT-OUTCOME CORRELATIONS ===")
        print(f"Analysis timestamp: {correlations['timestamp']}\n")

        for category, data in sorted(
            correlations["correlations"].items(),
            key=lambda x: x[1]["success_rate"],
            reverse=True,
        ):
            print(f"{category.capitalize()}:")
            print(f"  Success rate: {data['success_rate']:.0%}")
            print(
                f"  Sessions: {data['total_sessions']} ({data['successes']} success, {data['failures']} failure)"
            )
            print()

        if correlations["insights"]:
            print("INSIGHTS:")
            for insight in correlations["insights"]:
                print(f"  {insight}")

    elif command == "weights":
        weights_file = loop.cache_dir / "category_weights.json"
        if not weights_file.exists():
            print("No weights found. Run 'learn' first.")
            return

        with open(weights_file, "r") as f:
            data = json.load(f)

        print("\n=== CATEGORY WEIGHTS ===")
        print(f"Updated: {data['timestamp']}\n")

        for category, weight in sorted(data["weights"].items(), key=lambda x: x[1], reverse=True):
            arrow = "↑" if weight > 1.0 else "↓" if weight < 1.0 else "→"
            print(f"{arrow} {category}: {weight:.2f}x")


if __name__ == "__main__":
    main()
