#!/usr/bin/env python3
"""Convert Markdown files to styled PDFs using markdown + weasyprint."""

import sys
import markdown
from pathlib import Path
from weasyprint import HTML

CSS = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
    @bottom-center {
        content: "Cortex — " attr(data-title) " | Page " counter(page);
        font-size: 9px;
        color: #999;
    }
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 100%;
}

h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #0d1117;
    border-bottom: 2px solid #0969da;
    padding-bottom: 8px;
    margin-top: 0;
}

h2 {
    font-size: 16pt;
    font-weight: 600;
    color: #1a1a1a;
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 6px;
    margin-top: 24pt;
}

h3 {
    font-size: 13pt;
    font-weight: 600;
    color: #24292f;
    margin-top: 18pt;
}

code {
    font-family: "SF Mono", "Fira Code", "Fira Mono", Menlo, Consolas, monospace;
    font-size: 9pt;
    background: #f6f8fa;
    padding: 1px 4px;
    border-radius: 3px;
}

pre {
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 8.5pt;
    line-height: 1.45;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
}

pre code {
    background: none;
    padding: 0;
    font-size: 8.5pt;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 10pt;
}

th {
    background: #f6f8fa;
    font-weight: 600;
    text-align: left;
    padding: 8px 12px;
    border: 1px solid #d0d7de;
}

td {
    padding: 6px 12px;
    border: 1px solid #d0d7de;
}

tr:nth-child(even) {
    background: #f9fafb;
}

blockquote {
    border-left: 3px solid #0969da;
    margin: 12px 0;
    padding: 4px 16px;
    color: #57606a;
    font-style: italic;
}

strong {
    font-weight: 600;
}

hr {
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 24px 0;
}

ul, ol {
    padding-left: 24px;
}

li {
    margin-bottom: 4px;
}

a {
    color: #0969da;
    text-decoration: none;
}
"""


def convert(md_path: Path, pdf_path: Path):
    """Convert a single markdown file to PDF."""
    text = md_path.read_text()

    html_body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{CSS}</style></head>
<body>{html_body}</body>
</html>"""

    HTML(string=full_html).write_pdf(str(pdf_path))
    size_kb = pdf_path.stat().st_size / 1024
    print(f"  {pdf_path.name} ({size_kb:.0f} KB)")


def main():
    files = [
        # Marketing (public-facing)
        ("cortex/MARKETING/VISION.md", "cortex/MARKETING/pdf/Cortex_Vision.pdf"),
        ("cortex/MARKETING/MANIFESTO.md", "cortex/MARKETING/pdf/Cortex_Manifesto.pdf"),
        (
            "cortex/MARKETING/PRODUCT_OVERVIEW.md",
            "cortex/MARKETING/pdf/Cortex_Product_Overview.pdf",
        ),
        (
            "cortex/MARKETING/TECHNICAL_POSITIONING.md",
            "cortex/MARKETING/pdf/Cortex_Technical_Positioning.pdf",
        ),
        # Strategy (internal)
        ("cortex/STRATEGY/VISION_CONCEPTS.md", "cortex/STRATEGY/pdf/Cortex_Vision_Concepts.pdf"),
        ("cortex/STRATEGY/NAMING_ANALYSIS.md", "cortex/STRATEGY/pdf/Cortex_Naming_Analysis.pdf"),
        (
            "cortex/STRATEGY/MARKET_RESEARCH_2026-03.md",
            "cortex/STRATEGY/pdf/Cortex_Market_Research_2026-03.pdf",
        ),
    ]

    base = Path("/Users/jesse.kemp/Dev")

    print("Converting Markdown → PDF...")
    print()

    for md_rel, pdf_rel in files:
        md_path = base / md_rel
        pdf_path = base / pdf_rel
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        if not md_path.exists():
            print(f"  SKIP {md_rel} (not found)")
            continue

        try:
            convert(md_path, pdf_path)
        except Exception as e:
            print(f"  FAIL {md_rel}: {e}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
