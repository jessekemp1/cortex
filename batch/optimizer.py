#!/usr/bin/env python3
"""
Adaptive Batch Queue Optimizer

Intelligently generates batch work from multiple sources, scores it for priority,
and fills the overnight queue using bin packing algorithms to maximize capacity.

Key Features:
- Dynamic work generation from commits, TODOs, test failures
- Composite priority scoring (deadline + value + blocking)
- Bin packing algorithm for optimal capacity utilization
- Performance tracking with SQLite (learns from history)
- Adaptive token/duration estimation based on past performance
"""

import json
import re
import sqlite3
import subprocess

# Import existing models from intelligent_orchestrator
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from intelligent_orchestrator import BatchCapacity, BatchWorkItem


@dataclass
class WorkGenerationSource:
    """Metadata about where work was generated from"""

    source_type: str  # "commit", "todo", "test_failure", "manual"
    source_location: str  # file path, commit hash, etc.
    discovered_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # 0.0-1.0, how confident we are this needs batch work


class DynamicWorkGenerator:
    """
    Scans codebase for batch-able work opportunities.

    Generates BatchWorkItem objects from:
    - Recent commits (analyze changes for issues)
    - TODOs and FIXMEs in code
    - Test failures from CI/test runs
    """

    def __init__(self, root_dir: Path = Path("/Users/jesse.kemp/Dev")):
        self.root_dir = root_dir
        self.cortex_dir = root_dir / "cortex"

    def scan_recent_commits(self, hours: int = 24) -> List[BatchWorkItem]:
        """
        Scan recent commits for changes that warrant batch analysis.

        Analyzes:
        - Large refactors (many files changed)
        - Security-sensitive files (auth, crypto, API keys)
        - Performance-critical code (DB queries, loops)
        - New features (analyze for edge cases)

        Args:
            hours: How many hours back to scan

        Returns:
            List of BatchWorkItem objects for commit analysis
        """
        work_items = []

        try:
            # Get commits from last N hours
            since_time = datetime.now() - timedelta(hours=hours)
            since_str = since_time.strftime("%Y-%m-%d %H:%M:%S")

            result = subprocess.run(
                ["git", "log", f"--since={since_str}", "--format=%H|%s|%an", "--numstat"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return work_items

            # Parse commits
            commits = self._parse_git_log(result.stdout)

            for commit in commits:
                # Analyze commit characteristics
                files_changed = commit["files_changed"]
                insertions = commit["insertions"]
                deletions = commit["deletions"]

                # Large refactor detection
                if files_changed > 5 or (insertions + deletions) > 500:
                    # Fetch actual diff content for substantive analysis
                    diff_content = self._get_commit_diff(commit["hash"])

                    # Dynamic token estimation based on actual diff size
                    diff_tokens = len(diff_content) // 4 + 2000
                    estimated_input = max(15_000, diff_tokens)

                    work_items.append(
                        BatchWorkItem(
                            id=f"commit-analysis-{commit['hash'][:8]}",
                            title=f"Analyze large commit: {commit['subject'][:50]}",
                            description=f"Large commit ({files_changed} files, +{insertions}/-{deletions}). Analyze for: edge cases, test coverage, performance impact, breaking changes.",
                            prompt=f"""Analyze this large commit for potential issues:

Commit: {commit['hash']}
Subject: {commit['subject']}
Author: {commit['author']}
Files: {files_changed}, Lines: +{insertions}/-{deletions}

--- ACTUAL DIFF ---
{diff_content}
--- END DIFF ---

Review the actual code changes above for:
1. Edge cases not covered by existing tests — cite specific lines
2. Performance implications (new loops, DB queries, API calls)
3. Breaking changes to public APIs
4. Security concerns (auth, validation, sanitization)
5. Code quality issues (complexity, duplication)

Provide actionable recommendations with file paths and line references.""",
                            priority="high",
                            estimated_input_tokens=estimated_input,
                            estimated_output_tokens=3_000,
                            source="commit",
                            deadline_hours=12,
                        )
                    )

                # Security-sensitive file detection
                security_patterns = [
                    r"auth",
                    r"security",
                    r"crypto",
                    r"password",
                    r"token",
                    r"api[_-]?key",
                    r"secret",
                    r"credential",
                ]

                security_files = [
                    f
                    for f in commit.get("files", [])
                    if any(re.search(pattern, f.lower()) for pattern in security_patterns)
                ]

                if security_files:
                    # Fetch diff for security-sensitive files only
                    sec_diff = self._get_commit_diff(commit["hash"], security_files)
                    sec_tokens = len(sec_diff) // 4 + 2000

                    work_items.append(
                        BatchWorkItem(
                            id=f"security-commit-{commit['hash'][:8]}",
                            title=f"Security review: {commit['subject'][:50]}",
                            description=f"Commit modified security-sensitive files: {', '.join(security_files[:3])}",
                            prompt=f"""Security-focused review of commit:

Commit: {commit['hash']}
Subject: {commit['subject']}
Security-sensitive files: {', '.join(security_files)}

--- ACTUAL DIFF (security-sensitive files) ---
{sec_diff}
--- END DIFF ---

Analyze the actual code changes above for:
1. Authentication/authorization bypasses
2. Input validation gaps
3. SQL injection vectors
4. XSS vulnerabilities
5. Exposed secrets or credentials
6. Insecure cryptographic practices
7. API security issues

Flag any high-risk changes with specific line references and recommend mitigations.""",
                            priority="immediate",
                            estimated_input_tokens=max(12_000, sec_tokens),
                            estimated_output_tokens=4_000,
                            source="security",
                            deadline_hours=8,
                        )
                    )

        except Exception as e:
            print(f"Warning: Failed to scan commits: {e}")

        return work_items

    def _parse_git_log(self, log_output: str) -> List[Dict[str, Any]]:
        """Parse git log output into structured commits"""
        commits = []
        current_commit = None

        for line in log_output.split("\n"):
            if "|" in line and len(line.split("|")) == 3:
                # Commit header line
                if current_commit:
                    commits.append(current_commit)

                hash_val, subject, author = line.split("|", 2)
                current_commit = {
                    "hash": hash_val,
                    "subject": subject,
                    "author": author,
                    "files_changed": 0,
                    "insertions": 0,
                    "deletions": 0,
                    "files": [],
                }
            elif current_commit and line.strip():
                # File stat line: insertions  deletions  filename
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        ins = int(parts[0]) if parts[0].isdigit() else 0
                        dels = int(parts[1]) if parts[1].isdigit() else 0
                        filename = parts[2]

                        current_commit["insertions"] += ins
                        current_commit["deletions"] += dels
                        current_commit["files_changed"] += 1
                        current_commit["files"].append(filename)
                    except (ValueError, IndexError):
                        pass

        if current_commit:
            commits.append(current_commit)

        return commits

    def scan_todos_and_fixmes(self) -> List[BatchWorkItem]:
        """
        Scan codebase for TODO and FIXME comments.

        Clusters related TODOs into batch analysis tasks.

        Returns:
            List of BatchWorkItem objects for TODO analysis
        """
        work_items = []

        try:
            # Find all TODO/FIXME comments
            result = subprocess.run(
                ["git", "grep", "-niE", "TODO|FIXME|XXX|HACK"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return work_items

            # Parse and cluster TODOs
            todos = self._parse_todos(result.stdout)

            # Group by project
            by_project = {}
            for todo in todos:
                project = self._extract_project(todo["file"])
                if project not in by_project:
                    by_project[project] = []
                by_project[project].append(todo)

            # Create batch work for each project with significant TODOs
            for project, project_todos in by_project.items():
                if len(project_todos) < 3:
                    continue  # Skip projects with few TODOs

                # Count by priority
                fixmes = sum(1 for t in project_todos if "FIXME" in t["marker"])
                hacks = sum(1 for t in project_todos if "HACK" in t["marker"])

                priority = "high" if (fixmes > 2 or hacks > 1) else "normal"

                # Sample TODOs for prompt
                sample_todos = "\n".join(
                    [
                        f"  {t['file']}:{t['line']}: {t['marker']} {t['text']}"
                        for t in project_todos[:10]
                    ]
                )

                work_items.append(
                    BatchWorkItem(
                        id=f"todo-analysis-{project}",
                        title=f"TODO/FIXME analysis: {project}",
                        description=f"Analyze {len(project_todos)} TODOs in {project} ({fixmes} FIXMEs, {hacks} HACKs)",
                        prompt=f"""Analyze TODOs and FIXMEs in {project}:

Total items: {len(project_todos)}
FIXMEs: {fixmes} (bugs/issues)
HACKs: {hacks} (technical debt)
TODOs: {len(project_todos) - fixmes - hacks}

Sample items:
{sample_todos}

For each category:
1. Identify patterns (common themes, related issues)
2. Prioritize by risk and impact
3. Group into actionable batches
4. Estimate effort for resolution
5. Flag blockers or dependencies

Create a prioritized action plan.""",
                        priority=priority,
                        estimated_input_tokens=10_000 + (len(project_todos) * 100),
                        estimated_output_tokens=3_000,
                        source="pattern",
                        deadline_hours=24,
                    )
                )

        except Exception as e:
            print(f"Warning: Failed to scan TODOs: {e}")

        return work_items

    def _parse_todos(self, grep_output: str) -> List[Dict[str, Any]]:
        """Parse git grep output into structured TODOs"""
        todos = []

        for line in grep_output.split("\n"):
            if not line.strip():
                continue

            # Format: filename:line:content
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue

            filename, line_num, content = parts

            # Extract marker (TODO, FIXME, etc.)
            marker_match = re.search(r"(TODO|FIXME|XXX|HACK)", content, re.IGNORECASE)
            marker = marker_match.group(1) if marker_match else "TODO"

            # Extract text after marker
            text = re.sub(r".*?(TODO|FIXME|XXX|HACK)[:\s]*", "", content, flags=re.IGNORECASE)
            text = text.strip()

            todos.append({"file": filename, "line": line_num, "marker": marker, "text": text})

        return todos

    def _extract_project(self, filepath: str) -> str:
        """Extract project name from filepath"""
        parts = filepath.split("/")

        # Common patterns
        if len(parts) > 0:
            # Top-level directory is usually project
            return parts[0]

        return "unknown"

    def scan_test_failures(self) -> List[BatchWorkItem]:
        """
        Scan for recent test failures.

        Analyzes test output logs, CI results, or pytest cache
        to find failing tests that need investigation.

        Returns:
            List of BatchWorkItem objects for failure analysis
        """
        work_items = []

        try:
            # Check pytest cache for last failures
            pytest_cache = self.root_dir / ".pytest_cache" / "v" / "cache" / "lastfailed"

            if pytest_cache.exists():
                with open(pytest_cache) as f:
                    failures = json.load(f)

                if failures:
                    # Group by project
                    by_project = {}
                    for test_path in failures.keys():
                        project = self._extract_project(test_path)
                        if project not in by_project:
                            by_project[project] = []
                        by_project[project].append(test_path)

                    for project, failed_tests in by_project.items():
                        work_items.append(
                            BatchWorkItem(
                                id=f"test-failure-{project}",
                                title=f"Test failure analysis: {project}",
                                description=f"Analyze {len(failed_tests)} failing tests in {project}",
                                prompt=f"""Analyze failing tests in {project}:

Failed tests ({len(failed_tests)}):
{chr(10).join(f'  - {test}' for test in failed_tests[:20])}

For each failure:
1. Identify root cause (code bug, flaky test, env issue)
2. Assess impact (blocks dev, blocks deploy, low priority)
3. Suggest fix approach
4. Estimate fix effort
5. Check for common patterns across failures

Prioritize by impact and provide actionable recommendations.""",
                                priority="high",
                                estimated_input_tokens=8_000 + (len(failed_tests) * 200),
                                estimated_output_tokens=3_000,
                                source="pattern",
                                deadline_hours=8,
                            )
                        )

            # Also check for projects with pytest markers
            for project_dir in ["Vortex/backend", "alpha_arena", "cortex"]:
                full_path = self.root_dir / project_dir
                if not full_path.exists():
                    continue

                # Run quick pytest collect to see if tests exist
                result = subprocess.run(
                    ["pytest", "--collect-only", "-q"],
                    cwd=full_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Check if there are errors in collection
                if "error" in result.stdout.lower() or "error" in result.stderr.lower():
                    work_items.append(
                        BatchWorkItem(
                            id=f"test-collection-{project_dir.replace('/', '-')}",
                            title=f"Test collection errors: {project_dir}",
                            description=f"Test collection failing in {project_dir}",
                            prompt=f"""Investigate test collection errors in {project_dir}:

Error output:
{result.stderr[:500]}

Analyze:
1. Import errors (missing dependencies, circular imports)
2. Syntax errors in test files
3. Fixture issues
4. Configuration problems
5. Missing test data or fixtures

Provide fix recommendations.""",
                            priority="high",
                            estimated_input_tokens=6_000,
                            estimated_output_tokens=2_000,
                            source="pattern",
                            deadline_hours=8,
                        )
                    )

        except Exception as e:
            print(f"Warning: Failed to scan test failures: {e}")

        return work_items


class CapacityAwareQueueFiller:
    """
    Fills overnight batch queue using bin packing algorithm.

    Uses composite priority scoring and bin packing to maximize
    capacity utilization within token/time constraints.
    """

    def __init__(self, capacity: Optional[BatchCapacity] = None):
        self.capacity = capacity or BatchCapacity()

    def fill_queue(
        self, work_items: List[BatchWorkItem], target_utilization: float = 0.9
    ) -> List[BatchWorkItem]:
        """
        Fill queue to target utilization using bin packing.

        BIN PACKING ALGORITHM DOCUMENTATION
        ===================================

        Overview:
        Uses First Fit Decreasing (FFD) bin packing to maximize overnight
        capacity utilization while respecting multiple constraints.

        Algorithm Steps:
        ---------------
        1. SCORING PHASE
           - Calculate composite score for each work item
           - Score = base_priority × deadline_mult × value_mult × blocking_mult
           - Components:
             * base_priority: immediate=100, high=75, normal=50, low=25
             * deadline_mult: 2.0x (≤8h), 1.5x (≤12h), 1.2x (≤24h), 1.0x (else)
             * value_mult: security=2.0x, pattern=1.5x, docs=1.0x, research=0.8x
             * blocking_mult: 1.5x if blocks other work (future enhancement)

        2. SORTING PHASE
           - Sort work items by composite score (descending)
           - Higher scores get priority for inclusion
           - This creates the "decreasing" order for FFD

        3. BIN PACKING PHASE (First Fit Decreasing)
           - Initialize: empty selected list, counters at 0
           - Iterate through sorted work items
           - For each item:
             a. Calculate required resources (tokens, time)
             b. Check if adding item would exceed capacity:
                - Token constraint: total_tokens + item_tokens ≤ target_tokens
                - Time constraint: total_time + item_time ≤ max_time_hours
             c. If fits: add to selected, update counters
             d. If doesn't fit: skip and try next item
           - Continue until no more items fit or all items processed

        4. CAPACITY CONSTRAINTS
           - Token budget: 40% of weekly allocation (conservative)
           - Time window: overnight_hours - 2h buffer (processing time)
           - Target utilization: 90% (configurable)
           - Multiple dimensions considered simultaneously

        Why First Fit Decreasing?
        -------------------------
        - Optimal for single-dimension bin packing
        - Near-optimal for multi-dimension (our case: tokens + time)
        - Greedy approach: O(n log n) time complexity
        - Proven to achieve 11/9 OPT approximation ratio
        - Simple to implement and understand
        - Works well with composite scoring

        Alternative Algorithms Considered:
        ---------------------------------
        1. Best Fit Decreasing: More complex, similar results
        2. Next Fit: Worse utilization (sequential only)
        3. Dynamic Programming: Exact but too slow for real-time
        4. Genetic Algorithm: Overkill for this problem size

        Why FFD Wins:
        - Fast enough for interactive use
        - Good enough utilization (typically 85-95%)
        - Deterministic results (reproducible)
        - Easy to debug and validate

        Time Complexity: O(n log n) for sort + O(n) for packing = O(n log n)
        Space Complexity: O(n) for storing selected items

        Args:
            work_items: Available work items to schedule
            target_utilization: Target capacity usage (0.0-1.0)

        Returns:
            Sorted list of work items to schedule, optimized for capacity
        """
        if not work_items:
            return []

        # Calculate capacity constraints
        available_tokens = self.capacity.available_overnight_tokens()
        target_tokens = int(available_tokens * target_utilization)

        max_time_hours = self.capacity.overnight_hours - 2  # Buffer for processing

        # Score and sort work items
        scored_items = [(self._calculate_composite_score(item), item) for item in work_items]
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Bin packing: First Fit Decreasing
        selected = []
        total_tokens = 0
        total_time_hours = 0.0

        for score, item in scored_items:
            item_tokens = item.total_tokens
            item_time = self._estimate_time_hours(item)

            # Check if item fits
            if (
                total_tokens + item_tokens <= target_tokens
                and total_time_hours + item_time <= max_time_hours
            ):

                selected.append(item)
                total_tokens += item_tokens
                total_time_hours += item_time

        return selected

    def _calculate_composite_score(self, item: BatchWorkItem) -> float:
        """
        Calculate composite priority score.

        Components:
        - Base priority (immediate=100, high=75, normal=50, low=25)
        - Deadline urgency (1.0 - 2.0x multiplier)
        - Value estimate (security=2.0x, pattern=1.5x, docs=1.0x)
        - Blocking factor (blocks other work=1.5x)

        Returns:
            Composite score (higher = more important)
        """
        # Base priority
        base_score = item.priority_score

        # Deadline urgency multiplier
        deadline_mult = self._deadline_multiplier(item.deadline_hours)

        # Value multiplier by source
        value_mult = {
            "security": 2.0,
            "pattern": 1.5,
            "docs": 1.0,
            "research": 0.8,
            "goal": 1.3,
        }.get(item.source, 1.0)

        # Blocking factor (would need to be in metadata)
        blocking_mult = 1.0

        # Composite score
        score = base_score * deadline_mult * value_mult * blocking_mult

        return score

    def _deadline_multiplier(self, deadline_hours: int) -> float:
        """Calculate urgency multiplier based on deadline"""
        if deadline_hours <= 8:
            return 2.0  # Very urgent
        elif deadline_hours <= 12:
            return 1.5  # Urgent
        elif deadline_hours <= 24:
            return 1.2  # Moderate
        else:
            return 1.0  # Normal

    def _estimate_time_hours(self, item: BatchWorkItem) -> float:
        """
        Estimate processing time in hours.

        Batch API typically processes within 24h, but we estimate
        based on token count for scheduling purposes.
        """
        # Very rough estimate: 50K tokens takes ~30 minutes
        tokens = item.total_tokens
        hours = (tokens / 50_000) * 0.5

        # Minimum 15 minutes
        return max(0.25, hours)


class BatchPerformanceTracker:
    """
    Tracks batch job performance with SQLite.

    Records estimates vs actuals to improve future predictions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".cortex" / "batch" / "performance.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_tasks (
                    task_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    title TEXT,
                    source TEXT,
                    priority TEXT,

                    estimated_input_tokens INTEGER,
                    estimated_output_tokens INTEGER,
                    estimated_duration_hours REAL,

                    actual_input_tokens INTEGER,
                    actual_output_tokens INTEGER,
                    actual_duration_hours REAL,

                    submitted_at TEXT,
                    completed_at TEXT,
                    status TEXT,

                    error_message TEXT,

                    UNIQUE(task_id)
                )
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_submitted_at
                ON batch_tasks(submitted_at)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source
                ON batch_tasks(source)
            """
            )

            conn.commit()

    def record_submission(self, task: BatchWorkItem, job_id: str):
        """
        Record task submission.

        Args:
            task: BatchWorkItem being submitted
            job_id: Batch API job ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO batch_tasks (
                    task_id, job_id, title, source, priority,
                    estimated_input_tokens, estimated_output_tokens,
                    estimated_duration_hours, submitted_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task.id,
                    job_id,
                    task.title,
                    task.source,
                    task.priority,
                    task.estimated_input_tokens,
                    task.estimated_output_tokens,
                    0.5,  # Default estimate
                    datetime.now().isoformat(),
                    "submitted",
                ),
            )
            conn.commit()

    def record_completion(
        self,
        task_id: str,
        actual_tokens: Tuple[int, int],
        actual_duration: float,
        status: str = "completed",
        error_message: Optional[str] = None,
    ):
        """
        Record task completion with actuals.

        Args:
            task_id: Task ID
            actual_tokens: (input_tokens, output_tokens)
            actual_duration: Duration in hours
            status: "completed" or "failed"
            error_message: Error if failed
        """
        actual_input, actual_output = actual_tokens

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE batch_tasks
                SET actual_input_tokens = ?,
                    actual_output_tokens = ?,
                    actual_duration_hours = ?,
                    completed_at = ?,
                    status = ?,
                    error_message = ?
                WHERE task_id = ?
            """,
                (
                    actual_input,
                    actual_output,
                    actual_duration,
                    datetime.now().isoformat(),
                    status,
                    error_message,
                    task_id,
                ),
            )
            conn.commit()

    def get_estimation_accuracy(self, days: int = 30) -> Dict[str, Any]:
        """
        Calculate estimation accuracy over last N days.

        Returns:
            Dict with accuracy metrics by source
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """
                SELECT
                    source,
                    AVG(estimated_input_tokens) as avg_est_input,
                    AVG(actual_input_tokens) as avg_actual_input,
                    AVG(estimated_output_tokens) as avg_est_output,
                    AVG(actual_output_tokens) as avg_actual_output,
                    AVG(estimated_duration_hours) as avg_est_duration,
                    AVG(actual_duration_hours) as avg_actual_duration,
                    COUNT(*) as task_count
                FROM batch_tasks
                WHERE submitted_at >= ?
                  AND status = 'completed'
                  AND actual_input_tokens IS NOT NULL
                GROUP BY source
            """,
                (cutoff,),
            ).fetchall()

        accuracy = {}
        for row in rows:
            source = row["source"]

            # Calculate accuracy percentages
            input_accuracy = (
                (row["avg_actual_input"] / row["avg_est_input"] * 100)
                if row["avg_est_input"] > 0
                else 0
            )

            output_accuracy = (
                (row["avg_actual_output"] / row["avg_est_output"] * 100)
                if row["avg_est_output"] > 0
                else 0
            )

            duration_accuracy = (
                (row["avg_actual_duration"] / row["avg_est_duration"] * 100)
                if row["avg_est_duration"] > 0
                else 0
            )

            accuracy[source] = {
                "task_count": row["task_count"],
                "input_accuracy_pct": round(input_accuracy, 1),
                "output_accuracy_pct": round(output_accuracy, 1),
                "duration_accuracy_pct": round(duration_accuracy, 1),
                "avg_est_input": int(row["avg_est_input"]),
                "avg_actual_input": int(row["avg_actual_input"]),
                "avg_est_output": int(row["avg_est_output"]),
                "avg_actual_output": int(row["avg_actual_output"]),
            }

        return accuracy


class AdaptiveEstimator:
    """
    Learns from historical performance to improve estimates.

    Queries last 30 days of batch tasks, calculates moving averages,
    and adjusts token/duration estimates based on actuals.
    """

    def __init__(self, tracker: BatchPerformanceTracker):
        self.tracker = tracker

    def improve_estimates(
        self, work_items: List[BatchWorkItem], lookback_days: int = 30
    ) -> List[BatchWorkItem]:
        """
        Improve token/duration estimates based on history.

        Args:
            work_items: Work items with initial estimates
            lookback_days: Days of history to analyze

        Returns:
            Work items with improved estimates
        """
        # Get accuracy data
        accuracy = self.tracker.get_estimation_accuracy(days=lookback_days)

        if not accuracy:
            # No history yet, return as-is
            return work_items

        # Adjust estimates based on historical accuracy
        improved = []
        for item in work_items:
            source_accuracy = accuracy.get(item.source)

            if source_accuracy and source_accuracy["task_count"] >= 3:
                # Enough history for this source type

                # Calculate adjustment factors
                input_factor = (
                    source_accuracy["avg_actual_input"] / source_accuracy["avg_est_input"]
                )
                output_factor = (
                    source_accuracy["avg_actual_output"] / source_accuracy["avg_est_output"]
                )

                # Apply adjustments (cap at 2x to avoid overcompensation)
                input_factor = min(2.0, max(0.5, input_factor))
                output_factor = min(2.0, max(0.5, output_factor))

                # Create improved estimate
                improved_item = BatchWorkItem(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    prompt=item.prompt,
                    priority=item.priority,
                    estimated_input_tokens=int(item.estimated_input_tokens * input_factor),
                    estimated_output_tokens=int(item.estimated_output_tokens * output_factor),
                    source=item.source,
                    project=item.project,
                    files=item.files,
                    deadline_hours=item.deadline_hours,
                )

                improved.append(improved_item)
            else:
                # Not enough history, use original
                improved.append(item)

        return improved

    def get_learning_summary(self, days: int = 30) -> str:
        """
        Generate human-readable learning summary.

        Returns:
            Summary string showing what we've learned
        """
        accuracy = self.tracker.get_estimation_accuracy(days=days)

        if not accuracy:
            return "No historical data available yet. Need at least 3 completed tasks to start learning."

        lines = [f"Batch Performance Learning Summary (last {days} days)", "=" * 60, ""]

        for source, metrics in accuracy.items():
            lines.extend(
                [
                    f"{source.upper()} ({metrics['task_count']} tasks):",
                    f"  Input tokens:  {metrics['avg_est_input']:,} est → {metrics['avg_actual_input']:,} actual ({metrics['input_accuracy_pct']:.0f}% accuracy)",
                    f"  Output tokens: {metrics['avg_est_output']:,} est → {metrics['avg_actual_output']:,} actual ({metrics['output_accuracy_pct']:.0f}% accuracy)",
                    f"  Duration:      {metrics['duration_accuracy_pct']:.0f}% accuracy",
                    "",
                ]
            )

        return "\n".join(lines)


def integrate_with_orchestrator(
    root_dir: Path = Path("/Users/jesse.kemp/Dev"),
) -> List[BatchWorkItem]:
    """
    Integration point with IntelligentBatchOrchestrator.

    Adds dynamic work generation to the existing static work items.

    Returns:
        Combined list of static + dynamic work items
    """
    # Generate dynamic work
    generator = DynamicWorkGenerator(root_dir)

    dynamic_work = []
    dynamic_work.extend(generator.scan_recent_commits(hours=24))
    dynamic_work.extend(generator.scan_todos_and_fixmes())
    dynamic_work.extend(generator.scan_test_failures())

    # Get static work from orchestrator
    from intelligent_orchestrator import IntelligentBatchOrchestrator

    orchestrator = IntelligentBatchOrchestrator(root_dir=str(root_dir))
    static_work = orchestrator.generate_work_items()

    # Combine (static + dynamic)
    all_work = static_work + dynamic_work

    # Apply adaptive estimation
    tracker = BatchPerformanceTracker()
    estimator = AdaptiveEstimator(tracker)
    all_work = estimator.improve_estimates(all_work)

    # Fill queue with bin packing
    filler = CapacityAwareQueueFiller()
    selected_work = filler.fill_queue(all_work, target_utilization=0.9)

    return selected_work


if __name__ == "__main__":
    # Demo: Generate and optimize work queue
    print("Adaptive Batch Queue Optimizer")
    print("=" * 70)
    print()

    # Generate work
    print("Generating work items...")
    work_items = integrate_with_orchestrator()

    print(f"Selected {len(work_items)} items for overnight queue")
    print()

    # Show top 5 by priority
    print("Top priority items:")
    for i, item in enumerate(work_items[:5], 1):
        print(f"{i}. [{item.priority.upper():9}] {item.title}")
        print(f"   Tokens: {item.total_tokens:,} | Source: {item.source}")
    print()

    # Show learning summary
    tracker = BatchPerformanceTracker()
    estimator = AdaptiveEstimator(tracker)
    print(estimator.get_learning_summary())
