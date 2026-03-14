#!/usr/bin/env python3
"""
Cortex Research Agent (CRA) — Discovery Engine

Scans AI frontier sources, scores discoveries against Cortex capabilities,
and emits findings that feed into the supervisor's work intake pipeline.

Architecture:
  Discovery → Assessment → Proposal → WorkItem emission

Storage: ~/.cortex/research/
  discoveries.jsonl   — append-only raw findings
  assessments.jsonl   — scored assessments with recommendations
  proposals/          — integration plans (markdown, Golden Spec format)
  adopted.jsonl       — shipped integrations + measured outcomes
  dismissed.jsonl     — rejected findings with reasoning (prevents re-eval)

Usage:
    agent = CortexResearchAgent()
    agent.scan()                    # Run discovery + assessment
    agent.digest()                  # Generate weekly summary
    agent.get_pending_proposals()   # For supervisor intake

Batch usage:
    python -m cortex.engines.research_agent
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RESEARCH_DIR = Path.home() / ".cortex" / "research" / "cra"
BRIEFS_DIR = Path.home() / "Dev" / "cortex" / "research_briefs"
DIRECTIVES_PATH = Path.home() / "Dev" / "cortex" / "research_directives.md"

# Cortex capability vectors — discoveries are scored against these
CAPABILITY_VECTORS: Dict[str, str] = {
    "memory_retrieval": "BM25 embedding hybrid search pattern matching semantic retrieval",
    "outcome_learning": "implicit feedback outcome routing model selection quality score",
    "task_orchestration": "work discovery routing dispatch model tier supervisor pipeline",
    "anti_patterns": "failure prevention pattern memory recurring bugs gotcha trigger",
    "context_optimization": "token budget lost-in-middle attention reordering deferred loading",
    "goal_tracking": "GOALS.md parsing work items priority scheduling velocity",
    "research_automation": "arxiv discovery frontier scanning auto-research integration",
}

# Sources ranked by signal quality (existential threats first)
SOURCES = {
    "anthropic_native_memory": {
        "label": "Anthropic Memory/Native API Signals",
        "queries": [
            "anthropic memory API",
            "claude persistent memory",
            "anthropic developer changelog memory",
        ],
        "signal_quality": "existential",
        "frequency": "weekly",
        "threat_monitors": True,
    },
    "mem0_evolution": {
        "label": "Mem0 Releases & Orchestration Signals",
        "queries": [
            "mem0 orchestration",
            "mem0 task routing",
            "mem0ai/mem0 releases",
        ],
        "signal_quality": "existential",
        "frequency": "weekly",
        "threat_monitors": True,
    },
    "arxiv_agent_memory": {
        "label": "arXiv Agent Memory Research",
        "queries": [
            "arxiv agent memory architecture",
            "arxiv trajectory memory LLM",
            "arxiv memory admission control",
        ],
        "signal_quality": "high",
        "frequency": "daily",
    },
    "github_trending": {
        "label": "GitHub Trending (agent, memory, MCP)",
        "queries": [
            "github trending agent memory",
            "github trending MCP server",
            "github trending LLM orchestration",
        ],
        "signal_quality": "medium",
        "frequency": "weekly",
    },
    "anthropic_tooling": {
        "label": "Anthropic Claude Code & MCP Updates",
        "queries": [
            "anthropic claude code update",
            "MCP protocol update",
            "claude code changelog",
        ],
        "signal_quality": "very_high",
        "frequency": "weekly",
    },
    "cursor_evolution": {
        "label": "Cursor Agent Mode & Memory",
        "queries": [
            "cursor agent mode update",
            "cursor cross-session memory",
            "cursor parallel agents",
        ],
        "signal_quality": "medium",
        "frequency": "weekly",
        "threat_monitors": True,
    },
    "mcp_registry": {
        "label": "MCP Server Registry",
        "queries": [
            "new MCP servers",
            "MCP server registry agent",
        ],
        "signal_quality": "high",
        "frequency": "weekly",
    },
    "autoresearch_ecosystem": {
        "label": "Karpathy autoresearch & Autonomous Experiment Loops",
        "queries": [
            "karpathy autoresearch",
            "autonomous ML experiment agent",
            "autoresearch fork extension",
        ],
        "signal_quality": "high",
        "frequency": "weekly",
    },
}


@dataclass
class Discovery:
    """A single research finding from any source."""

    id: str
    source: str  # Key from SOURCES
    title: str
    url: str
    summary: str  # 2-3 sentence summary
    discovered_at: str  # ISO datetime
    relevance_scores: Dict[str, float]  # Per-capability scores (0-1)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def max_relevance(self) -> float:
        return max(self.relevance_scores.values()) if self.relevance_scores else 0.0

    @property
    def top_capability(self) -> str:
        if not self.relevance_scores:
            return "unknown"
        return max(self.relevance_scores, key=lambda k: self.relevance_scores[k])


@dataclass
class Assessment:
    """Scored assessment of a discovery's impact on Cortex."""

    discovery_id: str
    title: str
    source_url: str
    disruption_risk: float  # 0-1: how much does this threaten our approach?
    adoption_effort: str  # trivial | small | medium | large | rewrite
    expected_impact: str  # incremental | significant | transformative
    affected_modules: List[str]
    integration_approach: str  # 1-paragraph plan
    risks: List[str]
    recommendation: str  # adopt | monitor | dismiss
    reasoning: str
    assessed_at: str  # ISO datetime
    relevance_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def is_urgent(self) -> bool:
        """High disruption + achievable effort = urgent adoption."""
        return self.disruption_risk > 0.7 and self.adoption_effort in (
            "trivial",
            "small",
            "medium",
        )

    @property
    def priority_score(self) -> float:
        """Numeric score for ranking (higher = more important)."""
        impact_weights = {
            "transformative": 3.0,
            "significant": 2.0,
            "incremental": 1.0,
        }
        effort_weights = {
            "trivial": 1.0,
            "small": 0.8,
            "medium": 0.6,
            "large": 0.3,
            "rewrite": 0.1,
        }
        impact = impact_weights.get(self.expected_impact, 1.0)
        effort = effort_weights.get(self.adoption_effort, 0.5)
        return (impact * effort) + self.disruption_risk


