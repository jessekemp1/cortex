import { SectionHeader } from '@/design-system/components'
import { useAnomaliesQuery } from '@/api/hooks'
import { useAnomalyStore } from '@/stores/anomalyStore'
import { AnomalyCard } from './AnomalyCard'
import { AnomalySeverityBar } from './AnomalySeverityBar'
import type { Severity } from '@/design-system/components/SeverityIndicator'
import { cn } from '@/utils/cn'

const severities: (Severity | null)[] = [null, 'CRITICAL', 'WARNING', 'INFO']

export default function AnomalyPanel() {
  const { data, isLoading } = useAnomaliesQuery()
  const { severityFilter, setSeverityFilter } = useAnomalyStore()

  const anomalies = data?.anomalies ?? []
  const filtered = severityFilter
    ? anomalies.filter((a) => a.severity === severityFilter)
    : anomalies

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeader title="Anomaly Detection" count={anomalies.length} />

      {/* Severity breakdown chart */}
      {data?.by_severity && <AnomalySeverityBar bySeverity={data.by_severity} />}

      {/* Filter bar */}
      <div className="flex items-center gap-2">
        {severities.map((sev) => (
          <button
            key={sev ?? 'all'}
            onClick={() => setSeverityFilter(sev)}
            className={cn(
              'px-3 py-1.5 text-xs font-data rounded border transition-colors',
              severityFilter === sev
                ? 'bg-cortex-cyan-muted text-cortex-cyan border-cortex-cyan/30'
                : 'bg-cortex-surface text-cortex-text-secondary border-cortex-border hover:border-cortex-cyan/20'
            )}
          >
            {sev ?? 'ALL'}
          </button>
        ))}
      </div>

      {/* Anomaly list */}
      {isLoading ? (
        <div className="text-center py-8">
          <span className="font-data text-xs text-cortex-text-muted tracking-wider">SCANNING...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 bg-cortex-elevated rounded-panel border border-cortex-border">
          <span className="font-display text-sm text-cortex-nominal tracking-wider">ALL CLEAR</span>
          <p className="text-xs text-cortex-text-muted mt-1 font-data">No anomalies detected</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((anomaly) => (
            <AnomalyCard key={anomaly.id} anomaly={anomaly} />
          ))}
        </div>
      )}
    </div>
  )
}
