#!/usr/bin/env python3
"""
AI-as-a-Judge Quality Evaluation

Uses Claude to evaluate pattern matches and recommendations for quality.
Implements discrete 1-5 scoring as recommended in "AI Engineering" book.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

# Import prompt versioning system
try:
    from prompts import PromptRegistry
except ImportError:
    PromptRegistry = None


@dataclass
class PatternScore:
    """Quality scores for a pattern match.

    Uses discrete 1-5 scale as recommended by book for clearer calibration.
    """

    relevance: int  # 1-5: How relevant to the query?
    actionability: int  # 1-5: How actionable is this?
    specificity: int  # 1-5: Specific enough to act on?
    accuracy: int  # 1-5: Is the information accurate?
    overall: float  # Weighted average (0.0-1.0)
    rationale: str  # Explanation of scores
    timestamp: str = ""
    model: str = ""

    def __post_init__(self):
        """Set timestamp and calculate overall if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


@dataclass
class RecommendationScore:
    """Quality scores for a recommendation.

    Uses discrete 1-5 scale for clarity and calibration.
    """

    relevance: int  # 1-5: Relevant to context?
    actionability: int  # 1-5: Clear actions provided?
    clarity: int  # 1-5: Easy to understand?
    risk_awareness: int  # 1-5: Considers risks?
    overall: float  # Weighted average (0.0-1.0)
    rationale: str  # Explanation of scores
    timestamp: str = ""
    model: str = ""

    def __post_init__(self):
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


