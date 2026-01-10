"""
Interaction Learner - Automatic Learning from Claude Code Interactions

This module bridges the interaction capture system with Cortex's learning system.
It processes queued interactions and derives insights without manual feedback.

Key Learning Signals:
1. Implicit Feedback - Corrections, approvals, follow-ups detected from prompts
2. Tool Patterns - Success/failure rates by tool and project
3. Session Patterns - Flow patterns that lead to successful outcomes
4. Error Recovery - Patterns of retrying after failures

Integration Points:
- ClaudeSessionSource: Provides raw interaction data
- LearningSystem: Receives processed outcomes
- RecommendationEngine: Receives updated confidence calibration
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Queue file location (shared with hooks)
INTERACTION_QUEUE = Path.home() / ".cortex" / "interaction_queue.jsonl"
LEARNING_STATE = Path.home() / ".cortex" / "interaction_learning_state.json"


@dataclass
class ImplicitOutcome:
    """An outcome derived from implicit feedback signals."""
    outcome_id: str
    derived_from: str  # "correction", "approval", "tool_failure", "session_success"
    confidence: float  # How confident are we in this outcome?
    outcome_type: str  # "success", "partial", "failed"
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "outcome_id": self.outcome_id,
            "derived_from": self.derived_from,
            "confidence": self.confidence,
            "outcome_type": self.outcome_type,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LearningInsight:
    """A learning insight derived from interaction patterns."""
    insight_id: str
    insight_type: str  # "pattern", "calibration", "recommendation"
    title: str
    description: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    actionable: bool = False
    suggested_action: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "actionable": self.actionable,
            "suggested_action": self.suggested_action,
        }


class InteractionLearner:
    """
    Processes interaction data to derive learning signals automatically.

    This replaces manual `cortex feedback` calls with automatic learning
    from real-time interaction patterns.
    """

    def __init__(self):
        self.queue_file = INTERACTION_QUEUE
        self.state_file = LEARNING_STATE
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load learning state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load learning state: {e}")
        return {
            "last_processed": None,
            "total_processed": 0,
            "implicit_outcomes": 0,
            "insights_generated": 0,
        }

    def _save_state(self) -> None:
        """Save learning state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2)

    def process_queue(self) -> Dict[str, Any]:
        """
        Process all queued interactions and derive learning signals.

        Returns summary of processing results.
        """
        if not self.queue_file.exists():
            return {"status": "no_queue", "processed": 0}

        interactions = []
        try:
            with open(self.queue_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            interactions.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Failed to read queue: {e}")
            return {"status": "error", "error": str(e)}

        if not interactions:
            return {"status": "empty_queue", "processed": 0}

        # Process interactions
        outcomes = []
        insights = []

        # Group by session for context-aware analysis
        by_session = defaultdict(list)
        for interaction in interactions:
            session_id = interaction.get("session_id", "unknown")
            by_session[session_id].append(interaction)

        for session_id, session_interactions in by_session.items():
            # Analyze session interactions
            session_outcomes = self._analyze_session(session_id, session_interactions)
            outcomes.extend(session_outcomes)

            # Generate insights from patterns
            session_insights = self._generate_insights(session_id, session_interactions)
            insights.extend(session_insights)

        # Update learning system with implicit outcomes
        self._update_learning_system(outcomes)

        # Store in ClaudeSessionSource for pattern tracking
        self._update_session_patterns(interactions)

        # Clear processed queue
        self._clear_queue()

        # Update state
        self._state["last_processed"] = datetime.now().isoformat()
        self._state["total_processed"] += len(interactions)
        self._state["implicit_outcomes"] += len(outcomes)
        self._state["insights_generated"] += len(insights)
        self._save_state()

        return {
            "status": "success",
            "processed": len(interactions),
            "outcomes_derived": len(outcomes),
            "insights_generated": len(insights),
            "sessions_analyzed": len(by_session),
        }

    def _analyze_session(self, session_id: str,
                         interactions: List[Dict]) -> List[ImplicitOutcome]:
        """
        Analyze a session's interactions to derive implicit outcomes.

        Looks for:
        - Corrections (negative signal)
        - Approvals (positive signal)
        - Tool failures followed by success (recovery pattern)
        - Session completion without issues (positive signal)
        """
        import uuid
        outcomes = []

        prompts = [i for i in interactions if i.get("type") == "prompt_received"]
        tools = [i for i in interactions if i.get("type") == "tool_completed"]

        # Analyze prompt patterns for implicit feedback
        for i, prompt_data in enumerate(prompts):
            prompt = prompt_data.get("prompt", "").lower()

            # Detection: User correction
            if self._is_correction(prompt):
                outcomes.append(ImplicitOutcome(
                    outcome_id=f"imp_{uuid.uuid4().hex[:8]}",
                    derived_from="correction",
                    confidence=0.8,
                    outcome_type="failed",
                    context={
                        "session_id": session_id,
                        "prompt_index": i,
                        "prompt_snippet": prompt[:200],
                        "project": prompt_data.get("cwd", "").split("/")[-1],
                    },
                ))

            # Detection: User approval
            elif self._is_approval(prompt):
                outcomes.append(ImplicitOutcome(
                    outcome_id=f"imp_{uuid.uuid4().hex[:8]}",
                    derived_from="approval",
                    confidence=0.9,
                    outcome_type="success",
                    context={
                        "session_id": session_id,
                        "prompt_index": i,
                        "project": prompt_data.get("cwd", "").split("/")[-1],
                    },
                ))

        # Analyze tool outcomes
        tool_failures = [t for t in tools if not t.get("success", True)]
        tool_successes = [t for t in tools if t.get("success", True)]

        # High failure rate in session suggests issues
        if len(tool_failures) > 0 and len(tools) > 2:
            failure_rate = len(tool_failures) / len(tools)
            if failure_rate > 0.3:
                outcomes.append(ImplicitOutcome(
                    outcome_id=f"imp_{uuid.uuid4().hex[:8]}",
                    derived_from="tool_failure_rate",
                    confidence=0.7,
                    outcome_type="partial",
                    context={
                        "session_id": session_id,
                        "failure_rate": failure_rate,
                        "total_tools": len(tools),
                        "failed_tools": [t.get("tool_name") for t in tool_failures],
                    },
                ))

        # Session ended normally with mostly successful tools
        ended = any(i.get("type") == "session_ended" for i in interactions)
        if ended and len(tool_successes) > len(tool_failures):
            outcomes.append(ImplicitOutcome(
                outcome_id=f"imp_{uuid.uuid4().hex[:8]}",
                derived_from="session_success",
                confidence=0.6,  # Lower confidence - session ending normally is weak signal
                outcome_type="success",
                context={
                    "session_id": session_id,
                    "tool_count": len(tools),
                    "success_rate": len(tool_successes) / max(len(tools), 1),
                },
            ))

        return outcomes

    def _is_correction(self, prompt: str) -> bool:
        """Detect if prompt indicates a correction."""
        correction_phrases = [
            "no, ", "that's wrong", "actually,", "i meant", "not what i",
            "try again", "that didn't work", "wrong file", "undo",
            "revert", "go back", "that broke", "you misunderstood",
            "that's not right", "fix that", "redo", "don't do",
        ]
        return any(phrase in prompt for phrase in correction_phrases)

    def _is_approval(self, prompt: str) -> bool:
        """Detect if prompt indicates approval."""
        approval_phrases = [
            "looks good", "perfect", "thanks", "great", "yes",
            "that works", "commit", "push", "ship it", "done",
            "nice", "awesome", "exactly", "correct", "good job",
            "that's right", "proceed", "continue",
        ]
        return any(phrase in prompt for phrase in approval_phrases)

    def _generate_insights(self, session_id: str,
                           interactions: List[Dict]) -> List[LearningInsight]:
        """Generate learning insights from session patterns."""
        import uuid
        insights = []

        tools = [i for i in interactions if i.get("type") == "tool_completed"]

        # Tool usage pattern insights
        tool_counts = defaultdict(int)
        tool_failures = defaultdict(int)
        for tool in tools:
            name = tool.get("tool_name", "unknown")
            tool_counts[name] += 1
            if not tool.get("success", True):
                tool_failures[name] += 1

        # Identify problematic tools
        for tool_name, count in tool_counts.items():
            if count >= 3:
                failure_rate = tool_failures.get(tool_name, 0) / count
                if failure_rate > 0.4:
                    insights.append(LearningInsight(
                        insight_id=f"ins_{uuid.uuid4().hex[:8]}",
                        insight_type="pattern",
                        title=f"High failure rate for {tool_name}",
                        description=f"{tool_name} failed {failure_rate:.0%} of the time in this session",
                        confidence=0.75,
                        evidence={
                            "tool_name": tool_name,
                            "total_uses": count,
                            "failures": tool_failures.get(tool_name, 0),
                        },
                        actionable=True,
                        suggested_action=f"Review {tool_name} usage patterns and common failure causes",
                    ))

        # Prompt pattern insights
        prompts = [i for i in interactions if i.get("type") == "prompt_received"]
        correction_count = sum(1 for p in prompts if self._is_correction(p.get("prompt", "").lower()))

        if len(prompts) >= 3 and correction_count / len(prompts) > 0.2:
            insights.append(LearningInsight(
                insight_id=f"ins_{uuid.uuid4().hex[:8]}",
                insight_type="calibration",
                title="High correction rate detected",
                description=f"{correction_count}/{len(prompts)} prompts were corrections",
                confidence=0.8,
                evidence={
                    "total_prompts": len(prompts),
                    "corrections": correction_count,
                    "session_id": session_id,
                },
                actionable=True,
                suggested_action="Consider being more careful with assumptions and asking clarifying questions",
            ))

        return insights

    def _update_learning_system(self, outcomes: List[ImplicitOutcome]) -> None:
        """Update Cortex learning system with implicit outcomes."""
        if not outcomes:
            return

        try:
            from feedback import FeedbackLogger, OutcomeEntry

            logger_instance = FeedbackLogger()

            for outcome in outcomes:
                # Convert implicit outcome to OutcomeEntry format
                entry = OutcomeEntry(
                    timestamp=outcome.timestamp.isoformat(),
                    recommendation_id=f"implicit_{outcome.outcome_id}",
                    recommendation_title=f"Implicit {outcome.derived_from}",
                    recommendation_type=f"implicit_{outcome.derived_from}",
                    priority="B",  # Medium priority for implicit outcomes
                    confidence=outcome.confidence,
                    followed=True,  # Implicit outcomes are always "followed"
                    outcome=outcome.outcome_type,
                    notes=f"Auto-derived from {outcome.derived_from}",
                    context={
                        "project": outcome.context.get("project", "unknown"),
                        "session_id": outcome.context.get("session_id"),
                        "implicit": True,
                    },
                )
                logger_instance.log_outcome(entry)

            logger.info(f"Updated learning system with {len(outcomes)} implicit outcomes")

        except Exception as e:
            logger.error(f"Failed to update learning system: {e}")

    def _update_session_patterns(self, interactions: List[Dict]) -> None:
        """Update ClaudeSessionSource patterns from interactions."""
        try:
            from engines.claude_session_absorber import ClaudeSessionSource

            source = ClaudeSessionSource()

            for interaction in interactions:
                int_type = interaction.get("type")

                if int_type == "prompt_received":
                    source.on_prompt_received(
                        session_id=interaction.get("session_id", "unknown"),
                        prompt=interaction.get("prompt", ""),
                        cwd=interaction.get("cwd", ""),
                    )
                elif int_type == "tool_completed":
                    source.on_tool_completed(
                        session_id=interaction.get("session_id", "unknown"),
                        tool_name=interaction.get("tool_name", ""),
                        tool_input=interaction.get("tool_input", {}),
                        tool_response=interaction.get("response_summary", {}),
                        success=interaction.get("success", True),
                        cwd=interaction.get("cwd", ""),
                    )
                elif int_type == "session_ended":
                    source.on_session_ended(
                        session_id=interaction.get("session_id", "unknown"),
                        reason=interaction.get("reason", "unknown"),
                        cwd=interaction.get("cwd", ""),
                    )

        except Exception as e:
            logger.error(f"Failed to update session patterns: {e}")

    def _clear_queue(self) -> None:
        """Clear processed interactions from queue."""
        try:
            if self.queue_file.exists():
                self.queue_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")

    def get_learning_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get a summary of learning from recent interactions."""
        try:
            from engines.claude_session_absorber import ClaudeSessionSource

            source = ClaudeSessionSource()
            stats = source.get_implicit_feedback_stats(days=days)
            patterns = source.get_patterns(min_frequency=2)
            tool_rates = source.get_tool_success_rates()

            return {
                "period_days": days,
                "implicit_feedback": stats,
                "detected_patterns": len(patterns),
                "top_patterns": [p.to_dict() for p in patterns[:5]],
                "tool_success_rates": tool_rates,
                "learning_state": self._state,
            }

        except Exception as e:
            logger.error(f"Failed to get learning summary: {e}")
            return {"error": str(e)}

    def get_recommendations_for_session(self, project: str,
                                         recent_prompts: List[str]) -> List[str]:
        """
        Get recommendations based on learned patterns for current session.

        This is called at session start to provide proactive guidance.
        """
        recommendations = []

        try:
            from engines.claude_session_absorber import ClaudeSessionSource

            source = ClaudeSessionSource()

            # Check for high correction rate in this project
            sessions = source.get_session_history(project=project, days=14)
            if sessions:
                total_prompts = sum(s.get("prompt_count", 0) for s in sessions)
                # Get correction rate (would need to track this)
                if total_prompts > 10:
                    recommendations.append(
                        "Based on recent sessions, consider verifying file paths before edits."
                    )

            # Check tool success rates
            tool_rates = source.get_tool_success_rates()
            for tool, rates in tool_rates.items():
                if rates["frequency"] >= 5 and rates["success_rate"] < 0.7:
                    recommendations.append(
                        f"The {tool} tool has had issues recently. Double-check inputs."
                    )

        except Exception as e:
            logger.warning(f"Failed to get session recommendations: {e}")

        return recommendations[:3]  # Limit to 3 recommendations


def process_interaction_queue() -> Dict[str, Any]:
    """Convenience function to process the interaction queue."""
    learner = InteractionLearner()
    return learner.process_queue()


def get_interaction_learning_summary(days: int = 7) -> Dict[str, Any]:
    """Convenience function to get learning summary."""
    learner = InteractionLearner()
    return learner.get_learning_summary(days=days)
