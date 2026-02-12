"""
Batch API Scheduler for Cortex

Schedule work to run via Batch API (50% cost savings) instead of real-time.
Optimizes for token limits and usage constraints based on Claude Usage Optimization insights.

Key Features:
- Break large tasks into batch-sized chunks (within token limits)
- Schedule batch submissions via local-orchestrator
- Track usage: real-time vs batch
- Optimize for overnight/off-peak processing
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from batch_api_client import BatchAPIClient, BatchRequest


@dataclass
class TokenBudget:
    """Token budget constraints for batch planning"""

    # Claude API Limits
    max_input_tokens: int = 100_000  # Max input per request
    max_output_tokens: int = 8_000  # Max output per request

    # Usage Constraints (from optimization guide)
    weekly_hour_limit: float = 60.0  # Hours per week
    daily_hour_target: float = 8.6  # Sustainable hours per day

    # Batch API specific
    batch_size_limit: int = 50_000  # Recommended batch chunk size

    # Cost optimization
    batch_discount: float = 0.50  # 50% savings vs real-time

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token"""
        return len(text) // 4

    def can_fit_in_batch(self, text: str) -> bool:
        """Check if text fits in a single batch request"""
        tokens = self.estimate_tokens(text)
        return tokens <= self.max_input_tokens

    def split_into_chunks(self, text: str, chunk_size: int = None) -> List[str]:
        """Split text into batch-sized chunks"""
        if chunk_size is None:
            chunk_size = self.batch_size_limit

        tokens = self.estimate_tokens(text)
        if tokens <= chunk_size:
            return [text]

        # Split by paragraphs to maintain context
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)

            if current_tokens + para_tokens > chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks


