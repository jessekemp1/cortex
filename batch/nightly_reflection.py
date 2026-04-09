#!/usr/bin/env python3
"""
Nightly Reflection Batch Job

Runs at 22:00 (via com.cortex.batch.nightly.plist) as part of intelligent_orchestrator.py.

1. Reads today's interactions from ~/.cortex/interaction_queue.jsonl
2. Synthesises a structured reflection via Anthropic API (haiku — cheapest tier)
3. Seeds the reflection into ChromaDB / PortfolioMemory
4. Writes a JSON record to ~/.cortex/reflections/ for status queries
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CORTEX_HOME = Path.home() / ".cortex"
INTERACTION_QUEUE = CORTEX_HOME / "interaction_queue.jsonl"
REFLECTIONS_DIR = CORTEX_HOME / "reflections"

# ---------------------------------------------------------------------------
# Anthropic model — cheapest tier
# ---------------------------------------------------------------------------
REFLECTION_MODEL = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_str() -> str:
    return date.today().isoformat()


def load_todays_interactions(path: Path = INTERACTION_QUEUE) -> List[Dict[str, Any]]:
    """Return all type=='prompt' entries whose timestamp matches today."""
    today = _today_str()
    interactions: List[Dict[str, Any]] = []

    if not path.exists():
        return interactions

    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                ts = entry.get("timestamp", entry.get("ts", ""))

                # Accept type == "prompt" (or no type — legacy format)
                if entry_type not in ("prompt", ""):
                    continue

                if ts and ts[:10] == today:
                    interactions.append(entry)
    except OSError:
        pass

    return interactions


def _build_reflection_prompt(interactions: List[Dict[str, Any]]) -> str:
    """Build the haiku prompt from today's interactions."""
    snippets: List[str] = []
    for i, entry in enumerate(interactions[:30], 1):  # cap at 30 to stay cheap
        text = entry.get("content", entry.get("prompt", entry.get("text", "")))
        if text:
            snippets.append(f"{i}. {str(text)[:300]}")

    interaction_block = "\n".join(snippets) if snippets else "(no interaction content available)"

    return f"""You are a concise technical analyst. Review today's engineering interactions and produce a structured reflection.

TODAY'S INTERACTIONS ({len(interactions)} total):
{interaction_block}

Produce a JSON object with exactly these keys:
{{
  "date": "{_today_str()}",
  "themes": ["<theme1>", "<theme2>"],
  "decisions_made": ["<decision1>"],
  "blockers_surfaced": ["<blocker1>"],
  "patterns_noticed": ["<pattern1>"],
  "tomorrow_priorities": ["<priority1>", "<priority2>"],
  "confidence": 0.0
}}

Rules:
- Each list: 1-4 items max, each item ≤ 80 chars
- confidence: 0.0–1.0 reflecting how representative the sample is
- Output ONLY the JSON object, no markdown fences, no commentary
"""


