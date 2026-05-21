/**
 * Running Panel Component
 * Left panel showing active batch operations with real-time status
 */

import { useMemo } from 'react'
import { Card } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { useBatchesQuery } from '@/api/hooks'
import { enrichBatchStatus } from '@/utils/calculations'
import { ActiveBatchCard } from './ActiveBatchCard'
import type { EnrichedBatchStatus } from '@/types/batch'

const MAX_BATCH_SLOTS = 5

/**
 * Filter for only active batches (in_progress, validating, finalizing)
 */
function filterActiveBatches(batches: any[]): EnrichedBatchStatus[] {
  return batches
    .filter((b) => b.status !== 'ended')
    .map(enrichBatchStatus)
}

export function RunningPanel() {
  const { data: batchesData, isLoading, isError } = useBatchesQuery(20)

  const activeBatches = useMemo(() => {
    if (!batchesData || !Array.isArray(batchesData)) return []
    return filterActiveBatches(batchesData)
  }, [batchesData])

  const activeCount = activeBatches.length
  const capacityPercentage = (activeCount / MAX_BATCH_SLOTS) * 100

  /**
   * Get capacity bar color based on usage
   */
  const getCapacityColor = () => {
    if (capacityPercentage >= 80) return colors.critical
    if (capacityPercentage >= 60) return colors.warning
    return colors.nominal
  }

  return (
    <div className="flex flex-col h-full">
      {/* Panel Header */}
      <Card className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold tracking-wide text-cortex-text-primary">
            ACTIVE OPERATIONS
          </h2>
          <div
            className="px-3 py-1 rounded-full font-mono text-sm font-bold"
            style={{
              backgroundColor: colors.elevated,
              color: activeCount > 0 ? colors.processing : colors.textSecondary,
            }}
          >
            {activeCount}
          </div>
        </div>

        {/* Capacity Indicator */}
        <div className="space-y-2">
          <div className="flex items-center justify-between font-mono text-xs">
            <span className="text-cortex-text-secondary">CAPACITY</span>
            <span className="text-cortex-text-primary font-semibold">
              {activeCount}/{MAX_BATCH_SLOTS}
            </span>
          </div>
          <div className="w-full h-2 bg-cortex-surface rounded-full overflow-hidden">
            <div
              className="h-full transition-all duration-500 rounded-full"
              style={{
                width: `${capacityPercentage}%`,
                backgroundColor: getCapacityColor(),
              }}
            />
          </div>
        </div>
      </Card>

      {/* Batch List */}
      <div className="flex-1 overflow-y-auto space-y-3">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="text-cortex-text-secondary font-mono text-sm animate-pulse">
              LOADING OPERATIONS...
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
                Unable to fetch batch status
              </div>
            </div>
          </Card>
        )}

        {!isLoading && !isError && activeCount === 0 && (
          <Card>
            <div className="text-center py-12">
              <div className="text-6xl mb-4 opacity-20">⚙️</div>
              <div className="text-cortex-text-secondary font-mono text-sm font-semibold">
                NO ACTIVE BATCHES
              </div>
              <div className="text-cortex-text-muted text-xs mt-2">
                Queue is clear - ready for operations
              </div>
            </div>
          </Card>
        )}

        {!isLoading && !isError && activeBatches.map((batch) => (
          <ActiveBatchCard key={batch.id} batch={batch} />
        ))}
      </div>
    </div>
  )
}
