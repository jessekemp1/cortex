#!/usr/bin/env python3
"""
Intelligent Batch Orchestrator - Anthropic API Version

Submits overnight analysis jobs to Anthropic Batch API (not local queue).
This is the CORRECT version for Claude-powered analysis (security, quality, etc.)

Key Differences from intelligent_orchestrator.py:
- Submits to: Anthropic Batch API (cloud)
- Uses: BatchAPIClient.submit_batch()
- Returns: Claude analysis results
- Purpose: Deep code analysis overnight

Usage:
    python batch/intelligent_orchestrator_anthropic.py              # Submit jobs
    python batch/intelligent_orchestrator_anthropic.py --dry-run    # Preview only
    python batch/intelligent_orchestrator_anthropic.py --max-jobs 3 # Limit to 3
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch.batch_api_client import BatchAPIClient, BatchRequest

try:
    from cortex.conductor.batch_models import ConductorBatchModels
except ImportError:
    from batch.model_policy import AnthropicBatchModels as ConductorBatchModels  # type: ignore[assignment]


@dataclass
class BatchCapacity:
    """Batch API capacity limits and calculations"""

    # Batch API limits (per Claude API docs)
    max_input_tokens_per_request: int = 100_000
    max_output_tokens_per_request: int = 8_000
    max_concurrent_batches: int = 5

    # Overnight window
    overnight_start_hour: int = 22  # 10 PM
    overnight_end_hour: int = 6  # 6 AM
    overnight_hours: int = 8

    # Token budget constraints
    weekly_token_budget: int = 60 * 60 * 15_000  # 60 hours @ 15K tokens/hour
    current_weekly_usage: int = 0

    def available_overnight_tokens(self) -> int:
        """Calculate available tokens for overnight batch processing"""
        # Conservative: use 40% of weekly budget for overnight batches
        overnight_allocation = self.weekly_token_budget * 0.40
        remaining = overnight_allocation - self.current_weekly_usage
        return max(0, int(remaining))

    def max_jobs_by_tokens(self, avg_tokens_per_job: int = 50_000) -> int:
        """Calculate max jobs that fit in overnight token budget"""
        available = self.available_overnight_tokens()
        return available // avg_tokens_per_job

    def max_jobs_by_time(self, avg_hours_per_job: float = 0.5) -> int:
        """Calculate max jobs that fit in overnight time window"""
        # Batch jobs complete within 24h, but we want results by morning
        # Conservative: assume 2 hours for processing
        processing_window = self.overnight_hours - 2
        return int(processing_window / avg_hours_per_job)


@dataclass
class AnalysisJob:
    """A Claude analysis job for batch submission"""

    id: str
    title: str
    description: str
    system_prompt: str
    user_prompt: str
    priority: str  # "immediate", "high", "normal", "low"
    estimated_input_tokens: int
    estimated_output_tokens: int
    source: str  # "goal", "pattern", "security", "docs", "research"
    project: Optional[str] = None
    files: List[str] = field(default_factory=list)
    deadline_hours: int = 12

    @property
    def total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens

    @property
    def priority_score(self) -> int:
        """Numeric priority for sorting (higher = more important)"""
        scores = {"immediate": 100, "high": 75, "normal": 50, "low": 25}
        return scores.get(self.priority, 0)


class IntelligentBatchOrchestratorAnthropic:
    """
    Orchestrates batch job creation via Anthropic Batch API.
    Generates optimal overnight batch queue for Claude analysis.
    """

    def __init__(self, root_dir: str = "/Users/jesse.kemp/Dev"):
        self.root_dir = Path(root_dir)
        self.cortex_dir = self.root_dir / "cortex"
        self.capacity = BatchCapacity()
        self.work_items: List[AnalysisJob] = []

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        self.batch_client = BatchAPIClient(api_key=api_key)
        self.model_policy = ConductorBatchModels()

    def analyze_cortex_state(self) -> Dict[str, Any]:
        """Get current Cortex state (goals, projects, blockers)"""
        try:
            result = subprocess.run(
                ["python", str(self.cortex_dir / "cli.py"), "status"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse output for key metrics
            output = result.stdout
            state = {
                "active_projects": self._extract_metric(output, "Active"),
                "priority_a_goals": self._extract_metric(output, "Priority A"),
                "priority_b_goals": self._extract_metric(output, "Priority B"),
                "pending_goals": self._extract_metric(output, "pending"),
            }
            return state
        except Exception as e:
            print(f"Warning: Failed to get Cortex state: {e}", file=sys.stderr)
            # Use reasonable defaults
            return {
                "active_projects": 3,  # cortex, alpha_arena, vortex-backend
                "priority_a_goals": 0,
                "priority_b_goals": 0,
                "pending_goals": 0,
            }

    def _extract_metric(self, text: str, pattern: str) -> int:
        """Extract numeric metric from status output"""
        for line in text.split("\n"):
            if pattern in line:
                # Extract first number from line
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers:
                    return numbers[0]
        return 0

    def _build_codebase_context(self, projects: List[str]) -> str:
        """Build context about the codebase for Claude"""
        context_parts = []

        for project in projects:
            project_path = self.root_dir / project
            if not project_path.exists():
                continue

            # Get basic project info
            readme_path = project_path / "README.md"
            if readme_path.exists():
                context_parts.append(f"\n## {project}/README.md\n")
                # Read first 500 lines
                try:
                    content = readme_path.read_text()[:2000]
                    context_parts.append(content)
                except:
                    pass

        return "\n".join(context_parts) if context_parts else "No project context available."

    def generate_analysis_jobs(self) -> List[AnalysisJob]:
        """Generate Claude analysis jobs from Cortex intelligence"""
        jobs = []
        state = self.analyze_cortex_state()
        active_projects = state.get("active_projects", 3)

        # Build context once for reuse
        projects = ["cortex", "alpha_arena", "Vortex/backend"]
        codebase_context = self._build_codebase_context(projects)

        # 1. Security Scan (IMMEDIATE)
        jobs.append(
            AnalysisJob(
                id="security-scan",
                title="Overnight Security Audit",
                description="Comprehensive security scan across all active projects",
                system_prompt="""You are a security expert conducting a comprehensive code audit.
