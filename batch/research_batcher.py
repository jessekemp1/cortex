#!/usr/bin/env python3
"""
Research Queue Batch Processor

Submits research requests as a single batch to Claude API,
then polls for and processes results.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

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
            batch_requests,
            description=f"Research batch: {len(research_items)} items"
        )
        logger.info(f"Submitted batch {batch_id}")

        # Step 3: Poll for results
        results = self.batch_client.poll_results(batch_id)
        logger.info(f"Batch {batch_id} completed with {len(results)} results")

        # Step 4: Process results
        processed_results = {}
        for result in results:
            item_id = result.custom_id
            processed_result = self._process_result(item_id, result)
            processed_results[item_id] = processed_result

        return {
            "batch_id": batch_id,
            "submitted_count": len(research_items),
            "completed_count": len(results),
            "results": processed_results
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
                topic=topic,
                context=context,
                priority=priority
            )

            # Create batch request
            request = BatchRequest(
                custom_id=item_id,
                params={
                    "messages": [
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    "system": self.RESEARCH_SYSTEM_PROMPT
                }
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
                "completed_at": datetime.now().isoformat()
            }

        elif result.status == "errored":
            error = result.result.get("error", {})
            error_msg = error.get("message", "Unknown error")

            logger.error(f"Research item {item_id} failed: {error_msg}")

            return {
                "id": item_id,
                "status": "error",
                "error": error_msg,
                "completed_at": datetime.now().isoformat()
            }

        else:
            logger.warning(f"Research item {item_id} has unknown status: {result.status}")

            return {
                "id": item_id,
                "status": "unknown",
                "status_code": result.status,
                "completed_at": datetime.now().isoformat()
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
            with open(queue_file, 'r') as f:
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

            with open(queue_file, 'w') as f:
                json.dump(queue_data, f, indent=2)

            logger.info(f"Updated queue file: {len(completed)} items completed")

        except Exception as e:
            logger.error(f"Error updating queue file: {e}")
