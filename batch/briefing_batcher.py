import os
"""
Briefing Batch Processor

Batches morning briefing generation into single batch requests.
Reduces 4-5 sequential API calls to 1-2 batch requests.

Cost: 40-50% reduction on briefing generation
Time: Same end-to-end latency, asynchronous batch submission
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .batch_api_client import BatchAPIClient, BatchRequest

try:
    from cortex.conductor.batch_models import ConductorBatchModels as BatchModels
except ImportError:
    from .model_policy import AnthropicBatchModels as BatchModels  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class BriefingContext:
    """Context data for briefing generation"""

    portfolio_pulse: Dict[str, Any]
    system_health: Dict[str, Any]
    execution_history: Dict[str, Any]
    goals_context: Dict[str, Any]
    context_id: str = "briefing_001"


class RecommendationBatcher:
    """Batch recommendation generation for multiple briefing contexts"""

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize recommendation batcher with optional session manager integration"""
        self.client = BatchAPIClient()
        self.model_policy = BatchModels()
        self.root_dir = root_dir or Path(os.environ.get("CORTEX_ROOT_DIR", str(Path.cwd())))

        # Try to initialize session manager for context
        try:
            from cortex.intelligence.session_manager import SessionManager

            self.session_mgr = SessionManager(self.root_dir)
        except Exception:
            self.session_mgr = None
            logger.warning("SessionManager not available - briefings won't include session context")

        self.system_prompt = """You are a strategic advisor analyzing a developer's current state.
Provide clear, actionable recommendations based on:
1. Current portfolio/project status
2. System health metrics
3. Execution history and patterns

Format response as:
PRIORITY_ACTIONS:
- Action 1
- Action 2
- Action 3

BLOCKERS:
- Blocker 1
- Blocker 2

RECOMMENDED_FOCUS: [Primary goal]

ALTERNATIVE_APPROACHES:
- Approach 1
- Approach 2
- Approach 3
"""

    def process_batch(self, contexts: List[BriefingContext]) -> Dict[str, Any]:
        """
        Process multiple briefing contexts to get recommendations.

        Args:
            contexts: List of briefing contexts to process

        Returns:
            Dict with batch_id, submitted_count, completed_count, and results
        """
        if not contexts:
            return {
                "submitted_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "results": {},
            }

        logger.info(f"Processing {len(contexts)} briefing contexts for recommendations")

        try:
            # Build batch requests
            requests = self._build_recommendation_requests(contexts)

            if not requests:
                logger.warning("No valid requests generated")
                return {
                    "submitted_count": 0,
                    "completed_count": 0,
                    "failed_count": 0,
                    "results": {},
                }

            # Submit batch
            batch_id = self.client.submit_batch(
                requests, f"Briefing recommendations batch ({len(contexts)} items)"
            )
            logger.info(f"Recommendations batch submitted: {batch_id}")

            # Poll for results
            results_list = self.client.poll_results(batch_id)
            logger.info(f"Recommendations batch completed: {len(results_list)} results")

            # Process results
            results_dict = {}
            completed = 0
            failed = 0

            for result in results_list:
                context_id = result.custom_id
                try:
                    processed = self._process_recommendation_result(context_id, result.result)
                    results_dict[context_id] = processed
                    completed += 1
                except Exception as e:
                    logger.error(f"Failed to process result {context_id}: {e}")
                    results_dict[context_id] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    failed += 1

            return {
                "batch_id": batch_id,
                "submitted_count": len(requests),
                "completed_count": completed,
                "failed_count": failed,
                "results": results_dict,
            }

        except Exception as e:
            logger.error(f"Recommendation batching failed: {e}")
            raise

    def _build_recommendation_requests(self, contexts: List[BriefingContext]) -> List[BatchRequest]:
        """Convert briefing contexts to batch requests with session context integration"""
        requests = []
        models = BatchModels()

        # Get session context if available
        session_context = None
        if self.session_mgr:
            try:
                session_context = self.session_mgr.load_session_context()
            except Exception as e:
                logger.debug(f"Could not load session context: {e}")

        for context in contexts:
            # Build base prompt
            prompt_parts = [
                "Analyze this briefing state and provide strategic recommendations:",
                "",
                "PORTFOLIO STATE:",
                json.dumps(context.portfolio_pulse, indent=2),
                "",
                "SYSTEM HEALTH:",
                json.dumps(context.system_health, indent=2),
                "",
                "RECENT EXECUTION HISTORY:",
                json.dumps(context.execution_history, indent=2),
                "",
                "GOALS:",
                json.dumps(context.goals_context, indent=2),
            ]

            # Add session context if available
            if session_context:
                prompt_parts.extend(
                    [
                        "",
                        "CURRENT SESSION CONTEXT:",
                        f"Project: {session_context.project}",
                        f"Working Directory: {session_context.working_directory}",
                        f"Current Focus: {session_context.current_focus}",
                        f"Active Goals: {', '.join(session_context.active_goals[:3])}",
                    ]
                )

            prompt_parts.append("\nProvide clear, prioritized recommendations for today's focus.")
            prompt = "\n".join(prompt_parts)

            request = BatchRequest(
                custom_id=context.context_id,
                params={
                    "model": models.default,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "system": self.system_prompt,
                },
            )
            requests.append(request)

        logger.debug(f"Created {len(requests)} recommendation requests")
        return requests

    def _process_recommendation_result(
        self, context_id: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and structure recommendation results"""
        try:
            message = result.get("message", {})
            content = message.get("content", [])

            if not content:
                return {"status": "failed", "error": "No content in response"}

            text = content[0].get("text", "")

            # Parse structured response
            return {
                "status": "success",
                "context_id": context_id,
                "raw_response": text,
                "recommendations": self._parse_recommendations(text),
                "processed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing recommendation result: {e}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    def _parse_recommendations(text: str) -> Dict[str, Any]:
        """Parse structured recommendations from response"""
        parsed = {
            "priority_actions": [],
            "blockers": [],
            "recommended_focus": "",
            "alternative_approaches": [],
        }

        # Parse priority actions
        if "PRIORITY_ACTIONS:" in text:
            section = text.split("PRIORITY_ACTIONS:")[1].split("\n\n")[0]
            parsed["priority_actions"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        # Parse blockers
        if "BLOCKERS:" in text:
            section = text.split("BLOCKERS:")[1].split("\n\n")[0]
            parsed["blockers"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        # Parse recommended focus
        if "RECOMMENDED_FOCUS:" in text:
            section = text.split("RECOMMENDED_FOCUS:")[1].split("\n\n")[0]
            parsed["recommended_focus"] = section.strip()

        # Parse alternatives
        if "ALTERNATIVE_APPROACHES:" in text:
            section = text.split("ALTERNATIVE_APPROACHES:")[1].split("\n\n")[0]
            parsed["alternative_approaches"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        return parsed


class InsightBatcher:
    """Batch learning insights and decision generation"""

    def __init__(self):
        """Initialize insight batcher"""
        self.client = BatchAPIClient()
        # Model policy mirrors RecommendationBatcher: BatchModels picks the
        # appropriate Anthropic batch model for briefing/insight workloads.
        self.model_policy = BatchModels()
        self.system_prompt = """You are a learning system analyzing execution patterns.
Provide insights based on:
1. Historical execution results
2. Success/failure patterns
3. Decision effectiveness
4. Confidence in outcomes

Format response as:
KEY_LEARNINGS:
- Learning 1
- Learning 2
- Learning 3

DECISION_POINTS:
- Decision point 1
- Decision point 2

CONFIDENCE_ASSESSMENT:
Success likelihood: [percentage]%
Reasoning: [explanation]

ADJUSTMENT_SUGGESTIONS:
- Suggestion 1
- Suggestion 2
"""

    def process_batch(self, contexts: List[BriefingContext]) -> Dict[str, Any]:
        """
        Process multiple contexts for learning insights and decisions.

        Args:
            contexts: List of briefing contexts

        Returns:
            Dict with batch_id, submitted_count, completed_count, and results
        """
        if not contexts:
            return {
                "submitted_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "results": {},
            }

        logger.info(f"Processing {len(contexts)} contexts for learning insights")

        try:
            # Build requests
            requests = self._build_insight_requests(contexts)

            if not requests:
                logger.warning("No valid insight requests generated")
                return {
                    "submitted_count": 0,
                    "completed_count": 0,
                    "failed_count": 0,
                    "results": {},
                }

            # Submit batch
            batch_id = self.client.submit_batch(
                requests, f"Briefing insights batch ({len(contexts)} items)"
            )
            logger.info(f"Insights batch submitted: {batch_id}")

            # Poll for results
            results_list = self.client.poll_results(batch_id)
            logger.info(f"Insights batch completed: {len(results_list)} results")

            # Process results
            results_dict = {}
            completed = 0
            failed = 0

            for result in results_list:
                context_id = result.custom_id
                try:
                    processed = self._process_insight_result(context_id, result.result)
                    results_dict[context_id] = processed
                    completed += 1
                except Exception as e:
                    logger.error(f"Failed to process insight result {context_id}: {e}")
                    results_dict[context_id] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    failed += 1

            return {
                "batch_id": batch_id,
                "submitted_count": len(requests),
                "completed_count": completed,
                "failed_count": failed,
                "results": results_dict,
            }

        except Exception as e:
            logger.error(f"Insight batching failed: {e}")
            raise

    def _build_insight_requests(self, contexts: List[BriefingContext]) -> List[BatchRequest]:
        """Convert contexts to insight batch requests"""
        requests = []

        for context in contexts:
            prompt = f"""Analyze this execution history and generate learning insights:

EXECUTION HISTORY:
{json.dumps(context.execution_history, indent=2)}

GOALS:
{json.dumps(context.goals_context, indent=2)}

Provide learning insights, decision points, and confidence assessment for future execution."""

            request = BatchRequest(
                custom_id=f"{context.context_id}_insights",
                params={
                    "model": self.model_policy.for_briefing(),
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                    "system": self.system_prompt,
                },
            )
            requests.append(request)

        logger.debug(f"Created {len(requests)} insight requests")
        return requests

    def _process_insight_result(self, context_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and structure insight results"""
        try:
            message = result.get("message", {})
            content = message.get("content", [])

            if not content:
                return {"status": "failed", "error": "No content in response"}

            text = content[0].get("text", "")

            return {
                "status": "success",
                "context_id": context_id,
                "raw_response": text,
                "insights": self._parse_insights(text),
                "processed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing insight result: {e}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    def _parse_insights(text: str) -> Dict[str, Any]:
        """Parse structured insights from response"""
        parsed = {
            "key_learnings": [],
            "decision_points": [],
            "confidence_assessment": "",
            "adjustment_suggestions": [],
        }

        # Parse learnings
        if "KEY_LEARNINGS:" in text:
            section = text.split("KEY_LEARNINGS:")[1].split("\n\n")[0]
            parsed["key_learnings"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        # Parse decisions
        if "DECISION_POINTS:" in text:
            section = text.split("DECISION_POINTS:")[1].split("\n\n")[0]
            parsed["decision_points"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        # Parse confidence
        if "CONFIDENCE_ASSESSMENT:" in text:
            section = text.split("CONFIDENCE_ASSESSMENT:")[1].split("\n\n")[0]
            parsed["confidence_assessment"] = section.strip()

        # Parse adjustments
        if "ADJUSTMENT_SUGGESTIONS:" in text:
            section = text.split("ADJUSTMENT_SUGGESTIONS:")[1].split("\n\n")[0]
            parsed["adjustment_suggestions"] = [
                line.strip("- ").strip()
                for line in section.split("\n")
                if line.strip().startswith("-")
            ]

        return parsed
