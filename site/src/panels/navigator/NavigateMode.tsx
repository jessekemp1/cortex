import { Card, SectionHeader } from '@/design-system/components'
import { usePredictionsQuery, useRecordDecisionMutation } from '@/api/hooks'
import type { Prediction } from '@/types/navigator'
import { cn } from '@/utils/cn'

// ── Domain Colors ──

const defaultDomain = { bg: 'bg-cortex-processing/20', text: 'text-cortex-processing', label: 'DEV' }

const domainColors: Record<string, { bg: string; text: string; label: string }> = {
  qa: { bg: 'bg-cortex-warning/20', text: 'text-cortex-warning', label: 'QA' },
  dev: { bg: 'bg-cortex-processing/20', text: 'text-cortex-processing', label: 'DEV' },
  architecture: { bg: 'bg-cortex-ai-suggestion/20', text: 'text-cortex-ai-suggestion', label: 'ARCH' },
  release: { bg: 'bg-cortex-nominal/20', text: 'text-cortex-nominal', label: 'RELEASE' },
  product: { bg: 'bg-cortex-cyan/20', text: 'text-cortex-cyan', label: 'PRODUCT' },
  research: { bg: 'bg-cortex-text-secondary/20', text: 'text-cortex-text-secondary', label: 'RESEARCH' },
}

// ── Inline Components ──

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 80
      ? 'text-cortex-nominal'
      : pct >= 60
        ? 'text-cortex-warning'
        : 'text-cortex-critical'

  return (
    <span className={cn('font-data text-sm font-bold', color)}>{pct}%</span>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const colors: Record<string, string> = {
    low: 'text-cortex-nominal bg-cortex-nominal/10 border-cortex-nominal/30',
    medium: 'text-cortex-warning bg-cortex-warning/10 border-cortex-warning/30',
    high: 'text-cortex-critical bg-cortex-critical/10 border-cortex-critical/30',
  }

  return (
    <span
      className={cn(
        'font-data text-[10px] px-1.5 py-0.5 rounded border',
        colors[risk] ?? colors.low,
      )}
    >
      {risk.toUpperCase()}
    </span>
  )
}

function PredictionCard({
  prediction,
  onAccept,
}: {
  prediction: Prediction
  onAccept: (scenarioName: string, scenarioLabel: string) => void
}) {
  const domain = domainColors[prediction.domain] ?? defaultDomain

  return (
    <Card variant="elevated" padding="md" className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          <span
            className={cn(
              'px-2 py-0.5 rounded text-[10px] font-data font-bold tracking-wider shrink-0',
              domain.bg,
              domain.text,
            )}
          >
            {domain.label}
          </span>
          <p className="text-sm text-cortex-text-primary font-mono leading-relaxed">
            {prediction.prediction}
          </p>
        </div>
        <ConfidenceBadge value={prediction.confidence} />
      </div>

      {/* Evidence */}
      {prediction.evidence.length > 0 && (
        <div className="pl-14 space-y-1">
          {prediction.evidence.map((e, i) => (
            <p key={i} className="font-data text-xs text-cortex-text-muted">
              {e}
            </p>
          ))}
        </div>
      )}

      {/* Scenarios */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
        {prediction.scenarios.map((s, i) => {
          const label = String.fromCharCode(65 + i)
          return (
            <div
              key={i}
              className="border border-cortex-border rounded-panel p-3 hover:border-cortex-cyan/40 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-data text-xs text-cortex-text-primary font-bold">
                  {label}: {s.name.replace(/^[A-C]:\s*/, '')}
                </span>
                <RiskBadge risk={s.risk} />
              </div>
              <p className="font-data text-[11px] text-cortex-text-secondary mb-3 leading-relaxed">
                {s.description}
              </p>
              <div className="flex items-center justify-between">
                <span className="font-data text-[10px] text-cortex-text-muted">
                  Effort: {s.effort}
                </span>
                <button
                  onClick={() => onAccept(s.name, label)}
                  className="px-3 py-1 rounded text-[10px] font-data tracking-wider bg-cortex-cyan-muted text-cortex-cyan hover:bg-cortex-cyan/20 transition-colors opacity-70 group-hover:opacity-100"
                >
                  ACCEPT {label}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

// ── Decision History Table ──

function DecisionHistory({ predictions }: { predictions: Prediction[] }) {
  // Derive recent decisions from predictions that have been acted on
  // For now, show a compact summary of available predictions as a reference table
  const decided = predictions.filter((p) => p.scenarios.length > 0)

  if (decided.length === 0) return null

  return (
    <div className="space-y-3">
      <SectionHeader title="DECISION LOG" />
      <Card variant="outlined" padding="none">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-cortex-border">
              <th className="font-data text-[10px] text-cortex-text-muted tracking-wider px-4 py-2">
                DOMAIN
              </th>
              <th className="font-data text-[10px] text-cortex-text-muted tracking-wider px-4 py-2">
                PREDICTION
              </th>
              <th className="font-data text-[10px] text-cortex-text-muted tracking-wider px-4 py-2">
                CONFIDENCE
              </th>
              <th className="font-data text-[10px] text-cortex-text-muted tracking-wider px-4 py-2">
                SCENARIOS
              </th>
            </tr>
          </thead>
          <tbody>
            {decided.map((p) => {
              const domain = domainColors[p.domain] ?? defaultDomain
              return (
                <tr
                  key={p.id}
                  className="border-b border-cortex-border/50 last:border-b-0 hover:bg-cortex-surface/50 transition-colors"
                >
                  <td className="px-4 py-2.5">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded text-[10px] font-data font-bold tracking-wider',
                        domain.bg,
                        domain.text,
                      )}
                    >
                      {domain.label}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-mono text-xs text-cortex-text-primary line-clamp-1">
                      {p.prediction}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <ConfidenceBadge value={p.confidence} />
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-data text-xs text-cortex-text-secondary">
                      {p.scenarios.length} option{p.scenarios.length !== 1 ? 's' : ''}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

// ── Main Component ──

export default function NavigateMode() {
  const { data, isLoading } = usePredictionsQuery()
  const recordDecision = useRecordDecisionMutation()

  const handleAccept = (
    prediction: Prediction,
    scenarioName: string,
    scenarioLabel: string,
  ) => {
    recordDecision.mutate({
      prediction_id: prediction.id,
      scenario_chosen: scenarioLabel,
      scenario_name: scenarioName,
      domain: prediction.domain,
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="font-data text-xs text-cortex-text-muted tracking-wider animate-pulse">
          GENERATING PREDICTIONS...
        </span>
      </div>
    )
  }

  const predictions = data?.predictions ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Active Predictions */}
      <div className="flex items-center justify-between">
        <SectionHeader title="ACTIVE PREDICTIONS" count={predictions.length} />
        <span className="font-data text-[10px] text-cortex-text-muted">
          Updated{' '}
          {data?.generated_at
            ? new Date(data.generated_at).toLocaleTimeString()
            : '\u2014'}
        </span>
      </div>

      {predictions.length === 0 ? (
        <Card variant="outlined" padding="lg">
          <div className="text-center">
            <p className="font-data text-sm text-cortex-text-muted">
              No active predictions
            </p>
            <p className="font-data text-xs text-cortex-text-muted mt-1">
              Predictions generate from git activity, batch queue, and outcome
              history
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {predictions.map((pred) => (
            <PredictionCard
              key={pred.id}
              prediction={pred}
              onAccept={(name, label) => handleAccept(pred, name, label)}
            />
          ))}
        </div>
      )}

      {/* Decision History */}
      <DecisionHistory predictions={predictions} />
    </div>
  )
}
