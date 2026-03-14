"""Wisdom database — storage, indexing, and retrieval for the Kempion engine.

Organizes wisdom by tradition, aspect, truth layer, and inner season.
Filters out anti-patterns. Supports paradox pair lookups.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from motivation.models import (
    Aspect,
    InnerSeason,
    LifeDomain,
    ToneVector,
    TruthLayer,
    WisdomEntry,
)


class WisdomDatabase:
    """In-memory wisdom store with taxonomy-based filtering."""

    def __init__(self) -> None:
        self._entries: dict[str, WisdomEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, entry: WisdomEntry) -> None:
        self._entries[entry.id] = entry

    def get(self, wisdom_id: str) -> Optional[WisdomEntry]:
        return self._entries.get(wisdom_id)

    def all_entries(self) -> list[WisdomEntry]:
        return list(self._entries.values())

    def remove(self, wisdom_id: str) -> bool:
        return self._entries.pop(wisdom_id, None) is not None

    # --- Aspect / Tradition filtering ---

    def by_aspect(self, aspect: Aspect) -> list[WisdomEntry]:
        return [
            e for e in self._entries.values()
            if e.aspect == aspect or e.aspect == Aspect.ALL
        ]

    def by_tradition(self, tradition: str) -> list[WisdomEntry]:
        t_lower = tradition.lower()
        return [e for e in self._entries.values() if e.tradition.lower() == t_lower]

    def by_truth_layer(self, layer: TruthLayer) -> list[WisdomEntry]:
        return [e for e in self._entries.values() if e.truth_layer == layer]

    def by_theme(self, theme: str) -> list[WisdomEntry]:
        theme_lower = theme.lower()
        return [
            e for e in self._entries.values()
            if theme_lower in [t.lower() for t in e.themes]
        ]

    def by_domain(self, domain: LifeDomain) -> list[WisdomEntry]:
        return [e for e in self._entries.values() if domain in e.domains]

    def by_season(self, season: InnerSeason) -> list[WisdomEntry]:
        return [e for e in self._entries.values() if season in e.best_for_seasons]

    def by_author(self, author: str) -> list[WisdomEntry]:
        author_lower = author.lower()
        return [e for e in self._entries.values() if e.author.lower() == author_lower]

    def by_challenge_type(self, challenge_type: str) -> list[WisdomEntry]:
        ct_lower = challenge_type.lower()
        return [
            e for e in self._entries.values()
            if ct_lower in [c.lower() for c in e.challenge_types]
        ]

    def by_energy_match(self, energy: str) -> list[WisdomEntry]:
        return [e for e in self._entries.values() if e.energy_match == energy]

    def by_tone_proximity(self, target: ToneVector, max_distance: float = 0.5) -> list[WisdomEntry]:
        return [
            e for e in self._entries.values()
            if e.tone.distance_to(target) <= max_distance
        ]

    # --- Paradox pairs ---

    def get_paradox_pair(self, wisdom_id: str) -> Optional[WisdomEntry]:
        """Get the paradox partner of a wisdom entry."""
        entry = self.get(wisdom_id)
        if not entry or not entry.paradox_pair_id:
            return None
        return self.get(entry.paradox_pair_id)

    def all_paradox_pairs(self) -> list[tuple[WisdomEntry, WisdomEntry]]:
        """Get all linked paradox pairs (deduplicated)."""
        seen: set[str] = set()
        pairs: list[tuple[WisdomEntry, WisdomEntry]] = []
        for entry in self._entries.values():
            if entry.paradox_pair_id and entry.id not in seen:
                partner = self.get(entry.paradox_pair_id)
                if partner:
                    pairs.append((entry, partner))
                    seen.add(entry.id)
                    seen.add(partner.id)
        return pairs

    # --- Multi-filter search ---

    def search(
        self,
        themes: Optional[list[str]] = None,
        domains: Optional[list[LifeDomain]] = None,
        tradition: Optional[str] = None,
        aspect: Optional[Aspect] = None,
        truth_layer: Optional[TruthLayer] = None,
        season: Optional[InnerSeason] = None,
        challenge_type: Optional[str] = None,
        energy_match: Optional[str] = None,
        exclude_ids: Optional[set[str]] = None,
    ) -> list[WisdomEntry]:
        """Multi-filter search. All provided filters must match (AND logic)."""
        results = list(self._entries.values())
        exclude = exclude_ids or set()

        if exclude:
            results = [e for e in results if e.id not in exclude]
        if themes:
            themes_lower = {t.lower() for t in themes}
            results = [
                e for e in results if themes_lower & {t.lower() for t in e.themes}
            ]
        if domains:
            domain_set = set(domains)
            results = [e for e in results if domain_set & set(e.domains)]
        if tradition:
            t_lower = tradition.lower()
            results = [e for e in results if e.tradition.lower() == t_lower]
        if aspect:
            results = [
                e for e in results if e.aspect == aspect or e.aspect == Aspect.ALL
            ]
        if truth_layer:
            results = [e for e in results if e.truth_layer == truth_layer]
        if season:
            results = [e for e in results if season in e.best_for_seasons]
        if challenge_type:
            ct_lower = challenge_type.lower()
            results = [
                e for e in results
                if ct_lower in [c.lower() for c in e.challenge_types]
            ]
        if energy_match:
            results = [e for e in results if e.energy_match == energy_match]

        return results

    # --- Persistence ---

    def load_from_seed_data(self, path: Optional[Path] = None) -> int:
        """Load wisdom from the bundled seed data JSON file. Returns count loaded."""
        if path is None:
            path = Path(__file__).parent / "data" / "quotes.json"
        if not path.exists():
            return 0

        with open(path) as f:
            raw_entries = json.load(f)

        count = 0
        for entry in raw_entries:
            wisdom = _parse_wisdom_entry(entry)
            self.add(wisdom)
            count += 1
        return count

    def export_to_json(self, path: Path) -> int:
        """Export all wisdom to a JSON file. Returns count exported."""
        entries = []
        for e in self._entries.values():
            entries.append({
                "id": e.id,
                "text": e.text,
                "author": e.author,
                "source": e.source,
                "tradition": e.tradition,
                "era": e.era,
                "aspect": e.aspect.value,
                "truth_layer": e.truth_layer.value,
                "themes": e.themes,
                "domains": [d.value for d in e.domains],
                "tone": {
                    "severity": e.tone.severity,
                    "warmth": e.tone.warmth,
                    "directness": e.tone.directness,
                },
                "best_for_seasons": [s.value for s in e.best_for_seasons],
                "challenge_types": e.challenge_types,
                "energy_match": e.energy_match,
                "requires_context": e.requires_context,
                "companion_text": e.companion_text,
                "paradox_pair_id": e.paradox_pair_id,
            })
        with open(path, "w") as f:
            json.dump(entries, f, indent=2)
        return len(entries)


def _parse_wisdom_entry(entry: dict) -> WisdomEntry:
    """Parse a raw dict into a WisdomEntry."""
    tone_data = entry.get("tone", {})
    return WisdomEntry(
        id=entry.get("id", ""),
        text=entry.get("text", ""),
        author=entry.get("author", "Unknown"),
        source=entry.get("source"),
        tradition=entry.get("tradition", "stoic"),
        era=entry.get("era", "ancient"),
        aspect=Aspect(entry.get("aspect", "all")),
        truth_layer=TruthLayer(entry.get("truth_layer", "structural")),
        themes=entry.get("themes", []),
        domains=[LifeDomain(d) for d in entry.get("domains", [])],
        tone=ToneVector(
            severity=tone_data.get("severity", 0.5),
            warmth=tone_data.get("warmth", 0.5),
            directness=tone_data.get("directness", 0.5),
        ),
        best_for_seasons=[
            InnerSeason(s) for s in entry.get("best_for_seasons", [])
        ],
        challenge_types=entry.get("challenge_types", []),
        energy_match=entry.get("energy_match", "midday"),
        requires_context=entry.get("requires_context", False),
        companion_text=entry.get("companion_text"),
        paradox_pair_id=entry.get("paradox_pair_id"),
    )
