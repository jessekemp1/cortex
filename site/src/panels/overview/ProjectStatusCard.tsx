import { cn } from '@/utils/cn'
import type { ProjectStatus } from '@/types/cortex'

const statusColors: Record<string, { dot: string; text: string }> = {
  healthy: { dot: 'bg-cortex-nominal', text: 'text-cortex-nominal' },
  warning: { dot: 'bg-cortex-warning', text: 'text-cortex-warning' },
  critical: { dot: 'bg-cortex-critical', text: 'text-cortex-critical' },
  unknown: { dot: 'bg-cortex-text-muted', text: 'text-cortex-text-muted' },
}

interface ProjectStatusCardProps {
  project: ProjectStatus
}

export function ProjectStatusCard({ project }: ProjectStatusCardProps) {
  const colors = statusColors[project.status] || statusColors.unknown!

  return (
    <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4 hover:border-cortex-cyan/30 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-display text-xs font-semibold tracking-wider text-cortex-text-primary">
          {project.name.toUpperCase()}
        </h4>
        <div className="flex items-center gap-1.5">
          <div className={cn('w-2 h-2 rounded-full', colors.dot)} />
          <span className={cn('text-xs font-data', colors.text)}>
            {project.status.toUpperCase()}
          </span>
        </div>
      </div>
      {project.key_metric && (
        <div className="mt-2">
          <span className="text-xs text-cortex-text-muted font-data">{project.key_metric}</span>
          <span className="ml-2 text-sm font-data text-cortex-cyan font-semibold">
            {project.key_metric_value}
          </span>
        </div>
      )}
      <div className="mt-2 w-full bg-cortex-border/50 rounded-full h-1.5">
        <div
          className={cn('h-1.5 rounded-full', colors.dot)}
          style={{ width: `${Math.min(project.health_score, 100)}%` }}
        />
      </div>
    </div>
  )
}
