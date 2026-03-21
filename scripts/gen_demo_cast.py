#!/usr/bin/env python3
"""Generate asciinema v2 .cast file for Cortex CLI demo."""

import json
import random

random.seed(42)  # Reproducible "natural" typing

events: list[tuple[float, str, str]] = []
t = 0.0


def emit(text: str):
    """Add an output event at current time."""
    global t
    events.append((round(t, 4), "o", text))


def pause(secs: float):
    global t
    t += secs


def type_chars(text: str):
    """Simulate typing with variable delays."""
    for ch in text:
        delay = random.uniform(0.04, 0.09)
        pause(delay)
        emit(ch)


def enter():
    pause(0.06)
    emit("\r\n")


def output_lines(lines: list[str], delay: float = 0.10):
    """Emit lines with small inter-line delays to simulate terminal rendering."""
    for line in lines:
        emit(line + "\r\n")
        pause(delay)


# ANSI helpers
RST = "\x1b[0m"
BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
CYAN = "\x1b[36m"
YELLOW = "\x1b[33m"
RED = "\x1b[31m"
BWHITE = "\x1b[1;37m"
DIM = "\x1b[2m"

PROMPT = f"{GREEN}\u276f{RST} "


# ── Scene 1: Morning Briefing (~0s to ~12s) ──────────────────────

pause(1.0)
emit(f"{CYAN}# Morning context \u2014 Cortex remembers what happened across sessions{RST}\r\n")
pause(1.2)
emit(PROMPT)
pause(0.4)
type_chars("cortex briefing")
enter()
pause(0.6)

briefing = [
    f"{BOLD}+--------------------------------------------------------------+{RST}",
    f"{BOLD}|            CORTEX DAILY BRIEFING - March 09, 2026            |{RST}",
    f"{BOLD}+--------------------------------------------------------------+{RST}",
    "",
    f"{BWHITE}TL;DR{RST}",
    "  --------",
    "",
    "  \u2022 Portfolio: 6 active projects, 47 commits this week, no blockers",
    f"    Health ratio: {GREEN}[##########]{RST} 100% clear",
    f"  \u2022 Top Priority: {RED}[HIGH]{RST} Cortex OSS public launch (Mar 12)",
    "  \u2022 Git: on `main`, clean working tree",
    "  \u2022 Batch: 3 running, 2 queued (50% cost savings via Batch API)",
    "  \u2022 Today: Monday - Good day for planning and high-priority tasks",
    "",
    "----------------------------------------------------------------",
    "",
    f"{BWHITE}/== RESOURCE INTELLIGENCE ==/{RST}",
    "",
    "  \U0001f7e2 Pacing: Under Budget (2.1h/day vs 8.6h target)",
    "     \u2192 Room to push harder on complex tasks",
    "  \U0001f4ca Weekly: 14.7h/60.0h used (25%), 5 days left",
    "  \U0001f504 Batch API: 38% of work (target: 40.0%)",
    "",
    f"{BWHITE}/== ORCHESTRATION ADVISORY ==/{RST}",
    "",
    "  \U0001f7e2 Recommended Mode: Interactive Ok",
    "     Under budget - can use interactive sessions freely",
    "",
    "----------------------------------------------------------------",
    "",
    f"{BWHITE}PROJECT SNAPSHOT{RST}",
    f"  {DIM}Project                     C7d  WIP  Trend{RST}",
    f"  {DIM}-------------------------  ---  ---  ------{RST}",
    f"  vortex                      18    2  {RED}hot{RST}",
    f"  cortex                      14    0  {RED}hot{RST}",
    f"  alpha-arena                  8    1  {GREEN}active{RST}",
    f"  pupil                        4    0  {GREEN}active{RST}",
    f"  dj-copilot                   2    0  {DIM}idle{RST}",
    f"  kempion-site                 1    0  {DIM}idle{RST}",
    "",
    f"{BWHITE}PORTFOLIO PULSE{RST}",
    "  Active projects: 6",
    "  Recent commits: 8 in last 24h, 47 in last 7d",
    "  Commit trend (24h\u21927d): \u2588\u2588\u2588\u2581",
    f"  Blockers: {GREEN}None{RST}",
]
output_lines(briefing)

# User reads the briefing
pause(2.0)
emit(PROMPT)

# ── Scene 2: Deep Project Intelligence (~14s to ~24s) ────────────

pause(3.5)
emit("\r\n")
emit(f"{CYAN}# Deep analysis on any project \u2014 health, debt, recommendations{RST}\r\n")
pause(1.2)
emit(PROMPT)
pause(0.4)
type_chars("cortex deep cortex")
enter()
pause(0.6)

