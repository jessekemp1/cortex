#!/usr/bin/env python3
"""
Prompt History Intelligence - Learn from your conversation patterns.

This module extracts, analyzes, and learns from your Claude Code conversation history to:
1. Identify your working patterns and priorities
2. Detect workflow preferences and tool usage
3. Predict what you'll need next
4. Optimize Cortex recommendations based on what you actually ask for

Layer 2 of Cortex Intelligence Stack: Prompt Memory.
"""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set



@dataclass
class PromptPattern:
    """A pattern extracted from conversation history."""

    topic: str  # Main topic/theme
    keywords: List[str]  # Key terms
    frequency: int  # How often this appears
    recent_activity: datetime  # Last time you worked on this
    projects: Set[str]  # Which projects it relates to
    tools_used: List[str]  # Which tools you typically use for this
    urgency_score: float  # 0-1, based on language ("urgent", "quick", etc.)
    session_ids: List[str]  # Sessions where this appeared

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "topic": self.topic,
            "keywords": self.keywords,
            "frequency": self.frequency,
            "recent_activity": self.recent_activity.isoformat(),
            "projects": list(self.projects),
            "tools_used": self.tools_used,
            "urgency_score": self.urgency_score,
            "session_count": len(self.session_ids),
        }


@dataclass
class WorkflowPattern:
    """A workflow pattern detected from sequences of prompts."""

    name: str
    steps: List[str]  # Typical sequence of actions
    trigger_keywords: List[str]  # What triggers this workflow
    success_rate: float  # How often it completes successfully
    avg_duration_minutes: float
    last_used: datetime
    frequency: int  # How many times this workflow occurred

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "steps": self.steps,
            "trigger_keywords": self.trigger_keywords,
            "success_rate": self.success_rate,
            "avg_duration_minutes": self.avg_duration_minutes,
            "last_used": self.last_used.isoformat(),
            "frequency": self.frequency,
        }


@dataclass
class PrioritySignal:
    """Signals detected about your priorities from conversation patterns."""

    category: str  # "feature", "fix", "research", "infrastructure", etc.
    strength: float  # 0-1, how strongly this priority is signaled
    trend: str  # "increasing", "stable", "decreasing"
    evidence: List[str]  # Recent prompts that support this
    projects_affected: Set[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "category": self.category,
            "strength": self.strength,
            "trend": self.trend,
            "evidence": self.evidence[:5],  # Top 5 pieces of evidence
            "projects_affected": list(self.projects_affected),
        }


