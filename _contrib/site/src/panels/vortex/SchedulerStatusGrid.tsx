import { cn } from '@/utils/cn'
import type { SchedulerJob } from '@/types/vortex'

interface SchedulerStatusGridProps {
  jobs: SchedulerJob[]
}

const statusColors: Record<string, { bg: string; text: string }> = {
  success: { bg: 'bg-cortex-nominal/20', text: 'text-cortex-nominal' },
  failed: { bg: 'bg-cortex-critical/20', text: 'text-cortex-critical' },
  unknown: { bg: 'bg-cortex-border/50', text: 'text-cortex-text-muted' },
}

function formatTime(iso?: string): string {
  if (!iso) return '--:--'
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })
}

export function SchedulerStatusGrid({ jobs }: SchedulerStatusGridProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
      {jobs.map((job) => {
        const colors = statusColors[job.last_status] || statusColors.unknown!

        return (
          <div
            key={job.id}
            className={cn(
              'rounded-panel p-3 border border-cortex-border transition-colors',
              colors.bg,
              !job.enabled && 'opacity-40'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-display tracking-wider text-cortex-text-secondary truncate max-w-[75%]">
                {job.name.toUpperCase().replace(/_/g, ' ')}
              </span>
              <div className={cn(
                'w-2 h-2 rounded-full',
                job.last_status === 'success' ? 'bg-cortex-nominal' :
                job.last_status === 'failed' ? 'bg-cortex-critical' : 'bg-cortex-text-muted'
              )} />
            </div>
            <div className="flex items-center justify-between">
              <span className={cn('text-xs font-data', colors.text)}>
                {job.last_status.toUpperCase()}
              </span>
              <span className="text-[10px] font-data text-cortex-text-muted tabular-nums">
                {formatTime(job.last_run)}
              </span>
            </div>
            {job.next_run && (
              <div className="text-[9px] font-data text-cortex-text-muted mt-1">
                NEXT: {formatTime(job.next_run)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
