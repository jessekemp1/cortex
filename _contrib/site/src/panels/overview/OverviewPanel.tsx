import { SectionHeader } from '@/design-system/components'
import { SystemHealthGrid } from './SystemHealthGrid'
import { useHealthQuery, useAnomaliesQuery, useBatchesQuery, useMetricsQuery, useRecommendationsQuery } from '@/api/hooks'
import { formatCost } from '@/utils/formatters'
import { cn } from '@/utils/cn'

function MetricCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
      <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">{label}</div>
      <div className={cn('text-2xl font-display font-bold tabular-nums', color ?? 'text-cortex-cyan')}>
        {value}
      </div>
    </div>
  )
}

export default function OverviewPanel() {
  const { data: health } = useHealthQuery()
  const { data: anomalies } = useAnomaliesQuery()
  const { data: batches } = useBatchesQuery()
  const { data: metrics } = useMetricsQuery(7)
  const { data: recs } = useRecommendationsQuery()

  const isHealthy = health?.status === 'healthy'
  const anomalyCount = anomalies?.total ?? 0
  const activeBatches = batches?.filter(b => b.status !== 'ended').length ?? 0
  const savings = metrics?.cost_estimate?.savings ?? 0
  const topRecs = recs?.recommendations?.slice(0, 3) ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="System Overview" />

      {/* Row 1: Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          label="SYSTEM STATUS"
          value={isHealthy ? 'NOMINAL' : 'DEGRADED'}
          color={isHealthy ? 'text-cortex-nominal' : 'text-cortex-critical'}
        />
        <MetricCard
          label="ANOMALIES"
          value={anomalyCount}
          color={anomalyCount > 0 ? 'text-cortex-warning' : 'text-cortex-nominal'}
        />
        <MetricCard label="ACTIVE BATCHES" value={activeBatches} />
        <MetricCard label="COST SAVINGS (7D)" value={savings > 0 ? formatCost(savings) : '$0'} color="text-cortex-nominal" />
      </div>

      {/* Row 2: Project Health */}
      <div>
        <SectionHeader title="Project Health" count={5} />
        <SystemHealthGrid />
      </div>

      {/* Row 3: Recent Recommendations */}
      {topRecs.length > 0 && (
        <div>
          <SectionHeader title="Top Recommendations" count={topRecs.length} />
          <div className="space-y-2">
            {topRecs.map((rec) => (
              <div key={rec.id} className="bg-cortex-elevated border border-cortex-border rounded-panel p-3 border-l-[3px] border-l-cortex-ai-suggestion">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-1.5 py-0.5 text-[10px] font-display tracking-wider rounded bg-cortex-ai-suggestion-muted text-cortex-ai-suggestion">
                    {rec.priority}
                  </span>
                  <span className="text-xs font-data text-cortex-text-muted">{rec.project}</span>
                </div>
                <p className="text-sm text-cortex-text-primary">{rec.title}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
