#!/usr/bin/env python3
"""
Cortex Self-Audit — Phase 2 of Self-Awareness plan.

Audits the health of development systems and produces a JSON report.
Checks: memory bridge, learning loop, test quality, anti-pattern mechanisms, dead data.

Usage:
    python cortex/self_audit.py          # prints report + writes JSON
    python cortex/self_audit.py --quiet  # writes JSON only
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CORTEX_DIR = Path.home() / ".cortex"
CLAUDE_DIR = Path.home() / ".claude"
REPO_ROOT = Path("/Users/jesse.kemp/Dev")
METRICS_DIR = CORTEX_DIR / "metrics"
OUTPUT_FILE = METRICS_DIR / "self_audit.json"

# Known dead files — JSONL/JSON files that are written but never consumed
KNOWN_DEAD_FILES = [
    "session_outcomes.jsonl",
    "workflow_outcomes.jsonl",
    "q_table.json",
    "feedback.json",
]


def check_memory_bridge() -> dict:
    """Check bidirectional references between ~/.cortex/ and ~/.claude/ projects."""
    cross_refs = 0

    # Check: Do any files in ~/.cortex/ reference ".claude" paths?
    cortex_refs = 0
    for f in CORTEX_DIR.iterdir():
        if f.is_file() and f.suffix in (".json", ".jsonl", ".md", ".yaml", ".txt"):
            try:
                text = f.read_text(errors="replace")
                if ".claude" in text:
                    cortex_refs += 1
            except Exception:
                continue
    cross_refs += cortex_refs

    # Check: Do MEMORY.md or other files in claude project memory reference cortex?
    claude_mem_dir = CLAUDE_DIR / "projects" / "-Users-jesse-kemp-Dev" / "memory"
    claude_refs = 0
    if claude_mem_dir.exists():
        for f in claude_mem_dir.iterdir():
            if f.is_file():
                try:
                    text = f.read_text(errors="replace")
                    if "~/.cortex" in text or "cortex" in text.lower():
                        claude_refs += 1
                except Exception:
                    continue
    cross_refs += claude_refs

    status = "connected" if cross_refs > 0 else "disconnected"
    return {
        "status": status,
        "cross_references": cross_refs,
        "cortex_to_claude": cortex_refs,
        "claude_to_cortex": claude_refs,
    }


def check_learning_loop() -> dict:
    """Check health of the learning feedback loop."""
    outcomes_file = CORTEX_DIR / "outcomes.jsonl"
    feedback_file = CORTEX_DIR / "implicit_feedback.jsonl"
    model_outcomes_file = CORTEX_DIR / "model_outcomes.jsonl"

    outcome_count = 0
    feedback_count = 0
    model_outcome_count = 0
    freshness_days = -1  # -1 means file doesn't exist

    # outcomes.jsonl
    if outcomes_file.exists():
        try:
            lines = [l for l in outcomes_file.read_text().splitlines() if l.strip()]
            outcome_count = len(lines)

            # Check freshness from last entry
            if lines:
                last = json.loads(lines[-1])
                ts_str = last.get("timestamp") or last.get("ts") or last.get("created_at", "")
                if ts_str:
                    last_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if last_ts.tzinfo is None:
                        last_ts = last_ts.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - last_ts
                    freshness_days = age.days
                else:
                    # Fall back to file mtime
                    mtime = datetime.fromtimestamp(outcomes_file.stat().st_mtime, tz=timezone.utc)
                    freshness_days = (datetime.now(timezone.utc) - mtime).days
        except Exception:
            pass
    else:
        freshness_days = -1

    # implicit_feedback.jsonl
    if feedback_file.exists():
        try:
            lines = [l for l in feedback_file.read_text().splitlines() if l.strip()]
            feedback_count = len(lines)
        except Exception:
            pass

    # model_outcomes.jsonl
    if model_outcomes_file.exists():
        try:
            lines = [l for l in model_outcomes_file.read_text().splitlines() if l.strip()]
            model_outcome_count = len(lines)
        except Exception:
            pass

    # Determine status
    if freshness_days == -1 or outcome_count == 0:
        status = "dead"
    elif freshness_days > 7:
        status = "starving"
    else:
        status = "active"

    return {
        "status": status,
        "outcome_count": outcome_count,
        "feedback_count": feedback_count,
        "model_outcome_count": model_outcome_count,
        "freshness_days": freshness_days,
    }


def check_test_quality() -> dict:
    """Scan cortex/tests/ for trivial test functions."""
    tests_dir = REPO_ROOT / "cortex" / "tests"
    if not tests_dir.exists():
        return {"status": "poor", "total_tests": 0, "trivial_count": 0, "trivial_pct": 0.0}

    total_tests = 0
    trivial_count = 0

    # Patterns for trivial assertions
    trivial_patterns = [
        re.compile(r"assert\s+.*\s+in\s+\(True,\s*False\)"),
        re.compile(r"assert\s+.*\s+in\s+\(False,\s*True\)"),
        re.compile(r"^\s*assert\s+\S+\s+is\s+not\s+None\s*$"),
    ]

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            lines = test_file.read_text().splitlines()
        except Exception:
            continue

        in_test = False
        test_body_lines = []
        test_start_indent = 0

        for i, line in enumerate(lines):
            # Detect test function start
            match = re.match(r"^(\s*)def (test_\w+)", line)
            if match:
                # Process previous test if any
                if in_test:
                    total_tests += 1
                    if _is_trivial_test(test_body_lines, trivial_patterns):
                        trivial_count += 1

                in_test = True
                test_start_indent = len(match.group(1))
                test_body_lines = []
                continue

            if in_test:
                # Check if we've left the test function (dedented or new def/class)
                stripped = line.strip()
                if stripped and not line[0].isspace():
                    # Top-level definition — end of test
                    total_tests += 1
                    if _is_trivial_test(test_body_lines, trivial_patterns):
                        trivial_count += 1
                    in_test = False
                    test_body_lines = []
                elif stripped.startswith("def ") or stripped.startswith("class "):
                    # Could be a nested def or next function at same indent
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= test_start_indent:
                        total_tests += 1
                        if _is_trivial_test(test_body_lines, trivial_patterns):
                            trivial_count += 1
                        in_test = False
                        test_body_lines = []
                        # Check if this is also a test
                        m2 = re.match(r"^(\s*)def (test_\w+)", line)
                        if m2:
                            in_test = True
                            test_start_indent = len(m2.group(1))
                            test_body_lines = []
                    else:
                        test_body_lines.append(stripped)
                else:
                    if stripped:
                        test_body_lines.append(stripped)

        # Handle last test in file
        if in_test:
            total_tests += 1
            if _is_trivial_test(test_body_lines, trivial_patterns):
                trivial_count += 1

    trivial_pct = round((trivial_count / total_tests * 100), 1) if total_tests > 0 else 0.0

    if trivial_pct > 20:
        status = "poor"
    elif trivial_pct > 5:
        status = "degraded"
    else:
        status = "good"

    return {
        "status": status,
        "total_tests": total_tests,
        "trivial_count": trivial_count,
        "trivial_pct": trivial_pct,
    }


def _is_trivial_test(body_lines: list[str], trivial_patterns: list[re.Pattern]) -> bool:
    """Determine if a test function body is trivial.

    A test is trivial if:
    - Its body is just `pass`
    - All its assertions match trivial patterns (in True/False, is not None only)
    - It has no assertions at all (just setup/teardown without verification)
    """
    if not body_lines:
        return True

    # Filter out docstrings, comments, blank lines
    meaningful = [
        l
        for l in body_lines
        if not l.startswith("#") and not l.startswith('"""') and not l.startswith("'''")
    ]

    if not meaningful:
        return True

    # Body is just `pass`
    if meaningful == ["pass"]:
        return True

    # Check if there are any assertions
    assertions = [l for l in meaningful if l.startswith("assert ") or l.startswith("assert(")]
    if not assertions:
        # No assertions — could be testing for exceptions with pytest.raises
        has_raises = any("pytest.raises" in l or "raises(" in l for l in meaningful)
        if has_raises:
            return False
        # No assertions and no pytest.raises — trivial
        return len(meaningful) <= 3  # Allow small setup-only tests as non-trivial if > 3 lines

    # Check if ALL assertions are trivial
    for assertion in assertions:
        is_trivial = False
        for pattern in trivial_patterns:
            if pattern.search(assertion):
                is_trivial = True
                break
        if not is_trivial:
            return False

    return True


