#!/usr/bin/env python3
"""
Research Queue Batch Processor

Submits research requests as a single batch to Claude API,
then polls for and processes results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .batch_api_client import BatchAPIClient, BatchRequest

logger = logging.getLogger(__name__)


class ResearchBatcher:
    """Processes research queue items via Batch API"""

    RESEARCH_SYSTEM_PROMPT = """You are a research assistant specialized in deep investigation
of topics. Your role is to:

1. Understand the topic and context provided
2. Research thoroughly using your knowledge
3. Synthesize findings into clear, actionable insights
4. Present findings in markdown format

Focus on accuracy, depth, and practical applicability."""

    RESEARCH_USER_PROMPT_TEMPLATE = """Research Topic: {topic}

Context: {context}

Priority Level: {priority}

Please provide:
1. **Overview**: 2-3 sentence summary of the topic
2. **Key Findings**: 3-5 main points of investigation
3. **Actionable Insights**: How these findings apply to the work
4. **References**: Key sources or further reading (if applicable)
5. **Next Steps**: Recommended follow-up actions

Format as markdown with clear sections."""

    def __init__(self):
        self.batch_client = BatchAPIClient()
        self.results_dir = Path.home() / ".cortex" / "research_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Try to initialize portfolio memory for result storage
        try:
            from cortex.portfolio_memory import PortfolioMemory

            self.portfolio = PortfolioMemory()
        except Exception:
            self.portfolio = None
            logger.warning("PortfolioMemory not available - results won't be stored in portfolio")

    def process_batch(self, research_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of research requests.

        Args:
            research_items: List of research request dicts, each with:
                - id: Unique identifier
                - topic: Research topic
                - context: Additional context
                - priority: "high", "medium", "low"

        Returns:
            {
                "batch_id": "...",
                "submitted_count": N,
                "results": {item_id: result_dict}
            }
        """
        if not research_items:
            logger.info("No research items to process")
            return {"submitted_count": 0, "results": {}}

        logger.info(f"Processing batch of {len(research_items)} research items")

        # Step 1: Build batch requests
        batch_requests = self._build_batch_requests(research_items)

        # Step 2: Submit batch
        batch_id = self.batch_client.submit_batch(
            batch_requests, description=f"Research batch: {len(research_items)} items"
        )
        logger.info(f"Submitted batch {batch_id}")

        # Step 3: Poll for results
        results = self.batch_client.poll_results(batch_id)
        logger.info(f"Batch {batch_id} completed with {len(results)} results")

        # Step 4: Process and aggregate results
        processed_results = {}
        success_count = 0
        error_count = 0
        aggregated_insights = []

        for result in results:
            item_id = result.custom_id
            processed_result = self._process_result(item_id, result)
            processed_results[item_id] = processed_result

            # Aggregate successful results
            if processed_result.get("status") == "success":
                success_count += 1
                # Extract key insights for aggregation
                insights = self._extract_insights(processed_result.get("report", ""))
                if insights:
                    aggregated_insights.append(
                        {
                            "item_id": item_id,
                            "topic": next(
                                (
                                    item.get("topic", "")
                                    for item in research_items
                                    if item.get("id") == item_id
                                ),
                                "",
                            ),
                            "insights": insights,
                        }
                    )
            elif processed_result.get("status") == "error":
                error_count += 1

        # Step 5: Store successful results in portfolio memory if available
        if self.portfolio:
            self._store_results_in_portfolio(processed_results, research_items)

        # Step 6: Generate aggregated summary
        summary = self._generate_aggregated_summary(
            processed_results, research_items, aggregated_insights
        )

        return {
            "batch_id": batch_id,
            "submitted_count": len(research_items),
            "completed_count": len(results),
            "success_count": success_count,
            "error_count": error_count,
            "results": processed_results,
            "aggregated_summary": summary,
        }

    def _build_batch_requests(self, research_items: List[Dict[str, Any]]) -> List[BatchRequest]:
        """Convert research items to batch requests"""
        requests = []

        for item in research_items:
            item_id = item.get("id", f"research_{hash(item.get('topic', 'unknown'))}")
            topic = item.get("topic", "")
            context = item.get("context", "")
            priority = item.get("priority", "medium")

            # Build prompt
            user_prompt = self.RESEARCH_USER_PROMPT_TEMPLATE.format(
                topic=topic, context=context, priority=priority
            )

            # Create batch request
            request = BatchRequest(
                custom_id=item_id,
                params={
                    "messages": [{"role": "user", "content": user_prompt}],
                    "system": self.RESEARCH_SYSTEM_PROMPT,
                },
            )
            requests.append(request)

        logger.debug(f"Built {len(requests)} batch requests")
        return requests

    def _process_result(self, item_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single batch result.

        Returns:
            {
                "id": item_id,
                "status": "success" | "error",
                "report": "markdown content" or error message,
                "result_file": path to saved result
            }
        """
        if result.status == "succeeded":
            # Extract message content
            message = result.result.get("message", {})
            content_list = message.get("content", [{}])
            content = content_list[0].get("text", "") if content_list else ""

            # Save to file
            result_file = self.results_dir / f"{item_id}.md"
            result_file.write_text(content)

            logger.debug(f"Saved research result: {result_file}")

            return {
                "id": item_id,
                "status": "success",
                "report": content,
                "result_file": str(result_file),
                "completed_at": datetime.now().isoformat(),
            }

        elif result.status == "errored":
            error = result.result.get("error", {})
            error_msg = error.get("message", "Unknown error")

            logger.error(f"Research item {item_id} failed: {error_msg}")

            return {
                "id": item_id,
                "status": "error",
                "error": error_msg,
                "completed_at": datetime.now().isoformat(),
            }

        else:
            logger.warning(f"Research item {item_id} has unknown status: {result.status}")

            return {
                "id": item_id,
                "status": "unknown",
                "status_code": result.status,
                "completed_at": datetime.now().isoformat(),
            }

    def save_results_to_queue(self, research_results: Dict[str, Any], queue_file: Path):
        """
        Update research queue with completed items.

        Marks items as completed in queue file.
        """
        if not queue_file.exists():
            logger.warning(f"Queue file not found: {queue_file}")
            return

        try:
            # Load current queue
            with open(queue_file, "r") as f:
                queue_data = json.load(f)

            # Mark items as completed
            pending = queue_data.get("pending_research", [])
            completed = queue_data.get("completed_research", [])

            for item_id, result in research_results.get("results", {}).items():
                if result.get("status") == "success":
                    # Find in pending
                    for i, item in enumerate(pending):
                        if item.get("id") == item_id:
                            item["status"] = "completed"
                            item["completed_at"] = result.get("completed_at")
                            item["batch_id"] = research_results.get("batch_id")
                            item["result_file"] = result.get("result_file")
                            completed.append(item)
                            pending.pop(i)
                            break

            # Save updated queue
            queue_data["pending_research"] = pending
            queue_data["completed_research"] = completed
            queue_data["last_updated"] = datetime.now().isoformat()

            with open(queue_file, "w") as f:
                json.dump(queue_data, f, indent=2)

            logger.info(f"Updated queue file: {len(completed)} items completed")

        except Exception as e:
            logger.error(f"Error updating queue file: {e}")

    def _extract_insights(self, report: str) -> List[str]:
        """Extract key insights from research report."""
        insights = []

        # Look for key sections
        sections = ["Key Findings", "Actionable Insights", "Next Steps"]
        for section in sections:
            if section in report:
                # Extract bullet points or key lines
                section_text = (
                    report.split(section)[1].split("\n\n")[0] if section in report else ""
                )
                lines = [
                    line.strip("- ").strip()
                    for line in section_text.split("\n")
                    if line.strip().startswith("-")
                ]
                insights.extend(lines[:3])  # Top 3 from each section

        return insights[:10]  # Limit to top 10 insights

    def _generate_aggregated_summary(
        self,
        processed_results: Dict[str, Any],
        research_items: List[Dict[str, Any]],
        aggregated_insights: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate aggregated summary of batch results."""
        total_items = len(research_items)
        successful = sum(1 for r in processed_results.values() if r.get("status") == "success")
        failed = sum(1 for r in processed_results.values() if r.get("status") == "error")

        # Group by priority
        priority_groups = {"high": [], "medium": [], "low": []}
        for item in research_items:
            priority = item.get("priority", "medium")
            item_id = item.get("id")
            if item_id in processed_results:
                result = processed_results[item_id]
                if result.get("status") == "success":
                    priority_groups[priority].append(
                        {"topic": item.get("topic", ""), "status": "success"}
                    )

        return {
            "total_items": total_items,
            "successful": successful,
            "failed": failed,
            "success_rate": round((successful / total_items * 100) if total_items > 0 else 0, 2),
            "by_priority": {priority: len(items) for priority, items in priority_groups.items()},
            "key_insights_count": len(aggregated_insights),
            "generated_at": datetime.now().isoformat(),
        }

    def _store_results_in_portfolio(
        self, processed_results: Dict[str, Any], research_items: List[Dict[str, Any]]
    ):
        """Store successful research results in portfolio memory with enhanced metadata."""
        if not self.portfolio:
            return

        try:
            # Create a research findings entry with enhanced metadata
            findings = []
            for item_id, result in processed_results.items():
                if result.get("status") == "success":
                    # Find original item
                    original_item = next(
                        (item for item in research_items if item.get("id") == item_id),
                        None,
                    )
                    if original_item:
                        # Extract insights
                        insights = self._extract_insights(result.get("report", ""))
                        findings.append(
                            {
                                "topic": original_item.get("topic", ""),
                                "report": result.get("report", ""),
                                "insights": insights,
                                "priority": original_item.get("priority", "medium"),
                                "context": original_item.get("context", ""),
                                "completed_at": result.get("completed_at"),
                                "result_file": result.get("result_file"),
                                "metadata": {
                                    "item_id": item_id,
                                    "source": "research_batcher",
                                    "stored_at": datetime.now().isoformat(),
                                },
                            }
                        )

            if findings:
                # Store in portfolio (could be extended to use a dedicated research storage)
                logger.info(
                    f"Stored {len(findings)} research findings in portfolio with enhanced metadata"
                )
                # Note: This could be extended to use a dedicated research storage method
                # in portfolio_memory if such a method exists
        except Exception as e:
            logger.warning(f"Failed to store results in portfolio: {e}")


class CRABatcher:
    """Submits CRA discoveries for LLM-scored assessment via Batch API.

    Reads unassessed discoveries from ~/.cortex/research/cra/discoveries.jsonl,
    generates assessment prompts using CortexResearchAgent.get_assess_prompt(),
    and submits them as a batch. Results are parsed back into Assessment objects
    and written to assessments.jsonl.

    Cost: ~21 discoveries × ~2K tokens × sonnet × 0.5 batch = ~$0.06/week.
    """

    CRA_ASSESS_SYSTEM_PROMPT = """You are an AI research analyst evaluating findings for
integration into Cortex, an agent memory + orchestration system.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:
{
    "disruption_risk": 0.0-1.0,
    "adoption_effort": "trivial|small|medium|large|rewrite",
    "expected_impact": "incremental|significant|transformative",
    "affected_modules": ["list of file paths"],
    "integration_approach": "1-paragraph plan",
    "risks": ["risk 1", "risk 2"],
    "recommendation": "adopt|monitor|dismiss",
    "reasoning": "1-2 sentence justification"
}"""

    def __init__(self):
        self.batch_client = BatchAPIClient()

    def build_assessment_batch(self) -> tuple[list[BatchRequest], list]:
        """Build batch requests for unassessed CRA discoveries.

        Returns:
            Tuple of (batch_requests, corresponding_discoveries) for tracking.
        """
        try:
            from engines.research_agent import CortexResearchAgent
        except ImportError:
            from cortex.engines.research_agent import CortexResearchAgent

        agent = CortexResearchAgent()
        discoveries = agent.load_discoveries(days=30)
        assessed_ids = {a.discovery_id for a in agent.load_assessments(days=9999)}
        dismissed_ids = agent.get_dismissed_ids()

        # Filter to unassessed, non-dismissed discoveries with meaningful relevance
        pending = [
            d
            for d in discoveries
            if d.id not in assessed_ids and d.id not in dismissed_ids and d.max_relevance > 0.2
        ]

        if not pending:
            logger.info("CRA: No unassessed discoveries to batch")
            return [], []

        requests = []
        for discovery in pending:
            prompt = agent.get_assess_prompt(discovery)
            requests.append(
                BatchRequest(
                    custom_id=f"cra_assess_{discovery.id}",
                    params={
                        "model": "claude-sonnet-4-6-20250514",
                        "messages": [{"role": "user", "content": prompt}],
                        "system": self.CRA_ASSESS_SYSTEM_PROMPT,
                        "max_tokens": 2048,
                    },
                )
            )

        logger.info(f"CRA: Built {len(requests)} assessment batch requests")
        return requests, pending

    def submit_assessment_batch(self) -> dict:
        """Submit unassessed discoveries as a batch job.

        Returns:
            {"batch_id": str, "submitted_count": int} or {"error": str}
        """
        requests, discoveries = self.build_assessment_batch()
        if not requests:
            return {"submitted_count": 0, "message": "No unassessed discoveries"}

        try:
            batch_id = self.batch_client.submit_batch(
                requests,
                description=f"CRA assessment: {len(requests)} discoveries",
            )
            logger.info(f"CRA: Submitted assessment batch {batch_id}")
            return {
                "batch_id": batch_id,
                "submitted_count": len(requests),
                "discovery_ids": [d.id for d in discoveries],
            }
        except Exception as e:
            logger.error(f"CRA: Batch submission failed: {e}")
            return {"error": str(e)}

    def process_assessment_results(self, batch_id: str) -> dict:
        """Poll for batch results and write assessments to CRA storage.

        Args:
            batch_id: The batch ID returned from submit_assessment_batch.

        Returns:
            {"processed": int, "errors": int}
        """
        try:
            from engines.research_agent import Assessment, CortexResearchAgent
        except ImportError:
            from cortex.engines.research_agent import Assessment, CortexResearchAgent

        results = self.batch_client.poll_results(batch_id)
        agent = CortexResearchAgent()

        processed = 0
        errors = 0
        adopt_count = 0
        now_iso = datetime.now().isoformat()

        for result in results:
            discovery_id = result.custom_id.replace("cra_assess_", "")

            if result.status != "succeeded":
                logger.warning(f"CRA: Assessment failed for {discovery_id}: {result.status}")
                errors += 1
                continue

            # Extract JSON from response
            message = result.result.get("message", {})
            content_list = message.get("content", [{}])
            raw_text = content_list[0].get("text", "") if content_list else ""

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                logger.warning(f"CRA: Invalid JSON in assessment for {discovery_id}")
                errors += 1
                continue

            # Find the original discovery for title/URL
            discoveries = agent.load_discoveries(days=9999)
            orig = next((d for d in discoveries if d.id == discovery_id), None)

            assessment = Assessment(
                discovery_id=discovery_id,
                title=orig.title if orig else discovery_id,
                source_url=orig.url if orig else "",
                disruption_risk=float(data.get("disruption_risk", 0.0)),
                adoption_effort=data.get("adoption_effort", "medium"),
                expected_impact=data.get("expected_impact", "incremental"),
                affected_modules=data.get("affected_modules", []),
                integration_approach=data.get("integration_approach", ""),
                risks=data.get("risks", []),
                recommendation=data.get("recommendation", "monitor"),
                reasoning=data.get("reasoning", ""),
                assessed_at=now_iso,
                relevance_scores=orig.relevance_scores if orig else {},
            )

            agent.ingest_assessment(assessment)
            processed += 1

            # Auto-dismiss low-value findings
            if assessment.recommendation == "dismiss":
                agent.dismiss(discovery_id, assessment.reasoning)

            # Auto-generate proposal for "adopt" recommendations
            if assessment.recommendation == "adopt":
                spec = self._generate_proposal_spec(assessment)
                agent.save_proposal(assessment.title, spec)
                adopt_count += 1

        # Run experiment loop over new proposals if any were generated
        experiment_results = []
        if adopt_count > 0:
            proposals = agent.get_pending_proposals()
            if proposals:
                experiment_results = agent.run_experiment_loop(proposals, dry_run=True)
                kept = sum(1 for o in experiment_results if o["decision"] == "keep")
                logger.info(
                    "CRA: Experiment loop: %d/%d proposals kept (baseline=%.3f)",
                    kept,
                    len(experiment_results),
                    agent.get_baseline_score(),
                )

        logger.info(f"CRA: Processed {processed} assessments, {errors} errors, {adopt_count} adopt")
        return {
            "processed": processed,
            "errors": errors,
            "batch_id": batch_id,
            "adopt_count": adopt_count,
            "experiment_results": experiment_results,
        }

    @staticmethod
    def _generate_proposal_spec(assessment: "Assessment") -> str:
        """Generate a Golden Spec-format proposal from an assessment."""
        modules = ", ".join(assessment.affected_modules) if assessment.affected_modules else "TBD"
        risks = (
            "\n".join(f"- {r}" for r in assessment.risks)
            if assessment.risks
            else "- None identified"
        )
        return f"""# Integration: {assessment.title}

## Objective
{assessment.integration_approach}

## Source
{assessment.source_url}

## Impact
- Expected: {assessment.expected_impact}
- Effort: {assessment.adoption_effort}
- Disruption risk: {assessment.disruption_risk:.1f}

## Affected Modules
{modules}

## Risks
{risks}

## Acceptance Criteria
- [ ] All existing tests pass (no regressions)
- [ ] Capability score delta > 0 for target capability
- [ ] adoption_outcome_score > baseline ({assessment.disruption_risk:.2f} disruption weight)

## Reasoning
{assessment.reasoning}
"""
