"""
Conversation Ingestor - Extract structured digests from Claude Code chat history.

Parses the JSONL conversation files that Claude Code stores in
~/.claude/projects/<project-slug>/<session-id>.jsonl and produces
compact, searchable digests for Cortex's learning and retrieval systems.

Data flow:
  Raw JSONL conversation → parse → extract signals → ConversationDigest → store

Each digest captures:
  - Session metadata (id, project, branch, timestamps, duration)
  - Decisions made (slash commands, tool choices, file changes)
  - User corrections (negative feedback signal)
  - Files touched (read/written/created)
  - Tool usage summary (counts, success rates)
  - Outcome signal (success/partial/failed heuristic)
  - Key topics (extracted from user prompts)
"""

import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Storage paths
DIGESTS_PATH = Path.home() / ".cortex" / "conversation_digests.jsonl"
INGEST_STATE_PATH = Path.home() / ".cortex" / "conversation_ingest_state.json"

# Default conversation directory
CONVERSATIONS_DIR = Path.home() / ".claude" / "projects" / "-Users-jesse-kemp-Dev"

# Correction indicators (reuse from interaction_learner for consistency)
_CORRECTION_PHRASES = [
    "no, ",
    "that's wrong",
    "actually,",
    "i meant",
    "not what i",
    "try again",
    "that didn't work",
    "wrong file",
    "undo",
    "revert",
    "go back",
    "that broke",
    "you misunderstood",
    "that's not right",
    "fix that",
    "redo",
    "don't do",
    "stop",
    "no not",
    "lets not",
    "don't",
]

# Slash command pattern
_SLASH_CMD_RE = re.compile(r"<command-name>/([\w-]+)</command-name>")

# Project detection from cwd
_PROJECT_PATTERNS = {
    "vortex-backend": ["vortex/backend", "vortex\\backend"],
    "vortex-frontend": ["vortex/frontend", "vortex\\frontend"],
    "alpha-arena": ["alpha_arena"],
    "cortex": ["/cortex"],
    "pupil": ["/pupil"],
    "dj-copilot": ["dj-copilot", "dj_copilot"],
    "kempion": ["kempion"],
}


def _detect_project(cwd: str) -> str:
    """Derive project name from working directory."""
    cwd_lower = cwd.lower()
    for project, patterns in _PROJECT_PATTERNS.items():
        if any(p in cwd_lower for p in patterns):
            return project
    return "unknown"


@dataclass
class ConversationDigest:
    """Structured digest of a single Claude Code conversation."""

    session_id: str
    project: str
    git_branch: str
    started_at: str  # ISO-8601
    ended_at: str  # ISO-8601
    duration_minutes: float

    # Content signals
    user_prompt_count: int
    assistant_turn_count: int
    tool_use_count: int
    correction_count: int
    slash_commands: List[str]

    # Files
    files_read: List[str]
    files_written: List[str]

    # Tool breakdown
    tool_summary: Dict[str, int]  # tool_name → count

    # Extracted topics (from user prompts, deduplicated keywords)
    topics: List[str]

    # Outcome heuristic
    outcome: str  # "success", "partial", "abandoned"
    outcome_confidence: float

    # Raw stats
    total_messages: int
    has_subagents: bool

    # Digest metadata
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_path: str = ""
    source_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_search_text(self) -> str:
        """Produce a flat text representation for BM25 indexing."""
        parts = [
            f"project:{self.project}",
            f"branch:{self.git_branch}",
            " ".join(self.topics),
            " ".join(self.slash_commands),
            " ".join(self.files_written[:20]),
            f"outcome:{self.outcome}",
        ]
        return " ".join(parts)