class PromptHistoryAnalyzer:
    """Analyzes conversation history to extract patterns and insights."""

    # Urgency keywords
    URGENCY_KEYWORDS = {
        "urgent": 1.0,
        "asap": 0.9,
        "quick": 0.7,
        "fast": 0.7,
        "immediately": 1.0,
        "now": 0.8,
        "critical": 0.9,
        "blocker": 0.9,
        "broken": 0.8,
        "failing": 0.8,
    }

    # Project-related patterns
    PROJECT_PATTERNS = [
        r"@(\w+)",  # @vortex, @cortex, etc.
        r"(?:in|for|on)\s+(\w+(?:_\w+)*)\s+project",
        r"VortexV[23]",
        r"Alpha\s*Arena",
        r"Cortex",
    ]

    # Category patterns
    CATEGORY_PATTERNS = {
        "feature": [r"\badd\b", r"\bcreate\b", r"\bimplement\b", r"\bbuild\b", r"\bnew\b"],
        "fix": [r"\bfix\b", r"\bbug\b", r"\bissue\b", r"\berror\b", r"\bbroken\b"],
        "research": [
            r"\bresearch\b",
            r"\binvestigate\b",
            r"\bexplore\b",
            r"\blearn\b",
            r"\bunderstand\b",
        ],
        "refactor": [r"\brefactor\b", r"\bclean\s*up\b", r"\bimprove\b", r"\boptimize\b"],
        "test": [r"\btest\b", r"\bvalidate\b", r"\bverify\b", r"\bcheck\b"],
        "docs": [
            r"\bdocument\b",
            r"\bdocs\b",
            r"\bexplain\b",
            r"\breadme\b",
            r"\bcomment\b",
        ],
        "deploy": [r"\bdeploy\b", r"\bship\b", r"\brelease\b", r"\bpublish\b"],
    }

    def __init__(self, sessions_dir: Optional[Path] = None):
        """Initialize analyzer.

        Args:
            sessions_dir: Path to Claude Code sessions directory.
                         Defaults to ~/Library/Application Support/Claude/local-agent-mode-sessions/
        """
        if sessions_dir is None:
            sessions_dir = (
                Path.home() / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
            )

        self.sessions_dir = sessions_dir
        self.cache_dir = Path.home() / ".cortex" / "prompt_history"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def extract_sessions(
        self, days_back: int = 30, max_sessions: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Extract conversation sessions from audit logs.

        Args:
            days_back: How many days of history to extract
            max_sessions: Maximum number of sessions to process (None = all)

        Returns:
            List of sessions with extracted data
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        sessions = []

        # Find all audit.jsonl files
        audit_files = list(self.sessions_dir.rglob("audit.jsonl"))

        for audit_file in audit_files:
            try:
                session_data = self._parse_audit_file(audit_file, cutoff_date)
                if session_data:
                    sessions.append(session_data)

                    if max_sessions and len(sessions) >= max_sessions:
                        break
            except Exception:
                # Skip problematic files
                continue

        return sessions

    def _parse_audit_file(
        self, audit_file: Path, cutoff_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Parse a single audit.jsonl file.

        Returns:
            Session data dict or None if too old/empty
        """
        user_prompts = []
        assistant_responses = []
        tool_calls = []
        session_id = None
        session_start = None
        session_cwd = None

        with open(audit_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Extract timestamp
                timestamp_str = entry.get("_audit_timestamp")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

                    # Skip old sessions
                    if timestamp < cutoff_date:
                        continue

                    if session_start is None or timestamp < session_start:
                        session_start = timestamp

                # Extract session ID and CWD from system init
                if entry.get("type") == "system" and entry.get("subtype") == "init":
                    session_id = entry.get("session_id")
                    session_cwd = entry.get("cwd")

                # Extract user prompts
                if entry.get("type") == "user":
                    message = entry.get("message", {})
                    content = message.get("content", "")
                    if content and isinstance(content, str):
                        user_prompts.append(
                            {
                                "text": content,
                                "timestamp": timestamp if timestamp_str else None,
                            }
                        )

                # Extract assistant responses (for success/failure analysis)
                if entry.get("type") == "assistant":
                    message = entry.get("message", {})
                    assistant_responses.append(
                        {
                            "stop_reason": message.get("stop_reason"),
                            "error": entry.get("error"),
                            "timestamp": timestamp if timestamp_str else None,
                        }
                    )

                # Extract tool usage
                if entry.get("type") == "tool_use":
                    tool_calls.append(entry.get("tool_name"))

        if not user_prompts:
            return None

        return {
            "session_id": session_id,
            "cwd": session_cwd,
            "start_time": session_start,
            "prompts": user_prompts,
            "responses": assistant_responses,
            "tools_used": list(set(tool_calls)),  # Deduplicate
            "audit_file": str(audit_file),
        }

    def analyze_prompt_patterns(
        self, sessions: List[Dict[str, Any]], min_frequency: int = 2
    ) -> List[PromptPattern]:
        """Analyze sessions to extract recurring patterns.

        Args:
            sessions: Sessions from extract_sessions()
            min_frequency: Minimum times a pattern must appear

        Returns:
            List of detected patterns
        """
        # Track topics and their metadata
        topic_data = defaultdict(
            lambda: {
                "keywords": Counter(),
                "sessions": set(),
                "projects": set(),
                "tools": Counter(),
                "urgency_scores": [],
                "timestamps": [],
            }
        )

        for session in sessions:
            session_id = session["session_id"]
            tools_used = session["tools_used"]
            cwd = session["cwd"] or ""

            # Extract project from cwd
            project = self._extract_project_from_cwd(cwd)

            for prompt_data in session["prompts"]:
                prompt = prompt_data["text"]
                timestamp = prompt_data.get("timestamp")

                # Extract topics, keywords, urgency
                topics = self._extract_topics(prompt)
                keywords = self._extract_keywords(prompt)
                urgency = self._calculate_urgency(prompt)
                prompt_projects = self._extract_projects(prompt)

                for topic in topics:
                    topic_data[topic]["keywords"].update(keywords)
                    topic_data[topic]["sessions"].add(session_id)
                    topic_data[topic]["projects"].update(prompt_projects)
                    if project:
                        topic_data[topic]["projects"].add(project)
                    topic_data[topic]["tools"].update(tools_used)
                    topic_data[topic]["urgency_scores"].append(urgency)
                    if timestamp:
                        topic_data[topic]["timestamps"].append(timestamp)

        # Convert to PromptPattern objects
        patterns = []
        for topic, data in topic_data.items():
            frequency = len(data["sessions"])
            if frequency < min_frequency:
                continue

            # Get top keywords
            top_keywords = [word for word, _ in data["keywords"].most_common(10)]

            # Get top tools
            top_tools = [tool for tool, _ in data["tools"].most_common(5)]

            # Average urgency
            avg_urgency = sum(data["urgency_scores"]) / len(data["urgency_scores"]) if data["urgency_scores"] else 0

            # Most recent activity
            recent = max(data["timestamps"]) if data["timestamps"] else datetime.now()

            pattern = PromptPattern(
                topic=topic,
                keywords=top_keywords,
                frequency=frequency,
                recent_activity=recent,
                projects=data["projects"],
                tools_used=top_tools,
                urgency_score=avg_urgency,
                session_ids=list(data["sessions"]),
            )

            patterns.append(pattern)

        # Sort by frequency (most common first)
        patterns.sort(key=lambda p: p.frequency, reverse=True)

        return patterns

    def analyze_priorities(
        self, sessions: List[Dict[str, Any]], lookback_days: int = 7
    ) -> List[PrioritySignal]:
        """Detect your current priorities based on recent activity.

        Args:
            sessions: Sessions from extract_sessions()
            lookback_days: How many days to analyze for "recent"

        Returns:
            List of priority signals
        """
        recent_cutoff = datetime.now() - timedelta(days=lookback_days)
        older_cutoff = datetime.now() - timedelta(days=lookback_days * 2)

        # Track category mentions over time
        recent_counts = Counter()
        older_counts = Counter()
        category_evidence = defaultdict(list)
        category_projects = defaultdict(set)

        for session in sessions:
            for prompt_data in session["prompts"]:
                prompt = prompt_data["text"]
                timestamp = prompt_data.get("timestamp")
                cwd = session.get("cwd", "")
                project = self._extract_project_from_cwd(cwd)

                if not timestamp:
                    continue

                # Categorize the prompt
                categories = self._categorize_prompt(prompt)

                for category in categories:
                    # Add evidence
                    category_evidence[category].append(prompt[:100])  # First 100 chars
                    if project:
                        category_projects[category].add(project)

                    # Count by time period
                    if timestamp >= recent_cutoff:
                        recent_counts[category] += 1
                    elif timestamp >= older_cutoff:
                        older_counts[category] += 1

        # Calculate priority signals
        priorities = []
        for category in set(recent_counts.keys()) | set(older_counts.keys()):
            recent = recent_counts[category]
            older = older_counts[category]

            # Strength: normalized by total recent activity
            total_recent = sum(recent_counts.values())
            strength = recent / total_recent if total_recent > 0 else 0

            # Trend: increasing/decreasing/stable
            if older == 0:
                trend = "new" if recent > 0 else "stable"
            elif recent > older * 1.5:
                trend = "increasing"
            elif recent < older * 0.5:
                trend = "decreasing"
            else:
                trend = "stable"

            if strength > 0.05:  # At least 5% of recent activity
                priority = PrioritySignal(
                    category=category,
                    strength=strength,
                    trend=trend,
                    evidence=category_evidence[category],
                    projects_affected=category_projects[category],
                )
                priorities.append(priority)

        # Sort by strength
        priorities.sort(key=lambda p: p.strength, reverse=True)

        return priorities

    def detect_workflows(self, sessions: List[Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect common workflow patterns from session sequences.

        A workflow is a sequence of prompts that tend to occur together
        (e.g., investigate -> plan -> implement -> test -> commit).

        Args:
            sessions: Sessions from extract_sessions()

        Returns:
            List of detected workflows
        """
        # Track sequences of categories
        sequences = []

        for session in sessions:
            sequence = []
            session_duration = None

            for i, prompt_data in enumerate(session["prompts"]):
                prompt = prompt_data["text"]
                categories = self._categorize_prompt(prompt)

                for category in categories:
                    sequence.append(category)

                # Calculate session duration
                if i == 0 and prompt_data.get("timestamp"):
                    start_time = prompt_data["timestamp"]
                if i == len(session["prompts"]) - 1 and prompt_data.get("timestamp"):
                    end_time = prompt_data["timestamp"]
                    if start_time:
                        session_duration = (end_time - start_time).total_seconds() / 60

            if len(sequence) >= 2:  # Need at least 2 steps for a workflow
                sequences.append(
                    {
                        "sequence": tuple(sequence),
                        "duration": session_duration,
                        "success": self._session_completed_successfully(session),
                    }
                )

        # Find common sequences (at least 3 occurrences)
        sequence_counter = Counter(s["sequence"] for s in sequences)
        common_sequences = [seq for seq, count in sequence_counter.items() if count >= 3]

        # Build workflow patterns
        workflows = []
        for seq in common_sequences:
            matching = [s for s in sequences if s["sequence"] == seq]

            # Calculate metrics
            successes = sum(1 for s in matching if s["success"])
            success_rate = successes / len(matching) if matching else 0
            durations = [s["duration"] for s in matching if s["duration"]]
            avg_duration = sum(durations) / len(durations) if durations else 0

            # Generate workflow name from sequence
            name = " → ".join(seq)

            # Trigger keywords (common words in first step)
            trigger_keywords = list(seq[:1])  # First category

            workflow = WorkflowPattern(
                name=name,
                steps=list(seq),
                trigger_keywords=trigger_keywords,
                success_rate=success_rate,
                avg_duration_minutes=avg_duration,
                last_used=datetime.now(),  # Would need to track this properly
                frequency=len(matching),
            )

            workflows.append(workflow)

        # Sort by frequency
        workflows.sort(key=lambda w: w.frequency, reverse=True)

        return workflows

    def _extract_topics(self, prompt: str) -> List[str]:
        """Extract main topics from a prompt using simple heuristics."""
        # Remove URLs and code blocks
        text = re.sub(r"http\S+", "", prompt)
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]+`", "", text)

        # Extract sentences
        sentences = re.split(r"[.!?]\s+", text)

        topics = []

        # First sentence is often the main topic
        if sentences:
            first_sentence = sentences[0].strip().lower()
            # Extract key phrases (noun phrases approximately)
            # This is a simple heuristic - could be improved with NLP
            words = first_sentence.split()
            if words:
                # Take first 3-5 words as topic
                topic = " ".join(words[:min(5, len(words))])
                topics.append(topic)

        return topics if topics else ["general"]

    def _extract_keywords(self, prompt: str) -> List[str]:
        """Extract significant keywords from prompt."""
        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "this",
            "that",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "can",
            "could",
            "should",
            "would",
            "will",
            "i",
            "you",
            "we",
            "they",
            "it",
            "me",
            "my",
        }

        # Extract words
        words = re.findall(r"\b[a-z]+\b", prompt.lower())

        # Filter stop words and short words
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]

        return keywords

    def _calculate_urgency(self, prompt: str) -> float:
        """Calculate urgency score (0-1) based on keywords."""
        prompt_lower = prompt.lower()

        max_urgency = 0.0
        for keyword, score in self.URGENCY_KEYWORDS.items():
            if keyword in prompt_lower:
                max_urgency = max(max_urgency, score)

        return max_urgency

    def _extract_projects(self, prompt: str) -> Set[str]:
        """Extract project names mentioned in prompt."""
        projects = set()

        for pattern in self.PROJECT_PATTERNS:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            for match in matches:
                # Clean up match
                project = match.strip().lower()
                if project:
                    projects.add(project)

        return projects

    def _extract_project_from_cwd(self, cwd: str) -> Optional[str]:
        """Extract project name from current working directory."""
        if not cwd:
            return None

        # Extract last directory component that looks like a project
        parts = Path(cwd).parts
        for part in reversed(parts):
            # Skip sessions, worktrees, etc.
            if part.startswith(".") or "session" in part.lower() or "worktree" in part.lower():
                continue
            # Found a potential project
            if part and len(part) > 2:
                return part.lower()

        return None

    def _categorize_prompt(self, prompt: str) -> List[str]:
        """Categorize a prompt by intent (feature, fix, research, etc.)."""
        prompt_lower = prompt.lower()
        categories = []

        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    categories.append(category)
                    break  # Only count once per category

        return categories if categories else ["other"]

    def _session_completed_successfully(self, session: Dict[str, Any]) -> bool:
        """Determine if a session completed successfully based on responses."""
        responses = session.get("responses", [])

        if not responses:
            return False

        # Check last response
        last_response = responses[-1]

        # Failed if there's an error
        if last_response.get("error"):
            return False

        # Success if stop reason is normal
        if last_response.get("stop_reason") in ["end_turn", "stop_sequence"]:
            return True

        return False

    def save_analysis(
        self,
        patterns: List[PromptPattern],
        priorities: List[PrioritySignal],
        workflows: List[WorkflowPattern],
    ) -> None:
        """Save analysis results to cache."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "patterns": [p.to_dict() for p in patterns],
            "priorities": [p.to_dict() for p in priorities],
            "workflows": [w.to_dict() for w in workflows],
        }

        output_file = self.cache_dir / "prompt_analysis.json"
        with open(output_file, "w") as f:
            json.dump(analysis, f, indent=2)

        print(f"Analysis saved to {output_file}")

    def load_analysis(self) -> Optional[Dict[str, Any]]:
        """Load cached analysis results."""
        cache_file = self.cache_dir / "prompt_analysis.json"

        if not cache_file.exists():
            return None

        with open(cache_file, "r") as f:
            return json.load(f)


def main():
    """CLI for testing prompt history analysis."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python prompt_history.py <command> [args]")
        print("\nCommands:")
        print("  analyze [days]       - Analyze prompt history (default: 30 days)")
        print("  patterns             - Show detected patterns")
        print("  priorities           - Show current priorities")
        print("  workflows            - Show detected workflows")
        print("  stats                - Show statistics")
        return

    command = sys.argv[1]
    analyzer = PromptHistoryAnalyzer()

    if command == "analyze":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

        print(f"Analyzing last {days} days of conversation history...")
        sessions = analyzer.extract_sessions(days_back=days)

        print(f"Found {len(sessions)} sessions")

        # Analyze patterns
        print("\nAnalyzing prompt patterns...")
        patterns = analyzer.analyze_prompt_patterns(sessions)

        # Analyze priorities
        print("Analyzing priorities...")
        priorities = analyzer.analyze_priorities(sessions)

        # Detect workflows
        print("Detecting workflows...")
        workflows = analyzer.detect_workflows(sessions)

        # Save results
        analyzer.save_analysis(patterns, priorities, workflows)

        # Print summary
        print("\n=== SUMMARY ===")
        print(f"Patterns detected: {len(patterns)}")
        print(f"Priorities identified: {len(priorities)}")
        print(f"Workflows discovered: {len(workflows)}")

    elif command == "patterns":
        analysis = analyzer.load_analysis()
        if not analysis:
            print("No analysis found. Run 'analyze' first.")
            return

        print("\n=== TOP PROMPT PATTERNS ===")
        for i, pattern in enumerate(analysis["patterns"][:10], 1):
            print(f"\n{i}. {pattern['topic']}")
            print(f"   Frequency: {pattern['frequency']} sessions")
            print(f"   Projects: {', '.join(pattern['projects'])}")
            print(f"   Keywords: {', '.join(pattern['keywords'][:5])}")
            print(f"   Urgency: {pattern['urgency_score']:.1%}")

    elif command == "priorities":
        analysis = analyzer.load_analysis()
        if not analysis:
            print("No analysis found. Run 'analyze' first.")
            return

        print("\n=== CURRENT PRIORITIES ===")
        for i, priority in enumerate(analysis["priorities"], 1):
            print(f"\n{i}. {priority['category'].upper()}")
            print(f"   Strength: {priority['strength']:.1%}")
            print(f"   Trend: {priority['trend']}")
            print(f"   Projects: {', '.join(priority['projects_affected'])}")

    elif command == "workflows":
        analysis = analyzer.load_analysis()
        if not analysis:
            print("No analysis found. Run 'analyze' first.")
            return

        print("\n=== DETECTED WORKFLOWS ===")
        for i, workflow in enumerate(analysis["workflows"], 1):
            print(f"\n{i}. {workflow['name']}")
            print(f"   Frequency: {workflow['frequency']} times")
            print(f"   Success rate: {workflow['success_rate']:.1%}")
            print(f"   Avg duration: {workflow['avg_duration_minutes']:.0f} minutes")

    elif command == "stats":
        analysis = analyzer.load_analysis()
        if not analysis:
            print("No analysis found. Run 'analyze' first.")
            return

        print("\n=== PROMPT HISTORY STATISTICS ===")
        print(f"Analysis timestamp: {analysis['timestamp']}")
        print(f"Total patterns: {len(analysis['patterns'])}")
        print(f"Total priorities: {len(analysis['priorities'])}")
        print(f"Total workflows: {len(analysis['workflows'])}")

        # Top projects
        all_projects = set()
        for pattern in analysis["patterns"]:
            all_projects.update(pattern["projects"])
        print(f"\nProjects worked on: {', '.join(sorted(all_projects))}")


if __name__ == "__main__":
    main()
