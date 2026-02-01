#!/usr/bin/env python3
"""
Demo script for AI-as-a-Judge Quality Assessment

Demonstrates:
1. Pattern assessment
2. Recommendation assessment  
3. Batch assessment
4. Integration with learning system
"""

import asyncio
import json
from pathlib import Path

from intelligence.evaluation.quality_judge import QualityJudge
from learning import LearningSystem


async def demo_pattern_assessment():
    """Demo pattern quality assessment."""
    print("\n" + "=" * 60)
    print("PATTERN ASSESSMENT DEMO")
    print("=" * 60)

    # Create judge
    judge = QualityJudge()

    # Sample pattern
    pattern = {
        "id": "pattern_demo_001",
        "title": "Error handling in async functions",
        "description": (
            "Always wrap async API calls in try-except blocks to handle "
            "network timeouts and connection errors gracefully."
        ),
        "context": {"project": "cortex", "file": "bridge.py", "language": "python"},
    }

    query = "How should I handle errors in async API calls?"

    print(f"\nQuery: {query}")
    print(f"\nPattern: {pattern['title']}")
    print(f"Description: {pattern['description']}")

    print("\n[Assessment would be performed by Claude Haiku here]")
    print("\nCriteria:")
    print("  - Relevance (1-5): How relevant to the query?")
    print("  - Actionability (1-5): Clear actions provided?")
    print("  - Specificity (1-5): Specific enough to implement?")
    print("  - Accuracy (1-5): Technically sound?")

    print("\nSample score structure:")
    sample_score = {
        "relevance": 5,
        "actionability": 4,
        "specificity": 4,
        "accuracy": 5,
        "overall": 0.88,
        "rationale": "Highly relevant pattern with specific, accurate guidance",
    }
    print(json.dumps(sample_score, indent=2))


async def demo_recommendation_assessment():
    """Demo recommendation quality assessment."""
    print("\n" + "=" * 60)
    print("RECOMMENDATION ASSESSMENT DEMO")
    print("=" * 60)

    judge = QualityJudge()

    recommendation = {
        "id": "rec_demo_001",
        "title": "Implement defensive prompting in bridge.py",
        "type": "security",
        "priority": "A",
        "description": (
            "Add input validation and injection detection to bridge.py "
            "query methods to prevent prompt injection attacks."
        ),
        "action": (
            "1. Import safety validators\n"
            "2. Add validation before LLM calls\n"
            "3. Log validation failures"
        ),
    }

    context = {
        "project": "cortex",
        "goals": ["Improve security", "Add defensive prompting"],
        "recent_activity": ["Implemented safety module", "Added injection detection"],
    }

    print(f"\nRecommendation: {recommendation['title']}")
    print(f"Type: {recommendation['type']}")
    print(f"Priority: {recommendation['priority']}")
    print(f"\nContext: {context['goals']}")

    print("\n[Assessment would be performed by Claude Haiku here]")


def demo_batch_assessment():
    """Demo batch assessment capability."""
    print("\n" + "=" * 60)
    print("BATCH ASSESSMENT DEMO")
    print("=" * 60)

    print("\nBatch capability allows assessing multiple items efficiently:")
    print("  - Rate-limited to 50 requests/minute")
    print("  - Concurrent processing with asyncio")
    print("  - Graceful handling of individual failures")
    print("  - Results stored in ~/.cortex/evaluations.jsonl")


def demo_integration_with_learning():
    """Demo integration with learning system."""
    print("\n" + "=" * 60)
    print("LEARNING SYSTEM INTEGRATION")
    print("=" * 60)

    learning = LearningSystem()

    print("\nThe learning system now includes AI confidence calibration:")
    print("  - Compares AI quality scores with actual outcomes")
    print("  - Measures correlation between scores and success rates")
    print("  - Helps calibrate future assessments")

    calibration = learning.get_ai_confidence_calibration()

    print("\nCalibration structure:")
    print(json.dumps(calibration, indent=2))


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("AI-AS-A-JUDGE QUALITY ASSESSMENT DEMO")
    print("Cortex AI Engineering Improvements - Phase 2")
    print("=" * 60)

    asyncio.run(demo_pattern_assessment())
    asyncio.run(demo_recommendation_assessment())
    demo_batch_assessment()
    demo_integration_with_learning()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("\nAI-as-a-Judge provides:")
    print("  1. Automated quality scoring for patterns and recommendations")
    print("  2. Consistent assessment using Claude Haiku")
    print("  3. Integration with learning system for calibration")
    print("  4. Batch processing for efficiency")
    print("  5. Storage and retrieval for analysis")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
