import { SectionHeader, Card } from '@/design-system/components'
import { useServicesStatusQuery, useAnomaliesQuery } from '@/api/hooks'
import { cn } from '@/utils/cn'
import type { LaunchdService, CronJob, HealthCheck } from '@/types/navigator'

export default function MonitorMode() {
  const { data: services, isLoading } = useServicesStatusQuery()
  const { data: anomalies } = useAnomaliesQuery()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="font-data text-xs text-cortex-text-muted tracking-wider animate-pulse">
          SCANNING SERVICES...
        </span>
      </div>
    )
  }

  const launchdCount = services?.launchd?.length ?? 0
  const cronCount = services?.cron?.length ?? 0
  const healthCount = services?.health?.length ?? 0
  const recentAnomalies = anomalies?.anomalies?.filter((a) => !a.resolved).slice(0, 5) ?? []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Summary line */}
      <div className="flex items-center gap-2">
        <span className="font-data text-xs text-cortex-text-muted tracking-wide">
          {launchdCount} agents &middot; {cronCount} cron &middot; {healthCount} endpoints
        </span>
        {services?.timestamp && (
          <span className="font-data text-[10px] text-cortex-text-muted ml-auto">
            {new Date(services.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Health Check Bar */}
      <section>
        <SectionHeader title="HEALTH CHECKS" count={healthCount} />
        <div className="flex flex-wrap gap-3">
          {services?.health?.map((h: HealthCheck) => (
            <div
              key={h.name}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-panel border',
                h.healthy
                  ? 'border-cortex-nominal/30 bg-cortex-nominal/10'
                  : 'border-cortex-critical/30 bg-cortex-critical/10'
              )}
            >
              <div
                className={cn(
                  'w-2 h-2 rounded-full',
                  h.healthy
                    ? 'bg-cortex-nominal animate-pulse-slow'
                    : 'bg-cortex-critical animate-pulse-fast'
                )}
              />
              <span className="font-data text-xs text-cortex-text-primary">{h.name}</span>
              {h.healthy && h.latency_ms != null && (
                <span className="font-data text-[10px] text-cortex-text-muted">
                  {h.latency_ms}ms
                </span>
              )}
              {!h.healthy && (
                <span className="font-data text-[10px] text-cortex-critical">
                  {h.status ?? 'DOWN'}
                </span>
              )}
            </div>
          ))}
          {healthCount === 0 && (
            <span className="font-data text-xs text-cortex-text-muted">No endpoints configured</span>
          )}
        </div>
      </section>

      {/* LaunchAgent Grid */}
      <section>
        <SectionHeader title="LAUNCH AGENTS" count={launchdCount} />
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {services?.launchd?.map((svc: LaunchdService) => {
            const isRunning = svc.healthy && svc.pid != null
            return (
              <Card key={svc.label} variant="elevated" padding="sm">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full flex-shrink-0',
                      isRunning ? 'bg-cortex-nominal' : 'bg-cortex-text-muted'
                    )}
                  />
                  <span className="font-data text-xs text-cortex-text-primary truncate">
                    {svc.label.replace(/^com\.(cortex|vortex|alphaarena)\./, '')}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-3">
                  <span className="font-data text-[10px] text-cortex-text-muted">
                    PID: {svc.pid ?? '\u2014'}
                  </span>
                  <span
                    className={cn(
                      'font-data text-[10px]',
                      isRunning ? 'text-cortex-nominal' : 'text-cortex-text-muted'
                    )}
                  >
                    {isRunning ? 'RUNNING' : 'STOPPED'}
                  </span>
                  {svc.status !== 0 && !isRunning && (
                    <span className="font-data text-[10px] text-cortex-warning">
                      exit {svc.status}
                    </span>
                  )}
                </div>
              </Card>
            )
          })}
          {launchdCount === 0 && (
            <span className="font-data text-xs text-cortex-text-muted col-span-full">
              No LaunchAgents detected
            </span>
          )}
        </div>
      </section>

      {/* Cron Table */}
      <section>
        <SectionHeader title="CRON JOBS" count={cronCount} />
        <Card variant="default" padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-cortex-border">
                  <th className="font-data text-[10px] text-cortex-text-muted tracking-wider py-2 px-3 uppercase">
                    Schedule
                  </th>
                  <th className="font-data text-[10px] text-cortex-text-muted tracking-wider py-2 px-3 uppercase">
                    Command
                  </th>
                  <th className="font-data text-[10px] text-cortex-text-muted tracking-wider py-2 px-3 uppercase">
                    Project
                  </th>
                </tr>
              </thead>
              <tbody>
                {services?.cron?.map((job: CronJob, i: number) => (
                  <tr
                    key={`${job.schedule}-${job.command}-${i}`}
                    className="border-b border-cortex-border/50 hover:bg-cortex-elevated/50 transition-colors"
                  >
                    <td className="font-mono text-xs text-cortex-cyan py-2 px-3 whitespace-nowrap">
                      {job.schedule}
                    </td>
                    <td className="font-data text-xs text-cortex-text-secondary py-2 px-3 truncate max-w-xs">
                      {job.command}
                    </td>
                    <td className="font-data text-xs text-cortex-text-muted py-2 px-3">
                      {job.project}
                    </td>
                  </tr>
                ))}
                {cronCount === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="font-data text-xs text-cortex-text-muted py-4 px-3 text-center"
                    >
                      No cron jobs configured
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* Alert Feed */}
      {recentAnomalies.length > 0 && (
        <section>
          <SectionHeader title="RECENT ALERTS" count={recentAnomalies.length} />
          <Card variant="default" padding="sm">
            <div className="space-y-0.5">
              {recentAnomalies.map((a) => (
                <div key={a.id} className="flex items-center gap-2 py-1.5">
                  <span
                    className={cn(
                      'w-1.5 h-1.5 rounded-full flex-shrink-0',
                      a.severity === 'CRITICAL'
                        ? 'bg-cortex-critical'
                        : a.severity === 'WARNING'
                          ? 'bg-cortex-warning'
                          : 'bg-cortex-processing'
                    )}
                  />
                  <span className="font-data text-xs text-cortex-text-secondary truncate">
                    {a.title}
                  </span>
                  <span className="font-data text-[10px] text-cortex-text-muted ml-auto whitespace-nowrap flex-shrink-0">
                    {new Date(a.detected_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}
    </div>
  )
}
