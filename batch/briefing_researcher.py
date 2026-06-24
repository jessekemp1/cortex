#!/usr/bin/env python3
"""
Intelligence Briefing Researcher

Submits structured research topics to the Batch API for overnight processing,
then synthesizes results into a daily intelligence briefing.

Usage:
    # Submit research batch (run evening before)
    python -m cortex.batch.briefing_researcher submit

    # Collect results and generate briefing
    python -m cortex.batch.briefing_researcher collect <batch_id>

    # Full cycle (submit + poll + synthesize)
    python -m cortex.batch.briefing_researcher run

Integration:
    from cortex.batch.briefing_researcher import BriefingResearcher
    researcher = BriefingResearcher()
    result = researcher.submit_briefing_batch()
    # ... later ...
    briefing = researcher.collect_and_synthesize(result["batch_id"])
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .batch_api_client import BatchAPIClient, BatchRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Research topic definitions
# ---------------------------------------------------------------------------

BRIEFING_TRACKS = [
    # Track 1: Anthropic / Claude ecosystem
    {
        "id": "claude_ecosystem",
        "topic": "Claude Code, Claude API, and Anthropic product updates",
        "context": (
            "Focus on: Claude Code releases (changelog, new tools, agent SDK changes), "
            "Claude model updates (Sonnet/Opus/Haiku releases, pricing changes), "
            "Anthropic blog posts and developer docs changes. "
            "Include version numbers, breaking changes, and new capabilities. "
            "Check github.com/anthropics/claude-code releases and anthropic.com/news."
        ),
        "priority": "high",
        "relevance_filter": [
            "claude code",
            "anthropic",
            "claude api",
            "model context protocol",
            "claude sonnet",
            "claude opus",
            "claude haiku",
            "agent sdk",
        ],
    },
    # Track 2: Agent orchestration frameworks
    {
        "id": "agent_frameworks",
        "topic": "AI agent orchestration frameworks and multi-agent systems",
        "context": (
            "Track: CrewAI, AutoGen/Semantic Kernel, Google ADK, LangGraph, "
            "Composio, AgentStack, Mastra. Focus on releases in the last 7 days, "
            "new capabilities, breaking changes, and adoption metrics (stars, downloads). "
            "Highlight anything that changes the build-vs-buy calculus for agent orchestration."
        ),
        "priority": "high",
        "relevance_filter": [
            "crewai",
            "autogen",
            "langgraph",
            "google adk",
            "agent framework",
            "multi-agent",
            "agent orchestration",
            "mastra",
            "composio",
        ],
    },
    # Track 3: MCP / A2A protocol ecosystem
    {
        "id": "protocol_ecosystem",
        "topic": "Model Context Protocol (MCP) and Agent-to-Agent (A2A) protocol developments",
        "context": (
            "Track: MCP spec changes, new MCP servers/tools, A2A protocol releases, "
            "Linux Foundation Agentic AI Foundation announcements, "
            "enterprise MCP adoption patterns, new connectors. "
            "Focus on what's shipping, not what's announced."
        ),
        "priority": "high",
        "relevance_filter": [
            "model context protocol",
            "mcp",
            "a2a protocol",
            "agentic ai foundation",
            "mcp server",
            "tool use",
            "function calling",
        ],
    },
    # Track 4: AI engineering practices
    {
        "id": "ai_engineering",
        "topic": "AI engineering practices, evaluation, and production patterns",
        "context": (
            "Track: AI evaluation frameworks (Braintrust, Arize, Langfuse), "
            "prompt engineering advances, RAG improvements, code generation benchmarks, "
            "production deployment patterns, cost optimization techniques. "
            "Focus on practitioner-relevant insights, not academic benchmarks."
        ),
        "priority": "medium",
        "relevance_filter": [
            "ai engineering",
            "llm evaluation",
            "prompt engineering",
            "rag",
            "code generation",
            "llm ops",
            "ai production",
        ],
    },
    # Track 5: Cortex-relevant research (memory, learning, orchestration)
    {
        "id": "cortex_research",
        "topic": "Agent memory systems, trajectory learning, and orchestration intelligence",
        "context": (
            "Track: Papers and repos on agent memory (episodic, semantic, procedural), "
            "trajectory-based learning, skill extraction from interaction traces, "
            "memory admission control, causal retrieval. "
            "Cross-reference with cortex research_directives.md priorities. "
            "Sources: arxiv cs.AI/cs.CL/cs.SE, GitHub trending agent/memory repos."
        ),
        "priority": "high",
        "relevance_filter": [
            "agent memory",
            "trajectory learning",
            "skill extraction",
            "memory admission",
            "causal retrieval",
            "episodic memory",
            "orchestration",
            "task routing",
        ],
    },
    # Track 6: Hardware / inference economics
    {
        "id": "inference_economics",
        "topic": "AI inference hardware, cost trends, and deployment economics",
        "context": (
            "Track: NVIDIA (Rubin, Blackwell availability), AMD MI350, "
            "inference cost per token trends across providers, "
            "open-weight model releases that change self-hosting calculus, "
            "serverless inference platforms. Focus on what affects build decisions."
        ),
        "priority": "low",
        "relevance_filter": [
            "nvidia",
            "inference cost",
            "gpu",
            "token cost",
            "self-hosting",
            "open weight",
            "llama",
            "mistral",
        ],
    },
    # Track 7: Competitive landscape for Cortex
    {
        "id": "cortex_competitive",
        "topic": "Products competing with Cortex: Mem0, Letta, Zep, Claude native memory",
        "context": (
            "Track: Mem0 releases and roadmap, Letta (MemGPT) updates, "
            "Zep memory layer, any Claude/OpenAI native memory announcements. "
            "Assess: does this commoditize Cortex's unique layers "
            "(anti-patterns, outcome learning, goal pipeline, orchestration)? "
            "Flag anything that crosses the disruption threshold."
        ),
        "priority": "high",
        "relevance_filter": [
            "mem0",
            "memgpt",
            "letta",
            "zep",
            "agent memory product",
            "persistent memory",
            "claude memory",
        ],
    },
]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

BRIEFING_SYSTEM_PROMPT = """You are an intelligence analyst producing a daily technology briefing.

