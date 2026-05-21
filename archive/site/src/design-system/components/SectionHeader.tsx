import { cn } from '@/utils/cn'

interface SectionHeaderProps {
  title: string
  count?: number
  className?: string
  actions?: React.ReactNode
}

export function SectionHeader({ title, count, className, actions }: SectionHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      <div className="flex items-center gap-3">
        <h2 className="font-display text-sm font-semibold tracking-[0.15em] uppercase text-cortex-text-primary">
          {title}
        </h2>
        {count !== undefined && (
          <span className="px-2 py-0.5 text-xs font-data font-medium rounded bg-cortex-cyan-muted text-cortex-cyan tabular-nums">
            {count}
          </span>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
