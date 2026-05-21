/**
 * Status Bar Component
 * Top status bar showing system health, connection status, time, and cost savings
 */

import { useState, useEffect } from 'react'
import { colors } from '@/design-system/tokens'
import { useHealthQuery, useMetricsQuery } from '@/api/hooks'
import { formatCost } from '@/utils/formatters'
import { cn } from '@/utils/cn'

export function StatusBar() {
  const [currentTime, setCurrentTime] = useState(new Date())
  const { data: healthData } = useHealthQuery()
  const { data: metricsData } = useMetricsQuery(7) // Last 7 days

  // Update time every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const isHealthy = healthData?.status === 'healthy'
  const statusColor = isHealthy ? colors.nominal : colors.critical
  const statusText = isHealthy ? 'NOMINAL' : 'DEGRADED'

  const totalSavings = metricsData?.cost_estimate?.savings ?? 0
  const apiConnected = healthData !== undefined

  const formatUTCTime = (date: Date): string => {
    return date.toISOString().substr(11, 8)
  }

  return (
    <div
      className="flex items-center justify-between px-6 py-3 font-mono text-sm"
      style={{ backgroundColor: colors.surface }}
    >
      {/* Left - System Health */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isHealthy ? 'animate-pulse' : 'animate-none'
            )}
            style={{ backgroundColor: statusColor }}
          />
          <span style={{ color: statusColor }} className="font-semibold">
            {statusText}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span style={{ color: colors.textSecondary }}>API:</span>
          <span
            style={{ color: apiConnected ? colors.nominal : colors.critical }}
            className="font-semibold"
          >
            {apiConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Center - Title */}
      <div className="flex-1 text-center">
        <h1
          className="text-base font-bold tracking-wider"
          style={{ color: colors.textPrimary }}
        >
          CORTEX COMMAND CENTER
        </h1>
      </div>

      {/* Right - Time & Savings */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span style={{ color: colors.textSecondary }}>UTC</span>
          <span style={{ color: colors.textPrimary }} className="font-semibold tabular-nums">
            {formatUTCTime(currentTime)}
          </span>
        </div>

        {totalSavings > 0 && (
          <div
            className="px-3 py-1 rounded font-semibold"
            style={{
              backgroundColor: colors.nominalMuted,
              color: colors.nominal,
            }}
          >
            {formatCost(totalSavings)} saved
          </div>
        )}
      </div>
    </div>
  )
}
