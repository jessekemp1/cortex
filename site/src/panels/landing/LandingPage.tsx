import { InteractiveTerminal } from './InteractiveTerminal'

function HeroSection() {
  return (
    <section className="pt-20 pb-16 px-6">
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cortex-cyan/10 border border-cortex-cyan/20 mb-8">
          <div className="w-2 h-2 rounded-full bg-cortex-nominal animate-pulse-slow" />
          <span className="text-cortex-cyan text-xs font-mono tracking-wider">OPEN SOURCE &middot; APACHE 2.0 &middot; YOU OWN THE DATA</span>
        </div>

        <h1 className="text-5xl md:text-6xl font-bold text-cortex-text-primary mb-6 leading-tight">
          Your AI should
          <span className="text-cortex-cyan"> know you </span>
          by now.
        </h1>

        <p className="text-xl text-cortex-text-secondary max-w-2xl mx-auto mb-10 leading-relaxed">
          Every session starts from zero. Same questions, same mistakes, same context re-explained.
          Cortex gives your AI agent persistent memory, cross-session learning,
          and the ability to get better at helping <em>you</em> over time.
        </p>

        <div className="flex flex-wrap justify-center gap-4 mb-6">
          <code className="px-5 py-3 bg-cortex-surface border border-cortex-border rounded-lg text-cortex-cyan font-mono text-sm hover:border-cortex-cyan/40 transition-colors cursor-pointer select-all">
            pip install cortex-intelligence
          </code>
          <a
            href="https://github.com/jkempster34/cortex"
            className="px-5 py-3 bg-cortex-cyan/10 border border-cortex-cyan/30 rounded-lg text-cortex-cyan font-mono text-sm hover:bg-cortex-cyan/20 transition-colors"
          >
            View on GitHub &rarr;
          </a>
        </div>

        <div className="flex justify-center gap-8 text-cortex-text-muted text-xs font-mono">
          <span>600+ tests</span>
          <span>&middot;</span>
          <span>Python 3.11+</span>
          <span>&middot;</span>
          <span>You own the data</span>
          <span>&middot;</span>
          <span>Runs anywhere</span>
        </div>
      </div>
    </section>
  )
}

