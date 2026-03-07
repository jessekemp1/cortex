import { useState, useEffect, useRef, useCallback } from 'react'
import { clsx } from 'clsx'

interface TerminalLine {
  text: string
  type: 'command' | 'output' | 'highlight' | 'muted' | 'success' | 'warning' | 'header' | 'empty'
  delay?: number
}

interface Scenario {
  id: string
  label: string
  description: string
  lines: TerminalLine[]
}

const SCENARIOS: Scenario[] = [
  {
    id: 'session-start',
    label: 'Session Start',
    description: 'Every session begins with full context — no re-explaining needed',
    lines: [
      { text: '$ claude', type: 'command', delay: 400 },
      { text: '', type: 'empty', delay: 200 },
      { text: '=== Cortex Session Intelligence ===', type: 'header', delay: 100 },
      { text: '', type: 'empty', delay: 50 },
      { text: '=== Where You Left Off ===', type: 'highlight', delay: 80 },
      { text: '  Last session: building the checkout flow for the e-commerce app.', type: 'output', delay: 60 },
      { text: '  Stripe integration working. Cart total calculation had a', type: 'output', delay: 60 },
      { text: '  rounding bug with discount codes — fix started, not finished.', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '=== Alerts ===', type: 'highlight', delay: 80 },
      { text: '  WARN  2 tests failing in checkout/ since last commit', type: 'warning', delay: 80 },
      { text: '  INFO  Goal "Launch MVP" — 4 days left, 3 tasks remaining', type: 'muted', delay: 80 },
      { text: '', type: 'empty', delay: 50 },
      { text: '=== Things to Know ===', type: 'highlight', delay: 80 },
      { text: '  Your .env was updated by a teammate (2 new variables added).', type: 'output', delay: 60 },
      { text: '  The Stripe test key expired yesterday — renew before testing.', type: 'warning', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '=== Suggested Next Step ===', type: 'highlight', delay: 80 },
      { text: '  Finish the discount code rounding fix (you were mid-way)', type: 'success', delay: 80 },
      { text: '', type: 'empty', delay: 50 },
      { text: '===================================', type: 'header', delay: 80 },
      { text: '', type: 'empty', delay: 100 },
      { text: 'Ready. Context loaded in 87ms.', type: 'success', delay: 200 },
    ],
  },
  {
    id: 'intelligence',
    label: 'Ask Anything',
    description: 'Search your entire project history with plain English',
    lines: [
      { text: '$ cortex intelligence "Why did the deploy fail last Friday?"', type: 'command', delay: 600 },
      { text: '', type: 'empty', delay: 300 },
      { text: 'Searching memory... (52ms)', type: 'muted', delay: 400 },
      { text: '', type: 'empty', delay: 100 },
      { text: '=== Found 3 Related Episodes ===', type: 'header', delay: 80 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  [Mar 1, Session #94]  Deploy failed at build step:', type: 'highlight', delay: 80 },
      { text: '    - Node version mismatch: CI uses 18, local was 20', type: 'output', delay: 60 },
      { text: '    - Package lock out of sync after adding shadcn/ui', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  [Mar 1, Session #95]  Fix applied:', type: 'highlight', delay: 80 },
      { text: '    Added .nvmrc (v18) + regenerated package-lock. Deployed OK.', type: 'success', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  [Pattern learned]  "Adding new UI packages without lock sync"', type: 'warning', delay: 80 },
      { text: '    Confidence: 0.87  |  Seen 3 times across 2 projects', type: 'muted', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: 'Tip: Run npm install && npm ci --dry-run before pushing', type: 'success', delay: 100 },
      { text: 'after adding new packages. Catches lock drift early.', type: 'success', delay: 60 },
    ],
  },
  {
    id: 'anti-pattern',
    label: 'Mistake Prevention',
    description: 'Cortex catches problems before they happen',
    lines: [
      { text: '$ claude "Update the database schema to add a users table"', type: 'command', delay: 500 },
      { text: '', type: 'empty', delay: 300 },
      { text: '  CORTEX  Heads up — potential issue detected', type: 'warning', delay: 200 },
      { text: '', type: 'empty', delay: 100 },
      { text: '  Pattern: "Schema change without migration file"', type: 'warning', delay: 80 },
      { text: '  This has caused problems before (3 times in this project).', type: 'muted', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  What happened last time:', type: 'highlight', delay: 80 },
      { text: '  You edited models.py directly on Feb 12. The change worked', type: 'output', delay: 60 },
      { text: '  locally but broke staging because there was no migration.', type: 'output', delay: 60 },
      { text: '  Took 2 hours to debug why staging had the old schema.', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  Suggestion: Create a migration file alongside the schema', type: 'success', delay: 100 },
      { text: '  change so it applies automatically on deploy.', type: 'success', delay: 60 },
      { text: '', type: 'empty', delay: 200 },
      { text: '> Generating migration file...', type: 'muted', delay: 300 },
      { text: '  Created: migrations/003_add_users_table.sql', type: 'output', delay: 100 },
      { text: '  Schema + migration ready. No deployment surprises.', type: 'success', delay: 100 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  Crisis averted. Pattern reinforced.', type: 'success', delay: 200 },
    ],
  },
  {
    id: 'recommendations',
    label: 'Smart Priorities',
    description: 'What to work on next, ranked by impact',
    lines: [
      { text: '$ cortex recommendations', type: 'command', delay: 400 },
      { text: '', type: 'empty', delay: 200 },
      { text: '=== Your Priorities ===', type: 'header', delay: 100 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  #1  HIGH    Fix checkout rounding bug (in progress)', type: 'warning', delay: 80 },
      { text: '              Started last session. 2 tests still failing.', type: 'muted', delay: 60 },
      { text: '              Blocks: payment flow, launch milestone', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  #2  MEDIUM  Renew Stripe test API key (expired yesterday)', type: 'highlight', delay: 80 },
      { text: '              Nothing payment-related will work until this is done.', type: 'muted', delay: 60 },
      { text: '              Quick fix: update .env, takes 2 minutes', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  #3  MEDIUM  Review teammate\'s PR #47 (open 3 days)', type: 'highlight', delay: 80 },
      { text: '              They\'re blocked waiting on your review.', type: 'muted', delay: 60 },
      { text: '              14 files changed — mostly CSS + 1 API route', type: 'output', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: '  #4  LOW     "Launch MVP" goal: 3 tasks left, 4 days remain', type: 'output', delay: 80 },
      { text: '              On track if #1 and #2 are done today.', type: 'muted', delay: 60 },
      { text: '', type: 'empty', delay: 50 },
      { text: 'Based on: your git activity, goal deadlines, and team signals', type: 'muted', delay: 100 },
    ],
  },
]

const lineColors: Record<TerminalLine['type'], string> = {
  command: 'text-cortex-cyan',
  output: 'text-cortex-text-secondary',
  highlight: 'text-cortex-text-primary font-medium',
  muted: 'text-cortex-text-muted',
  success: 'text-cortex-nominal',
  warning: 'text-cortex-warning',
  header: 'text-cortex-cyan font-bold',
  empty: '',
}

export function InteractiveTerminal() {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS[0])
  const [visibleLines, setVisibleLines] = useState<number>(0)
  const [isTyping, setIsTyping] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)
  const timeoutRefs = useRef<ReturnType<typeof setTimeout>[]>([])

  const clearTimeouts = useCallback(() => {
    timeoutRefs.current.forEach(clearTimeout)
    timeoutRefs.current = []
  }, [])

  const playScenario = useCallback((scenario: Scenario) => {
    clearTimeouts()
    setVisibleLines(0)
    setIsTyping(true)

    let cumulativeDelay = 300
    scenario.lines.forEach((line, index) => {
      cumulativeDelay += line.delay || 80
      const t = setTimeout(() => {
        setVisibleLines(index + 1)
        if (terminalRef.current) {
          terminalRef.current.scrollTop = terminalRef.current.scrollHeight
        }
        if (index === scenario.lines.length - 1) {
          setIsTyping(false)
        }
      }, cumulativeDelay)
      timeoutRefs.current.push(t)
    })
  }, [clearTimeouts])

  useEffect(() => {
    playScenario(activeScenario)
    return clearTimeouts
  }, [activeScenario, playScenario, clearTimeouts])

  const handleScenarioClick = (scenario: Scenario) => {
    setActiveScenario(scenario)
  }

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Scenario selector tabs */}
      <div className="flex flex-wrap gap-2 mb-4">
        {SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => handleScenarioClick(scenario)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-mono transition-all duration-200',
              activeScenario.id === scenario.id
                ? 'bg-cortex-cyan/20 text-cortex-cyan border border-cortex-cyan/40 shadow-cyan-glow'
                : 'bg-cortex-surface text-cortex-text-muted border border-cortex-border hover:border-cortex-cyan/30 hover:text-cortex-text-secondary'
            )}
          >
            {scenario.label}
          </button>
        ))}
      </div>

      {/* Description */}
      <p className="text-cortex-text-muted text-sm mb-3 font-mono">
        {activeScenario.description}
      </p>

      {/* Terminal window */}
      <div className="rounded-xl overflow-hidden border border-cortex-border shadow-elevated">
        {/* Title bar */}
        <div className="bg-cortex-elevated px-4 py-2.5 flex items-center gap-2 border-b border-cortex-border">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-cortex-text-muted text-xs font-mono ml-2">
            cortex-demo — zsh — 80x24
          </span>
          {isTyping && (
            <span className="ml-auto text-cortex-cyan text-xs font-mono animate-pulse-fast">
              running...
            </span>
          )}
        </div>

        {/* Terminal body */}
        <div
          ref={terminalRef}
          className="bg-cortex-bg p-4 font-mono text-sm leading-6 h-[420px] overflow-y-auto scroll-smooth"
        >
          {activeScenario.lines.slice(0, visibleLines).map((line, i) => (
            <div
              key={`${activeScenario.id}-${i}`}
              className={clsx(
                'animate-fade-in whitespace-pre-wrap',
                lineColors[line.type],
                line.type === 'empty' && 'h-4'
              )}
            >
              {line.type !== 'empty' && line.text}
            </div>
          ))}
          {isTyping && visibleLines < activeScenario.lines.length && (
            <span className="inline-block w-2 h-4 bg-cortex-cyan animate-pulse-fast" />
          )}
        </div>
      </div>
    </div>
  )
}
