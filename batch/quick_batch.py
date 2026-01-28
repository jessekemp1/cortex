#!/usr/bin/env python3
"""
Quick Batch Submission Helper

Simple, one-command batch submissions for common work patterns.
Goal: Make batch API usage as easy as possible to increase adoption.

Usage:
    python quick_batch.py review path/to/file.py
    python quick_batch.py docs VortexV2/
    python quick_batch.py research "Should we use Redis?"
    python quick_batch.py security
    python quick_batch.py patterns
    python quick_batch.py test-gaps cortex/
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add batch module to path
sys.path.insert(0, str(Path(__file__).parent))

from batch_scheduler import BatchScheduler

# Common prompt templates for different batch types
TEMPLATES = {
    "review": """Review the following code for:
1. Security vulnerabilities (injection, auth issues, data exposure)
2. Performance issues (N+1 queries, inefficient algorithms, missing caching)
3. Correctness (edge cases, error handling, race conditions)
4. Maintainability (code clarity, naming, documentation)
5. Best practices (Python conventions, typing, testing)

Files to review:
{files}

{context}

Provide specific, actionable feedback with file:line references.""",

    "docs": """Generate comprehensive documentation for:

{files}

Include:
1. Module/function docstrings
2. API reference if applicable
3. Usage examples
4. Architecture notes
5. Dependencies and integration points

Format as markdown suitable for project documentation.""",

    "research": """Research question: {topic}

Please provide:
1. Overview - 2-3 sentence summary
2. Key Findings - 3-5 main points
3. Pros and Cons - balanced analysis
4. Recommendations - specific, actionable advice
5. References - key sources or documentation
6. Next Steps - what to do with this information

Focus on practical applicability to development work.""",

    "security": """Perform comprehensive security audit across active projects:

1. Dependency vulnerabilities - check for known CVEs
2. Secret exposure - hardcoded keys, credentials in code
3. Input validation - SQL injection, XSS, path traversal
4. Authentication/Authorization - session handling, access control
5. API security - rate limiting, input sanitization
6. Cryptography - weak algorithms, key management
7. Error handling - information leakage in errors

Provide specific findings with severity ratings (Critical/High/Medium/Low).""",

    "patterns": """Analyze codebase for:

1. Anti-patterns - code smells, complexity issues, circular imports
2. Duplication - similar code across files, copy-paste patterns
3. Architecture issues - coupling, cohesion, separation of concerns
4. Type safety - missing type hints, incorrect annotations
5. Error handling patterns - inconsistent approaches
6. Testing gaps - untested critical paths

Provide specific examples with file:line references and improvement suggestions.""",

    "test-gaps": """Analyze test coverage for:

{files}

Identify:
1. Missing unit tests - functions/methods without tests
2. Missing edge cases - boundary conditions, error paths
3. Missing integration tests - cross-module interactions
4. Missing regression tests - for known bugs/issues
5. Test quality issues - weak assertions, missing mocks

