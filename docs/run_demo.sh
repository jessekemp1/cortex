#!/bin/bash
# Cortex Demo Script — Senior Developer Audience
# Run in a fresh terminal: bash cortex/docs/run_demo.sh
# Each step pauses. Press Enter to continue.

set -e
cd /Users/jesse.kemp/Dev
PYTHON="/Users/jesse.kemp/Dev/Vortex/backend/.venv/bin/python"

pause() {
  echo ""
  echo "  ─── Press Enter for next step ───"
  read -r
  clear
}

# ══════════════════════════════════════════════════════════════════
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           CORTEX INTELLIGENCE — LIVE DEMO               ║"
echo "║                                                          ║"
echo "║  Persistent memory + outcome learning + task routing     ║"
echo "║  for LLM-powered development across 6 projects.         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Every Claude Code session starts from zero."
echo "  Cortex remembers what worked, what failed, and what matters."
echo ""
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 1: PORTFOLIO — Live data from 6 projects           │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
python3 scripts/portfolio_status.py
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 2: MEMORY — Three-tier retrieval (841 patterns)    │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  Query: 'GRIB coordinate conventions'"
echo "  Searching: short-term → working → long-term (BM25 + embeddings)"
echo ""
$PYTHON -c "
import sys; sys.path.insert(0, '.')
from cortex.bridge import CortexBridge
b = CortexBridge()
ctx = b.get_context('GRIB coordinate conventions', limit=5, project='vortex')
if isinstance(ctx, list):
    for i, item in enumerate(ctx[:5]):
        source = item.get('source', '?')
        content = str(item.get('content', item.get('description', '')))[:120]
        print(f'  {i+1}. [{source}] {content}')
elif isinstance(ctx, dict):
    for k, v in list(ctx.items())[:5]:
        print(f'  {k}: {str(v)[:120]}')
print()
print('  Benchmark: 80% recall@10, 0.643 MRR (domain-specific queries)')
"
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 3: ANTI-PATTERNS — Behavioral failure prevention   │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  These are not linter rules. They're patterns learned from"
echo "  real failures that cost hours to debug."
echo ""
echo "  Example — Mock Patch Namespace (cost 2 sessions):"
echo "  ──────────────────────────────────────────────────"
echo "  Pattern:  from X import Y at module level binds Y"
echo "            in the importing module at import time."
echo "  Symptom:  Mock never called, real code runs, test"
echo "            passes silently with real data."
echo "  Fix:      Patch importing_module.Y, not X.Y."
echo "  Detect:   Add mock.assert_called() after every"
echo "            response assertion."
echo ""
echo "  12+ anti-patterns stored, each with prevention context."
echo "  Every new session gets these automatically via CLAUDE.md."
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 4: AST META-TESTING — Tests that test the tests    │"
echo "│          (Novel contribution)                             │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  Three AST-based checks enforce assertion quality across"
echo "  the entire test suite. Running now..."
echo ""
pytest cortex/tests/test_assertion_quality.py -v 2>&1
echo ""
echo "  Result: 1.8% trivial assertion rate (enforced automatically)."
echo "  Checks: no trivial-only files, integration tests have"
echo "  behavioral calls, no empty test bodies."
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 5: ORCHESTRATION — Intake → Route → Dispatch       │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  Bridge API at :8765 — querying recommendations..."
echo ""
curl -s http://127.0.0.1:8765/intelligence/recommendations | python3 -c "
import json, sys
data = json.load(sys.stdin)
action = data.get('next_action', {})
print(f'  Next Action: [{action.get(\"priority\", \"?\")}] {action.get(\"action\", \"?\")}')
print(f'  Type: {action.get(\"type\", \"?\")}')
print()
alerts = data.get('risk_alerts', [])
if alerts:
    print(f'  Risk Alerts ({len(alerts)}):')
    for a in alerts:
        print(f'    [{a.get(\"severity\",\"?\")}] {a.get(\"message\",\"?\")}')