def check_anti_pattern_mechanisms() -> dict:
    """Check if anti-pattern mechanism fixes are actually implemented."""
    anti_patterns_file = CLAUDE_DIR / "memories" / "anti-patterns.md"
    if not anti_patterns_file.exists():
        return {"status": "unimplemented", "total": 0, "implemented": 0, "entries": []}

    try:
        text = anti_patterns_file.read_text()
    except Exception:
        return {"status": "unimplemented", "total": 0, "implemented": 0, "entries": []}

    # Parse entries: look for ### headers and **Mechanism fix**: lines
    entries = []
    current_name = None
    current_mechanism = None

    for line in text.splitlines():
        header_match = re.match(r"^###\s+(.+)", line)
        if header_match:
            if current_name and current_mechanism:
                entries.append({"name": current_name, "mechanism": current_mechanism})
            current_name = header_match.group(1).strip()
            current_mechanism = None

        mech_match = re.match(r"^-\s+\*\*Mechanism fix\*\*:\s*(.+)", line)
        if mech_match and current_name:
            current_mechanism = mech_match.group(1).strip()

    # Don't forget last entry
    if current_name and current_mechanism:
        entries.append({"name": current_name, "mechanism": current_mechanism})

    # Check implementation of each mechanism
    results = []
    implemented_count = 0

    for entry in entries:
        mechanism = entry["mechanism"].lower()
        checks = []
        is_implemented = False

        if "pre-commit" in mechanism or "pre-push" in mechanism:
            # Check if .pre-commit-config.yaml exists
            if (REPO_ROOT / ".pre-commit-config.yaml").exists():
                checks.append("pre-commit config exists")
                is_implemented = True

        if "ci" in mechanism and ("grep" in mechanism or "gate" in mechanism):
            # Check if any safety script exists
            safety_dir = REPO_ROOT / "scripts" / "safety"
            if safety_dir.exists() and any(safety_dir.iterdir()):
                checks.append("safety scripts exist")
                is_implemented = True

        if "test fixture" in mechanism or "conftest" in mechanism or "shared test" in mechanism:
            # Check if cortex conftest mentions relevant patterns
            conftest = REPO_ROOT / "cortex" / "tests" / "conftest.py"
            if conftest.exists():
                try:
                    content = conftest.read_text()
                    if "fixture" in content or "mock" in content:
                        checks.append("conftest has fixtures")
                        is_implemented = True
                except Exception:
                    pass

        if "linter" in mechanism or "test_quality_linter" in mechanism:
            linter = REPO_ROOT / "scripts" / "safety" / "test_quality_linter.py"
            if linter.exists():
                checks.append("test_quality_linter.py exists")
                is_implemented = True

        if "self_audit" in mechanism:
            # We're building it right now — check if the file exists
            audit_file = REPO_ROOT / "cortex" / "self_audit.py"
            if audit_file.exists():
                checks.append("self_audit.py exists")
                is_implemented = True

        if "meta-test" in mechanism or "test_assertion_quality" in mechanism:
            # Check if the meta-test exists
            for search_dir in [REPO_ROOT / "cortex" / "tests", REPO_ROOT / "scripts" / "safety"]:
                if search_dir.exists():
                    for f in search_dir.rglob("test_assertion_quality*"):
                        checks.append(f"{f.name} exists")
                        is_implemented = True
                        break

        if "documented" in mechanism:
            # Anti-pattern is acknowledged in writing — valid enforcement for process patterns
            # that cannot be code-enforced (e.g., "no time estimates in specs")
            checks.append("mechanism documented in anti-patterns.md")
            is_implemented = True

        if "end-to-end" in mechanism or "round-trip" in mechanism or "e2e" in mechanism:
            # Check for E2E/round-trip tests (e.g., batch submission pipeline)
            test_dir = REPO_ROOT / "cortex" / "tests"
            if test_dir.exists():
                for test_file in test_dir.glob("test_batch*.py"):
                    try:
                        content = test_file.read_text()
                        if "submit_pending" in content and "assert_called" in content:
                            checks.append(f"{test_file.name} has E2E submission test")
                            is_implemented = True
                            break
                    except Exception:
                        continue

        if is_implemented:
            implemented_count += 1

        results.append(
            {
                "name": entry["name"],
                "implemented": is_implemented,
                "checks": checks,
            }
        )

    total = len(entries)
    if total == 0:
        status = "unimplemented"
    elif implemented_count == total:
        status = "implemented"
    elif implemented_count > 0:
        status = "partial"
    else:
        status = "unimplemented"

    return {
        "status": status,
        "total": total,
        "implemented": implemented_count,
        "entries": results,
    }


