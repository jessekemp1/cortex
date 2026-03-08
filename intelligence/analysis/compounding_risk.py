#!/usr/bin/env python3
"""
Compounding Risk Assessor — Examined Engineer, Principle 2.

Quantifies how fast a current technical problem grows over time.
Produces 6-month trajectory assessments for projects and code locations.

Usage (CLI):
    python -m cortex.intelligence.analysis.compounding_risk --project vortex-backend
    python -m cortex.intelligence.analysis.compounding_risk --file cortex/bridge.py

Usage (API):
    from cortex.intelligence.analysis.compounding_risk import CompoundingRiskAssessor
    assessor = CompoundingRiskAssessor()
    risk = assessor.assess_project("vortex-backend")
    print(risk.to_inline())   # [Conf: 72% | Assumption: change velocity stable | ...]
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Data Model ──────────────────────────────────────────────────────────────


@dataclass
class CompoundingRisk:
    """A quantified compounding risk assessment."""

    target: str  # project name or file path
    rate: str  # "low" | "medium" | "high" | "critical"
    confidence: int  # 0-100
    specific_risk: str  # concrete description of what compounds
    trajectory_6mo: str  # "At current rate, in 6mo this becomes..."
    assumption: str  # the key assumption this assessment rests on
    flips_if: str  # what change invalidates this assessment
    boring_risk: Optional[str] = None  # the quiet risk nobody is talking about
    signals: list = field(default_factory=list)  # data points used in assessment

    def to_inline(self) -> str:
        """Compact inline format for appending to recommendations."""
        return (
            f"[Conf: {self.confidence}% | "
            f"Assumption: {self.assumption} | "
            f"Flips if: {self.flips_if} | "
            f"6mo: {self.trajectory_6mo}]"
        )

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "rate": self.rate,
            "confidence": self.confidence,
            "specific_risk": self.specific_risk,
            "trajectory_6mo": self.trajectory_6mo,
            "assumption": self.assumption,
            "flips_if": self.flips_if,
            "boring_risk": self.boring_risk,
            "signals": self.signals,
            "inline": self.to_inline(),
        }

    def to_report(self) -> str:
        lines = [
            f"## Compounding Risk: {self.target}",
            f"**Rate**: {self.rate.upper()} (confidence {self.confidence}%)",
            f"**Specific risk**: {self.specific_risk}",
            f"**6-month trajectory**: {self.trajectory_6mo}",
            f"**Key assumption**: {self.assumption}",
            f"**Flips if**: {self.flips_if}",
        ]
        if self.boring_risk:
            lines.append(f"**Boring risk (untracked)**: {self.boring_risk}")
        if self.signals:
            lines.append("**Signals used**:")
            for s in self.signals:
                lines.append(f"  - {s}")
        return "\n".join(lines)


# ─── Assessor ────────────────────────────────────────────────────────────────


class CompoundingRiskAssessor:
    """
    Assesses compounding risk using git history, test metrics, and anti-pattern logs.

    Risk rate mapping:
      - low:      Problem exists but changes slowly; 6mo impact is manageable
      - medium:   Problem grows with feature velocity; 6mo impact is significant
      - high:     Problem multiplies with each change; 6mo impact is structural
      - critical: Problem is already compounding faster than team can manage
    """

    REPO_ROOT = Path(__file__).parent.parent.parent.parent  # /Dev
    CORTEX_DIR = Path.home() / ".cortex"
    ANTI_PATTERNS_FILE = Path.home() / ".claude" / "memories" / "anti-patterns.md"
    METRICS_FILE = CORTEX_DIR / "metrics" / "tests.json"

    # Known high-churn files from domain knowledge
    HIGH_CHURN_PATTERNS = [
        "bridge.py",
        "bridge_endpoint.py",
        "intake.py",
        "router.py",
        "forecast_ingestion",
        "ensemble",
        "competition",
    ]

    # Projects with known risk profiles
    PROJECT_PROFILES = {
        "vortex-backend": {
            "test_count_target": 3200,
            "known_risks": ["legacy permissive assertions", "GRIB longitude convention violations"],
            "boring_risk": "forecast_ingestion.py has no load test — data pipeline correctness assumed, never measured under concurrent requests",
        },
        "cortex": {
            "test_count_target": 850,
            "known_risks": [
                "hardcoded quality scores",
                "orchestration pipeline not monitored end-to-end in CI",
            ],
            "boring_risk": "bridge_endpoint.py (2154 lines) has a single owner and no architectural tests",
        },
        "alpha-arena": {
            "test_count_target": 520,
            "known_risks": [
                "circular import risk (model_competition/ensemble_analyzer)",
                "ON HOLD — strategy drift",
            ],
            "boring_risk": "PaperExecutor has been 'wired' for weeks with no actual paper trades recorded",
        },
        "pupil": {
            "test_count_target": 1260,
            "known_risks": ["Phase 2 batches stale since Feb 26"],
            "boring_risk": "Nowcasting Phase 2 stale = data being predicted on has drifted; model validity window unknown",
        },
    }

    def assess_project(self, project: str) -> CompoundingRisk:
        """Assess compounding risk for a named project."""
        profile = self.PROJECT_PROFILES.get(project, {})
        signals = []

        # 1. Change velocity (commits in last 14 days touching project)
        velocity = self._git_change_velocity(project)
        signals.append(f"Change velocity: {velocity} commits/14d touching {project}/")

        # 2. Test count vs. target
        test_count = self._read_test_count(project)
        target = profile.get("test_count_target", 500)
        test_ratio = test_count / target if target else 1.0
        signals.append(f"Test coverage ratio: {test_count}/{target} ({test_ratio:.0%})")

        # 3. Anti-pattern recurrence
        recurrence_count = self._count_anti_pattern_recurrences(project)
        signals.append(f"Anti-pattern recurrences logged: {recurrence_count}")

        # 4. Known risks
        known_risks = profile.get("known_risks", [])

        # Compute rate
        rate, confidence = self._compute_rate(velocity, test_ratio, recurrence_count, known_risks)

        # Build trajectory
        primary_risk = known_risks[0] if known_risks else "untracked debt"
        trajectory = self._build_trajectory(project, rate, velocity, primary_risk)

        return CompoundingRisk(
            target=project,
            rate=rate,
            confidence=confidence,
            specific_risk=primary_risk,
            trajectory_6mo=trajectory,
            assumption="change velocity stays within 20% of current level",
            flips_if="strict CI gates added for all known_risks patterns, or feature freeze",
            boring_risk=profile.get("boring_risk"),
            signals=signals,
        )

    def assess_file(self, file_path: str) -> CompoundingRisk:
        """Assess compounding risk for a specific file."""
        path = Path(file_path)
        signals = []

        # 1. Caller count (how many other files import this)
        callers = self._count_callers(file_path)
        signals.append(f"Import callers: {callers}")

        # 2. Churn rate (commits touching this file in last 30 days)
        churn = self._git_file_churn(file_path)
        signals.append(f"File churn (30d): {churn} commits")

        # 3. Test coverage signal (does a test file exist for this module?)
        has_test = self._has_test_file(file_path)
        signals.append(f"Dedicated test file: {'yes' if has_test else 'NO'}")

        # 4. High-churn pattern match
        is_high_churn = any(p in file_path for p in self.HIGH_CHURN_PATTERNS)

        # Compute rate
        if callers > 20 and not has_test:
            rate, confidence = "critical", 85
        elif callers > 10 and churn > 5:
            rate, confidence = "high", 75
        elif callers > 5 or (is_high_churn and not has_test):
            rate, confidence = "medium", 65
        else:
            rate, confidence = "low", 70

        name = path.name
        trajectory = (
            f"At current change rate ({churn} commits/30d), {name} with {callers} callers "
            f"and {'no' if not has_test else 'some'} test coverage accumulates silent regressions. "
            f"6mo: each new caller adds undiscovered integration surface."
        )

        return CompoundingRisk(
            target=file_path,
            rate=rate,
            confidence=confidence,
            specific_risk=f"{name}: {callers} callers, {churn} commits/30d, test={'yes' if has_test else 'NO'}",
            trajectory_6mo=trajectory,
            assumption="call graph doesn't shrink and churn rate holds",
            flips_if=f"test coverage added for {name} and callers stabilize",
            signals=signals,
        )

    def assess_portfolio(self) -> list[CompoundingRisk]:
        """Assess all known projects."""
        return [self.assess_project(p) for p in self.PROJECT_PROFILES]

    # ─── Private Helpers ──────────────────────────────────────────────────────

    def _git_change_velocity(self, project: str) -> int:
        """Count commits touching project directory in last 14 days."""
        # Explicit mapping: profile key → actual directory on disk.
        # Cannot be derived from the key name (e.g. "vortex-backend" lives in "Vortex/").
        dir_map = {
            "vortex-backend": "Vortex",
            "cortex": "cortex",
            "alpha-arena": "alpha_arena",
            "pupil": "pupil",
        }
        git_dir = dir_map.get(project, project)
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--since=14 days ago", "--", f"{git_dir}/"],
                capture_output=True,
                text=True,
                cwd=self.REPO_ROOT,
                timeout=5,
            )
            return len([l for l in result.stdout.splitlines() if l.strip()])
        except Exception:
            return 0

    def _git_file_churn(self, file_path: str) -> int:
        """Count commits touching a file in last 30 days."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--since=30 days ago", "--", file_path],
                capture_output=True,
                text=True,
                cwd=self.REPO_ROOT,
                timeout=5,
            )
            return len([l for l in result.stdout.splitlines() if l.strip()])
        except Exception:
            return 0

    def _count_callers(self, file_path: str) -> int:
        """Estimate how many files import this module."""
        try:
            module_name = Path(file_path).stem
            result = subprocess.run(
                [
                    "grep",
                    "-rl",
                    "--include=*.py",
                    "--exclude-dir=.git",
                    "--exclude-dir=node_modules",
                    "--exclude-dir=.venv",
                    "--exclude-dir=venv",
                    "--exclude-dir=__pycache__",
                    "--exclude-dir=data",
                    f"import {module_name}",
                    str(self.REPO_ROOT),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return len([l for l in result.stdout.splitlines() if l.strip()])
        except Exception:
            return 0

    def _has_test_file(self, file_path: str) -> bool:
        """Check if a dedicated test file exists for this module."""
        stem = Path(file_path).stem
        repo = self.REPO_ROOT
        candidates = list(repo.rglob(f"test_{stem}.py")) + list(repo.rglob(f"{stem}_test.py"))
        return len(candidates) > 0

    def _read_test_count(self, project: str) -> int:
        """Read test count from cortex metrics or fall back to MEMORY heuristics."""
        known = {
            "vortex-backend": 3153,
            "cortex": 842,
            "alpha-arena": 519,
            "pupil": 1255,
            "winfield": 409,
        }
        if self.METRICS_FILE.exists():
            try:
                data = json.loads(self.METRICS_FILE.read_text())
                key = project.replace("-", "_")
                if key in data:
                    return data[key].get("passed", 0) + data[key].get("failed", 0)
            except Exception:
                pass
        return known.get(project, 0)

    def _count_anti_pattern_recurrences(self, project: str) -> int:
        """Count anti-patterns logged for this project."""
        if not self.ANTI_PATTERNS_FILE.exists():
            return 0
        try:
            text = self.ANTI_PATTERNS_FILE.read_text()
            # Rough heuristic: count entries mentioning this project
            return text.lower().count(project.replace("-", " ").lower())
        except Exception:
            return 0

    def _compute_rate(
        self, velocity: int, test_ratio: float, recurrence_count: int, known_risks: list
    ) -> tuple[str, int]:
        """Compute compounding rate and confidence from signals."""
        score = 0
        confidence = 60

        # Velocity contribution
        if velocity > 20:
            score += 3
            confidence += 10
        elif velocity > 10:
            score += 2
            confidence += 5
        elif velocity > 3:
            score += 1

        # Test ratio contribution (inverse — lower coverage = higher risk)
        if test_ratio < 0.7:
            score += 3
            confidence += 10
        elif test_ratio < 0.85:
            score += 2
            confidence += 5
        elif test_ratio < 1.0:
            score += 1

        # Recurrence (repeated anti-patterns = environment not fixed)
        if recurrence_count > 3:
            score += 2
            confidence += 10
        elif recurrence_count > 1:
            score += 1
            confidence += 5

        # Known risks
        score += min(len(known_risks), 2)

        confidence = min(confidence, 90)

        if score >= 8:
            return "critical", confidence
        elif score >= 5:
            return "high", confidence
        elif score >= 3:
            return "medium", confidence
        else:
            return "low", confidence

    def _build_trajectory(self, project: str, rate: str, velocity: int, risk: str) -> str:
        rate_desc = {
            "critical": "structural breakdown — new features become liabilities faster than they ship",
            "high": "a significant refactor that blocks feature velocity",
            "medium": "a painful investigation that costs 2-3 sprints",
            "low": "a known debt item that can be scheduled normally",
        }
        return (
            f"At current rate ({velocity} commits/14d), {project}'s '{risk}' becomes "
            f"{rate_desc.get(rate, 'an unresolved issue')}."
        )


# ─── PRD Regression Suite ────────────────────────────────────────────────────


def verify() -> int:
    """
    Run the full PRD regression suite (Examined Engineer Option B).

    Suite A: Module smoke tests (always run — pure Python)
    Suite B: CLI subprocess tests (always run — pure Python)
    Suite C: Bridge HTTP tests (conditional — skip gracefully if bridge offline)

    Returns:
        0: Full pass (all suites including bridge)
        1: Any assertion failed
        2: Partial pass (A+B passed, C skipped — bridge offline)
    """
    import json as _json
    import subprocess as _sub
    import sys
    import urllib.request
    from urllib.error import HTTPError

    results: dict[str, list[str]] = {"passed": [], "failed": [], "skipped": []}

    def ok(name: str, detail: str = "") -> None:
        msg = f"[PASS] {name}" + (f" ({detail})" if detail else "")
        print(msg)
        results["passed"].append(name)

    def fail(name: str, reason: str) -> None:
        print(f"[FAIL] {name}: {reason}")
        results["failed"].append(name)

    def skip(name: str, reason: str) -> None:
        print(f"[SKIP] {name} ({reason})")
        results["skipped"].append(name)

    # ── Suite A: Module smoke tests ───────────────────────────────────────────

    try:
        assessor = CompoundingRiskAssessor()
        ok("A1", "Module import and instantiation")
    except Exception as e:
        fail("A1", f"instantiation failed: {e}")
        print("\nRESULT: FAIL (A1 fatal — cannot continue)")
        return 1

    try:
        r = assessor.assess_project("vortex-backend")
        assert r.rate in ["low", "medium", "high", "critical"], f"bad rate: {r.rate}"
        assert 0 < r.confidence <= 90, f"bad confidence: {r.confidence}"
        assert r.trajectory_6mo, "empty trajectory"
        ok("A2", f"vortex-backend rate={r.rate}, conf={r.confidence}%")
    except Exception as e:
        fail("A2", str(e))

    try:
        risks = assessor.assess_portfolio()
        assert len(risks) == 4, f"expected 4 projects, got {len(risks)}"
        expected = {"vortex-backend", "cortex", "alpha-arena", "pupil"}
        actual = {r.target for r in risks}
        assert actual == expected, f"target mismatch: {actual}"
        assert all(r.rate in ["low", "medium", "high", "critical"] for r in risks)
        ok("A3", "Portfolio assessment (4 projects)")
    except Exception as e:
        fail("A3", str(e))

    try:
        rf = assessor.assess_file("cortex/bridge.py")
        assert rf.rate in ["low", "medium", "high", "critical"], f"bad rate: {rf.rate}"
        assert len(rf.signals) >= 2, f"too few signals: {len(rf.signals)}"
        ok("A4", f"File assessment cortex/bridge.py rate={rf.rate}")
    except Exception as e:
        fail("A4", str(e))

    try:
        r = assessor.assess_project("vortex-backend")
        d = r.to_dict()
        _json.dumps(d)  # must not raise
        assert "target" in d and "rate" in d and "inline" in d
        ok("A5", "to_dict() JSON-serializable")
    except Exception as e:
        fail("A5", str(e))

    try:
        r = assessor.assess_project("vortex-backend")
        inline = r.to_inline()
        assert "[Conf:" in inline, f"missing [Conf: in: {inline}"
        assert "% |" in inline
        assert "Assumption:" in inline
        assert "Flips if:" in inline
        assert "6mo:" in inline
        ok("A6", "to_inline() format compliance")
    except Exception as e:
        fail("A6", str(e))

    try:
        r = assessor.assess_project("vortex-backend")
        report = r.to_report()
        assert "## Compounding Risk:" in report
        assert "**Rate**:" in report
        assert "**Specific risk**:" in report
        assert "**6-month trajectory**:" in report
        assert "**Key assumption**:" in report
        assert "**Flips if**:" in report
        ok("A7", "to_report() all fields present")
    except Exception as e:
        fail("A7", str(e))

    try:
        r = assessor.assess_project("vortex-backend")
        assert r.rate in ["high", "critical"], (
            f"expected high or critical (post dir_map fix), got: {r.rate}"
        )
        ok("A8", f"vortex-backend rate={r.rate} (high or critical confirmed)")
    except Exception as e:
        fail("A8", str(e))

    # ── Suite B: CLI subprocess tests ─────────────────────────────────────────

    cli = [sys.executable, "-m", "cortex.intelligence.analysis.compounding_risk"]

    try:
        out = _sub.run(cli + ["--help"], capture_output=True, text=True, timeout=10).stdout
        assert "--verify" in out, "--verify not in help output"
        ok("B1", "--help includes --verify flag")
    except Exception as e:
        fail("B1", str(e))

    try:
        out = _sub.run(
            cli + ["--project", "vortex-backend"], capture_output=True, text=True, timeout=15
        ).stdout
        assert "**Rate**:" in out, "Rate: missing from report"
        assert "**Specific risk**:" in out, "Specific risk: missing from report"
        ok("B2", "--project report format")
    except Exception as e:
        fail("B2", str(e))

    try:
        out = _sub.run(cli + ["--portfolio"], capture_output=True, text=True, timeout=30).stdout
        for name in ["vortex-backend", "cortex", "alpha-arena", "pupil"]:
            assert name in out, f"{name} missing from portfolio output"
        ok("B3", "--portfolio lists all 4 projects")
    except Exception as e:
        fail("B3", str(e))

    try:
        out = _sub.run(
            cli + ["--project", "vortex-backend", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        parsed = _json.loads(out)
        assert "rate" in parsed and "confidence" in parsed
        ok("B4", "--json valid JSON")
    except Exception as e:
        fail("B4", str(e))

    try:
        out = _sub.run(
            cli + ["--portfolio", "--json"], capture_output=True, text=True, timeout=30
        ).stdout
        parsed = _json.loads(out)
        assert isinstance(parsed, list) and len(parsed) == 4, (
            f"expected list[4], got {type(parsed).__name__}[{len(parsed) if isinstance(parsed, list) else '?'}]"
        )
        ok("B5", "--portfolio --json list of 4")
    except Exception as e:
        fail("B5", str(e))

    # ── Suite C: Bridge HTTP tests (conditional) ──────────────────────────────

    bridge_alive = False
    try:
        urllib.request.urlopen("http://localhost:8765/health", timeout=3)
        bridge_alive = True
    except Exception:
        pass

    if not bridge_alive:
        for label in [
            "C1: /meta/compounding",
            "C2: /meta/compounding/portfolio",
            "C3: /meta/compounding/file",
        ]:
            skip(label, "bridge offline")
    else:
        try:
            with urllib.request.urlopen(
                "http://localhost:8765/meta/compounding?project=vortex-backend", timeout=10
            ) as resp:
                data = _json.loads(resp.read())
            assert data.get("meta_layer") == "compounding_risk"
            assert "rate" in data and "confidence" in data
            ok("C1", f"/meta/compounding (rate={data['rate']})")
        except HTTPError as e:
            if e.code == 404:
                skip("C1", "endpoint not found — bridge running stale code, restart required")
            else:
                fail("C1", str(e))
        except Exception as e:
            fail("C1", str(e))

        try:
            with urllib.request.urlopen(
                "http://localhost:8765/meta/compounding/portfolio", timeout=10
            ) as resp:
                data = _json.loads(resp.read())
            assert isinstance(data.get("projects"), list) and len(data["projects"]) == 4
            ok("C2", f"/meta/compounding/portfolio ({len(data['projects'])} projects)")
        except HTTPError as e:
            if e.code == 404:
                skip("C2", "endpoint not found — bridge running stale code, restart required")
            else:
                fail("C2", str(e))
        except Exception as e:
            fail("C2", str(e))

        try:
            with urllib.request.urlopen(
                "http://localhost:8765/meta/compounding/file?path=cortex/bridge.py", timeout=10
            ) as resp:
                data = _json.loads(resp.read())
            assert data.get("meta_layer") == "compounding_risk_file"
            ok("C3", "/meta/compounding/file")
        except HTTPError as e:
            if e.code == 404:
                skip("C3", "endpoint not found — bridge running stale code, restart required")
            else:
                fail("C3", str(e))
        except Exception as e:
            fail("C3", str(e))

    # ── Summary ───────────────────────────────────────────────────────────────

    n_pass = len(results["passed"])
    n_fail = len(results["failed"])
    n_skip = len(results["skipped"])
    bridge_msg = "bridge online" if bridge_alive else "bridge offline"

    print()
    if n_fail > 0:
        print(f"RESULT: FAIL ({n_pass} passed, {n_fail} failed, {n_skip} skipped)")
        return 1
    elif n_skip > 0:
        print(
            f"RESULT: PARTIAL PASS "
            f"({n_pass} passed, {n_fail} failed, {n_skip} skipped — {bridge_msg})"
        )
        return 2
    else:
        print(
            f"RESULT: FULL PASS ({n_pass} passed, {n_fail} failed, {n_skip} skipped — {bridge_msg})"
        )
        return 0


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Compounding Risk Assessor")
    parser.add_argument("--project", help="Assess a named project")
    parser.add_argument("--file", help="Assess a specific file path")
    parser.add_argument("--portfolio", action="store_true", help="Assess all projects")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run PRD regression suite (exit 0=full pass, 2=partial/bridge-offline, 1=fail)",
    )
    args = parser.parse_args()

    if args.verify:
        sys.exit(verify())

    assessor = CompoundingRiskAssessor()

    if args.portfolio:
        risks = assessor.assess_portfolio()
        if args.json:
            print(json.dumps([r.to_dict() for r in risks], indent=2))
        else:
            for r in sorted(
                risks,
                key=lambda x: ["low", "medium", "high", "critical"].index(x.rate),
                reverse=True,
            ):
                print(r.to_report())
                print()
    elif args.project:
        risk = assessor.assess_project(args.project)
        if args.json:
            print(json.dumps(risk.to_dict(), indent=2))
        else:
            print(risk.to_report())
            print(f"\n**Inline format**: {risk.to_inline()}")
    elif args.file:
        risk = assessor.assess_file(args.file)
        if args.json:
            print(json.dumps(risk.to_dict(), indent=2))
        else:
            print(risk.to_report())
            print(f"\n**Inline format**: {risk.to_inline()}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
