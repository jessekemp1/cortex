import { Card, SectionHeader } from '@/design-system/components'
import { cn } from '@/utils/cn'
import type { ConductorStartup } from '@/types/conductor'

interface SessionMonitorProps {
  data: ConductorStartup | undefined
  isLoading: boolean
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
