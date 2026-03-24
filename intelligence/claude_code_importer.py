#!/usr/bin/env python3
"""
Claude Code Data Importer - Pulls learning data from ~/.claude/ into Cortex.

Imports:
- Project index data from ~/.claude/portfolio/project_index.json
- Session data from Claude Code's conversation history
- Anti-pattern observations from ~/.claude/memories/anti-patterns.md
- Tool usage patterns from conversation histories

All imported data is stored in the consolidated outcome store for
cross-system learning.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortex.state_paths import get_cortex_dir

logger = logging.getLogger(__name__)


class ClaudeCodeImporter:
    """Imports learning data from Claude Code's ~/.claude/ directory."""

    def __init__(self, claude_dir: Optional[Path] = None, cortex_dir: Optional[Path] = None):
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.cortex_dir = cortex_dir or get_cortex_dir()
        self._store = None

    def _get_store(self):
        """Lazy-load the consolidated store."""
        if self._store is None:
            try:
                from intelligence.storage.consolidated_store import get_consolidated_store
                self._store = get_consolidated_store()
            except Exception:
                pass
        return self._store

    def import_all(self) -> Dict[str, Any]:
        """
        Run all importers and return summary.

        Returns:
            Dict with counts and status per import type.
        """
        results = {}

        if not self.claude_dir.exists():
            return {"error": f"Claude Code directory not found: {self.claude_dir}"}

        results["project_patterns"] = self.import_project_patterns()
        results["anti_patterns"] = self.import_anti_patterns()
        results["tool_preferences"] = self.import_tool_preferences()
        results["session_topics"] = self.import_session_topics()

        return results

    def import_project_patterns(self) -> Dict[str, Any]:
        """
        Import project metadata from Claude Code's project index.

        Extracts:
        - Project names and types
        - Active vs inactive status
        - File structure patterns
        - Language/framework preferences
        """
        index_file = self.claude_dir / "portfolio" / "project_index.json"
        if not index_file.exists():
            # Try alternate locations
            for alt in [
                self.claude_dir / "projects" / "index.json",
                self.claude_dir / "project_index.json",
            ]:
                if alt.exists():
                    index_file = alt
                    break
            else:
                return {"status": "skipped", "reason": "no project index found"}

        try:
            with open(index_file) as f:
                data = json.load(f)

            projects = data if isinstance(data, list) else data.get("projects", [])
            if not projects:
                return {"status": "skipped", "reason": "empty project index"}

            # Extract patterns
            patterns = {
                "languages": set(),
                "frameworks": set(),
                "project_types": set(),
                "total_projects": len(projects),
                "active_projects": 0,
            }

            for project in projects:
                if isinstance(project, dict):
                    if project.get("active") or project.get("commits_7d", 0) > 0:
                        patterns["active_projects"] += 1

                    lang = project.get("language") or project.get("primary_language")
                    if lang:
                        patterns["languages"].add(lang)

                    framework = project.get("framework")
                    if framework:
                        patterns["frameworks"].add(framework)

                    ptype = project.get("type") or project.get("project_type")
                    if ptype:
                        patterns["project_types"].add(ptype)

            # Persist as learning context
            output_file = self.cortex_dir / "imported" / "project_patterns.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                k: list(v) if isinstance(v, set) else v
                for k, v in patterns.items()
            }
            with open(output_file, "w") as f:
                json.dump(serializable, f, indent=2)

            return {
                "status": "imported",
                "projects": len(projects),
                "active": patterns["active_projects"],
                "languages": list(patterns["languages"]),
            }

        except (json.JSONDecodeError, IOError, KeyError) as e:
            return {"status": "error", "reason": str(e)}

    def import_anti_patterns(self) -> Dict[str, Any]:
        """
        Import anti-pattern observations from Claude Code's memory.

        Parses ~/.claude/memories/anti-patterns.md (or similar) to extract
        learned rules about what NOT to do.
        """
        anti_patterns = []

        # Check multiple possible locations
        candidates = [
            self.claude_dir / "memories" / "anti-patterns.md",
            self.claude_dir / "memories" / "anti_patterns.md",
            self.claude_dir / "CLAUDE.md",
        ]

        for candidate in candidates:
            if candidate.exists():
                try:
                    content = candidate.read_text(encoding="utf-8")
                    patterns = self._extract_anti_patterns(content)
                    anti_patterns.extend(patterns)
                except IOError:
                    continue

        if not anti_patterns:
            return {"status": "skipped", "reason": "no anti-pattern files found"}

        # Persist
        output_file = self.cortex_dir / "imported" / "anti_patterns.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(anti_patterns, f, indent=2)

        return {
            "status": "imported",
            "count": len(anti_patterns),
            "source_files": [str(c) for c in candidates if c.exists()],
        }

    def _extract_anti_patterns(self, content: str) -> List[Dict[str, str]]:
        """Extract anti-patterns from markdown content."""
        patterns = []

        # Match common patterns: "Don't ...", "Never ...", "Avoid ..."
        anti_pattern_regex = re.compile(
            r"[-*]\s+((?:Don'?t|Never|Avoid|Do not|Always)\s+.+?)(?:\n|$)",
            re.IGNORECASE,
        )

        for match in anti_pattern_regex.finditer(content):
            text = match.group(1).strip()
            if len(text) > 10:  # Skip very short matches
                patterns.append({
                    "rule": text,
                    "source": "claude_code",
                    "imported_at": datetime.now().isoformat(),
                })

        return patterns

    def import_tool_preferences(self) -> Dict[str, Any]:
        """
        Extract tool usage preferences from Claude Code configuration.

        Looks at settings that reveal user workflow preferences:
        - Preferred editor/IDE
        - Shell preferences
        - Permission patterns (what tools are auto-approved)
        """
        preferences = {}

        # Check settings files
        settings_candidates = [
            self.claude_dir / "settings.json",
            self.claude_dir / "settings.local.json",
        ]

        for settings_file in settings_candidates:
            if not settings_file.exists():
                continue
            try:
                with open(settings_file) as f:
                    settings = json.load(f)

                # Extract permission patterns (reveals workflow)
                permissions = settings.get("permissions", {})
                if permissions:
                    allowed = permissions.get("allow", [])
                    if allowed:
                        preferences["auto_approved_tools"] = allowed

                # Extract model preferences
                model = settings.get("model")
                if model:
                    preferences["preferred_model"] = model

                # Extract env vars (workflow context)
                env = settings.get("env", {})
                if env:
                    # Only capture non-sensitive env var names (not values)
                    preferences["env_vars_set"] = list(env.keys())

            except (json.JSONDecodeError, IOError):
                continue

        if not preferences:
            return {"status": "skipped", "reason": "no settings found"}

        # Persist
        output_file = self.cortex_dir / "imported" / "tool_preferences.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(preferences, f, indent=2)

        return {"status": "imported", "keys": list(preferences.keys())}

    def import_session_topics(self) -> Dict[str, Any]:
        """
        Import session topic patterns from Claude Code conversation history.

        Extracts:
        - Common task types (what does the user ask about most?)
        - Time-of-day patterns
        - Session duration patterns
        """
        # Claude Code stores conversations in various locations
        session_dirs = [
            self.claude_dir / "conversations",
            self.claude_dir / "sessions",
            self.claude_dir / "projects",
        ]

        topics = []
        session_count = 0

        for session_dir in session_dirs:
            if not session_dir.exists() or not session_dir.is_dir():
                continue

            for session_file in sorted(session_dir.glob("*.json"))[-50:]:
                try:
                    with open(session_file) as f:
                        session = json.load(f)

                    session_count += 1

                    # Extract first user message as topic indicator
                    messages = session.get("messages", [])
                    if not messages:
                        messages = session.get("conversation", [])

                    for msg in messages[:3]:  # First 3 messages
                        if isinstance(msg, dict):
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if role in ("user", "human") and isinstance(content, str):
                                # Extract topic keywords
                                topic = self._classify_topic(content[:200])
                                if topic:
                                    topics.append(topic)
                                break

                except (json.JSONDecodeError, IOError, KeyError):
                    continue

        if not topics:
            return {"status": "skipped", "reason": "no session data found"}

        # Aggregate topic frequencies
        topic_counts = {}
        for topic in topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

        result = {
            "sessions_analyzed": session_count,
            "topic_distribution": dict(sorted_topics[:20]),
        }

        # Persist
        output_file = self.cortex_dir / "imported" / "session_topics.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        return {"status": "imported", **result}

    def _classify_topic(self, text: str) -> Optional[str]:
        """Classify a user message into a topic category."""
        text_lower = text.lower()

        topic_keywords = {
            "bug_fix": ["fix", "bug", "error", "broken", "crash", "failing"],
            "implementation": ["implement", "add", "create", "build", "write"],
            "refactoring": ["refactor", "clean", "reorganize", "simplify"],
            "testing": ["test", "spec", "coverage", "assertion"],
            "debugging": ["debug", "investigate", "trace", "log"],
            "code_review": ["review", "check", "audit", "assess"],
            "documentation": ["document", "readme", "comment", "explain"],
            "configuration": ["config", "setup", "install", "deploy"],
            "research": ["research", "find", "search", "explore", "how do"],
            "planning": ["plan", "design", "architect", "strategy"],
        }

        for topic, keywords in topic_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return topic

        return None

    def get_import_status(self) -> Dict[str, Any]:
        """Check what has been imported and when."""
        imported_dir = self.cortex_dir / "imported"
        if not imported_dir.exists():
            return {"status": "no_imports", "files": []}

        files = {}
        for f in imported_dir.glob("*.json"):
            try:
                stat = f.stat()
                files[f.stem] = {
                    "path": str(f),
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            except OSError:
                continue

        return {"status": "imported" if files else "no_imports", "files": files}
