#!/usr/bin/env python3
"""Generate Cortex Demo Scripts PDF — professional product brief."""

import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    Flowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Courier New (has box-drawing glyphs, unlike built-in Courier)
_CN_PATH = "/System/Library/Fonts/Supplemental/Courier New.ttf"
_CN_BOLD_PATH = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
pdfmetrics.registerFont(TTFont("CourierNew", _CN_PATH))
pdfmetrics.registerFont(TTFont("CourierNew-Bold", _CN_BOLD_PATH))

# Emoji → ASCII fallback map (Courier New lacks emoji glyphs)
_EMOJI_MAP = {
    "\u2705": "[OK]",  # ✅
    "\u274c": "[X]",  # ❌
    "\u26a0\ufe0f": "[!]",  # ⚠️  (2-char sequence)
    "\u26a0": "[!]",  # ⚠  (bare)
    "\U0001f534": "(R)",  # 🔴
    "\U0001f7e2": "(G)",  # 🟢
    "\U0001f7e1": "(Y)",  # 🟡
    "\u26aa": "(W)",  # ⚪
    "\U0001f50d": "[?]",  # 🔍
    "\U0001f4cb": "[=]",  # 📋
    "\U0001f4ca": "[#]",  # 📊
    "\U0001f3af": "[*]",  # 🎯
    "\U0001f4c8": "[^]",  # 📈
    "\u2328": "[K]",  # ⌨️  (unused but safe)
    "\U0001f4a1": "[i]",  # 💡
    "\u2717": "x",  # ✗
    "\u23f0": "[T]",  # ⏰
    "\u2718": "x",  # ✘
    "❯": ">",  # prompt char
}


def _sanitize_for_courier_new(text: str) -> str:
    """Replace emoji/symbols that Courier New cannot render."""
    for emoji, replacement in _EMOJI_MAP.items():
        text = text.replace(emoji, replacement)
    # Strip any remaining variation selectors
    text = text.replace("\ufe0f", "")
    return text


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BLUE = HexColor("#1a73e8")
DARK_BLUE = HexColor("#0d47a1")
GREEN = HexColor("#2e7d32")
RED = HexColor("#c62828")
ORANGE = HexColor("#e65100")
GRAY = HexColor("#424242")
LIGHT_GRAY = HexColor("#f5f5f5")
MED_GRAY = HexColor("#9e9e9e")
DARK_BG = HexColor("#1e1e2e")
TERM_GREEN = HexColor("#a6e3a1")
TERM_RED = HexColor("#f38ba8")
TERM_BLUE = HexColor("#89b4fa")
TERM_YELLOW = HexColor("#f9e2af")
TERM_WHITE = HexColor("#cdd6f4")
TERM_GRAY = HexColor("#6c7086")
WHITE = white


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def make_styles():
    s = {}
    s["title"] = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=DARK_BLUE,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="Helvetica",
        fontSize=16,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    s["date"] = ParagraphStyle(
        "date",
        fontName="Helvetica",
        fontSize=13,
        textColor=MED_GRAY,
        alignment=TA_CENTER,
        spaceAfter=40,
    )
    s["toc_title"] = ParagraphStyle(
        "toc_title",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=DARK_BLUE,
        spaceAfter=18,
    )
    s["toc_cat"] = ParagraphStyle(
        "toc_cat",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=BLUE,
        spaceBefore=10,
        spaceAfter=4,
        leftIndent=10,
    )
    s["toc_item"] = ParagraphStyle(
        "toc_item",
        fontName="Helvetica",
        fontSize=11,
        textColor=GRAY,
        leftIndent=30,
        spaceAfter=2,
    )
    s["cat_heading"] = ParagraphStyle(
        "cat_heading",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=DARK_BLUE,
        spaceBefore=0,
        spaceAfter=6,
    )
    s["cat_thesis"] = ParagraphStyle(
        "cat_thesis",
        fontName="Helvetica-Oblique",
        fontSize=12,
        textColor=GRAY,
        spaceAfter=18,
        leftIndent=10,
    )
    s["script_title"] = ParagraphStyle(
        "script_title",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=BLUE,
        spaceBefore=6,
        spaceAfter=4,
    )
    s["target"] = ParagraphStyle(
        "target",
        fontName="Helvetica-BoldOblique",
        fontSize=12,
        textColor=GREEN,
        spaceAfter=8,
        leftIndent=10,
    )
    s["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=11,
        textColor=GRAY,
        spaceAfter=6,
        leading=14,
    )
    s["summary_head"] = ParagraphStyle(
        "summary_head",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=DARK_BLUE,
        spaceBefore=12,
        spaceAfter=12,
    )
    return s