deep = [
    f"{BWHITE}============================================================{RST}",
    f"{BWHITE}Cortex Deep Intelligence: cortex{RST}",
    f"{DIM}Mode: deep | Analysis time: 842ms{RST}",
    f"{BWHITE}============================================================{RST}",
    "",
    f"  {GREEN}\u2705 90/100 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2591\u2591{RST} ({GREEN}excellent{RST})",
    "",
    f"{BWHITE}Git Analysis:{RST}",
    "  Branch: main",
    "  Commits analyzed: 1204 (90 days)",
    "  Uncommitted files: 0 (clean)",
    "",
    f"{BWHITE}Code Quality:{RST}",
    "  Tech debt markers: 0",
    "",
    f"{YELLOW}\u26a0\ufe0f  Warnings (1):{RST}",
    f"  {YELLOW}\U0001f7e1 [WARNING] High code churn detected in orchestration/{RST}",
    "",
    f"{BWHITE}\U0001f4a1 Recommendations (2):{RST}",
    f"  {RED}\U0001f525 [HIGH]{RST} Ship OSS release before Mar 12 deadline",
    "     5 items remain on launch checklist",
    f"  {GREEN}\U0001f7e2 [LOW]{RST} Consider splitting cli.py (4,400+ lines)",
    "     Modular CLI improves contributor onboarding",
    "",
    f"{DIM}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{RST}",
    f"{DIM}Tip: Use 'cortex deep --verbose' for full details{RST}",
]
output_lines(deep)

# User reads the deep analysis
pause(2.5)
emit(PROMPT)

# ── Scene 3: Learning Metrics (~26s to ~36s) ─────────────────────

pause(3.0)
emit("\r\n")
emit(f"{CYAN}# Cortex learns from outcomes \u2014 patterns compound over time{RST}\r\n")
pause(1.2)
emit(PROMPT)
pause(0.4)
type_chars("cortex learn")
enter()
pause(0.4)

learn = [
    f"{BWHITE}\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557{RST}",
    f"{BWHITE}\u2551              CORTEX - LEARNING METRICS               \u2551{RST}",
    f"{BWHITE}\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d{RST}",
    "",
    f"\U0001f4ca {BWHITE}OVERALL METRICS{RST}",
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    "Total Outcomes: 511",
    "Followed Recommendations: 502",
    f"Success Rate: {GREEN}51.2%{RST}",
    f"Partial Success: {YELLOW}34.3%{RST}",
    f"Failed: {RED}14.5%{RST}",
    f"Recommendation Accuracy: {GREEN}68.2%{RST}",
    "",
    f"\U0001f3af {BWHITE}CONFIDENCE CALIBRATION{RST}",
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    "How well do confidence scores predict success?",
    "",
    f"  medium (0.5-0.8): {YELLOW}\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588{DIM}\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591{RST} {YELLOW}54.5%{RST}",
    f"  high (0.8-1.0):   {GREEN}\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588{DIM}\u2591\u2591\u2591{RST} {GREEN}87.7%{RST}",
    "",
    f"\U0001f4c8 {BWHITE}LEARNING VELOCITY{RST}",
    "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    f"Patterns learned: 134 ({GREEN}+12 this week{RST})",
    "Anti-patterns stored: 28",
    "Cross-project insights: 47",
]
output_lines(learn)

# User reads learning metrics
pause(2.5)
emit(PROMPT)

# ── Outro (~38s to ~41s) ─────────────────────────────────────────

pause(3.0)
emit("\r\n")

outro = [
    f"{YELLOW}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{RST}",
    f"  {BWHITE}Cortex{RST} \u2014 Persistent Intelligence for LLM Agents",
    f"  Every session builds on the last.  {CYAN}pip install cortex-intelligence{RST}",
    f"{YELLOW}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{RST}",
]
output_lines(outro, delay=0.10)

pause(4.0)

# ── Write .cast file ─────────────────────────────────────────────

header = {
    "version": 2,
    "width": 80,
    "height": 40,
    "timestamp": 1741478400,
    "env": {"SHELL": "/bin/zsh", "TERM": "xterm-256color"},
}

out_path = "/Users/jesse/dev/cortex/docs/assets/demo.cast"
with open(out_path, "w") as f:
    f.write(json.dumps(header) + "\n")
    for ts, etype, text in events:
        f.write(json.dumps([round(ts, 4), etype, text]) + "\n")

print(f"Wrote {len(events)} events, duration {round(t, 1)}s -> {out_path}")
