/**
 * Active Batch Card Component
 * Individual card showing running batch job with real-time metrics
 */

import { useEffect, useState } from 'react'
import { Card, ProgressRing, StatusBadge } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { cn } from '@/utils/cn'
import { formatDuration, calculateElapsedSeconds, calculateErrorRate } from '@/utils/calculations'
import type { EnrichedBatchStatus } from '@/types/batch'
import { useBatchStore } from '@/stores/batchStore'

interface ActiveBatchCardProps {
  batch: EnrichedBatchStatus
}

/**
 * Map batch status to StatusType for StatusBadge
 */
function mapBatchStatusToStatusType(status: string): 'PROCESSING' | 'QUEUED' | 'COMPLETED' | 'FAILED' | 'CANCELLED' {
  // Map API statuses to display statuses
  if (status === 'in_progress') return 'PROCESSING'
  if (status === 'validating' || status === 'finalizing') return 'PROCESSING'
  if (status === 'ended') return 'COMPLETED'
  return 'PROCESSING' // default fallback
}

/**
 * Get error rate color based on percentage
 */
function getErrorRateColor(errorRate: number): string {
  if (errorRate < 5) return colors.nominal
  if (errorRate < 10) return colors.warning
  return colors.critical
}

/**
 * Truncate batch ID for display
 */
function truncateBatchId(id: string): string {
  if (id.length <= 20) return id
  return `${id.slice(0, 20)}...`
}

export function ActiveBatchCard({ batch }: ActiveBatchCardProps) {
  const { selectedBatchId, setSelectedBatchId } = useBatchStore()
  const [elapsedSeconds, setElapsedSeconds] = useState(calculateElapsedSeconds(batch))

  const isSelected = selectedBatchId === batch.id
  const errorRate = calculateErrorRate(batch)
  const errorRateColor = getErrorRateColor(errorRate)

  // Update elapsed time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(calculateElapsedSeconds(batch))
    }, 1000)

    return () => clearInterval(interval)
  }, [batch])

  const handleClick = () => {
    setSelectedBatchId(batch.id)
  }

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-300 hover:border-cortex-accent',
        isSelected && 'border-cortex-accent shadow-elevated'
      )}
      onClick={handleClick}
    >
      {/* Header with ID and status */}
      <div className="flex items-center justify-between mb-4">
        <span
          className="font-mono text-sm text-cortex-text-primary truncate"
          title={batch.id}
        >
          {truncateBatchId(batch.id)}
        </span>
        <StatusBadge status={mapBatchStatusToStatusType(batch.status)} />
      </div>

      {/* Progress ring and counters */}
      <div className="flex items-center gap-6 mb-4">
        <ProgressRing
          progress={batch.progress_percentage / 100}
          size={80}
          strokeWidth={6}
          color={colors.processing}
        />

        <div className="flex-1 font-mono text-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-cortex-text-secondary">Processing:</span>
            <span className="text-cortex-text-primary font-semibold">
              {batch.request_counts.processing}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-cortex-text-secondary">Succeeded:</span>
            <span className="text-cortex-text-primary font-semibold">
              {batch.request_counts.succeeded}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-cortex-text-secondary">Errored:</span>
            <span
              className="font-semibold"
              style={{ color: batch.request_counts.errored > 0 ? colors.critical : colors.textPrimary }}
            >
              {batch.request_counts.errored}
            </span>
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div className="flex items-center justify-between font-mono text-xs text-cortex-text-secondary mb-3">
        <span>Elapsed: {formatDuration(elapsedSeconds)}</span>
        <span>Rate: {batch.requests_per_second} req/s</span>
      </div>

      {/* Error rate bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between font-mono text-xs">
          <span className="text-cortex-text-secondary">Error Rate:</span>
          <span style={{ color: errorRateColor }} className="font-semibold">
            {errorRate.toFixed(1)}%
          </span>
        </div>
        <div className="w-full h-1.5 bg-cortex-surface rounded-full overflow-hidden">
          <div
            className="h-full transition-all duration-300 rounded-full"
            style={{
              width: `${Math.min(errorRate * 10, 100)}%`,
              backgroundColor: errorRateColor,
            }}
          />
        </div>
      </div>
    </Card>
  )
}
