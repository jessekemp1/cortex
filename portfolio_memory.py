"""
Portfolio Memory - Access cross-project patterns, lessons, and metadata

Reads from ~/.claude/portfolio/project_index.json to provide:
- Project statistics and metadata
- Cross-project patterns
- Lessons learned from past work
- Project context for intelligence queries
- Project health tracking and trends
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from metric_result import mark_unavailable

logger = logging.getLogger(__name__)


def _repo_summary(repo_path: Path, days: int) -> Dict[str, Any]:
    """Git health for one repo: {commits, uncommitted, health, branches, ...}.

    Replaces three calls to HealthTracker.get_cached_health(), which does not
    exist — HealthTracker only exposes get_health_history / get_health_trends /
    get_portfolio_trends. Those calls raised AttributeError on every invocation,
    the surrounding `except` turned it into {"error": ...}, and callers reading
    overall.get("commits", 0) then saw 0 and reported "No commits in analysis
    period" unconditionally. GitAnalyzer.get_project_summary returns exactly the
    shape those callers already expect, so the fix is to call the API that exists.

    No caching layer here: get_project_summary shells out to git and is cheap
    enough at this call frequency, and a stale cache is what hid the breakage.
    """
    from cortex.agents.data_agent.analyzers.git_analyzer import GitAnalyzer

    return GitAnalyzer(repo_path).get_project_summary(days=days)


def _numeric_metrics(result: Dict[str, Any]) -> Dict[str, int]:
    """Pull score/commits/uncommitted out of a GitAnalyzer summary, strictly.

    GitAnalyzer.get_project_summary always populates health/commits/uncommitted,
    so reading them as `.get("count", 0)` never fired — but if that shape ever
    changed, the miss would surface as a real-looking 0 rather than an error, and
    a 0 is what every consumer threshold acts on. Indexing raises KeyError
    instead, which the callers' existing handlers turn into an explicit outage.
    """
    return {
        "score": result["health"]["total_score"],
        "commits": result["commits"]["count"],
        "uncommitted": result["uncommitted"]["total"],
    }


def _assess(score: int) -> str:
    """Map a 0-100 health score to an assessment label.

    Mirrors GitAnalyzer.calculate_health_score's bands (>=80 excellent, >=60
    good, >=40 fair, else needs_attention) so an aggregate score and a
    per-repo score never disagree about what the same number means.
    """
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "fair"
    return "needs_attention"


def _discovered_repos() -> Dict[str, Path]:
    """{lowercased project name: repo path} for repos under the workspace root.

    Live discovery, not the portfolio index: the index at
    ~/.claude/portfolio/project_index.json still lists the ~/Dev-era projects
    (Vortex/backend, alpha_arena, pupil) with empty paths, so it cannot resolve
    anything on its own.
    """
    try:
        from config import discover_projects
    except ImportError:
        try:
            from cortex.config import discover_projects
        except ImportError:
            return {}
    try:
        return {p["name"].lower(): Path(p["path"]) for p in discover_projects()}
    except Exception:
        logger.debug("project discovery failed", exc_info=True)
        return {}


def _resolve_repo_path(
    project_name: str, portfolio_projects: Optional[Dict[str, Any]] = None
) -> Optional[Path]:
    """The repo whose git history represents this project, or None.

    Order: the portfolio index's own recorded path when it is set and is a real
    checkout, then live discovery by name under the workspace root.

    Returns None rather than falling back to the workspace root. That fallback
    is exactly what made every project report one repo's numbers: with
    CORTEX_ROOT_DIR=~/dbx-dev, `cortex` was scored 57/100 off dbx-dev's 14
    commits and 18 uncommitted files while the cortex repo itself had 2 and 1.
    Five projects all reported the identical score because they were all
    measuring the same repo. A caller that cannot resolve a path must say so.
    """
    if portfolio_projects:
        for name, data in portfolio_projects.items():
            if name.lower() != project_name.lower():
                continue
            recorded = str((data or {}).get("path") or "").strip()
            if recorded:
                candidate = Path(recorded).expanduser()
                if (candidate / ".git").is_dir():
                    return candidate
            break

    return _discovered_repos().get(project_name.lower())


class PortfolioMemory:
    """Access portfolio-wide patterns, lessons, and project metadata"""

    def __init__(self, portfolio_path: Optional[Path] = None):
        # Resolve at call time, not at function-definition time — otherwise
        # we capture whatever Path.home() was when this module was first
        # imported, which breaks any caller that monkeypatches HOME later.
        if portfolio_path is None:
            portfolio_path = Path.home() / ".claude" / "portfolio"
        self.portfolio_path = portfolio_path
        self.index_file = portfolio_path / "project_index.json"
        self.portfolio_data = self._load_portfolio()

        # Lazy load health tracker
        self._health_tracker = None

    def _load_portfolio(self) -> Dict[str, Any]:
        """Load portfolio data from project_index.json"""
        if not self.index_file.exists():
            return {
                "meta": {
                    "last_updated": datetime.now().isoformat(),
                    "total_projects": 0,
                    "total_specs": 0,
                },
                "projects": {},
            }

        with open(self.index_file, "r") as f:
            return json.load(f)

    def _get_health_tracker(self):
        """Lazy load HealthTracker to avoid import errors"""
        if self._health_tracker is None:
            try:
                # Try absolute import first
                from cortex.agents.data_agent.analyzers.health_tracker import (
                    HealthTracker,
                )

                self._health_tracker = HealthTracker()
            except ImportError:
                try:
                    # Try relative import
                    from agents.data_agent.analyzers.health_tracker import HealthTracker

                    self._health_tracker = HealthTracker()
                except ImportError:
                    # HealthTracker not available
                    pass
        return self._health_tracker

    def get_stats(self, include_health: bool = True) -> Dict[str, Any]:
        """
        Get portfolio statistics

        Args:
            include_health: Include health summary (default: True)

        Returns:
            Portfolio statistics with optional health data
        """
        projects = self.portfolio_data.get("projects", {})

        # Calculate stats
        total_projects = len(projects)
        tier1_count = sum(1 for p in projects.values() if p.get("priority") == "tier1")
        tier2_count = sum(1 for p in projects.values() if p.get("priority") == "tier2")
        tier3_count = sum(1 for p in projects.values() if p.get("priority") == "tier3")

        # Active projects (commits in last 7 days)
        active_projects = [
            name for name, data in projects.items() if data.get("activity_commits_7d", 0) > 0
        ]

        # Tech stack distribution
        all_tech = []
        for proj_data in projects.values():
            all_tech.extend(proj_data.get("tech_stack", []))

        from collections import Counter

        tech_counts = Counter(all_tech)
        top_tech = dict(tech_counts.most_common(10))

        # Pattern distribution
        all_patterns = []
        for proj_data in projects.values():
            all_patterns.extend(proj_data.get("common_patterns", []))

        pattern_counts = Counter(all_patterns)
        top_patterns = dict(pattern_counts.most_common(10))

        stats = {
            "total_projects": total_projects,
            "by_priority": {
                "tier1": tier1_count,
                "tier2": tier2_count,
                "tier3": tier3_count,
            },
            "active_projects": len(active_projects),
            "active_project_names": active_projects[:10],  # Top 10
            "top_technologies": top_tech,
            "top_patterns": top_patterns,
            "last_updated": self.portfolio_data.get("meta", {}).get("last_updated", "Unknown"),
        }

        # Add health summary if requested
        if include_health:
            health_summary = self.get_portfolio_health_summary(days=7)
            if "error" not in health_summary:
                stats["health"] = {
                    "healthy_count": len(health_summary["aggregate"]["healthy_projects"]),
                    "at_risk_count": len(health_summary["aggregate"]["at_risk_projects"]),
                    "critical_count": len(health_summary["aggregate"]["critical_projects"]),
                    "projects": health_summary["projects"],
                }

        return stats

    def get_cross_project_patterns(
        self, pattern_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns

        Args:
            pattern_type: Optional filter (e.g., 'async_fastapi_routes', 'sqlalchemy_2.0_queries')

        Returns:
            List of pattern dictionaries with usage examples
        """
        projects = self.portfolio_data.get("projects", {})

        # Collect all patterns with their project usage
        pattern_usage = {}
        for project_name, project_data in projects.items():
            patterns = project_data.get("common_patterns", [])
            for pattern in patterns:
                if pattern_type and pattern != pattern_type:
                    continue

                if pattern not in pattern_usage:
                    pattern_usage[pattern] = {
                        "pattern": pattern,
                        "used_in": [],
                        "count": 0,
                    }

                pattern_usage[pattern]["used_in"].append(
                    {
                        "project": project_name,
                        "priority": project_data.get("priority", "tier3"),
                        "path": project_data.get("path", ""),
                    }
                )
                pattern_usage[pattern]["count"] += 1

        # Sort by usage count (most common first)
        patterns_list = sorted(pattern_usage.values(), key=lambda x: x["count"], reverse=True)

        return patterns_list

    def get_lessons_learned(
        self, project: Optional[str] = None, pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get lessons learned from past work

        Args:
            project: Optional project filter
            pattern: Optional pattern filter (e.g., 'async', 'sqlalchemy')

        Returns:
            List of lesson dictionaries
        """
        projects = self.portfolio_data.get("projects", {})
        lessons = []

        for project_name, project_data in projects.items():
            # Filter by project if specified
            if project and project_name != project:
                continue

            # Extract issues as lessons
            issues = project_data.get("common_issues", [])
            for issue in issues:
                # Filter by pattern if specified
                if pattern and pattern.lower() not in issue.lower():
                    continue

                lessons.append(
                    {
                        "lesson": issue,
                        "project": project_name,
                        "priority": project_data.get("priority", "tier3"),
                        "source": "common_issues",
                    }
                )

            # Extract from related_projects context (migration lessons)
            related = project_data.get("related_projects", [])
            if related and "migration" in str(project_data.get("tech_stack", [])).lower():
                lessons.append(
                    {
                        "lesson": f"Project shares context with: {', '.join(related)}",
                        "project": project_name,
                        "priority": project_data.get("priority", "tier3"),
                        "source": "related_projects",
                    }
                )

        return lessons

    def refresh_index(self) -> Dict[str, Any]:
        """Reconcile the portfolio index with the repos that actually exist.

        Nothing in this codebase writes project_index.json — `cortex onboard`
        seeds working memory and anti-patterns but never touches it — so once
        hand-seeded it could only rot. It kept describing the ~/Dev era
        (Vortex/backend, Vortex/frontend, alpha_arena, pupil) for months after
        CORTEX_ROOT_DIR moved to ~/dbx-dev. Health resolution no longer trusts
        it (discovery is the authority), but stale names still surface as
        unresolved entries, so make the refresh repeatable instead of manual.

        Each discovered repo gets its real path recorded; entries that no
        longer resolve move to `retired_projects`. Curated payloads
        (deep_analysis, tech_stack, warnings) are carried over in both
        directions — this reconciles, it never discards.

        Returns {"added", "updated", "retired", "total"}.
        """
        discovered = _discovered_repos()
        projects: Dict[str, Any] = dict(self.portfolio_data.get("projects", {}))
        retired: Dict[str, Any] = dict(self.portfolio_data.get("retired_projects", {}))

        existing_by_key = {name.lower(): name for name in projects}
        added, updated = [], []

        for key, repo_path in sorted(discovered.items()):
            name = existing_by_key.get(key, repo_path.name)
            entry = projects.get(name, {})
            was_new = name not in projects
            entry["path"] = str(repo_path)
            entry["rel"] = repo_path.name
            projects[name] = entry
            (added if was_new else updated).append(name)

        # Anything the index carries that resolves to no repo is retired, not
        # deleted: its analysis may still be worth reading after the move.
        newly_retired = []
        for name in list(projects):
            if _resolve_repo_path(name, projects) is None:
                retired[name] = projects.pop(name)
                retired[name]["retired_at"] = datetime.now().isoformat()
                newly_retired.append(name)

        self.portfolio_data["projects"] = projects
        self.portfolio_data["retired_projects"] = retired
        meta = self.portfolio_data.setdefault("meta", {})
        meta["last_updated"] = datetime.now().isoformat()
        meta["total_projects"] = len(projects)

        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_file, "w") as f:
            json.dump(self.portfolio_data, f, indent=2)

        return {
            "added": sorted(added),
            "updated": sorted(n for n in updated if n not in newly_retired),
            "retired": sorted(newly_retired),
            "total": len(projects),
        }

    def store_deep_analysis(
        self,
        project: str,
        tech_stack: Dict[str, Any],
        architecture: Dict[str, Any],
        code_quality: Dict[str, Any],
    ) -> bool:
        """
        Store deep analysis results in portfolio memory.

        Args:
            project: Project name
            tech_stack: Tech stack analysis results
            architecture: Architecture analysis results
            code_quality: Code quality analysis results

        Returns:
            True if stored successfully
        """
        try:
            projects = self.portfolio_data.get("projects", {})
            if project not in projects:
                projects[project] = {}

            # Store analysis results
            projects[project]["deep_analysis"] = {
                "tech_stack": tech_stack,
                "architecture": architecture,
                "code_quality": code_quality,
                "analyzed_at": datetime.now().isoformat(),
            }

            # Update tech stack in project data
            if tech_stack.get("languages"):
                projects[project]["tech_stack"] = tech_stack.get("languages", [])

            # Save updated portfolio
            self.portfolio_data["projects"] = projects
            self.portfolio_data["meta"]["last_updated"] = datetime.now().isoformat()

            # Save to file
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.index_file, "w") as f:
                json.dump(self.portfolio_data, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Failed to store deep analysis for {project}: {e}")
            return False

    def store_warnings(self, project: str, warnings: List[Dict[str, Any]]) -> bool:
        """
        Store warnings in portfolio memory.

        Args:
            project: Project name
            warnings: List of warning dictionaries

        Returns:
            True if stored successfully
        """
        try:
            projects = self.portfolio_data.get("projects", {})
            if project not in projects:
                projects[project] = {}

            # Store warnings
            projects[project]["warnings"] = warnings
            projects[project]["warnings_updated_at"] = datetime.now().isoformat()

            # Save updated portfolio
            self.portfolio_data["projects"] = projects
            self.portfolio_data["meta"]["last_updated"] = datetime.now().isoformat()

            # Save to file
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.index_file, "w") as f:
                json.dump(self.portfolio_data, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Failed to store warnings for {project}: {e}")
            return False

    def get_warnings(
        self, project: Optional[str] = None, severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get warnings for project(s).

        Args:
            project: Optional project filter
            severity: Optional severity filter (critical, high, medium, low)

        Returns:
            List of warnings
        """
        projects = self.portfolio_data.get("projects", {})
        all_warnings = []

        for project_name, project_data in projects.items():
            if project and project_name != project:
                continue

            warnings = project_data.get("warnings", [])
            for warning in warnings:
                if severity and warning.get("severity") != severity:
                    continue
                all_warnings.append(warning)

        # Sort by severity and creation time
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_warnings.sort(
            key=lambda w: (
                severity_order.get(w.get("severity", "low"), 3),
                w.get("created_at", ""),
            )
        )

        return all_warnings

    def get_project_context(self, project: str, include_health: bool = True) -> Dict[str, Any]:
        """
        Get detailed context for a specific project

        Args:
            project: Project name (e.g., 'vortex-backend', 'cortex')
            include_health: Include health score data (default: True)

        Returns:
            Project context dictionary
        """
        projects = self.portfolio_data.get("projects", {})

        if project not in projects:
            # Try case-insensitive match
            project_lower = project.lower()
            for proj_name in projects.keys():
                if proj_name.lower() == project_lower:
                    project = proj_name
                    break
            else:
                return {
                    "error": f"Project '{project}' not found in portfolio",
                    "available_projects": list(projects.keys())[:10],
                }

        project_data = projects[project]

        # Enrich with cross-project context
        patterns = project_data.get("common_patterns", [])
        pattern_context = []
        for pattern in patterns:
            cross_project_patterns = self.get_cross_project_patterns(pattern)
            if cross_project_patterns:
                pattern_context.append(
                    {
                        "pattern": pattern,
                        "also_used_in": [
                            p["project"]
                            for p in cross_project_patterns[0]["used_in"]
                            if p["project"] != project
                        ][
                            :5
                        ],  # Top 5 other projects
                    }
                )

        context = {
            "project": project,
            "path": project_data.get("path", ""),
            "priority": project_data.get("priority", "tier3"),
            "activity_7d": project_data.get("activity_commits_7d", 0),
            "tech_stack": project_data.get("tech_stack", []),
            "patterns": pattern_context,
            "common_issues": project_data.get("common_issues", []),
            "related_projects": project_data.get("related_projects", []),
        }

        # Add health data if requested
        if include_health:
            # Use Dev directory as git repo root
            health_data = self._get_health_for_project(project, days=7)
            if health_data:
                context["health"] = health_data

        return context

    def search_projects(self, query: str) -> List[str]:
        """
        Search for projects by name or technology

        Args:
            query: Search query (project name or tech)

        Returns:
            List of matching project names
        """
        projects = self.portfolio_data.get("projects", {})
        query_lower = query.lower()
        matches = []

        for project_name, project_data in projects.items():
            # Match on project name
            if query_lower in project_name.lower():
                matches.append(project_name)
                continue

            # Match on tech stack
            tech_stack = project_data.get("tech_stack", [])
            if any(query_lower in tech.lower() for tech in tech_stack):
                matches.append(project_name)
                continue

            # Match on patterns
            patterns = project_data.get("common_patterns", [])
            if any(query_lower in pattern.lower() for pattern in patterns):
                matches.append(project_name)

        return matches

    def _get_health_for_project(self, project_name: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Internal method to get health data for a project

        Measures the project's OWN repo. The workspace root is one repo among
        many under ~/dbx-dev, not a monorepo containing them all, so analyzing
        the root here reported the root's numbers under every project's name.

        Args:
            project_name: Project name
            days: Days to analyze

        Returns:
            Dict with score, assessment, trend, commits_7d, uncommitted_files or None
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return None

        repo_path = _resolve_repo_path(project_name, self.portfolio_data.get("projects", {}))
        if repo_path is None:
            return None

        try:
            result = _repo_summary(repo_path, days)

            # Extract health metrics from nested structure
            health_section = result.get("health", {})
            commits_section = result.get("commits", {})

            metrics = _numeric_metrics(result)
            return {
                "score": metrics["score"],
                "assessment": health_section.get("assessment", "unknown"),
                "trend": commits_section.get("trend", "unknown"),
                "commits_7d": metrics["commits"],
                "uncommitted_files": metrics["uncommitted"],
            }
        except Exception:
            return None

    def get_project_health(
        self, project_name: str, days: int = 7, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get health score and analysis for a specific project

        Args:
            project_name: Project name (e.g., 'vortex-backend', 'cortex')
            days: Days to analyze (default: 7)
            force_refresh: Force cache refresh

        Returns:
            Dict with health score, assessment, recommendations

        Example:
            >>> pm = PortfolioMemory()
            >>> health = pm.get_project_health("cortex")
            >>> print(health["score"])
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {"error": "HealthTracker not available", "project": project_name}

        projects = self.portfolio_data.get("projects", {})

        # Find project (case-insensitive)
        actual_name = project_name
        for proj_name in projects.keys():
            if proj_name.lower() == project_name.lower():
                actual_name = proj_name
                break

        repo_path = _resolve_repo_path(actual_name, projects)
        if repo_path is None:
            return {
                "error": (
                    f"No repo resolved for '{actual_name}' — it is not a git repo under "
                    "the workspace root and the portfolio index records no path for it"
                ),
                "project": actual_name,
            }

        try:
            result = _repo_summary(repo_path, days)

            # Extract and flatten health data
            health_section = result.get("health", {})
            commits_section = result.get("commits", {})

            metrics = _numeric_metrics(result)
            return {
                "project": actual_name,
                "repo_path": str(repo_path),
                "score": metrics["score"],
                "assessment": health_section.get("assessment", "unknown"),
                "breakdown": health_section.get("breakdown", {}),
                "trend": commits_section.get("trend", "unknown"),
                "commits_7d": metrics["commits"],
                "uncommitted_files": metrics["uncommitted"],
                "analysis_period_days": days,
                "from_cache": result.get("from_cache", False),
            }
        except Exception as e:
            return {"error": str(e), "project": actual_name}

    def get_portfolio_health_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get health summary for all projects in portfolio

        Args:
            days: Days to analyze (default: 7)

        Returns:
            Dict with health scores for all projects

        Example:
            >>> pm = PortfolioMemory()
            >>> summary = pm.get_portfolio_health_summary()
            >>> for project, health in summary["projects"].items():
            ...     print(f"{project}: {health['score']}")
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {"error": "HealthTracker not available"}

        index_projects = self.portfolio_data.get("projects", {})

        # Candidate set = every repo under the workspace root, plus any name the
        # portfolio index carries. Discovery is the authority on what exists;
        # the index is kept in the union so a curated entry is never dropped
        # silently, only reported as unresolved.
        discovered = _discovered_repos()
        candidates = {name: path for name, path in discovered.items()}
        names_by_key = {name: name for name in discovered}
        for name in index_projects:
            key = name.lower()
            names_by_key.setdefault(key, name)
            if key not in candidates:
                resolved = _resolve_repo_path(name, index_projects)
                if resolved is not None:
                    candidates[key] = resolved

        summary: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "total_projects": len(candidates),
            "analysis_period_days": days,
            "projects": {},
            "aggregate": {
                "healthy_projects": [],
                "at_risk_projects": [],
                "critical_projects": [],
                # A repo with no commits in the window has no health signal to
                # decline. Bucketing dormant repos as "critical" turned every
                # archived checkout into a MEDIUM alert, so they are listed
                # here and kept out of the alert path.
                "inactive_projects": [],
                # Index entries that resolve to no repo — visible staleness
                # rather than a fabricated score. The ~/Dev-era names
                # (Vortex/backend, alpha_arena, pupil) land here.
                "unresolved_projects": [],
            },
        }

        for name in index_projects:
            if name.lower() not in candidates:
                summary["aggregate"]["unresolved_projects"].append(name)

        scores: List[int] = []
        total_commits = 0
        total_uncommitted = 0
        errors: List[str] = []

        for key, repo_path in sorted(candidates.items()):
            project_name = names_by_key.get(key, key)
            try:
                result = _repo_summary(repo_path, days)
                metrics = _numeric_metrics(result)
            except Exception as e:  # one bad repo must not blank the portfolio
                errors.append(f"{project_name}: {e}")
                continue

            health_section = result.get("health", {})
            commits_section = result.get("commits", {})

            score = metrics["score"]
            commits = metrics["commits"]
            uncommitted = metrics["uncommitted"]

            summary["projects"][project_name] = {
                "score": score,
                "assessment": health_section.get("assessment", "unknown"),
                "trend": commits_section.get("trend", "unknown"),
                "commits": commits,
                "uncommitted": uncommitted,
                "repo_path": str(repo_path),
            }

            total_commits += commits
            total_uncommitted += uncommitted

            if commits == 0:
                summary["aggregate"]["inactive_projects"].append(project_name)
                continue

            scores.append(score)
            if score >= 70:
                summary["aggregate"]["healthy_projects"].append(project_name)
            elif score >= 50:
                summary["aggregate"]["at_risk_projects"].append(project_name)
            else:
                summary["aggregate"]["critical_projects"].append(project_name)

        # Every candidate failed to measure: that is a health-data outage, and
        # callers check for "error" precisely so they can say so instead of
        # reading a zero as real.
        if not summary["projects"]:
            detail = "; ".join(errors) if errors else "no repos resolved under the workspace root"
            return {"error": f"No project health could be measured ({detail})"}

        # Overall is scored over ACTIVE repos only, for the same reason the
        # buckets are: averaging in dormant checkouts dragged the portfolio
        # score down and produced a permanent "health is critical" alert.
        #
        # commits and uncommitted are real sums over every repo that measured, so
        # they are reported even when nothing was active. score and assessment
        # are not: with no active repo there is nothing to average, and the old
        # `else 0` produced a 0 that consumers compared against `< 50` and
        # reported as "Portfolio health is critical: 0/100" — a fabricated claim
        # about repos that were merely quiet.
        overall: Dict[str, Any] = {
            "trend": "mixed",
            "commits": total_commits,
            "uncommitted": total_uncommitted,
            "active_projects": len(scores),
        }
        if scores:
            overall_score = round(sum(scores) / len(scores))
            overall["score"] = overall_score
            overall["assessment"] = _assess(overall_score)
        else:
            reason = f"no active repo in the last {days}d to score ({len(summary['projects'])} measured, all quiet)"
            mark_unavailable(overall, "score", reason)
            mark_unavailable(overall, "assessment", reason)
        summary["overall"] = overall
        if errors:
            summary["partial_errors"] = errors

        return summary

    def get_project_health_trends(self, project_name: str) -> Dict[str, Any]:
        """
        Get comprehensive health trends for a project

        Args:
            project_name: Project name

        Returns:
            Dict with trends, insights, recommendations

        Example:
            >>> pm = PortfolioMemory()
            >>> trends = pm.get_project_health_trends("cortex")
            >>> print(trends["insights"])
        """
        tracker = self._get_health_tracker()
        if not tracker:
            return {"error": "HealthTracker not available", "project": project_name}

        projects = self.portfolio_data.get("projects", {})

        # Find project (case-insensitive)
        project_data = None
        actual_name = project_name
        for proj_name, data in projects.items():
            if proj_name.lower() == project_name.lower():
                project_data = data
                actual_name = proj_name
                break

        if not project_data:
            return {"error": f"Project '{project_name}' not found in portfolio"}

        project_path = Path(project_data.get("path", ""))
        if not project_path.exists():
            return {"error": f"Project path not found: {project_path}"}

        try:
            trends = tracker.get_health_trends(actual_name, project_path)
            return trends
        except Exception as e:
            return {"error": str(e), "project": actual_name}


# CLI helper for testing
if __name__ == "__main__":
    import sys

    pm = PortfolioMemory()

    if len(sys.argv) < 2:
        print("Usage: python portfolio_memory.py <command> [args]")
        print("Commands: stats, patterns, lessons, project <name>, search <query>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "stats":
        import json

        print(json.dumps(pm.get_stats(), indent=2))

    elif command == "patterns":
        pattern_type = sys.argv[2] if len(sys.argv) > 2 else None
        patterns = pm.get_cross_project_patterns(pattern_type)
        for p in patterns:
            print(f"\n{p['pattern']} (used in {p['count']} projects)")
            for usage in p["used_in"][:3]:
                print(f"  - {usage['project']} ({usage['priority']})")

    elif command == "lessons":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        lessons = pm.get_lessons_learned(project=project)
        for lesson in lessons:
            print(f"\n[{lesson['project']}] {lesson['lesson']}")

    elif command == "project":
        if len(sys.argv) < 3:
            print("Usage: python portfolio_memory.py project <name>")
            sys.exit(1)
        project_name = sys.argv[2]
        context = pm.get_project_context(project_name)
        import json

        print(json.dumps(context, indent=2))

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python portfolio_memory.py search <query>")
            sys.exit(1)
        query = sys.argv[2]
        matches = pm.search_projects(query)
        print(f"Found {len(matches)} projects matching '{query}':")
        for match in matches:
            print(f"  - {match}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
