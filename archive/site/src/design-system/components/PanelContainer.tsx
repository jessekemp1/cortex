import { cn } from '@/utils/cn'
import { ScanningBorder } from './ScanningBorder'

interface PanelContainerProps {
  title: string
  count?: number
  children: React.ReactNode
  className?: string
  scanning?: boolean
  accent?: boolean
}

export function PanelContainer({
  title,
  count,
  children,
  className,
  scanning = false,
  accent = true,
}: PanelContainerProps) {
  return (
    <div
      className={cn(
        'bg-cortex-surface border border-cortex-border rounded-panel overflow-hidden',
        accent && 'border-l-[3px] border-l-cortex-cyan',
        className
      )}
    >
      {scanning && <ScanningBorder />}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display text-xs font-semibold tracking-[0.15em] uppercase text-cortex-text-secondary">
            {title}
          </h3>
          {count !== undefined && (
            <span className="px-2 py-0.5 text-xs font-data rounded bg-cortex-cyan-muted text-cortex-cyan tabular-nums">
              {count}
            </span>
          )}
        </div>
        {children}
      </div>
    </div>
  )
}