Focus on identifying real vulnerabilities, not theoretical ones.
Prioritize findings by severity: Critical > High > Medium > Low.""",
                user_prompt=f"""Perform a comprehensive security audit across {active_projects} active projects.

Check for SQL injection, XSS, exposed credentials, insecure dependencies, missing input validation, and path traversal vulnerabilities.

For each finding, provide: severity level, file/line, code snippet, exploit scenario, and recommended fix.

Context: {codebase_context[:3000]}""",
                priority="immediate",
                estimated_input_tokens=20_000,
                estimated_output_tokens=4_000,
                source="security",
                deadline_hours=8,
            )
        )

        # 2. Code Quality Analysis (HIGH)
        jobs.append(
            AnalysisJob(
                id="code-quality-scan",
                title="Code Quality Analysis",
                description="Analyze complexity, duplication, and anti-patterns",
                system_prompt="""You are a senior software engineer conducting a code quality review.
Focus on maintainability issues that will cause problems as the codebase grows.
Be specific with file names and line numbers. Prioritize by impact on velocity.""",
                user_prompt=f"""Analyze code quality across {active_projects} projects (cortex, alpha_arena, vortex-backend).

Identify:
1. **High complexity functions** (>50 lines, >10 branches, deeply nested)
   - Function name, file:line
   - Complexity metrics (lines, cyclomatic complexity)
   - Why it's hard to maintain
   - Refactoring approach

2. **Code duplication** (similar logic in multiple places >10 lines)
   - Duplicated code blocks
   - Files involved
   - Refactoring into shared utility