@dataclass
class ProposalResult:
    """Result of a CRA experiment loop iteration (autoresearch-inspired).

    Each proposal that enters the experiment loop produces one of these,
    which feeds into adoption_outcome_score() for keep/discard decision.
    """

    proposal_title: str
    tests_passing: int
    tests_total: int
    capability_score_delta: float  # 0-1: improvement in target capability
    addresses_threat: bool  # Does this address a Priority 1 threat?
    branch_name: str = ""
    error: str = ""

    @property
    def test_pass_rate(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return self.tests_passing / self.tests_total


def adoption_outcome_score(result: ProposalResult) -> float:
    """Single scalar metric for the CRA experiment loop.

    Inspired by Karpathy's autoresearch val_bpb — one number to
    decide keep/discard. Higher is better. Range: 0.0-1.0.

    Weights:
      50% test pass rate — nothing ships if tests break
      30% capability gain — did this actually improve something?
      20% threat response — existential threats get priority
    """
    test_weight = 0.5 * result.test_pass_rate
    capability_weight = 0.3 * min(max(result.capability_score_delta, 0.0), 1.0)
    threat_weight = 0.2 * (1.0 if result.addresses_threat else 0.0)
    return test_weight + capability_weight + threat_weight


def load_research_directives(path: Optional[Path] = None) -> str:
    """Load human-authored research directives (Karpathy program.md pattern).

    Returns the directives content, or empty string if file doesn't exist.
    """
    directives_path = path or DIRECTIVES_PATH
    if directives_path.exists():
        return directives_path.read_text(encoding="utf-8")
    logger.warning("research_directives.md not found at %s, using defaults", directives_path)
    return ""


def parse_directives_priorities(directives_text: str) -> Dict[str, List[str]]:
    """Extract priority tiers and items from research_directives.md.

    Returns {"priority_1": [...], "priority_2": [...], "priority_3": [...]}.
    """
    priorities: Dict[str, List[str]] = {
        "priority_1": [],
        "priority_2": [],
        "priority_3": [],
    }
    current_priority = ""

    for line in directives_text.splitlines():
        if "### Priority 1" in line:
            current_priority = "priority_1"
        elif "### Priority 2" in line:
            current_priority = "priority_2"
        elif "### Priority 3" in line:
            current_priority = "priority_3"
        elif line.startswith("## Constraints") or line.startswith("## Evaluation"):
            current_priority = ""
        elif current_priority and line.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
            item = line.strip()
            if "**" in item:
                bold_start = item.index("**") + 2
                bold_end = item.index("**", bold_start)
                item = item[bold_start:bold_end]
            priorities[current_priority].append(item)

    return priorities


class CortexResearchAgent:
    """
    CRA: Discovers, assesses, and proposes research integrations for Cortex.

    Designed to run via:
    1. Batch queue (overnight, 50% cost savings)
    2. CLI command (cortex research scan/assess/propose)
    3. Slash command (/frontier-scout extended mode)

    Experiment loop (autoresearch-inspired):
      read research_directives.md -> propose integration -> batch prototype ->
      evaluate adoption_outcome_score -> keep/discard -> repeat
    """

    def __init__(self, research_dir: Optional[Path] = None):
        self.research_dir = research_dir or RESEARCH_DIR
        self.research_dir.mkdir(parents=True, exist_ok=True)
        (self.research_dir / "proposals").mkdir(exist_ok=True)

        self.discoveries_path = self.research_dir / "discoveries.jsonl"
        self.assessments_path = self.research_dir / "assessments.jsonl"
        self.adopted_path = self.research_dir / "adopted.jsonl"
        self.dismissed_path = self.research_dir / "dismissed.jsonl"

    # ── Discovery ──

    def get_sources(self) -> Dict[str, Any]:
        """Return scan sources for external callers."""
        return SOURCES

    def get_capability_vectors(self) -> Dict[str, str]:
        """Return capability vectors for relevance scoring."""
        return CAPABILITY_VECTORS

    def get_threat_sources(self) -> Dict[str, Any]:
        """Return only sources flagged as existential threats."""
        return {k: v for k, v in SOURCES.items() if v.get("threat_monitors")}

    def ingest_discovery(self, discovery: Discovery) -> None:
        """Append a discovery to the JSONL log."""
        # Check if already exists (by URL dedup)
        existing_urls = self._get_existing_urls()
        if discovery.url in existing_urls:
            logger.info("Skipping duplicate discovery: %s", discovery.url)
            return

        with open(self.discoveries_path, "a") as f:
            f.write(json.dumps(asdict(discovery)) + "\n")
        logger.info("Ingested discovery: %s", discovery.title)

    def ingest_from_brief(self, brief_path: Path) -> List[Discovery]:
        """Parse a research brief markdown file into Discovery objects.

        Handles the structured format used by the frontier scout / intel briefs.
        """
        if not brief_path.exists():
            logger.warning("Brief not found: %s", brief_path)
            return []

        text = brief_path.read_text(encoding="utf-8")
        discoveries: List[Discovery] = []

        # Extract date from filename or frontmatter
        date_str = datetime.now(tz=timezone.utc).isoformat()
        for line in text.splitlines()[:5]:
            if "date:" in line.lower():
                parts = line.split(":")
                if len(parts) >= 2:
                    date_str = parts[-1].strip().split("|")[0].strip()
                    break

        # Parse sections — each ### heading is a potential finding
        current_section = ""
        current_title = ""
        current_content: List[str] = []
        current_source_url = ""

        for line in text.splitlines():
            if line.startswith("## "):
                current_section = line.lstrip("#").strip()
                continue

            if line.startswith("**") and line.endswith("**"):
                # Save previous finding if we have one
                if current_title and current_content:
                    discovery = self._parse_finding_block(
                        title=current_title,
                        content="\n".join(current_content),
                        section=current_section,
                        source_url=current_source_url,
                        date_str=date_str,
                    )
                    if discovery:
                        discoveries.append(discovery)

                current_title = line.strip("*").strip()
                current_content = []
                current_source_url = ""
                continue

            if line.startswith("Source:"):
                # Extract URL from markdown link
                url_match = line.split("(")[-1].rstrip(")")
                if url_match.startswith("http"):
                    current_source_url = url_match

            current_content.append(line)

        # Don't forget the last finding
        if current_title and current_content:
            discovery = self._parse_finding_block(
                title=current_title,
                content="\n".join(current_content),
                section=current_section,
                source_url=current_source_url,
                date_str=date_str,
            )
            if discovery:
                discoveries.append(discovery)

        logger.info("Parsed %d discoveries from %s", len(discoveries), brief_path.name)
        return discoveries

    def _parse_finding_block(
        self,
        title: str,
        content: str,
        section: str,
        source_url: str,
        date_str: str,
    ) -> Optional[Discovery]:
        """Parse a single finding block into a Discovery."""
        # Extract what/impact/action from structured content
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        summary_parts = []
        for line in lines:
            if line.startswith("What:"):
                summary_parts.append(line[5:].strip())
            elif line.startswith("Impact:"):
                summary_parts.append(line[7:].strip())

        summary = " ".join(summary_parts) if summary_parts else " ".join(lines[:3])
        if not summary or len(summary) < 10:
            return None

        # Score relevance against capability vectors (keyword overlap)
        relevance_scores = self._score_relevance(f"{title} {summary}")

        discovery_id = f"cra_{hash(title + source_url) & 0xFFFFFFFF:08x}"

        return Discovery(
            id=discovery_id,
            source=self._infer_source(section, source_url),
            title=title,
            url=source_url,
            summary=summary[:500],
            discovered_at=date_str,
            relevance_scores=relevance_scores,
            raw_metadata={"section": section, "brief_content": content[:1000]},
        )

    def _score_relevance(self, text: str) -> Dict[str, float]:
        """Score text against capability vectors using keyword overlap.

        This is the fast/local scoring method. For production, replace with
        embedding cosine similarity when running via batch API.
        """
        text_lower = text.lower()
        text_words = set(text_lower.split())
        scores = {}

        for capability, vector_text in CAPABILITY_VECTORS.items():
            vector_words = set(vector_text.lower().split())
            if not vector_words:
                scores[capability] = 0.0
                continue
            overlap = len(text_words & vector_words)
            scores[capability] = min(overlap / max(len(vector_words) * 0.4, 1), 1.0)

        return scores

    def _infer_source(self, section: str, url: str) -> str:
        """Infer source key from section header and URL."""
        section_lower = section.lower()
        url_lower = url.lower()

        if "arxiv" in url_lower:
            return "arxiv_agent_memory"
        if "github" in url_lower:
            return "github_trending"
        if "anthropic" in url_lower or "claude" in section_lower:
            return "anthropic_tooling"
        if "mcp" in section_lower or "mcp" in url_lower:
            return "mcp_registry"
        if "mem0" in section_lower or "mem0" in url_lower:
            return "mem0_evolution"
        return "github_trending"  # default

    def _get_existing_urls(self) -> set:
        """Load existing discovery URLs for dedup."""
        urls = set()
        if self.discoveries_path.exists():
            for line in self.discoveries_path.read_text().splitlines():
                try:
                    d = json.loads(line)
                    urls.add(d.get("url", ""))
                except json.JSONDecodeError:
                    continue
        return urls

    # ── Assessment ──

    def ingest_assessment(self, assessment: Assessment) -> None:
        """Append an assessment to the JSONL log."""
        with open(self.assessments_path, "a") as f:
            f.write(json.dumps(asdict(assessment)) + "\n")
        logger.info(
            "Assessed: %s → %s (disruption=%.1f)",
            assessment.title,
            assessment.recommendation,
            assessment.disruption_risk,
        )

    def dismiss(self, discovery_id: str, reasoning: str) -> None:
        """Record a dismissed finding (prevents re-evaluation)."""
        entry = {
            "discovery_id": discovery_id,
            "reasoning": reasoning,
            "dismissed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        with open(self.dismissed_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_dismissed_ids(self) -> set:
        """Load IDs of previously dismissed discoveries."""
        ids = set()
        if self.dismissed_path.exists():
            for line in self.dismissed_path.read_text().splitlines():
                try:
                    ids.add(json.loads(line).get("discovery_id", ""))
                except json.JSONDecodeError:
                    continue
        return ids

    # ── Proposals ──

    def save_proposal(self, title: str, spec: str) -> Path:
        """Save an integration proposal in Golden Spec format."""
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        safe_title = title.lower().replace(" ", "_")[:40]
        path = self.research_dir / "proposals" / f"{date_str}_{safe_title}.md"
        path.write_text(spec)
        logger.info("Proposal saved: %s", path)
        return path

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Return proposals not yet adopted or dismissed."""
        adopted_ids = set()
        if self.adopted_path.exists():
            for line in self.adopted_path.read_text().splitlines():
                try:
                    adopted_ids.add(json.loads(line).get("proposal_file", ""))
                except json.JSONDecodeError:
                    continue

        proposals = []
        proposals_dir = self.research_dir / "proposals"
        if proposals_dir.exists():
            for md_file in sorted(proposals_dir.glob("*.md")):
                if md_file.name not in adopted_ids:
                    proposals.append(
                        {
                            "file": md_file.name,
                            "path": str(md_file),
                            "title": md_file.stem.split("_", 1)[-1].replace("_", " "),
                            "created": md_file.stem.split("_", 1)[0],
                        }
                    )
        return proposals

    def record_adoption(self, proposal_file: str, outcome: str = "") -> None:
        """Record that a proposal was adopted (feeds back into discovery priorities)."""
        entry = {
            "proposal_file": proposal_file,
            "adopted_at": datetime.now(tz=timezone.utc).isoformat(),
            "outcome": outcome,
        }
        with open(self.adopted_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ── Queries ──

    def load_discoveries(self, days: int = 30) -> List[Discovery]:
        """Load recent discoveries (optionally filtered by age)."""
        if not self.discoveries_path.exists():
            return []

        cutoff = datetime.now(tz=timezone.utc).timestamp() - (days * 86400)
        discoveries = []
        for line in self.discoveries_path.read_text().splitlines():
            try:
                d = json.loads(line)
                # Filter by age if date is parseable
                disc_date = d.get("discovered_at", "")
                if disc_date and days < 9999:
                    try:
                        dt = datetime.fromisoformat(disc_date.replace("Z", "+00:00"))
                        if dt.timestamp() < cutoff:
                            continue
                    except ValueError:
                        pass  # Include if date unparseable
                discoveries.append(Discovery(**d))
            except (json.JSONDecodeError, TypeError):
                continue
        return discoveries

    def load_assessments(self, days: int = 30) -> List[Assessment]:
        """Load recent assessments (optionally filtered by age)."""
        if not self.assessments_path.exists():
            return []

        cutoff = datetime.now(tz=timezone.utc).timestamp() - (days * 86400)
        assessments = []
        for line in self.assessments_path.read_text().splitlines():
            try:
                a = json.loads(line)
                assessed_date = a.get("assessed_at", "")
                if assessed_date and days < 9999:
                    try:
                        dt = datetime.fromisoformat(assessed_date.replace("Z", "+00:00"))
                        if dt.timestamp() < cutoff:
                            continue
                    except ValueError:
                        pass
                assessments.append(Assessment(**a))
            except (json.JSONDecodeError, TypeError):
                continue
        return assessments

    def get_adopt_recommendations(self) -> List[Assessment]:
        """Return assessments with 'adopt' recommendation, sorted by priority."""
        assessments = self.load_assessments()
        adopt = [a for a in assessments if a.recommendation == "adopt"]
        return sorted(adopt, key=lambda a: a.priority_score, reverse=True)

    def get_urgent_threats(self) -> List[Assessment]:
        """Return assessments flagged as urgent (high disruption + achievable effort)."""
        assessments = self.load_assessments()
        return [a for a in assessments if a.is_urgent]

    # ── Digest ──

    def weekly_digest(self) -> str:
        """Generate a human-readable weekly research digest."""
        discoveries = self.load_discoveries(days=7)
        assessments = self.load_assessments(days=7)
        adopt = [a for a in assessments if a.recommendation == "adopt"]
        monitor = [a for a in assessments if a.recommendation == "monitor"]
        urgent = [a for a in assessments if a.is_urgent]

        lines = [
            f"# CRA Weekly Digest — {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}",
            "",
            f"**Discoveries:** {len(discoveries)} | "
            f"**Assessed:** {len(assessments)} | "
            f"**Adopt:** {len(adopt)} | "
            f"**Monitor:** {len(monitor)} | "
            f"**Urgent:** {len(urgent)}",
            "",
        ]

        if urgent:
            lines.append("## URGENT — High Disruption + Achievable Effort")
            lines.append("")
            for a in urgent:
                lines.append(
                    f"- **{a.title}** (disruption={a.disruption_risk:.1f}, "
                    f"effort={a.adoption_effort}) — {a.reasoning[:100]}"
                )
            lines.append("")

        if adopt:
            lines.append("## Recommended Adoptions")
            lines.append("")
            for a in adopt:
                lines.append(
                    f"- **{a.title}** ({a.expected_impact}, "
                    f"effort={a.adoption_effort}) — {a.integration_approach[:100]}"
                )
            lines.append("")

        if monitor:
            lines.append("## Monitoring")
            lines.append("")
            for a in monitor:
                lines.append(f"- {a.title} — {a.reasoning[:80]}")
            lines.append("")

        proposals = self.get_pending_proposals()
        if proposals:
            lines.append(f"## Pending Proposals ({len(proposals)})")
            lines.append("")
            for p in proposals:
                lines.append(f"- {p['title']} ({p['created']})")
            lines.append("")

        return "\n".join(lines)

    def should_scan(self) -> bool:
        """Check if a scan is due (>6 days since last discovery)."""
        if not self.discoveries_path.exists():
            return True

        # Check last line
        lines = self.discoveries_path.read_text().strip().splitlines()
        if not lines:
            return True

        try:
            last = json.loads(lines[-1])
            last_date = datetime.fromisoformat(last["discovered_at"].split("T")[0])
            days_since = (
                datetime.now(tz=timezone.utc) - last_date.replace(tzinfo=timezone.utc)
            ).days
            return days_since >= 6
        except (json.JSONDecodeError, KeyError, ValueError):
            return True

    # ── Experiment Loop (autoresearch-inspired) ──

    def evaluate_experiment(
        self,
        result: "ProposalResult",
        baseline_score: float = 0.5,
    ) -> Dict[str, Any]:
        """Evaluate a single experiment iteration and decide keep/discard.

        This is the core of the autoresearch-inspired loop:
        run proposal → evaluate score → keep if better → log everything.

        Returns dict with decision, score, and metadata.
        """
        score = adoption_outcome_score(result)
        decision = "keep" if score > baseline_score and not result.error else "discard"

        entry = {
            "proposal_title": result.proposal_title,
            "score": round(score, 4),
            "baseline": round(baseline_score, 4),
            "decision": decision,
            "test_pass_rate": round(result.test_pass_rate, 4),
            "capability_delta": round(result.capability_score_delta, 4),
            "addresses_threat": result.addresses_threat,
            "branch": result.branch_name,
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        if result.error:
            entry["error"] = result.error

        # Persist to experiment log
        log_path = self.research_dir / "experiment_log.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.info(
            "Experiment [%s]: %s (score=%.3f, baseline=%.3f)",
            decision.upper(),
            result.proposal_title,
            score,
            baseline_score,
        )

        return entry

    def get_baseline_score(self) -> float:
        """Get the current baseline score from the last kept experiment.

        If no experiments have been kept, returns 0.5 as default.
        """
        log_path = self.research_dir / "experiment_log.jsonl"
        if not log_path.exists():
            return 0.5

        last_kept_score = 0.5
        for line in log_path.read_text().strip().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("decision") == "keep":
                    last_kept_score = entry.get("score", 0.5)
            except json.JSONDecodeError:
                continue

        return last_kept_score

    def run_experiment_loop(
        self,
        proposals: List[Dict[str, Any]],
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        """Run the full experiment loop over a list of proposals.

        In dry_run mode (default), simulates the loop without creating
        branches or running tests. Set dry_run=False for actual execution.

        Returns list of experiment outcomes.
        """
        baseline = self.get_baseline_score()
        outcomes: List[Dict[str, Any]] = []

        logger.info(
            "Starting experiment loop: %d proposals, baseline=%.3f",
            len(proposals),
            baseline,
        )

        for proposal in proposals:
            title = proposal.get("title", "untitled")
            logger.info("Evaluating proposal: %s", title)

            if dry_run:
                # Simulate: assume tests pass, no capability delta measured
                result = ProposalResult(
                    proposal_title=title,
                    tests_passing=0,
                    tests_total=0,
                    capability_score_delta=0.0,
                    addresses_threat=False,
                    branch_name=f"cra/{title.lower().replace(' ', '-')[:30]}",
                )
                outcome = self.evaluate_experiment(result, baseline_score=baseline)
                outcome["dry_run"] = True
            else:
                result = self._execute_live_experiment(proposal)
                outcome = self.evaluate_experiment(result, baseline_score=baseline)

            outcomes.append(outcome)

            # Update baseline if kept
            if outcome["decision"] == "keep":
                baseline = outcome["score"]

        logger.info(
            "Experiment loop complete: %d/%d kept",
            sum(1 for o in outcomes if o["decision"] == "keep"),
            len(outcomes),
        )

        return outcomes

    # ── Batch Integration ──

    def get_scan_prompt(self) -> str:
        """Return prompt for batch API submission (discovery scan).

        Reads research_directives.md (human-authored, Karpathy program.md pattern)
        to steer scan priorities. Falls back to hardcoded threats if missing.
        """
        threat_sources = self.get_threat_sources()
        threat_section = "\n".join(
            f"- **{v['label']}**: {', '.join(v['queries'])}" for v in threat_sources.values()
        )

        # Load human-authored directives for priority steering
        directives = load_research_directives()
        directives_section = ""
        if directives:
            priorities = parse_directives_priorities(directives)
            if any(priorities.values()):
                directives_section = "\nHUMAN RESEARCH DIRECTIVES (from research_directives.md):\n"
                for tier, items in priorities.items():
                    if items:
                        tier_label = tier.replace("_", " ").title()
                        directives_section += f"\n{tier_label}:\n"
                        for item in items:
                            directives_section += f"  - {item}\n"

        return f"""You are the Cortex Research Agent (CRA). Scan the AI engineering frontier
for developments relevant to an agent memory + orchestration system.

PRIORITY THREAT MONITORING (check these FIRST):
{threat_section}
{directives_section}
CAPABILITY VECTORS (score each finding against these):
{json.dumps(CAPABILITY_VECTORS, indent=2)}

For each finding, return JSON:
{{
    "title": "...",
    "url": "...",
    "summary": "2-3 sentences",
    "relevance_scores": {{"capability": 0.0-1.0}},
    "disruption_risk": 0.0-1.0,
    "adoption_effort": "trivial|small|medium|large|rewrite",
    "expected_impact": "incremental|significant|transformative",
    "recommendation": "adopt|monitor|dismiss",
    "reasoning": "1-2 sentences"
}}

Return findings as a JSON array. Prioritize existential threats over incremental improvements."""

    def get_assess_prompt(self, discovery: Discovery) -> str:
        """Return prompt for batch API submission (assessment)."""
        return f"""Assess this research finding for integration into Cortex
(an agent memory + orchestration system for Claude Code).

FINDING:
Title: {discovery.title}
URL: {discovery.url}
Summary: {discovery.summary}

CORTEX CAPABILITIES:
{json.dumps(CAPABILITY_VECTORS, indent=2)}

CORTEX MOAT (don't compete here — LEVERAGE instead):
- Task orchestration + memory in one system
- Anti-pattern primitives (failure mode + trigger + prevention)
- Goal-to-task pipeline with model tier routing + outcome learning

CORTEX WEAKNESSES (opportunities for improvement):
- BM25+embedding retrieval (table stakes, not differentiated)
- File-based storage (functional but not scalable)
- Zero external users (no community validation)

Provide a structured assessment as JSON with these fields:
disruption_risk, adoption_effort, expected_impact, affected_modules,
integration_approach, risks, recommendation, reasoning."""


def main():
    """CLI entry point for CRA."""
    import sys

    agent = CortexResearchAgent()

    if len(sys.argv) < 2:
        print(
            f"CRA status: {len(agent.load_discoveries())} discoveries, "
            f"{len(agent.load_assessments())} assessments"
        )
        print(f"Scan due: {agent.should_scan()}")
        print(f"Pending proposals: {len(agent.get_pending_proposals())}")
        return

    command = sys.argv[1]

    if command == "ingest-brief":
        # Ingest a research brief file
        if len(sys.argv) < 3:
            # Default to latest brief
            briefs = sorted(BRIEFS_DIR.glob("*.md"), reverse=True)
            if not briefs:
                print("No briefs found in", BRIEFS_DIR)
                return
            brief_path = briefs[0]
        else:
            brief_path = Path(sys.argv[2])

        discoveries = agent.ingest_from_brief(brief_path)
        for d in discoveries:
            agent.ingest_discovery(d)
        print(f"Ingested {len(discoveries)} discoveries from {brief_path.name}")

    elif command == "digest":
        print(agent.weekly_digest())

    elif command == "threats":
        threats = agent.get_urgent_threats()
        if threats:
            for t in threats:
                print(f"  URGENT: {t.title} (disruption={t.disruption_risk:.1f})")
        else:
            print("No urgent threats detected.")

    elif command == "status":
        discoveries = agent.load_discoveries()
        assessments = agent.load_assessments()
        adopt = agent.get_adopt_recommendations()
        threats = agent.get_urgent_threats()
        proposals = agent.get_pending_proposals()

        print(f"Discoveries:  {len(discoveries)}")
        print(f"Assessments:  {len(assessments)}")
        print(f"Adopt recs:   {len(adopt)}")
        print(f"Urgent:       {len(threats)}")
        print(f"Proposals:    {len(proposals)}")
        print(f"Scan due:     {agent.should_scan()}")

    elif command == "experiment":
        # Run experiment loop over pending proposals (dry-run by default)
        proposals = agent.get_pending_proposals()
        if not proposals:
            print("No pending proposals to experiment with.")
            return
        dry_run = "--live" not in sys.argv
        outcomes = agent.run_experiment_loop(proposals, dry_run=dry_run)
        for o in outcomes:
            status = "KEEP" if o["decision"] == "keep" else "DISCARD"
            flag = " [DRY RUN]" if o.get("dry_run") else ""
            print(f"  [{status}] {o['proposal_title']} (score={o['score']:.3f}){flag}")
        kept = sum(1 for o in outcomes if o["decision"] == "keep")
        print(f"\nResults: {kept}/{len(outcomes)} kept (baseline={agent.get_baseline_score():.3f})")

    elif command == "baseline":
        print(f"Current baseline score: {agent.get_baseline_score():.3f}")

    elif command == "directives":
        directives = load_research_directives()
        if directives:
            priorities = parse_directives_priorities(directives)
            for tier, items in priorities.items():
                if items:
                    print(f"\n{tier.replace('_', ' ').title()}:")
                    for item in items:
                        print(f"  - {item}")
        else:
            print("No research_directives.md found.")

    else:
        print(f"Unknown command: {command}")
        print(
            "Usage: python -m cortex.engines.research_agent "
            "[ingest-brief|digest|threats|status|experiment|baseline|directives]"
        )


if __name__ == "__main__":
    main()
