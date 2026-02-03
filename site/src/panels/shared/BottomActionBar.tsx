/**
 * Bottom Action Bar Component
 * Bottom action bar with primary actions and last updated timestamp
 */

import { useState } from 'react'
import { Button } from '@/design-system/components'
import { colors } from '@/design-system/tokens'
import { formatRelativeTime } from '@/utils/formatters'

export function BottomActionBar() {
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now())

  const handleRefresh = () => {
    // Trigger refresh of all queries
    window.location.reload()
    setLastUpdated(Date.now())
  }

  const handleSubmitBatch = () => {
    // TODO: Open batch submission modal
    console.log('Submit new batch clicked')
  }

  const handleSettings = () => {
    // TODO: Open settings modal
    console.log('Settings clicked')
  }

  return (
    <div
      className="flex items-center justify-between px-6 py-3"
      style={{ backgroundColor: colors.surface }}
    >
      {/* Left - Primary Actions */}
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={handleSubmitBatch}>
          Submit New Batch
        </Button>
        <Button variant="secondary" onClick={handleRefresh}>
          Refresh All
        </Button>
        <Button variant="ghost" onClick={handleSettings}>
          Settings
        </Button>
      </div>

      {/* Right - Last Updated */}
      <div className="text-xs font-mono" style={{ color: colors.textSecondary }}>
        Last updated: <span style={{ color: colors.textPrimary }}>
          {formatRelativeTime(lastUpdated)}
        </span>
      </div>
    </div>
  )
}