# ---------------------------------------------------------------------------
# Terminal block — dark background with pre-formatted text
# ---------------------------------------------------------------------------
class TerminalBlock(Flowable):
    """Renders a dark-background terminal block with syntax-highlighted text."""

    PADDING = 10
    FONT = "CourierNew"
    FONT_SIZE = 7.2
    LINE_HEIGHT = 9.6

    def __init__(self, raw_text: str, width: float = 6.5 * inch):
        super().__init__()
        sanitized = _sanitize_for_courier_new(raw_text)
        self.lines = sanitized.rstrip("\n").split("\n")
        self.block_width = width
        self.block_height = self.PADDING * 2 + len(self.lines) * self.LINE_HEIGHT + 4

    # reportlab api
    def wrap(self, availWidth, availHeight):
        return self.block_width, self.block_height

    def draw(self):
        c = self.canv
        # background
        c.setFillColor(DARK_BG)
        c.roundRect(0, 0, self.block_width, self.block_height, 6, fill=1, stroke=0)
        # text
        y = self.block_height - self.PADDING - self.FONT_SIZE
        for line in self.lines:
            color, text = self._colorize(line)
            c.setFont(self.FONT, self.FONT_SIZE)
            c.setFillColor(color)
            c.drawString(self.PADDING, y, text)
            y -= self.LINE_HEIGHT

    @staticmethod
    def _colorize(line: str):
        stripped = line.strip()
        if stripped.startswith("#"):
            return TERM_GRAY, line
        if stripped.startswith(">") and ("cortex" in line or ">" == stripped[0:1]):
            return TERM_GREEN, line
        if "[!]" in line or "WARNING" in line.upper() or "(Y)" in line or "SLOW" in line:
            return TERM_YELLOW, line
        if (
            "(R)" in line
            or " x " in line
            or "[X]" in line
            or "RISK" in line.upper()
            or "DRIFT" in line.upper()
        ):
            return TERM_RED, line
        if "[OK]" in line or "(G)" in line or "Success" in line:
            return TERM_GREEN, line
        if "╔" in line or "╚" in line or "║" in line or "┌" in line or "└" in line or "│" in line:
            return TERM_BLUE, line
        if stripped.startswith("→") or stripped.startswith("Δ"):
            return TERM_YELLOW, line
        return TERM_WHITE, line


# ---------------------------------------------------------------------------
# Horizontal rule
# ---------------------------------------------------------------------------
class HRule(Flowable):
    def __init__(self, width=6.5 * inch, color=MED_GRAY, thickness=0.5):
        super().__init__()
        self.rule_width = width
        self.color = color
        self.thickness = thickness

    def wrap(self, aw, ah):
        return self.rule_width, 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.rule_width, 2)


# ---------------------------------------------------------------------------
# Data — all 16 demo scripts
# ---------------------------------------------------------------------------

