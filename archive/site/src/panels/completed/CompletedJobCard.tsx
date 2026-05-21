/**
 * Completed Job Card Component
 * Collapsible card showing completed batch information
 */

import { useState } from 'react'
import { Card } from '@/design-system/components'
import { StatusBadge } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { formatTokens, formatDuration, formatDateTime } from '@/utils/formatters'
import type { EnrichedBatchStatus } from '@/types/batch'

export interface CompletedJobCardProps {
  batch: EnrichedBatchStatus
}

export function CompletedJobCard({ batch }: CompletedJobCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const succeeded = batch.request_counts.succeeded
  const errored = batch.request_counts.errored
  const total = succeeded + errored
  const successRate = total > 0 ? (succeeded / total) * 100 : 0

  const status = errored > 0 ? 'FAILED' : 'COMPLETED'
  const duration = batch.ended_at
    ? new Date(batch.ended_at).getTime() - new Date(batch.created_at).getTime()
    : 0

  const totalTokens = succeeded * 1000 // Rough estimate

  return (
    <Card
      className="cursor-pointer hover:bg-cortex-elevated transition-colors"
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-mono font-semibold"
            style={{ color: colors.textPrimary }}
          >
            {batch.id.slice(0, 12)}...
          </span>
          <StatusBadge status={status} />
        </div>

        <button
          className="text-xs font-mono hover:opacity-80 transition-opacity"
          style={{ color: colors.textSecondary }}
          onClick={(e) => {
            e.stopPropagation()
            setIsExpanded(!isExpanded)
          }}
        >
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div>
          <span style={{ color: colors.textSecondary }}>Success Rate</span>
          <div
            className="font-semibold"
            style={{
              color: successRate >= 95 ? colors.nominal : successRate >= 80 ? colors.warning : colors.critical,
            }}
          >
            {successRate.toFixed(1)}%
          </div>
        </div>

        <div>
          <span style={{ color: colors.textSecondary }}>Duration</span>
          <div style={{ color: colors.textPrimary }} className="font-semibold">
            {formatDuration(duration)}
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div
          className="mt-4 pt-4 space-y-2 text-xs font-mono"
          style={{ borderTop: `1px solid ${colors.border}` }}
        >
          <div className="flex justify-between">
            <span style={{ color: colors.textSecondary }}>Completed</span>
            <span style={{ color: colors.textPrimary }}>
              {batch.ended_at ? formatDateTime(new Date(batch.ended_at)) : 'N/A'}
            </span>
          </div>

          <div className="flex justify-between">
            <span style={{ color: colors.textSecondary }}>Tokens</span>
            <span style={{ color: colors.textPrimary }}>
              {formatTokens(totalTokens)}
            </span>
          </div>

          <div className="flex justify-between">
            <span style={{ color: colors.textSecondary }}>Succeeded</span>
            <span style={{ color: colors.nominal }}>{succeeded}</span>
          </div>

          {errored > 0 && (
            <div className="flex justify-between">
              <span style={{ color: colors.textSecondary }}>Errored</span>
              <span style={{ color: colors.critical }}>{errored}</span>
            </div>
          )}

          {/* Result Preview */}
          <div
            className="mt-3 p-2 rounded text-xs"
            style={{
              backgroundColor: colors.elevated,
              color: colors.textSecondary,
            }}
          >
            Batch ID: {batch.id}
          </div>
        </div>
      )}
    </Card>
  )
}