class ConversationParser:
    """Parse a single Claude Code JSONL conversation file into structured messages."""

    def __init__(self, path: Path):
        self.path = path
        self.messages: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}

    def parse(self) -> List[Dict[str, Any]]:
        """Parse JSONL file into list of message dicts."""
        self.messages = []
        try:
            text = self.path.read_text(errors="replace")
        except Exception as e:
            logger.warning(f"Cannot read {self.path}: {e}")
            return []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            if entry_type in ("user", "assistant", "system"):
                self.messages.append(entry)
            elif entry_type == "last-prompt":
                self.metadata["last_prompt"] = entry.get("lastPrompt", "")
                self.metadata["session_id"] = entry.get("sessionId", "")

        return self.messages

    def get_session_id(self) -> str:
        return self.metadata.get("session_id", self.path.stem)

    def get_timestamps(self) -> tuple:
        """Return (first_timestamp, last_timestamp) as ISO strings."""
        timestamps = []
        for msg in self.messages:
            ts = msg.get("timestamp")
            if ts:
                timestamps.append(ts)
        if not timestamps:
            return ("", "")
        return (min(timestamps), max(timestamps))


class DigestExtractor:
    """Extract a ConversationDigest from parsed conversation messages."""

    def extract(
        self,
        messages: List[Dict[str, Any]],
        session_id: str,
        source_path: Path,
        timestamps: tuple,
    ) -> ConversationDigest:
        user_prompts = []
        corrections = 0
        slash_commands = []
        files_read: Set[str] = set()
        files_written: Set[str] = set()
        tool_counts: Counter = Counter()
        tool_use_total = 0
        assistant_turns = 0
        git_branch = ""
        project = "unknown"
        cwd = ""

        # Collect all cwds to vote on project if first cwd is monorepo root
        all_cwds: List[str] = []

        for msg in messages:
            msg_type = msg.get("type")

            # Extract metadata from first message with cwd
            if msg.get("cwd"):
                if not cwd:
                    cwd = msg["cwd"]
                    project = _detect_project(cwd)
                all_cwds.append(msg["cwd"])
            if not git_branch and msg.get("gitBranch"):
                git_branch = msg["gitBranch"]

            if msg_type == "user":
                content = self._get_text_content(msg)
                if content:
                    user_prompts.append(content)

                    # Detect corrections
                    content_lower = content.lower()
                    if any(p in content_lower for p in _CORRECTION_PHRASES):
                        corrections += 1

                    # Detect slash commands
                    cmd_match = _SLASH_CMD_RE.search(content)
                    if cmd_match:
                        slash_commands.append(f"/{cmd_match.group(1)}")

            elif msg_type == "assistant":
                assistant_turns += 1
                # Extract tool uses from assistant content blocks
                content = msg.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_counts[tool_name] += 1
                            tool_use_total += 1

                            # Track file operations
                            tool_input = block.get("input", {})
                            self._track_file_ops(tool_name, tool_input, files_read, files_written)

        # If project is still unknown, infer from most common non-root cwd
        # or from files written/read
        if project == "unknown":
            project = self._infer_project(all_cwds, files_read, files_written)

        # Compute duration
        duration_minutes = 0.0
        if timestamps[0] and timestamps[1]:
            try:
                t0 = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(timestamps[1].replace("Z", "+00:00"))
                duration_minutes = round((t1 - t0).total_seconds() / 60, 1)
            except (ValueError, TypeError):
                pass

        # Extract topics from user prompts
        topics = self._extract_topics(user_prompts)

        # Compute outcome heuristic
        outcome, confidence = self._compute_outcome(
            user_prompts, corrections, tool_use_total, assistant_turns
        )

        # Check for subagents
        subagent_dir = source_path.parent / source_path.stem / "subagents"
        has_subagents = subagent_dir.exists() and any(subagent_dir.iterdir())

        return ConversationDigest(
            session_id=session_id,
            project=project,
            git_branch=git_branch,
            started_at=timestamps[0] or "",
            ended_at=timestamps[1] or "",
            duration_minutes=duration_minutes,
            user_prompt_count=len(user_prompts),
            assistant_turn_count=assistant_turns,
            tool_use_count=tool_use_total,
            correction_count=corrections,
            slash_commands=list(set(slash_commands)),
            files_read=sorted(files_read)[:50],  # cap for storage
            files_written=sorted(files_written)[:50],
            tool_summary=dict(tool_counts.most_common(20)),
            topics=topics[:20],
            outcome=outcome,
            outcome_confidence=confidence,
            total_messages=len(messages),
            has_subagents=has_subagents,
            source_path=str(source_path),
            source_size_bytes=source_path.stat().st_size if source_path.exists() else 0,
        )

    def _get_text_content(self, msg: Dict) -> str:
        """Extract text content from a user or assistant message."""
        content = msg.get("message", {}).get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return " ".join(parts)
        return ""

    def _track_file_ops(
        self,
        tool_name: str,
        tool_input: Dict,
        files_read: Set[str],
        files_written: Set[str],
    ) -> None:
        """Track which files were read/written by tool calls."""
        if tool_name == "Read":
            path = tool_input.get("file_path", "")
            if path:
                files_read.add(self._normalize_path(path))
        elif tool_name in ("Edit", "Write"):
            path = tool_input.get("file_path", "")
            if path:
                files_written.add(self._normalize_path(path))
        elif tool_name == "Bash":
            # Best-effort: detect file paths in bash commands
            cmd = tool_input.get("command", "")
            if ">" in cmd or "tee " in cmd:
                # Heuristic: output redirection likely writes a file
                pass  # Too noisy to extract reliably
        elif tool_name == "Grep" or tool_name == "Glob":
            path = tool_input.get("path", "")
            if path:
                files_read.add(self._normalize_path(path))

    def _normalize_path(self, path: str) -> str:
        """Normalize file paths to be relative to project root."""
        root_dir = os.environ.get("CORTEX_ROOT_DIR", "")
        if root_dir and path.startswith(root_dir):
            return path[len(root_dir):].lstrip("/")
        # Strip common home-relative dev paths
        home = str(Path.home())
        for dev_dir in [f"{home}/Dev/", f"{home}/dev/", f"{home}/projects/"]:
            if path.startswith(dev_dir):
                return path[len(dev_dir):]
        return path

    def _infer_project(
        self,
        cwds: List[str],
        files_read: Set[str],
        files_written: Set[str],
    ) -> str:
        """Infer project from cwd distribution and file paths when initial detection fails."""
        # Vote from all cwds
        project_votes: Counter = Counter()
        for c in cwds:
            p = _detect_project(c)
            if p != "unknown":
                project_votes[p] += 1

        if project_votes:
            return project_votes.most_common(1)[0][0]

        # Fallback: infer from file paths
        all_files = files_read | files_written
        for f in all_files:
            f_lower = f.lower()
            for proj, patterns in _PROJECT_PATTERNS.items():
                if any(p.lstrip("/") in f_lower for p in patterns):
                    project_votes[proj] += 1

        if project_votes:
            return project_votes.most_common(1)[0][0]

        return "unknown"

    def _extract_topics(self, prompts: List[str]) -> List[str]:
        """Extract key topics from user prompts."""
        # Simple approach: extract significant words from first few prompts
        # (avoiding system tags, command syntax, etc.)
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "shall",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "and",
            "but",
            "or",
            "nor",
            "not",
            "so",
            "yet",
            "both",
            "each",
            "every",
            "all",
            "any",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "only",
            "own",
            "same",
            "than",
            "too",
            "very",
            "just",
            "also",
            "now",
            "then",
            "here",
            "there",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "i",
            "me",
            "my",
            "we",
            "our",
            "you",
            "your",
            "he",
            "him",
            "his",
            "she",
            "her",
            "they",
            "them",
            "their",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
            "if",
            "up",
            "let",
            "lets",
            "get",
            "got",
            "make",
            "use",
            "run",
            "see",
            "try",
            "go",
        }

        word_counts: Counter = Counter()
        tag_re = re.compile(r"<[^>]+>")

        for prompt in prompts[:15]:  # First 15 prompts for topic extraction
            # Strip XML tags (system reminders, command tags)
            clean = tag_re.sub("", prompt)
            # Extract words
            words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", clean.lower())
            for w in words:
                if w not in stop_words and len(w) > 2:
                    word_counts[w] += 1

        # Return most common meaningful words
        return [w for w, _ in word_counts.most_common(20) if _ >= 1]

    def _compute_outcome(
        self,
        prompts: List[str],
        corrections: int,
        tool_uses: int,
        assistant_turns: int,
    ) -> tuple:
        """
        Heuristic outcome assessment.

        Returns (outcome, confidence) where outcome is success/partial/abandoned.
        """
        if not prompts:
            return ("abandoned", 0.5)

        # Very short sessions with no tool use → likely abandoned
        if len(prompts) <= 1 and tool_uses == 0:
            return ("abandoned", 0.6)

        # High correction rate → partial
        correction_rate = corrections / max(len(prompts), 1)
        if correction_rate > 0.3:
            return ("partial", 0.7)

        # Check last prompt for positive signals
        last_prompt = prompts[-1].lower() if prompts else ""
        positive_endings = [
            "commit",
            "push",
            "ship",
            "deploy",
            "looks good",
            "perfect",
            "thanks",
            "done",
            "great",
            "nice",
            "awesome",
        ]
        negative_endings = [
            "nevermind",
            "forget it",
            "stop",
            "cancel",
            "undo",
        ]

        if any(p in last_prompt for p in positive_endings):
            return ("success", 0.8)
        if any(p in last_prompt for p in negative_endings):
            return ("abandoned", 0.7)

        # Default: if there was meaningful tool use, assume partial success
        if tool_uses > 3:
            return ("success", 0.6)

        return ("partial", 0.5)


