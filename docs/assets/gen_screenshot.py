"""
Generate a terminal-style PNG for the Cortex README demo.
Produces docs/assets/demo.png — 960×680 dark terminal with colored ANSI-style text.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ── Palette (Monokai-ish dark terminal) ─────────────────────────────────
BG = (30, 30, 30)
FRAME_BAR = (50, 50, 50)
DOT_RED = (255, 95, 87)
DOT_YEL = (255, 189, 46)
DOT_GRN = (39, 201, 63)
WHITE = (240, 240, 240)
DIM = (140, 140, 140)
CYAN = (97, 214, 214)
GREEN = (87, 201, 120)
YELLOW = (255, 204, 102)
ORANGE = (255, 154, 80)
BLUE = (100, 149, 237)
MAGENTA = (197, 134, 192)

W, H = 960, 700
TITLE_H = 36
PAD_L = 24
LINE_H = 19
FONT_SIZE = 13


# ── Font ─────────────────────────────────────────────────────────────────
def load_font(size):
    candidates = [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/System/Library/Fonts/Courier.dfont",
        "/Library/Fonts/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


font = load_font(FONT_SIZE)
font_bold = load_font(FONT_SIZE + 1)

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# ── Title bar ─────────────────────────────────────────────────────────────
draw.rectangle([0, 0, W, TITLE_H], fill=FRAME_BAR)
for i, (cx, col) in enumerate([(16, DOT_RED), (36, DOT_YEL), (56, DOT_GRN)]):
    draw.ellipse([cx - 6, TITLE_H // 2 - 6, cx + 6, TITLE_H // 2 + 6], fill=col)
title_text = "cortex — terminal"
tw = draw.textlength(title_text, font=font)
draw.text(((W - tw) / 2, 10), title_text, font=font, fill=DIM)

# ── Content lines: (text, color, indent) ─────────────────────────────────
lines = [
    ("$ cortex briefing", GREEN, 0),
    ("", WHITE, 0),
    ("╔══════════════════════════════════════════════════════════════════╗", CYAN, 0),
    ("║        CORTEX INTELLIGENCE BRIEFING — March 5, 2026            ║", CYAN, 0),
    ("╚══════════════════════════════════════════════════════════════════╝", CYAN, 0),
    ("", WHITE, 0),
    ("🎯  ACTIVE PROJECTS (3)", YELLOW, 0),
    ("  • fastapi-backend    2 commits since yesterday, tests passing", WHITE, 2),
    ("  • data-pipeline      scheduled job failed 6hrs ago (memory threshold)", ORANGE, 2),
    ("  • frontend-react     goal deadline in 3 days — no recent activity", ORANGE, 2),
    ("", WHITE, 0),
    ("⚠️   NEEDS ATTENTION", ORANGE, 0),
    ("  • data-pipeline: investigate memory usage spike", WHITE, 2),
    ("  • frontend-react: authentication integration overdue", WHITE, 2),
    ("", WHITE, 0),
    ("🧠  RELEVANT PATTERNS (from previous sessions)", MAGENTA, 0),
    ("  • Redis connection pooling: timeout settings matter for long-running tasks", WHITE, 2),
    ("  • FastAPI circular imports: resolved via lazy imports in auth module", WHITE, 2),
    ("  • Docker memory limits: 512MB minimum for FastAPI + Redis stack", WHITE, 2),
    ("", WHITE, 0),
    ("📈  PORTFOLIO HEALTH", GREEN, 0),
    ("  • 12 anti-patterns learned, 0 repeated in last 30 days", WHITE, 2),
    ("  • Average debugging time: ↓ 34% since November", GREEN, 2),
    ("  • Test coverage: 89% average across all projects", WHITE, 2),
    ("", WHITE, 0),
    ('$ cortex intelligence "should I use Redis for user sessions?"', GREEN, 0),
    ("", WHITE, 0),
    ("🔍  INTELLIGENCE RESULTS", CYAN, 0),
    ("", WHITE, 0),
    ("  APPLICABLE PATTERNS", YELLOW, 2),
    ("  • Redis connection pool: max_connections=20, timeout=30s for this stack", WHITE, 4),
    ("  • Separate DB indices: 0=cache  1=sessions  2=rate_limiting", WHITE, 4),
    ("  • Start with TTL=3600, monitor hit rates before tuning", WHITE, 4),
    ("", WHITE, 0),
    ("  ⚠️  ANTI-PATTERNS", ORANGE, 2),
    ("  • DON'T use default Redis timeout → 502 errors under load", WHITE, 4),
    ("  • AVOID storing objects >1MB → use PostgreSQL for user profiles", WHITE, 4),
    ("", WHITE, 0),
    ("  ✅  RECOMMENDATIONS", GREEN, 2),
    ("  • Use RedisJSON if storing complex session objects", WHITE, 4),
    ("  • Monitor connection pool exhaustion from the start", WHITE, 4),
]

y = TITLE_H + 14
for text, color, indent in lines:
    if y > H - 10:
        break
    x = PAD_L + indent * 6
    draw.text((x, y), text, font=font, fill=color)
    y += LINE_H

# ── Cursor blink ──────────────────────────────────────────────────────────
draw.rectangle([PAD_L, y + 2, PAD_L + 8, y + LINE_H - 2], fill=GREEN)

img.save("/Users/jesse.kemp/Dev/cortex/docs/assets/demo.png", "PNG", optimize=True)
print(f"Saved: docs/assets/demo.png  ({W}×{H})")
