#!/usr/bin/env python3
"""
Prompt Database — Scoring, Ranking, Dedup, Purge, Pattern Extraction

This is the batch-processing brain of the Prompt Optimization Layer.
The hook (prompt_capture.py) captures prompts in real-time.
This module analyzes them periodically to:

1. RE-SCORE: Adjust value scores based on outcome correlation
2. DEDUP: Find semantically similar prompts, keep highest-scored
3. PURGE: Remove entries below value threshold
4. EXTRACT: Identify high-value patterns for the hook to inject
5. RANK: Surface top prompts for review and learning
6. REBUILD CACHE: Write patterns.json for hook fast-path

Usage:
    python prompt_db.py score          # Re-score all prompts
    python prompt_db.py rank [N]       # Show top N prompts
    python prompt_db.py dedup          # Find and mark duplicates
    python prompt_db.py purge [threshold]  # Remove low-value entries
    python prompt_db.py patterns       # Extract and cache patterns
    python prompt_db.py stats          # Show database statistics
    python prompt_db.py full           # Run full maintenance cycle
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORTEX_DIR = Path.home() / ".cortex"
PROMPTS_DIR = CORTEX_DIR / "prompts"
LOG_FILE = PROMPTS_DIR / "prompt_log.jsonl"
PATTERNS_FILE = PROMPTS_DIR / "patterns.json"
SCORES_FILE = PROMPTS_DIR / "scores.json"
CURATED_DIR = PROMPTS_DIR  # Daily JSON files live here


def read_log() -> list[dict]:
    """Read all entries from prompt_log.jsonl."""
    if not LOG_FILE.exists():
        return []

    entries = []
    for line in LOG_FILE.read_text().strip().split("\n"):
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return entries


def read_curated() -> list[dict]:
    """Read curated prompts from daily JSON files."""
    all_prompts = []
    for f in sorted(CURATED_DIR.glob("20??-??-??.json")):
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                for entry in data:
                    entry["_source_file"] = f.name
                    all_prompts.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return all_prompts


def write_log(entries: list[dict]) -> None:
    """Rewrite the log (used after purge/dedup)."""
    with open(LOG_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


# === SCORING ===


def rescore_entry(entry: dict, category_performance: dict) -> float:
    """Re-score a single entry incorporating outcome data.

    category_performance: {category: {avg_outcome: float, count: int}}
    """
    base_score = entry.get("value_score", 0.0)

    # Boost/penalize based on category performance
    category = entry.get("category", "request")
    perf = category_performance.get(category, {})
    avg_outcome = perf.get("avg_outcome", 0.5)

    # Adjust: if this category correlates with good outcomes, boost
    outcome_multiplier = 0.8 + (avg_outcome * 0.4)  # Range: 0.8 - 1.2

    # Recency boost: more recent prompts are more relevant
    try:
        ts = datetime.fromisoformat(entry["timestamp"])
        days_ago = (datetime.now(timezone.utc) - ts).days
        recency_factor = max(0.5, 1.0 - (days_ago * 0.02))  # -2% per day, floor 0.5
    except (KeyError, ValueError):
        recency_factor = 0.7

    # Combined score
    new_score = base_score * outcome_multiplier * recency_factor

    # Cap at 1.0
    return min(1.0, round(new_score, 3))


def score_all(entries: list[dict]) -> list[dict]:
    """Re-score all entries. Returns updated entries."""
    # Build category performance from curated prompts (they have outcome_hint)
    curated = read_curated()
    category_performance = _compute_category_performance(curated)

    for entry in entries:
        entry["value_score"] = rescore_entry(entry, category_performance)

    return entries


def _compute_category_performance(curated: list[dict]) -> dict:
    """Compute average outcome quality per category from curated prompts."""
    category_data = defaultdict(list)

    quality_map = {
        "very high": 0.95,
        "high": 0.80,
        "medium-high": 0.65,
        "medium": 0.50,
        "low": 0.20,
    }

    for prompt in curated:
        category = prompt.get("category", "request")
        quality_str = str(prompt.get("prompt_quality", "medium")).lower()

        # Match quality string to score
        quality_score = 0.5  # default
        for key, score in quality_map.items():
            if key in quality_str:
                quality_score = score
                break

        category_data[category].append(quality_score)

    result = {}
    for category, scores in category_data.items():
        result[category] = {
            "avg_outcome": sum(scores) / len(scores),
            "count": len(scores),
        }

    return result


# === DEDUP ===


def find_duplicates(
    entries: list[dict], similarity_threshold: float = 0.8
) -> list[tuple[int, int]]:
    """Find duplicate pairs based on prompt_hash and word overlap.

    Returns list of (lower_idx, higher_idx) pairs where higher is the duplicate.
    """
    duplicates = []
    hash_groups = defaultdict(list)

    # Group by exact hash first
    for i, entry in enumerate(entries):
        h = entry.get("prompt_hash", "")
        if h:
            hash_groups[h].append(i)

    # Exact hash duplicates
    for indices in hash_groups.values():
        if len(indices) > 1:
            # Keep the first, mark rest as duplicates
            for idx in indices[1:]:
                duplicates.append((indices[0], idx))

    # Word overlap for near-duplicates (only on non-trivial entries)
    significant = [
        (i, entry) for i, entry in enumerate(entries) if entry.get("word_count", 0) >= 10
    ]

    for i, (idx_a, entry_a) in enumerate(significant):
        words_a = set(entry_a.get("prompt_text", "").lower().split())
        if not words_a:
            continue

        for idx_b, entry_b in significant[i + 1 :]:
            words_b = set(entry_b.get("prompt_text", "").lower().split())
            if not words_b:
                continue

            # Jaccard similarity
            intersection = len(words_a & words_b)
            union = len(words_a | words_b)
            if union > 0 and (intersection / union) >= similarity_threshold:
                duplicates.append((idx_a, idx_b))

    return duplicates


def dedup_entries(entries: list[dict]) -> tuple[list[dict], int]:
    """Remove duplicates, keeping highest-scored version.

    Returns (deduped_entries, num_removed).
    """
    duplicates = find_duplicates(entries)

    if not duplicates:
        return entries, 0

    # For each duplicate pair, mark the lower-scored one for removal
    to_remove = set()
    for idx_a, idx_b in duplicates:
        score_a = entries[idx_a].get("value_score", 0)
        score_b = entries[idx_b].get("value_score", 0)
        if score_a >= score_b:
            to_remove.add(idx_b)
        else:
            to_remove.add(idx_a)

    deduped = [e for i, e in enumerate(entries) if i not in to_remove]
    return deduped, len(to_remove)


# === PURGE ===


def purge_entries(entries: list[dict], threshold: float = 0.15) -> tuple[list[dict], int]:
    """Remove entries below value threshold.

    Returns (remaining_entries, num_purged).
    """
    remaining = [e for e in entries if e.get("value_score", 0) >= threshold]
    return remaining, len(entries) - len(remaining)


# === PATTERN EXTRACTION ===


def extract_patterns(entries: list[dict], curated: list[dict] | None = None) -> dict:
    """Extract high-value patterns and build the patterns.json cache.

    This is what the hook reads at runtime for injection context.
    """
    if curated is None:
        curated = read_curated()

    # Top patterns: highest-scored entries
    sorted_entries = sorted(entries, key=lambda e: e.get("value_score", 0), reverse=True)
    top = sorted_entries[:20]

    top_patterns = []
    for entry in top:
        top_patterns.append(
            {
                "text": entry.get("prompt_text", "")[:100],
                "category": entry.get("category", "request"),
                "value_score": entry.get("value_score", 0),
                "word_count": entry.get("word_count", 0),
            }
        )

    # Also include curated prompts (manual high-quality)
    for prompt in curated:
        quality = str(prompt.get("prompt_quality", "")).lower()
        if "high" in quality:
            top_patterns.append(
                {
                    "text": prompt.get("prompt_text", "")[:100],
                    "category": prompt.get("category", "request"),
                    "value_score": 0.9 if "very high" in quality else 0.8,
                    "word_count": prompt.get("word_count", 0),
                    "curated": True,
                }
            )

    # Dedup top patterns by text similarity
    seen_texts = set()
    unique_patterns = []
    for p in top_patterns:
        short = p["text"][:50].lower()
        if short not in seen_texts:
            seen_texts.add(short)
            unique_patterns.append(p)

    # Category hints: what context to inject for each category
    category_hints = {
        "direction": "Refine: specify scope boundary, reference GOALS.md priorities, include success criteria",
        "investigation": "Refine: specify symptoms, recent changes, data sources to check, define 'confirmed'",
        "meta": "Refine: reference what worked before (check prompt_log), specify measurable outcome",
        "idea": "Refine: add constraints (budget, timeline, dependencies), specify validation criteria",
        "decision": "Refine: list trade-offs explicitly, specify reversibility, reference architecture",
        "request": "Refine: add acceptance criteria, specify test requirements, scope to single project",
    }

    # Category statistics
    category_stats = Counter(e.get("category", "request") for e in entries)
    avg_scores = defaultdict(list)
    for e in entries:
        avg_scores[e.get("category", "request")].append(e.get("value_score", 0))

    category_summary = {}
    for cat, count in category_stats.items():
        scores = avg_scores[cat]
        category_summary[cat] = {
            "count": count,
            "avg_value": round(sum(scores) / len(scores), 3) if scores else 0,
            "max_value": round(max(scores), 3) if scores else 0,
        }

    # Notable patterns from curated prompts
    notable = []
    for prompt in curated:
        for pattern in prompt.get("notable_patterns", []):
            notable.append(pattern)

    # Frequency analysis of notable patterns
    pattern_freq = Counter(notable)
    recurring_patterns = [
        {"pattern": p, "frequency": c} for p, c in pattern_freq.most_common(10) if c >= 2
    ]

    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_captured": len(entries),
        "top_patterns": unique_patterns[:15],  # Cap at 15
        "category_hints": category_hints,
        "category_stats": category_summary,
        "recurring_patterns": recurring_patterns,
    }

    # Write cache
    with open(PATTERNS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    return result


# === RANKING ===


def rank(entries: list[dict], top_n: int = 20) -> list[dict]:
    """Return top N prompts by value score."""
    return sorted(entries, key=lambda e: e.get("value_score", 0), reverse=True)[:top_n]


# === STATISTICS ===


def compute_stats(entries: list[dict]) -> dict:
    """Compute database statistics."""
    if not entries:
        return {"total": 0}

    categories = Counter(e.get("category", "unknown") for e in entries)
    scores = [e.get("value_score", 0) for e in entries]
    word_counts = [e.get("word_count", 0) for e in entries]
    injected = sum(1 for e in entries if e.get("injection_applied"))
    duplicates = sum(1 for e in entries if e.get("is_duplicate"))

    # Date range
    timestamps = []
    for e in entries:
        try:
            timestamps.append(datetime.fromisoformat(e["timestamp"]))
        except (KeyError, ValueError):
            pass

    return {
        "total": len(entries),
        "categories": dict(categories),
        "score_avg": round(sum(scores) / len(scores), 3),
        "score_max": round(max(scores), 3),
        "score_min": round(min(scores), 3),
        "word_count_avg": round(sum(word_counts) / len(word_counts), 1),
        "injection_rate": round(injected / len(entries), 3),
        "duplicate_rate": round(duplicates / len(entries), 3),
        "date_range": {
            "earliest": min(timestamps).isoformat() if timestamps else None,
            "latest": max(timestamps).isoformat() if timestamps else None,
        },
        "curated_count": len(read_curated()),
    }


# === FULL MAINTENANCE ===


def full_maintenance(purge_threshold: float = 0.15) -> dict:
    """Run full maintenance cycle: score → dedup → purge → patterns."""
    entries = read_log()
    if not entries:
        return {"status": "empty", "message": "No entries in prompt log"}

    original_count = len(entries)

    # 1. Re-score
    entries = score_all(entries)

    # 2. Dedup
    entries, dedup_removed = dedup_entries(entries)

    # 3. Purge
    entries, purge_removed = purge_entries(entries, threshold=purge_threshold)

    # 4. Write cleaned log
    write_log(entries)

    # 5. Extract patterns
    extract_patterns(entries)

    # 6. Save scores summary
    stats = compute_stats(entries)
    stats["maintenance"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_count": original_count,
        "dedup_removed": dedup_removed,
        "purge_removed": purge_removed,
        "final_count": len(entries),
    }
    with open(SCORES_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    return stats


# === CLI ===


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Prompt Database — Scoring, Ranking, Dedup, Purge")
        print()
        print("Usage: python prompt_db.py <command> [args]")
        print()
        print("Commands:")
        print("  score          Re-score all prompts against outcomes")
        print("  rank [N]       Show top N prompts (default: 20)")
        print("  dedup          Find and remove duplicates")
        print("  purge [T]      Remove entries below threshold T (default: 0.15)")
        print("  patterns       Extract patterns and rebuild cache")
        print("  stats          Show database statistics")
        print("  full           Run full maintenance cycle")
        return

    command = sys.argv[1]
    entries = read_log()

    if command == "score":
        entries = score_all(entries)
        write_log(entries)
        print(f"Re-scored {len(entries)} entries")

    elif command == "rank":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        top = rank(entries, n)
        print(f"\n{'=' * 60}")
        print(f" TOP {len(top)} PROMPTS BY VALUE SCORE")
        print(f"{'=' * 60}\n")
        for i, entry in enumerate(top, 1):
            score = entry.get("value_score", 0)
            cat = entry.get("category", "?")
            text = entry.get("prompt_text", "")[:80]
            words = entry.get("word_count", 0)
            bar = "█" * int(score * 20)
            print(f"  {i:2d}. [{score:.2f}] {bar}")
            print(f"      [{cat}] ({words}w) {text}")
            print()

    elif command == "dedup":
        entries, removed = dedup_entries(entries)
        write_log(entries)
        print(f"Removed {removed} duplicates. {len(entries)} entries remain.")

    elif command == "purge":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
        entries, removed = purge_entries(entries, threshold)
        write_log(entries)
        print(f"Purged {removed} entries below {threshold}. {len(entries)} remain.")

    elif command == "patterns":
        patterns = extract_patterns(entries)
        print(f"Extracted patterns from {len(entries)} entries")
        print(f"  Top patterns: {len(patterns.get('top_patterns', []))}")
        print(f"  Categories: {json.dumps(patterns.get('category_stats', {}), indent=2)}")
        if patterns.get("recurring_patterns"):
            print("\n  Recurring notable patterns:")
            for p in patterns["recurring_patterns"]:
                print(f"    [{p['frequency']}x] {p['pattern']}")

    elif command == "stats":
        stats = compute_stats(entries)
        print(f"\n{'=' * 60}")
        print(" PROMPT DATABASE STATISTICS")
        print(f"{'=' * 60}\n")
        print(f"  Total captured:  {stats['total']}")
        print(f"  Curated (manual): {stats.get('curated_count', 0)}")
        print(
            f"  Score avg/max:   {stats.get('score_avg', 0):.2f} / {stats.get('score_max', 0):.2f}"
        )
        print(f"  Word count avg:  {stats.get('word_count_avg', 0):.0f}")
        print(f"  Injection rate:  {stats.get('injection_rate', 0):.0%}")
        print(f"  Duplicate rate:  {stats.get('duplicate_rate', 0):.0%}")
        print("\n  Categories:")
        for cat, count in sorted(
            stats.get("categories", {}).items(), key=lambda x: x[1], reverse=True
        ):
            print(f"    {cat:15s}: {count}")
        dr = stats.get("date_range", {})
        if dr.get("earliest"):
            print(f"\n  Date range: {dr['earliest'][:10]} → {dr['latest'][:10]}")

    elif command == "full":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
        print("Running full maintenance cycle...")
        stats = full_maintenance(purge_threshold=threshold)
        maint = stats.get("maintenance", {})
        print(f"\n  Original:  {maint.get('original_count', 0)}")
        print(f"  Deduped:   -{maint.get('dedup_removed', 0)}")
        print(f"  Purged:    -{maint.get('purge_removed', 0)}")
        print(f"  Final:     {maint.get('final_count', 0)}")
        print(f"\n  Patterns cache rebuilt: {PATTERNS_FILE}")

    else:
        print(f"Unknown command: {command}")
        print("Run without arguments for help.")


if __name__ == "__main__":
    main()
