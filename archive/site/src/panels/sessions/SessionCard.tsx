import { Card } from '@/design-system/components/Card'
import { ScanningBorder } from '@/design-system/components/ScanningBorder'
import { cn } from '@/utils/cn'
import type { Session, SessionStatus } from '@/types/session'
import { SESSION_STATUS_COLORS, SESSION_STATUS_PULSE } from '@/types/session'

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`
  return `${Math.round(seconds / 86400)}d ago`
}

function StatusDot({ status }: { status: SessionStatus }) {
  const color = SESSION_STATUS_COLORS[status]
  const shouldPulse = SESSION_STATUS_PULSE[status]

  return (
    <span className="relative flex h-2 w-2">
      {shouldPulse && (
        <span
          className="animate-pulse-fast absolute inline-flex h-full w-full rounded-full opacity-75"
          style={{ backgroundColor: color }}
        />
      )}
      <span
        className="relative inline-flex rounded-full h-2 w-2"
        style={{ backgroundColor: color }}
      />
    </span>
  )
}

interface SessionCardProps {
  session: Session
}

export function SessionCard({ session }: SessionCardProps) {
  const color = SESSION_STATUS_COLORS[session.status]
  const isActive = session.status === 'ACTIVE'

  return (
    <Card variant="default" padding="none" className="overflow-hidden">
      {isActive && <ScanningBorder color={color} />}
      <div className="p-3">
        {/* Header: project + status */}
        <div className="flex items-center justify-between mb-2">
          <span className="font-data text-sm text-cortex-text-primary truncate">
            {session.project}
          </span>
          <div
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase tracking-wider bg-cortex-elevated border"
            style={{ borderColor: color, color }}
          >
            <StatusDot status={session.status} />
            {session.status}
          </div>
        </div>

        {/* Branch */}
        {session.git_branch && (
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-cortex-text-muted text-[10px] font-data">BRANCH</span>
            <span className="text-cortex-cyan text-xs font-mono truncate">{session.git_branch}</span>
          </div>
        )}

        {/* Meta row */}
        <div className="flex items-center justify-between text-[10px] text-cortex-text-muted font-data">
          <span className={cn('tabular-nums', isActive && 'text-cortex-nominal')}>
            {formatAge(session.last_event_age_seconds)}
          </span>
          <span className="tabular-nums">{session.event_count} events</span>
          {session.model && (
            <span className="truncate max-w-[80px]">{session.model.replace('claude-', '').replace('-4-6', '')}</span>
          )}
        </div>
      </div>
    </Card>
  )
}