def synthesise_reflection(
    interactions: List[Dict[str, Any]],
    anthropic_client=None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Call Anthropic haiku to synthesise a structured reflection.

    Args:
        interactions: Today's interaction entries.
        anthropic_client: Injected Anthropic client (for testing). If None, creates one.
        dry_run: If True, return a stub without calling the API.

    Returns:
        Reflection dict (always includes 'date' and 'synthesised_at').
    """
    stub: Dict[str, Any] = {
        "date": _today_str(),
        "themes": [],
        "decisions_made": [],
        "blockers_surfaced": [],
        "patterns_noticed": [],
        "tomorrow_priorities": [],
        "confidence": 0.0,
        "interaction_count": len(interactions),
        "synthesised_at": datetime.now().isoformat(),
        "model": REFLECTION_MODEL,
        "dry_run": dry_run,
    }

    if dry_run:
        stub["themes"] = ["dry-run mode — no API call made"]
        return stub

    if not interactions:
        stub["themes"] = ["no interactions recorded today"]
        return stub

    # Build client if not injected
    if anthropic_client is None:
        try:
            import anthropic  # type: ignore

            anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        except ImportError:
            stub["error"] = "anthropic package not installed"
            return stub

    prompt = _build_reflection_prompt(interactions)

    try:
        response = anthropic_client.messages.create(
            model=REFLECTION_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        stub.update(parsed)
    except json.JSONDecodeError as exc:
        stub["error"] = f"JSON parse error: {exc}"
    except Exception as exc:
        stub["error"] = str(exc)

    stub["interaction_count"] = len(interactions)
    stub["synthesised_at"] = datetime.now().isoformat()
    stub["model"] = REFLECTION_MODEL
    return stub


def save_reflection(reflection: Dict[str, Any]) -> Path:
    """Persist reflection JSON to ~/.cortex/reflections/<date>.json."""
    REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = REFLECTIONS_DIR / f"{reflection['date']}.json"
    out.write_text(json.dumps(reflection, indent=2), encoding="utf-8")
    return out


def seed_reflection_to_memory(reflection: Dict[str, Any]) -> bool:
    """
    Seed the reflection into ChromaDB (SpecKnowledgeBase) and PortfolioMemory.

    Graceful degradation: returns False if dependencies unavailable.
    """
    try:
        _repo = str(Path.home() / "Dev")
        if _repo not in sys.path:
            sys.path.insert(0, _repo)
        if str(Path.home() / "Dev" / "cortex") not in sys.path:
            sys.path.insert(0, str(Path.home() / "Dev" / "cortex"))

        from cortex.intelligence.spec_knowledge_base import SpecKnowledgeBase  # type: ignore

        kb = SpecKnowledgeBase()
        doc_text = (
            f"Nightly reflection {reflection['date']}: "
            f"themes={reflection.get('themes', [])}; "
            f"decisions={reflection.get('decisions_made', [])}; "
            f"blockers={reflection.get('blockers_surfaced', [])}; "
            f"priorities={reflection.get('tomorrow_priorities', [])}"
        )
        kb.collection.upsert(
            ids=[f"nightly_reflection_{reflection['date']}"],
            documents=[doc_text],
            metadatas=[{"source": "nightly_reflection", "date": reflection["date"]}],
        )
        return True
    except Exception:
        pass

    try:
        from cortex.portfolio_memory import PortfolioMemory  # type: ignore

        pm = PortfolioMemory()
        pm.record_event(
            project="cortex",
            event_type="nightly_reflection",
            description=f"Reflection {reflection['date']}: {reflection.get('themes', [])}",
            metadata=reflection,
        )
        return True
    except Exception:
        return False


def get_last_reflection() -> Optional[Dict[str, Any]]:
    """Return the most recent saved reflection, or None."""
    if not REFLECTIONS_DIR.exists():
        return None
    files = sorted(REFLECTIONS_DIR.glob("*.json"), reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main entry point (also called by intelligent_orchestrator)
# ---------------------------------------------------------------------------


class NightlyReflection:
    """Orchestrates the full nightly reflection pipeline."""

    def __init__(
        self,
        anthropic_client=None,
        interaction_queue: Path = INTERACTION_QUEUE,
    ):
        self._client = anthropic_client
        self._queue_path = interaction_queue

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the reflection pipeline. Returns the reflection dict."""
        print(f"  Loading today's interactions from {self._queue_path}…")
        interactions = load_todays_interactions(self._queue_path)
        print(f"  Found {len(interactions)} prompt interactions for {_today_str()}")

        print(f"  Synthesising reflection via {REFLECTION_MODEL}…")
        reflection = synthesise_reflection(
            interactions,
            anthropic_client=self._client,
            dry_run=dry_run,
        )

        if reflection.get("error"):
            print(f"  Warning: reflection synthesis error — {reflection['error']}")

        out_path = save_reflection(reflection)
        print(f"  Saved: {out_path}")

        if not dry_run:
            seeded = seed_reflection_to_memory(reflection)
            print(f"  Memory seed: {'ok' if seeded else 'skipped (deps unavailable)'}")

        return reflection

    def status(self) -> str:
        """Human-readable status line."""
        last = get_last_reflection()
        if last is None:
            return "no reflections yet"
        date_str = last.get("date", "unknown")
        count = last.get("interaction_count", "?")
        themes = last.get("themes", [])
        theme_str = ", ".join(themes[:2]) if themes else "none"
        error = last.get("error")
        if error:
            return f"last reflection: {date_str} ({count} interactions) — ERROR: {error}"
        return f"last reflection: {date_str} ({count} interactions) — themes: {theme_str}"


def run_nightly_reflection(dry_run: bool = False) -> None:
    """Top-level function called by intelligent_orchestrator.py."""
    nr = NightlyReflection()
    reflection = nr.run(dry_run=dry_run)
    themes = reflection.get("themes", [])
    print(f"  Reflection complete — themes: {themes}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nightly Reflection")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    nr = NightlyReflection()
    if args.status:
        print(nr.status())
    else:
        nr.run(dry_run=args.dry_run)