3. **Anti-patterns**
   - Circular imports
   - God classes (>500 lines, >20 methods)
   - Missing error handling (bare except, no logging)
   - Magic numbers (hardcoded values without constants)

4. **Tech debt markers** (TODO, FIXME, HACK comments)
   - Count by project
   - Most critical to address

For each finding: file:line, code snippet, impact, refactoring suggestion.

Context: {codebase_context[:3000]}""",
                priority="high",
                estimated_input_tokens=40_000,
                estimated_output_tokens=6_000,
                source="pattern",
                deadline_hours=12,
            )
        )

        # 3. Test Coverage Gap Analysis (HIGH)
        jobs.append(
            AnalysisJob(
                id="test-coverage-analysis",
                title="Test Coverage Gap Analysis",
                description="Identify untested critical paths and missing test cases",
                system_prompt="""You are a QA engineer analyzing test coverage.
Focus on high-risk code that lacks tests, not achieving 100% coverage.
Prioritize by business impact and failure risk.""",
                user_prompt=f"""Analyze test coverage across {active_projects} projects.

Identify:
1. **Critical paths without tests**
   - Core business logic (trading, forecasting, analysis)
   - Data persistence (save/load/update)
   - File:function with no tests
   - Risk level and why

2. **Edge cases not covered**
   - Boundary conditions (empty lists, max values, None)
   - Error conditions (network failures, invalid input)
   - Needed test cases

3. **Integration test gaps**
   - Components that interact but aren't tested together
   - API endpoints without integration tests
   - Database operations without transaction tests

4. **Missing error scenario tests**
   - Exception handling without tests
   - Retry logic without failure simulation
   - Timeout handling without tests

For each gap: file:function, untested scenario, risk level (High/Medium/Low), suggested test outline.

Focus on tests that would catch real bugs.

Context: {codebase_context[:3000]}""",
                priority="high",
                estimated_input_tokens=35_000,
                estimated_output_tokens=5_000,
                source="pattern",
                deadline_hours=12,
            )
        )

        # 4. Documentation Completeness (NORMAL)
        jobs.append(
            AnalysisJob(
                id="docs-completeness",
                title="Documentation Completeness Audit",
                description="Identify missing or outdated documentation",
                system_prompt="""You are a technical writer auditing documentation.
Focus on documentation that users and developers actually need.
Distinguish between "nice-to-have" and "must-have" docs.""",
                user_prompt=f"""Audit documentation across {active_projects} projects.

Check:
1. **README completeness**
   - Missing setup/installation instructions
   - No usage examples
   - Outdated dependencies or commands
   - Missing troubleshooting section

2. **API documentation**
   - Undocumented endpoints (FastAPI routes without docstrings)
   - Missing parameter descriptions
   - No request/response examples
   - Missing error response codes

3. **Public function docstrings**
   - Functions without docstrings (in __init__.py, public APIs)
   - Docstrings missing parameter types
   - No return value documentation
   - Missing usage examples for complex functions

4. **Architecture documentation**
   - No system design docs
   - Missing data flow diagrams
   - Undocumented design decisions

For each gap: file:location, what's missing, priority (Critical/High/Medium/Low), suggested outline.

Focus on docs that reduce onboarding time and prevent mistakes.

Context: {codebase_context[:3000]}""",
                priority="normal",
                estimated_input_tokens=25_000,
                estimated_output_tokens=4_000,
                source="docs",
                deadline_hours=24,
            )
        )

        # 5. Dependency Audit (NORMAL)
        jobs.append(
            AnalysisJob(
                id="dependency-audit",
                title="Dependency Version Audit",
                description="Check outdated packages, CVEs, conflicts, unused deps",
                system_prompt="""You are a DevOps engineer auditing dependencies.
Focus on security vulnerabilities and compatibility issues.
Prioritize updates by risk level.""",
                user_prompt=f"""Audit dependencies across {active_projects} projects.

