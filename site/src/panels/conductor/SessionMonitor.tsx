import { Card, SectionHeader } from '@/design-system/components'
import { cn } from '@/utils/cn'
import { useSessionsQuery } from '@/api/hooks'
import type { ConductorStartup } from '@/types/conductor'
import type { Session, SessionStatus } from '@/types/session'

interface SessionMonitorProps {
  data: ConductorStartup | undefined
  isLoading: boolean
}

const STATUS_BADGE_STYLES: Record<SessionStatus, string> = {
  ACTIVE: 'bg-cortex-nominal-muted text-cortex-nominal',
  WAITING: 'bg-cortex-cyan/10 text-cortex-cyan',
  IDLE: 'bg-cortex-warning-muted text-cortex-warning',
  STALE: 'bg-cortex-text-muted/10 text-cortex-text-muted',
}

const STATUS_DOT_STYLES: Record<SessionStatus, string> = {
  ACTIVE: 'bg-cortex-nominal',
  WAITING: 'bg-cortex-cyan',
  IDLE: 'bg-cortex-warning',
  STALE: 'bg-cortex-text-muted',
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

function formatModel(model: string): string {
  // Shorten model names for display: "claude-opus-4-..." -> "opus-4"
  if (model.includes('opus')) return model.replace('claude-', '').split('-').slice(0, 2).join('-')
  if (model.includes('sonnet')) return model.replace('claude-', '').split('-').slice(0, 2).join('-')
  if (model.includes('haiku')) return model.replace('claude-', '').split('-').slice(0, 2).join('-')
  return model.length > 16 ? model.slice(0, 14) + '..' : model
}

function ActiveSessionsSection() {
  const { data: sessionsData, isLoading: sessionsLoading, isError } = useSessionsQuery()

  const liveSessions: Session[] = (sessionsData?.sessions ?? []).filter(
    (s) => s.status === 'ACTIVE' || s.status === 'WAITING' || s.status === 'IDLE'
  )

  if (sessionsLoading) {
    return (
      <div>
        <SectionHeader title="Active Sessions" />
        <Card variant="elevated" padding="md">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
            <span className="font-data text-xs text-cortex-text-muted tracking-wider">POLLING SESSIONS</span>
          </div>
        </Card>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <SectionHeader title="Active Sessions" />
        <Card variant="elevated" padding="md">
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">SESSION API UNAVAILABLE</span>
        </Card>
      </div>
    )
  }

  if (liveSessions.length === 0) {
    return (
      <div>
        <SectionHeader title="Active Sessions" count={0} />
        <Card variant="elevated" padding="md">
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">NO ACTIVE SESSIONS</span>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <SectionHeader title="Active Sessions" count={liveSessions.length} />
      <div className="space-y-2">
        {liveSessions.map((session) => (
          <Card key={session.id} variant="elevated" padding="sm">
            <div className="flex items-center gap-3">
              {/* Status dot with pulse for ACTIVE */}
              <div className="relative flex-shrink-0">
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  STATUS_DOT_STYLES[session.status],
                )} />
                {session.status === 'ACTIVE' && (
                  <div className={cn(
                    'absolute inset-0 w-2 h-2 rounded-full animate-ping',
                    STATUS_DOT_STYLES[session.status],
                    'opacity-50',
                  )} />
                )}
              </div>

              {/* Status badge */}
              <span className={cn(
                'px-1.5 py-0.5 text-[10px] font-display tracking-wider rounded flex-shrink-0',
                STATUS_BADGE_STYLES[session.status],
              )}>
                {session.status}
              </span>

              {/* Project name */}
              <span className="font-data text-xs tracking-wider text-cortex-text-primary flex-shrink-0">
                {session.project.toUpperCase()}
              </span>

              {/* Branch */}
              <span className="font-data text-[10px] text-cortex-cyan truncate">
                {session.git_branch}
              </span>

              {/* Spacer */}
              <div className="flex-1" />

              {/* Last event */}
              <span className="font-data text-[10px] text-cortex-text-muted flex-shrink-0">
                {session.last_event_type}
              </span>
              <span className="font-data text-[10px] text-cortex-text-secondary flex-shrink-0">
                {formatAge(session.last_event_age_seconds)}
              </span>

              {/* Model */}
              <span className="font-data text-[10px] text-cortex-text-muted flex-shrink-0 hidden lg:inline">
                {formatModel(session.model)}
              </span>

              {/* Event count */}
              <span className="font-data text-[10px] text-cortex-text-muted flex-shrink-0">
                {session.event_count}ev
              </span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

export function SessionMonitor({ data, isLoading }: SessionMonitorProps) {
  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-cortex-cyan border-t-transparent rounded-full animate-spin" />
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">LOADING SESSION STATE</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Active Sessions (live polling) */}
      <ActiveSessionsSection />

      {/* Portfolio Health Grid */}
      <div>
        <SectionHeader title="Portfolio Health" count={data.projects.length} />
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {data.projects.map((proj) => (
            <Card key={proj.id} variant="elevated" padding="md">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-base">{proj.icon}</span>
                  <span className="font-data text-xs tracking-wider text-cortex-text-primary">
                    {proj.name.toUpperCase()}
                  </span>
                </div>
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  proj.uncommitted_files > 0 ? 'bg-cortex-warning' : 'bg-cortex-nominal'
                )} />
              </div>

              <div className="space-y-1.5">
                {proj.last_commit && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-data text-cortex-text-muted w-12">COMMIT</span>
                    <span className="text-xs font-data text-cortex-text-secondary truncate">
                      {proj.last_commit} {proj.last_commit_msg}
                    </span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-data text-cortex-text-muted w-12">DIRTY</span>
                  <span className={cn(
                    'text-xs font-data',
                    proj.uncommitted_files > 0 ? 'text-cortex-warning' : 'text-cortex-nominal'
                  )}>
                    {proj.uncommitted_files} files
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Git Overview */}
      <div>
        <SectionHeader title="Repository State" />
        <Card variant="accent" padding="md">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] font-data text-cortex-text-muted tracking-wider">BRANCH</span>
              <p className="text-lg font-data text-cortex-cyan mt-1">{data.git.branch}</p>
            </div>
            <div>
              <span className="text-[10px] font-data text-cortex-text-muted tracking-wider">CHANGED FILES</span>
              <p className={cn(
                'text-lg font-data mt-1',
                data.git.changed_files > 0 ? 'text-cortex-warning' : 'text-cortex-nominal'
              )}>
                {data.git.changed_files}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Active Alerts */}
      {data.alerts.length > 0 && (
        <div>
          <SectionHeader title="Active Alerts" count={data.alerts.length} />
          <div className="space-y-2">
            {data.alerts.map((alert, i) => (
              <Card key={i} variant="elevated" padding="sm">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'px-1.5 py-0.5 text-[10px] font-display tracking-wider rounded',
                    alert.severity === 'HIGH'
                      ? 'bg-cortex-critical-muted text-cortex-critical'
                      : alert.severity === 'MEDIUM'
                      ? 'bg-cortex-warning-muted text-cortex-warning'
                      : 'bg-cortex-processing-muted text-cortex-processing'
                  )}>
                    {alert.severity}
                  </span>
                  <span className="text-sm text-cortex-text-primary flex-1">{alert.message}</span>
                  <span className="text-[10px] font-data text-cortex-text-muted">{alert.type}</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Memory Snapshot */}
      {data.memory_snapshot && (
        <div>
          <SectionHeader title="Memory Snapshot" />
          <Card variant="elevated" padding="md">
            <pre className="text-xs text-cortex-text-secondary font-mono whitespace-pre-wrap max-h-48 overflow-y-auto scrollbar-thin">
              {data.memory_snapshot}
            </pre>
          </Card>
        </div>
      )}

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div>
          <SectionHeader title="Next Actions" count={data.recommendations.length} />
          <div className="space-y-2">
            {data.recommendations.map((rec, i) => (
              <Card key={i} variant="elevated" padding="sm" className="border-l-[3px] border-l-cortex-ai-suggestion">
                <div className="flex items-center gap-2">
                  <span className="px-1.5 py-0.5 text-[10px] font-display tracking-wider rounded bg-cortex-ai-suggestion-muted text-cortex-ai-suggestion">
                    {rec.priority}
                  </span>
                  <span className="text-sm text-cortex-text-primary">{rec.action}</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