Rules:
1. Lead with WHAT SHIPPED, not what was announced. Announcements without artifacts are noted but deprioritized.
2. Include version numbers, dates, and links where possible.
3. For each finding, assess: does this affect our build decisions in the next 30 days?
4. Flag anything that changes the competitive landscape for agent memory + orchestration systems.
5. Be terse. No filler. Data over opinion.
6. End with 2-3 specific "watch this week" items.

Output format (markdown):
## [Track Name]
### Shipped
- [item]: [1-2 sentence description]. [Link if available]
### Announced (not yet shipped)
- [item]: [description]
### Impact Assessment
[1-2 sentences on build-decision relevance]
### Watch This Week
- [specific thing to monitor]
"""

BRIEFING_USER_PROMPT_TEMPLATE = """Research Track: {topic}

Scope: {context}

Priority: {priority}

Time window: Last 7 days from {date}.

Produce a structured intelligence brief for this track following the system prompt format.
Include URLs where possible. Be specific about versions, dates, and metrics."""


# ---------------------------------------------------------------------------
# BriefingResearcher class
# ---------------------------------------------------------------------------


class BriefingResearcher:
    """Orchestrates intelligence briefing research via Batch API.

    Lifecycle:
        1. submit_briefing_batch() — builds prompts from BRIEFING_TRACKS, submits to Batch API
        2. collect_and_synthesize(batch_id) — polls results, merges into single briefing
        3. save_briefing(briefing) — writes to ~/.cortex/briefings/ and portfolio memory

    Can also run end-to-end via run().
    """

    def __init__(self, tracks: Optional[List[Dict]] = None):
        self.batch_client = BatchAPIClient()
        self.tracks = tracks or BRIEFING_TRACKS
        self.briefings_dir = Path.home() / ".cortex" / "briefings"
        self.briefings_dir.mkdir(parents=True, exist_ok=True)

        # Portfolio memory for cross-session persistence
        try:
            from cortex.portfolio_memory import PortfolioMemory

            self.portfolio = PortfolioMemory()
        except Exception:
            self.portfolio = None

    def submit_briefing_batch(self) -> Dict[str, Any]:
        """Submit all tracks as a single batch.

        Returns:
            {"batch_id": str, "submitted_count": int, "tracks": [str]}
        """
        today = datetime.now().strftime("%Y-%m-%d")
        requests = []

        for track in self.tracks:
            user_prompt = BRIEFING_USER_PROMPT_TEMPLATE.format(
                topic=track["topic"],
                context=track["context"],
                priority=track["priority"],
                date=today,
            )
            requests.append(
                BatchRequest(
                    custom_id=f"briefing_{today}_{track['id']}",
                    params={
                        "model": "claude-sonnet-4-6",
                        "messages": [{"role": "user", "content": user_prompt}],
                        "system": BRIEFING_SYSTEM_PROMPT,
                        "max_tokens": 4096,
                    },
                )
            )

        batch_id = self.batch_client.submit_batch(
            requests,
            description=f"Intelligence briefing {today}: {len(requests)} tracks",
        )

        logger.info(f"Briefing batch submitted: {batch_id} ({len(requests)} tracks)")
        return {
            "batch_id": batch_id,
            "submitted_count": len(requests),
            "tracks": [t["id"] for t in self.tracks],
            "submitted_at": datetime.now().isoformat(),
        }

    def collect_and_synthesize(self, batch_id: str) -> Dict[str, Any]:
        """Poll batch results and merge into a single briefing document.

        Args:
            batch_id: From submit_briefing_batch().

        Returns:
            {"briefing_file": str, "track_results": dict, "summary": str}
        """
        results = self.batch_client.poll_results(batch_id)
        today = datetime.now().strftime("%Y-%m-%d")

        track_reports = {}
        errors = []

        for result in results:
            track_id = result.custom_id.replace(f"briefing_{today}_", "")

            if result.status == "succeeded":
                message = result.result.get("message", {})
                content_list = message.get("content", [{}])
                text = content_list[0].get("text", "") if content_list else ""
                track_reports[track_id] = text
            else:
                error_msg = result.result.get("error", {}).get("message", "Unknown")
                errors.append(f"{track_id}: {error_msg}")
                logger.warning(f"Track {track_id} failed: {error_msg}")

        # Build merged briefing
        briefing = self._merge_briefing(today, track_reports, errors)
        briefing_file = self.save_briefing(briefing, today)

        return {
            "briefing_file": str(briefing_file),
            "tracks_completed": len(track_reports),
            "tracks_failed": len(errors),
            "errors": errors,
            "summary": self._extract_watch_items(briefing),
        }

    def run(self) -> Dict[str, Any]:
        """Full cycle: submit → poll → synthesize → save.

        Blocks until batch completes (typically 5-15 min for 7 tracks).
        """
        submission = self.submit_briefing_batch()
        result = self.collect_and_synthesize(submission["batch_id"])
        result["batch_id"] = submission["batch_id"]
        return result

    def save_briefing(self, content: str, date_str: str) -> Path:
        """Write briefing to disk and portfolio memory."""
        filepath = self.briefings_dir / f"briefing_{date_str}.md"
        filepath.write_text(content)
        logger.info(f"Briefing saved: {filepath}")

        if self.portfolio:
            try:
                self.portfolio.store_memory(
                    key=f"briefing_{date_str}",
                    content=content,
                    metadata={
                        "type": "intelligence_briefing",
                        "date": date_str,
                        "source": "briefing_researcher",
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to store briefing in portfolio: {e}")

        return filepath

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _merge_briefing(
        self,
        date_str: str,
        track_reports: Dict[str, str],
        errors: List[str],
    ) -> str:
        """Merge per-track reports into a single briefing document."""
        # Track ordering matches priority
        track_order = [t["id"] for t in self.tracks]

        sections = [
            f"# Intelligence Briefing — {date_str}",
            f"*Generated {datetime.now().strftime('%H:%M')} | "
            f"{len(track_reports)} tracks completed, {len(errors)} failed*\n",
        ]

        for track_id in track_order:
            if track_id in track_reports:
                # Find track metadata
                track_meta = next((t for t in self.tracks if t["id"] == track_id), None)
                label = track_meta["topic"] if track_meta else track_id
                sections.append(f"---\n\n## {label}\n")
                sections.append(track_reports[track_id])
                sections.append("")

        if errors:
            sections.append("---\n\n## Errors\n")
            for err in errors:
                sections.append(f"- {err}")
            sections.append("")

        # Append focus recommendations stub
        sections.append("---\n\n## Focus Recommendations\n")
        sections.append(
            "*Cross-track synthesis — review watch items above and "
            "prioritize based on current GOALS.md sprint.*\n"
        )

        return "\n".join(sections)

    def _extract_watch_items(self, briefing: str) -> str:
        """Pull out 'Watch This Week' lines for the summary."""
        lines = briefing.split("\n")
        watch_items = []
        in_watch = False
        for line in lines:
            if "Watch This Week" in line:
                in_watch = True
                continue
            if in_watch:
                if line.startswith("- "):
                    watch_items.append(line)
                elif line.startswith("#") or line.startswith("---"):
                    in_watch = False
        return "\n".join(watch_items) if watch_items else "No watch items extracted."


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    researcher = BriefingResearcher()

    if len(sys.argv) < 2 or sys.argv[1] == "run":
        result = researcher.run()
        print(f"\nBriefing saved: {result['briefing_file']}")
        print(f"Tracks: {result['tracks_completed']} ok, {result['tracks_failed']} failed")
        print(f"\nWatch items:\n{result['summary']}")

    elif sys.argv[1] == "submit":
        result = researcher.submit_briefing_batch()
        print(f"Batch submitted: {result['batch_id']}")
        print(f"Tracks: {', '.join(result['tracks'])}")
        print(f"\nRun: python -m cortex.batch.briefing_researcher collect {result['batch_id']}")

    elif sys.argv[1] == "collect" and len(sys.argv) > 2:
        batch_id = sys.argv[2]
        result = researcher.collect_and_synthesize(batch_id)
        print(f"\nBriefing saved: {result['briefing_file']}")
        print(f"\nWatch items:\n{result['summary']}")

    else:
        print("Usage: python -m cortex.batch.briefing_researcher [submit|collect <batch_id>|run]")
        sys.exit(1)


if __name__ == "__main__":
    main()
