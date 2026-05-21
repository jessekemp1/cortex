import { SeverityIndicator } from '@/design-system/components'
import type { Anomaly } from '@/types/cortex'

interface AnomalyCardProps {
  anomaly: Anomaly
}

export function AnomalyCard({ anomaly }: AnomalyCardProps) {
  return (
    <div className="bg-cortex-elevated border border-cortex-border rounded-panel p-4 hover:border-cortex-cyan/20 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <SeverityIndicator severity={anomaly.severity} pulse={anomaly.severity === 'CRITICAL'} />
        <span className="text-[10px] font-data text-cortex-text-muted">
          {new Date(anomaly.detected_at).toLocaleString('en-US', { hour12: false, timeZone: 'UTC' })}
        </span>
      </div>
      <h4 className="text-sm font-semibold text-cortex-text-primary mb-1">{anomaly.title}</h4>
      <p className="text-xs text-cortex-text-secondary leading-relaxed mb-2">{anomaly.description}</p>
      <div className="flex items-center gap-2">
        <span className="px-1.5 py-0.5 text-[10px] font-data rounded bg-cortex-surface text-cortex-text-muted border border-cortex-border">
          {anomaly.project}
        </span>
      </div>
      {anomaly.recommendation && (
        <div className="mt-2 pt-2 border-t border-cortex-border/50">
          <span className="text-[10px] font-display tracking-wider text-cortex-ai-suggestion">RECOMMENDATION</span>
          <p className="text-xs text-cortex-text-secondary mt-0.5">{anomaly.recommendation}</p>
        </div>
      )}
    </div>
  )
}