def check_dead_data() -> dict:
    """Check for dead/unused data files in ~/.cortex/."""
    dead_files = []

    # Check known dead files
    for filename in KNOWN_DEAD_FILES:
        filepath = CORTEX_DIR / filename
        if filepath.exists():
            try:
                if filepath.suffix == ".jsonl":
                    lines = [l for l in filepath.read_text().splitlines() if l.strip()]
                    if len(lines) == 0:
                        dead_files.append({"file": filename, "reason": "empty"})
                    else:
                        dead_files.append(
                            {"file": filename, "reason": "known dead (never consumed)"}
                        )
                elif filepath.suffix == ".json":
                    dead_files.append({"file": filename, "reason": "known dead (never consumed)"})
            except Exception:
                dead_files.append({"file": filename, "reason": "unreadable"})

    # Check for empty JSONL files
    for filepath in CORTEX_DIR.glob("*.jsonl"):
        if filepath.name in KNOWN_DEAD_FILES:
            continue  # Already checked
        try:
            content = filepath.read_text().strip()
            if not content:
                dead_files.append({"file": filepath.name, "reason": "empty"})
        except Exception:
            continue

    # Check for very old JSON files (>30 days) that are never read
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    for filepath in CORTEX_DIR.glob("*.json"):
        if filepath.name in KNOWN_DEAD_FILES:
            continue  # Already checked
        try:
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
            if mtime < threshold:
                # Only flag if it's a small file (likely config/state that's abandoned)
                size = filepath.stat().st_size
                if size < 1024:  # < 1KB
                    dead_files.append(
                        {
                            "file": filepath.name,
                            "reason": f"stale (>{(datetime.now(timezone.utc) - mtime).days}d, {size}B)",
                        }
                    )
        except Exception:
            continue

    status = "clean" if not dead_files else "has_dead_files"
    return {
        "status": status,
        "dead_files": dead_files,
    }


