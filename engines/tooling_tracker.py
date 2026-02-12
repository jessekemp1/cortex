"""
Cortex Tooling Intelligence Engine

Tracks and provides queryable intelligence about Claude Code tooling configuration:
- Hook configurations and changes
- Command definitions and updates
- Memory content and evolution
- Agent configurations
- Settings changes

This enables Cortex to answer questions like:
- "What hooks do I currently have configured?"
- "When did I last update my /test command?"
- "Show me my hook configuration history"
- "What commands use the test-orchestrator agent?"
"""

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolingChange(BaseModel):
    """Represents a change to Claude Code tooling."""

    category: str = Field(description="Category: settings, command, hook, memory, agent, skill")
    name: str = Field(description="Name of the tooling component")
    file_path: str = Field(description="Full path to the file")
    change_type: str = Field(description="Type: created, modified, deleted")
    timestamp: str = Field(description="ISO timestamp of change")
    session_id: str = Field(description="Claude Code session ID")
    cwd: str = Field(description="Working directory when changed")


class ToolingSnapshot(BaseModel):
    """Current state of tooling configuration."""

    settings: Optional[Dict[str, Any]] = None
    commands: List[str] = Field(default_factory=list)
    hooks: List[str] = Field(default_factory=list)
    memories: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


class ToolingTracker:
    """Tracks Claude Code tooling changes and provides intelligence."""

    def __init__(self, claude_dir: Optional[Path] = None):
        self.tooling_log = Path.home() / ".cortex" / "tooling_changes.jsonl"
        self.claude_dir = claude_dir or self._find_claude_dir()

    def _find_claude_dir(self) -> Path:
        """
        Find the .claude directory dynamically.

        Tries in order:
        1. CLAUDE_DIR environment variable
        2. Git repository root + .claude
        3. Current working directory + .claude
        4. Fallback to ~/Dev/.claude (for backward compatibility)
        """
        # Try environment variable first
        if "CLAUDE_DIR" in os.environ:
            claude_dir = Path(os.environ["CLAUDE_DIR"])
            if claude_dir.exists():
                return claude_dir

        # Try git root + .claude
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                git_root = Path(result.stdout.strip())
                claude_dir = git_root / ".claude"
                if claude_dir.exists():
                    return claude_dir
        except Exception:
            pass

        # Try current working directory + .claude
        cwd_claude = Path.cwd() / ".claude"
        if cwd_claude.exists():
            return cwd_claude

        # Fallback to legacy path for backward compatibility
        return Path.home() / "Dev" / ".claude"

    def get_recent_changes(
        self, days: int = 7, category: Optional[str] = None
    ) -> List[ToolingChange]:
        """Get recent tooling changes."""
        if not self.tooling_log.exists():
            return []

        cutoff = datetime.now() - timedelta(days=days)
        changes = []

        with open(self.tooling_log) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    timestamp = datetime.fromisoformat(data["timestamp"])

                    if timestamp < cutoff:
                        continue

                    if category and data.get("category") != category:
                        continue

                    changes.append(ToolingChange(**data))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        return sorted(changes, key=lambda x: x.timestamp, reverse=True)

    def get_current_snapshot(self) -> ToolingSnapshot:
        """Get current state of all tooling."""
        snapshot = ToolingSnapshot()

        # Load settings
        settings_path = self.claude_dir / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path) as f:
                    snapshot.settings = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # List commands
        commands_dir = self.claude_dir / "commands"
        if commands_dir.exists():
            snapshot.commands = sorted([f.stem for f in commands_dir.glob("*.md") if f.is_file()])

        # List hooks
        hooks_dir = self.claude_dir / "hooks"
        if hooks_dir.exists():
            snapshot.hooks = sorted([f.stem for f in hooks_dir.glob("*.py") if f.is_file()])

        # List memories
        memories_dir = self.claude_dir / "memories"
        if memories_dir.exists():
            snapshot.memories = sorted([f.stem for f in memories_dir.glob("*.md") if f.is_file()])

        # List agents
        agents_dir = self.claude_dir / "agents"
        if agents_dir.exists():
            snapshot.agents = sorted([f.stem for f in agents_dir.glob("*.md") if f.is_file()])

        return snapshot

    def get_hook_config(self) -> Dict[str, List[str]]:
        """Extract hook configuration from settings."""
        snapshot = self.get_current_snapshot()

        if not snapshot.settings:
            return {}

        hooks_config = snapshot.settings.get("hooks", {})
        result = {}

        for event_type, matchers in hooks_config.items():
            hooks_list = []

            if not isinstance(matchers, list):
                continue

            for matcher_group in matchers:
                if not isinstance(matcher_group, dict):
                    continue

                for hook_def in matcher_group.get("hooks", []):
                    if not isinstance(hook_def, dict):
                        continue

                    command = hook_def.get("command", "")
                    if command:
                        # Extract just the filename
                        hook_name = Path(command.split()[0]).stem
                        is_async = hook_def.get("async", False)
                        timeout = hook_def.get("timeout", "?")

                        hooks_list.append(f"{hook_name} (async={is_async}, timeout={timeout}s)")

            result[event_type] = hooks_list

        return result

    def get_change_history(self, name: str, category: Optional[str] = None) -> List[ToolingChange]:
        """Get change history for a specific tooling component."""
        if not self.tooling_log.exists():
            return []

        changes = []

        with open(self.tooling_log) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())

                    if data.get("name") != name:
                        continue

                    if category and data.get("category") != category:
                        continue

                    changes.append(ToolingChange(**data))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        return sorted(changes, key=lambda x: x.timestamp, reverse=True)

    def get_intelligence_summary(self) -> str:
        """Generate a human-readable summary of tooling intelligence."""
        snapshot = self.get_current_snapshot()
        recent_changes = self.get_recent_changes(days=7)
        hook_config = self.get_hook_config()

        lines = [
            "=== Claude Code Tooling Intelligence ===",
            "",
            "## Current Configuration",
            f"Commands: {len(snapshot.commands)}",
            f"Hooks: {len(snapshot.hooks)}",
            f"Memories: {len(snapshot.memories)}",
            f"Agents: {len(snapshot.agents)}",
            "",
            "## Active Hook Events",
        ]

        for event_type, hooks in hook_config.items():
            lines.append(f"  {event_type}:")
            for hook in hooks:
                lines.append(f"    - {hook}")

        if recent_changes:
            lines.append("")
            lines.append(f"## Recent Changes (Last 7 Days): {len(recent_changes)}")
            for change in recent_changes[:10]:  # Show latest 10
                timestamp = datetime.fromisoformat(change.timestamp)
                time_str = timestamp.strftime("%Y-%m-%d %H:%M")
                lines.append(
                    f"  [{time_str}] {change.change_type} {change.category}: {change.name}"
                )

        return "\n".join(lines)

    def query(self, question: str) -> str:
        """
        Answer natural language questions about tooling.

        Supported queries:
        - "What hooks do I have?" / "List my hooks"
        - "Show my hook configuration" / "Hook config"
        - "What commands are available?" / "List commands"
        - "Recent changes" / "What changed recently?"
        - "History of <name>" / "Changes to <name>"
        """
        question_lower = question.lower()

        # Hook configuration queries
        if any(
            phrase in question_lower
            for phrase in ["hook config", "hook configuration", "what hooks"]
        ):
            config = self.get_hook_config()
            lines = ["Current Hook Configuration:", ""]
            for event_type, hooks in config.items():
                lines.append(f"{event_type}:")
                for hook in hooks:
                    lines.append(f"  - {hook}")
            return "\n".join(lines)

        # Command listing
        if any(
            phrase in question_lower
            for phrase in ["list commands", "what commands", "available commands"]
        ):
            snapshot = self.get_current_snapshot()
            return f"Available commands ({len(snapshot.commands)}):\n" + "\n".join(
                f"  /{cmd}" for cmd in snapshot.commands
            )

        # Recent changes
        if any(phrase in question_lower for phrase in ["recent changes", "what changed"]):
            changes = self.get_recent_changes(days=7)
            if not changes:
                return "No tooling changes in the last 7 days."

            lines = [f"Recent tooling changes ({len(changes)}):"]
            for change in changes[:15]:
                timestamp = datetime.fromisoformat(change.timestamp)
                time_str = timestamp.strftime("%Y-%m-%d %H:%M")
                lines.append(
                    f"  [{time_str}] {change.change_type} {change.category}: {change.name}"
                )
            return "\n".join(lines)

        # Change history for specific component
        if "history of" in question_lower or "changes to" in question_lower:
            # Extract component name (heuristic)
            for keyword in ["history of", "changes to"]:
                if keyword in question_lower:
                    name = question_lower.split(keyword)[1].strip().strip("'\"")
                    history = self.get_change_history(name)

                    if not history:
                        return f"No change history found for '{name}'"

                    lines = [f"Change history for '{name}':"]
                    for change in history:
                        timestamp = datetime.fromisoformat(change.timestamp)
                        time_str = timestamp.strftime("%Y-%m-%d %H:%M")
                        lines.append(f"  [{time_str}] {change.change_type}")
                    return "\n".join(lines)

        # Default: full summary
        return self.get_intelligence_summary()


def get_tracker() -> ToolingTracker:
    """Get or create singleton ToolingTracker instance."""
    return ToolingTracker()


# CLI interface for testing
if __name__ == "__main__":
    import sys

    tracker = get_tracker()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(tracker.query(query))
    else:
        print(tracker.get_intelligence_summary())