Check:
1. **Outdated packages** (requirements.txt, package.json)
   - Current version vs latest stable
   - Breaking changes in update
   - Security fixes included

2. **Security vulnerabilities**
   - Known CVEs in current versions
   - Severity level (Critical/High/Medium/Low)
   - Available patched version
   - Exploit scenario

3. **Version conflicts**
   - Incompatible version ranges
   - Transitive dependency issues
   - Python version compatibility

4. **Unused dependencies**
   - Packages in requirements.txt not imported
   - Orphaned dependencies after refactoring

For each finding: package name, current version, issue, risk level, recommended action.

Focus on security risks and blocking issues, not just "being on latest".

Context: {codebase_context[:3000]}""",
                priority="normal",
                estimated_input_tokens=20_000,
                estimated_output_tokens=3_000,
                source="security",
                deadline_hours=24,
            )
        )

        # 6. Performance Bottleneck Detection (NORMAL)
        jobs.append(
            AnalysisJob(
                id="performance-analysis",
                title="Performance Bottleneck Detection",
                description="Identify N+1 queries, inefficient algorithms, missing caching",
                system_prompt="""You are a performance engineer analyzing code efficiency.
Focus on actual bottlenecks that impact user experience.
Distinguish between micro-optimizations and real problems.""",
                user_prompt=f"""Analyze performance across {active_projects} projects.

Identify:
1. **N+1 query problems**
   - Queries in loops
   - Missing eager loading
   - File:line, data volume impact

2. **Missing indexes**
   - Database queries without indexes
   - Slow lookup patterns
   - Table/field names

3. **Inefficient algorithms**
   - O(n²) or worse complexity
   - Nested loops over large data
   - File:function, better algorithm

4. **Blocking I/O**
   - Synchronous network calls in request handlers
   - File I/O without async
   - Database queries without connection pooling

5. **Missing caching**
   - Repeated expensive computations
   - Static data fetched repeatedly
   - Memoization opportunities

For each bottleneck: file:line, performance impact (latency estimate), user impact, optimization approach with code.

Focus on issues affecting actual users.

