import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'
import { getStatusColor, isActiveStatus, type StatusType } from '../tokens'

export interface StatusBadgeProps extends HTMLAttributes<HTMLDivElement> {
  status: StatusType
  showPulse?: boolean
}

/**
 * Status badge with optional pulse animation for active states
 * Military command center style with status color coding
 */
export const StatusBadge = forwardRef<HTMLDivElement, StatusBadgeProps>(
  ({ className, status, showPulse = true, ...props }, ref) => {
    const color = getStatusColor(status)
    const shouldPulse = showPulse && isActiveStatus(status)

    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center gap-2 px-2.5 py-1 rounded text-xs font-mono font-medium uppercase tracking-wide',
          'bg-cortex-elevated border',
          className
        )}
        style={{
          borderColor: color,
          color: color,
        }}
        {...props}
      >
        {/* Status indicator dot with optional pulse */}
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

        {/* Status text */}
        <span>{status}</span>
      </div>
    )
  }
)

StatusBadge.displayName = 'StatusBadge'