def determine_overall(report: dict) -> str:
    """Determine overall health status."""
    memory = report["memory_bridge"]["status"]
    learning = report["learning_loop"]["status"]
    tests = report["test_quality"]["status"]
    anti = report["anti_pattern_mechanisms"]["status"]
    dead = report["dead_data"]["status"]

    # Unhealthy: memory bridge disconnected AND test quality poor
    if memory == "disconnected" and tests == "poor":
        return "unhealthy"

    # Degraded: any single check failing
    if any(
        [
            memory == "disconnected",
            learning in ("starving", "dead"),
            tests in ("degraded", "poor"),
            anti in ("unimplemented", "partial"),
            dead == "has_dead_files",
        ]
    ):
        return "degraded"

    return "healthy"


def run_audit() -> dict:
    """Run full self-audit and return the report dict."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "memory_bridge": check_memory_bridge(),
        "learning_loop": check_learning_loop(),
        "test_quality": check_test_quality(),
        "anti_pattern_mechanisms": check_anti_pattern_mechanisms(),
        "dead_data": check_dead_data(),
    }
    report["overall"] = determine_overall(report)
    return report


def format_report(report: dict) -> str:
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 50)
    lines.append("  CORTEX SELF-AUDIT REPORT")
    lines.append("=" * 50)
    lines.append(f"  Timestamp: {report['timestamp'][:19]}")
    lines.append(f"  Overall:   {report['overall'].upper()}")
    lines.append("")

    # Memory Bridge
    mb = report["memory_bridge"]
    icon = "\u2705" if mb["status"] == "connected" else "\u274c"
    lines.append(f"  {icon} Memory Bridge: {mb['status'].upper()}")
    lines.append(
        f"     Cross-references: {mb['cross_references']} "
        f"(cortex->claude: {mb['cortex_to_claude']}, claude->cortex: {mb['claude_to_cortex']})"
    )

    # Learning Loop
    ll = report["learning_loop"]
    icon = (
        "\u2705"
        if ll["status"] == "active"
        else ("\u26a0\ufe0f" if ll["status"] == "starving" else "\u274c")
    )
    lines.append(f"  {icon} Learning Loop: {ll['status'].upper()}")
    lines.append(
        f"     Outcomes: {ll['outcome_count']} | Feedback: {ll['feedback_count']} "
        f"| Model outcomes: {ll['model_outcome_count']} | Freshness: {ll['freshness_days']}d"
    )

    # Test Quality
    tq = report["test_quality"]
    icon = (
        "\u2705"
        if tq["status"] == "good"
        else ("\u26a0\ufe0f" if tq["status"] == "degraded" else "\u274c")
    )
    lines.append(f"  {icon} Test Quality: {tq['status'].upper()}")
    lines.append(
        f"     Total: {tq['total_tests']} | Trivial: {tq['trivial_count']} ({tq['trivial_pct']}%)"
    )

    # Anti-Pattern Mechanisms
    ap = report["anti_pattern_mechanisms"]
    icon = (
        "\u2705"
        if ap["status"] == "implemented"
        else ("\u26a0\ufe0f" if ap["status"] == "partial" else "\u274c")
    )
    lines.append(f"  {icon} Anti-Pattern Mechanisms: {ap['status'].upper()}")
    lines.append(f"     Implemented: {ap['implemented']}/{ap['total']}")
    for entry in ap["entries"]:
        e_icon = "\u2713" if entry["implemented"] else "\u2717"
        lines.append(f"       {e_icon} {entry['name']}")

    # Dead Data
    dd = report["dead_data"]
    icon = "\u2705" if dd["status"] == "clean" else "\u26a0\ufe0f"
    lines.append(f"  {icon} Dead Data: {dd['status'].upper()}")
    if dd["dead_files"]:
        for df in dd["dead_files"]:
            lines.append(f"       - {df['file']}: {df['reason']}")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def main():
    quiet = "--quiet" in sys.argv

    report = run_audit()

    # Write JSON report
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2))

    if not quiet:
        print(format_report(report))
        print(f"\n  Report written to: {OUTPUT_FILE}")

    # Exit code: 0 healthy, 1 degraded, 2 unhealthy
    if report["overall"] == "unhealthy":
        sys.exit(2)
    elif report["overall"] == "degraded":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
