import { cn } from '@/utils/cn'

interface SuccessRateGaugeProps {
  rate: number // 0-100
  label?: string
}

export function SuccessRateGauge({ rate, label = 'Success Rate' }: SuccessRateGaugeProps) {
  const circumference = 2 * Math.PI * 40 // radius 40
  const offset = circumference - (rate / 100) * circumference

  const color =
    rate >= 90 ? 'text-cortex-nominal' :
    rate >= 70 ? 'text-cortex-warning' : 'text-cortex-critical'

  const strokeColor =
    rate >= 90 ? '#10B981' :
    rate >= 70 ? '#F59E0B' : '#EF4444'

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" stroke="#2A2D3A" strokeWidth="6" fill="none" />
          <circle
            cx="50"
            cy="50"
            r="40"
            stroke={strokeColor}
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn('text-lg font-display font-bold tabular-nums', color)}>
            {Math.round(rate)}%
          </span>
        </div>
      </div>
      <span className="mt-2 text-xs font-data text-cortex-text-muted tracking-wider">{label}</span>
    </div>
  )
}
