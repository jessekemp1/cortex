import { cn } from '@/utils/cn'

export type Severity = 'CRITICAL' | 'WARNING' | 'INFO'

interface SeverityIndicatorProps {
  severity: Severity
  className?: string
  pulse?: boolean
}

const severityConfig: Record<Severity, { bg: string; text: string; border: string }> = {
  CRITICAL: {
    bg: 'bg-cortex-critical-muted',
    text: 'text-cortex-critical',
    border: 'border-cortex-critical/30',
  },
  WARNING: {
    bg: 'bg-cortex-warning-muted',
    text: 'text-cortex-warning',
    border: 'border-cortex-warning/30',
  },
  INFO: {
    bg: 'bg-cortex-processing-muted',
    text: 'text-cortex-processing',
    border: 'border-cortex-processing/30',
  },
}

export function SeverityIndicator({ severity, className, pulse = false }: SeverityIndicatorProps) {
  const config = severityConfig[severity]

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-display font-semibold tracking-wider rounded border',
        config.bg,
        config.text,
        config.border,
        pulse && severity === 'CRITICAL' && 'animate-pulse-fast',
        className
      )}
    >
      <span
        className={cn(
          'w-1.5 h-1.5 rounded-full',
          severity === 'CRITICAL' && 'bg-cortex-critical',
          severity === 'WARNING' && 'bg-cortex-warning',
          severity === 'INFO' && 'bg-cortex-processing'
        )}
      />
      {severity}
    </span>
  )
}
