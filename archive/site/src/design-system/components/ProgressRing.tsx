import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

export interface ProgressRingProps extends HTMLAttributes<HTMLDivElement> {
  progress: number // 0-1
  size?: number // diameter in pixels
  strokeWidth?: number
  color?: string
  backgroundColor?: string
  showPercentage?: boolean
}

/**
 * SVG-based circular progress indicator
 * Clean, military-styled progress ring with optional percentage display
 */
export const ProgressRing = forwardRef<HTMLDivElement, ProgressRingProps>(
  ({
    className,
    progress,
    size = 80,
    strokeWidth = 6,
    color = '#3B82F6', // cortex-processing
    backgroundColor = '#2A2D3A', // cortex-border
    showPercentage = true,
    ...props
  }, ref) => {
    const normalizedProgress = Math.min(Math.max(progress, 0), 1)
    const radius = (size - strokeWidth) / 2
    const circumference = radius * 2 * Math.PI
    const offset = circumference - normalizedProgress * circumference

    const percentage = Math.round(normalizedProgress * 100)

    return (
      <div
        ref={ref}
        className={cn('relative inline-flex items-center justify-center', className)}
        style={{ width: size, height: size }}
        {...props}
      >
        {/* SVG Progress Ring */}
        <svg
          width={size}
          height={size}
          className="transform -rotate-90"
        >
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={backgroundColor}
            strokeWidth={strokeWidth}
            fill="none"
          />

          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
          />
        </svg>

        {/* Centered percentage text */}
        {showPercentage && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span
              className="font-mono font-semibold"
              style={{
                fontSize: size / 4,
                color: color,
              }}
            >
              {percentage}%
            </span>
          </div>
        )}
      </div>
    )
  }
)

ProgressRing.displayName = 'ProgressRing'
