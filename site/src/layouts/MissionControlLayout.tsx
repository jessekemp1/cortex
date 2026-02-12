import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/panels/shared/Sidebar'
import { ScanningBorder } from '@/design-system/components/ScanningBorder'
import { TimeDisplay } from '@/design-system/components/TimeDisplay'
import { useHealthQuery, useMetricsQuery } from '@/api/hooks'
import { formatCost } from '@/utils/formatters'

export function MissionControlLayout() {
  const { data: health } = useHealthQuery()
  const { data: metrics } = useMetricsQuery(7)

  const isHealthy = health?.status === 'healthy'
  const savings = metrics?.cost_estimate?.savings ?? 0

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-cortex-bg">
      {/* Status Bar — top */}
      <header className="flex-none border-b border-cortex-border">
        <ScanningBorder />
        <div className="flex items-center justify-between px-4 py-2">
          {/* Left: status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-cortex-nominal animate-pulse-slow' : 'bg-cortex-critical animate-pulse-fast'}`} />
              <span className={`font-data text-xs tracking-wider ${isHealthy ? 'text-cortex-nominal' : 'text-cortex-critical'}`}>
                {isHealthy ? 'NOMINAL' : 'DEGRADED'}
              </span>
            </div>
            <span className="text-cortex-text-muted text-xs font-data">|</span>
            <span className="text-cortex-text-secondary text-xs font-data">
              API: <span className={health ? 'text-cortex-nominal' : 'text-cortex-critical'}>
                {health ? 'CONNECTED' : 'OFFLINE'}
              </span>
            </span>
          </div>

          {/* Center: title */}
          <h1 className="font-display text-sm font-semibold tracking-[0.25em] text-cortex-text-primary">
            CORTEX MISSION CONTROL
          </h1>

          {/* Right: time + savings */}
          <div className="flex items-center gap-4">
            {savings > 0 && (
              <span className="px-2 py-0.5 text-xs font-data rounded bg-cortex-nominal-muted text-cortex-nominal">
                {formatCost(savings)} SAVED
              </span>
            )}
            <TimeDisplay />
          </div>
        </div>
      </header>

      {/* Main: Sidebar + Content */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
