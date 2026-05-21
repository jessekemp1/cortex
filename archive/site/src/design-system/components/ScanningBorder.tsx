import { cn } from '@/utils/cn'

interface ScanningBorderProps {
  className?: string
  color?: string
}

export function ScanningBorder({ className, color }: ScanningBorderProps) {
  return (
    <div className={cn('relative overflow-hidden h-[2px]', className)}>
      <div
        className="absolute top-0 h-full w-[60px] bg-gradient-to-r from-transparent via-cortex-cyan to-transparent animate-scan"
        style={color ? { background: `linear-gradient(to right, transparent, ${color}, transparent)` } : undefined}
      />
      <div className="absolute inset-0 bg-cortex-border/30" />
    </div>
  )
}
