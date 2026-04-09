import { SectionHeader } from '@/design-system/components/SectionHeader'
import { useSessionsQuery } from '@/api/hooks'
import { useSessionStore } from '@/stores/sessionStore'
import { SessionCard } from './SessionCard'
import type { SessionStatus } from '@/types/session'
import { SESSION_STATUS_COLORS } from '@/types/session'

const STATUS_COLUMNS: SessionStatus[] = ['ACTIVE', 'WAITING', 'IDLE', 'STALE']

const COLUMN_DESCRIPTIONS: Record<SessionStatus, string> = {
  ACTIVE: 'Claude processing',
  WAITING: 'Needs your input',
  IDLE: 'Inactive 1-5 min',
  STALE: 'Inactive 5+ min',
}

export default function SessionPanel() {
  const { data, isLoading, error } = useSessionsQuery()
  const { statusFilter, setStatusFilter } = useSessionStore()

  const sessions = data?.sessions ?? []

  // Group sessions by status
  const grouped = STATUS_COLUMNS.reduce(
    (acc, status) => {
      acc[status] = sessions.filter((s) => s.status === status)
      return acc
    },
    {} as Record<SessionStatus, typeof sessions>
  )

  return (
    <div className="p-6 space-y-6">
      <SectionHeader
        title="Sessions"
        count={data?.active_count}
        actions={
          <div className="flex items-center gap-2">
            {STATUS_COLUMNS.map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(statusFilter === status ? null : status)}
                className={`px-2 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors ${
                  statusFilter === status
                    ? 'bg-cortex-elevated'
                    : 'bg-transparent border-transparent text-cortex-text-muted hover:text-cortex-text-secondary'
                }`}
                style={
                  statusFilter === status
                    ? { borderColor: SESSION_STATUS_COLORS[status], color: SESSION_STATUS_COLORS[status] }
                    : undefined
                }
              >
                {status}
              </button>
            ))}
          </div>
        }
      />

      {isLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="w-6 h-6 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="text-cortex-critical text-sm font-data p-4 bg-cortex-elevated rounded-panel border border-cortex-critical/30">
          Failed to load sessions: {error.message}
        </div>
      )}

      {!isLoading && !error && (
        <div className="grid grid-cols-4 gap-4">
          {STATUS_COLUMNS.filter((s) => !statusFilter || s === statusFilter).map((status) => (
            <div key={status} className="space-y-3">
              {/* Column header */}
              <div className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: SESSION_STATUS_COLORS[status] }}
                  />
                  <span className="text-[11px] font-display font-semibold tracking-[0.15em] uppercase text-cortex-text-secondary">
                    {status}
                  </span>
                </div>
                <span className="text-[10px] font-data text-cortex-text-muted tabular-nums">
                  {grouped[status].length}
                </span>
              </div>
              <p className="text-[10px] font-data text-cortex-text-muted px-1">
                {COLUMN_DESCRIPTIONS[status]}
              </p>

              {/* Cards */}
              <div className="space-y-2">
                {grouped[status].map((session) => (
                  <SessionCard key={session.id} session={session} />
                ))}
                {grouped[status].length === 0 && (
                  <div className="p-4 text-center text-[10px] font-data text-cortex-text-muted border border-dashed border-cortex-border rounded-panel">
                    No sessions
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
