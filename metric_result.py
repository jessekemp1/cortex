"""Typed metric results: a measurement and a missing measurement are different.

Cortex signalled a failed lookup by returning a value that a caller could not
distinguish from a real measurement — `{}`, `None`, or `{"error": ...}` that the
next layer read with `.get(key, 0)`. Three separate defects were that one idiom:

  * `tracker.get_cached_health()` did not exist, so every call raised
    AttributeError, an `except Exception` turned it into `{"error": ...}`, and
    `overall.get("commits", 0)` produced a confident "No commits in analysis
    period" alert that had never measured commits.
  * Every project resolved its health to the workspace root, so five projects
    reported one repo's score with nothing marking the number as borrowed.
  * `project_index.json` had no writer for three months and consumers could not
    tell a stale index from a current one.

`Unavailable` deliberately has no `value` attribute. A caller that forgets to
branch raises AttributeError immediately instead of rendering a plausible zero,
which is the whole point: make the wrong thing loud rather than believable.

The mapping helpers exist because the health producers return plain dicts to six
call sites plus the bridge API, so wrapping their return type is not a
ship-alone change. Instead a producer omits a metric it could not measure and
records why under `unavailable`, and consumers read it through `require()` /
`is_available()` rather than `.get(key, default)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Tuple

UNAVAILABLE_KEY = "unavailable"


@dataclass(frozen=True)
class Measured:
    """A value that was actually read, with where it came from."""

    value: Any
    source: str = ""
    measured_at: str = field(default_factory=lambda: datetime.now().isoformat())
    available: bool = True


@dataclass(frozen=True)
class Unavailable:
    """A measurement that did not happen, and why.

    No `value` attribute on purpose — see the module docstring.
    """

    reason: str
    source: str = ""
    available: bool = False


class MetricUnavailable(KeyError):
    """Raised by require() when a metric was not measured."""


def unwrap_or_report(result: Measured | Unavailable) -> Tuple[Optional[Any], Optional[str]]:
    """(value, None) when measured, (None, reason) when not.

    For renderers that want a tuple instead of an isinstance check.
    """
    if getattr(result, "available", False):
        return result.value, None  # type: ignore[union-attr]
    return None, getattr(result, "reason", "unknown")


def mark_unavailable(container: Dict[str, Any], metric: str, reason: str) -> Dict[str, Any]:
    """Record that `metric` could not be measured, and remove any stale value.

    Deleting the key matters: leaving a previous value in place next to an
    `unavailable` note is how a stale number keeps being served.
    """
    container.setdefault(UNAVAILABLE_KEY, {})[metric] = reason
    container.pop(metric, None)
    return container


def is_available(container: Mapping[str, Any], metric: str) -> bool:
    """True only when the metric is present AND not marked unavailable."""
    if metric in (container.get(UNAVAILABLE_KEY) or {}):
        return False
    return metric in container


def require(container: Mapping[str, Any], metric: str) -> Any:
    """The measured value, or raise. Never a default.

    Use this on any path that would otherwise write `.get(metric, 0)`. The raise
    is the feature — a metric that was never measured must not reach a threshold
    comparison, because `0 < threshold` and `missing < threshold` are different
    claims about the world.
    """
    if not is_available(container, metric):
        reason = (container.get(UNAVAILABLE_KEY) or {}).get(metric, "not present")
        raise MetricUnavailable(f"{metric}: {reason}")
    return container[metric]


def unavailable_reasons(container: Mapping[str, Any]) -> Dict[str, str]:
    """Every metric this container could not measure, metric -> reason."""
    return dict(container.get(UNAVAILABLE_KEY) or {})