function ProblemSection() {
  const problems = [
    {
      icon: '🧠',
      title: 'Sessions are isolated',
      description: 'Opus can solve anything in one session. But session #95 has no idea what happened in session #94. You re-explain, re-discover, re-debug.',
    },
    {
      icon: '🔁',
      title: 'Mistakes repeat',
      description: 'Your AI figured out the deploy needs a migration file last week. This week? Same mistake, same 2-hour detour. Intelligence without memory = Groundhog Day.',
    },
    {
      icon: '📈',
      title: 'No compound learning',
      description: 'A smarter model makes each session better. But it never gets better at helping you specifically — your codebase, your patterns, your projects.',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Not an intelligence problem. An infrastructure one.
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Opus 4.6 is the most capable AI model ever built.
          But more intelligence doesn't solve statelessness.
          These problems persist regardless of how smart the model gets.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {problems.map((problem) => (
            <div
              key={problem.title}
              className="p-6 rounded-xl bg-cortex-surface border border-cortex-border hover:border-cortex-critical/30 transition-colors"
            >
              <div className="text-2xl mb-3">{problem.icon}</div>
              <h3 className="text-lg font-semibold text-cortex-text-primary mb-2">
                {problem.title}
              </h3>
              <p className="text-cortex-text-muted text-sm leading-relaxed">
                {problem.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function WhatCortexAddsSection() {
  const rows = [
    {
      capability: 'Remember what you did last week',
      model: false,
      cortex: true,
      detail: 'Models reset every session. Cortex persists context across sessions, projects, and months.',
    },
    {
      capability: 'Know your codebase\'s specific gotchas',
      model: false,
      cortex: true,
      detail: 'Models know general patterns. Cortex learns that your project breaks when you edit schema without a migration.',
    },
    {
      capability: 'Track whether a fix held over time',
      model: false,
      cortex: true,
      detail: 'Models have no longitudinal view. Cortex tracks outcomes across weeks and months.',
    },
    {
      capability: 'Warn you before repeating a mistake',
      model: false,
      cortex: true,
      detail: 'Models respond to prompts. Cortex proactively intervenes at session start based on behavioral patterns.',
    },
    {
      capability: 'Transfer lessons between projects',
      model: false,
      cortex: true,
      detail: 'Each model session is isolated. Cortex carries patterns learned in Project A into Project B.',
    },
    {
      capability: 'Get better at helping you specifically',
      model: false,
      cortex: true,
      detail: 'Model weights are frozen. Cortex calibrates from your outcomes — what works for you, what doesn\'t.',
    },
    {
      capability: 'Work across multiple AI models',
      model: false,
      cortex: true,
      detail: 'Switch from Claude to GPT to Gemini — your memory travels with you. Vendor-native memory stays behind.',
    },
    {
      capability: 'Own your AI\'s memory',
      model: false,
      cortex: true,
      detail: 'Vendor memory is rented — stored on their terms, locked to their platform. Cortex memory is yours to keep, move, inspect, or delete.',
    },
    {
      capability: 'Reason about complex code',
      model: true,
      cortex: false,
      detail: 'This is what models are built for. Cortex doesn\'t replace your AI — it gives it a memory.',
    },
    {
      capability: 'Generate, debug, and refactor',
      model: true,
      cortex: false,
      detail: 'Opus handles the thinking. Cortex handles the remembering.',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          What Cortex adds to your AI
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Cortex doesn't replace your model. It fills the gaps that no model — however intelligent — can fill on its own.
        </p>

        <div className="overflow-hidden rounded-xl border border-cortex-border">
          <table className="w-full">
            <thead>
              <tr className="bg-cortex-elevated border-b border-cortex-border">
                <th className="text-left text-cortex-text-secondary text-sm font-medium px-5 py-3">Capability</th>
                <th className="text-center text-cortex-text-secondary text-sm font-medium px-4 py-3 w-24">Model</th>
                <th className="text-center text-cortex-cyan text-sm font-medium px-4 py-3 w-24">+ Cortex</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.capability} className={`border-b border-cortex-border/50 ${i % 2 === 0 ? 'bg-cortex-surface' : 'bg-cortex-bg'} group`}>
                  <td className="px-5 py-3">
                    <div className="text-cortex-text-primary text-sm font-medium">{row.capability}</div>
                    <div className="text-cortex-text-muted text-xs mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">{row.detail}</div>
                  </td>
                  <td className="text-center px-4 py-3">
                    {row.model
                      ? <span className="text-cortex-nominal text-lg">&#10003;</span>
                      : <span className="text-cortex-text-muted text-lg">&mdash;</span>
                    }
                  </td>
                  <td className="text-center px-4 py-3">
                    {row.cortex
                      ? <span className="text-cortex-cyan text-lg">&#10003;</span>
                      : <span className="text-cortex-text-muted text-xs font-mono">model</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-center text-cortex-text-muted text-sm mt-6 font-mono">
          Intelligence × Memory = Compound value. Neither alone is enough.
        </p>
      </div>
    </section>
  )
}

function HowItWorksSection() {
  const steps = [
    {
      step: '01',
      name: 'Observe',
      color: 'text-cortex-processing',
      border: 'border-cortex-processing/30',
      description: 'Hooks into git commits, test results, session events, and goal tracking. No manual logging.',
    },
    {
      step: '02',
      name: 'Detect',
      color: 'text-cortex-warning',
      border: 'border-cortex-warning/30',
      description: 'Matches current context against 103 learned behavioral patterns. Flags anti-patterns before they cause bugs.',
    },
    {
      step: '03',
      name: 'Intervene',
      color: 'text-cortex-cyan',
      border: 'border-cortex-cyan/30',
      description: 'Surfaces warnings and recommendations at session start — the moment you actually read context.',
    },
    {
      step: '04',
      name: 'Learn',
      color: 'text-cortex-nominal',
      border: 'border-cortex-nominal/30',
      description: 'Tracks outcomes from git, tests, and goals. Patterns that help get reinforced. Patterns that don\'t fade away.',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          How the loop works
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Your model handles the thinking. Cortex handles the remembering.
          Together, each session builds on every session before it.
        </p>

        <div className="grid md:grid-cols-4 gap-4">
          {steps.map((step, i) => (
            <div key={step.name} className="relative">
              <div className={`p-5 rounded-xl bg-cortex-surface border ${step.border} hover:bg-cortex-elevated transition-colors h-full`}>
                <div className={`text-xs font-mono ${step.color} mb-2`}>STEP {step.step}</div>
                <h3 className={`text-xl font-bold ${step.color} mb-3`}>{step.name}</h3>
                <p className="text-cortex-text-muted text-sm leading-relaxed">
                  {step.description}
                </p>
              </div>
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -right-3 text-cortex-text-muted text-lg">
                  &rarr;
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="text-center mt-6">
          <span className="text-cortex-text-muted text-sm font-mono">
            Step 4 feeds back into Step 1. The loop never stops.
          </span>
        </div>
      </div>
    </section>
  )
}

function DemoSection() {
  return (
    <section className="py-20 px-6 border-t border-cortex-border bg-cortex-bg">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Try it yourself
        </h2>
        <p className="text-cortex-text-secondary text-center mb-10 max-w-2xl mx-auto">
          Click a scenario to see what Cortex does in practice.
          This is real output from a production Cortex instance.
        </p>

        <InteractiveTerminal />
      </div>
    </section>
  )
}

function MemoryTierSection() {
  const tiers = [
    {
      name: 'Working',
      temp: 'hot',
      color: 'text-cortex-critical',
      bg: 'bg-cortex-critical/5',
      border: 'border-cortex-critical/20',
      latency: '<1ms',
      contents: 'Current branch, recent commits, active goals',
      example: 'You\'re on feature/checkout-flow with 2 uncommitted files',
    },
    {
      name: 'Episodic',
      temp: 'warm',
      color: 'text-cortex-warning',
      bg: 'bg-cortex-warning/5',
      border: 'border-cortex-warning/20',
      latency: '~10ms',
      contents: 'Past decisions, debugging sessions, outcomes',
      example: '"Last Friday\'s deploy failed — Node version mismatch + stale lock file"',
    },
    {
      name: 'Semantic',
      temp: 'cold',
      color: 'text-cortex-processing',
      bg: 'bg-cortex-processing/5',
      border: 'border-cortex-processing/20',
      latency: '~50ms',
      contents: 'Learned patterns, anti-patterns, project-specific rules',
      example: '"Schema changes in this project need a migration file or staging breaks"',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Three-tier memory
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Today's session becomes tomorrow's history, which distills into permanent patterns.
          No manual curation required.
        </p>

        <div className="space-y-4">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`p-6 rounded-xl ${tier.bg} border ${tier.border} hover:bg-cortex-elevated/50 transition-colors`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className={`text-lg font-bold ${tier.color}`}>{tier.name}</h3>
                    <span className="text-cortex-text-muted text-xs font-mono">({tier.temp})</span>
                    <span className="ml-auto text-cortex-text-muted text-xs font-mono">{tier.latency}</span>
                  </div>
                  <p className="text-cortex-text-secondary text-sm mb-2">{tier.contents}</p>
                  <p className="text-cortex-text-muted text-sm italic font-mono">{tier.example}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-center mt-6 gap-2 items-center text-cortex-text-muted text-sm font-mono">
          <span>Working</span>
          <span>&darr;</span>
          <span>Episodic</span>
          <span>&darr;</span>
          <span>Semantic</span>
          <span className="text-cortex-cyan ml-2">(auto-tiering)</span>
        </div>
      </div>
    </section>
  )
}

function IntegrationSection() {
  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Works with your tools
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          MCP server for Claude Code and Claude Desktop. Python SDK and CLI for everything else.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {/* MCP */}
          <div className="p-6 rounded-xl bg-cortex-surface border border-cortex-border">
            <h3 className="text-lg font-semibold text-cortex-cyan mb-3 font-mono">MCP Server</h3>
            <p className="text-cortex-text-muted text-sm mb-4">
              Add to <code className="text-cortex-text-secondary">.mcp.json</code> — your agent gets 6 tools automatically.
            </p>
            <div className="bg-cortex-bg rounded-lg p-3 font-mono text-xs text-cortex-text-secondary">
              <div>cortex_intelligence</div>
              <div>cortex_recommendations</div>
              <div>cortex_anomalies</div>
              <div>cortex_projects</div>
              <div>cortex_taskboard</div>
              <div>cortex_prompt_refine</div>
            </div>
          </div>

          {/* Python SDK */}
          <div className="p-6 rounded-xl bg-cortex-surface border border-cortex-border">
            <h3 className="text-lg font-semibold text-cortex-cyan mb-3 font-mono">Python SDK</h3>
            <p className="text-cortex-text-muted text-sm mb-4">
              Import and query. Natural language against your full history.
            </p>
            <div className="bg-cortex-bg rounded-lg p-3 font-mono text-xs">
              <div className="text-cortex-accent">from</div>
              <div className="text-cortex-text-secondary pl-2">cortex.bridge <span className="text-cortex-accent">import</span> CortexBridge</div>
              <div className="text-cortex-text-muted mt-2"># Ask anything</div>
              <div className="text-cortex-text-secondary">bridge.intelligence(</div>
              <div className="text-cortex-nominal pl-2">"What broke last week?"</div>
              <div className="text-cortex-text-secondary">)</div>
            </div>
          </div>

          {/* CLI */}
          <div className="p-6 rounded-xl bg-cortex-surface border border-cortex-border">
            <h3 className="text-lg font-semibold text-cortex-cyan mb-3 font-mono">CLI</h3>
            <p className="text-cortex-text-muted text-sm mb-4">
              Quick queries from your terminal. Pipe into scripts.
            </p>
            <div className="bg-cortex-bg rounded-lg p-3 font-mono text-xs text-cortex-text-secondary space-y-1">
              <div><span className="text-cortex-cyan">$</span> cortex intelligence "..."</div>
              <div><span className="text-cortex-cyan">$</span> cortex recommendations</div>
              <div><span className="text-cortex-cyan">$</span> cortex anomalies</div>
              <div><span className="text-cortex-cyan">$</span> cortex taskboard</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function Week1Section() {
  const timeline = [
    { day: 'Day 1', color: 'bg-cortex-processing', description: 'MCP tools work immediately. Track goals, manage tasks, query project state. Session hooks begin capturing context.' },
    { day: 'Day 3', color: 'bg-cortex-warning', description: 'Episodic memory kicks in. Cortex remembers what you worked on yesterday and surfaces it at session start.' },
    { day: 'Week 2', color: 'bg-cortex-cyan', description: 'Project-specific patterns accumulate. Cortex catches your codebase\'s unique gotchas — the imports, the config files, the flaky tests.' },
    { day: 'Month 2+', color: 'bg-cortex-nominal', description: 'Compound value. Cross-project transfer, personalized timing, high-confidence anomaly detection. Qualitatively different from a static CLAUDE.md.' },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Gets better every session
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Your model's weights are frozen. Cortex isn't. It compounds knowledge from every session — useful on day 1, transformative by month 2.
        </p>

        <div className="space-y-0">
          {timeline.map((item, i) => (
            <div key={item.day} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className={`w-3 h-3 rounded-full ${item.color} shrink-0 mt-1.5`} />
                {i < timeline.length - 1 && (
                  <div className="w-px h-full bg-cortex-border min-h-[60px]" />
                )}
              </div>
              <div className="pb-8">
                <div className="text-cortex-text-primary font-semibold font-mono text-sm">{item.day}</div>
                <p className="text-cortex-text-muted text-sm mt-1 leading-relaxed">{item.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function WhySeparateSection() {
  const reasons = [
    {
      icon: '👤',
      title: 'You own it',
      description: 'Vendor memory is the vendor\'s asset — stored on their servers, governed by their terms, deleted on their schedule. Cortex memory is your asset. Export it, move it, delete it, keep it forever. Your engineering DNA belongs to you.',
    },
    {
      icon: '🔄',
      title: 'Portable across models',
      description: 'Switch from Claude to GPT to Gemini — your memory travels with you. Vendor memory stays behind when you switch providers. Cortex is the continuity layer that no single vendor can provide.',
    },
    {
      icon: '🛡️',
      title: 'Independent verification',
      description: 'If the model holds your memory AND suggests actions, who checks the work? Cortex is a separate trust boundary — it catches model suggestions that historically caused problems, because it\'s not the one making the suggestions.',
    },
    {
      icon: '♾️',
      title: 'Survives vendor changes',
      description: 'Providers retrain, deprecate, change pricing, and sunset features. Your behavioral patterns accumulated over months shouldn\'t depend on a vendor\'s product roadmap. Cortex persists across any model lifecycle event.',
    },
    {
      icon: '🔍',
      title: 'Transparent and auditable',
      description: 'Vendor memory is opaque — you can\'t inspect, query, or prove what the model "remembers." Cortex gives you explicit, queryable, deletable records. You see exactly what it knows and why.',
    },
    {
      icon: '🤖',
      title: 'Shared across agents',
      description: 'The future is multiple AI agents working in parallel. No single vendor\'s memory covers what happened in a competitor\'s session. Cortex is the shared memory layer across all of them.',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Why you should own your AI&apos;s memory
        </h2>
        <p className="text-cortex-text-secondary text-center mb-4 max-w-2xl mx-auto">
          Models will ship native memory. But vendor memory is the vendor&apos;s asset —
          stored on their terms, locked to their platform, opaque by design.
          Cortex is memory <em>you</em> control.
        </p>
        <p className="text-cortex-text-muted text-center mb-12 max-w-2xl mx-auto text-sm">
          Run it on your laptop, a VM, or your team&apos;s private cloud.
          No accounts, no telemetry. The data is yours wherever it lives.
        </p>

        <div className="grid md:grid-cols-2 gap-5">
          {reasons.map((reason) => (
            <div
              key={reason.title}
              className="p-5 rounded-xl bg-cortex-surface border border-cortex-border hover:border-cortex-cyan/30 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="text-xl mt-0.5">{reason.icon}</div>
                <div>
                  <h3 className="text-cortex-text-primary font-semibold mb-1.5">{reason.title}</h3>
                  <p className="text-cortex-text-muted text-sm leading-relaxed">{reason.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-10 p-6 rounded-xl bg-cortex-cyan/5 border border-cortex-cyan/20 text-center">
          <p className="text-cortex-cyan font-medium text-lg mb-2">
            Vendor memory is rented. Cortex memory is owned.
          </p>
          <p className="text-cortex-text-muted text-sm">
            That difference compounds every session.
          </p>
        </div>
      </div>
    </section>
  )
}

function FutureProofSection() {
  const evolutions = [
    {
      letter: 'A',
      name: 'Behavioral Firewall',
      color: 'text-cortex-critical',
      border: 'border-cortex-critical/30',
      description: 'Cortex evolves from "gives agents memory" to "verifies agent behavior against your history." The model is powerful but uncautious about your specific patterns. Cortex catches model-suggested actions that historically cause problems.',
      example: '"The model suggested removing the migration — but last time, staging broke for 2 hours."',
    },
    {
      letter: 'B',
      name: 'Model Performance Router',
      color: 'text-cortex-warning',
      border: 'border-cortex-warning/30',
      description: 'Track which model + prompt pattern produces the best outcomes for your specific tasks. Auto-route to the best model based on your data. A personal performance database no vendor would provide.',
      example: '"For this refactor, use Claude. For this migration, use GPT. For test generation, use Gemini."',
    },
    {
      letter: 'C',
      name: 'Predictive Context Assembly',
      color: 'text-cortex-nominal',
      border: 'border-cortex-nominal/30',
      description: 'Before you even ask, pre-load the context you\'ll need based on time, branch, recent commits, and team activity. Model memory is reactive. Cortex is proactive.',
      example: '"It\'s Monday morning, you\'re on the checkout branch — here\'s what your team shipped over the weekend."',
    },
  ]

  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="text-3xl font-bold text-cortex-text-primary text-center mb-4">
          Where this goes next
        </h2>
        <p className="text-cortex-text-secondary text-center mb-12 max-w-2xl mx-auto">
          Memory is the foundation. These are the three evolution paths that compound on top of it.
        </p>

        <div className="space-y-5">
          {evolutions.map((evo) => (
            <div
              key={evo.letter}
              className={`p-6 rounded-xl bg-cortex-surface border ${evo.border} hover:bg-cortex-elevated transition-colors`}
            >
              <div className="flex items-start gap-4">
                <div className={`text-2xl font-bold ${evo.color} font-mono shrink-0 w-8`}>
                  {evo.letter}
                </div>
                <div>
                  <h3 className={`text-lg font-bold ${evo.color} mb-2`}>{evo.name}</h3>
                  <p className="text-cortex-text-secondary text-sm leading-relaxed mb-2">
                    {evo.description}
                  </p>
                  <p className="text-cortex-text-muted text-sm italic font-mono">
                    {evo.example}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function GetStartedSection() {
  return (
    <section className="py-20 px-6 border-t border-cortex-border">
      <div className="max-w-2xl mx-auto text-center">
        <h2 className="text-3xl font-bold text-cortex-text-primary mb-6">
          Get started in 60 seconds
        </h2>

        <div className="bg-cortex-surface border border-cortex-border rounded-xl p-6 text-left font-mono text-sm mb-8">
          <div className="text-cortex-text-muted mb-2"># Install</div>
          <div className="text-cortex-cyan mb-4">
            git clone https://github.com/jkempster34/cortex.git<br />
            cd cortex && pip install -e .
          </div>

          <div className="text-cortex-text-muted mb-2"># Try it</div>
          <div className="text-cortex-cyan mb-4">
            python cortex/bridge.py intelligence "What should I work on?"
          </div>

          <div className="text-cortex-text-muted mb-2"># Add to Claude Code (MCP)</div>
          <div className="text-cortex-text-secondary">
            Add cortex to your <span className="text-cortex-cyan">.mcp.json</span> — see README for config
          </div>
        </div>

        <p className="text-cortex-text-muted text-sm">
          Python 3.11+ required. Runs anywhere — laptop, VM, or private cloud.
          <br />
          Anthropic API key optional (for embeddings — falls back to keyword search without it).
        </p>

        <div className="mt-10 pt-8 border-t border-cortex-border">
          <p className="text-cortex-text-muted text-xs font-mono">
            Cortex &middot; Apache 2.0 &middot; March 2026
            <br />
            Built and validated across 6 projects, 18 months, 600+ tests.
          </p>
        </div>
      </div>
    </section>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cortex-bg">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-cortex-bg/80 backdrop-blur-md border-b border-cortex-border">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-cortex-cyan animate-pulse-slow" />
            <span className="font-display text-sm text-cortex-text-primary tracking-wider">CORTEX</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#demo" className="text-cortex-text-muted text-sm hover:text-cortex-text-secondary transition-colors">Demo</a>
            <a href="#get-started" className="text-cortex-text-muted text-sm hover:text-cortex-text-secondary transition-colors">Install</a>
            <a
              href="https://github.com/jkempster34/cortex"
              className="text-cortex-cyan text-sm font-mono hover:text-cortex-cyan/80 transition-colors"
            >
              GitHub &rarr;
            </a>
          </div>
        </div>
      </nav>

      <HeroSection />
      <ProblemSection />
      <WhatCortexAddsSection />
      <HowItWorksSection />
      <div id="demo">
        <DemoSection />
      </div>
      <MemoryTierSection />
      <Week1Section />
      <IntegrationSection />
      <WhySeparateSection />
      <FutureProofSection />
      <div id="get-started">
        <GetStartedSection />
      </div>
    </div>
  )
}
