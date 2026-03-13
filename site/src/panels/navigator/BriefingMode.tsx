import { useState } from 'react'
import { Card, SectionHeader } from '@/design-system/components'
import {
  useServiceHealthQuery,
  useRecommendationsQuery,
  usePredictionsQuery,
  useBatchesQuery,
  useAnomaliesQuery,
} from '@/api/hooks'
import { cn } from '@/utils/cn'

const DOMAIN_COLORS: Record<string, string> = {
  dev: 'bg-cortex-processing/20 text-cortex-processing',
  architecture: 'bg-cortex-ai-suggestion/20 text-cortex-ai-suggestion',
  product: 'bg-cortex-nominal/20 text-cortex-nominal',
  qa: 'bg-cortex-warning/20 text-cortex-warning',
  release: 'bg-cortex-critical/20 text-cortex-critical',
  research: 'bg-cortex-cyan/20 text-cortex-cyan',
}

export default function BriefingMode() {
  const { data: serviceHealth } = useServiceHealthQuery()
  const { data: recs } = useRecommendationsQuery()
  const { data: predictions } = usePredictionsQuery()
  const { data: batches } = useBatchesQuery(5)
  const { data: anomalies } = useAnomaliesQuery()

  const [accepted, setAccepted] = useState<Set<string>>(new Set())
  const [deferred, setDeferred] = useState<Set<string>>(new Set())

  const completedBatches = Array.isArray(batches)
    ? batches.filter((b) => b.status === 'ended').length
    : 0
  const failedBatches = Array.isArray(batches)
    ? batches.filter((b) => (b.request_counts?.errored ?? 0) > 0).length
    : 0
  const anomalyCount = anomalies?.total ?? 0

  const topPredictions = predictions?.predictions?.slice(0, 3) ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="MORNING BRIEFING" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Service Health */}
        <Card variant="accent" padding="md">
          <h3 className="font-data text-xs text-cortex-text-muted tracking-wider mb-3">
            SYSTEM HEALTH
          </h3>
          {serviceHealth && typeof serviceHealth === 'object' ? (
            <div className="space-y-1.5">
              {Object.entries(
                (serviceHealth as Record<string, unknown>).services as Record<string, unknown> ?? serviceHealth as Record<string, unknown>
              )
                .filter(([k]) => k !== 'timestamp' && k !== 'generated_at' && k !== 'overall')
                .map(([name, status]) => {
                  const svc = status as Record<string, unknown> | null
                  const isHealthy = svc?.status === 'healthy'
                  return (
                    <div key={name} className="flex items-center gap-2">
                      <div
                        className={cn(
                          'w-2 h-2 rounded-full',
                          isHealthy ? 'bg-cortex-nominal' : 'bg-cortex-critical'
                        )}
                      />
                      <span className="font-data text-xs text-cortex-text-secondary capitalize">
                        {name.replace(/_/g, ' ')}
                      </span>
                    </div>
                  )
                })}
            </div>
          ) : (
            <p className="font-data text-xs text-cortex-text-muted text-center py-4">
              Loading health data...
            </p>
          )}
        </Card>

        {/* Overnight */}
        <Card variant="accent" padding="md">
          <h3 className="font-data text-xs text-cortex-text-muted tracking-wider mb-3">
            OVERNIGHT
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-data text-xs text-cortex-text-secondary">
                Batches completed
              </span>
              <span className="font-data text-xs text-cortex-nominal font-bold">
                {completedBatches}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-data text-xs text-cortex-text-secondary">
                Batches with errors
              </span>
              <span
                className={cn(
                  'font-data text-xs font-bold',
                  failedBatches > 0 ? 'text-cortex-critical' : 'text-cortex-text-muted'
                )}
              >
                {failedBatches}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-data text-xs text-cortex-text-secondary">
                Anomalies detected
              </span>
              <span
                className={cn(
                  'font-data text-xs font-bold',
                  anomalyCount > 0 ? 'text-cortex-warning' : 'text-cortex-text-muted'
                )}
              >
                {anomalyCount}
              </span>
            </div>
            {anomalies && anomalies.by_severity && (
              <div className="pt-2 border-t border-cortex-border">
                <div className="flex items-center gap-3">
                  {Object.entries(anomalies.by_severity).map(([severity, count]) => (
                    <span
                      key={severity}
                      className={cn(
                        'font-data text-[10px]',
                        severity === 'CRITICAL'
                          ? 'text-cortex-critical'
                          : severity === 'WARNING'
                            ? 'text-cortex-warning'
                            : 'text-cortex-text-muted'
                      )}
                    >
                      {count} {severity}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Predictions Summary */}
        <Card variant="accent" padding="md">
          <h3 className="font-data text-xs text-cortex-text-muted tracking-wider mb-3">
            PREDICTIONS
          </h3>
          {topPredictions.length > 0 ? (
            <div className="space-y-2.5">
              {topPredictions.map((pred) => (
                <div key={pred.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'px-1.5 py-0.5 rounded text-[10px] font-data uppercase',
                        DOMAIN_COLORS[pred.domain] ?? 'bg-cortex-elevated text-cortex-text-muted'
                      )}
                    >
                      {pred.domain}
                    </span>
                    <span className="font-data text-[10px] text-cortex-text-muted ml-auto">
                      {Math.round(pred.confidence * 100)}%
                    </span>
                  </div>
                  <p className="font-data text-xs text-cortex-text-secondary leading-relaxed line-clamp-2">
                    {pred.prediction}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="font-data text-xs text-cortex-text-muted text-center py-4">
              No predictions available
            </p>
          )}
        </Card>
      </div>

      {/* Next Actions (full width) */}
      <Card variant="elevated" padding="md">
        <h3 className="font-data text-xs text-cortex-text-muted tracking-wider mb-3">
          RECOMMENDED ACTIONS
        </h3>
        <div className="space-y-2">
          {recs?.recommendations?.map((rec) => (
            <div
              key={rec.id}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded border transition-all',
                accepted.has(rec.id)
                  ? 'border-cortex-nominal/30 bg-cortex-nominal/5'
                  : deferred.has(rec.id)
                    ? 'border-cortex-border opacity-40'
                    : 'border-cortex-border'
              )}
            >
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded text-[10px] font-data shrink-0',
                  rec.priority === 'HIGH'
                    ? 'bg-cortex-critical/20 text-cortex-critical'
                    : rec.priority === 'MEDIUM'
                      ? 'bg-cortex-warning/20 text-cortex-warning'
                      : 'bg-cortex-processing/20 text-cortex-processing'
                )}
              >
                {rec.priority}
              </span>
              <span className="font-data text-xs text-cortex-text-primary flex-1">
                {rec.title}
              </span>
              {!accepted.has(rec.id) && !deferred.has(rec.id) && (
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => setAccepted(new Set([...accepted, rec.id]))}
                    className="px-2 py-0.5 rounded text-[10px] font-data bg-cortex-nominal/20 text-cortex-nominal hover:bg-cortex-nominal/30 transition-colors"
                  >
                    ACCEPT
                  </button>
                  <button
                    onClick={() => setDeferred(new Set([...deferred, rec.id]))}
                    className="px-2 py-0.5 rounded text-[10px] font-data bg-cortex-elevated text-cortex-text-muted hover:text-cortex-text-secondary transition-colors"
                  >
                    DEFER
                  </button>
                </div>
              )}
              {accepted.has(rec.id) && (
                <span className="font-data text-[10px] text-cortex-nominal shrink-0">
                  ACCEPTED
                </span>
              )}
              {deferred.has(rec.id) && (
                <span className="font-data text-[10px] text-cortex-text-muted shrink-0">
                  DEFERRED
                </span>
              )}
            </div>
          ))}
          {(!recs?.recommendations || recs.recommendations.length === 0) && (
            <p className="font-data text-xs text-cortex-text-muted text-center py-4">
              No pending actions
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}