Prioritize by risk (Critical paths first) and provide test case suggestions.""",
}


def get_file_content(file_path: Path, max_lines: int = 500) -> str:
    """Read file content, truncating if too large."""
    if not file_path.exists():
        return f"(File not found: {file_path})"

    try:
        lines = file_path.read_text().split('\n')
        if len(lines) > max_lines:
            return '\n'.join(lines[:max_lines]) + f"\n\n... (truncated, {len(lines)} lines total)"
        return file_path.read_text()
    except Exception as e:
        return f"(Error reading file: {e})"


def collect_files(path: str, extensions: tuple = ('.py', '.js', '.ts', '.tsx')) -> list:
    """Collect relevant source files from path."""
    target = Path(path)

    if target.is_file():
        return [target]

    if target.is_dir():
        files = []
        for ext in extensions:
            files.extend(target.rglob(f'*{ext}'))
        # Filter out venv, node_modules, etc.
        files = [f for f in files if not any(
            skip in str(f) for skip in ['venv/', 'node_modules/', '__pycache__/', '.git/']
        )]
        return sorted(files)[:20]  # Limit to 20 files

    return []


def submit_batch(
    batch_type: str,
    target: Optional[str] = None,
    context: str = "",
    priority: str = "normal",
    deadline_hours: int = 24
) -> dict:
    """
    Submit a batch job using templates.

    Args:
        batch_type: Type of batch (review, docs, research, security, patterns, test-gaps)
        target: File path or topic (depends on batch_type)
        context: Additional context
        priority: normal, high, low
        deadline_hours: Hours until results needed

    Returns:
        dict with submission details
    """
    scheduler = BatchScheduler()

    # Build prompt from template
    template = TEMPLATES.get(batch_type)
    if not template:
        raise ValueError(f"Unknown batch type: {batch_type}. Available: {list(TEMPLATES.keys())}")

    # Process based on type
    if batch_type in ["review", "docs", "test-gaps"]:
        if not target:
            raise ValueError(f"Batch type '{batch_type}' requires a file or directory path")

        files = collect_files(target)
        if not files:
            raise ValueError(f"No source files found at: {target}")

        # Build file list with content (for smaller sets)
        if len(files) <= 5:
            file_content = []
            for f in files:
                content = get_file_content(f)
                file_content.append(f"### {f}\n```\n{content}\n```")
            files_text = "\n\n".join(file_content)
        else:
            files_text = "Files:\n" + "\n".join(f"- {f}" for f in files)

        prompt = template.format(files=files_text, context=context)
        title = f"{batch_type.title()} - {target}"

    elif batch_type == "research":
        if not target:
            raise ValueError("Research batch requires a topic/question")

        prompt = template.format(topic=target)
        title = f"Research: {target[:50]}..."

    elif batch_type in ["security", "patterns"]:
        # Whole-codebase analysis
        prompt = template
        title = f"{batch_type.title()} Audit"

    else:
        raise ValueError(f"Unknown batch type: {batch_type}")

    # Add context if provided
    if context:
        prompt += f"\n\nAdditional context:\n{context}"

    # Schedule the task
    task = scheduler.schedule_task(
        title=title,
        description=f"{batch_type.title()} batch job",
        prompt=prompt,
        priority=priority,
        deadline_hours=deadline_hours,
    )

    return {
        "success": True,
        "task_id": task.id,
        "title": task.title,
        "priority": priority,
        "estimated_tokens": task.estimated_input_tokens + task.estimated_output_tokens,
        "submit_after": task.submit_after.strftime("%Y-%m-%d %I:%M %p") if task.submit_after else "Now",
        "deadline": task.deadline.strftime("%Y-%m-%d %I:%M %p") if task.deadline else "None",
        "cost_savings": "50% vs real-time",
    }


def show_pending():
    """Show pending batch jobs."""
    scheduler = BatchScheduler()
    pending = scheduler.get_pending_tasks()
    submitted = scheduler.get_submitted_tasks()

    print("\n" + "=" * 60)
    print("BATCH JOB QUEUE STATUS")
    print("=" * 60)

    if pending:
        print(f"\n📋 PENDING ({len(pending)} jobs)")
        print("-" * 40)
        for task in pending:
            submit_time = task.submit_after.strftime("%I:%M %p") if task.submit_after else "Now"
            print(f"  [{task.priority.upper():6}] {task.title[:45]}")
            print(f"           Submit: {submit_time} | Tokens: ~{task.estimated_input_tokens:,}")

    if submitted:
        print(f"\n⚙️  PROCESSING ({len(submitted)} jobs)")
        print("-" * 40)
        for task in submitted:
            print(f"  [{task.batch_id[:15]}...] {task.title[:40]}")

    if not pending and not submitted:
        print("\n  No pending or processing jobs.")
        print("  Use: quick_batch.py <type> [args] to submit work")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Quick Batch Submission - Submit work to Anthropic Batch API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s review src/api.py          # Review a file
  %(prog)s review src/                # Review a directory
  %(prog)s docs cortex/batch/         # Generate documentation
  %(prog)s research "Redis vs Memcached for caching"
  %(prog)s security                   # Security audit
  %(prog)s patterns                   # Code pattern analysis
  %(prog)s test-gaps cortex/tests/    # Find test gaps
  %(prog)s status                     # Show pending jobs
        """
    )

    parser.add_argument(
        "type",
        choices=["review", "docs", "research", "security", "patterns", "test-gaps", "status"],
        help="Type of batch job"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="File/directory path or research topic"
    )
    parser.add_argument(
        "--context", "-c",
        default="",
        help="Additional context for the job"
    )
    parser.add_argument(
        "--priority", "-p",
        choices=["low", "normal", "high"],
        default="normal",
        help="Job priority (default: normal)"
    )
    parser.add_argument(
        "--deadline", "-d",
        type=int,
        default=24,
        help="Hours until results needed (default: 24)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    args = parser.parse_args()

    if args.type == "status":
        show_pending()
        return

    try:
        result = submit_batch(
            batch_type=args.type,
            target=args.target,
            context=args.context,
            priority=args.priority,
            deadline_hours=args.deadline,
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print()
            print("=" * 50)
            print("  BATCH JOB SUBMITTED")
            print("=" * 50)
            print(f"  Task ID:    {result['task_id']}")
            print(f"  Title:      {result['title']}")
            print(f"  Priority:   {result['priority']}")
            print(f"  Tokens:     ~{result['estimated_tokens']:,}")
            print(f"  Submit:     {result['submit_after']}")
            print(f"  Deadline:   {result['deadline']}")
            print(f"  Savings:    {result['cost_savings']}")
            print("=" * 50)
            print()
            print("  Check status:  python quick_batch.py status")
            print("  Or run:        /batch-status")
            print()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
