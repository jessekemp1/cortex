/**
 * Command Center Layout
 * Main 3-column responsive layout for the Cortex Batch Command Center
 *
 * Layout Structure:
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │                           STATUS BAR                                │
 * ├──────────────────┬────────────────────────┬─────────────────────────┤
 * │                  │                        │                         │
 * │  RUNNING PANEL   │    PENDING PANEL       │   COMPLETED PANEL       │
 * │  (Left - 25%)    │    (Center - 50%)      │   (Right - 25%)         │
 * │                  │                        │                         │
 * │                  │                        │                         │
 * ├──────────────────┴────────────────────────┴─────────────────────────┤
 * │                        BOTTOM ACTION BAR                            │
 * └─────────────────────────────────────────────────────────────────────┘
 */

import { type ReactNode } from 'react'
import { colors } from '@/design-system/tokens'

export interface CommandCenterLayoutProps {
  statusBar: ReactNode
  bottomBar: ReactNode
  children: [ReactNode, ReactNode, ReactNode] // [RunningPanel, PendingPanel, CompletedPanel]
}

export function CommandCenterLayout({
  statusBar,
  bottomBar,
  children,
}: CommandCenterLayoutProps) {
  const [runningPanel, pendingPanel, completedPanel] = children

  return (
    <div
      className="h-screen flex flex-col overflow-hidden font-sans"
      style={{ backgroundColor: colors.bg }}
    >
      {/* Status Bar - Fixed Top */}
      <div className="flex-none" style={{ borderBottom: `1px solid ${colors.border}` }}>
        {statusBar}
      </div>

      {/* Main Content - 3 Column Grid */}
      <div className="flex-1 overflow-hidden">
        <div className="grid grid-cols-1 lg:grid-cols-12 h-full gap-0">
          {/* Left Panel - Running (25%) */}
          <div
            className="lg:col-span-3 p-4 overflow-y-auto"
            style={{ borderRight: `1px solid ${colors.border}` }}
          >
            {runningPanel}
          </div>

          {/* Center Panel - Pending (50%) */}
          <div
            className="lg:col-span-6 p-4 overflow-y-auto"
            style={{ borderRight: `1px solid ${colors.border}` }}
          >
            {pendingPanel}
          </div>

          {/* Right Panel - Completed (25%) */}
          <div className="lg:col-span-3 p-4 overflow-y-auto">
            {completedPanel}
          </div>
        </div>
      </div>

      {/* Bottom Action Bar - Fixed Bottom */}
      <div className="flex-none" style={{ borderTop: `1px solid ${colors.border}` }}>
        {bottomBar}
      </div>
    </div>
  )
}