print()
goals = data.get('goals_summary', {})
print(f'  Goals: {goals.get(\"completed\", 0)} completed, {goals.get(\"high_pending\", 0)} high pending')
"
echo ""
echo "  Honest note: 13 unique work items dispatched to date."
echo "  Router uses static heuristics — learning infrastructure"
echo "  is built (Q-table, 360 states) but needs more data."
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 6: CRA — Continuous Research Agent                  │"
echo "│          Frontier scanning + capability-vector scoring    │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
DISC=$(wc -l < ~/.cortex/research/cra/discoveries.jsonl 2>/dev/null || echo "0")
ASSESS=$(wc -l < ~/.cortex/research/cra/assessments.jsonl 2>/dev/null || echo "0")
PROPS=$(ls ~/.cortex/research/cra/proposals/ 2>/dev/null | wc -l | tr -d ' ')
echo "  Pipeline:  ${DISC} discoveries → ${ASSESS} assessed → ${PROPS} proposals"
echo ""
echo "  Latest assessment:"
tail -1 ~/.cortex/research/cra/assessments.jsonl 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'    Title:      {data.get(\"title\", \"?\")[:60]}')
print(f'    Disruption: {data.get(\"disruption_risk\", \"?\")}')
print(f'    Effort:     {data.get(\"adoption_effort\", \"?\")}')
print(f'    Impact:     {data.get(\"expected_impact\", \"?\")}')
print(f'    Verdict:    {data.get(\"recommendation\", \"?\")}')
scores = data.get('relevance_scores', {})
if scores:
    print(f'    Capability scores:')
    for k, v in scores.items():
        bar = '#' * int(v * 20)
        print(f'      {k:<22} {v:.2f} [{bar}]')
"
echo ""
echo "  Each discovery scored against 7 Cortex-specific capability"
echo "  vectors. Not 'trending repo' — 'how does this affect YOUR architecture.'"
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 7: WEB GATEWAY — Self-hosted chat UI               │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  Opening http://127.0.0.1:8765/chat ..."
echo "  (JetBrains Mono, dark theme, WebSocket, PWA-installable)"
echo ""
open http://127.0.0.1:8765/chat 2>/dev/null || echo "  Open manually: http://127.0.0.1:8765/chat"
echo ""
echo "  Try: /briefing, /status, /projects, or any question."
echo "  Backed by the same Bridge API used by MCP, Telegram bot,"
echo "  and the CLI."
pause

# ══════════════════════════════════════════════════════════════════
echo "┌──────────────────────────────────────────────────────────┐"
echo "│  STEP 8: HONEST LIMITATIONS                               │"
echo "└──────────────────────────────────────────────────────────┘"
echo ""
echo "  What doesn't work yet:"
echo ""
echo "  • Implicit feedback: 39 entries in 14 weeks."
echo "    Not at learning scale."
echo ""
echo "  • Model routing: 13 dispatched items."
echo "    Static heuristics, not learned thresholds."
echo ""
echo "  • Outcome data: ~60 human-verified out of 657 total."
echo "    Rest is test fixtures and automated pipelines."
echo ""
echo "  • Context benchmark (21.2% dedup) was synthetic."
echo "    We caught this, rewrote the paper, now lead with"
echo "    retrieval benchmark (80% recall, 0.643 MRR) instead."
echo ""
echo "  The architecture is sound. The data needs to accumulate."
echo ""

# ══════════════════════════════════════════════════════════════════
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                   DEMO COMPLETE                          ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║                                                          ║"
echo "║  Cortex: 1,291 tests │ 14 weeks production │ Apache 2.0 ║"
echo "║  Portfolio: 7,500+ tests across 6 projects               ║"
echo "║                                                          ║"
echo "║  Paper:  cortex/docs/cortex_paper.md                     ║"
echo "║  Code:   github.com/jessekemp1/cortex                    ║"
echo "║  Bridge: http://127.0.0.1:8765                           ║"
echo "║  Chat:   http://127.0.0.1:8765/chat                      ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