@dataclass
class BatchTask:
    """A task to be processed via Batch API"""

    id: str
    title: str
    description: str
    prompt: str  # The actual prompt for Claude
    priority: str = "normal"  # normal, high, low

    # Token estimates
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    # Scheduling
    submit_after: Optional[datetime] = None  # Don't submit before this time
    deadline: Optional[datetime] = None  # Results needed by this time

    # Batch API
    batch_id: Optional[str] = None
    status: str = "pending"  # pending, submitted, processing, completed, failed

    # Results
    result: Optional[str] = None
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BatchScheduler:
    """
    Schedules and manages Batch API work for Cortex.

    Optimizes for:
    - Token budget constraints
    - 50% cost savings vs real-time
    - Off-peak processing (overnight)
    - Usage limit compliance
    """

    def __init__(self, storage_path: Path = None, budget: TokenBudget = None):
        if storage_path is None:
            storage_path = Path.home() / ".cortex" / "batch_schedule"

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.budget = budget or TokenBudget()
        self.batch_client = BatchAPIClient()

        # Load existing tasks
        self.tasks: List[BatchTask] = self._load_tasks()

    def _load_tasks(self) -> List[BatchTask]:
        """Load tasks from storage"""
        tasks_file = self.storage_path / "tasks.json"

        if not tasks_file.exists():
            return []

        with open(tasks_file) as f:
            data = json.load(f)

        # Convert to BatchTask objects
        tasks = []
        for task_data in data:
            # Convert datetime strings back to datetime objects
            for field in [
                "submit_after",
                "deadline",
                "created_at",
                "submitted_at",
                "completed_at",
            ]:
                if task_data.get(field):
                    task_data[field] = datetime.fromisoformat(task_data[field])

            tasks.append(BatchTask(**task_data))

        return tasks

    def _save_tasks(self):
        """Save tasks to storage"""
        tasks_file = self.storage_path / "tasks.json"

        # Convert to JSON-serializable format
        data = []
        for task in self.tasks:
            task_dict = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "prompt": task.prompt,
                "priority": task.priority,
                "estimated_input_tokens": task.estimated_input_tokens,
                "estimated_output_tokens": task.estimated_output_tokens,
                "submit_after": (task.submit_after.isoformat() if task.submit_after else None),
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "batch_id": task.batch_id,
                "status": task.status,
                "result": task.result,
                "actual_input_tokens": task.actual_input_tokens,
                "actual_output_tokens": task.actual_output_tokens,
                "created_at": task.created_at.isoformat(),
                "submitted_at": (task.submitted_at.isoformat() if task.submitted_at else None),
                "completed_at": (task.completed_at.isoformat() if task.completed_at else None),
            }
            data.append(task_dict)

        with open(tasks_file, "w") as f:
            json.dump(data, f, indent=2)

    def schedule_task(
        self,
        title: str,
        description: str,
        prompt: str,
        priority: str = "normal",
        deadline_hours: int = 48,  # Default: results in 48 hours
    ) -> BatchTask:
        """
        Schedule a task for Batch API processing.

        Args:
            title: Task title
            description: Task description
            prompt: The actual prompt for Claude
            priority: normal, high, low
            deadline_hours: Hours until results needed (default 48)

        Returns:
            BatchTask object
        """
        # Estimate tokens
        estimated_input = self.budget.estimate_tokens(prompt)
        # For analysis/planning tasks, use generous output limit
        # Most analysis tasks need 2000-4000 tokens
        estimated_output = 4000

        # Calculate scheduling times
        now = datetime.now()

        # Submit after 6 PM (off-peak) or immediately if high priority
        if priority == "high":
            submit_after = now
        else:
            # Schedule for 6 PM today or tomorrow
            today_6pm = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if now < today_6pm:
                submit_after = today_6pm
            else:
                submit_after = today_6pm + timedelta(days=1)

        # Deadline
        deadline = now + timedelta(hours=deadline_hours)

        # Create task
        task = BatchTask(
            id=f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            title=title,
            description=description,
            prompt=prompt,
            priority=priority,
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            submit_after=submit_after,
            deadline=deadline,
        )

        self.tasks.append(task)
        self._save_tasks()

        return task

    def submit_ready_tasks(self) -> List[BatchTask]:
        """
        Submit tasks that are ready (past submit_after time).

        Returns:
            List of submitted tasks
        """
        now = datetime.now()
        submitted = []

        for task in self.tasks:
            if task.status == "pending" and task.submit_after and now >= task.submit_after:

                try:
                    # Create batch request with proper message format
                    batch_request = BatchRequest(
                        custom_id=task.id,
                        params={
                            "messages": [{"role": "user", "content": task.prompt}],
                            "max_tokens": task.estimated_output_tokens,
                        },
                    )

                    # Submit to Batch API
                    batch_id = self.batch_client.submit_batch(
                        requests=[batch_request],
                        description=f"Batch task: {task.title}",
                    )

                    task.batch_id = batch_id
                    task.status = "submitted"
                    task.submitted_at = now

                    submitted.append(task)

                except Exception as e:
                    task.status = "failed"
                    task.result = f"Submission failed: {str(e)}"

        if submitted:
            self._save_tasks()

        return submitted

    def check_completed_tasks(self) -> List[BatchTask]:
        """
        Check for completed batch tasks and retrieve results.

        Returns:
            List of newly completed tasks
        """
        completed = []

        for task in self.tasks:
            if task.status == "submitted" and task.batch_id:
                try:
                    # Check batch status
                    status_data = self.batch_client.get_batch_status(task.batch_id)

                    if status_data.get("status") == "ended":
                        # Retrieve results
                        results = self.batch_client._retrieve_batch_results(task.batch_id)

                        # Extract result text from first (and only) result
                        if results and len(results) > 0:
                            batch_result = results[0]

                            if batch_result.status == "succeeded":
                                # Extract message content
                                result_msg = batch_result.result.get("message", {})
                                content_blocks = result_msg.get("content", [])
                                if content_blocks:
                                    task.result = content_blocks[0].get("text", "")

                                # Extract usage
                                usage = result_msg.get("usage", {})
                                task.actual_input_tokens = usage.get("input_tokens", 0)
                                task.actual_output_tokens = usage.get("output_tokens", 0)

                                task.status = "completed"
                            else:
                                # Request errored or expired
                                error_info = batch_result.result.get("error", {})
                                task.status = "failed"
                                task.result = f"Batch request {batch_result.status}: {error_info.get('message', 'Unknown error')}"
                        else:
                            task.status = "failed"
                            task.result = "No results returned from batch"

                        task.completed_at = datetime.now()
                        completed.append(task)

                except Exception:
                    # Don't mark as failed yet, might be temporary network issue
                    pass

        if completed:
            self._save_tasks()

        return completed

    def get_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get usage statistics for batch vs real-time.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with usage stats
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_tasks = [t for t in self.tasks if t.created_at >= cutoff and t.status == "completed"]

        total_input = sum(t.actual_input_tokens for t in recent_tasks)
        total_output = sum(t.actual_output_tokens for t in recent_tasks)
        total_tokens = total_input + total_output

        # Estimate cost savings (50% discount)
        # Rough cost: $15/million input tokens, $75/million output tokens (Opus pricing)
        real_time_cost = (total_input / 1_000_000 * 15) + (total_output / 1_000_000 * 75)
        batch_cost = real_time_cost * 0.5
        savings = real_time_cost - batch_cost

        return {
            "days_analyzed": days,
            "tasks_completed": len(recent_tasks),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "estimated_real_time_cost": round(real_time_cost, 2),
            "estimated_batch_cost": round(batch_cost, 2),
            "estimated_savings": round(savings, 2),
            "savings_percentage": 50.0,
        }

    def get_pending_tasks(self) -> List[BatchTask]:
        """Get tasks pending submission"""
        return [t for t in self.tasks if t.status == "pending"]

    def get_submitted_tasks(self) -> List[BatchTask]:
        """Get tasks currently processing"""
        return [t for t in self.tasks if t.status == "submitted"]

    def get_completed_tasks(self, days: int = 7) -> List[BatchTask]:
        """Get recently completed tasks"""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            t
            for t in self.tasks
            if t.status == "completed" and t.completed_at and t.completed_at >= cutoff
        ]


def create_batch_plan_from_cortex_plan(plan_id: str, scheduler: BatchScheduler) -> List[BatchTask]:
    """
    Convert a Cortex Layer 5 plan into Batch API tasks.

    Args:
        plan_id: Cortex plan ID (e.g., "cortex-enhancements-2025")
        scheduler: BatchScheduler instance

    Returns:
        List of created BatchTask objects
    """
    from intelligence.planning import PlanExecutor

    executor = PlanExecutor()
    plan = executor.load_plan(plan_id)

    batch_tasks = []

    for step in plan.steps:
        # Create a prompt for each step
        prompt = f"""Analyze and create an implementation guide for this task:

**Title:** {step.title}

**Description:** {step.description}

**Files to modify:** {', '.join(step.files) if step.files else 'TBD'}

**Estimated time:** {step.estimated_time} minutes

**Validation criteria:** {step.validation if hasattr(step, 'validation') else 'TBD'}

Please provide:
1. Detailed implementation steps
2. Code structure and key functions needed
3. Potential challenges and solutions
4. Testing approach
5. Integration points with existing code

Focus on being thorough and actionable. This will guide interactive implementation."""

        # Schedule as batch task
        batch_task = scheduler.schedule_task(
            title=f"{plan.title} - {step.title}",
            description=step.description,
            prompt=prompt,
            priority="normal",
            deadline_hours=48,
        )

        batch_tasks.append(batch_task)

    return batch_tasks
