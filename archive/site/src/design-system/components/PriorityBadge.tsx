import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'
import { getPriorityColor, type PriorityLevel } from '../tokens'

export interface PriorityBadgeProps extends HTMLAttributes<HTMLDivElement> {
  priority: PriorityLevel
  showIcon?: boolean
}

/**
 * Priority badge for tactical command center
 * Color-coded priority levels: CRITICAL, HIGH, MEDIUM, LOW
 */
export const PriorityBadge = forwardRef<HTMLDivElement, PriorityBadgeProps>(
  ({ className, priority, showIcon = true, ...props }, ref) => {
    const color = getPriorityColor(priority)

    const priorityIcons: Record<PriorityLevel, string> = {
      CRITICAL: '⚠',
      HIGH: '▲',
      MEDIUM: '●',
      LOW: '▽',
    }

    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-semibold uppercase tracking-wider',
          'bg-cortex-elevated border',
          className
        )}
        style={{
          borderColor: color,
          color: color,
        }}
        {...props}
      >
        {showIcon && (
          <span className="text-sm" aria-hidden="true">
            {priorityIcons[priority]}
          </span>
        )}
        <span>{priority}</span>
      </div>
    )
  }
)

PriorityBadge.displayName = 'PriorityBadge'