class QualityJudge:
    """AI-as-a-judge for pattern and recommendation quality.

    Uses Claude Haiku for fast, cost-effective evaluation.
    Stores results in ~/.cortex/evaluations.jsonl for analysis.
    """

    # Evaluation criteria definitions
    EVALUATION_CRITERIA = {
        "relevance": "How relevant is this to the query?",
        "actionability": "How actionable is the recommendation?",
        "specificity": "Is it specific enough to act on?",
        "accuracy": "Is the information accurate?",
        "clarity": "Is this clear and easy to understand?",
        "risk_awareness": "Does this consider potential risks?",
    }

    # Default model for evaluation (fast + cheap)
    DEFAULT_MODEL = "claude-3-5-haiku-20241022"

    # Rate limiting: max requests per minute
    MAX_REQUESTS_PER_MINUTE = 50

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        evaluations_file: Optional[Path] = None,
    ):
        """Initialize quality judge.

        Args:
            model: Claude model to use for evaluation (default: Haiku)
            evaluations_file: Path to store evaluations (default: ~/.cortex/evaluations.jsonl)
        """
        self.client = anthropic.Anthropic()
        self.model = model

        # Set up evaluations storage
        if evaluations_file is None:
            evaluations_file = Path.home() / ".cortex" / "evaluations.jsonl"
        self.evaluations_file = evaluations_file
        self.evaluations_file.parent.mkdir(parents=True, exist_ok=True)

        # Load prompt template
        self.prompt_registry = None
        if PromptRegistry:
            try:
                self.prompt_registry = PromptRegistry.get_instance()
                # Load evaluation template if available
                self.prompt_registry.load_template("quality_evaluation", "1.0.0")
            except Exception:
                # Fall back to inline prompts if template not available
                pass

        # Rate limiting state
        self._request_times: List[float] = []

    def _build_pattern_prompt(self, pattern: Dict, query: str) -> str:
        """Build evaluation prompt for a pattern match.

        Args:
            pattern: Pattern dictionary with title, description, context
            query: User query that triggered this pattern

        Returns:
            Formatted prompt string
        """
        # Try to use versioned template first
        if self.prompt_registry:
            try:
                template = self.prompt_registry.get_template("quality_evaluation", "1.0.0")
                return template.render(
                    item_type="pattern",
                    content=json.dumps(pattern, indent=2),
                    context=f"User query: {query}",
                )
            except Exception:
                pass

        # Fallback to inline prompt
        pattern_text = f"Title: {pattern.get('title', 'N/A')}\n"
        pattern_text += f"Description: {pattern.get('description', 'N/A')}\n"
        if pattern.get("context"):
            pattern_text += f"Context: {json.dumps(pattern['context'], indent=2)}\n"

        return f"""# Pattern Match Quality Evaluation

## User Query
{query}

## Pattern Match
{pattern_text}

## Evaluation Task
Rate this pattern match on a 1-5 scale for each dimension:

1. **Relevance** (1-5): How relevant is this pattern to the user's query?
   - 5: Highly relevant, directly addresses the query
   - 3: Somewhat relevant, tangentially related
   - 1: Not relevant

2. **Actionability** (1-5): How actionable is this pattern?
   - 5: Clear, specific actions with concrete steps
   - 3: General guidance, requires interpretation
   - 1: Vague, no clear actions

3. **Specificity** (1-5): Is it specific enough to act on?
   - 5: Includes specific files, commands, or steps
   - 3: General direction provided
   - 1: Too abstract to implement

4. **Accuracy** (1-5): Is the information accurate?
   - 5: Factually correct, technically sound
   - 3: Mostly correct with minor issues
   - 1: Contains errors or misconceptions

## Response Format
Provide JSON with integer scores (1-5) and brief rationale:
{{
    "relevance": <1-5>,
    "actionability": <1-5>,
    "specificity": <1-5>,
    "accuracy": <1-5>,
    "rationale": "<1-2 sentence explanation>"
}}

Respond with ONLY the JSON, no additional text."""

    def _build_recommendation_prompt(self, rec: Dict, context: Dict) -> str:
        """Build evaluation prompt for a recommendation.

        Args:
            rec: Recommendation dictionary
            context: Context dictionary (goals, projects, etc.)

        Returns:
            Formatted prompt string
        """
        # Try to use versioned template first
        if self.prompt_registry:
            try:
                template = self.prompt_registry.get_template("quality_evaluation", "1.0.0")
                return template.render(
                    item_type="recommendation",
                    content=json.dumps(rec, indent=2),
                    context=json.dumps(context, indent=2),
                )
            except Exception:
                pass

        # Fallback to inline prompt
        rec_text = f"Title: {rec.get('title', 'N/A')}\n"
        rec_text += f"Type: {rec.get('type', 'N/A')}\n"
        rec_text += f"Priority: {rec.get('priority', 'N/A')}\n"
        rec_text += f"Description: {rec.get('description', 'N/A')}\n"
        if rec.get("action"):
            rec_text += f"Action: {rec['action']}\n"

        context_text = json.dumps(context, indent=2)

        return f"""# Recommendation Quality Evaluation

## Context
{context_text}

## Recommendation
{rec_text}

## Evaluation Task
Rate this recommendation on a 1-5 scale for each dimension:

1. **Relevance** (1-5): How relevant is this to the context?
   - 5: Highly relevant, directly addresses needs
   - 3: Somewhat relevant
   - 1: Not relevant

2. **Actionability** (1-5): How actionable is this?
   - 5: Clear, specific actions with steps
   - 3: General guidance
   - 1: Vague, unclear

3. **Clarity** (1-5): Is this clear and easy to understand?
   - 5: Crystal clear, no ambiguity
   - 3: Mostly clear, some interpretation needed
   - 1: Confusing or unclear

4. **Risk Awareness** (1-5): Does this consider potential risks?
   - 5: Explicitly addresses risks and mitigation
   - 3: Mentions some risks
   - 1: Ignores risks

## Response Format
Provide JSON with integer scores (1-5) and brief rationale:
{{
    "relevance": <1-5>,
    "actionability": <1-5>,
    "clarity": <1-5>,
    "risk_awareness": <1-5>,
    "rationale": "<1-2 sentence explanation>"
}}

Respond with ONLY the JSON, no additional text."""

    def _parse_pattern_scores(self, response: str) -> PatternScore:
        """Parse API response into PatternScore.

        Args:
            response: JSON response from Claude

        Returns:
            PatternScore object

        Raises:
            ValueError: If response is invalid
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Validate scores are in range
            for key in ["relevance", "actionability", "specificity", "accuracy"]:
                if key not in data:
                    raise ValueError(f"Missing score: {key}")
                score = data[key]
                if not isinstance(score, int) or not 1 <= score <= 5:
                    raise ValueError(f"Score {key} must be integer 1-5, got {score}")

            # Calculate weighted overall (normalize to 0.0-1.0)
            # Weights: accuracy=30%, relevance=30%, actionability=25%, specificity=15%
            overall = (
                data["accuracy"] * 0.30
                + data["relevance"] * 0.30
                + data["actionability"] * 0.25
                + data["specificity"] * 0.15
            ) / 5.0  # Normalize from 1-5 scale to 0-1 scale

            return PatternScore(
                relevance=data["relevance"],
                actionability=data["actionability"],
                specificity=data["specificity"],
                accuracy=data["accuracy"],
                overall=round(overall, 3),
                rationale=data.get("rationale", ""),
                model=self.model,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Failed to parse pattern scores: {e}\nResponse: {response}")

    def _parse_recommendation_scores(self, response: str) -> RecommendationScore:
        """Parse API response into RecommendationScore.

        Args:
            response: JSON response from Claude

        Returns:
            RecommendationScore object

        Raises:
            ValueError: If response is invalid
        """
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Validate scores
            for key in ["relevance", "actionability", "clarity", "risk_awareness"]:
                if key not in data:
                    raise ValueError(f"Missing score: {key}")
                score = data[key]
                if not isinstance(score, int) or not 1 <= score <= 5:
                    raise ValueError(f"Score {key} must be integer 1-5, got {score}")

            # Calculate weighted overall (normalize to 0.0-1.0)
            # Weights: relevance=30%, actionability=30%, clarity=25%, risk=15%
            overall = (
                data["relevance"] * 0.30
                + data["actionability"] * 0.30
                + data["clarity"] * 0.25
                + data["risk_awareness"] * 0.15
            ) / 5.0  # Normalize to 0-1

            return RecommendationScore(
                relevance=data["relevance"],
                actionability=data["actionability"],
                clarity=data["clarity"],
                risk_awareness=data["risk_awareness"],
                overall=round(overall, 3),
                rationale=data.get("rationale", ""),
                model=self.model,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Failed to parse recommendation scores: {e}\nResponse: {response}")

    async def _rate_limited_request(self, prompt: str) -> str:
        """Make rate-limited API request.

        Args:
            prompt: Prompt to send to Claude

        Returns:
            Response text
        """
        # Rate limiting: ensure we don't exceed max requests per minute
        now = datetime.now().timestamp()

        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        # If at limit, wait
        if len(self._request_times) >= self.MAX_REQUESTS_PER_MINUTE:
            oldest = self._request_times[0]
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        # Record this request
        self._request_times.append(now)

        # Make request
        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    async def evaluate_pattern(self, pattern: Dict, query: str) -> PatternScore:
        """Evaluate a pattern match against a query.

        Args:
            pattern: Pattern dictionary with title, description, context
            query: User query that triggered this pattern

        Returns:
            PatternScore with quality ratings
        """
        prompt = self._build_pattern_prompt(pattern, query)
        response = await self._rate_limited_request(prompt)
        score = self._parse_pattern_scores(response)

        # Store evaluation
        self._store_evaluation(
            item_type="pattern",
            item_id=pattern.get("id", "unknown"),
            score=score.to_dict(),
            context={"query": query, "pattern": pattern},
        )

        return score

    async def evaluate_recommendation(self, rec: Dict, context: Dict) -> RecommendationScore:
        """Evaluate a recommendation in context.

        Args:
            rec: Recommendation dictionary
            context: Context dictionary (goals, projects, etc.)

        Returns:
            RecommendationScore with quality ratings
        """
        prompt = self._build_recommendation_prompt(rec, context)
        response = await self._rate_limited_request(prompt)
        score = self._parse_recommendation_scores(response)

        # Store evaluation
        self._store_evaluation(
            item_type="recommendation",
            item_id=rec.get("id", "unknown"),
            score=score.to_dict(),
            context={"recommendation": rec, "context": context},
        )

        return score

    async def batch_evaluate(
        self, items: List[Dict], eval_type: str, context: Optional[Dict] = None
    ) -> List:
        """Batch evaluation with rate limiting.

        Args:
            items: List of items to evaluate (patterns or recommendations)
            eval_type: "pattern" or "recommendation"
            context: Optional context for recommendations

        Returns:
            List of score objects (PatternScore or RecommendationScore)
        """
        if eval_type not in ["pattern", "recommendation"]:
            raise ValueError(f"Invalid eval_type: {eval_type}")

        tasks = []
        for item in items:
            if eval_type == "pattern":
                # For patterns, expect query in item or use default
                query = item.get("query", "")
                tasks.append(self.evaluate_pattern(item, query))
            else:
                # For recommendations
                ctx = context or {}
                tasks.append(self.evaluate_recommendation(item, ctx))

        # Execute with rate limiting
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors and return successful evaluations
        scores = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Warning: Evaluation {i} failed: {result}")
            else:
                scores.append(result)

        return scores

    def _store_evaluation(
        self, item_type: str, item_id: str, score: Dict, context: Dict
    ) -> None:
        """Store evaluation result to JSONL file.

        Args:
            item_type: "pattern" or "recommendation"
            item_id: Unique identifier for the item
            score: Score dictionary
            context: Context dictionary
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "item_type": item_type,
            "item_id": item_id,
            "score": score,
            "model": self.model,
            "context": context,
        }

        with open(self.evaluations_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def load_evaluations(
        self, item_type: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict]:
        """Load stored evaluations.

        Args:
            item_type: Filter by type (pattern/recommendation), or None for all
            limit: Maximum number to return (most recent first), or None for all

        Returns:
            List of evaluation dictionaries
        """
        if not self.evaluations_file.exists():
            return []

        evaluations = []
        with open(self.evaluations_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if item_type is None or entry.get("item_type") == item_type:
                        evaluations.append(entry)
                except json.JSONDecodeError:
                    continue

        # Return most recent first
        evaluations.reverse()

        if limit:
            evaluations = evaluations[:limit]

        return evaluations

    def get_ai_confidence_calibration(self) -> Dict[str, float]:
        """Get AI-evaluated confidence calibration.

        Compares AI quality scores with actual outcome success rates.
        This helps calibrate whether high AI scores predict success.

        Returns:
            Dictionary mapping score ranges to success rates:
            {
                "high (0.8-1.0)": 0.85,
                "medium (0.5-0.8)": 0.65,
                "low (0.0-0.5)": 0.45
            }
        """
        evaluations = self.load_evaluations(item_type="recommendation")

        if not evaluations:
            return {}

        # Group by AI score bucket
        buckets = {
            "high (0.8-1.0)": [],
            "medium (0.5-0.8)": [],
            "low (0.0-0.5)": [],
        }

        for eval_entry in evaluations:
            score = eval_entry.get("score", {})
            overall = score.get("overall", 0.0)

            # Categorize
            if overall >= 0.8:
                bucket = "high (0.8-1.0)"
            elif overall >= 0.5:
                bucket = "medium (0.5-0.8)"
            else:
                bucket = "low (0.0-0.5)"

            buckets[bucket].append(eval_entry)

        # For now, return counts (would need outcome data for true calibration)
        calibration = {}
        for bucket, entries in buckets.items():
            calibration[bucket] = len(entries)

        return calibration
