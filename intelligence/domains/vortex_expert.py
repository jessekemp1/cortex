#!/usr/bin/env python3
"""
Vortex backend Domain Expert - Marine weather forecasting intelligence.

Provides:
- GRIB data freshness monitoring
- Coordinate system hints (NAD83 vs WGS84)
- NDBC station guidance
- Forecast validation suggestions
"""

import os
import time
from pathlib import Path
from typing import List, Optional

from intelligence.domains.base_expert import BaseDomainExpert, DomainInsight


class VortexExpert(BaseDomainExpert):
    """Vortex backend marine weather forecasting domain expert."""

    # Vortex backend project location — resolved from CORTEX_ROOT_DIR or CWD
    VORTEX_PATH = Path(os.environ.get("CORTEX_ROOT_DIR", ".")) / "Vortex" / "backend"
    DATA_PATH = VORTEX_PATH / "data"

    # Domain-specific keywords that trigger expertise
    DOMAIN_KEYWORDS = [
        "grib",
        "grib2",
        "ndbc",
        "forecast",
        "wind",
        "wave",
        "lake huron",
        "buoy",
        "station",
        "ensemble",
        "lstm",
        "weather",
        "coordinate",
        "ecmwf",
        "validation",
        "observation",
        "marine",
        "u10",
        "v10",
        "wind speed",
        "wind direction",
    ]

    # Cache for expensive operations
    _cache = {}
    _cache_time = {}

    @property
    def project_name(self) -> str:
        return "vortex-backend"

    def is_relevant(self, cwd: Path, task: str = "") -> bool:
        """Check relevance — matches both identifier and filesystem path."""
        path_str = str(cwd).lower()
        if "vortex/backend" in path_str or "vortex-backend" in path_str:
            return True
        if task and any(kw in task.lower() for kw in self._get_domain_keywords()):
            return True
        return False

    def get_quick_insight(self, cwd: Path, task: str = "") -> Optional[str]:
        """
        Get quick insight for context injection (under 150ms).

        Returns compact domain-specific hints based on task keywords.
        """
        # Check if this is Vortex backend related
        if not self.is_relevant(cwd, task):
            return None

        insights = []

        # 1. Check GRIB data freshness (cached, quick)
        grib_warning = self._check_grib_freshness()
        if grib_warning:
            insights.append(grib_warning)

        # 2. Task-specific guidance
        task_lower = task.lower()

        # Coordinate/datum hints
        if any(kw in task_lower for kw in ["coordinate", "lat", "lon", "lake huron", "datum"]):
            insights.append("Datum: NAD83 for Great Lakes")

        # GRIB format hints
        if "grib" in task_lower:
            insights.append("GRIB: u10/v10 for wind components")

        # NDBC hints
        if "ndbc" in task_lower or "buoy" in task_lower:
            insights.append("NDBC: Wind speeds in m/s, convert to knots")

        # Validation hints
        if "validation" in task_lower or "test" in task_lower:
            insights.append("Validate: ±30min temporal, 50km spatial")

        # Return compact format (max 100 chars)
        if insights:
            result = " | ".join(insights)
            if len(result) > 100:
                result = result[:97] + "..."
            return result

        return None

    def get_warnings(self, cwd: Path) -> List[DomainInsight]:
        """Get current warnings for Vortex backend project."""
        warnings = []

        # Check GRIB data freshness
        grib_age = self._get_grib_age_hours()
        if grib_age is not None:
            if grib_age > 12:
                warnings.append(
                    DomainInsight(
                        category="warning",
                        message=f"GRIB data {int(grib_age)}h old (consider refresh)",
                        confidence=0.9,
                        source="grib_data",
                    )
                )

        # Check if data directory exists
        if not self.DATA_PATH.exists():
            warnings.append(
                DomainInsight(
                    category="warning",
                    message="Vortex backend data directory not found",
                    confidence=1.0,
                    source="filesystem",
                )
            )

        return warnings

    def get_validation_suggestions(self, task: str) -> List[str]:
        """Suggest validation steps for Vortex backend tasks."""
        suggestions = []
        task_lower = task.lower()

        if "grib" in task_lower:
            suggestions.extend(
                [
                    "Validate GRIB coordinates in expected bounds",
                    "Check u10/v10 components convert correctly to speed/direction",
                    "Verify forecast_time is in UTC",
                ]
            )

        if "ndbc" in task_lower or "buoy" in task_lower:
            suggestions.extend(
                [
                    "Verify station_id format (5 digits for NDBC)",
                    "Check observation_time matches forecast_time ±30min",
                    "Convert wind speeds from m/s to knots (multiply by 1.944)",
                ]
            )

        if "lake huron" in task_lower:
            suggestions.extend(
                [
                    "Verify coordinates: lat [43°, 46°N], lon [80°, 84°W]",
                    "Use NAD83 datum for Great Lakes stations",
                    "Check station 45008 for Southern Lake Huron data",
                ]
            )

        if "ensemble" in task_lower:
            suggestions.extend(
                [
                    "Test with all 7 model sources (GFS, ECMWF, ensemble variants)",
                    "Verify ensemble weights sum to 1.0",
                    "Check confidence intervals are reasonable",
                ]
            )

        return suggestions

    def _get_domain_keywords(self) -> List[str]:
        """Get Vortex backend domain keywords."""
        return self.DOMAIN_KEYWORDS

    def _check_grib_freshness(self) -> Optional[str]:
        """
        Check GRIB data freshness (cached).

        Returns compact warning string or None.
        """
        age_hours = self._get_grib_age_hours()

        if age_hours is None:
            return None

        if age_hours > 12:
            return f"GRIB {int(age_hours)}h old"

        return None

    def _get_grib_age_hours(self) -> Optional[float]:
        """
        Get age of most recent GRIB file in hours (cached).

        Returns None if no GRIB directory or files found.
        """
        cache_key = "grib_age"

        # Check cache (5 minute TTL)
        if cache_key in self._cache_time:
            age = time.time() - self._cache_time[cache_key]
            if age < self.CACHE_TTL:
                return self._cache.get(cache_key)

        # Calculate GRIB age
        grib_dir = self.DATA_PATH / "grib"
        if not grib_dir.exists():
            self._cache[cache_key] = None
            self._cache_time[cache_key] = time.time()
            return None

        # Find most recent GRIB file
        grib_files = list(grib_dir.glob("*.grib2"))
        if not grib_files:
            # Also check for .grib files
            grib_files = list(grib_dir.glob("*.grib"))

        if not grib_files:
            self._cache[cache_key] = None
            self._cache_time[cache_key] = time.time()
            return None

        # Get most recent modification time
        latest = max(grib_files, key=lambda f: f.stat().st_mtime)
        age_hours = (time.time() - latest.stat().st_mtime) / 3600

        # Cache result
        self._cache[cache_key] = age_hours
        self._cache_time[cache_key] = time.time()

        return age_hours