Context: {codebase_context[:3000]}""",
                priority="normal",
                estimated_input_tokens=30_000,
                estimated_output_tokens=4_000,
                source="pattern",
                deadline_hours=24,
            )
        )

        return jobs

    def prioritize_jobs(self, jobs: List[AnalysisJob]) -> List[AnalysisJob]:
        """Sort jobs by priority and token efficiency"""
        return sorted(jobs, key=lambda x: (-x.priority_score, x.total_tokens))

    def fill_overnight_queue(self, max_jobs: Optional[int] = None) -> List[AnalysisJob]:
        """Fill overnight batch queue to maximize capacity"""
        jobs = self.generate_analysis_jobs()
        prioritized = self.prioritize_jobs(jobs)

        if max_jobs is None:
            max_by_tokens = self.capacity.max_jobs_by_tokens()
            max_by_time = self.capacity.max_jobs_by_time()
            max_by_concurrent = self.capacity.max_concurrent_batches
            max_jobs = min(max_by_tokens, max_by_time, max_by_concurrent)

        selected_jobs = []
        total_tokens = 0

        for job in prioritized:
            if len(selected_jobs) >= max_jobs:
                break
            if total_tokens + job.total_tokens <= self.capacity.available_overnight_tokens():
                selected_jobs.append(job)
                total_tokens += job.total_tokens

        return selected_jobs

    def submit_batch_queue(
        self, dry_run: bool = False, max_jobs: Optional[int] = None
    ) -> Dict[str, Any]:
        """Submit overnight batch queue to Anthropic Batch API"""
        queue = self.fill_overnight_queue(max_jobs=max_jobs)

        summary = {
            "total_jobs": len(queue),
            "total_tokens": sum(j.total_tokens for j in queue),
            "by_priority": {
                "immediate": len([j for j in queue if j.priority == "immediate"]),
                "high": len([j for j in queue if j.priority == "high"]),
                "normal": len([j for j in queue if j.priority == "normal"]),
                "low": len([j for j in queue if j.priority == "low"]),
            },
            "jobs": [],
            "capacity": {
                "available_tokens": self.capacity.available_overnight_tokens(),
                "utilization_pct": (
                    (
                        sum(j.total_tokens for j in queue)
                        / self.capacity.available_overnight_tokens()
                        * 100
                    )
                    if self.capacity.available_overnight_tokens() > 0
                    else 0
                ),
            },
            "batch_id": None,
        }

        if not dry_run:
            batch_requests = []
            for job in queue:
                model = self.model_policy.get_model(job.source)
                request = BatchRequest(
                    custom_id=job.id,
                    params={
                        "model": model,
                        "max_tokens": job.estimated_output_tokens,
                        "system": job.system_prompt,
                        "messages": [{"role": "user", "content": job.user_prompt}],
                    },
                )
                batch_requests.append(request)
                summary["jobs"].append(
                    {
                        "id": job.id,
                        "title": job.title,
                        "priority": job.priority,
                        "tokens": job.total_tokens,
                        "source": job.source,
                        "model": model,
                    }
                )

            try:
                batch_id = self.batch_client.submit_batch(
                    requests=batch_requests,
                    description=f"Cortex Overnight Analysis - {datetime.now().strftime('%Y-%m-%d')}",
                )
                summary["batch_id"] = batch_id
                summary["submitted"] = True
                self._save_batch_tracking(batch_id, queue)
            except Exception as e:
                summary["submitted"] = False
                summary["error"] = str(e)
        else:
            for job in queue:
                summary["jobs"].append(
                    {
                        "id": job.id,
                        "title": job.title,
                        "priority": job.priority,
                        "tokens": job.total_tokens,
                        "source": job.source,
                        "submitted": "dry_run",
                    }
                )

        return summary

    def _save_batch_tracking(self, batch_id: str, jobs: List[AnalysisJob]):
        """Save batch tracking info for morning retrieval"""
        tracking_dir = Path.home() / ".cortex" / "batches"
        tracking_dir.mkdir(parents=True, exist_ok=True)

        tracking_file = tracking_dir / f"{batch_id}_jobs.json"
        tracking_data = {
            "batch_id": batch_id,
            "submitted_at": datetime.now().isoformat(),
            "job_count": len(jobs),
            "jobs": [
                {"id": job.id, "title": job.title, "priority": job.priority, "source": job.source}
                for job in jobs
            ],
        }
        tracking_file.write_text(json.dumps(tracking_data, indent=2))

    def print_summary(self, summary: Dict[str, Any]) -> None:
        """Pretty print submission summary"""
        print("╔══════════════════════════════════════════════════════╗")
        print("║   INTELLIGENT ORCHESTRATOR - ANTHROPIC API VERSION   ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()
        print(f"Total Jobs: {summary['total_jobs']}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print(f"Utilization: {summary['capacity']['utilization_pct']:.1f}%")
        if summary.get("batch_id"):
            print(f"\n✅ Batch ID: {summary['batch_id']}")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Batch Orchestrator (Anthropic API)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted")
    parser.add_argument("--max-jobs", type=int, help="Maximum jobs to queue")
    args = parser.parse_args()

    try:
        orchestrator = IntelligentBatchOrchestratorAnthropic()
        summary = orchestrator.submit_batch_queue(dry_run=args.dry_run, max_jobs=args.max_jobs)
        orchestrator.print_summary(summary)

        if args.dry_run:
            print("💡 This was a dry run. Remove --dry-run to actually submit.")
        elif summary.get("submitted"):
            print(
                f"✅ Submitted! Check status: python batch/check_batch_status.py {summary['batch_id']}"
            )
        else:
            print(f"❌ Failed: {summary.get('error')}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
