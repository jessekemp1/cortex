import { cn } from '@/utils/cn'
import type { ModelPerformance } from '@/types/vortex'

interface ModelPerformanceTableProps {
  models: ModelPerformance[]
}

const statusBadge: Record<string, { bg: string; text: string }> = {
  pass: { bg: 'bg-cortex-nominal-muted', text: 'text-cortex-nominal' },
  fail: { bg: 'bg-cortex-critical-muted', text: 'text-cortex-critical' },
  insufficient_data: { bg: 'bg-cortex-border/50', text: 'text-cortex-text-muted' },
}

export function ModelPerformanceTable({ models }: ModelPerformanceTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-data">
        <thead>
          <tr className="border-b border-cortex-border">
            <th className="text-left py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">MODEL</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">MAE (kt)</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">BIAS</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">DRIFT</th>
            <th className="text-right py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">SAMPLES</th>
            <th className="text-center py-2 px-3 font-display text-[10px] tracking-wider text-cortex-text-muted">STATUS</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m) => {
            const badge = statusBadge[m.status] || statusBadge.insufficient_data!
            return (
              <tr key={`${m.model}-${m.station}`} className="border-b border-cortex-border/50 hover:bg-cortex-elevated/50">
                <td className="py-2 px-3 text-cortex-text-primary font-semibold">{m.model}</td>
                <td className="py-2 px-3 text-right tabular-nums text-cortex-cyan">{m.mae_speed.toFixed(2)}</td>
                <td className="py-2 px-3 text-right tabular-nums text-cortex-text-secondary">{m.bias_speed.toFixed(2)}</td>
                <td className="py-2 px-3 text-right tabular-nums text-cortex-text-secondary">
                  {m.drift_speed !== undefined ? m.drift_speed.toFixed(2) : '—'}
                </td>
                <td className="py-2 px-3 text-right tabular-nums text-cortex-text-muted">{m.sample_count}</td>
                <td className="py-2 px-3 text-center">
                  <span className={cn('px-2 py-0.5 rounded text-[10px] font-display tracking-wider', badge.bg, badge.text)}>
                    {m.status.toUpperCase().replace('_', ' ')}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
