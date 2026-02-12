import { SectionHeader } from '@/design-system/components'
import { useMetricsQuery, useBatchesQuery } from '@/api/hooks'
import { formatCost } from '@/utils/formatters'
import { CostSavingsChart } from './CostSavingsChart'
import { SuccessRateGauge } from './SuccessRateGauge'
import { cn } from '@/utils/cn'

function MetricCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4">
      <div className="text-xs font-data text-cortex-text-muted tracking-wider mb-1">{label}</div>
      <div className={cn('text-xl font-display font-bold tabular-nums', color ?? 'text-cortex-cyan')}>{value}</div>
      {sub && <div className="text-[10px] font-data text-cortex-text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

export default function MetricsPanel() {
  const { data: metrics } = useMetricsQuery(7)
  const { data: batches } = useBatchesQuery()

  const savings = metrics?.cost_estimate?.savings ?? 0
  const batchCost = metrics?.cost_estimate?.batch_actual ?? 0
  const realTimeCost = metrics?.cost_estimate?.real_time_would_be ?? 0
  const totalTasks = metrics?.total_tasks ?? 0
  const totalTokens = metrics?.total_tokens ?? 0

  const completedBatches = batches?.filter(b => b.status === 'ended') ?? []
  const successfulBatches = completedBatches.filter(b => b.request_counts.errored === 0)
  const successRate = completedBatches.length > 0
    ? (successfulBatches.length / completedBatches.length) * 100
    : 100

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="Operations Metrics" />

      {/* Key metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard label="TOTAL TASKS (7D)" value={String(totalTasks)} />
        <MetricCard label="TOKENS USED" value={totalTokens > 1_000_000 ? `${(totalTokens / 1_000_000).toFixed(1)}M` : String(totalTokens)} />
        <MetricCard label="BATCH COST" value={formatCost(batchCost)} />
        <MetricCard label="COST SAVINGS" value={formatCost(savings)} color="text-cortex-nominal" sub={realTimeCost > 0 ? `vs ${formatCost(realTimeCost)} real-time` : undefined} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-cortex-elevated border border-cortex-border rounded-panel p-4">
          <h3 className="font-display text-xs font-semibold tracking-[0.15em] text-cortex-text-secondary mb-3">
            CUMULATIVE SAVINGS
          </h3>
          <CostSavingsChart savings={savings} batchCost={batchCost} realTimeCost={realTimeCost} />
        </div>

        <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4 flex items-center justify-center">
          <SuccessRateGauge rate={successRate} />
        </div>
      </div>

      {/* By priority breakdown */}
      {metrics?.by_priority && Object.keys(metrics.by_priority).length > 0 && (
        <div>
          <SectionHeader title="Tasks by Priority" />
          <div className="flex gap-3">
            {Object.entries(metrics.by_priority).map(([priority, count]) => (
              <div key={priority} className="bg-cortex-elevated border border-cortex-border rounded-panel px-4 py-3 flex-1 text-center">
                <div className="text-xs font-display tracking-wider text-cortex-text-muted">{priority}</div>
                <div className="text-lg font-display font-bold text-cortex-text-primary tabular-nums mt-1">{count}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
