"""Growth trajectory and potential mapping for the Kempion path.

Tracks the seeker's development across life domains over time,
detects growth patterns, and identifies where wisdom is most needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from motivation.models import (
    DomainPotential,
    GrowthPattern,
    GrowthTrajectory,
    InnerSeason,
    LifeDomain,
    PotentialMap,
    PotentialSnapshot,
    SeekerProfile,
)


class PotentialTracker:
    """Tracks and analyzes the seeker's growth potential across domains."""

    def __init__(self) -> None:
        self._maps: dict[str, PotentialMap] = {}
        self._trajectories: dict[str, GrowthTrajectory] = {}

    def initialize_map(self, profile: SeekerProfile) -> PotentialMap:
        """Create an initial potential map from the seeker's profile."""
        domains: dict[str, DomainPotential] = {}

        # Initialize from active quests
        for quest in profile.active_quests:
            domain_key = quest.domain.value
            if domain_key not in domains:
                domains[domain_key] = DomainPotential(
                    domain=quest.domain,
                    current_level=0.3,  # Default starting point
                    target_level=1.0,
                    wisdom_themes_needed=_themes_for_domain(quest.domain),
                )

        potential_map = PotentialMap(seeker_id=profile.id, domains=domains)
        self._maps[profile.id] = potential_map

        # Initialize trajectory
        self._trajectories[profile.id] = GrowthTrajectory(seeker_id=profile.id)

        return potential_map

    def get_map(self, seeker_id: str) -> Optional[PotentialMap]:
        return self._maps.get(seeker_id)

    def get_trajectory(self, seeker_id: str) -> Optional[GrowthTrajectory]:
        return self._trajectories.get(seeker_id)

    def update_domain_level(
        self,
        seeker_id: str,
        domain: LifeDomain,
        new_level: float,
    ) -> bool:
        """Update a domain's current level (from self-assessment)."""
        potential_map = self._maps.get(seeker_id)
        if not potential_map:
            return False

        domain_key = domain.value
        if domain_key not in potential_map.domains:
            potential_map.domains[domain_key] = DomainPotential(domain=domain)

        dp = potential_map.domains[domain_key]
        old_level = dp.current_level
        dp.current_level = max(0.0, min(1.0, new_level))
        dp.growth_velocity = dp.current_level - old_level
        potential_map.last_updated = datetime.now()

        return True

    def take_snapshot(
        self, seeker_id: str, inner_season: InnerSeason = InnerSeason.UNKNOWN
    ) -> Optional[PotentialSnapshot]:
        """Capture a point-in-time snapshot of the seeker's potential levels."""
        potential_map = self._maps.get(seeker_id)
        trajectory = self._trajectories.get(seeker_id)
        if not potential_map or not trajectory:
            return None

        snapshot = PotentialSnapshot(
            domain_levels={
                key: dp.current_level for key, dp in potential_map.domains.items()
            },
            inner_season=inner_season,
        )
        trajectory.snapshots.append(snapshot)
        return snapshot

    def detect_patterns(self, seeker_id: str) -> list[GrowthPattern]:
        """Detect growth patterns from trajectory snapshots."""
        trajectory = self._trajectories.get(seeker_id)
        if not trajectory or len(trajectory.snapshots) < 3:
            return []

        patterns: list[GrowthPattern] = []
        recent = trajectory.snapshots[-5:]

        # For each domain, check trend across recent snapshots
        all_domains: set[str] = set()
        for snap in recent:
            all_domains.update(snap.domain_levels.keys())

        for domain_key in all_domains:
            levels = [
                snap.domain_levels.get(domain_key)
                for snap in recent
                if domain_key in snap.domain_levels
            ]
            levels = [l for l in levels if l is not None]

            if len(levels) < 3:
                continue

            # Simple trend detection
            first_half = sum(levels[: len(levels) // 2]) / (len(levels) // 2)
            second_half = sum(levels[len(levels) // 2 :]) / (len(levels) - len(levels) // 2)
            diff = second_half - first_half

            if diff > 0.05:
                trend = "improving"
                confidence = min(1.0, abs(diff) * 5)
            elif diff < -0.05:
                trend = "declining"
                confidence = min(1.0, abs(diff) * 5)
            else:
                trend = "stable"
                confidence = 0.7

            try:
                domain_enum = LifeDomain(domain_key)
            except ValueError:
                continue

            patterns.append(
                GrowthPattern(
                    description=f"{domain_key}: {trend}",
                    domain=domain_enum,
                    trend=trend,
                    confidence=confidence,
                )
            )

        trajectory.patterns = patterns
        return patterns

    def identify_wisdom_gaps(self, seeker_id: str) -> dict[str, list[str]]:
        """Identify which domains need the most wisdom support."""
        potential_map = self._maps.get(seeker_id)
        if not potential_map:
            return {}

        gaps: dict[str, list[str]] = {}
        for key, dp in potential_map.domains.items():
            if dp.gap > 0.3:  # Significant gap
                gaps[key] = dp.wisdom_themes_needed or _themes_for_domain(dp.domain)

        return gaps


def _themes_for_domain(domain: LifeDomain) -> list[str]:
    """Default wisdom themes needed for each domain."""
    themes: dict[LifeDomain, list[str]] = {
        LifeDomain.CRAFT: ["discipline", "mastery", "craft", "perseverance", "excellence"],
        LifeDomain.BODY: ["discipline", "endurance", "presence", "vitality"],
        LifeDomain.BONDS: ["vulnerability", "patience", "compassion", "truth"],
        LifeDomain.MIND: ["clarity", "humility", "curiosity", "discernment"],
        LifeDomain.SPIRIT: ["meaning", "impermanence", "acceptance", "transcendence"],
        LifeDomain.WEALTH: ["sovereignty", "discipline", "patience", "value"],
        LifeDomain.EXPRESSION: ["courage", "authenticity", "craft", "vulnerability"],
    }
    return themes.get(domain, ["growth", "truth", "discipline"])
