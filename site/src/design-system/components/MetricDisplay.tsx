import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/utils/cn'

export interface MetricDisplayProps extends HTMLAttributes<HTMLDivElement> {
  label: string
  value: string | number
  sublabel?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  color?: string
}

/**
 * Large metric display for command center dashboards
 * Shows primary value with label, optional trend, and icon
 */
export const MetricDisplay = forwardRef<HTMLDivElement, MetricDisplayProps>(
  ({
    className,
    label,
    value,
    sublabel,
    icon,
    trend,
    trendValue,
    color = '#F9FAFB',
    ...props
  }, ref) => {
    const trendColors = {
      up: '#10B981',     // cortex-nominal
      down: '#EF4444',   // cortex-critical
      neutral: '#9CA3AF', // cortex-text-secondary
    }

    const trendIcons = {
      up: '↑',
      down: '↓',
      neutral: '→',
    }

    return (
      <div
        ref={ref}
        className={cn('flex flex-col', className)}
        {...props}
      >
        {/* Label and Icon */}
        <div className="flex items-center gap-2 mb-2">
          {icon && <div className="text-cortex-text-secondary">{icon}</div>}
          <span className="text-sm font-medium text-cortex-text-secondary uppercase tracking-wide font-mono">
            {label}
          </span>
        </div>

        {/* Main Value */}
        <div className="flex items-baseline gap-3">
          <span
            className="text-4xl font-bold font-mono tabular-nums"
            style={{ color }}
          >
            {value}
          </span>

          {/* Trend Indicator */}
          {trend && trendValue && (
            <span
              className="text-sm font-medium font-mono"
              style={{ color: trendColors[trend] }}
            >
              {trendIcons[trend]} {trendValue}
            </span>
          )}
        </div>

        {/* Sublabel */}
        {sublabel && (
          <p className="text-xs text-cortex-text-muted mt-1 font-mono">
            {sublabel}
          </p>
        )}
      </div>
    )
  }
)

MetricDisplay.displayName = 'MetricDisplay'
