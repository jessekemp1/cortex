import { useState, useEffect } from 'react'
import { cn } from '@/utils/cn'

interface TimeDisplayProps {
  className?: string
  showDate?: boolean
}

export function TimeDisplay({ className, showDate = false }: TimeDisplayProps) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatUTC = (d: Date) => {
    const h = d.getUTCHours().toString().padStart(2, '0')
    const m = d.getUTCMinutes().toString().padStart(2, '0')
    const s = d.getUTCSeconds().toString().padStart(2, '0')
    return `${h}:${m}:${s}`
  }

  const formatDate = (d: Date) => {
    const y = d.getUTCFullYear()
    const m = (d.getUTCMonth() + 1).toString().padStart(2, '0')
    const day = d.getUTCDate().toString().padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  return (
    <div className={cn('flex items-center gap-2 font-data text-sm', className)}>
      <span className="text-cortex-text-muted">UTC</span>
      {showDate && <span className="text-cortex-text-secondary tabular-nums">{formatDate(now)}</span>}
      <span className="text-cortex-cyan font-semibold tabular-nums">{formatUTC(now)}</span>
    </div>
  )
}