class ConversationIngestor:
    """
    Main entry point for conversation ingestion.

    Handles:
    - Single conversation ingestion (live, from SessionEnd hook)
    - Bulk backfill of all historical conversations
    - Deduplication via ingest state tracking
    """

    def __init__(
        self,
        conversations_dir: Optional[Path] = None,
        digests_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
    ):
        self.conversations_dir = conversations_dir or CONVERSATIONS_DIR
        self.digests_path = digests_path or DIGESTS_PATH
        self.state_path = state_path or INGEST_STATE_PATH
        self.extractor = DigestExtractor()
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load ingest state (tracks which files have been processed)."""
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"ingested_sessions": {}, "last_run": None, "total_ingested": 0}

    def _save_state(self) -> None:
        """Persist ingest state."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state["last_run"] = datetime.now().isoformat()
        self.state_path.write_text(json.dumps(self._state, indent=2))

    def ingest_single(self, transcript_path: str | Path) -> Optional[ConversationDigest]:
        """
        Ingest a single conversation file (live path, e.g. from SessionEnd hook).

        Returns the digest or None if already ingested or invalid.
        """
        path = Path(transcript_path)
        if not path.exists() or not path.suffix == ".jsonl":
            logger.warning(f"Invalid transcript path: {path}")
            return None

        # Dedup check
        path_key = str(path)
        if path_key in self._state["ingested_sessions"]:
            mtime = path.stat().st_mtime
            prev_mtime = self._state["ingested_sessions"][path_key].get("mtime", 0)
            if mtime <= prev_mtime:
                logger.debug(f"Already ingested (unchanged): {path.name}")
                return None

        digest = self._process_file(path)
        if digest:
            self._store_digest(digest)
            self._state["ingested_sessions"][path_key] = {
                "session_id": digest.session_id,
                "mtime": path.stat().st_mtime,
                "ingested_at": datetime.now().isoformat(),
            }
            self._state["total_ingested"] += 1
            self._save_state()
            logger.info(
                f"Ingested conversation {digest.session_id}: "
                f"{digest.user_prompt_count} prompts, {digest.tool_use_count} tools, "
                f"outcome={digest.outcome}"
            )
        return digest

    def backfill(self) -> Dict[str, Any]:
        """
        Ingest all historical conversation files not yet processed.

        Returns summary stats.
        """
        if not self.conversations_dir.exists():
            return {"error": f"Conversations dir not found: {self.conversations_dir}"}

        files = sorted(self.conversations_dir.glob("*.jsonl"))
        ingested = 0
        skipped = 0
        errors = 0
        results = []

        for f in files:
            try:
                digest = self.ingest_single(f)
                if digest:
                    ingested += 1
                    results.append(
                        {
                            "session_id": digest.session_id,
                            "project": digest.project,
                            "prompts": digest.user_prompt_count,
                            "outcome": digest.outcome,
                        }
                    )
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                logger.error(f"Failed to ingest {f.name}: {e}")

        return {
            "total_files": len(files),
            "ingested": ingested,
            "skipped": skipped,
            "errors": errors,
            "results": results,
        }

    def _process_file(self, path: Path) -> Optional[ConversationDigest]:
        """Parse and extract digest from a single JSONL file."""
        parser = ConversationParser(path)
        messages = parser.parse()

        if not messages:
            logger.debug(f"No messages in {path.name}")
            return None

        session_id = parser.get_session_id()
        timestamps = parser.get_timestamps()

        return self.extractor.extract(messages, session_id, path, timestamps)

    def _store_digest(self, digest: ConversationDigest) -> None:
        """Append digest to JSONL storage, replacing any existing entry for this session."""
        self.digests_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing, filter out old entry for this session_id
        existing_lines = []
        if self.digests_path.exists():
            for line in self.digests_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("session_id") == digest.session_id:
                        continue  # Replace with new digest
                    existing_lines.append(line)
                except json.JSONDecodeError:
                    existing_lines.append(line)

        existing_lines.append(json.dumps(digest.to_dict()))
        self.digests_path.write_text("\n".join(existing_lines) + "\n")

    def get_digests(
        self,
        project: Optional[str] = None,
        limit: int = 50,
    ) -> List[ConversationDigest]:
        """Load stored digests, optionally filtered by project."""
        if not self.digests_path.exists():
            return []

        digests = []
        for line in self.digests_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if project and data.get("project") != project:
                    continue
                digests.append(data)
            except json.JSONDecodeError:
                continue

        # Most recent first
        digests.sort(key=lambda d: d.get("ended_at", ""), reverse=True)
        return digests[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Return ingestion statistics."""
        digests = self.get_digests(limit=9999)
        if not digests:
            return {"total": 0}

        projects = Counter(d.get("project", "unknown") for d in digests)
        outcomes = Counter(d.get("outcome", "unknown") for d in digests)
        total_prompts = sum(d.get("user_prompt_count", 0) for d in digests)
        total_tools = sum(d.get("tool_use_count", 0) for d in digests)
        total_corrections = sum(d.get("correction_count", 0) for d in digests)

        return {
            "total_conversations": len(digests),
            "by_project": dict(projects.most_common()),
            "by_outcome": dict(outcomes.most_common()),
            "total_prompts": total_prompts,
            "total_tool_uses": total_tools,
            "total_corrections": total_corrections,
            "correction_rate": round(total_corrections / max(total_prompts, 1), 3),
            "state": {
                "last_run": self._state.get("last_run"),
                "total_ingested": self._state.get("total_ingested", 0),
            },
        }


# --- CLI entry points ---


def ingest_conversation(transcript_path: str) -> Optional[Dict]:
    """Ingest a single conversation. Called from hooks."""
    ingestor = ConversationIngestor()
    digest = ingestor.ingest_single(transcript_path)
    return digest.to_dict() if digest else None


def backfill_conversations() -> Dict[str, Any]:
    """Backfill all historical conversations. Called from CLI."""
    ingestor = ConversationIngestor()
    return ingestor.backfill()


def get_ingest_stats() -> Dict[str, Any]:
    """Get ingestion statistics. Called from CLI."""
    ingestor = ConversationIngestor()
    return ingestor.get_stats()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        print("Starting conversation backfill...")
        result = backfill_conversations()
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = get_ingest_stats()
        print(json.dumps(stats, indent=2))
    elif len(sys.argv) > 1:
        # Single file ingestion
        result = ingest_conversation(sys.argv[1])
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No digest produced (already ingested or empty)")
    else:
        print("Usage: conversation_ingestor.py <backfill|stats|<transcript_path>>")
