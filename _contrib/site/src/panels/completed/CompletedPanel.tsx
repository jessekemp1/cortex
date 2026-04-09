/**
 * Completed Panel Component
 * Right panel showing completed batches with filtering options
 */

import { useState, useMemo } from 'react'
import { Card } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { useBatchesQuery, useMetricsQuery } from '@/api/hooks'
import { enrichBatchStatus } from '@/utils/calculations'
import { formatCost } from '@/utils/formatters'
import { CompletedJobCard } from './CompletedJobCard'
import type { EnrichedBatchStatus } from '@/types/batch'

type TimeFilter = 'today' | '7days' | '30days'

/**
 * Filter for only completed batches
 */
function filterCompletedBatches(batches: any[]): EnrichedBatchStatus[] {
  return batches
    .filter((b) => b.status === 'ended')
    .map(enrichBatchStatus)
}

/**
 * Filter batches by time period
 */
function filterByTime(batches: EnrichedBatchStatus[], filter: TimeFilter): EnrichedBatchStatus[] {
  const now = Date.now()
  const cutoffTimes = {
    today: now - 24 * 60 * 60 * 1000,
    '7days': now - 7 * 24 * 60 * 60 * 1000,
    '30days': now - 30 * 24 * 60 * 60 * 1000,
  }

  const cutoff = cutoffTimes[filter]
  return batches.filter((b) => {
    const endTime = b.ended_at ? new Date(b.ended_at).getTime() : 0
    return endTime >= cutoff
  })
}

export function CompletedPanel() {
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('7days')
  const { data: batchesData, isLoading, isError } = useBatchesQuery(100)
  const { data: metricsData } = useMetricsQuery(7)

  const completedBatches = useMemo(() => {
    if (!batchesData || !Array.isArray(batchesData)) return []
    const completed = filterCompletedBatches(batchesData)
    return filterByTime(completed, timeFilter)
  }, [batchesData, timeFilter])

  const todayCount = useMemo(() => {
    if (!batchesData || !Array.isArray(batchesData)) return 0
    const completed = filterCompletedBatches(batchesData)
    return filterByTime(completed, 'today').length
  }, [batchesData])

  // Calculate success rate
  const successRate = useMemo(() => {
    if (completedBatches.length === 0) return 100
    const total = completedBatches.reduce(
      (sum, b) => sum + b.request_counts.succeeded + b.request_counts.errored,
      0
    )
    const succeeded = completedBatches.reduce(
      (sum, b) => sum + b.request_counts.succeeded,
      0
    )
    return total > 0 ? (succeeded / total) * 100 : 100
  }, [completedBatches])

  const totalSavings = metricsData?.cost_estimate?.savings ?? 0

  const filterButtons: { value: TimeFilter; label: string }[] = [
    { value: 'today', label: 'Today' },
    { value: '7days', label: '7 Days' },
    { value: '30days', label: '30 Days' },
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Panel Header */}
      <Card className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold tracking-wide text-cortex-text-primary">
            COMPLETED
          </h2>
          <div
            className="px-3 py-1 rounded-full font-mono text-sm font-bold"
            style={{
              backgroundColor: colors.elevated,
              color: colors.nominal,
            }}
          >
            {todayCount}
          </div>
        </div>

        {/* Metrics */}
        <div className="space-y-3">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-cortex-text-secondary">SUCCESS RATE</span>
            <span
              className="font-semibold"
              style={{
                color: successRate >= 95 ? colors.nominal : successRate >= 80 ? colors.warning : colors.critical,
              }}
            >
              {successRate.toFixed(1)}%
            </span>
          </div>

          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-cortex-text-secondary">SAVINGS (7D)</span>
            <span className="font-semibold" style={{ color: colors.nominal }}>
              {formatCost(totalSavings)}
            </span>
          </div>
        </div>

        {/* Time Filter */}
        <div className="flex gap-2 mt-4">
          {filterButtons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => setTimeFilter(btn.value)}
              className="flex-1 px-2 py-1 text-xs font-mono font-semibold rounded transition-colors"
              style={{
                backgroundColor: timeFilter === btn.value ? colors.processing : colors.elevated,
                color: timeFilter === btn.value ? colors.textPrimary : colors.textSecondary,
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </Card>

      {/* Batch List */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="text-cortex-text-secondary font-mono text-sm animate-pulse">
              LOADING HISTORY...
            </div>
          </div>
        )}

        {isError && (
          <Card>
            <div className="text-center py-8">
              <div className="text-cortex-critical font-mono text-sm mb-2">
                CONNECTION FAILED
              </div>
              <div className="text-cortex-text-secondary text-xs">
                Unable to fetch batch history
              </div>
            </div>
          </Card>
        )}

        {!isLoading && !isError && completedBatches.length === 0 && (
          <Card>
            <div className="text-center py-12">
              <div className="text-6xl mb-4 opacity-20">✓</div>
              <div className="text-cortex-text-secondary font-mono text-sm font-semibold">
                NO COMPLETED BATCHES
              </div>
              <div className="text-cortex-text-muted text-xs mt-2">
                Completed batches will appear here
              </div>
            </div>
          </Card>
        )}

        {!isLoading && !isError && completedBatches.map((batch) => (
          <CompletedJobCard key={batch.id} batch={batch} />
        ))}
      </div>
    </div>
  )
}