CATEGORIES = [
    {
        "num": 1,
        "title": '"The Memory Layer" \u2014 Developer Productivity',
        "thesis": "Core thesis: Your AI assistant forgets everything between sessions. Cortex fixes that.",
        "scripts": [
            {
                "id": "1A",
                "name": '"Monday Morning" (The Opener)',
                "feeling": 'Target feeling: "I need this."',
                "terminal": r"""# It's Monday. You open Claude. It has no idea what you did last week.
❯ cortex briefing

┌──────────────────────────────────────────────────────────┐
│          CORTEX DAILY BRIEFING — March 10, 2026          │
└──────────────────────────────────────────────────────────┘

TL;DR
  • Portfolio: 6 active projects, 47 commits last week
  • You left off: refactoring auth middleware in api-gateway
  • Unfinished: 2 TODOs from Friday's session
  • Warning: CI failed on data-pipeline at 2am (memory spike)
  • Today: Monday — Good day for planning and deep work

PROJECT SNAPSHOT
  Project              C7d  WIP  Trend
  ──────────────────  ───  ───  ──────
  api-gateway           18    2  hot
  data-pipeline         12    1  active
  ml-serving             8    0  active
  dashboard-ui           5    0  idle

# Your AI assistant now knows exactly where you left off.
# No "remember, we use ruff..." No re-explaining architecture.
# 23% fewer preamble tokens. Zero re-discovered bugs.""",
            },
            {
                "id": "1B",
                "name": '"The Anti-Pattern Save" (The Hero Moment)',
                "feeling": 'Target feeling: "This would have saved me a week."',
                "terminal": r"""# You're about to make a mistake. Cortex has seen this before.
❯ cortex intelligence "add Redis caching for user sessions"

🔍 INTELLIGENCE RESULTS (42ms)

📋 SIMILAR WORK
  • 2025-12-15: Redis caching for API rate limiting (api-gateway)
  • 2025-11-28: Session storage comparison: Redis vs PostgreSQL

⚠️  ANTI-PATTERNS (2 matches)
  ✗ "Never use default Redis timeout under load"
    Last seen: 2025-12-15 | Caused: 502 errors in production
    Prevention: Set timeout=30s, max_connections=20

  ✗ "Don't store objects >1MB in Redis"
    Last seen: 2025-11-02 | Caused: 3x latency spike
    Prevention: Use PostgreSQL for user profiles, Redis for tokens only

✅ RECOMMENDATIONS
  • Start with TTL=3600 for session tokens
  • Use separate Redis DB indices (0=cache, 1=sessions)
  • Monitor connection pool exhaustion

# Two production bugs prevented. Zero recurrences in 6 months.
# Not because you remembered. Because Cortex remembered for you.""",
            },
            {
                "id": "1C",
                "name": '"Cross-Project Transfer" (The Multiplier)',
                "feeling": 'Target feeling: "My experience compounds."',
                "terminal": r"""# You solved rate limiting in Project A. Now Project B needs it.
❯ cortex intelligence "implement API rate limiting" --project ml-serving

🔍 INTELLIGENCE RESULTS

📋 CROSS-PROJECT PATTERNS
  • api-gateway (2025-12-15): Token bucket with Redis backend
    Files: middleware/rate_limiter.py, tests/test_rate_limit.py
    Outcome: ✅ Success (production 4 months, 0 incidents)

  • data-pipeline (2025-10-22): Sliding window for batch endpoints
    Files: api/throttle.py
    Outcome: ✅ Success (handles 10K req/s)

💡 APPLICABLE TO ml-serving:
  • Use token bucket (proven in api-gateway)
  • ML inference endpoints need longer windows (60s vs 1s)
  • Pre-warm rate limit counters on cold start

# Knowledge earned once, applied everywhere.
# 6 projects. 134 patterns. Automatic transfer.""",
            },
            {
                "id": "1D",
                "name": '"The Learning Proof" (The Science)',
                "feeling": 'Target feeling: "This is real ML, not a gimmick."',
                "terminal": r"""# Cortex doesn't just store — it learns what works.
❯ cortex learn

╔══════════════════════════════════════════════════════╗
║              CORTEX — LEARNING METRICS               ║
╚══════════════════════════════════════════════════════╝

📊 RECOMMENDATION ACCURACY
────────────────
Total outcomes tracked:         511
Recommendations followed:       502
Success rate:                  51.2%
Partial success:               34.3%
Recommendation accuracy:       68.2%

🎯 CONFIDENCE CALIBRATION
────────────────
  low  (0.0-0.5): ████░░░░░░░░░░░░░░░░ 22.1%
  med  (0.5-0.8): ██████████░░░░░░░░░░ 54.5%
  high (0.8-1.0): █████████████████░░░ 87.7%

  → High-confidence recommendations land 88% of the time.
  → No annotation required. Learned from your behavior.

📈 TREND (6 months)
────────────────
  Month 1:  52% relevance in top-3 results
  Month 6:  71% relevance in top-3 results
  Δ:       +37% improvement, zero manual labeling

# This is an ML system running on your workflow.
# Implicit feedback. Quality-weighted outcomes.
# The more you use it, the better it gets.""",
            },
        ],
    },
    {
        "num": 2,
        "title": '"The Cost Engine" \u2014 AI Infrastructure Economics',
        "thesis": "Core thesis: You're burning money sending every task to GPT-5/Opus. Cortex routes intelligently.",
        "scripts": [
            {
                "id": "2A",
                "name": '"The Router" (Cost Optimization)',
                "feeling": 'Target feeling: "I\'m wasting money right now."',
                "terminal": r"""# You have 12 tasks queued. Cortex routes each to the right model.
❯ cortex orchestrate --dry-run

╔══════════════════════════════════════════════════════╗
║           CORTEX — ORCHESTRATION DRY RUN             ║
╚══════════════════════════════════════════════════════╝

TASK ROUTING (12 items)
────────────────
  Task                        Complexity   Model              Cost
  ─────────────────────────  ──────────  ─────────────────  ──────
  Classify PR type            simple      Groq Llama 8B      $0.001
  Generate test stubs         simple      Groq Llama 8B      $0.002
  Review auth middleware      moderate    Claude Sonnet       $0.08
  Analyze memory leak         moderate    DeepSeek Chat       $0.04
  Design caching layer        complex     Claude Opus         $0.42
  Security audit              complex     Claude Opus         $0.38
  Lint 6 config files         simple      Groq Llama 8B      $0.003
  Draft API docs              moderate    xAI Grok Fast       $0.05
  Refactor DB migrations      moderate    Claude Sonnet       $0.07
  Prototype WebSocket layer   complex     Claude Opus         $0.51
  Update README               simple      Groq Llama 8B      $0.001
  Check dependency CVEs       moderate    MiniMax M1          $0.03
  ─────────────────────────  ──────────  ─────────────────  ──────
  TOTAL                                                       $1.61
  If all sent to Opus:                                        $4.20
  SAVINGS:                                          61% ($2.59)

  Providers: 6 | Models: 8 | Avg latency: 1.2s

# 11 models. 6 providers. Route by complexity, not habit.
# Same quality. 61% less cost. Automatic fallback chains.""",
            },
            {
                "id": "2B",
                "name": '"Batch Intelligence" (Overnight Economics)',
                "feeling": 'Target feeling: "Free money on the table."',
                "terminal": r"""# End of day. Queue deep work for overnight batch processing.
❯ cortex batch --fill

╔══════════════════════════════════════════════════════╗
║          CORTEX — OVERNIGHT BATCH QUEUE              ║
╚══════════════════════════════════════════════════════╝

QUEUED (40 items, 2-6 AM UTC window)
────────────────
  Type                Count   Model        Batch Savings
  ─────────────────  ─────  ───────────  ─────────────
  Security audits        6   Opus          50% ($1.14→$0.57)
  Code quality scans    12   Sonnet        50% ($2.88→$1.44)
  Test coverage gaps     8   Sonnet        50% ($1.92→$0.96)
  TODO triage           14   Haiku         50% ($0.28→$0.14)
  ─────────────────  ─────  ───────────  ─────────────
  TOTAL                 40                 $6.22 → $3.11

  Strategy: Use best models (Opus/Sonnet) at batch pricing
  Tradeoff: Accept 2-5s latency → 50% cost + higher quality

  ⏰ Results ready by 7 AM. cortex batch-results to review.

# Batch API: half the cost, better models, overnight.
# Your AI works while you sleep.""",
            },
            {
                "id": "2C",
                "name": '"The Feedback ROI" (Learning Pays Back)',
                "feeling": 'Target feeling: "I can justify this to my manager."',
                "terminal": r"""# How much has Cortex's learning loop saved?
❯ cortex learn --roi

╔══════════════════════════════════════════════════════╗
║           CORTEX — LEARNING ROI (6 months)           ║
╚══════════════════════════════════════════════════════╝

BUG PREVENTION
────────────────
  Anti-patterns stored:          28
  Times surfaced before repeat:  47
  Estimated debug hours saved:   ~23h (28 bugs × 0.8h avg)

CONTEXT EFFICIENCY
────────────────
  Preamble tokens (month 1):    2,847 avg
  Preamble tokens (month 6):    2,198 avg  (−23%)
  Re-explanation sessions:       Weekly → 0
  Estimated token savings:       ~340K tokens/month

MODEL ROUTING
────────────────
  If all Opus:                   $126.40/month
  With intelligent routing:       $48.80/month
  Monthly savings:                $77.60 (61%)

TOTAL 6-MONTH VALUE
────────────────
  Debug time saved:              ~23 hours
  Token cost avoided:            ~$194
  Model routing savings:         ~$466
  ─────────────────────────────────────
  Combined:  ~$660 saved + 23 hours recovered

# ROI isn't theoretical. It's measured.
# Every outcome tracked. Every pattern costed.""",
            },
            {
                "id": "2D",
                "name": '"Provider Resilience" (Production Operations)',
                "feeling": 'Target feeling: "Single-provider is a risk I didn\'t realize I had."',
                "terminal": r"""# 3:47 AM. Anthropic API has elevated latency. Cortex auto-routes.
❯ cortex health --providers

╔══════════════════════════════════════════════════════╗
║          CORTEX — PROVIDER HEALTH MONITOR            ║
╚══════════════════════════════════════════════════════╝

PROVIDER STATUS
────────────────
  Provider       Status    P95 Latency   Fallback Active
  ───────────   ────────  ───────────   ──────────────
  Anthropic      ⚠️ SLOW    4,200ms      → OpenAI GPT-5
  OpenAI         🟢 OK        890ms      —
  Groq           🟢 OK        120ms      —
  xAI            🟢 OK        340ms      —
  DeepSeek       🟢 OK        780ms      —
  MiniMax        🟢 OK        450ms      —

AUTO-REROUTED (last 2h)
────────────────
  8 tasks rerouted Anthropic → OpenAI (4.2s → 0.9s)
  0 failures. All tasks completed successfully.

  Cost impact: +$0.12 (OpenAI slightly more expensive)
  Latency impact: −78% (4.2s → 0.9s avg)

# Multi-provider isn't just about cost.
# It's about never being down because one API is slow.""",
            },
        ],
    },
    {
        "num": 3,
        "title": '"The Portfolio Brain" \u2014 Multi-Project Intelligence',
        "thesis": "Core thesis: You don't work on one project. You work on six. Cortex sees across all of them.",
        "scripts": [
            {
                "id": "3A",
                "name": '"Portfolio Pulse" (Operational Dashboard)',
                "feeling": 'Target feeling: "I\'ve never had this view before."',
                "terminal": r"""# One command. Full portfolio health.
❯ cortex briefing --portfolio

╔══════════════════════════════════════════════════════╗
║        CORTEX — PORTFOLIO INTELLIGENCE               ║
╚══════════════════════════════════════════════════════╝

HEALTH MATRIX (6 projects)
────────────────
  Project          Health  Tests    Commits  Status
  ──────────────  ──────  ───────  ───────  ─────────
  vortex-backend   92/100  2,835    18/wk    🟢 shipping
  cortex           90/100    600    14/wk    🟢 shipping
  alpha-arena      85/100    603     8/wk    🟡 collecting
  pupil            88/100  1,255     4/wk    🟡 blocked
  data-pipeline    76/100    342     2/wk    🔴 stale CI
  ml-serving       81/100    189     1/wk    ⚪ idle

CROSS-PROJECT SIGNALS
────────────────
  ⚠️  data-pipeline shares FastAPI patterns with vortex-backend
     but hasn't adopted rate limiting (added to vortex 3 weeks ago)
  ⚠️  ml-serving and alpha-arena both use Redis
     but different timeout configs (30s vs default)
  ✅ All 6 projects use ruff — consistent tooling

FOCUS RECOMMENDATION
────────────────
  1. [HIGH] Fix data-pipeline CI (stale 3 days)
  2. [MED]  Propagate rate limiting to data-pipeline
  3. [MED]  Standardize Redis config across projects
  4. [LOW]  ml-serving idle 2 weeks — archive or revive?

# 6 projects. One command. Cross-project drift detected.
# Not just monitoring — actionable intelligence.""",
            },
            {
                "id": "3B",
                "name": '"Pattern Propagation" (Knowledge Transfer)',
                "feeling": 'Target feeling: "My projects should be learning from each other."',
                "terminal": r"""# Cortex detected a pattern that should propagate.
❯ cortex portfolio patterns --propagate

╔══════════════════════════════════════════════════════╗
║       CORTEX — PATTERN PROPAGATION ANALYSIS          ║
╚══════════════════════════════════════════════════════╝

PATTERNS WITH HIGH TRANSFER POTENTIAL
────────────────

1. "Token bucket rate limiting" (confidence: 92%)
   ✅ api-gateway:  Deployed 4 months, 0 incidents
   ✅ vortex:       Deployed 3 weeks, 0 incidents
   ❌ data-pipeline: NOT APPLIED (12K req/s endpoint exposed)
   ❌ ml-serving:    NOT APPLIED (inference endpoint unprotected)
   → Recommendation: Apply to both. Template available.

2. "SQLite WAL mode for local caches" (confidence: 88%)
   ✅ vortex:       Deployed, eliminated read/write contention
   ❌ cortex:       Still using default journal mode
   ❌ alpha-arena:  Using file-based JSON (no DB)
   → Recommendation: Apply to cortex. Skip alpha-arena.

3. "Structured error responses" (confidence: 79%)
   ✅ api-gateway:  RFC 7807 format, consistent across 42 endpoints
   ⚠️  vortex:      Partial (28 of 35 endpoints)
   ❌ ml-serving:   Raw exceptions in 3 endpoints
   → Recommendation: Complete vortex, apply to ml-serving.

# Patterns aren't just remembered. They're propagated.
# What works in one project becomes a template for others.""",
            },
            {
                "id": "3C",
                "name": '"Dependency Intelligence" (Architecture Awareness)',
                "feeling": 'Target feeling: "I\'ve been flying blind on cross-project deps."',
                "terminal": r"""# How do your projects relate? What breaks if something changes?
❯ cortex deps --cross-project

╔══════════════════════════════════════════════════════╗
║       CORTEX — CROSS-PROJECT DEPENDENCY MAP          ║
╚══════════════════════════════════════════════════════╝

SHARED DEPENDENCIES
────────────────
  Package        Version(s)         Projects          Risk
  ───────────   ────────────────   ──────────────   ──────
  fastapi        0.109.0            4/6 projects     🟢 aligned
  redis          5.0.1 / 4.6.0     3/6 projects     🟡 drift
  pydantic       2.6.0 / 1.10.4    4/6 projects     🔴 major split
  sqlalchemy     2.0.25             3/6 projects     🟢 aligned
  pytest         8.0.0              6/6 projects     🟢 aligned

RISK ALERTS
────────────────
  🔴 pydantic v1 → v2 migration incomplete
     ml-serving and data-pipeline still on v1.10.4
     Impact: Shared models break if imported cross-project
     → 14 shared Pydantic models affected

  🟡 redis version drift
     alpha-arena on 4.6.0 (6 months old)
     CVE-2024-31228: DoS via unbounded RESP3 response
     → Upgrade recommended

# Not just "what versions do I have" — "what breaks if I upgrade" """,
            },
            {
                "id": "3D",
                "name": '"Context Switching Cost" (The Hidden Tax)',
                "feeling": 'Target feeling: "I knew switching was expensive but never measured it."',
                "terminal": r"""# You context-switch between projects constantly. What does it cost?
❯ cortex portfolio --switching-cost

╔══════════════════════════════════════════════════════╗
║       CORTEX — CONTEXT SWITCHING ANALYSIS            ║
╚══════════════════════════════════════════════════════╝

LAST 30 DAYS
────────────────
  Avg project switches/day:      3.4
  Avg preamble tokens/switch:    2,198 (with Cortex)
  Estimated without Cortex:      2,847 tokens
  Token savings from memory:     649 tokens/switch

  Monthly switching overhead:
    Without Cortex:  102 switches × 2,847 = 290K tokens (~$4.35)
    With Cortex:     102 switches × 2,198 = 224K tokens (~$3.36)
    Saved:           66K tokens/month (~$1.00)

DEEPER COST: RE-DISCOVERY
────────────────
  Bugs re-discovered (before Cortex):    3.2/month
  Bugs re-discovered (with Cortex):      0/month
  Avg debug time per re-discovery:       47 minutes
  Time saved:                            ~2.5 hours/month

CONTEXT QUALITY BY PROJECT
────────────────
  Project          Patterns  Anti-Patterns  Context Score
  ──────────────  ────────  ─────────────  ─────────────
  vortex-backend       47           8         94%
  cortex               38           6         91%
  alpha-arena          22           4         82%
  pupil                18           3         78%
  data-pipeline         6           2         61%
  ml-serving            3           1         44%

  → ml-serving needs more sessions to build context depth
  → data-pipeline context degrading (2 weeks idle)

# Context switching isn't just annoying. It's measurable.
# Cortex reduces the tax from ~$4.35 to ~$3.36 per month
# and eliminates 2.5 hours of re-debugging.""",
            },
        ],
    },
    {
        "num": 4,
        "title": '"The Future" \u2014 Where Cortex Shines Next',
        "thesis": "Core thesis: As AI agents become more autonomous, persistent memory isn't nice-to-have \u2014 it's the difference between a tool and a teammate.",
        "scripts": [
            {
                "id": "4A",
                "name": '"Autonomous Agent Memory" (2026 \u2014 Agent Teams)',
                "feeling": 'Target feeling: "This is what agent infrastructure looks like."',
                "terminal": r"""# 2026: Your CI pipeline runs 4 AI agents in parallel.
# Each agent inherits institutional memory from Cortex.
❯ cortex sessions --active

╔══════════════════════════════════════════════════════╗
║       CORTEX — ACTIVE AGENT SESSIONS                 ║
╚══════════════════════════════════════════════════════╝

LIVE AGENTS (4 active)
────────────────
  Agent             Project         Task                  Memory
  ───────────────  ──────────────  ────────────────────  ────────
  code-reviewer     api-gateway     PR #247 review        134 patterns
  security-scanner  ml-serving      CVE triage            28 anti-patterns
  test-generator    data-pipeline   Gap coverage          89 patterns
  doc-writer        cortex          API reference         47 patterns

MEMORY SHARING
────────────────
  code-reviewer surfaced anti-pattern from security-scanner:
    "SQL injection via f-string in query builder"
    Originally found: ml-serving, 2025-11-14
    Now preventing in: api-gateway PR #247 ✅

  test-generator using pattern from code-reviewer:
    "Edge case: empty list input on batch endpoints"
    Originally found: api-gateway, 2026-01-08
    Applying to: data-pipeline test suite ✅

# 4 agents. Shared memory. Cross-agent learning.
# The security scanner's finding saves the code reviewer.
# That's not coordination — it's institutional knowledge.""",
            },
            {
                "id": "4B",
                "name": '"Continuous Learning Pipeline" (2026 \u2014 ML Ops for AI Agents)',
                "feeling": 'Target feeling: "They\'ve built MLOps for agent memory."',
                "terminal": r"""# Cortex as MLOps for your AI agent's intelligence.
❯ cortex learn --pipeline

╔══════════════════════════════════════════════════════╗
║       CORTEX — LEARNING PIPELINE STATUS              ║
╚══════════════════════════════════════════════════════╝

FEEDBACK LOOP
────────────────
  ┌─────────┐     ┌──────────┐     ┌──────────┐
  │ Session  │────→│ Implicit │────→│ Pattern  │
  │ Actions  │     │ Feedback │     │ Weights  │
  └─────────┘     └──────────┘     └──────────┘
       │                                 │
       │          ┌──────────┐           │
       └─────────→│ Outcome  │←──────────┘
                  │ Tracking │
                  └──────────┘

PIPELINE METRICS (last 30 days)
────────────────
  Sessions processed:           42
  Implicit signals captured:    1,847
  Patterns weight-adjusted:     23
  New patterns crystallized:     8
  Anti-patterns validated:       3

QUALITY GATES
────────────────
  ✅ Confidence calibration: r² = 0.84 (well-calibrated)
  ✅ Pattern decay: 12 patterns deprecated (stale >90 days)
  ✅ Feedback loop latency: <100ms (real-time)
  ⚠️  Cold-start projects: 2 (ml-serving, dashboard-ui)
     Need 10+ sessions for reliable recommendations

MODEL DRIFT DETECTION
────────────────
  api-gateway: Recommendations shifting toward security patterns
    (+34% security, −18% performance in last 30 days)
    Likely cause: Recent CVE triage sessions
    Action: Rebalance if unintentional, accept if strategic

# This isn't a database. It's an ML pipeline.
# Feature extraction → training → inference → monitoring.
# Running on your workflow data. Improving every day.""",
            },
            {
                "id": "4C",
                "name": '"Team Memory" (2027 \u2014 Shared Institutional Knowledge)',
                "feeling": 'Target feeling: "Every team should have this."',
                "terminal": r"""# VISION: What team-scale Cortex could look like.
# Today: single-user. Tomorrow: shared institutional memory.
❯ cortex vision --team-memory

╔══════════════════════════════════════════════════════╗
║   CORTEX — TEAM INTELLIGENCE (Vision / Not Yet Built) ║
╚══════════════════════════════════════════════════════╝

COLLECTIVE KNOWLEDGE
────────────────
  Total patterns:        847  (vs 134 solo)
  Anti-patterns:         112  (vs 28 solo)
  Cross-engineer:        234  patterns discovered by one, used by others

TOP TEAM PATTERNS (by adoption)
────────────────
  Pattern                              Discovered By    Adopted By
  ──────────────────────────────────  ──────────────  ──────────
  "Structured logging with trace_id"  Sarah (Oct)      5/5 ✅
  "Pydantic V2 migration checklist"   Alex (Nov)       4/5
  "Redis connection pool sizing"      You (Dec)        4/5
  "Async test fixtures for FastAPI"   Maria (Jan)      3/5

ANTI-PATTERN HALL OF FAME
────────────────
  "Never deploy on Friday without rollback plan"
    Originally: Alex shipped a broken migration, 3h incident
    Prevented:  7 times across team since stored
    Status:     Organizational knowledge ✅

ONBOARDING IMPACT
────────────────
  New engineer (Raj, joined 3 weeks ago):
    Sessions to first productive PR:    3 (team avg before Cortex: 12)
    Anti-patterns surfaced in week 1:   14
    → "It's like having a senior engineer pair with you 24/7"

# One engineer's lesson. Five engineers' knowledge.
# Onboarding: 12 sessions → 3 sessions.
# That's the compound effect at team scale.""",
            },
            {
                "id": "4D",
                "name": '"The Autonomous Codebase" (2028 \u2014 Self-Healing Systems)',
                "feeling": 'Target feeling: "This is where AI-assisted development is going."',
                "terminal": r"""# 2028: Cortex monitors production. Detects drift. Proposes fixes.
❯ cortex watch --autonomous

╔══════════════════════════════════════════════════════╗
║     CORTEX — AUTONOMOUS CODEBASE INTELLIGENCE        ║
╚══════════════════════════════════════════════════════╝

LIVE MONITORING (last 24h)
────────────────
  Commits observed:         23
  Patterns matched:         12 (applied correctly)
  Anti-patterns triggered:   2 (prevented pre-merge)
  Architecture drift:        1 (flagged for review)

AUTONOMOUS ACTIONS TAKEN
────────────────
  09:14  PR #312: Detected circular import risk
         → Added comment with prevention pattern + fix
         → Author accepted suggestion. Merged clean.

  14:22  PR #315: Redis timeout set to default (0)
         → Flagged anti-pattern: "Never use default Redis timeout"
         → Linked to incident from 2025-12-15
         → Author fixed before review.

  18:41  Commit a3f82c: New endpoint without rate limiting
         → Opened draft PR with rate limiter middleware
         → Based on template from api-gateway (92% confidence)
         → Awaiting human review.

ARCHITECTURE GUARDIAN
────────────────
  ⚠️  DRIFT DETECTED: ml-serving now imports from data-pipeline
     This creates a circular dependency risk.
     Historical: api-gateway had same issue 2025-10-22 (resolved)
     Recommendation: Extract shared models to common/ package
     Confidence: 87% (pattern matched 3 prior resolutions)

# Cortex doesn't just remember. It watches. It intervenes.
# Not replacing engineers. Amplifying institutional knowledge
# at the speed of git push.""",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Build PDF
# ---------------------------------------------------------------------------
def build_pdf(output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    styles = make_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story: list[Flowable] = []
    usable_width = doc.width

    # ── Title page ──────────────────────────────────────────────
    story.append(Spacer(1, 2.0 * inch))
    story.append(Paragraph("Cortex Demo Scripts", styles["title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Developer Experience Showcase", styles["subtitle"]))
    story.append(Spacer(1, 12))
    story.append(HRule(width=3 * inch, color=BLUE, thickness=2))
    story.append(Spacer(1, 18))
    story.append(Paragraph("16 Demo Scripts Across 4 Use Case Categories", styles["subtitle"]))
    story.append(Spacer(1, 24))
    story.append(Paragraph("March 2026", styles["date"]))
    story.append(PageBreak())

    # ── Table of Contents ───────────────────────────────────────
    story.append(Paragraph("Table of Contents", styles["toc_title"]))
    story.append(HRule(width=usable_width, color=BLUE, thickness=1))
    story.append(Spacer(1, 12))
    for cat in CATEGORIES:
        story.append(Paragraph(f"Category {cat['num']}: {cat['title']}", styles["toc_cat"]))
        for sc in cat["scripts"]:
            story.append(Paragraph(f"{sc['id']}  {sc['name']}", styles["toc_item"]))
    story.append(Spacer(1, 18))
    story.append(Paragraph("Summary Assessment Table", styles["toc_cat"]))
    story.append(Paragraph("Appendix: Feature Validation Matrix", styles["toc_cat"]))
    story.append(PageBreak())

    # ── Category sections ───────────────────────────────────────
    for cat in CATEGORIES:
        # Category heading page
        story.append(Paragraph(f"Category {cat['num']}: {cat['title']}", styles["cat_heading"]))
        story.append(HRule(width=usable_width, color=BLUE, thickness=1.5))
        story.append(Spacer(1, 6))
        story.append(Paragraph(cat["thesis"], styles["cat_thesis"]))

        for i, sc in enumerate(cat["scripts"]):
            if i > 0:
                story.append(PageBreak())
            story.append(Paragraph(f"{sc['id']}: {sc['name']}", styles["script_title"]))
            story.append(Paragraph(sc["feeling"], styles["target"]))
            story.append(Spacer(1, 4))
            story.append(TerminalBlock(sc["terminal"], width=usable_width))
            story.append(Spacer(1, 12))

        story.append(PageBreak())

    # ── Summary Assessment Table ────────────────────────────────
    story.append(Paragraph("Summary Assessment", styles["summary_head"]))
    story.append(HRule(width=usable_width, color=BLUE, thickness=1.5))
    story.append(Spacer(1, 12))

    # Use Paragraph cells so text wraps instead of overflowing
    hdr_style = ParagraphStyle(
        "tbl_hdr",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=WHITE,
        leading=13,
    )
    cell_style = ParagraphStyle(
        "tbl_cell",
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY,
        leading=12,
    )

    table_data = [
        [
            Paragraph("Category", hdr_style),
            Paragraph("Best Script", hdr_style),
            Paragraph("Why It Wins", hdr_style),
            Paragraph("Audience Hook", hdr_style),
        ],
        [
            Paragraph("1. Memory Layer", cell_style),
            Paragraph("1B: Anti-Pattern Save", cell_style),
            Paragraph("Visceral \u2014 shows a real bug prevented", cell_style),
            Paragraph('"This would have saved me a week"', cell_style),
        ],
        [
            Paragraph("2. Cost Engine", cell_style),
            Paragraph("2A: The Router", cell_style),
            Paragraph("Hard numbers \u2014 61% savings, 11 models", cell_style),
            Paragraph('"I\'m wasting money right now"', cell_style),
        ],
        [
            Paragraph("3. Portfolio Brain", cell_style),
            Paragraph("3A: Portfolio Pulse", cell_style),
            Paragraph("Novel view \u2014 no tool gives this today", cell_style),
            Paragraph('"I\'ve never had this view before"', cell_style),
        ],
        [
            Paragraph("4. Future", cell_style),
            Paragraph("4A: Agent Memory", cell_style),
            Paragraph("Timely \u2014 agent infra is the 2026 conversation", cell_style),
            Paragraph('"This is what agent infra looks like"', cell_style),
        ],
    ]

    col_widths = [1.2 * inch, 1.5 * inch, 2.2 * inch, 2.1 * inch]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tbl)

    # ── Appendix: Feature Validation Matrix ───────────────────
    story.append(PageBreak())
    story.append(Paragraph("Appendix: Feature Validation Matrix", styles["summary_head"]))
    story.append(HRule(width=usable_width, color=BLUE, thickness=1.5))
    story.append(Spacer(1, 12))

    # Validation summary paragraph
    validation_summary = (
        "<b>Validation Summary</b><br/>"
        "&bull; 24 features SHIPPED (code + tests + production-ready)<br/>"
        "&bull; 2 features PARTIAL (backend exists, CLI gap)<br/>"
        "&bull; 1 feature VISION (future — no multi-user architecture yet)<br/>"
        "&bull; 1 feature UNVERIFIED (Batch API 50% savings — pricing real, no measurement)<br/>"
        "&bull; Total test coverage: 1,111 tests passing"
    )
    summary_style = ParagraphStyle(
        "val_summary",
        fontName="Helvetica",
        fontSize=11,
        textColor=GRAY,
        leading=16,
        spaceAfter=18,
    )
    story.append(Paragraph(validation_summary, summary_style))
    story.append(Spacer(1, 6))

    # Status colours for cell backgrounds
    STATUS_GREEN = HexColor("#c8e6c9")  # SHIPPED
    STATUS_YELLOW = HexColor("#fff9c4")  # PARTIAL
    STATUS_RED = HexColor("#ffcdd2")  # NOT IMPLEMENTED
    STATUS_GRAY_BG = HexColor("#e0e0e0")  # DEMO ONLY
    STATUS_BLUE_BG = HexColor("#bbdefb")  # VISION (future)

    # Reusable styles for validation tables
    val_hdr_style = ParagraphStyle(
        "val_hdr",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=WHITE,
        leading=12,
    )
    val_cell_style = ParagraphStyle(
        "val_cell",
        fontName="Helvetica",
        fontSize=8,
        textColor=GRAY,
        leading=11,
    )
    val_cat_title = ParagraphStyle(
        "val_cat_title",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=BLUE,
        spaceBefore=14,
        spaceAfter=8,
    )

    val_col_widths = [2.3 * inch, 1.3 * inch, 3.4 * inch]

    def _status_color(status_text):
        """Return background colour for a status string."""
        s = status_text.upper()
        if "SHIPPED" in s:
            return STATUS_GREEN
        if "PARTIAL" in s:
            return STATUS_YELLOW
        if "NOT IMPLEMENTED" in s:
            return STATUS_RED
        if "DEMO ONLY" in s:
            return STATUS_GRAY_BG
        if "VISION" in s:
            return STATUS_BLUE_BG
        if "UNVERIFIED" in s:
            return STATUS_YELLOW
        return WHITE

    def _build_validation_table(title, rows):
        """Build a category validation table and add to story."""
        story.append(Paragraph(title, val_cat_title))
        data = [
            [
                Paragraph("Claim", val_hdr_style),
                Paragraph("Status", val_hdr_style),
                Paragraph("Evidence", val_hdr_style),
            ],
        ]
        for claim, status, evidence in rows:
            data.append(
                [
                    Paragraph(claim, val_cell_style),
                    Paragraph(status, val_cell_style),
                    Paragraph(evidence, val_cell_style),
                ]
            )

        tbl_v = Table(data, colWidths=val_col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, MED_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        # Apply per-row status colour to the Status column (col 1)
        for row_idx in range(1, len(data)):
            status_text = rows[row_idx - 1][1]
            bg = _status_color(status_text)
            style_cmds.append(("BACKGROUND", (1, row_idx), (1, row_idx), bg))

        tbl_v.setStyle(TableStyle(style_cmds))
        story.append(tbl_v)
        story.append(Spacer(1, 6))

    # Category 1: Memory Layer
    _build_validation_table(
        "Category 1: Memory Layer",
        [
            ("cortex briefing", "SHIPPED", "cli.py:649, 7 tests"),
            (
                'cortex intelligence "&lt;query&gt;"',
                "SHIPPED",
                "cli.py, MCP + bridge API + CLI subparser",
            ),
            (
                "Anti-pattern database",
                "SHIPPED",
                "orchestration/anti_pattern_detector.py, seed patterns",
            ),
            (
                "Cross-project pattern transfer",
                "SHIPPED",
                "cortex portfolio patterns --propagate CLI wired",
            ),
            ("cortex learn", "SHIPPED", "cli.py:1430, 8 tests"),
            ("cortex learn --pipeline", "SHIPPED", "learning_telemetry.py, 12 tests"),
            ("Implicit feedback", "SHIPPED", "implicit_collector.py, 28 tests"),
            (
                "Context quality optimization",
                "SHIPPED",
                "21% dedup savings, 0.94 position quality score",
            ),
        ],
    )

    # Category 2: Cost Engine
    _build_validation_table(
        "Category 2: Cost Engine",
        [
            ("cortex orchestrate --dry-run", "SHIPPED", "78+ orchestration tests"),
            ("Multi-provider (12 models, 6 providers)", "SHIPPED", "191 conductor tests"),
            ("All 6 providers", "SHIPPED", "conductor/providers/"),
            ("cortex batch fill", "SHIPPED", "CLI wired to IntelligentBatchOrchestrator"),
            (
                "50% Batch API savings",
                "EXISTS BUT UNVERIFIED",
                "Anthropic pricing is real, no measurement",
            ),
            ("Automatic fallback chains", "SHIPPED", "conductor/caller.py:336-367"),
            ("cortex health --providers", "SHIPPED", "CLI flag wired to conductor provider status"),
        ],
    )

    story.append(PageBreak())

    # Category 3: Portfolio Brain
    _build_validation_table(
        "Category 3: Portfolio Brain",
        [
            ("cortex briefing --portfolio", "SHIPPED", "CLI flag wired to health matrix"),
            ("cortex portfolio patterns --propagate", "SHIPPED", "CLI wired to PortfolioMemory"),
            (
                "cortex deps --cross-project",
                "SHIPPED",
                "CLI wired to bridge_system dependency analysis",
            ),
            (
                "cortex portfolio --switching-cost",
                "SHIPPED",
                "Real measurement via switch_tracker.py, 8 tests",
            ),
            ("Cross-project signals", "PARTIAL", "Passive retrieval, not active detection"),
        ],
    )

    # Category 4: Future
    _build_validation_table(
        "Category 4: Future",
        [
            ("cortex sessions --active", "PARTIAL", "MCP tool exists, no CLI"),
            ("cortex learn --pipeline", "SHIPPED", "learning_telemetry.py, 12 tests"),
            (
                "cortex team --insights",
                "VISION",
                "Future feature -- no multi-user architecture yet",
            ),
            ("cortex watch --autonomous", "SHIPPED", "cli.py cmd_watch --autonomous flag"),
        ],
    )

    # Cross-Cutting
    _build_validation_table(
        "Cross-Cutting",
        [
            ("Hybrid BM25 + embedding (RRF)", "SHIPPED", "17 tests"),
            ("Three-tier memory", "SHIPPED", "31 tests"),
            ("Context optimizer", "SHIPPED", "26 tests"),
            ("Model selection intelligence", "SHIPPED", "37 tests"),
            ("Quality-weighted accuracy", "SHIPPED", "8 tests"),
        ],
    )

    # ── Build ───────────────────────────────────────────────────
    doc.build(story)
    print(f"PDF generated: {output_path}")
    print(f"  Pages: ~{len(CATEGORIES) * 5 + 4}")


if __name__ == "__main__":
    build_pdf("/Users/jesse.kemp/Dev/cortex/docs/assets/Cortex_Demo_Scripts.pdf")
